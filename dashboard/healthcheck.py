"""Read-only dashboard healthcheck for local and container readiness.

Run locally with:

    python -m dashboard.healthcheck --db-mode optional

The dashboard Docker service runs the stricter container form:

    python -m dashboard.healthcheck --streamlit-url http://localhost:8501/_stcore/health

The healthcheck intentionally performs only ``SELECT`` reads and emits only
sanitized status messages.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd
from jsonschema import Draft202012Validator
from sqlalchemy.exc import SQLAlchemyError

from dashboard import data_layer
from plugins.db_manager import DBManager

DbMode = Literal["required", "optional", "disabled"]

REQUIRED_VIEW_SCHEMAS = tuple(data_layer.VIEW_COLUMNS)
REQUIRED_CONTRACT_SCHEMAS = (*REQUIRED_VIEW_SCHEMAS, "dashboard_empty_state_v1")
APP_PAGE_MODULES = (
    "dashboard.pages.portfolio",
    "dashboard.pages.live_markets",
    "dashboard.pages.tennis_predictions",
    "dashboard.pages.tennis_model_health",
    "dashboard.pages.rankings",
    "dashboard.pages.calibration",
    "dashboard.pages.data_quality",
    "dashboard.pages.bet_detail",
)
SENSITIVE_TOKENS = (
    "select ",
    " from ",
    " join ",
    "postgresql://",
    "postgres://",
    "password",
    "secret",
    "traceback",
    "sqlalchemy",
    "dsn",
)


@dataclass(frozen=True)
class HealthcheckItem:
    """One sanitized healthcheck item."""

    name: str
    ok: bool
    message: str

    def as_dict(self) -> dict[str, str | bool]:
        """Return a JSON-safe representation."""

        return {"name": self.name, "ok": self.ok, "message": self.message}


@dataclass(frozen=True)
class HealthcheckReport:
    """Dashboard healthcheck result."""

    ok: bool
    checks: tuple[HealthcheckItem, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        return {"ok": self.ok, "checks": [check.as_dict() for check in self.checks]}


def _safe_message(message: str) -> str:
    """Return a message that does not expose SQL, DSNs, secrets, or traces."""

    lowered = message.lower()
    if any(token in lowered for token in SENSITIVE_TOKENS):
        return "Details are hidden; check dashboard healthcheck logs."
    return message


def _ok(name: str, message: str) -> HealthcheckItem:
    """Build a passing check item."""

    return HealthcheckItem(name=name, ok=True, message=_safe_message(message))


def _fail(name: str, message: str) -> HealthcheckItem:
    """Build a failing check item."""

    return HealthcheckItem(name=name, ok=False, message=_safe_message(message))


def _check_streamlit_and_app(
    *, streamlit_url: str | None, app_module: str, timeout_seconds: float
) -> list[HealthcheckItem]:
    """Validate Streamlit availability and app/page import readiness."""

    checks: list[HealthcheckItem] = []
    try:
        importlib.import_module("streamlit")
    except Exception:
        return [
            _fail(
                "streamlit",
                "Streamlit is unavailable in the dashboard runtime.",
            )
        ]

    checks.append(_ok("streamlit", "Streamlit is importable."))

    if streamlit_url:
        try:
            request = Request(streamlit_url, method="GET")
            with urlopen(request, timeout=timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
            if status < 200 or status >= 400:
                checks.append(
                    _fail("streamlit_http", "Streamlit readiness endpoint failed.")
                )
            else:
                checks.append(
                    _ok("streamlit_http", "Streamlit readiness endpoint is healthy.")
                )
        except (OSError, URLError, TimeoutError):
            checks.append(
                _fail("streamlit_http", "Streamlit readiness endpoint is unavailable.")
            )

    try:
        app = importlib.import_module(app_module)
        for page_module in APP_PAGE_MODULES:
            importlib.import_module(page_module)
        if not callable(getattr(app, "main", None)):
            checks.append(_fail("dashboard_app", "Dashboard app route is not ready."))
        else:
            checks.append(_ok("dashboard_app", "Dashboard app routes are importable."))
    except Exception:
        checks.append(_fail("dashboard_app", "Dashboard app import failed."))

    return checks


def _load_contract(schema_dir: Path, schema_name: str) -> dict[str, Any]:
    """Load a canonical JSON Schema file."""

    schema_path = schema_dir / f"{schema_name}.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _check_contracts(schema_dir: Path) -> list[HealthcheckItem]:
    """Validate required canonical dashboard contracts."""

    checks: list[HealthcheckItem] = []
    for schema_name in REQUIRED_CONTRACT_SCHEMAS:
        check_name = f"contract:{schema_name}"
        try:
            schema = _load_contract(schema_dir, schema_name)
            Draft202012Validator.check_schema(schema)
        except FileNotFoundError:
            checks.append(_fail(check_name, "Required dashboard contract is missing."))
            continue
        except (json.JSONDecodeError, TypeError):
            checks.append(_fail(check_name, "Required dashboard contract is invalid."))
            continue
        except Exception:
            checks.append(_fail(check_name, "Required dashboard contract is invalid."))
            continue

        if schema_name in data_layer.VIEW_COLUMNS:
            expected_columns = list(data_layer.VIEW_COLUMNS[schema_name])
            actual_columns = list(schema.get("properties", {}))
            required = set(schema.get("required", []))
            if actual_columns != expected_columns or required != set(expected_columns):
                checks.append(
                    _fail(
                        check_name,
                        "Required dashboard contract does not match expected columns.",
                    )
                )
                continue

        checks.append(_ok(check_name, "Required dashboard contract is valid."))

    return checks


def _fetch_df(
    db: Any, query: str, params: dict[str, Any] | None = None
) -> pd.DataFrame:
    """Fetch a DataFrame from a DBManager-compatible object."""

    return db.fetch_df(query, params or {})


def _check_db_reachable(db: Any, db_mode: DbMode) -> tuple[list[HealthcheckItem], bool]:
    """Check database reachability respecting local/test DB mode."""

    if db_mode == "disabled":
        return (
            [_ok("database", "Database checks disabled for local healthcheck.")],
            False,
        )

    try:
        _fetch_df(db, "SELECT 1 AS healthcheck_ok")
        return ([_ok("database", "Database is reachable.")], True)
    except Exception:
        if db_mode == "optional":
            return (
                [
                    _ok(
                        "database",
                        "Database is unreachable; database checks skipped in optional mode.",
                    )
                ],
                False,
            )
        return ([_fail("database", "Database is unreachable.")], False)


def _fetch_relation_type(db: Any, view_name: str) -> str | None:
    """Return the relation type reported by PostgreSQL information_schema."""

    df = _fetch_df(
        db,
        (
            "SELECT table_name, table_type FROM information_schema.tables "
            "WHERE table_schema = CURRENT_SCHEMA() AND table_name = :view_name"
        ),
        {"view_name": view_name},
    )
    if df.empty:
        return None
    return str(df.iloc[0]["table_type"]).upper()


def _fetch_relation_columns(db: Any, view_name: str) -> list[str]:
    """Return relation columns in ordinal order from information_schema."""

    df = _fetch_df(
        db,
        (
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = CURRENT_SCHEMA() AND table_name = :view_name "
            "ORDER BY ordinal_position"
        ),
        {"view_name": view_name},
    )
    return [str(value) for value in df["column_name"].tolist()]


def _check_view_definitions(db: Any) -> list[HealthcheckItem]:
    """Validate required dashboard views exist as views with expected columns."""

    checks: list[HealthcheckItem] = []
    for view_name, expected_columns in data_layer.VIEW_COLUMNS.items():
        check_name = f"view:{view_name}"
        try:
            relation_type = _fetch_relation_type(db, view_name)
            if relation_type is None:
                checks.append(_fail(check_name, "Required dashboard view is missing."))
                continue
            if relation_type != "VIEW":
                checks.append(
                    _fail(check_name, "Required dashboard relation is not a view.")
                )
                continue

            actual_columns = _fetch_relation_columns(db, view_name)
            if actual_columns != list(expected_columns):
                checks.append(
                    _fail(
                        check_name,
                        "Required dashboard view columns do not match the contract.",
                    )
                )
                continue
        except Exception:
            checks.append(
                _fail(check_name, "Required dashboard view definition is unreadable.")
            )
            continue

        checks.append(_ok(check_name, "Required dashboard view definition matches."))

    return checks


def _minimal_read_view(db: Any, view_name: str) -> pd.DataFrame:
    """Run the data-layer read path against one dashboard read model."""

    original_db = data_layer._db
    try:
        data_layer._db = db
        return data_layer._fetch_read_model(view_name, limit=1)
    finally:
        data_layer._db = original_db


def _check_data_layer_reads(db: Any) -> list[HealthcheckItem]:
    """Validate minimal data-layer reads and non-empty data quality checks."""

    checks: list[HealthcheckItem] = []
    for view_name in data_layer.VIEW_COLUMNS:
        check_name = f"read:{view_name}"
        try:
            df = _minimal_read_view(db, view_name)
            if view_name == data_layer.DATA_QUALITY_VIEW and df.empty:
                checks.append(
                    _fail(
                        check_name,
                        "Dashboard data-quality read model returned zero checks.",
                    )
                )
                continue
        except data_layer.DashboardDataError:
            checks.append(_fail(check_name, "Dashboard data-layer read failed."))
            continue
        except SQLAlchemyError:
            checks.append(_fail(check_name, "Dashboard data-layer query failed."))
            continue
        except Exception:
            checks.append(_fail(check_name, "Dashboard data-layer read failed."))
            continue

        checks.append(_ok(check_name, "Dashboard data-layer read succeeded."))

    return checks


def _check_database(db: Any, db_mode: DbMode) -> list[HealthcheckItem]:
    """Run all read-only database checks."""

    checks, reachable = _check_db_reachable(db, db_mode)
    if not reachable:
        return checks

    checks.extend(_check_view_definitions(db))
    checks.extend(_check_data_layer_reads(db))
    return checks


def run_healthcheck(
    *,
    db: Any | None = None,
    schema_dir: Path | None = None,
    streamlit_url: str | None = None,
    app_module: str = "dashboard.app",
    db_mode: DbMode = "required",
    timeout_seconds: float = 3.0,
) -> HealthcheckReport:
    """Run the dashboard healthcheck and return sanitized check results."""

    health_db = db if db is not None else DBManager()
    contract_dir = Path(schema_dir or data_layer.DASHBOARD_SCHEMA_DIR)
    checks = [
        *_check_streamlit_and_app(
            streamlit_url=streamlit_url,
            app_module=app_module,
            timeout_seconds=timeout_seconds,
        ),
        *_check_contracts(contract_dir),
        *_check_database(health_db, db_mode),
    ]
    return HealthcheckReport(
        ok=all(check.ok for check in checks),
        checks=tuple(checks),
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the healthcheck CLI parser."""

    parser = argparse.ArgumentParser(description="Run the dashboard healthcheck.")
    parser.add_argument(
        "--streamlit-url",
        default=os.getenv("DASHBOARD_HEALTHCHECK_URL"),
        help="Optional Streamlit readiness URL, for example /_stcore/health.",
    )
    parser.add_argument(
        "--db-mode",
        choices=("required", "optional", "disabled"),
        default=os.getenv("DASHBOARD_HEALTHCHECK_DB_MODE", "required"),
        help="Database check mode. Container health should use required.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("DASHBOARD_HEALTHCHECK_TIMEOUT_SECONDS", "3.0")),
        help="Network timeout for the optional Streamlit readiness URL.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI healthcheck."""

    args = _build_parser().parse_args(argv)
    report = run_healthcheck(
        streamlit_url=args.streamlit_url,
        db_mode=args.db_mode,
        timeout_seconds=args.timeout_seconds,
    )
    failed_checks = [check.name for check in report.checks if not check.ok]
    if report.ok:
        print("dashboard healthcheck: ok")
        return 0

    print("dashboard healthcheck: failed; failed checks: " + ", ".join(failed_checks))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
