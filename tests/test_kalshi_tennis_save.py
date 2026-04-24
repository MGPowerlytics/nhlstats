"""Tests for Kalshi tennis save flow.

Validates that the new tennis-specific Kalshi save path consolidates one-sided
binary markets into a single unified game with full player names and
correctly-mapped odds rows.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _build_market(
    ticker: str,
    event_ticker: str,
    yes_sub_title: str,
    yes_ask: int,
    title: str,
) -> Dict[str, Any]:
    return {
        "ticker": ticker,
        "event_ticker": event_ticker,
        "yes_sub_title": yes_sub_title,
        "no_sub_title": yes_sub_title,
        "yes_ask": yes_ask,
        "no_ask": 100 - yes_ask,
        "title": title,
        "close_time": "2026-04-21T09:00:00Z",
        "status": "active",
    }


class _FakeDB:
    def __init__(self) -> None:
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    def execute(self, sql: str, params: Dict[str, Any] | None = None) -> None:
        self.calls.append((sql, params or {}))

    def fetch_scalar(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def test_tennis_save_aggregates_event_into_unified_game() -> None:
    """Both YES-side markets for a matchup should produce one game + two odds."""
    from plugins import kalshi_markets

    markets = [
        _build_market(
            "KXATPMATCH-26APR07COBBLO-COB",
            "KXATPMATCH-26APR07COBBLO",
            "Flavio Cobolli",
            66,
            "Will Flavio Cobolli win the Cobolli vs Blockx : Round Of 32 match?",
        ),
        _build_market(
            "KXATPMATCH-26APR07COBBLO-BLO",
            "KXATPMATCH-26APR07COBBLO",
            "Alexander Blockx",
            38,
            "Will Alexander Blockx win the Cobolli vs Blockx : Round Of 32 match?",
        ),
    ]

    db = _FakeDB()
    with patch("plugins.database_schema_manager.DatabaseSchemaManager") as mock_schema:
        mock_schema.return_value.initialize_schema.return_value = None
        odds_count = kalshi_markets.save_to_db("tennis", markets, db_manager=db)

    assert odds_count == 2

    # Inspect SQL fingerprints
    unified_inserts = [c for c in db.calls if "INSERT INTO unified_games" in c[0]]
    odds_inserts = [c for c in db.calls if "INSERT INTO game_odds" in c[0]]

    # Exactly one unified game row, two odds rows (home + away)
    assert len(unified_inserts) == 1
    assert len(odds_inserts) == 2

    game_params = unified_inserts[0][1]
    # Alphabetical sort on full names: Alexander Blockx < Flavio Cobolli
    assert game_params["home_name"] == "Alexander Blockx"
    assert game_params["away_name"] == "Flavio Cobolli"
    assert game_params["sport"] == "TENNIS"
    assert game_params["game_date"] == "2026-04-07"
    assert game_params["game_id"].startswith("TENNIS_ATP_2026-04-07_")

    outcome_to_ticker = {
        c[1]["outcome_name"]: c[1]["ticker"] for c in odds_inserts
    }
    assert outcome_to_ticker["home"].endswith("-BLO")
    assert outcome_to_ticker["away"].endswith("-COB")

    # Decimal odds = 100 / yes_ask_cents
    home_price = next(
        c[1]["price"] for c in odds_inserts if c[1]["outcome_name"] == "home"
    )
    assert abs(home_price - (100 / 38)) < 1e-6


def test_tennis_save_handles_single_market_event() -> None:
    """If only one market is present we still hydrate the opponent slot from
    the title's '<X> vs <Y>' segment so the matchup gets a unified row."""
    from plugins import kalshi_markets

    markets = [
        _build_market(
            "KXATPMATCH-26APR06DJOMED-MED",
            "KXATPMATCH-26APR06DJOMED",
            "Daniil Medvedev",
            56,
            "Will Daniil Medvedev win the Djokovic vs Medvedev : Round Of 32 match?",
        ),
    ]

    db = _FakeDB()
    with patch("plugins.database_schema_manager.DatabaseSchemaManager") as mock_schema:
        mock_schema.return_value.initialize_schema.return_value = None
        odds_count = kalshi_markets.save_to_db("tennis", markets, db_manager=db)

    # We saved one market => one odds row, but the unified game should exist
    assert odds_count == 1
    unified = [c for c in db.calls if "INSERT INTO unified_games" in c[0]]
    assert len(unified) == 1
    params = unified[0][1]
    # Daniil Medvedev < Djokovic alphabetically (D<D, then a<j)
    assert params["home_name"] == "Daniil Medvedev"
    assert params["away_name"] == "Djokovic"


def test_tennis_save_skips_event_with_no_resolvable_players() -> None:
    """Markets without yes_sub_title or 'Will X win' title prefix are skipped."""
    from plugins import kalshi_markets

    markets = [
        {
            "ticker": "KXATPMATCH-26APR07XYZABC-XYZ",
            "event_ticker": "KXATPMATCH-26APR07XYZABC",
            "yes_ask": 50,
            "title": "garbage title",
            "close_time": "2026-04-07T09:00:00Z",
        }
    ]

    db = _FakeDB()
    with patch("plugins.database_schema_manager.DatabaseSchemaManager") as mock_schema:
        mock_schema.return_value.initialize_schema.return_value = None
        odds_count = kalshi_markets.save_to_db("tennis", markets, db_manager=db)

    assert odds_count == 0
    assert not [c for c in db.calls if "INSERT INTO unified_games" in c[0]]


def test_fetch_tennis_markets_uses_kalshi_path() -> None:
    """fetch_tennis_markets must delegate to the shared Kalshi helper."""
    from plugins import kalshi_markets

    with patch.object(
        kalshi_markets, "_fetch_sport_markets", return_value=[{"ticker": "x"}]
    ) as mock_fetch:
        result = kalshi_markets.fetch_tennis_markets("2026-04-07")

    mock_fetch.assert_called_once_with("tennis")
    assert result == [{"ticker": "x"}]


def test_kalshi_tennis_tour_detection() -> None:
    from plugins.kalshi_markets import _kalshi_tennis_tour

    assert _kalshi_tennis_tour("KXATPMATCH-26APR07COBBLO") == "ATP"
    assert _kalshi_tennis_tour("KXWTAMATCH-26APR07COBBLO") == "WTA"
    assert _kalshi_tennis_tour("KXATPCHALLENGERMATCH-26APR07ABC") == "ATP"
    assert _kalshi_tennis_tour("KXWTACHALLENGERMATCH-26APR07ABC") == "WTA"
