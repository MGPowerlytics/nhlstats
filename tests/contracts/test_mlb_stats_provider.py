"""Wave-3 provider-red contract tests for MLB historical stats.

Exercises ``MLBBoxScoreFetcher`` (``plugins.stats.mlb_box_score``) against
the frozen Wave-2 schemas:

* ``mlb_team_game_stats_row_v1`` — core ``team_game_stats`` row contract
* ``mlb_team_game_stats_ext_row_v1`` — extension ``mlb_team_game_stats_ext`` row

Coverage spans both the row-builder (``_build_row``) and the persistence path
(``upsert_rows``) so any drift in either surface is caught at the boundary.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from plugins.stats.mlb_box_score import MLBBoxScoreFetcher
from tests.contracts.helpers import (
    find_execute_params,
    serialize_contract_payload,
    validate_contract_payload,
)


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Realistic raw inputs (mirroring statsapi.mlb.com response shapes)
# ---------------------------------------------------------------------------


_HOME_BATTING = {
    "hits": 11,
    "doubles": 2,
    "triples": 0,
    "homeRuns": 2,
    "baseOnBalls": 4,
    "hitByPitch": 0,
    "sacFlies": 0,
    "atBats": 34,
    "strikeOuts": 8,
    "leftOnBase": 7,
    "rbi": 6,
    "stolenBases": 1,
    "obp": "0.395",
    "slg": "0.588",
}

_HOME_PITCHING = {"inningsPitched": "9.0", "earnedRuns": 3}
_HOME_FIELDING = {"errors": 0}

_AWAY_BATTING = {
    "hits": 7,
    "doubles": 1,
    "triples": 0,
    "homeRuns": 1,
    "baseOnBalls": 2,
    "hitByPitch": 0,
    "sacFlies": 0,
    "atBats": 33,
    "strikeOuts": 10,
    "leftOnBase": 6,
    "rbi": 3,
    "stolenBases": 0,
    "obp": "0.270",
    "slg": "0.333",
}

_AWAY_PITCHING = {"inningsPitched": "9.0", "earnedRuns": 6}
_AWAY_FIELDING = {"errors": 1}


def _build_provider_rows() -> list[dict]:
    fetcher = MLBBoxScoreFetcher(db=MagicMock())
    return [
        fetcher._build_row(
            game_id="745431",
            game_date=date(2025, 4, 15),
            season="2025",
            side="home",
            team_abbr="NYY",
            opp_abbr="BOS",
            runs_for=6,
            runs_against=3,
            batting=_HOME_BATTING,
            pitching=_HOME_PITCHING,
            fielding=_HOME_FIELDING,
        ),
        fetcher._build_row(
            game_id="745431",
            game_date=date(2025, 4, 15),
            season="2025",
            side="away",
            team_abbr="BOS",
            opp_abbr="NYY",
            runs_for=3,
            runs_against=6,
            batting=_AWAY_BATTING,
            pitching=_AWAY_PITCHING,
            fielding=_AWAY_FIELDING,
        ),
    ]


CORE_FIELDS = (
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


def _core_payload(row: dict) -> dict:
    return {field: row[field] for field in CORE_FIELDS}


def _ext_payload(row: dict) -> dict:
    return {"game_id": row["game_id"], "team": row["team"], **row["ext"]}


# ---------------------------------------------------------------------------
# Row-builder: _build_row
# ---------------------------------------------------------------------------


def test_build_row_emits_two_rows_one_per_side() -> None:
    rows = _build_provider_rows()
    assert len(rows) == 2
    assert {row["is_home"] for row in rows} == {True, False}
    assert {row["sport"] for row in rows} == {"MLB"}


def test_build_row_core_payload_satisfies_team_game_stats_contract() -> None:
    rows = _build_provider_rows()
    schema = _load_schema("mlb_team_game_stats_row_v1.json")
    for row in rows:
        validate_contract_payload(serialize_contract_payload(_core_payload(row)), schema)


def test_build_row_extension_payload_satisfies_ext_contract() -> None:
    rows = _build_provider_rows()
    schema = _load_schema("mlb_team_game_stats_ext_row_v1.json")
    for row in rows:
        validate_contract_payload(serialize_contract_payload(_ext_payload(row)), schema)


def test_build_row_uses_native_gamepk_string_for_game_id() -> None:
    """game_id must be the native MLB gamePk string (matches unified_games)."""
    rows = _build_provider_rows()
    for row in rows:
        assert row["game_id"] == "745431"
        assert row["game_id"].isdigit()


def test_build_row_season_is_four_digit_string() -> None:
    """season must be a 4-digit string per the frozen contract pattern ^[0-9]{4}$."""
    rows = _build_provider_rows()
    for row in rows:
        assert isinstance(row["season"], str)
        assert len(row["season"]) == 4
        assert row["season"].isdigit()


# ---------------------------------------------------------------------------
# Persistence path: upsert_rows
# ---------------------------------------------------------------------------


def test_upsert_rows_persists_contract_valid_core_and_extension_params() -> None:
    rows = _build_provider_rows()
    db = MagicMock()
    fetcher = MLBBoxScoreFetcher(db=db)

    upserted = fetcher.upsert_rows(rows)
    assert upserted == 2

    core_rows = find_execute_params(db.execute.call_args_list, "team_game_stats")
    ext_rows = find_execute_params(db.execute.call_args_list, "mlb_team_game_stats_ext")

    # Two writes per row across both tables.
    assert len(core_rows) == 2
    assert len(ext_rows) == 2

    core_schema = _load_schema("mlb_team_game_stats_row_v1.json")
    ext_schema = _load_schema("mlb_team_game_stats_ext_row_v1.json")

    for row in core_rows:
        validate_contract_payload(serialize_contract_payload(row), core_schema)
    for row in ext_rows:
        validate_contract_payload(serialize_contract_payload(row), ext_schema)


def test_upsert_rows_extension_inherits_native_game_id_and_team_abbr() -> None:
    rows = _build_provider_rows()
    db = MagicMock()
    fetcher = MLBBoxScoreFetcher(db=db)

    fetcher.upsert_rows(rows)
    ext_rows = find_execute_params(db.execute.call_args_list, "mlb_team_game_stats_ext")

    assert {(r["game_id"], r["team"]) for r in ext_rows} == {
        ("745431", "NYY"),
        ("745431", "BOS"),
    }
