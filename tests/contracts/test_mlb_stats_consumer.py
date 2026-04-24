"""Wave-2 consumer-red contract tests for MLB historical box-score writes.

Locks the canonical row shape that ``MLBBoxScoreFetcher.upsert_rows`` writes
into ``team_game_stats`` and ``mlb_team_game_stats_ext``. Sport='MLB'
(uppercase), 3-letter team abbreviations, season is the four-digit year, and
``additionalProperties: false`` is used so that any new column drift is
surfaced immediately.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from tests.contracts.fixtures.mlb_stats_samples import (
    build_mlb_box_score_fetcher_rows,
    build_mlb_team_game_stats_ext_rows,
    build_mlb_team_game_stats_rows,
)
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

EXT_ROW_REQUIRED_FIELDS = (
    "game_id",
    "team",
    "hits",
    "errors",
    "lob",
    "doubles",
    "triples",
    "home_runs",
    "rbi",
    "stolen_bases",
    "strikeouts",
    "walks",
    "at_bats",
    "obp",
    "slg",
    "ops",
    "woba",
    "era",
)


def _load_schema(filename: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def _team_contract_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = {field: row[field] for field in TEAM_ROW_REQUIRED_FIELDS}
    game_date = payload["game_date"]
    if hasattr(game_date, "isoformat"):
        payload["game_date"] = game_date.isoformat()
    return payload


def _extension_contract_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {"game_id": row["game_id"], "team": row["team"], **row["ext"]}


# ---------------------------------------------------------------------------
# Schema-shape invariants
# ---------------------------------------------------------------------------


def test_team_game_stats_schema_defines_canonical_contract() -> None:
    schema = _load_schema("mlb_team_game_stats_row_v1.json")

    assert schema["title"] == "MLB team_game_stats Row Contract"
    assert schema["required"] == list(TEAM_ROW_REQUIRED_FIELDS)
    assert schema["properties"]["sport"]["const"] == "MLB"
    assert schema["properties"]["season"]["pattern"] == "^[0-9]{4}$"
    assert schema["additionalProperties"] is False


def test_mlb_team_game_stats_ext_schema_defines_canonical_contract() -> None:
    schema = _load_schema("mlb_team_game_stats_ext_row_v1.json")

    assert schema["title"] == "MLB mlb_team_game_stats_ext Row Contract"
    assert schema["required"] == list(EXT_ROW_REQUIRED_FIELDS)
    assert schema["properties"]["game_id"]["pattern"] == "^[0-9]+$"
    assert schema["properties"]["team"]["pattern"] == "^[A-Z]{2,4}$"
    assert schema["additionalProperties"] is False


# ---------------------------------------------------------------------------
# Positive fixture validation
# ---------------------------------------------------------------------------


def test_canonical_team_rows_satisfy_contract() -> None:
    rows = build_mlb_team_game_stats_rows()

    assert len(rows) == 2
    assert {row["is_home"] for row in rows} == {True, False}

    schema = _load_schema("mlb_team_game_stats_row_v1.json")
    for row in rows:
        validate_contract_payload(row, schema)


def test_canonical_extension_rows_satisfy_contract() -> None:
    rows = build_mlb_team_game_stats_ext_rows()

    assert len(rows) == 2

    schema = _load_schema("mlb_team_game_stats_ext_row_v1.json")
    for row in rows:
        validate_contract_payload(row, schema)


def test_fetcher_shaped_rows_split_into_contract_valid_core_and_ext() -> None:
    """Rows shaped like ``MLBBoxScoreFetcher._build_row`` split cleanly across both tables."""
    fetcher_rows = build_mlb_box_score_fetcher_rows()

    assert len(fetcher_rows) == 2
    assert {row["is_home"] for row in fetcher_rows} == {True, False}

    core_schema = _load_schema("mlb_team_game_stats_row_v1.json")
    ext_schema = _load_schema("mlb_team_game_stats_ext_row_v1.json")

    for row in fetcher_rows:
        validate_contract_payload(_team_contract_payload(row), core_schema)
        validate_contract_payload(_extension_contract_payload(row), ext_schema)


# ---------------------------------------------------------------------------
# Negative cases — core team_game_stats row
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_field",
    ["game_id", "sport", "team", "opponent", "is_home", "game_date", "season",
     "points_for", "points_against", "won", "margin"],
)
def test_team_game_stats_contract_rejects_missing_core_fields(
    missing_field: str,
) -> None:
    row = dict(build_mlb_team_game_stats_rows()[0])
    row.pop(missing_field)

    with pytest.raises(ValidationError):
        validate_contract_payload(
            row, _load_schema("mlb_team_game_stats_row_v1.json")
        )


def test_team_game_stats_contract_rejects_lowercase_sport() -> None:
    row = build_mlb_team_game_stats_rows()[0]
    row["sport"] = "mlb"

    with pytest.raises(ValidationError):
        validate_contract_payload(
            row, _load_schema("mlb_team_game_stats_row_v1.json")
        )


def test_team_game_stats_contract_rejects_non_mlb_sport() -> None:
    row = build_mlb_team_game_stats_rows()[0]
    row["sport"] = "EPL"

    with pytest.raises(ValidationError):
        validate_contract_payload(
            row, _load_schema("mlb_team_game_stats_row_v1.json")
        )


def test_team_game_stats_contract_rejects_full_team_name() -> None:
    """Production writes 3-letter abbreviations; full names must be rejected."""
    row = build_mlb_team_game_stats_rows()[0]
    row["team"] = "New York Yankees"

    with pytest.raises(ValidationError):
        validate_contract_payload(
            row, _load_schema("mlb_team_game_stats_row_v1.json")
        )


def test_team_game_stats_contract_rejects_unknown_top_level_field() -> None:
    row = build_mlb_team_game_stats_rows()[0]
    row["pace"] = 12.34

    with pytest.raises(ValidationError):
        validate_contract_payload(
            row, _load_schema("mlb_team_game_stats_row_v1.json")
        )


def test_team_game_stats_contract_rejects_two_digit_season() -> None:
    row = build_mlb_team_game_stats_rows()[0]
    row["season"] = "25"

    with pytest.raises(ValidationError):
        validate_contract_payload(
            row, _load_schema("mlb_team_game_stats_row_v1.json")
        )


# ---------------------------------------------------------------------------
# Negative cases — extension row
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_field",
    ["game_id", "team", "hits", "obp", "slg", "ops", "woba", "era"],
)
def test_extension_contract_rejects_missing_required_fields(
    missing_field: str,
) -> None:
    row = dict(build_mlb_team_game_stats_ext_rows()[0])
    row.pop(missing_field)

    with pytest.raises(ValidationError):
        validate_contract_payload(
            row, _load_schema("mlb_team_game_stats_ext_row_v1.json")
        )


def test_extension_contract_rejects_unknown_top_level_field() -> None:
    row = build_mlb_team_game_stats_ext_rows()[0]
    row["xera"] = 3.21

    with pytest.raises(ValidationError):
        validate_contract_payload(
            row, _load_schema("mlb_team_game_stats_ext_row_v1.json")
        )


@pytest.mark.parametrize(
    "payload_override",
    [
        {"hits": "11"},  # wrong type
        {"obp": 1.5},  # out of range
        {"slg": -0.1},  # negative
        {"era": -1.0},  # negative
    ],
)
def test_extension_contract_rejects_malformed_payloads(
    payload_override: dict[str, Any],
) -> None:
    row = build_mlb_team_game_stats_ext_rows()[0]
    row.update(payload_override)

    with pytest.raises(ValidationError):
        validate_contract_payload(
            row, _load_schema("mlb_team_game_stats_ext_row_v1.json")
        )
