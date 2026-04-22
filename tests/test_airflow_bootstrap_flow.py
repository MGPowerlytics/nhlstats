from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import call, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

with patch("plugins.db_manager.DBManager"):
    import scripts.airflow_bootstrap as airflow_bootstrap


def test_compose_defines_image_bootstrap_services() -> None:
    compose = (REPO_ROOT / "docker-compose.yaml").read_text(encoding="utf-8")

    for required in (
        "airflow-preflight:",
        "airflow-bootstrap-admin:",
        "airflow-verify:",
        "airflow_bootstrap.py",
        "config/airflow_pools.json",
    ):
        assert required in compose

    for forbidden in (
        "airflow-init:",
        "_AIRFLOW_DB_MIGRATE",
        "_AIRFLOW_WWW_USER_CREATE",
    ):
        assert forbidden not in compose


def test_compose_wires_bootstrap_admin_before_steady_state_services() -> None:
    compose = (REPO_ROOT / "docker-compose.yaml").read_text(encoding="utf-8")

    dependency = "airflow-bootstrap-admin:\n        condition: service_completed_successfully"
    assert compose.count(dependency) >= 6
    assert "airflow-apiserver:\n        condition: service_healthy" in compose
    assert "airflow-scheduler:\n        condition: service_healthy" in compose
    assert "_AIRFLOW_WWW_USER_USERNAME: ${_AIRFLOW_WWW_USER_USERNAME:-airflow}" in compose
    assert "KALSHI_API_KEY_ID: ${KALSHI_API_KEY_ID:?KALSHI_API_KEY_ID is required}" in compose
    assert (
        "file: ${KALSHI_PRIVATE_KEY_FILE:?KALSHI_PRIVATE_KEY_FILE must point to a valid PEM private key on the host}"
        in compose
    )


def test_checked_in_pool_config_matches_required_stats_pools() -> None:
    pools = airflow_bootstrap.load_required_pools(
        REPO_ROOT / "config" / "airflow_pools.json"
    )

    assert {pool["name"] for pool in pools} == {
        "stats_nba_pool",
        "stats_nhl_pool",
        "stats_mlb_pool",
        "stats_nfl_pool",
        "stats_fbref_pool",
        "stats_cbb_pool",
        "stats_tennis_pool",
    }
    assert {pool["name"]: pool["slots"] for pool in pools} == {
        "stats_nba_pool": 3,
        "stats_nhl_pool": 1,
        "stats_mlb_pool": 2,
        "stats_nfl_pool": 2,
        "stats_fbref_pool": 1,
        "stats_cbb_pool": 2,
        "stats_tennis_pool": 1,
    }


def test_validate_secret_contract_rejects_non_runtime_private_key_path() -> None:
    with pytest.raises(ValueError, match="KALSHI_PRIVATE_KEY_PATH"):
        airflow_bootstrap.validate_secret_contract(
            {
                "KALSHI_API_KEY_ID": "runtime-key",
                "KALSHI_PRIVATE_KEY_PATH": "/opt/airflow/private_key.pem",
            }
        )


def test_validate_secret_contract_requires_api_key_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key_path = tmp_path / "kalshi_private_key.pem"
    key_path.write_bytes(_generate_test_private_key_pem())
    monkeypatch.setattr(
        airflow_bootstrap,
        "CANONICAL_KALSHI_PRIVATE_KEY_PATH",
        str(key_path),
    )

    with pytest.raises(ValueError, match="KALSHI_API_KEY_ID"):
        airflow_bootstrap.validate_secret_contract(
            {"KALSHI_PRIVATE_KEY_PATH": str(key_path)}
        )


def test_validate_kalshi_private_key_mount_rejects_non_regular_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="regular file"):
        airflow_bootstrap.validate_kalshi_private_key_mount(tmp_path)


def test_validate_kalshi_private_key_mount_rejects_empty_pem(tmp_path: Path) -> None:
    key_path = tmp_path / "kalshi_private_key.pem"
    key_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="non-empty PEM"):
        airflow_bootstrap.validate_kalshi_private_key_mount(key_path)


def test_validate_kalshi_private_key_mount_rejects_unparseable_pem(
    tmp_path: Path,
) -> None:
    key_path = tmp_path / "kalshi_private_key.pem"
    key_path.write_text("-----BEGIN PRIVATE KEY-----\ninvalid\n", encoding="utf-8")

    with pytest.raises(ValueError, match="parseable PEM"):
        airflow_bootstrap.validate_kalshi_private_key_mount(key_path)


def test_validate_kalshi_private_key_mount_accepts_valid_pem(tmp_path: Path) -> None:
    key_path = tmp_path / "kalshi_private_key.pem"
    key_path.write_bytes(_generate_test_private_key_pem())

    airflow_bootstrap.validate_kalshi_private_key_mount(key_path)


def test_validate_immutable_runtime_rejects_runtime_pip_installs() -> None:
    with pytest.raises(ValueError, match="_PIP_ADDITIONAL_REQUIREMENTS"):
        airflow_bootstrap.validate_immutable_runtime(
            {"_PIP_ADDITIONAL_REQUIREMENTS": "pandas==2.2.3"}
        )


def test_ensure_admin_user_creates_missing_account() -> None:
    with patch.object(
        airflow_bootstrap,
        "run_cli",
        side_effect=["[]", None],
    ) as run_cli:
        result = airflow_bootstrap.ensure_admin_user(
            {
                "_AIRFLOW_WWW_USER_USERNAME": "airflow",
                "_AIRFLOW_WWW_USER_PASSWORD": "change-me",
            }
        )

    assert result == "created"
    run_cli.assert_has_calls(
        [
            call(["airflow", "users", "list", "--output", "json"], capture_output=True),
            call(
                [
                    "airflow",
                    "users",
                    "create",
                    "--username",
                    "airflow",
                    "--password",
                    "change-me",
                    "--firstname",
                    "Airflow",
                    "--lastname",
                    "Admin",
                    "--role",
                    "Admin",
                    "--email",
                    "airflow@example.com",
                ]
            ),
        ]
    )


def test_assert_required_pools_fails_when_pool_missing() -> None:
    required = [
        {"name": "stats_nba_pool", "slots": 3},
        {"name": "stats_nhl_pool", "slots": 1},
    ]

    with pytest.raises(RuntimeError, match="stats_nhl_pool"):
        airflow_bootstrap.assert_required_pools(
            required,
            existing_pools=[{"name": "stats_nba_pool", "slots": 3}],
        )


def _generate_test_private_key_pem() -> bytes:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
