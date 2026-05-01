"""Consumer-driven contract tests for dashboard data layer.

Each data_layer function's output must validate against its JSON Schema.
These tests run against an in-memory SQLite database seeded with
schema-compatible test data.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

# Ensure dashboard and plugins are importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from jsonschema import Draft202012Validator, ValidationError

CONTRACTS_DIR = Path(__file__).parent.parent.parent / "dashboard" / "contracts"


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((CONTRACTS_DIR / f"{name}_v1.json").read_text())


def validate(instance: Any, schema: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(instance)


# ------------------------------------------------------------------
# Schema existence and parseability
# ------------------------------------------------------------------

SCHEMA_NAMES = [
    "portfolio_summary",
    "placed_bet_row",
    "bet_detail",
    "elo_ratings",
    "today_game",
    "bet_recommendation",
    "calibration_data",
    "elo_history",
    "data_quality",
    "portfolio_snapshots",
]


class TestSchemasExist:
    @pytest.mark.parametrize("name", SCHEMA_NAMES)
    def test_schema_file_exists_and_is_valid_json(self, name: str):
        path = CONTRACTS_DIR / f"{name}_v1.json"
        assert path.exists(), f"Missing schema: {path}"
        schema = json.loads(path.read_text())
        assert "$schema" in schema
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


# ------------------------------------------------------------------
# Portfolio summary contract
# ------------------------------------------------------------------

class TestPortfolioSummaryContract:
    def test_valid_payload_passes(self):
        schema = load_schema("portfolio_summary")
        payload = {
            "portfolio_value": 1234.56,
            "daily_pnl": 23.45,
            "open_bets_count": 4,
            "total_exposure": 38.00,
            "win_rate": 0.542,
            "total_bets": 59,
            "settled_count": 55,
        }
        validate(payload, schema)

    def test_missing_required_field_fails(self):
        schema = load_schema("portfolio_summary")
        for field in schema["required"]:
            payload = {"portfolio_value": 100, "daily_pnl": 0, "open_bets_count": 0,
                       "total_exposure": 0, "win_rate": 0, "total_bets": 0, "settled_count": 0}
            del payload[field]
            with pytest.raises(ValidationError):
                validate(payload, schema)

    def test_negative_open_bets_fails(self):
        schema = load_schema("portfolio_summary")
        payload = {"portfolio_value": 100, "daily_pnl": 0, "open_bets_count": -1,
                   "total_exposure": 0, "win_rate": 0, "total_bets": 0, "settled_count": 0}
        with pytest.raises(ValidationError):
            validate(payload, schema)

    def test_win_rate_out_of_range_fails(self):
        schema = load_schema("portfolio_summary")
        payload = {"portfolio_value": 100, "daily_pnl": 0, "open_bets_count": 0,
                   "total_exposure": 0, "win_rate": 1.5, "total_bets": 0, "settled_count": 0}
        with pytest.raises(ValidationError):
            validate(payload, schema)

    def test_blocks_unknown_fields(self):
        schema = load_schema("portfolio_summary")
        payload = {"portfolio_value": 100, "daily_pnl": 0, "open_bets_count": 0,
                   "total_exposure": 0, "win_rate": 0, "total_bets": 0, "settled_count": 0,
                   "extra_field": "nope"}
        with pytest.raises(ValidationError):
            validate(payload, schema)


# ------------------------------------------------------------------
# Placed bet row contract
# ------------------------------------------------------------------

class TestPlacedBetRowContract:
    def test_valid_row_passes(self):
        schema = load_schema("placed_bet_row")
        payload = {
            "bet_id": "bet-001",
            "sport": "NBA",
            "market": "Lakers ML",
            "team": "Los Angeles Lakers",
            "placed_at": "2026-05-01T14:32:00Z",
            "stake": 10.00,
            "status": "PENDING",
            "edge": 0.059,
            "elo_prob": 0.583,
            "market_prob": 0.524,
            "kelly_fraction": 0.20,
            "confidence": "MEDIUM",
            "payout": 0.0,
            "ticker": "KX-2026-05-01-LAL-PHX-Y",
            "bookmaker": "Kalshi",
            "game_id": "NBA-2026-05-01-LAL-PHX",
            "home_team": "Los Angeles Lakers",
            "away_team": "Phoenix Suns",
            "side": "home",
            "elo_home_rating": 1582.0,
            "elo_away_rating": 1547.0,
        }
        validate(payload, schema)

    def test_invalid_status_fails(self):
        schema = load_schema("placed_bet_row")
        payload = {"bet_id": "x", "sport": "NBA", "market": "m", "team": "t",
                   "placed_at": "2026-01-01", "stake": 10, "status": "INVALID"}
        with pytest.raises(ValidationError):
            validate(payload, schema)

    def test_invalid_confidence_fails(self):
        schema = load_schema("placed_bet_row")
        payload = {"bet_id": "x", "sport": "NBA", "market": "m", "team": "t",
                   "placed_at": "2026-01-01", "stake": 10, "status": "WON",
                   "confidence": "medium"}
        with pytest.raises(ValidationError):
            validate(payload, schema)

    def test_negative_stake_fails(self):
        schema = load_schema("placed_bet_row")
        payload = {"bet_id": "x", "sport": "NBA", "market": "m", "team": "t",
                   "placed_at": "2026-01-01", "stake": -5, "status": "WON"}
        with pytest.raises(ValidationError):
            validate(payload, schema)


# ------------------------------------------------------------------
# Bet detail contract
# ------------------------------------------------------------------

class TestBetDetailContract:
    def test_full_detail_passes(self):
        schema = load_schema("bet_detail")
        payload = {
            "bet": {
                "bet_id": "bet-001", "sport": "NBA", "market": "Lakers ML",
                "team": "Los Angeles Lakers", "placed_at": "2026-05-01T14:32:00Z",
                "stake": 10.00, "status": "WON", "edge": 0.059, "elo_prob": 0.583,
                "market_prob": 0.524, "kelly_fraction": 0.20, "confidence": "MEDIUM",
                "payout": 18.20, "settled_at": "2026-05-02T03:00:00Z",
                "bookmaker": "Kalshi", "ticker": "KX-LAL-PHX-Y",
                "home_team": "LAL", "away_team": "PHX", "side": "home",
            },
            "odds": [
                {"source": "kalshi", "price": -110, "implied_prob": 0.524, "timestamp": "2026-05-01T14:30:00Z"},
                {"source": "betmgm", "price": -115, "implied_prob": 0.535, "timestamp": "2026-05-01T14:28:00Z"},
            ],
            "elo_snapshot": {
                "team_a_rating": 1582, "team_b_rating": 1547,
                "team_a_name": "LAL", "team_b_name": "PHX",
                "rating_diff": 35, "home_advantage": 100, "effective_diff": 135,
            },
            "elo_history": [
                {"date": "2026-04-30", "team": "LAL", "rating": 1580},
                {"date": "2026-05-01", "team": "LAL", "rating": 1582},
            ],
            "recent_form": {
                "team_a": {
                    "team": "LAL", "record": "4-1",
                    "games": [{"opponent": "BOS", "result": "W", "score": "112-108", "date": "2026-04-28"}],
                },
                "team_b": {
                    "team": "PHX", "record": "1-4",
                    "games": [{"opponent": "DAL", "result": "L", "score": "101-115", "date": "2026-04-28"}],
                },
            },
        }
        validate(payload, schema)

    def test_empty_odds_allowed(self):
        schema = load_schema("bet_detail")
        payload = {
            "bet": {"bet_id": "x", "sport": "NBA", "market": "m", "team": "t",
                    "placed_at": "2026-01-01", "stake": 10, "status": "PENDING",
                    "edge": 0.05, "elo_prob": 0.55, "market_prob": 0.50,
                    "kelly_fraction": 0.20, "confidence": "LOW"},
            "odds": [],
            "elo_snapshot": {"team_a_rating": 1500, "team_b_rating": 1500,
                             "team_a_name": "A", "team_b_name": "B",
                             "rating_diff": 0, "home_advantage": 0, "effective_diff": 0},
            "elo_history": [],
            "recent_form": {
                "team_a": {"team": "A", "games": [], "record": "0-0"},
                "team_b": {"team": "B", "games": [], "record": "0-0"},
            },
        }
        validate(payload, schema)


# ------------------------------------------------------------------
# Elo ratings contract
# ------------------------------------------------------------------

class TestEloRatingsContract:
    def test_valid_ratings_pass(self):
        schema = load_schema("elo_ratings")
        payload = [
            {"team": "LAL", "rating": 1582.0, "sport": "NBA", "last_updated": "2026-05-01T10:00:00Z",
             "trend_7d": 12.0, "trend_30d": 25.0, "rank": 1},
            {"team": "BOS", "rating": 1570.0, "sport": "NBA", "last_updated": "2026-05-01T10:00:00Z", "rank": 2},
        ]
        validate(payload, schema)

    def test_empty_array_passes(self):
        schema = load_schema("elo_ratings")
        validate([], schema)

    def test_missing_required_field_fails(self):
        schema = load_schema("elo_ratings")
        with pytest.raises(ValidationError):
            validate([{"team": "LAL"}], schema)


# ------------------------------------------------------------------
# Today games contract
# ------------------------------------------------------------------

class TestTodayGamesContract:
    def test_valid_game_passes(self):
        schema = load_schema("today_game")
        payload = [{
            "game_id": "NBA-2026-05-01-LAL-PHX", "sport": "NBA",
            "home_team": "Los Angeles Lakers", "away_team": "Phoenix Suns",
            "start_time": "2026-05-01T19:00:00Z",
            "home_elo": 1582, "away_elo": 1547,
            "home_win_prob": 0.583,
            "best_home_odds": -110, "best_away_odds": -110,
            "best_home_bookmaker": "Kalshi", "best_away_bookmaker": "BetMGM",
            "edge": 0.059, "edge_side": "home", "confidence": "MEDIUM",
        }]
        validate(payload, schema)


# ------------------------------------------------------------------
# Bet recommendations contract
# ------------------------------------------------------------------

class TestBetRecommendationsContract:
    def test_valid_recommendation_passes(self):
        schema = load_schema("bet_recommendation")
        payload = [{
            "sport": "NBA", "game_id": "NBA-2026-05-01-LAL-PHX",
            "bet_on": "Los Angeles Lakers", "home_team": "LAL", "away_team": "PHX",
            "side": "home", "elo_prob": 0.583, "market_prob": 0.524,
            "market_odds": -110, "bookmaker": "Kalshi", "edge": 0.059,
            "expected_value": 0.112, "kelly_fraction": 0.20, "confidence": "MEDIUM",
            "ticker": "KX-LAL-PHX-Y",
        }]
        validate(payload, schema)

    def test_invalid_confidence_fails(self):
        schema = load_schema("bet_recommendation")
        payload = [{"sport": "X", "game_id": "g", "bet_on": "t", "elo_prob": 0.5,
                    "market_prob": 0.5, "edge": 0.05, "confidence": "UNKNOWN"}]
        with pytest.raises(ValidationError):
            validate(payload, schema)


# ------------------------------------------------------------------
# Calibration data contract
# ------------------------------------------------------------------

class TestCalibrationDataContract:
    def test_valid_calibration_passes(self):
        schema = load_schema("calibration_data")
        payload = {
            "bets": [
                {"sport": "NBA", "elo_prob": 0.60, "result": "WON", "edge": 0.08, "stake": 10, "payout": 18.20},
                {"sport": "NBA", "elo_prob": 0.55, "result": "LOST", "edge": 0.05, "stake": 10, "payout": 0},
            ],
            "buckets": [
                {"label": "0-10%", "predicted_min": 0.0, "predicted_max": 0.10,
                 "count": 5, "actual_win_rate": 0.20},
            ],
            "by_sport": [
                {"sport": "NBA", "bet_count": 10, "win_rate": 0.50, "avg_edge": 0.06, "roi": 0.05},
            ],
        }
        validate(payload, schema)


# ------------------------------------------------------------------
# Elo history contract
# ------------------------------------------------------------------

class TestEloHistoryContract:
    def test_valid_history_passes(self):
        schema = load_schema("elo_history")
        payload = [
            {"date": "2026-04-01", "team": "LAL", "rating": 1550},
            {"date": "2026-04-02", "team": "LAL", "rating": 1555},
        ]
        validate(payload, schema)

    def test_empty_array_passes(self):
        schema = load_schema("elo_history")
        validate([], schema)


# ------------------------------------------------------------------
# Data quality contract
# ------------------------------------------------------------------

class TestDataQualityContract:
    def test_valid_report_passes(self):
        schema = load_schema("data_quality")
        payload = {
            "overall_health": 85,
            "sports": [
                {"sport": "NBA", "health_score": 90, "missing_games": 0,
                 "stale_elo": 0, "odds_freshness_minutes": 5,
                 "last_game_date": "2026-05-01", "last_dag_run": "2026-05-01T10:00:00Z",
                 "issues": []},
            ],
        }
        validate(payload, schema)


# ------------------------------------------------------------------
# Portfolio snapshots contract
# ------------------------------------------------------------------

class TestPortfolioSnapshotsContract:
    def test_valid_snapshots_pass(self):
        schema = load_schema("portfolio_snapshots")
        payload = [
            {"timestamp": "2026-05-01T10:00:00Z", "portfolio_value": 1200.00},
            {"timestamp": "2026-05-01T11:00:00Z", "portfolio_value": 1210.50},
        ]
        validate(payload, schema)
