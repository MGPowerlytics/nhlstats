from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher
from tests.contracts.fixtures.epl_stats_samples import (
    build_epl_soccer_stats_ext_rows,
    build_epl_stats_csv_row,
    build_epl_team_game_stats_rows,
)
from tests.contracts.helpers import (
    find_execute_params,
    serialize_contract_payload,
    validate_contract_payload,
)

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"
TEAM_ROW_FIELDS = (
    "game_id",
    "sport",
    "team",
    "opponent",
    "is_home",
    "game_date",
    "season",
    "points_for",
    "points_against",
    "won",
    "margin",
)


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def _build_provider_rows() -> list[dict]:
    fetcher = SoccerBoxScoreFetcher(sport="EPL", db=MagicMock())
    return fetcher._build_team_rows(build_epl_stats_csv_row())


def _core_contract_payload(row: dict) -> dict:
    return {field: row[field] for field in TEAM_ROW_FIELDS}


def _extension_contract_payload(row: dict) -> dict:
    return {
        "game_id": row["game_id"],
        "team": row["team"],
        **row["ext"],
    }


def test_build_team_rows_returns_two_epl_team_rows() -> None:
    """One EPL match should still yield exactly one home row and one away row."""
    rows = _build_provider_rows()

    assert len(rows) == 2
    assert {row["is_home"] for row in rows} == {True, False}


def test_build_team_rows_match_frozen_team_game_stats_contract() -> None:
    """Real SoccerBoxScoreFetcher rows must satisfy the frozen EPL team row contract."""
    rows = _build_provider_rows()
    schema = _load_schema("epl_team_game_stats_row_v1.json")

    for row in rows:
        validate_contract_payload(serialize_contract_payload(_core_contract_payload(row)), schema)


def test_build_team_rows_match_frozen_soccer_extension_contract() -> None:
    """Real SoccerBoxScoreFetcher extension rows must satisfy the frozen EPL ext contract."""
    rows = _build_provider_rows()
    schema = _load_schema("epl_soccer_stats_ext_row_v1.json")

    for row in rows:
        validate_contract_payload(
            serialize_contract_payload(_extension_contract_payload(row)),
            schema,
        )


def test_build_team_rows_expose_storage_identity_drift() -> None:
    """Provider rows must match the EPL storage-compatible game_id semantics."""
    rows = _build_provider_rows()
    expected_rows = build_epl_team_game_stats_rows()

    assert [row["game_id"] for row in rows] == [row["game_id"] for row in expected_rows]


def test_build_team_rows_expose_storage_season_drift() -> None:
    """Provider rows must match the frozen EPL season representation."""
    rows = _build_provider_rows()
    expected_rows = build_epl_team_game_stats_rows()

    assert [row["season"] for row in rows] == [row["season"] for row in expected_rows]


def test_upsert_rows_persist_contract_valid_core_and_extension_params() -> None:
    """Upsert params must remain contract-valid where stats rows hit EPL storage."""
    provider_rows = _build_provider_rows()
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [(provider_rows[0]["game_id"],)]
    fetcher = SoccerBoxScoreFetcher(sport="EPL", db=db)

    upserted = fetcher.upsert_rows(provider_rows)

    assert upserted == 2

    core_rows = find_execute_params(db.execute.call_args_list, "team_game_stats")
    extension_rows = find_execute_params(db.execute.call_args_list, "soccer_team_game_stats_ext")

    assert len(core_rows) == 2
    assert len(extension_rows) == 2

    core_schema = _load_schema("epl_team_game_stats_row_v1.json")
    extension_schema = _load_schema("epl_soccer_stats_ext_row_v1.json")

    for row in core_rows:
        validate_contract_payload(serialize_contract_payload(row), core_schema)
    for row in extension_rows:
        validate_contract_payload(serialize_contract_payload(row), extension_schema)


def test_upsert_rows_preserve_canonical_game_reference_for_extension_rows() -> None:
    """Extension upserts must use the same EPL-compatible game reference as frozen fixtures."""
    provider_rows = _build_provider_rows()
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [(provider_rows[0]["game_id"],)]
    fetcher = SoccerBoxScoreFetcher(sport="EPL", db=db)

    fetcher.upsert_rows(provider_rows)

    extension_rows = find_execute_params(db.execute.call_args_list, "soccer_team_game_stats_ext")

    assert extension_rows == build_epl_soccer_stats_ext_rows()
