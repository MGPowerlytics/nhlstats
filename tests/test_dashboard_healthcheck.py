"""Focused tests for the read-only dashboard healthcheck."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from sqlalchemy.exc import SQLAlchemyError

from dashboard import data_layer
from dashboard import healthcheck


class FakeHealthcheckDB:
    """DBManager-compatible fake for read-only healthcheck queries."""

    def __init__(
        self,
        *,
        missing_views: set[str] | None = None,
        zero_data_quality: bool = False,
        db_error: bool = False,
        read_error_views: set[str] | None = None,
        mismatched_columns: set[str] | None = None,
    ) -> None:
        self.missing_views = missing_views or set()
        self.zero_data_quality = zero_data_quality
        self.db_error = db_error
        self.read_error_views = read_error_views or set()
        self.mismatched_columns = mismatched_columns or set()
        self.queries: list[str] = []

    def fetch_df(
        self, query: str, params: dict[str, Any] | None = None
    ) -> pd.DataFrame:
        """Return deterministic healthcheck frames and record query text."""

        self.queries.append(query)
        if self.db_error:
            raise SQLAlchemyError(
                "SELECT secret FROM postgresql://user:password@host/database"
            )

        params = params or {}
        normalized = " ".join(query.lower().split())
        view_name = str(params.get("view_name", ""))

        if normalized.startswith("select 1 as healthcheck_ok"):
            return pd.DataFrame([{"healthcheck_ok": 1}])

        if "from information_schema.tables" in normalized:
            if view_name in self.missing_views:
                return pd.DataFrame(columns=["table_name", "table_type"])
            return pd.DataFrame(
                [{"table_name": view_name, "table_type": "VIEW"}],
                columns=["table_name", "table_type"],
            )

        if "from information_schema.columns" in normalized:
            columns = list(data_layer.VIEW_COLUMNS[view_name])
            if view_name in self.mismatched_columns:
                columns = columns[:-1]
            return pd.DataFrame(
                [{"column_name": column} for column in columns],
                columns=["column_name"],
            )

        for required_view, columns in data_layer.VIEW_COLUMNS.items():
            if f" from {required_view}" not in normalized:
                continue
            if required_view in self.read_error_views:
                raise SQLAlchemyError(
                    "SELECT secret FROM postgresql://user:password@host/database"
                )
            if required_view == data_layer.DATA_QUALITY_VIEW:
                if self.zero_data_quality:
                    return pd.DataFrame(columns=columns)
                return pd.DataFrame(
                    [
                        {
                            "check_name": "dashboard_data_quality_v1_exists",
                            "relation_name": "dashboard_data_quality_v1",
                            "relation_type": "view",
                            "status": "pass",
                            "row_count": None,
                            "freshness_timestamp": None,
                            "max_allowed_lag_minutes": None,
                            "actual_lag_minutes": None,
                            "message": "Dashboard view exists",
                            "checked_at_utc": datetime(
                                2026, 5, 3, 12, tzinfo=timezone.utc
                            ),
                        }
                    ],
                    columns=columns,
                )
            return pd.DataFrame(columns=columns)

        raise AssertionError(f"Unexpected healthcheck query: {query}")


@pytest.fixture()
def import_ready_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make Streamlit/app imports deterministic for healthcheck tests."""

    real_import_module = importlib.import_module

    def fake_import_module(name: str) -> Any:
        if name == "streamlit":
            return SimpleNamespace()
        if name == "dashboard.app":
            return SimpleNamespace(main=lambda: None)
        if name in healthcheck.APP_PAGE_MODULES:
            return SimpleNamespace(render=lambda: None)
        return real_import_module(name)

    monkeypatch.setattr(healthcheck.importlib, "import_module", fake_import_module)


def _run_fake_healthcheck(
    db: FakeHealthcheckDB, **kwargs: Any
) -> healthcheck.HealthcheckReport:
    return healthcheck.run_healthcheck(
        db=db,
        streamlit_url=None,
        db_mode=kwargs.pop("db_mode", "required"),
        **kwargs,
    )


def test_dashboard_healthcheck_passes_and_uses_read_only_queries(
    import_ready_app: None,
) -> None:
    """Healthy app, contracts, views, DQ checks, and reads pass without mutations."""

    db = FakeHealthcheckDB()
    report = _run_fake_healthcheck(db)

    assert report.ok is True
    assert all(query.lstrip().upper().startswith("SELECT") for query in db.queries)
    assert any(
        check.name == "read:dashboard_data_quality_v1" for check in report.checks
    )


def test_dashboard_healthcheck_fails_when_contract_missing(
    tmp_path: Any,
    import_ready_app: None,
) -> None:
    """Missing canonical contracts fail before dashboard deployment is healthy."""

    report = _run_fake_healthcheck(FakeHealthcheckDB(), schema_dir=tmp_path)

    assert report.ok is False
    assert any(
        check.name == "contract:dashboard_portfolio_v1" and not check.ok
        for check in report.checks
    )


def test_dashboard_healthcheck_fails_when_required_view_missing(
    import_ready_app: None,
) -> None:
    """Missing governed dashboard views fail the healthcheck."""

    report = _run_fake_healthcheck(
        FakeHealthcheckDB(missing_views={data_layer.LIVE_MARKETS_VIEW})
    )

    assert report.ok is False
    assert any(
        check.name == f"view:{data_layer.LIVE_MARKETS_VIEW}" and not check.ok
        for check in report.checks
    )


def test_dashboard_healthcheck_fails_when_view_definition_mismatches_contract(
    import_ready_app: None,
) -> None:
    """Dashboard view column drift fails even when the view exists."""

    report = _run_fake_healthcheck(
        FakeHealthcheckDB(mismatched_columns={data_layer.PORTFOLIO_VIEW})
    )

    assert report.ok is False
    assert any(
        check.name == f"view:{data_layer.PORTFOLIO_VIEW}" and not check.ok
        for check in report.checks
    )


def test_dashboard_healthcheck_required_db_mode_fails_when_db_unavailable(
    import_ready_app: None,
) -> None:
    """Container health fails when the required database is unavailable."""

    report = _run_fake_healthcheck(FakeHealthcheckDB(db_error=True))

    assert report.ok is False
    assert any(check.name == "database" and not check.ok for check in report.checks)
    assert "postgresql://" not in repr(report.as_dict())
    assert "password" not in repr(report.as_dict()).lower()
    assert "select " not in repr(report.as_dict()).lower()


def test_dashboard_healthcheck_optional_db_mode_skips_unreachable_db(
    import_ready_app: None,
) -> None:
    """Local/test mode can validate app and contracts without live credentials."""

    report = _run_fake_healthcheck(
        FakeHealthcheckDB(db_error=True),
        db_mode="optional",
    )

    assert report.ok is True
    assert any(check.name == "database" and check.ok for check in report.checks)


def test_dashboard_healthcheck_fails_when_streamlit_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Streamlit import failures make the dashboard unhealthy."""

    real_import_module = importlib.import_module

    def fail_streamlit_import(name: str) -> Any:
        if name == "streamlit":
            raise ImportError("streamlit missing")
        return real_import_module(name)

    monkeypatch.setattr(healthcheck.importlib, "import_module", fail_streamlit_import)

    report = _run_fake_healthcheck(FakeHealthcheckDB(), db_mode="disabled")

    assert report.ok is False
    assert any(check.name == "streamlit" and not check.ok for check in report.checks)


def test_dashboard_healthcheck_fails_when_app_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """App/page import failures make the dashboard unhealthy."""

    real_import_module = importlib.import_module

    def fail_app_import(name: str) -> Any:
        if name == "streamlit":
            return SimpleNamespace()
        if name == "dashboard.app":
            raise RuntimeError("broken app")
        return real_import_module(name)

    monkeypatch.setattr(healthcheck.importlib, "import_module", fail_app_import)

    report = _run_fake_healthcheck(FakeHealthcheckDB(), db_mode="disabled")

    assert report.ok is False
    assert any(
        check.name == "dashboard_app" and not check.ok for check in report.checks
    )


def test_dashboard_healthcheck_fails_when_data_quality_has_zero_checks(
    import_ready_app: None,
) -> None:
    """dashboard_data_quality_v1 returning zero rows is a contract failure."""

    report = _run_fake_healthcheck(FakeHealthcheckDB(zero_data_quality=True))

    assert report.ok is False
    assert any(
        check.name == f"read:{data_layer.DATA_QUALITY_VIEW}" and not check.ok
        for check in report.checks
    )


def test_dashboard_healthcheck_fails_on_sanitized_query_error(
    import_ready_app: None,
) -> None:
    """Data-layer query errors fail without exposing SQL, DSNs, or secrets."""

    report = _run_fake_healthcheck(
        FakeHealthcheckDB(read_error_views={data_layer.RANKINGS_VIEW})
    )
    rendered = repr(report.as_dict()).lower()

    assert report.ok is False
    assert any(
        check.name == f"read:{data_layer.RANKINGS_VIEW}" and not check.ok
        for check in report.checks
    )
    assert "postgresql://" not in rendered
    assert "password" not in rendered
    assert "select " not in rendered
