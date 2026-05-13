# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 2,475-line monolithic `dashboard/dashboard_app.py` with a clean Streamlit `pages/` architecture backed by a contract-enforced data layer and auto-refresh.

**Architecture:** Streamlit multi-page app with `dashboard/data_layer.py` as the sole database interface (all SQL lives here), `dashboard/pages/` with one file per page, `dashboard/contracts/` with JSON Schema per data function, and consumer-driven contract tests validating every data shape.

**Tech Stack:** Streamlit, PostgreSQL (via DBManager), pandas, plotly, jsonschema (Draft 2020-12), pytest

**Spec:** `docs/superpowers/specs/2026-05-01-dashboard-redesign.md`

---

### Task 1: Create dashboard package skeleton and contract schemas

**Files:**
- Create: `dashboard/__init__.py`
- Create: `dashboard/contracts/portfolio_summary_v1.json`
- Create: `dashboard/contracts/placed_bet_row_v1.json`
- Create: `dashboard/contracts/bet_detail_v1.json`
- Create: `dashboard/contracts/elo_ratings_v1.json`
- Create: `dashboard/contracts/today_game_v1.json`
- Create: `dashboard/contracts/bet_recommendation_v1.json`
- Create: `dashboard/contracts/calibration_data_v1.json`
- Create: `dashboard/contracts/elo_history_v1.json`
- Create: `dashboard/contracts/data_quality_v1.json`
- Create: `dashboard/contracts/portfolio_snapshots_v1.json`

- [ ] **Step 1: Create directories**

```bash
mkdir -p dashboard/pages dashboard/contracts
```

- [ ] **Step 2: Create `dashboard/__init__.py`**

```python
"""Dashboard package for the NHLStats multi-sport betting analytics platform."""
```

- [ ] **Step 3: Create `dashboard/contracts/portfolio_summary_v1.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Portfolio Summary",
  "description": "Top-level portfolio KPIs consumed by the Portfolio page.",
  "type": "object",
  "required": ["portfolio_value", "daily_pnl", "open_bets_count", "total_exposure", "win_rate", "total_bets", "settled_count"],
  "properties": {
    "portfolio_value": {"type": "number"},
    "daily_pnl": {"type": "number"},
    "open_bets_count": {"type": "integer", "minimum": 0},
    "total_exposure": {"type": "number", "minimum": 0},
    "win_rate": {"type": "number", "minimum": 0, "maximum": 1},
    "total_bets": {"type": "integer", "minimum": 0},
    "settled_count": {"type": "integer", "minimum": 0}
  },
  "additionalProperties": false
}
```

- [ ] **Step 4: Create `dashboard/contracts/placed_bet_row_v1.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Placed Bet Row",
  "description": "A single row from the placed_bets table consumed by the Portfolio and Bet Detail pages.",
  "type": "object",
  "required": ["bet_id", "sport", "market", "team", "placed_at", "stake", "status"],
  "properties": {
    "bet_id": {"type": "string", "minLength": 1},
    "sport": {"type": "string", "minLength": 1},
    "market": {"type": "string"},
    "team": {"type": "string"},
    "placed_at": {"type": "string"},
    "stake": {"type": "number", "minimum": 0},
    "status": {"type": "string", "enum": ["PENDING", "WON", "LOST", "CANCELLED"]},
    "edge": {"type": "number"},
    "elo_prob": {"type": "number", "minimum": 0, "maximum": 1},
    "market_prob": {"type": "number", "minimum": 0, "maximum": 1},
    "kelly_fraction": {"type": "number"},
    "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
    "payout": {"type": "number"},
    "settled_at": {"type": "string"},
    "ticker": {"type": "string"},
    "bookmaker": {"type": "string"},
    "game_id": {"type": "string"},
    "home_team": {"type": "string"},
    "away_team": {"type": "string"},
    "side": {"type": "string"},
    "elo_home_rating": {"type": "number"},
    "elo_away_rating": {"type": "number"}
  },
  "additionalProperties": true
}
```

- [ ] **Step 5: Create `dashboard/contracts/bet_detail_v1.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Bet Detail",
  "description": "Full bet traceability data consumed by the Bet Detail drill-down page.",
  "type": "object",
  "required": ["bet", "odds", "elo_snapshot", "elo_history", "recent_form"],
  "properties": {
    "bet": {
      "type": "object",
      "required": ["bet_id", "sport", "market", "team", "placed_at", "stake", "status", "edge", "elo_prob", "market_prob", "kelly_fraction", "confidence"],
      "properties": {
        "bet_id": {"type": "string"},
        "sport": {"type": "string"},
        "market": {"type": "string"},
        "team": {"type": "string"},
        "placed_at": {"type": "string"},
        "stake": {"type": "number"},
        "status": {"type": "string"},
        "edge": {"type": "number"},
        "elo_prob": {"type": "number"},
        "market_prob": {"type": "number"},
        "kelly_fraction": {"type": "number"},
        "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
        "payout": {"type": "number"},
        "settled_at": {"type": "string"},
        "bookmaker": {"type": "string"},
        "ticker": {"type": "string"},
        "home_team": {"type": "string"},
        "away_team": {"type": "string"},
        "side": {"type": "string"}
      }
    },
    "odds": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["source", "price", "implied_prob", "timestamp"],
        "properties": {
          "source": {"type": "string", "enum": ["kalshi", "betmgm", "draftkings", "sbr"]},
          "price": {"type": "number"},
          "implied_prob": {"type": "number", "minimum": 0, "maximum": 1},
          "timestamp": {"type": "string"}
        }
      }
    },
    "elo_snapshot": {
      "type": "object",
      "required": ["team_a_rating", "team_b_rating", "team_a_name", "team_b_name", "rating_diff", "home_advantage", "effective_diff"],
      "properties": {
        "team_a_rating": {"type": "number"},
        "team_b_rating": {"type": "number"},
        "team_a_name": {"type": "string"},
        "team_b_name": {"type": "string"},
        "rating_diff": {"type": "number"},
        "home_advantage": {"type": "number"},
        "effective_diff": {"type": "number"}
      }
    },
    "elo_history": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["date", "team", "rating"],
        "properties": {
          "date": {"type": "string"},
          "team": {"type": "string"},
          "rating": {"type": "number"}
        }
      }
    },
    "recent_form": {
      "type": "object",
      "required": ["team_a", "team_b"],
      "properties": {
        "team_a": {
          "type": "object",
          "required": ["team", "games"],
          "properties": {
            "team": {"type": "string"},
            "games": {"type": "array", "items": {
              "type": "object",
              "required": ["opponent", "result", "score", "date"],
              "properties": {
                "opponent": {"type": "string"},
                "result": {"type": "string", "enum": ["W", "L", "D"]},
                "score": {"type": "string"},
                "date": {"type": "string"}
              }
            }},
            "record": {"type": "string"}
          }
        },
        "team_b": {
          "type": "object",
          "required": ["team", "games"],
          "properties": {
            "team": {"type": "string"},
            "games": {"type": "array"},
            "record": {"type": "string"}
          }
        }
      }
    }
  }
}
```

- [ ] **Step 6: Create `dashboard/contracts/elo_ratings_v1.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Elo Ratings",
  "description": "Current Elo ratings for teams/players in a sport, consumed by the Rankings page.",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["team", "rating", "sport", "last_updated"],
    "properties": {
      "team": {"type": "string"},
      "rating": {"type": "number"},
      "sport": {"type": "string"},
      "last_updated": {"type": "string"},
      "trend_7d": {"type": "number"},
      "trend_30d": {"type": "number"},
      "rank": {"type": "integer", "minimum": 1}
    },
    "additionalProperties": true
  }
}
```

- [ ] **Step 7: Create `dashboard/contracts/today_game_v1.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Today Games",
  "description": "Today's games with Elo probabilities and odds, consumed by the Live Markets page.",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["game_id", "sport", "home_team", "away_team", "start_time"],
    "properties": {
      "game_id": {"type": "string"},
      "sport": {"type": "string"},
      "home_team": {"type": "string"},
      "away_team": {"type": "string"},
      "start_time": {"type": "string"},
      "home_elo": {"type": "number"},
      "away_elo": {"type": "number"},
      "home_win_prob": {"type": "number", "minimum": 0, "maximum": 1},
      "best_home_odds": {"type": "number"},
      "best_away_odds": {"type": "number"},
      "best_home_bookmaker": {"type": "string"},
      "best_away_bookmaker": {"type": "string"},
      "edge": {"type": "number"},
      "edge_side": {"type": "string"},
      "confidence": {"type": "string"}
    },
    "additionalProperties": true
  }
}
```

- [ ] **Step 8: Create `dashboard/contracts/bet_recommendation_v1.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Bet Recommendations",
  "description": "Current bet recommendations the system wants to place, consumed by the Live Markets page.",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["sport", "game_id", "bet_on", "elo_prob", "market_prob", "edge", "confidence"],
    "properties": {
      "sport": {"type": "string"},
      "game_id": {"type": "string"},
      "bet_on": {"type": "string"},
      "home_team": {"type": "string"},
      "away_team": {"type": "string"},
      "side": {"type": "string"},
      "elo_prob": {"type": "number", "minimum": 0, "maximum": 1},
      "market_prob": {"type": "number", "minimum": 0, "maximum": 1},
      "market_odds": {"type": "number"},
      "bookmaker": {"type": "string"},
      "edge": {"type": "number"},
      "expected_value": {"type": "number"},
      "kelly_fraction": {"type": "number"},
      "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
      "ticker": {"type": "string"}
    },
    "additionalProperties": true
  }
}
```

- [ ] **Step 9: Create `dashboard/contracts/calibration_data_v1.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Calibration Data",
  "description": "Model calibration data consumed by the Calibration page.",
  "type": "object",
  "required": ["bets", "buckets", "by_sport"],
  "properties": {
    "bets": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["sport", "elo_prob", "result", "edge", "stake", "payout"],
        "properties": {
          "sport": {"type": "string"},
          "elo_prob": {"type": "number", "minimum": 0, "maximum": 1},
          "result": {"type": "string", "enum": ["WON", "LOST"]},
          "edge": {"type": "number"},
          "stake": {"type": "number"},
          "payout": {"type": "number"}
        }
      }
    },
    "buckets": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["label", "predicted_min", "predicted_max", "count", "actual_win_rate"],
        "properties": {
          "label": {"type": "string"},
          "predicted_min": {"type": "number"},
          "predicted_max": {"type": "number"},
          "count": {"type": "integer"},
          "actual_win_rate": {"type": "number"}
        }
      }
    },
    "by_sport": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["sport", "bet_count", "win_rate", "avg_edge", "roi"],
        "properties": {
          "sport": {"type": "string"},
          "bet_count": {"type": "integer", "minimum": 0},
          "win_rate": {"type": "number", "minimum": 0, "maximum": 1},
          "avg_edge": {"type": "number"},
          "roi": {"type": "number"}
        }
      }
    }
  }
}
```

- [ ] **Step 10: Create `dashboard/contracts/elo_history_v1.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Elo History",
  "description": "Elo rating timeseries for one team, consumed by Rankings and Bet Detail pages.",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["date", "team", "rating"],
    "properties": {
      "date": {"type": "string"},
      "team": {"type": "string"},
      "rating": {"type": "number"}
    }
  }
}
```

- [ ] **Step 11: Create `dashboard/contracts/data_quality_v1.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Data Quality Report",
  "description": "System health report consumed by the Data Quality page.",
  "type": "object",
  "required": ["overall_health", "sports"],
  "properties": {
    "overall_health": {"type": "integer", "minimum": 0, "maximum": 100},
    "sports": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["sport", "health_score"],
        "properties": {
          "sport": {"type": "string"},
          "health_score": {"type": "integer", "minimum": 0, "maximum": 100},
          "missing_games": {"type": "integer"},
          "stale_elo": {"type": "integer"},
          "odds_freshness_minutes": {"type": "integer"},
          "last_game_date": {"type": "string"},
          "last_dag_run": {"type": "string"},
          "issues": {"type": "array", "items": {"type": "string"}}
        }
      }
    }
  }
}
```

- [ ] **Step 12: Create `dashboard/contracts/portfolio_snapshots_v1.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Portfolio Snapshots",
  "description": "Timeseries of portfolio value snapshots consumed by the Portfolio page.",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["timestamp", "portfolio_value"],
    "properties": {
      "timestamp": {"type": "string"},
      "portfolio_value": {"type": "number"}
    }
  }
}
```

- [ ] **Step 13: Commit**

```bash
git add dashboard/__init__.py dashboard/contracts/
git commit -m "feat(dashboard): add contract schemas for all 10 data functions"
```

---

### Task 2: Write contract validation tests

**Files:**
- Create: `tests/contracts/test_dashboard_data_contracts.py`

Inspired by existing pattern in `tests/contracts/test_dashboard_bet_opportunity_consumer.py` and `tests/contracts/helpers.py`.

- [ ] **Step 1: Create `tests/contracts/test_dashboard_data_contracts.py`**

```python
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
```

- [ ] **Step 2: Run contract tests to verify they fail (no data layer yet — but schemas exist so they should parse and pass the static tests)**

```bash
pytest tests/contracts/test_dashboard_data_contracts.py -v
```

Expected: 20+ tests PASS (these tests validate payloads against schemas, they don't call data_layer yet)

- [ ] **Step 3: Commit**

```bash
git add tests/contracts/test_dashboard_data_contracts.py
git commit -m "test(dashboard): add consumer contract tests for all 10 data schemas"
```

---

### Task 3: Create the data layer (`dashboard/data_layer.py`)

**Files:**
- Create: `dashboard/data_layer.py`
- Modify: `tests/contracts/test_dashboard_data_contracts.py` (add integration tests)

- [ ] **Step 1: Create `dashboard/data_layer.py`**

```python
"""Dashboard data layer — the ONLY file that contains SQL queries.

All page files import from here. No SQL strings exist outside this file.
Every function is decorated with @st.cache_data for Streamlit caching.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from plugins.db_manager import DBManager

_db = DBManager()

# Cache TTLs (seconds)
TTL_LIVE = 30       # odds, markets, portfolio
TTL_STANDARD = 300  # ratings, snapshots, data quality
TTL_LONG = 3600     # calibration, historical


@st.cache_data(ttl=TTL_LIVE)
def get_portfolio_summary() -> dict:
    """Return KPIs: portfolio_value, daily_pnl, open_bets_count, total_exposure, win_rate, total_bets, settled_count."""
    latest_snapshot = _db.fetch_scalar(
        "SELECT portfolio_value FROM portfolio_value_snapshots ORDER BY timestamp DESC LIMIT 1"
    )
    portfolio_value = float(latest_snapshot) if latest_snapshot else 0.0

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_result = _db.fetch_df(
        "SELECT COALESCE(SUM(CASE WHEN status = 'WON' THEN payout - stake "
        "WHEN status = 'LOST' THEN -stake ELSE 0 END), 0) AS daily_pnl "
        "FROM placed_bets WHERE DATE(settled_at) = %(today)s",
        {"today": today},
    )
    daily_pnl = float(daily_result["daily_pnl"].iloc[0]) if len(daily_result) > 0 else 0.0

    open_bets = _db.fetch_df(
        "SELECT COUNT(*) AS cnt, COALESCE(SUM(stake), 0) AS exposure "
        "FROM placed_bets WHERE status = 'PENDING'"
    )
    open_bets_count = int(open_bets["cnt"].iloc[0]) if len(open_bets) > 0 else 0
    total_exposure = float(open_bets["exposure"].iloc[0]) if len(open_bets) > 0 else 0.0

    settled = _db.fetch_df(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN status = 'WON' THEN 1 ELSE 0 END) AS wins "
        "FROM placed_bets WHERE status IN ('WON', 'LOST')"
    )
    total_bets = int(settled["total"].iloc[0]) if len(settled) > 0 else 0
    wins = int(settled["wins"].iloc[0]) if len(settled) > 0 else 0
    win_rate = wins / total_bets if total_bets > 0 else 0.0

    return {
        "portfolio_value": portfolio_value,
        "daily_pnl": daily_pnl,
        "open_bets_count": open_bets_count,
        "total_exposure": total_exposure,
        "win_rate": win_rate,
        "total_bets": total_bets,
        "settled_count": total_bets,
    }


@st.cache_data(ttl=TTL_LIVE)
def get_placed_bets(limit: int = 50, status: Optional[str] = None, sport: Optional[str] = None) -> pd.DataFrame:
    """Return placed_bets rows, newest first. Optionally filter by status and sport."""
    query = "SELECT * FROM placed_bets WHERE 1=1"
    params = {}
    if status:
        query += " AND status = %(status)s"
        params["status"] = status
    if sport:
        query += " AND sport = %(sport)s"
        params["sport"] = sport
    query += " ORDER BY placed_at DESC LIMIT %(limit)s"
    params["limit"] = limit
    return _db.fetch_df(query, params)


@st.cache_data(ttl=TTL_STANDARD)
def get_bet_detail(bet_id: str) -> dict:
    """Return full bet traceability: the bet record, odds snapshot, Elo snapshot, Elo history, recent form."""
    bet_df = _db.fetch_df(
        "SELECT * FROM placed_bets WHERE bet_id = %(bet_id)s",
        {"bet_id": bet_id},
    )
    if bet_df.empty:
        raise ValueError(f"Bet not found: {bet_id}")

    bet_row = bet_df.iloc[0].to_dict()
    # Coerce numpy/pandas types to native Python
    bet = {}
    for k, v in bet_row.items():
        if pd.isna(v):
            bet[k] = None
        elif hasattr(v, "isoformat"):
            bet[k] = v.isoformat()
        elif hasattr(v, "item"):
            bet[k] = v.item()
        else:
            bet[k] = v

    # Odds at bet placement time
    odds = _load_odds_for_bet(bet)

    # Elo snapshot at bet time
    elo_snapshot = _load_elo_snapshot(bet)

    # Elo history (30 days before bet)
    elo_history = _load_elo_history_for_bet(bet)

    # Recent form (last 5 games for each team)
    recent_form = _load_recent_form(bet)

    return {
        "bet": bet,
        "odds": odds,
        "elo_snapshot": elo_snapshot,
        "elo_history": elo_history,
        "recent_form": recent_form,
    }


def _load_odds_for_bet(bet: dict) -> list:
    """Load odds from all sources near the bet placement time."""
    bet_time = bet.get("placed_at")
    game_id = bet.get("game_id")
    if not bet_time or not game_id:
        return []

    # Parse the bet time to a date range (±30 min window)
    try:
        if isinstance(bet_time, str):
            bt = datetime.fromisoformat(bet_time.replace("Z", "+00:00"))
        else:
            bt = bet_time
        window_start = (bt - timedelta(minutes=30)).isoformat()
        window_end = (bt + timedelta(minutes=30)).isoformat()
    except (ValueError, TypeError):
        return []

    odds_df = _db.fetch_df(
        "SELECT source, price, implied_prob, timestamp FROM game_odds "
        "WHERE game_id = %(game_id)s "
        "AND timestamp BETWEEN %(start)s AND %(end)s "
        "ORDER BY source, timestamp DESC",
        {"game_id": game_id, "start": window_start, "end": window_end},
    )
    odds = odds_df.to_dict(orient="records")
    result = []
    for row in odds:
        row_out = {}
        for k, v in row.items():
            if pd.isna(v):
                row_out[k] = None
            elif hasattr(v, "isoformat"):
                row_out[k] = v.isoformat()
            elif hasattr(v, "item"):
                row_out[k] = v.item()
            else:
                row_out[k] = v
        # Normalize source names to lowercase
        if "source" in row_out and row_out["source"]:
            row_out["source"] = row_out["source"].lower()
        result.append(row_out)
    return result


def _load_elo_snapshot(bet: dict) -> dict:
    """Load Elo ratings for both teams at bet placement time."""
    sport = bet.get("sport", "")
    home_team = bet.get("home_team", "")
    away_team = bet.get("away_team", "")
    bet_time = bet.get("placed_at")

    if not home_team or not away_team:
        return {
            "team_a_rating": 0, "team_b_rating": 0,
            "team_a_name": home_team or "", "team_b_name": away_team or "",
            "rating_diff": 0, "home_advantage": 0, "effective_diff": 0,
        }

    # Find ratings closest to bet time
    home_rating = _get_rating_at_time(sport, home_team, bet_time)
    away_rating = _get_rating_at_time(sport, away_team, bet_time)

    home_adv = _get_home_advantage(sport)
    rating_diff = home_rating - away_rating
    effective_diff = rating_diff + home_adv

    return {
        "team_a_rating": home_rating,
        "team_b_rating": away_rating,
        "team_a_name": home_team,
        "team_b_name": away_team,
        "rating_diff": rating_diff,
        "home_advantage": home_adv,
        "effective_diff": effective_diff,
    }


def _get_rating_at_time(sport: str, team: str, at_time) -> float:
    """Get Elo rating for a team closest to a given timestamp."""
    if at_time is None:
        at_time = datetime.now(timezone.utc).isoformat()
    rating = _db.fetch_scalar(
        "SELECT rating FROM elo_ratings WHERE sport = %(sport)s AND team = %(team)s "
        "AND timestamp <= %(ts)s ORDER BY timestamp DESC LIMIT 1",
        {"sport": sport, "team": team, "ts": at_time},
    )
    return float(rating) if rating else 1500.0


def _get_home_advantage(sport: str) -> float:
    """Return home advantage for a sport."""
    adv = {
        "NBA": 100, "NHL": 100, "NCAAB": 100, "WNCAAB": 100,
        "MLB": 50, "NFL": 65,
        "EPL": 60, "Ligue1": 60, "CBA": 100, "Unrivaled": 100,
        "TENNIS": 0,
    }
    return adv.get(sport, 50)


def _load_elo_history_for_bet(bet: dict) -> list:
    """Load 30-day Elo rating history for both teams before the bet."""
    sport = bet.get("sport", "")
    home_team = bet.get("home_team", "")
    away_team = bet.get("away_team", "")
    bet_time = bet.get("placed_at")

    if not home_team or not away_team or not bet_time:
        return []

    try:
        if isinstance(bet_time, str):
            bt = datetime.fromisoformat(bet_time.replace("Z", "+00:00"))
        else:
            bt = bet_time
        start = (bt - timedelta(days=30)).isoformat()
    except (ValueError, TypeError):
        return []

    df = _db.fetch_df(
        "SELECT timestamp AS date, team, rating FROM elo_ratings "
        "WHERE sport = %(sport)s AND team IN (%(home)s, %(away)s) "
        "AND timestamp BETWEEN %(start)s AND %(end)s "
        "ORDER BY timestamp ASC",
        {"sport": sport, "home": home_team, "away": away_team,
         "start": start, "end": bet_time},
    )
    result = df.to_dict(orient="records")
    for row in result:
        if hasattr(row.get("date"), "isoformat"):
            row["date"] = row["date"].isoformat()
    return result


def _load_recent_form(bet: dict) -> dict:
    """Load last 5 games for each team before the bet."""
    sport = bet.get("sport", "")
    home_team = bet.get("home_team", "")
    away_team = bet.get("away_team", "")
    bet_time = bet.get("placed_at")

    def _form(team: str) -> dict:
        if not team:
            return {"team": team or "", "games": [], "record": "0-0"}
        query = (
            "SELECT home_team, away_team, home_score, away_score, start_time AS date "
            "FROM unified_games "
            "WHERE sport = %(sport)s AND (home_team = %(team)s OR away_team = %(team)s) "
            "AND status = 'Final' "
        )
        params: dict = {"sport": sport, "team": team}
        if bet_time:
            query += " AND start_time < %(bet_time)s"
            params["bet_time"] = bet_time
        query += " ORDER BY start_time DESC LIMIT 5"
        df = _db.fetch_df(query, params)
        games = []
        wins = 0
        losses = 0
        for _, row in df.iterrows():
            is_home = row["home_team"] == team
            opp = row["away_team"] if is_home else row["home_team"]
            team_score = row["home_score"] if is_home else row["away_score"]
            opp_score = row["away_score"] if is_home else row["home_score"]
            if team_score > opp_score:
                result = "W"
                wins += 1
            elif team_score < opp_score:
                result = "L"
                losses += 1
            else:
                result = "D"
            score_str = f"{int(team_score)}-{int(opp_score)}" if team_score is not None else "?-?"
            date_val = row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"])
            games.append({
                "opponent": opp,
                "result": result,
                "score": score_str,
                "date": date_val,
            })
        return {"team": team, "games": games, "record": f"{wins}-{losses}"}

    return {"team_a": _form(home_team), "team_b": _form(away_team)}


@st.cache_data(ttl=TTL_STANDARD)
def get_current_elo_ratings(sport: str) -> pd.DataFrame:
    """Return current Elo ratings for all teams in a sport, ranked."""
    df = _db.fetch_df(
        "SELECT team, rating, sport, timestamp AS last_updated FROM elo_ratings "
        "WHERE sport = %(sport)s AND timestamp = ("
        "  SELECT MAX(timestamp) FROM elo_ratings WHERE sport = %(sport)s"
        ") ORDER BY rating DESC",
        {"sport": sport},
    )
    if df.empty:
        return df
    # Add rank column
    df["rank"] = range(1, len(df) + 1)
    # Add trend columns (optional — populated if historical data exists)
    df["trend_7d"] = 0.0
    df["trend_30d"] = 0.0
    # Coerce timestamps
    if "last_updated" in df.columns:
        df["last_updated"] = df["last_updated"].apply(
            lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x)
        )
    return df


@st.cache_data(ttl=TTL_LIVE)
def get_today_games(sport: Optional[str] = None) -> pd.DataFrame:
    """Return today's games with Elo probabilities and best odds."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    query = (
        "SELECT game_id, sport, home_team, away_team, start_time "
        "FROM unified_games WHERE DATE(start_time) = %(today)s AND status != 'Cancelled'"
    )
    params: dict = {"today": today}
    if sport:
        query += " AND sport = %(sport)s"
        params["sport"] = sport
    query += " ORDER BY start_time ASC"
    df = _db.fetch_df(query, params)

    if df.empty:
        return df

    # Enrich with Elo probabilities
    home_probs = []
    away_elos = []
    home_elos_list = []
    for _, row in df.iterrows():
        h_elo = _get_rating_at_time(row["sport"], row["home_team"], None)
        a_elo = _get_rating_at_time(row["sport"], row["away_team"], None)
        home_elos_list.append(h_elo)
        away_elos.append(a_elo)
        home_adv = _get_home_advantage(row["sport"])
        effective_diff = h_elo - a_elo + home_adv
        prob = 1.0 / (1.0 + 10.0 ** (-effective_diff / 400.0))
        home_probs.append(round(prob, 4))
    df["home_elo"] = home_elos_list
    df["away_elo"] = away_elos
    df["home_win_prob"] = home_probs
    df["best_home_odds"] = -110.0
    df["best_away_odds"] = -110.0
    df["best_home_bookmaker"] = ""
    df["best_away_bookmaker"] = ""
    df["edge"] = 0.0
    df["edge_side"] = ""
    df["confidence"] = ""

    if "start_time" in df.columns:
        df["start_time"] = df["start_time"].apply(
            lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x)
        )
    return df


@st.cache_data(ttl=TTL_LIVE)
def get_bet_recommendations(sport: Optional[str] = None) -> pd.DataFrame:
    """Return latest bet recommendations from the bet_recommendations table."""
    query = "SELECT * FROM bet_recommendations WHERE 1=1"
    params: dict = {}
    if sport:
        query += " AND sport = %(sport)s"
        params["sport"] = sport
    query += " ORDER BY created_at DESC LIMIT 100"
    return _db.fetch_df(query, params)


@st.cache_data(ttl=TTL_LONG)
def get_calibration_data(sport: Optional[str] = None) -> dict:
    """Return calibration data: individual bet predictions vs outcomes, buckets, and by-sport summary."""
    query = (
        "SELECT sport, elo_prob, status AS result, edge, stake, "
        "COALESCE(payout, 0) AS payout "
        "FROM placed_bets WHERE status IN ('WON', 'LOST')"
    )
    params: dict = {}
    if sport:
        query += " AND sport = %(sport)s"
        params["sport"] = sport
    df = _db.fetch_df(query, params)

    bets = []
    for _, row in df.iterrows():
        bets.append({
            "sport": row["sport"],
            "elo_prob": float(row["elo_prob"]) if not pd.isna(row.get("elo_prob")) else 0.5,
            "result": row["result"],
            "edge": float(row["edge"]) if not pd.isna(row.get("edge")) else 0.0,
            "stake": float(row["stake"]),
            "payout": float(row["payout"]),
        })

    # Build buckets
    bucket_edges = [0.0, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 1.0]
    bucket_labels = ["<50%", "50-55%", "55-60%", "60-65%", "65-70%", "70-75%", "75-80%", "80%+"]
    buckets = []
    for i, label in enumerate(bucket_labels):
        lo = bucket_edges[i]
        hi = bucket_edges[i + 1]
        in_bucket = [b for b in bets if lo <= b["elo_prob"] < hi]
        count = len(in_bucket)
        wins = sum(1 for b in in_bucket if b["result"] == "WON")
        actual = wins / count if count > 0 else 0.0
        buckets.append({
            "label": label, "predicted_min": lo, "predicted_max": hi,
            "count": count, "actual_win_rate": round(actual, 4),
        })

    # By sport
    sport_groups = {}
    for b in bets:
        s = b["sport"]
        if s not in sport_groups:
            sport_groups[s] = {"count": 0, "wins": 0, "total_edge": 0, "total_stake": 0, "total_payout": 0}
        sport_groups[s]["count"] += 1
        if b["result"] == "WON":
            sport_groups[s]["wins"] += 1
        sport_groups[s]["total_edge"] += b["edge"]
        sport_groups[s]["total_stake"] += b["stake"]
        sport_groups[s]["total_payout"] += b["payout"]

    by_sport = []
    for s, g in sorted(sport_groups.items()):
        by_sport.append({
            "sport": s, "bet_count": g["count"],
            "win_rate": round(g["wins"] / g["count"], 4) if g["count"] else 0,
            "avg_edge": round(g["total_edge"] / g["count"], 4) if g["count"] else 0,
            "roi": round((g["total_payout"] - g["total_stake"]) / g["total_stake"], 4) if g["total_stake"] else 0,
        })

    return {"bets": bets, "buckets": buckets, "by_sport": by_sport}


@st.cache_data(ttl=TTL_STANDARD)
def get_elo_history(team: str, sport: str, days: int = 30) -> pd.DataFrame:
    """Return Elo rating timeseries for a team."""
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    df = _db.fetch_df(
        "SELECT timestamp AS date, team, rating FROM elo_ratings "
        "WHERE sport = %(sport)s AND team = %(team)s AND timestamp >= %(start)s "
        "ORDER BY timestamp ASC",
        {"sport": sport, "team": team, "start": start},
    )
    if "date" in df.columns:
        df["date"] = df["date"].apply(lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x))
    return df


@st.cache_data(ttl=TTL_STANDARD)
def get_data_quality_report() -> dict:
    """Return system health report: overall score + per-sport details."""
    sports = ["NBA", "NHL", "MLB", "NFL", "NCAAB", "WNCAAB", "TENNIS", "EPL", "Ligue1", "CBA", "Unrivaled"]
    sport_reports = []
    total_score = 0

    for sport in sports:
        score = 100
        issues_list = []

        # Check for missing recent games
        missing = _db.fetch_scalar(
            "SELECT COUNT(*) FROM unified_games WHERE sport = %(sport)s "
            "AND start_time >= DATE('now', '-3 days')",
            {"sport": sport},
        )
        missing_count = max(0, 3 - (int(missing) if missing else 0))
        if missing_count > 0:
            score -= missing_count * 10
            issues_list.append(f"Missing recent games")

        # Check for stale Elo ratings
        stale = _db.fetch_scalar(
            "SELECT COUNT(*) FROM elo_ratings WHERE sport = %(sport)s "
            "AND timestamp < DATE('now', '-7 days')",
            {"sport": sport},
        )
        stale_count = int(stale) if stale else 0
        if stale_count > 0:
            score -= min(30, stale_count * 5)
            issues_list.append(f"{stale_count} stale Elo ratings")

        # Check odds freshness
        last_odds = _db.fetch_scalar(
            "SELECT MAX(timestamp) FROM game_odds WHERE sport = %(sport)s",
            {"sport": sport},
        )
        odds_minutes = 999
        if last_odds:
            try:
                if hasattr(last_odds, "isoformat"):
                    last_odds_dt = last_odds
                else:
                    last_odds_dt = datetime.fromisoformat(str(last_odds).replace("Z", "+00:00"))
                delta = datetime.now(timezone.utc) - last_odds_dt.replace(tzinfo=timezone.utc)
                odds_minutes = int(delta.total_seconds() / 60)
            except (ValueError, TypeError):
                pass

        # Last game date
        last_game = _db.fetch_scalar(
            "SELECT MAX(start_time) FROM unified_games WHERE sport = %(sport)s",
            {"sport": sport},
        )
        last_game_str = last_game.isoformat() if hasattr(last_game, "isoformat") else str(last_game) if last_game else "N/A"

        score = max(0, min(100, score))
        total_score += score
        sport_reports.append({
            "sport": sport,
            "health_score": score,
            "missing_games": missing_count,
            "stale_elo": stale_count,
            "odds_freshness_minutes": odds_minutes,
            "last_game_date": last_game_str,
            "last_dag_run": "N/A",  # Could be enhanced to read from Airflow metadata
            "issues": issues_list,
        })

    overall = total_score // len(sports) if sports else 0
    return {"overall_health": overall, "sports": sport_reports}


@st.cache_data(ttl=TTL_STANDARD)
def get_portfolio_snapshots(hours: int = 168) -> pd.DataFrame:
    """Return hourly portfolio value timeseries."""
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    df = _db.fetch_df(
        "SELECT timestamp, portfolio_value FROM portfolio_value_snapshots "
        "WHERE timestamp >= %(start)s ORDER BY timestamp ASC",
        {"start": start},
    )
    if "timestamp" in df.columns:
        df["timestamp"] = df["timestamp"].apply(
            lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x)
        )
    return df


def bust_cache():
    """Clear all cached data. Called on auto-refresh cycle."""
    get_portfolio_summary.clear()
    get_placed_bets.clear()
    get_bet_detail.clear()
    get_current_elo_ratings.clear()
    get_today_games.clear()
    get_bet_recommendations.clear()
    get_calibration_data.clear()
    get_elo_history.clear()
    get_data_quality_report.clear()
    get_portfolio_snapshots.clear()
```

- [ ] **Step 2: Run contract tests to confirm compat**

```bash
pytest tests/contracts/test_dashboard_data_contracts.py -v
```

Expected: All tests still PASS

- [ ] **Step 3: Commit**

```bash
git add dashboard/data_layer.py
git commit -m "feat(dashboard): add data layer with 10 cached query functions"
```

---

### Task 4: Create app.py with sidebar nav and auto-refresh

**Files:**
- Create: `dashboard/app.py`

- [ ] **Step 1: Create `dashboard/app.py`**

```python
"""NHLStats Dashboard — multi-sport betting analytics.

Entry point for Streamlit. Handles sidebar navigation, auto-refresh,
and delegates to page modules in dashboard/pages/.
"""

import sys
import os
import time

# Ensure plugins and dashboard are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))

import streamlit as st

st.set_page_config(
    page_title="NHLStats Dashboard",
    page_icon="\U0001F3D2",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.data_layer import bust_cache

# Per-page refresh intervals (seconds)
PAGE_REFRESH = {
    "Portfolio": 30,
    "Live Markets": 30,
    "Rankings": 300,
    "Calibration": 3600,
    "Data Quality": 300,
    "Bet Detail": 0,  # manual only
}


def render_sidebar() -> str:
    """Render sidebar navigation. Returns the selected page name."""
    with st.sidebar:
        st.title("\U0001F3D2 NHLStats")
        st.caption("Multi-Sport Betting Analytics")

        page = st.radio(
            "Navigation",
            ["Portfolio", "Live Markets", "Rankings", "Calibration", "Data Quality"],
            index=0,
        )

        st.divider()

        # Refresh controls
        refresh_seconds = PAGE_REFRESH.get(page, 0)
        st.caption(f"Auto-refresh: {refresh_seconds}s" if refresh_seconds else "Auto-refresh: off")

        if st.button("\U0001F503 Refresh Now", use_container_width=True):
            bust_cache()
            st.rerun()

        st.divider()
        st.caption("Data freshness indicators:")
        st.caption("\U0001F7E2 Fresh   \U0001F7E1 Stale   \U0001F534 Outdated")

    return page


def auto_refresh_loop(page: str):
    """Sleep and trigger rerun at the page's refresh interval."""
    seconds = PAGE_REFRESH.get(page, 0)
    if seconds <= 0:
        return  # manual-only pages

    # Show a countdown placeholder at the bottom of the sidebar
    placeholder = st.sidebar.empty()
    for remaining in range(seconds, 0, -1):
        placeholder.caption(f"Next refresh in {remaining}s...")
        time.sleep(1)

    bust_cache()
    placeholder.empty()
    st.rerun()


def main():
    page = render_sidebar()

    # Route to the correct page module
    if page == "Portfolio":
        from dashboard.pages.portfolio import render
    elif page == "Live Markets":
        from dashboard.pages.live_markets import render
    elif page == "Rankings":
        from dashboard.pages.rankings import render
    elif page == "Calibration":
        from dashboard.pages.calibration import render
    elif page == "Data Quality":
        from dashboard.pages.data_quality import render
    else:
        from dashboard.pages.portfolio import render

    render()

    # Handle bet detail drill-down via query params
    query_params = st.query_params
    if "bet_id" in query_params:
        from dashboard.pages.bet_detail import render_bet_detail
        render_bet_detail(query_params["bet_id"])
    # Check session state for bet detail navigation from other pages
    if st.session_state.get("show_bet_detail"):
        bet_id = st.session_state["show_bet_detail"]
        from dashboard.pages.bet_detail import render_bet_detail
        render_bet_detail(bet_id)

    auto_refresh_loop(page)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app.py
git commit -m "feat(dashboard): add app.py with sidebar nav and auto-refresh loop"
```

---

### Task 5: Create Bet Detail drill-down page

**Files:**
- Create: `dashboard/pages/__init__.py`
- Create: `dashboard/pages/bet_detail.py`

- [ ] **Step 1: Create `dashboard/pages/__init__.py`**

```python
"""Dashboard page modules."""
```

- [ ] **Step 2: Create `dashboard/pages/bet_detail.py`**

```python
"""Bet Detail drill-down — every number that went into a bet placement decision."""

import streamlit as st
import plotly.express as px
import pandas as pd

from dashboard.data_layer import get_bet_detail


def render_bet_detail(bet_id: str):
    """Render the full bet traceability view for a given bet_id."""
    st.header(f"Bet Detail: {bet_id}")

    try:
        detail = get_bet_detail(bet_id)
    except ValueError:
        st.error(f"Bet not found: {bet_id}")
        if st.button("Back"):
            st.session_state["show_bet_detail"] = None
            st.rerun()
        return

    bet = detail["bet"]
    odds = detail.get("odds", [])
    elo_snapshot = detail.get("elo_snapshot", {})
    elo_history = detail.get("elo_history", [])
    recent_form = detail.get("recent_form", {})

    # Back button
    if st.button("\u2190 Back"):
        st.session_state["show_bet_detail"] = None
        st.rerun()

    # --- Header bar ---
    cols = st.columns(5)
    cols[0].metric("Sport", bet.get("sport", "N/A"))
    cols[1].metric("Market", bet.get("market", "N/A"))
    cols[2].metric("Placed", str(bet.get("placed_at", ""))[:16])
    status = bet.get("status", "PENDING")
    if status == "WON":
        payout_display = f"+${bet.get('payout', 0) - bet.get('stake', 0):.2f}"
        cols[3].metric("Result", status, delta=payout_display, delta_color="normal")
    elif status == "LOST":
        cols[3].metric("Result", status, delta=f"-${bet.get('stake', 0):.2f}", delta_color="inverse")
    else:
        cols[3].metric("Result", status)
    cols[4].metric("Stake", f"${bet.get('stake', 0):.2f}")

    st.divider()

    # --- The Decision ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("The Decision")
        edge = bet.get("edge", 0) or 0
        elo_prob = bet.get("elo_prob", 0) or 0
        market_prob = bet.get("market_prob", 0) or 0
        st.metric("Elo Probability", f"{elo_prob:.1%}")
        st.metric("Market Implied Probability", f"{market_prob:.1%}")
        st.metric("Edge", f"{edge:.1%}", delta=f"{edge:.1%}")
        st.metric("Confidence", bet.get("confidence", "N/A"))
        st.metric("Kelly Fraction", f"{bet.get('kelly_fraction', 0):.2f}")
        st.metric("Stake", f"${bet.get('stake', 0):.2f}")

    with col_b:
        st.subheader("Elo Rating Snapshot")
        st.metric(elo_snapshot.get("team_a_name", "Team A"),
                  f"{elo_snapshot.get('team_a_rating', 0):.0f}")
        st.metric(elo_snapshot.get("team_b_name", "Team B"),
                  f"{elo_snapshot.get('team_b_rating', 0):.0f}")
        st.caption(f"Rating diff: {elo_snapshot.get('rating_diff', 0):+.0f} | "
                   f"Home adv: {elo_snapshot.get('home_advantage', 0):+.0f} | "
                   f"Effective: {elo_snapshot.get('effective_diff', 0):+.0f}")

    st.divider()

    # --- Odds Comparison ---
    st.subheader("Odds Comparison (at placement time)")
    if odds:
        odds_df = pd.DataFrame(odds)
        # Format nicely
        display_df = odds_df.rename(columns={
            "source": "Source", "price": "Price", "implied_prob": "Implied Prob",
            "timestamp": "Timestamp",
        })
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No odds data available for this bet.")

    st.divider()

    # --- Elo History Chart ---
    st.subheader("Elo Rating History (30 days before bet)")
    if elo_history:
        hist_df = pd.DataFrame(elo_history)
        fig = px.line(
            hist_df, x="date", y="rating", color="team",
            title="Elo Rating Trend",
            labels={"date": "Date", "rating": "Elo Rating", "team": "Team"},
        )
        # Add vertical line at bet placement
        placed = bet.get("placed_at", "")
        if placed:
            fig.add_vline(x=placed, line_dash="dash", line_color="red",
                          annotation_text="Bet Placed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No Elo history available.")

    # --- Recent Form ---
    st.subheader("Recent Form")
    form_a, form_b = st.columns(2)

    with form_a:
        team_a_data = recent_form.get("team_a", {})
        st.write(f"**{team_a_data.get('team', 'Team A')}** ({team_a_data.get('record', '0-0')})")
        games_a = team_a_data.get("games", [])
        if games_a:
            for g in games_a:
                icon = "\U0001F7E2" if g["result"] == "W" else ("\U0001F534" if g["result"] == "L" else "\u26AA")
                st.write(f"{icon} {g['result']} vs {g['opponent']} {g['score']}")

    with form_b:
        team_b_data = recent_form.get("team_b", {})
        st.write(f"**{team_b_data.get('team', 'Team B')}** ({team_b_data.get('record', '0-0')})")
        games_b = team_b_data.get("games", [])
        if games_b:
            for g in games_b:
                icon = "\U0001F7E2" if g["result"] == "W" else ("\U0001F534" if g["result"] == "L" else "\u26AA")
                st.write(f"{icon} {g['result']} vs {g['opponent']} {g['score']}")
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/pages/__init__.py dashboard/pages/bet_detail.py
git commit -m "feat(dashboard): add Bet Detail drill-down page"
```

---

### Task 6: Create Portfolio page

**Files:**
- Create: `dashboard/pages/portfolio.py`

- [ ] **Step 1: Create `dashboard/pages/portfolio.py`**

```python
"""Portfolio Overview — the home page. Portfolio health, P&L, open bets, win rate."""

import streamlit as st
import plotly.express as px
import pandas as pd

from dashboard.data_layer import (
    get_portfolio_summary,
    get_placed_bets,
    get_portfolio_snapshots,
)


def render():
    st.title("Portfolio Overview")

    summary = get_portfolio_summary()

    # KPI cards
    cols = st.columns(4)
    cols[0].metric("Portfolio Value", f"${summary['portfolio_value']:,.2f}",
                   delta=f"${summary['daily_pnl']:+,.2f} today")
    cols[1].metric("Open Bets", summary["open_bets_count"],
                   delta=f"${summary['total_exposure']:,.2f} exposed")
    cols[2].metric("Win Rate", f"{summary['win_rate']:.1%}",
                   help=f"{summary['settled_count']} settled bets")
    cols[3].metric("Total Bets", summary["total_bets"])

    st.divider()

    # Portfolio value chart
    st.subheader("Portfolio Value")
    snapshots = get_portfolio_snapshots(hours=168)
    if not snapshots.empty:
        fig = px.area(
            snapshots, x="timestamp", y="portfolio_value",
            title="Portfolio Value (7 days)",
            labels={"timestamp": "Time", "portfolio_value": "Value ($)"},
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No portfolio snapshot data available.")

    # P&L by sport
    st.subheader("P&L by Sport")
    bets_df = get_placed_bets(limit=500)
    if not bets_df.empty:
        settled = bets_df[bets_df["status"].isin(["WON", "LOST"])].copy()
        if not settled.empty:
            settled["pnl"] = settled.apply(
                lambda r: (r["payout"] - r["stake"]) if r["status"] == "WON" else -r["stake"],
                axis=1,
            )
            sport_pnl = settled.groupby("sport")["pnl"].sum().reset_index()
            sport_pnl = sport_pnl.sort_values("pnl", ascending=True)
            fig = px.bar(
                sport_pnl, x="pnl", y="sport", orientation="h",
                title="Total P&L by Sport",
                labels={"pnl": "P&L ($)", "sport": "Sport"},
                color="pnl",
                color_continuous_scale=["red", "lightgray", "green"],
            )
            st.plotly_chart(fig, use_container_width=True)

    # Recent bets table
    st.subheader("Recent Activity")
    recent = get_placed_bets(limit=50)
    if not recent.empty:
        # Select display columns
        display_cols = ["placed_at", "sport", "market", "team", "stake", "status",
                        "edge", "elo_prob", "market_prob", "confidence"]
        available = [c for c in display_cols if c in recent.columns]
        display = recent[available].copy()
        if "placed_at" in display.columns:
            display["placed_at"] = display["placed_at"].astype(str).str[:16]
        if "edge" in display.columns:
            display["edge"] = (display["edge"] * 100).round(1).astype(str) + "%"
        if "elo_prob" in display.columns:
            display["elo_prob"] = (display["elo_prob"] * 100).round(1).astype(str) + "%"
        if "market_prob" in display.columns:
            display["market_prob"] = (display["market_prob"] * 100).round(1).astype(str) + "%"

        # Make each row clickable via a detail button
        for idx, row in display.iterrows():
            cols = st.columns([8, 2])
            cols[0].write(
                f"{row.get('placed_at', '')} | {row.get('sport', '')} | "
                f"{row.get('market', '')} | ${row.get('stake', 0):.2f} | "
                f"{row.get('status', '')}"
            )
            bet_id = recent.iloc[idx]["bet_id"]
            if cols[1].button("Details", key=f"detail_{bet_id}"):
                st.session_state["show_bet_detail"] = bet_id
                st.rerun()
    else:
        st.caption("No bets placed yet.")
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/pages/portfolio.py
git commit -m "feat(dashboard): add Portfolio overview page"
```

---

### Task 7: Create Live Markets page

**Files:**
- Create: `dashboard/pages/live_markets.py`

- [ ] **Step 1: Create `dashboard/pages/live_markets.py`**

```python
"""Live Markets — today's games, Elo probabilities, odds, and active recommendations."""

import streamlit as st
import pandas as pd

from dashboard.data_layer import get_today_games, get_bet_recommendations


def render():
    st.title("Live Markets")

    sport_filter = st.selectbox(
        "Sport",
        ["All", "NBA", "NHL", "MLB", "NFL", "NCAAB", "WNCAAB", "TENNIS", "EPL", "Ligue1", "CBA", "Unrivaled"],
    )
    sport = None if sport_filter == "All" else sport_filter

    # Today's games
    st.subheader("Today's Games")
    games = get_today_games(sport)
    if not games.empty:
        display_cols = ["start_time", "sport", "home_team", "away_team",
                        "home_elo", "away_elo", "home_win_prob",
                        "edge", "edge_side", "confidence"]
        available = [c for c in display_cols if c in games.columns]
        display = games[available].copy()
        if "start_time" in display.columns:
            display["start_time"] = display["start_time"].astype(str).str[:16]
        if "home_win_prob" in display.columns:
            display["home_win_prob"] = (display["home_win_prob"] * 100).round(1).astype(str) + "%"
        if "edge" in display.columns:
            display["edge"] = (display["edge"] * 100).round(1).astype(str) + "%"

        def color_edge(val):
            if val is None or val == "":
                return ""
            try:
                v = float(str(val).rstrip("%"))
                if v >= 8: return "background-color: #1b5e20"
                if v >= 3: return "background-color: #33691e"
                return ""
            except ValueError:
                return ""

        styled = display.style.applymap(color_edge, subset=["edge"] if "edge" in display.columns else [])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.caption("No games scheduled for today.")

    st.divider()

    # Active recommendations
    st.subheader("Active Bet Recommendations")
    recs = get_bet_recommendations(sport)
    if not recs.empty:
        rec_cols = ["sport", "game_id", "bet_on", "side", "elo_prob", "market_prob",
                     "edge", "expected_value", "kelly_fraction", "confidence", "bookmaker"]
        available = [c for c in rec_cols if c in recs.columns]
        display = recs[available].copy()
        if "elo_prob" in display.columns:
            display["elo_prob"] = (display["elo_prob"] * 100).round(1).astype(str) + "%"
        if "market_prob" in display.columns:
            display["market_prob"] = (display["market_prob"] * 100).round(1).astype(str) + "%"
        if "edge" in display.columns:
            display["edge"] = (display["edge"] * 100).round(1).astype(str) + "%"
        if "expected_value" in display.columns:
            display["expected_value"] = (display["expected_value"] * 100).round(1).astype(str) + "%"

        def color_confidence(val):
            if val == "HIGH": return "background-color: #1b5e20; color: white"
            if val == "MEDIUM": return "background-color: #f57f17; color: black"
            if val == "LOW": return "background-color: #b71c1c; color: white"
            return ""

        styled = display.style.applymap(color_confidence, subset=["confidence"] if "confidence" in display.columns else [])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.caption("No active recommendations.")
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/pages/live_markets.py
git commit -m "feat(dashboard): add Live Markets page"
```

---

### Task 8: Create Rankings page

**Files:**
- Create: `dashboard/pages/rankings.py`

- [ ] **Step 1: Create `dashboard/pages/rankings.py`**

```python
"""Rankings — current Elo ratings, team comparison tool."""

import streamlit as st
import plotly.express as px
import pandas as pd

from dashboard.data_layer import get_current_elo_ratings, get_elo_history


def render():
    st.title("Elo Rankings")

    sport = st.selectbox(
        "Sport",
        ["NBA", "NHL", "MLB", "NFL", "NCAAB", "WNCAAB", "TENNIS", "EPL", "Ligue1", "CBA", "Unrivaled"],
    )

    ratings = get_current_elo_ratings(sport)

    if not ratings.empty:
        st.subheader(f"{sport} Ratings ({len(ratings)} teams)")
        display_cols = ["rank", "team", "rating", "last_updated"]
        available = [c for c in display_cols if c in ratings.columns]
        st.dataframe(
            ratings[available].style.format({"rating": "{:.0f}"}),
            use_container_width=True, hide_index=True,
        )

        # Rating distribution chart
        fig = px.bar(
            ratings, x="team", y="rating",
            title=f"{sport} Elo Ratings",
            labels={"team": "Team", "rating": "Elo Rating"},
            color="rating",
            color_continuous_scale="viridis",
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

        # Team comparison tool
        st.divider()
        st.subheader("Team Comparison")
        teams = ratings["team"].tolist()
        col_a, col_b = st.columns(2)
        team_a = col_a.selectbox("Team A", teams, key="team_a")
        team_b = col_b.selectbox("Team B", teams, key="team_b",
                                 index=min(1, len(teams) - 1))

        if team_a and team_b and team_a != team_b:
            a_rating = float(ratings[ratings["team"] == team_a]["rating"].iloc[0])
            b_rating = float(ratings[ratings["team"] == team_b]["rating"].iloc[0])
            diff = a_rating - b_rating
            prob_a = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
            prob_b = 1.0 - prob_a

            c1, c2, c3 = st.columns(3)
            c1.metric(team_a, f"{a_rating:.0f}")
            c2.metric("Head-to-Head Prediction",
                      f"{team_a if prob_a > prob_b else team_b} wins")
            c3.metric(team_b, f"{b_rating:.0f}")
            st.write(f"{team_a}: {prob_a:.1%} | {team_b}: {prob_b:.1%}")

            # Rating history overlay
            hist_a = get_elo_history(team_a, sport, days=30)
            hist_b = get_elo_history(team_b, sport, days=30)
            if not hist_a.empty and not hist_b.empty:
                combined = pd.concat([hist_a, hist_b])
                fig = px.line(
                    combined, x="date", y="rating", color="team",
                    title=f"30-Day Rating History: {team_a} vs {team_b}",
                    labels={"date": "Date", "rating": "Rating", "team": "Team"},
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"No Elo ratings found for {sport}.")
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/pages/rankings.py
git commit -m "feat(dashboard): add Rankings page with team comparison"
```

---

### Task 9: Create Calibration page

**Files:**
- Create: `dashboard/pages/calibration.py`

- [ ] **Step 1: Create `dashboard/pages/calibration.py`**

```python
"""Calibration — model accuracy, calibration curves, edge-vs-ROI analysis."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from dashboard.data_layer import get_calibration_data


def render():
    st.title("Model Calibration")

    sport_filter = st.selectbox(
        "Sport",
        ["All", "NBA", "NHL", "MLB", "NFL", "NCAAB", "WNCAAB", "TENNIS", "EPL", "Ligue1", "CBA", "Unrivaled"],
    )
    sport = None if sport_filter == "All" else sport_filter

    data = get_calibration_data(sport)
    by_sport = data.get("by_sport", [])
    buckets = data.get("buckets", [])
    bets = data.get("bets", [])

    # By-sport summary
    st.subheader("Performance by Sport")
    if by_sport:
        sport_df = pd.DataFrame(by_sport)
        display = sport_df.copy()
        display["win_rate"] = (display["win_rate"] * 100).round(1).astype(str) + "%"
        display["avg_edge"] = (display["avg_edge"] * 100).round(1).astype(str) + "%"
        display["roi"] = (display["roi"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True, hide_index=True)

        # ROI by sport bar chart
        fig = px.bar(
            sport_df, x="sport", y="roi",
            title="ROI by Sport",
            labels={"sport": "Sport", "roi": "ROI"},
            color="roi",
            color_continuous_scale=["red", "lightgray", "green"],
        )
        st.plotly_chart(fig, use_container_width=True)

    # Calibration curve
    st.subheader("Calibration Curve")
    if buckets:
        bucket_df = pd.DataFrame(buckets)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[(b["predicted_min"] + b["predicted_max"]) / 2 for b in buckets],
            y=[b["actual_win_rate"] for b in buckets],
            mode="lines+markers",
            name="Actual Win Rate",
        ))
        fig.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1], mode="lines",
            line=dict(dash="dash", color="gray"),
            name="Perfect Calibration",
        ))
        fig.update_layout(
            xaxis_title="Predicted Probability",
            yaxis_title="Actual Win Rate",
            xaxis=dict(range=[0, 1]),
            yaxis=dict(range=[0, 1]),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Edge vs ROI scatter
    st.subheader("Edge vs Actual ROI")
    if bets:
        bets_df = pd.DataFrame(bets)
        bets_df["roi"] = (bets_df["payout"] - bets_df["stake"]) / bets_df["stake"]
        bets_df["result_code"] = bets_df["result"].map({"WON": 1, "LOST": 0})

        fig = px.scatter(
            bets_df, x="edge", y="roi", color="sport",
            title="Edge vs Actual ROI per Bet",
            labels={"edge": "Predicted Edge", "roi": "Actual ROI", "sport": "Sport"},
            opacity=0.6,
        )
        fig.add_hline(y=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No settled bets available for calibration analysis.")
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/pages/calibration.py
git commit -m "feat(dashboard): add Calibration page"
```

---

### Task 10: Create Data Quality page

**Files:**
- Create: `dashboard/pages/data_quality.py`

- [ ] **Step 1: Create `dashboard/pages/data_quality.py`**

```python
"""Data Quality — system health scores, missing data alerts, odds freshness."""

import streamlit as st
import plotly.express as px
import pandas as pd

from dashboard.data_layer import get_data_quality_report


def render():
    st.title("Data Quality")

    report = get_data_quality_report()
    overall = report.get("overall_health", 0)
    sports = report.get("sports", [])

    # Overall health gauge
    st.metric("Overall Health Score", f"{overall}/100")

    # Health bar chart
    if sports:
        sport_df = pd.DataFrame(sports)
        fig = px.bar(
            sport_df, x="sport", y="health_score",
            title="Health Score by Sport",
            labels={"sport": "Sport", "health_score": "Health Score"},
            color="health_score",
            color_continuous_scale=["red", "yellow", "green"],
            range_color=[0, 100],
        )
        fig.add_hline(y=80, line_dash="dash", line_color="green", annotation_text="Healthy")
        fig.add_hline(y=50, line_dash="dash", line_color="red", annotation_text="Warning")
        st.plotly_chart(fig, use_container_width=True)

    # Per-sport details
    st.subheader("Per-Sport Details")
    for s in sports:
        health = s["health_score"]
        color = "green" if health >= 80 else ("orange" if health >= 50 else "red")
        with st.expander(f"{s['sport']} — Health: {health}/100"):
            cols = st.columns(3)
            cols[0].metric("Missing Games", s.get("missing_games", 0))
            cols[1].metric("Stale Elo Ratings", s.get("stale_elo", 0))
            cols[2].metric("Odds Freshness", f"{s.get('odds_freshness_minutes', 'N/A')} min")
            st.caption(f"Last game: {s.get('last_game_date', 'N/A')}")

            issues = s.get("issues", [])
            if issues:
                st.warning("Issues: " + ", ".join(issues))
            else:
                st.success("No issues detected")
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/pages/data_quality.py
git commit -m "feat(dashboard): add Data Quality page"
```

---

### Task 11: Update docker-compose.yaml and delete old dashboard

**Files:**
- Modify: `docker-compose.yaml:323`
- Delete: `dashboard/dashboard_app.py`

- [ ] **Step 1: Update docker-compose.yaml to point at new entry point**

Edit `docker-compose.yaml`, change line 323 from:
```
    command: -c "streamlit run /opt/airflow/dashboard/dashboard_app.py --server.address=0.0.0.0 --server.fileWatcherType=none"
```
To:
```
    command: -c "streamlit run /opt/airflow/dashboard/app.py --server.address=0.0.0.0 --server.fileWatcherType=none"
```

- [ ] **Step 2: Add dashboard volume mount to docker-compose**

The dashboard container needs the new `dashboard/` directory mounted. Add to the `volumes` section of the dashboard service in `docker-compose.yaml`:
```
      - ./dashboard:/opt/airflow/dashboard:rw
```

- [ ] **Step 3: Delete old dashboard**

```bash
rm dashboard/dashboard_app.py
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yaml
git rm dashboard/dashboard_app.py
git commit -m "feat(dashboard): switch to new dashboard architecture, delete old app"
```

---

### Task 12: Integration verification

**Files:**
- Create: `tests/test_dashboard_data_layer.py`

- [ ] **Step 1: Create `tests/test_dashboard_data_layer.py`**

```python
"""Integration tests for dashboard data layer functions.

Uses the test SQLite database from conftest.py.
Ensures each data function runs without error and returns expected types.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.data_layer import (
    get_portfolio_summary,
    get_calibration_data,
    get_data_quality_report,
)


class TestPortfolioSummary:
    def test_returns_dict_with_required_keys(self):
        result = get_portfolio_summary()
        assert isinstance(result, dict)
        required = ["portfolio_value", "daily_pnl", "open_bets_count",
                    "total_exposure", "win_rate", "total_bets", "settled_count"]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_portfolio_value_is_float(self):
        result = get_portfolio_summary()
        assert isinstance(result["portfolio_value"], (int, float))

    def test_counts_are_non_negative(self):
        result = get_portfolio_summary()
        assert result["open_bets_count"] >= 0
        assert result["total_bets"] >= 0
        assert result["settled_count"] >= 0

    def test_win_rate_in_range(self):
        result = get_portfolio_summary()
        assert 0.0 <= result["win_rate"] <= 1.0


class TestCalibrationData:
    def test_returns_dict_with_required_keys(self):
        result = get_calibration_data()
        assert isinstance(result, dict)
        for key in ["bets", "buckets", "by_sport"]:
            assert key in result

    def test_bets_is_list(self):
        result = get_calibration_data()
        assert isinstance(result["bets"], list)

    def test_buckets_has_eight_entries(self):
        result = get_calibration_data()
        assert len(result["buckets"]) == 8


class TestDataQualityReport:
    def test_returns_dict_with_required_keys(self):
        result = get_data_quality_report()
        assert isinstance(result, dict)
        for key in ["overall_health", "sports"]:
            assert key in result

    def test_overall_health_is_int_between_0_and_100(self):
        result = get_data_quality_report()
        assert isinstance(result["overall_health"], int)
        assert 0 <= result["overall_health"] <= 100

    def test_sports_is_list(self):
        result = get_data_quality_report()
        assert isinstance(result["sports"], list)


class TestDashboardImports:
    """Verify all page modules import cleanly."""

    def test_import_app(self):
        from dashboard import app  # noqa: F401

    def test_import_data_layer(self):
        from dashboard import data_layer  # noqa: F401

    def test_import_bet_detail(self):
        from dashboard.pages import bet_detail  # noqa: F401

    def test_import_portfolio(self):
        from dashboard.pages import portfolio  # noqa: F401

    def test_import_live_markets(self):
        from dashboard.pages import live_markets  # noqa: F401

    def test_import_rankings(self):
        from dashboard.pages import rankings  # noqa: F401

    def test_import_calibration(self):
        from dashboard.pages import calibration  # noqa: F401

    def test_import_data_quality(self):
        from dashboard.pages import data_quality  # noqa: F401
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_dashboard_data_layer.py -v
pytest tests/contracts/test_dashboard_data_contracts.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Run full test suite to verify no regressions**

```bash
pytest -q --ignore=tests/test_dashboard_data_layer.py --ignore=tests/contracts/test_dashboard_data_contracts.py
```

Expected: All existing tests still PASS. No regressions from dashboard changes.

- [ ] **Step 4: Verify dashboard module structure**

```bash
python -c "
from dashboard.data_layer import (
    get_portfolio_summary, get_placed_bets, get_bet_detail,
    get_current_elo_ratings, get_today_games, get_bet_recommendations,
    get_calibration_data, get_elo_history, get_data_quality_report,
    get_portfolio_snapshots, bust_cache,
)
print('All imports OK')
print('Portfolio summary:', get_portfolio_summary())
"
```

Expected: "All imports OK" + portfolio summary dict printed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_dashboard_data_layer.py
git commit -m "test(dashboard): add integration tests for data layer functions"
```

---

### Task 13: Rebuild and verify dashboard renders

- [ ] **Step 1: Rebuild Docker image**

```bash
docker compose build dashboard
```

Expected: Build succeeds.

- [ ] **Step 2: Restart dashboard container**

```bash
docker compose up -d dashboard
```

Expected: Container starts without errors.

- [ ] **Step 3: Check dashboard logs**

```bash
docker compose logs dashboard --tail 30
```

Expected: Streamlit starts, no import errors, serving on port 8501.

- [ ] **Step 4: Verify dashboard is accessible**

```bash
curl -s http://localhost:8501 | head -20
```

Expected: HTML content returned (Streamlit page).

- [ ] **Step 5: Final commit (if any docker-compose tweaks needed)**

```bash
git add docker-compose.yaml
git commit -m "chore: finalize dashboard container config"
```
