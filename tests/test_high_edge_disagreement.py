"""Test positive EV edge-based betting strategy."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from pathlib import Path
import sys

import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.odds_comparator import (
    OddsComparator,
    BettingThresholds,
    BettingOpportunityConfig,
)


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
        if key in self.predictions:
            return self.predictions[key]
        return next(iter(self.predictions.values()), 0.5)

    def get_rating(self, team, tour=None):
        return self.ratings.get(team, 1500)


def test_large_positive_edge_bet():
    """Test that large positive edge bets are identified with HIGH confidence."""

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

    # Elo predicts Lakers win with 70% vs market's 40% = 30% edge
    elo_system = DummyEloSystem({"Lakers_Warriors": 0.70})
    elo_system.ratings = {"Lakers": 1600, "Warriors": 1500}

    comparator = OddsComparator(db_manager=db)

    opportunities = comparator.find_opportunities(
        config=BettingOpportunityConfig(
            sport="nba",
            elo_system=elo_system,
            thresholds=BettingThresholds(
                min_edge=0.05,
                max_edge=1.0,
            ),
        )
    )

    assert len(opportunities) == 1
    bet = opportunities[0]
    assert bet["sport"] == "nba"
    assert bet["bet_on"] == "Lakers"
    assert bet["side"] == "home"
    assert bet["elo_prob"] == 0.70
    assert abs(bet["market_prob"] - 0.40) < 0.001
    assert abs(bet["edge"] - 0.30) < 0.001
    # Edge >= 15% = HIGH confidence
    assert bet["confidence"] == "HIGH"


def test_small_edge_below_threshold_no_bet():
    """Test that bets below minimum edge threshold are NOT identified."""

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

    # Elo predicts Lakers win with 53% vs market's 50% = only 3% edge (below 5% min)
    elo_system = DummyEloSystem({"Lakers_Warriors": 0.53})
    elo_system.ratings = {"Lakers": 1600, "Warriors": 1500}

    comparator = OddsComparator(db_manager=db)

    opportunities = comparator.find_opportunities(
        config=BettingOpportunityConfig(
            sport="nba",
            elo_system=elo_system,
            thresholds=BettingThresholds(
                min_edge=0.05,
                max_edge=1.0,
            ),
        )
    )

    # Should find 0 opportunities (edge 3% below 5% min_edge)
    assert len(opportunities) == 0


def test_positive_ev_with_medium_edge():
    """Test that a medium positive edge bet is identified with correct confidence."""

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

    # Elo predicts Lakers win with 70% vs market's 60% = 10% edge
    elo_system = DummyEloSystem({"Lakers_Warriors": 0.70})
    elo_system.ratings = {"Lakers": 1600, "Warriors": 1500}

    comparator = OddsComparator(db_manager=db)

    opportunities = comparator.find_opportunities(
        config=BettingOpportunityConfig(
            sport="nba",
            elo_system=elo_system,
            thresholds=BettingThresholds(
                min_edge=0.05,
                max_edge=1.0,
            ),
        )
    )

    assert len(opportunities) == 1
    bet = opportunities[0]
    assert bet["sport"] == "nba"
    assert bet["bet_on"] == "Lakers"
    assert bet["side"] == "home"
    assert bet["elo_prob"] == 0.70
    assert abs(bet["edge"] - 0.10) < 0.01
    # Edge 10% is >= 8% but < 15% = MEDIUM confidence
    assert bet["confidence"] == "MEDIUM"


def test_max_edge_cap_rejects_extreme_edges():
    """Test that bets with edge above max_edge are rejected as likely data errors."""

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
        return pd.DataFrame(
            [
                {
                    "bookmaker": "Kalshi",
                    "outcome_name": "home",
                    "price": 10.0,  # 10% implied probability
                    "last_update": "2026-02-26",
                    "external_id": "KXNBAGAME-26FEB26-LALGSW-YESLAL",
                },
                {
                    "bookmaker": "Kalshi",
                    "outcome_name": "away",
                    "price": 1.11,  # 90% implied probability
                    "last_update": "2026-02-26",
                    "external_id": "KXNBAGAME-26FEB26-LALGSW-YESGSW",
                },
            ]
        )

    db = DummyDB(
        {"FROM unified_games": frame_for_games, "FROM game_odds": frame_for_odds}
    )

    # Elo predicts Lakers win with 70% vs market's 10% = 60% edge (suspiciously high)
    elo_system = DummyEloSystem({"Lakers_Warriors": 0.70})
    elo_system.ratings = {"Lakers": 1600, "Warriors": 1500}

    comparator = OddsComparator(db_manager=db)

    opportunities = comparator.find_opportunities(
        config=BettingOpportunityConfig(
            sport="nba",
            elo_system=elo_system,
            thresholds=BettingThresholds(
                min_edge=0.05,
                max_edge=0.40,  # Cap at 40%
            ),
        )
    )

    # Should reject - 60% edge exceeds 40% max_edge cap
    assert len(opportunities) == 0


if __name__ == "__main__":
    test_large_positive_edge_bet()
    test_small_edge_below_threshold_no_bet()
    test_positive_ev_with_medium_edge()
    test_max_edge_cap_rejects_extreme_edges()
    print("All tests passed!")
