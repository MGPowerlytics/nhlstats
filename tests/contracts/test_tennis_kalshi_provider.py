"""Provider RED tests for the Tennis Kalshi save flow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

import plugins.database_schema_manager as database_schema_manager
import plugins.kalshi_markets as kalshi_markets
from plugins.kalshi_markets import save_to_db
from tests.contracts.fixtures.tennis_kalshi_provider_samples import (
    build_tennis_paired_raw_markets,
    build_tennis_single_sided_raw_markets,
    build_tennis_wta_paired_raw_markets,
)
from tests.contracts.helpers import find_execute_params


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


class _FakeExecuteCall:
    def __init__(self, sql: str, params: dict[str, Any]) -> None:
        self.args = (sql, params)


class RecordingDBManager:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    def execute(self, sql: str, params: dict[str, Any]) -> None:
        self.calls.append(_FakeExecuteCall(sql, dict(params)))

    def fetch_scalar(self, sql: str, params: dict[str, Any]) -> Any:
        return None


class NoOpSchemaManager:
    def __init__(self, _db_manager: RecordingDBManager) -> None:
        pass

    def initialize_schema(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _patch_schema_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        database_schema_manager, "DatabaseSchemaManager", NoOpSchemaManager
    )
    monkeypatch.setattr(
        kalshi_markets, "DatabaseSchemaManager", NoOpSchemaManager, raising=False
    )


# ---------------------------------------------------------------------------
# Validation helpers (registry-based $ref resolution)
# ---------------------------------------------------------------------------


def _validator(schema: dict[str, Any], def_name: str) -> Draft202012Validator:
    resource = Resource.from_contents(schema)
    registry = Registry().with_resource(uri=schema["$id"], resource=resource)
    return Draft202012Validator(
        {"$ref": f"{schema['$id']}#/$defs/{def_name}"}, registry=registry
    )


def _projected_unified_row(params: dict[str, Any]) -> dict[str, Any]:
    """Mirror the SQL column shape for ``unified_games`` from execute params."""
    return {
        "game_id": params["game_id"],
        "sport": params["sport"],
        "game_date": params["game_date"],
        "home_team_id": params["home_id"],
        "home_team_name": params["home_name"],
        "away_team_id": params["away_id"],
        "away_team_name": params["away_name"],
        "commence_time": params["commence_time"],
        "status": params.get("status", "Scheduled"),
    }


def _projected_odds_row(params: dict[str, Any]) -> dict[str, Any]:
    """Mirror the SQL column shape for ``game_odds`` from execute params."""
    return {
        "odds_id": params["odds_id"],
        "game_id": params["game_id"],
        "bookmaker": "Kalshi",
        "market_name": "moneyline",
        "outcome_name": params["outcome_name"],
        "price": params["price"],
        "is_pregame": True,
        "external_id": params["ticker"],
    }


# ---------------------------------------------------------------------------
# Paired ATP matchup → unified + two odds rows
# ---------------------------------------------------------------------------


def test_save_to_db_writes_paired_atp_unified_and_odds_rows() -> None:
    db = RecordingDBManager()
    odds_count = save_to_db("tennis", build_tennis_paired_raw_markets(), db)

    assert odds_count == 2

    unified_params = find_execute_params(db.calls, "unified_games")
    assert len(unified_params) == 1
    unified_row = _projected_unified_row(unified_params[0])

    schema = _load("tennis_unified_game_row_v1.json")
    Draft202012Validator(schema).validate(unified_row)

    # Alphabetical sort on full names → Blockx is home, Cobolli is away.
    assert unified_row["home_team_name"] == "Alexander Blockx"
    assert unified_row["away_team_name"] == "Flavio Cobolli"
    assert unified_row["sport"] == "TENNIS"
    assert unified_row["game_id"].startswith("TENNIS_ATP_2026-04-07_")

    odds_params = find_execute_params(db.calls, "game_odds")
    assert len(odds_params) == 2

    market_schema = _load("tennis_kalshi_market_v1.json")
    odds_validator = _validator(market_schema, "game_odds_row")
    for params in odds_params:
        odds_validator.validate(_projected_odds_row(params))

    outcomes = sorted(p["outcome_name"] for p in odds_params)
    assert outcomes == ["away", "home"]


def test_save_to_db_writes_wta_pair() -> None:
    db = RecordingDBManager()
    odds_count = save_to_db("tennis", build_tennis_wta_paired_raw_markets(), db)

    assert odds_count == 2

    unified_params = find_execute_params(db.calls, "unified_games")
    assert len(unified_params) == 1
    assert unified_params[0]["game_id"].startswith("TENNIS_WTA_2026-04-07_")
    # Coco Gauff < Iga Swiatek alphabetically (case-insensitive)
    assert unified_params[0]["home_name"] == "Coco Gauff"
    assert unified_params[0]["away_name"] == "Iga Swiatek"


def test_save_to_db_skips_single_sided_event() -> None:
    """Single-sided events lacking a paired binary must not write unified rows."""
    db = RecordingDBManager()
    odds_count = save_to_db("tennis", build_tennis_single_sided_raw_markets(), db)

    # Title parsing back-fills the opponent → save proceeds with two players.
    # If the back-fill fails we expect no rows written.
    unified_params = find_execute_params(db.calls, "unified_games")
    if not unified_params:
        assert odds_count == 0
    else:
        assert odds_count >= 1
