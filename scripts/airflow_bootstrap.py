#!/usr/bin/env python
"""Repo-controlled Airflow preflight, bootstrap, and verification flow."""

from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import subprocess
import urllib.request
from pathlib import Path
from typing import Iterable, Sequence

from cryptography.hazmat.primitives import serialization
from sqlalchemy import text

from plugins.db_manager import DBManager


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIGRATION_DIR = REPO_ROOT / "migrations" / "stats_schema"
DEFAULT_POOL_CONFIG = REPO_ROOT / "config" / "airflow_pools.json"
DEFAULT_REQUIRED_DIRS = (REPO_ROOT / "logs", REPO_ROOT / "data")
CANONICAL_KALSHI_PRIVATE_KEY_PATH = "/run/secrets/kalshi_private_key.pem"
DEFAULT_API_URL = "http://airflow-apiserver:8080/api/v2/version"
DEFAULT_SCHEDULER_HEALTH_URL = "http://airflow-scheduler:8974/health"


def load_required_pools(pool_config_path: Path) -> list[dict]:
    """Return the checked-in pool definitions."""
    raw_pools = json.loads(pool_config_path.read_text(encoding="utf-8"))
    if isinstance(raw_pools, dict) and raw_pools:
        return [
            {"name": name, **definition}
            for name, definition in raw_pools.items()
        ]
    if isinstance(raw_pools, list) and raw_pools:
        return raw_pools
    raise ValueError(
        f"Pool config must be a non-empty JSON object or array: {pool_config_path}"
    )


def run_cli(args: Sequence[str], capture_output: bool = False) -> str | None:
    """Run a CLI command and optionally return stdout."""
    completed = subprocess.run(
        list(args),
        check=True,
        text=True,
        capture_output=capture_output,
    )
    return completed.stdout if capture_output else None


def validate_immutable_runtime(env: dict[str, str] | None = None) -> None:
    """Reject mutable runtime dependency injection."""
    runtime_env = env or dict(os.environ)
    if runtime_env.get("_PIP_ADDITIONAL_REQUIREMENTS"):
        raise ValueError("_PIP_ADDITIONAL_REQUIREMENTS is forbidden in the immutable runtime")


def validate_secret_contract(env: dict[str, str] | None = None) -> None:
    """Enforce the runtime secret boundary for Kalshi credentials."""
    runtime_env = env or dict(os.environ)
    api_key_id = runtime_env.get("KALSHI_API_KEY_ID", "").strip()
    if not api_key_id:
        raise ValueError("KALSHI_API_KEY_ID environment variable is required")

    key_path = runtime_env.get("KALSHI_PRIVATE_KEY_PATH", "").strip()
    if not key_path:
        raise ValueError("KALSHI_PRIVATE_KEY_PATH environment variable is required")

    if key_path != CANONICAL_KALSHI_PRIVATE_KEY_PATH:
        raise ValueError(
            "KALSHI_PRIVATE_KEY_PATH must point at /run/secrets/kalshi_private_key.pem"
        )

    validate_kalshi_private_key_mount(Path(key_path))


def validate_kalshi_private_key_mount(key_path: Path) -> None:
    """Reject broken Kalshi secret mounts before Airflow reports healthy."""
    if not key_path.exists():
        raise FileNotFoundError(f"Kalshi private key not found at {key_path}")

    key_stat = key_path.lstat()
    if not stat.S_ISREG(key_stat.st_mode):
        raise ValueError(f"Kalshi private key must be a regular file: {key_path}")

    pem_bytes = key_path.read_bytes()
    if not pem_bytes.strip():
        raise ValueError(f"Kalshi private key must be a non-empty PEM file: {key_path}")

    try:
        serialization.load_pem_private_key(pem_bytes, password=None)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Kalshi private key must be a parseable PEM private key: {key_path}"
        ) from exc


def chown_tree(path: Path, uid: int, gid: int = 0) -> None:
    """Recursively set ownership on a runtime directory tree."""
    os.chown(path, uid, gid)
    for root, dirnames, filenames in os.walk(path):
        root_path = Path(root)
        os.chown(root_path, uid, gid)
        for dirname in dirnames:
            os.chown(root_path / dirname, uid, gid)
        for filename in filenames:
            os.chown(root_path / filename, uid, gid)


def ensure_runtime_directories(
    required_dirs: Iterable[Path] = DEFAULT_REQUIRED_DIRS,
    uid: int | None = None,
) -> None:
    """Create and own the managed runtime directories."""
    target_uid = uid if uid is not None else int(os.environ.get("AIRFLOW_UID", "50000"))
    for required_dir in required_dirs:
        required_dir.mkdir(parents=True, exist_ok=True)
        chown_tree(required_dir, target_uid)


def assert_required_files(migration_dir: Path, pool_config_path: Path) -> None:
    """Ensure the baked image contains the governed bootstrap inputs."""
    if not migration_dir.exists():
        raise FileNotFoundError(f"Migration directory not found: {migration_dir}")
    if not list(migration_dir.glob("V*.sql")):
        raise FileNotFoundError(f"No checked-in migrations found in {migration_dir}")
    if not pool_config_path.exists():
        raise FileNotFoundError(f"Pool config not found: {pool_config_path}")


def check_database_connection() -> None:
    """Verify PostgreSQL reachability with the shared DB contract."""
    db = DBManager()
    with db.engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def check_socket_service(host: str, port: int, timeout: float = 5.0) -> None:
    """Verify a TCP service is reachable."""
    with socket.create_connection((host, port), timeout=timeout):
        return


def run_schema_command(command: str, migration_dir: Path) -> None:
    """Execute the governed migration runner command."""
    run_cli(
        [
            "python",
            "-m",
            "plugins.schema_migrations",
            command,
            "--migration-dir",
            str(migration_dir),
        ]
    )


def ensure_admin_user(env: dict[str, str] | None = None) -> str:
    """Create the bootstrap admin user if it does not already exist."""
    runtime_env = env or dict(os.environ)
    username = runtime_env.get("_AIRFLOW_WWW_USER_USERNAME", "airflow")
    password = runtime_env.get("_AIRFLOW_WWW_USER_PASSWORD", "airflow")
    firstname = runtime_env.get("_AIRFLOW_WWW_USER_FIRSTNAME", "Airflow")
    lastname = runtime_env.get("_AIRFLOW_WWW_USER_LASTNAME", "Admin")
    email = runtime_env.get("_AIRFLOW_WWW_USER_EMAIL", f"{username}@example.com")

    users = json.loads(
        run_cli(["airflow", "users", "list", "--output", "json"], capture_output=True)
        or "[]"
    )
    if any(
        user.get("username") == username or user.get("email") == email
        for user in users
    ):
        print(f"Admin user already present: {username}")
        return "existing"

    run_cli(
        [
            "airflow",
            "users",
            "create",
            "--username",
            username,
            "--password",
            password,
            "--firstname",
            firstname,
            "--lastname",
            lastname,
            "--role",
            "Admin",
            "--email",
            email,
        ]
    )
    print(f"Created bootstrap admin user: {username}")
    return "created"


def import_pools(pool_config_path: Path) -> None:
    """Create or update required Airflow pools from checked-in JSON."""
    run_cli(["airflow", "pools", "import", str(pool_config_path)])


def list_pools() -> list[dict]:
    """Return Airflow pool metadata."""
    return json.loads(
        run_cli(["airflow", "pools", "list", "--output", "json"], capture_output=True)
        or "[]"
    )


def assert_required_pools(
    required_pools: Sequence[dict],
    existing_pools: Sequence[dict] | None = None,
) -> None:
    """Ensure required pools exist with the checked-in slot counts."""
    present = {
        (pool.get("name") or pool.get("pool")): int(pool["slots"])
        for pool in (existing_pools if existing_pools is not None else list_pools())
    }
    problems: list[str] = []
    for required in required_pools:
        actual_slots = present.get(required["name"])
        if actual_slots is None:
            problems.append(f"missing {required['name']}")
            continue
        if int(required["slots"]) != actual_slots:
            problems.append(
                f"{required['name']} slots mismatch: expected {required['slots']} got {actual_slots}"
            )
    if problems:
        raise RuntimeError("; ".join(problems))


def check_http_endpoint(url: str, timeout: float = 10.0) -> None:
    """Require a successful HTTP response from a readiness endpoint."""
    with urllib.request.urlopen(url, timeout=timeout) as response:
        if response.status >= 400:
            raise RuntimeError(f"Endpoint unhealthy: {url} returned {response.status}")


def run_contract_checks(migration_dir: Path, pool_config_path: Path) -> list[dict]:
    """Validate immutable runtime inputs and return required pools."""
    validate_immutable_runtime()
    validate_secret_contract()
    assert_required_files(migration_dir, pool_config_path)
    check_database_connection()
    check_socket_service("redis", 6379)
    return load_required_pools(pool_config_path)


def preflight(migration_dir: Path, pool_config_path: Path) -> None:
    """Create managed directories and validate bootstrap prerequisites."""
    required_pools = run_contract_checks(migration_dir, pool_config_path)
    ensure_runtime_directories()
    print(
        "Preflight passed with governed migrations and pools: "
        + ", ".join(pool["name"] for pool in required_pools)
    )


def bootstrap_admin(migration_dir: Path, pool_config_path: Path) -> None:
    """Apply metadata and governed schema bootstrap, then seed pools/admin."""
    required_pools = run_contract_checks(migration_dir, pool_config_path)
    run_cli(["airflow", "db", "migrate"])
    run_schema_command("apply", migration_dir)
    run_schema_command("verify", migration_dir)
    ensure_admin_user()
    import_pools(pool_config_path)
    assert_required_pools(required_pools)
    print("Bootstrap admin completed successfully.")


def verify(
    migration_dir: Path,
    pool_config_path: Path,
    api_url: str,
    scheduler_health_url: str,
) -> None:
    """Validate schema ledger, pools, and runtime service readiness."""
    required_pools = run_contract_checks(migration_dir, pool_config_path)
    run_schema_command("verify", migration_dir)
    assert_required_pools(required_pools)
    check_http_endpoint(api_url)
    check_http_endpoint(scheduler_health_url)
    print("Airflow verification completed successfully.")


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("preflight", "bootstrap-admin", "verify"),
        help="Bootstrap stage to execute.",
    )
    parser.add_argument(
        "--migration-dir",
        default=str(DEFAULT_MIGRATION_DIR),
        help="Checked-in stats migration directory baked into the image.",
    )
    parser.add_argument(
        "--pool-config",
        default=str(DEFAULT_POOL_CONFIG),
        help="Checked-in Airflow pool definition JSON baked into the image.",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="Airflow API readiness endpoint for the verify stage.",
    )
    parser.add_argument(
        "--scheduler-health-url",
        default=DEFAULT_SCHEDULER_HEALTH_URL,
        help="Scheduler health endpoint for the verify stage.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    args = build_parser().parse_args(argv)
    migration_dir = Path(args.migration_dir)
    pool_config_path = Path(args.pool_config)

    if args.command == "preflight":
        preflight(migration_dir, pool_config_path)
        return 0
    if args.command == "bootstrap-admin":
        bootstrap_admin(migration_dir, pool_config_path)
        return 0

    verify(
        migration_dir=migration_dir,
        pool_config_path=pool_config_path,
        api_url=args.api_url,
        scheduler_health_url=args.scheduler_health_url,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
