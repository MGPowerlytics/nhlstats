from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from jsonschema import ValidationError

from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher
from tests.contracts.helpers import validate_contract_payload

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"
TEAM_ROW_REQUIRED_FIELDS = (
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


def _load_schema(filename: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def _build_canonical_team_rows() -> list[dict[str, Any]]:
    return [
        {
            "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
            "sport": "EPL",
            "team": "Manchester City",
            "opponent": "Tottenham Hotspur",
            "is_home": True,
            "game_date": "2025-08-16",
            "season": "2526",
            "points_for": 2,
            "points_against": 1,
            "won": True,
            "margin": 1,
        },
        {
            "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
            "sport": "EPL",
            "team": "Tottenham Hotspur",
            "opponent": "Manchester City",
            "is_home": False,
            "game_date": "2025-08-16",
            "season": "2526",
            "points_for": 1,
            "points_against": 2,
            "won": False,
            "margin": -1,
        },
    ]


def _build_canonical_extension_rows() -> list[dict[str, Any]]:
    return [
        {
            "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
            "team": "Manchester City",
            "shots": 15,
            "shots_on_target": 6,
            "possession_pct": None,
            "passes": None,
            "pass_accuracy": None,
            "xg": None,
            "xga": None,
            "fouls": 8,
            "yellow_cards": 1,
            "red_cards": 0,
            "corners": 7,
            "offsides": None,
            "saves": None,
        },
        {
            "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
            "team": "Tottenham Hotspur",
            "shots": 10,
            "shots_on_target": 4,
            "possession_pct": None,
            "passes": None,
            "pass_accuracy": None,
            "xg": None,
            "xga": None,
            "fouls": 11,
            "yellow_cards": 2,
            "red_cards": 0,
            "corners": 3,
            "offsides": None,
            "saves": None,
        },
    ]


def _build_current_fetcher_rows() -> list[dict[str, Any]]:
    fetcher = SoccerBoxScoreFetcher(sport="EPL", db=MagicMock())
    row = pd.Series(
        {
            "Date": pd.Timestamp("2025-08-16"),
            "HomeTeam": "Manchester City",
            "AwayTeam": "Tottenham Hotspur",
            "FTHG": 2,
            "FTAG": 1,
            "FTR": "H",
            "HS": 15,
            "AS": 10,
            "HST": 6,
            "AST": 4,
            "HF": 8,
            "AF": 11,
            "HY": 1,
            "AY": 2,
            "HR": 0,
            "AR": 0,
            "HC": 7,
            "AC": 3,
        }
    )
    return fetcher._build_team_rows(row)


def _team_contract_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = {field: row[field] for field in TEAM_ROW_REQUIRED_FIELDS}
    game_date = payload["game_date"]
    if hasattr(game_date, "isoformat"):
        payload["game_date"] = game_date.isoformat()
    return payload


def _extension_contract_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "game_id": row["game_id"],
        "team": row["team"],
        **row["ext"],
    }


def test_team_game_stats_schema_defines_canonical_contract() -> None:
    """The EPL core stats schema freezes required fields and identity semantics."""
    schema = _load_schema("epl_team_game_stats_row_v1.json")

    assert schema["title"] == "EPL team_game_stats Row Contract"
    assert schema["required"] == list(TEAM_ROW_REQUIRED_FIELDS)
    assert schema["properties"]["sport"]["const"] == "EPL"
    assert schema["properties"]["season"]["pattern"] == "^[0-9]{4}$"


def test_soccer_stats_extension_schema_defines_canonical_contract() -> None:
    """The EPL soccer extension schema freezes the consumer-visible stat payload."""
    schema = _load_schema("epl_soccer_stats_ext_row_v1.json")

    assert schema["title"] == "EPL soccer_team_game_stats_ext Row Contract"
    assert schema["required"] == [
        "game_id",
        "team",
        "shots",
        "shots_on_target",
        "fouls",
        "yellow_cards",
        "red_cards",
        "corners",
    ]
    assert schema["properties"]["game_id"]["pattern"] == "^EPL_[0-9]{8}_[A-Z0-9]+_[A-Z0-9]+$"


def test_canonical_team_rows_satisfy_contract() -> None:
    """A deterministic EPL match produces exactly two valid team_game_stats rows."""
    rows = _build_canonical_team_rows()

    assert len(rows) == 2

    schema = _load_schema("epl_team_game_stats_row_v1.json")
    for row in rows:
        validate_contract_payload(row, schema)


def test_canonical_soccer_extension_rows_satisfy_contract() -> None:
    """A deterministic EPL match produces schema-valid soccer extension payloads."""
    rows = _build_canonical_extension_rows()

    assert len(rows) == 2

    schema = _load_schema("epl_soccer_stats_ext_row_v1.json")
    for row in rows:
        validate_contract_payload(row, schema)


@pytest.mark.parametrize("missing_field", ["game_id", "team", "season", "points_for", "won"])
def test_team_game_stats_contract_rejects_missing_core_fields(missing_field: str) -> None:
    """Missing core fields fail fast before historical stats validation runs."""
    row = dict(_build_canonical_team_rows()[0])
    row.pop(missing_field)

    with pytest.raises(ValidationError):
        validate_contract_payload(row, _load_schema("epl_team_game_stats_row_v1.json"))


@pytest.mark.parametrize(
    "payload",
    [
        {
            "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
            "team": "Manchester City",
            "shots": "15",
            "shots_on_target": 6,
            "fouls": 8,
            "yellow_cards": 1,
            "red_cards": 0,
            "corners": 7,
        },
        {
            "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
            "team": "Manchester City",
            "shots": 15,
            "shots_on_target": 6,
            "fouls": 8,
            "yellow_cards": 1,
            "red_cards": 0,
            "corners": 7,
            "unexpected": 99,
        },
    ],
)
def test_soccer_extension_contract_rejects_malformed_payloads(
    payload: dict[str, Any],
) -> None:
    """Malformed extension payloads fail explicitly instead of being coerced."""
    with pytest.raises(ValidationError):
        validate_contract_payload(payload, _load_schema("epl_soccer_stats_ext_row_v1.json"))


def test_fetcher_output_boundary_requires_exactly_two_team_rows_per_match() -> None:
    """The historical stats consumer freezes a two-row home/away output boundary."""
    rows = _build_current_fetcher_rows()

    assert len(rows) == 2
    assert {row["is_home"] for row in rows} == {True, False}


def test_current_fetcher_core_rows_show_identity_and_season_drift() -> None:
    """Current fetcher output must align with approved EPL identity and season semantics."""
    rows = _build_current_fetcher_rows()
    schema = _load_schema("epl_team_game_stats_row_v1.json")

    for row in rows:
        validate_contract_payload(_team_contract_payload(row), schema)


def test_current_fetcher_rows_show_season_representation_drift() -> None:
    """Current fetcher season labels must converge on the approved EPL representation."""
    rows = _build_current_fetcher_rows()

    for row in rows:
        assert row["season"] == "2526"


def test_current_fetcher_extension_rows_show_identity_drift() -> None:
    """Extension payloads inherit the same approved EPL game identity boundary."""
    rows = _build_current_fetcher_rows()
    schema = _load_schema("epl_soccer_stats_ext_row_v1.json")

    for row in rows:
        validate_contract_payload(_extension_contract_payload(row), schema)
