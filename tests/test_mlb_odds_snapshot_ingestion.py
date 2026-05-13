"""Tests for MLB odds snapshot ingestion and free historical odds support."""

from __future__ import annotations

import json
from pathlib import Path
from plugins.the_odds_api import TheOddsAPI
from plugins.mlb_modeling.free_odds_sources import (
    GITHUB_SPORTSBOOKREVIEW_SOURCE,
    PRINCETON_HISTORICAL_SOURCE,
    build_princeton_mlb_odds_snapshots,
    build_sportsbookreview_mlb_odds_snapshots,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "contracts" / "schemas"


class _FakeDb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, sql: str, params: dict) -> None:
        self.calls.append((sql, params))


def _raw_mlb_game() -> dict:
    return {
        "id": "odds-api-event-1",
        "sport_key": "baseball_mlb",
        "sport_title": "MLB",
        "commence_time": "2026-05-10T23:10:00Z",
        "home_team": "Los Angeles Dodgers",
        "away_team": "San Diego Padres",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "last_update": "2026-05-10T20:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Los Angeles Dodgers", "price": 1.80},
                            {"name": "San Diego Padres", "price": 2.05},
                        ],
                    }
                ],
            }
        ],
    }


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


def _free_sportsbookreview_json() -> dict:
    return {
        "2023-07-04": [
            {
                "gameView": {
                    "startDate": "2023-07-04T23:10:00Z",
                    "awayTeam": {"fullName": "San Diego Padres", "shortName": "SD"},
                    "homeTeam": {
                        "fullName": "Los Angeles Dodgers",
                        "shortName": "LAD",
                    },
                },
                "odds": {
                    "moneyline": [
                        {
                            "sportsbook": "draftkings",
                            "openingLine": {"homeOdds": -125, "awayOdds": 115},
                            "currentLine": {"homeOdds": -140, "awayOdds": 120},
                        }
                    ]
                },
            }
        ]
    }


def test_princeton_free_historical_odds_build_open_and_close_snapshots() -> None:
    """Free Princeton-style rows produce open/close home/away snapshots."""
    rows = [
        {
            "game_date": "2023-07-04",
            "home_team": "Los Angeles Dodgers",
            "away_team": "San Diego Padres",
            "home_score": 5,
            "away_score": 3,
            "home_open_ml": -125,
            "away_open_ml": 115,
            "home_close_ml": -140,
            "away_close_ml": 120,
        }
    ]

    payloads = build_princeton_mlb_odds_snapshots(rows)

    assert len(payloads) == 4
    assert {payload["source"] for payload in payloads} == {PRINCETON_HISTORICAL_SOURCE}
    assert {payload["snapshot_type"] for payload in payloads} == {"open", "close"}
    assert {payload["outcome_role"] for payload in payloads} == {"home", "away"}
    schema = _load_schema("mlb_odds_snapshot_v1.json")
    for payload in payloads:
        validate_contract_payload(payload, schema)


def test_build_mlb_odds_snapshot_payloads_match_contract() -> None:
    """Parsed MLB odds produce canonical home/away snapshot payloads."""
    api = TheOddsAPI(api_key="test_key", db_manager=_FakeDb())
    parsed = api._parse_game(_raw_mlb_game(), "mlb")
    assert parsed is not None
    parsed["source_snapshot_at"] = "2026-05-10T20:00:00Z"

    payloads = api.build_mlb_odds_snapshot_payloads(parsed)

    assert len(payloads) == 2
    schema = _load_schema("mlb_odds_snapshot_v1.json")
    for payload in payloads:
        validate_contract_payload(payload, schema)
    assert {payload["outcome_role"] for payload in payloads} == {"home", "away"}
    assert {payload["snapshot_type"] for payload in payloads} == {"intraday"}


def test_sportsbookreview_json_builds_open_and_close_snapshots() -> None:
    """Free GitHub JSON odds should produce contract-valid open/close snapshots."""
    payloads = build_sportsbookreview_mlb_odds_snapshots(_free_sportsbookreview_json())

    assert len(payloads) == 4
    assert {payload["source"] for payload in payloads} == {GITHUB_SPORTSBOOKREVIEW_SOURCE}
    assert {payload["snapshot_type"] for payload in payloads} == {"open", "close"}
    assert {payload["outcome_role"] for payload in payloads} == {"home", "away"}
    schema = _load_schema("mlb_odds_snapshot_v1.json")
    for payload in payloads:
        validate_contract_payload(payload, schema)


def test_sportsbookreview_json_skips_zero_moneylines() -> None:
    """Malformed zero-odds rows should be skipped, not abort the entire import."""
    raw = _free_sportsbookreview_json()
    raw["2023-07-04"][0]["odds"]["moneyline"][0]["currentLine"]["awayOdds"] = 0

    payloads = build_sportsbookreview_mlb_odds_snapshots(raw)

    assert len(payloads) == 3
    assert all(payload["decimal_price"] > 1.0 for payload in payloads)


def test_save_to_db_persists_mlb_odds_snapshots_for_future_collection() -> None:
    """Future MLB odds fetches populate both latest odds and snapshot history."""
    db = _FakeDb()
    api = TheOddsAPI(api_key="test_key", db_manager=db)
    parsed = api._parse_game(_raw_mlb_game(), "mlb")
    assert parsed is not None

    odds_count = api.save_to_db([parsed])

    snapshot_calls = [
        (sql, params) for sql, params in db.calls if "mlb_odds_snapshots" in sql
    ]
    assert odds_count == 2
    assert len(snapshot_calls) == 2
    sql, params = snapshot_calls[0]
    assert "ON CONFLICT" in sql
    assert params["source"] == "the_odds_api"
    assert params["sport"] == "MLB"
    assert params["source_event_id"] == "odds-api-event-1"
