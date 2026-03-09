"""Test that negative edge bets are rejected."""

from datetime import datetime
from types import SimpleNamespace
from pathlib import Path
import sys

import pandas as pd
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

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


def test_no_bet_when_negative_edge():
    """Test that no bet is placed when edge is negative (market probability > Elo probability)."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "kalshi-negative-edge",
                "game_date": today,
                "home_team_name": "Lakers",
                "away_team_name": "Celtics",
                "status": "Scheduled",
            }
        ]
    )
    # Market says home wins with 84% probability (higher than Elo's 83.9%)
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.1904761904761905,  # ~84% implied probability
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 5.0,  # ~20% implied probability
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo predicts home wins with 83.9% (slightly lower than market)
    elo_system = SimpleNamespace(
        predict=lambda home, away: 0.839,
        get_rating=lambda team: 1550 if team == "Lakers" else 1500,
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        thresholds = BettingThresholds(
            threshold=0.65,
            min_edge=0.05,
            max_edge=1.0,
            market_confidence_cutoff=0.55,
            enable_high_edge_disagreement=True,
            high_edge_threshold=0.10,
        )

        config = BettingOpportunityConfig(
            sport="nba",
            elo_system=elo_system,
            thresholds=thresholds,
        )

        results = comparator.find_opportunities(config)

    # Should NOT bet because edge is negative (0.839 - 0.84 = -0.001)
    assert len(results) == 0, f"Expected no bets with negative edge, got {len(results)}"


def test_bet_when_small_positive_edge():
    """Test that bet IS placed when edge is small but positive."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "kalshi-positive-edge",
                "game_date": today,
                "home_team_name": "Lakers",
                "away_team_name": "Celtics",
                "status": "Scheduled",
            }
        ]
    )
    # Market says home wins with 70% probability (lower than Elo's 81.1%)
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.4285714285714286,  # ~70% implied probability
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 3.3333333333333335,  # ~30% implied probability
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo predicts home wins with 81.1% (higher than market)
    elo_system = SimpleNamespace(
        predict=lambda home, away: 0.811,
        get_rating=lambda team: 1550 if team == "Lakers" else 1500,
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        thresholds = BettingThresholds(
            threshold=0.65,
            min_edge=0.05,
            max_edge=1.0,
            market_confidence_cutoff=0.55,
            enable_high_edge_disagreement=True,
            high_edge_threshold=0.10,
        )

        config = BettingOpportunityConfig(
            sport="nba",
            elo_system=elo_system,
            thresholds=thresholds,
        )

        results = comparator.find_opportunities(config)

    # SHOULD bet because edge is > 5% (0.811 - 0.70 = 0.111 > 0.05)
    assert len(results) == 1, f"Expected 1 bet with edge > 5%, got {len(results)}"
    assert results[0]["edge"] > 0.05
    assert results[0]["expected_value"] > 0


def test_high_edge_disagreement_still_works_with_positive_edge():
    """Test that large positive edge bets are identified as HIGH confidence."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "kalshi-high-edge",
                "game_date": today,
                "home_team_name": "Lakers",
                "away_team_name": "Celtics",
                "status": "Scheduled",
            }
        ]
    )
    # Market says home wins with only 43% probability (much lower than Elo's 80%)
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 2.3255813953488373,  # ~43% implied probability
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 1.7,  # ~59% implied probability
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo predicts home wins with 80% (much higher than market)
    elo_system = SimpleNamespace(
        predict=lambda home, away: 0.80,
        get_rating=lambda team: 1550 if team == "Lakers" else 1500,
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        thresholds = BettingThresholds(
            threshold=0.65,
            min_edge=0.05,
            max_edge=1.0,
            market_confidence_cutoff=0.55,
            enable_high_edge_disagreement=True,
            high_edge_threshold=0.10,
        )

        config = BettingOpportunityConfig(
            sport="nba",
            elo_system=elo_system,
            thresholds=thresholds,
        )

        results = comparator.find_opportunities(config)

    # SHOULD bet because edge = 0.80 - 0.43 = 0.37 > 0.05 min_edge
    assert len(results) == 1, (
        f"Expected 1 bet with high positive edge, got {len(results)}"
    )
    assert results[0]["edge"] > 0.12
    # In positive EV, edge > 15% = HIGH confidence
    assert results[0]["confidence"] == "HIGH"


if __name__ == "__main__":
    test_no_bet_when_negative_edge()
    print("✓ test_no_bet_when_negative_edge passed")

    test_bet_when_small_positive_edge()
    print("✓ test_bet_when_small_positive_edge passed")

    test_high_edge_disagreement_still_works_with_positive_edge()
    print("✓ test_high_edge_disagreement_still_works_with_positive_edge passed")

    print("\nAll tests passed!")
