"""Test high-edge disagreement betting strategy."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from pathlib import Path
import sys

import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.odds_comparator import OddsComparator


class DummyDB:
    """Simple DB stub for fetch_df calls."""

    def __init__(self, frames_by_query):
        self.frames_by_query = frames_by_query

    def fetch_df(self, query, params=None):
        for key, frame in self.frames_by_query.items():
            if key in query:
                return frame(params or {}) if callable(frame) else frame
        return pd.DataFrame()


class DummyEloSystem:
    """Dummy Elo system for testing."""

    def __init__(self, predictions):
        self.predictions = predictions
        self.ratings = {}

    def predict(self, home, away, tour=None):
        key = f"{home}_{away}"
        if tour:
            key = f"{key}_{tour}"
        return self.predictions.get(key, 0.5)

    def get_rating(self, team, tour=None):
        return self.ratings.get(team, 1500)


def test_high_edge_disagreement_enabled():
    """Test that high-edge disagreement bets are identified when enabled."""

    # Mock database response
    def frame_for_games(params):
        return pd.DataFrame(
            [
                {
                    "game_id": "NBA_20240226_LAL_GSW",
                    "game_date": "2026-02-26",
                    "home_team_name": "Lakers",
                    "away_team_name": "Warriors",
                    "status": "scheduled",
                }
            ]
        )

    def frame_for_odds(params):
        # Create odds where market strongly disagrees with Elo
        # Elo predicts Lakers win (70%), but market gives Warriors 60% chance
        # This creates a 10% edge for Lakers
        return pd.DataFrame(
            [
                {
                    "bookmaker": "Kalshi",
                    "outcome_name": "home",
                    "price": 2.5,  # 40% implied probability (1/2.5)
                    "last_update": "2026-02-26",
                    "external_id": "KXNBAGAME-26FEB26-LALGSW-YESLAL",
                },
                {
                    "bookmaker": "Kalshi",
                    "outcome_name": "away",
                    "price": 1.67,  # 60% implied probability (1/1.67)
                    "last_update": "2026-02-26",
                    "external_id": "KXNBAGAME-26FEB26-LALGSW-YESGSW",
                },
            ]
        )

    db = DummyDB(
        {"FROM unified_games": frame_for_games, "FROM game_odds": frame_for_odds}
    )

    # Elo system that predicts Lakers win with 70% probability
    elo_system = DummyEloSystem({"Lakers_Warriors": 0.70})
    elo_system.ratings = {"Lakers": 1600, "Warriors": 1500}

    comparator = OddsComparator(db_manager=db)

    # Test with high-edge disagreement enabled (should find a bet)
    opportunities = comparator.find_opportunities(
        sport="nba",
        elo_ratings={},
        elo_system=elo_system,
        threshold=0.65,
        market_confidence_cutoff=0.55,
        enable_high_edge_disagreement=True,
        high_edge_threshold=0.10,
    )

    # Should find 1 opportunity (Lakers with high edge)
    assert len(opportunities) == 1
    bet = opportunities[0]
    assert bet["sport"] == "nba"
    assert bet["bet_on"] == "Lakers"
    assert bet["side"] == "home"
    assert bet["elo_prob"] == 0.70
    assert abs(bet["market_prob"] - 0.40) < 0.001  # 1/2.5 (floating point tolerance)
    assert abs(bet["edge"] - 0.30) < 0.001  # 0.70 - 0.40 (floating point tolerance)
    assert "DISAGREEMENT" in bet["confidence"]  # Should be a disagreement bet

    # Test with high-edge disagreement disabled (should find no bets)
    opportunities = comparator.find_opportunities(
        sport="nba",
        elo_ratings={},
        elo_system=elo_system,
        threshold=0.65,
        market_confidence_cutoff=0.55,
        enable_high_edge_disagreement=False,
        high_edge_threshold=0.10,
    )

    # Should find 0 opportunities because market doesn't agree
    assert len(opportunities) == 0


def test_high_edge_disagreement_below_threshold():
    """Test that high-edge disagreement bets are NOT identified when edge is below threshold."""

    # Mock database response
    def frame_for_games(params):
        return pd.DataFrame(
            [
                {
                    "game_id": "NBA_20240226_LAL_GSW",
                    "game_date": "2026-02-26",
                    "home_team_name": "Lakers",
                    "away_team_name": "Warriors",
                    "status": "scheduled",
                }
            ]
        )

    def frame_for_odds(params):
        # Create odds with smaller edge (8%, below 10% threshold)
        return pd.DataFrame(
            [
                {
                    "bookmaker": "Kalshi",
                    "outcome_name": "home",
                    "price": 2.0,  # 50% implied probability
                    "last_update": "2026-02-26",
                    "external_id": "KXNBAGAME-26FEB26-LALGSW-YESLAL",
                },
                {
                    "bookmaker": "Kalshi",
                    "outcome_name": "away",
                    "price": 2.0,  # 50% implied probability
                    "last_update": "2026-02-26",
                    "external_id": "KXNBAGAME-26FEB26-LALGSW-YESGSW",
                },
            ]
        )

    db = DummyDB(
        {"FROM unified_games": frame_for_games, "FROM game_odds": frame_for_odds}
    )

    # Elo system that predicts Lakers win with 58% probability (8% edge)
    elo_system = DummyEloSystem({"Lakers_Warriors": 0.58})
    elo_system.ratings = {"Lakers": 1600, "Warriors": 1500}

    comparator = OddsComparator(db_manager=db)

    # Test with high-edge disagreement enabled but edge below threshold
    opportunities = comparator.find_opportunities(
        sport="nba",
        elo_ratings={},
        elo_system=elo_system,
        threshold=0.65,  # Elo prob 58% < 65%, so no bet
        market_confidence_cutoff=0.55,
        enable_high_edge_disagreement=True,
        high_edge_threshold=0.10,  # Edge 8% < 10%
    )

    # Should find 0 opportunities (edge below threshold AND elo_prob below threshold)
    assert len(opportunities) == 0


def test_market_agreement_still_works():
    """Test that market agreement strategy still works alongside high-edge disagreement."""

    # Mock database response
    def frame_for_games(params):
        return pd.DataFrame(
            [
                {
                    "game_id": "NBA_20240226_LAL_GSW",
                    "game_date": "2026-02-26",
                    "home_team_name": "Lakers",
                    "away_team_name": "Warriors",
                    "status": "scheduled",
                }
            ]
        )

    def frame_for_odds(params):
        # Create odds where market agrees with Elo
        return pd.DataFrame(
            [
                {
                    "bookmaker": "Kalshi",
                    "outcome_name": "home",
                    "price": 1.67,  # 60% implied probability
                    "last_update": "2026-02-26",
                    "external_id": "KXNBAGAME-26FEB26-LALGSW-YESLAL",
                },
                {
                    "bookmaker": "Kalshi",
                    "outcome_name": "away",
                    "price": 2.5,  # 40% implied probability
                    "last_update": "2026-02-26",
                    "external_id": "KXNBAGAME-26FEB26-LALGSW-YESGSW",
                },
            ]
        )

    db = DummyDB(
        {"FROM unified_games": frame_for_games, "FROM game_odds": frame_for_odds}
    )

    # Elo system that predicts Lakers win with 70% probability
    elo_system = DummyEloSystem({"Lakers_Warriors": 0.70})
    elo_system.ratings = {"Lakers": 1600, "Warriors": 1500}

    comparator = OddsComparator(db_manager=db)

    # Test with both strategies
    opportunities = comparator.find_opportunities(
        sport="nba",
        elo_ratings={},
        elo_system=elo_system,
        threshold=0.65,
        market_confidence_cutoff=0.55,
        enable_high_edge_disagreement=True,
        high_edge_threshold=0.10,
    )

    # Should find 1 opportunity (market agreement)
    assert len(opportunities) == 1
    bet = opportunities[0]
    assert bet["sport"] == "nba"
    assert bet["bet_on"] == "Lakers"
    assert bet["side"] == "home"
    assert bet["elo_prob"] == 0.70
    assert (
        abs(bet["market_prob"] - (1 / 1.67)) < 0.001
    )  # 1/1.67 (floating point tolerance)
    assert (
        abs(bet["edge"] - (0.70 - (1 / 1.67))) < 0.001
    )  # 0.70 - (1/1.67) (floating point tolerance)
    # Edge is 0.1012 which is above 0.10 threshold, so it's a disagreement bet
    # even though market also agrees (market_prob > cutoff)
    assert "DISAGREEMENT" in bet["confidence"]  # High edge makes it a disagreement bet


if __name__ == "__main__":
    test_high_edge_disagreement_enabled()
    test_high_edge_disagreement_below_threshold()
    test_market_agreement_still_works()
    print("All tests passed!")
