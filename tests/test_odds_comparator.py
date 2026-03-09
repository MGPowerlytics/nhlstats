"""Tests for OddsComparator core logic."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from pathlib import Path
import sys

import pandas as pd
from unittest.mock import patch, MagicMock

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


def test_get_best_odds_returns_expected_dict():
    def frame_for_side(params):
        side = params.get("side")
        if side == "home":
            return pd.DataFrame(
                [{"bookmaker": "Kalshi", "price": 2.0, "last_update": "now"}]
            )
        if side == "away":
            return pd.DataFrame(
                [{"bookmaker": "Kalshi", "price": 1.8, "last_update": "now"}]
            )
        return pd.DataFrame()

    db = DummyDB({"FROM game_odds": frame_for_side})
    comparator = OddsComparator(db_manager=db)

    best = comparator.get_best_odds("game-1")

    assert best["home"]["decimal_odds"] == 2.0
    assert best["away"]["decimal_odds"] == 1.8
    assert "draw" not in best


def test_get_all_odds_returns_records():
    df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.9,
                "last_update": "now",
                "external_id": "ticker-1",
            }
        ]
    )
    db = DummyDB({"FROM game_odds": df})
    comparator = OddsComparator(db_manager=db)

    records = comparator.get_all_odds("game-1")

    assert records[0]["bookmaker"] == "Kalshi"
    assert records[0]["external_id"] == "ticker-1"


def test_find_opportunities_basic_flow():
    """Test positive EV strategy: bet when Elo probability exceeds market probability."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "kalshi-1",
                "game_date": today,
                "home_team_name": "Lakers",
                "away_team_name": "Celtics",
                "status": "Scheduled",
            }
        ]
    )
    # Market says home wins with 60% probability (1/1.67 ≈ 0.60)
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.67,  # ~60% implied probability
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 2.5,  # ~40% implied probability
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo also predicts home wins with 65%
    elo_system = SimpleNamespace(
        predict=lambda home, away: 0.65,
        get_rating=lambda team: 1550 if team == "Lakers" else 1500,
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            config=BettingOpportunityConfig(
                sport="nba",
                elo_system=elo_system,
                thresholds=BettingThresholds(
                    threshold=0.60,
                    min_edge=0.05,
                    max_edge=1.0,
                    market_confidence_cutoff=0.55,
                    enable_high_edge_disagreement=False,
                    high_edge_threshold=0.10,
                ),
            )
        )

    assert len(results) == 1
    assert results[0]["bookmaker"] == "Kalshi"
    assert results[0]["bet_on"] == "Lakers"  # Both agree home wins
    assert results[0]["side"] == "home"


def test_find_opportunities_epl_3way():
    """Test positive EV for soccer 3-way markets."""
    today = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "epl-1",
                "game_date": today,
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "status": "Scheduled",
            }
        ]
    )
    # Market says home wins with 60% (1/1.67), draw 25%, away 15%
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.67,  # ~60% implied
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "draw",
                "price": 4.0,  # ~25% implied
                "last_update": "now",
                "external_id": "kalshi-draw",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 6.67,  # ~15% implied
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo also predicts home with 65%
    elo_system = SimpleNamespace(
        predict_3way=lambda home, away: {"home": 0.65, "draw": 0.20, "away": 0.15},
        get_rating=lambda team: 1600 if team == "Arsenal" else 1500,
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            config=BettingOpportunityConfig(
                sport="epl",
                elo_system=elo_system,
                thresholds=BettingThresholds(
                    threshold=0.45,
                    min_edge=0.05,
                    max_edge=1.0,
                    market_confidence_cutoff=0.55,
                    enable_high_edge_disagreement=False,
                    high_edge_threshold=0.10,
                ),
            )
        )

    assert len(results) == 1
    assert results[0]["side"] == "home"
    assert results[0]["bet_on"] == "Arsenal"


def test_find_opportunities_handles_db_error():
    class ErrorDB:
        def fetch_df(self, query, params=None):
            raise RuntimeError("db error")

    comparator = OddsComparator(db_manager=ErrorDB())
    elo_system = SimpleNamespace(predict=lambda home, away: 0.8)

    results = comparator.find_opportunities(
        config=BettingOpportunityConfig(
            sport="nba",
            elo_system=elo_system,
            thresholds=BettingThresholds(
                threshold=0.65,
                min_edge=0.05,
                max_edge=1.0,
                market_confidence_cutoff=0.55,
                enable_high_edge_disagreement=False,
                high_edge_threshold=0.10,
            ),
        )
    )

    assert results == []


def test_get_best_odds_handles_exception():
    class ErrorDB:
        def fetch_df(self, query, params=None):
            raise RuntimeError("db error")

    comparator = OddsComparator(db_manager=ErrorDB())

    assert comparator.get_best_odds("game-1") == {}


def test_find_opportunities_skips_when_no_odds():
    """Test that no opportunities are returned when no odds available."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "kalshi-2",
                "game_date": today,
                "home_team_name": "Lakers",
                "away_team_name": "Celtics",
                "status": "Scheduled",
            }
        ]
    )
    odds_df = pd.DataFrame([])

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    elo_system = SimpleNamespace(predict=lambda home, away: 0.8)

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            config=BettingOpportunityConfig(
                sport="nba",
                elo_system=elo_system,
                thresholds=BettingThresholds(
                    threshold=0.65,
                    min_edge=0.05,
                    max_edge=1.0,
                    market_confidence_cutoff=0.55,
                    enable_high_edge_disagreement=False,
                    high_edge_threshold=0.10,
                ),
            )
        )

    assert results == []


def test_find_opportunities_named_outcomes_resolve():
    """Test that team name outcomes get resolved to home/away correctly."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "epl-2",
                "game_date": today,
                "home_team_name": "Arsenal",
                "away_team_name": "Chelsea",
                "status": "Scheduled",
            }
        ]
    )
    # Odds use team names instead of home/away
    # Market says Arsenal wins with 60%
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "Arsenal",
                "price": 1.67,  # ~60% implied
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "Chelsea",
                "price": 6.67,  # ~15% implied
                "last_update": "now",
                "external_id": "kalshi-away",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "Draw",
                "price": 4.0,  # ~25% implied
                "last_update": "now",
                "external_id": "kalshi-draw",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo also predicts Arsenal (home) with 65%
    elo_system = SimpleNamespace(
        predict_3way=lambda home, away: {"home": 0.65, "draw": 0.20, "away": 0.15},
        get_rating=lambda team: 1600 if team == "Arsenal" else 1500,
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            config=BettingOpportunityConfig(
                sport="epl",
                elo_system=elo_system,
                thresholds=BettingThresholds(
                    threshold=0.45,
                    min_edge=0.05,
                    max_edge=1.0,
                    market_confidence_cutoff=0.55,
                    enable_high_edge_disagreement=False,
                    high_edge_threshold=0.10,
                ),
            )
        )

    assert results


def test_find_opportunities_no_bet_when_disagreement():
    """Test that a bet IS placed when Elo has positive edge over market (positive EV)."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "kalshi-3",
                "game_date": today,
                "home_team_name": "Lakers",
                "away_team_name": "Celtics",
                "status": "Scheduled",
            }
        ]
    )
    # Market says away wins with 60% probability
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 2.5,  # ~40% implied (away favored)
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 1.67,  # ~60% implied
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo predicts home wins with 70% - positive edge of 30% against market's 40%
    elo_system = SimpleNamespace(
        predict=lambda home, away: 0.70,
        get_rating=lambda team: 1550 if team == "Lakers" else 1500,
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            config=BettingOpportunityConfig(
                sport="nba",
                elo_system=elo_system,
                thresholds=BettingThresholds(
                    threshold=0.65,
                    min_edge=0.05,
                    max_edge=1.0,
                    market_confidence_cutoff=0.55,
                    enable_high_edge_disagreement=False,
                    high_edge_threshold=0.10,
                ),
            )
        )

    # In positive EV: Elo says home 70%, market implies home 40% → edge = 30% → BET
    assert len(results) == 1
    assert results[0]["side"] == "home"
    assert results[0]["bet_on"] == "Lakers"
    assert results[0]["edge"] > 0.05


def test_find_opportunities_tennis_tour_selection():
    """Test that tennis matches correctly use ATP/WTA tour selection."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "KXATPMATCH-20260121-TEST",
                "game_date": today,
                "home_team_name": "Player A",
                "away_team_name": "Player B",
                "status": "Scheduled",
            }
        ]
    )
    # Market says home wins with 60%
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.67,  # ~60% implied
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 2.5,  # ~40% implied
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    elo_system = MagicMock()
    # Elo also predicts home with 65%
    elo_system.predict.return_value = 0.65
    elo_system.get_rating = MagicMock(return_value=1500)

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            config=BettingOpportunityConfig(
                sport="tennis",
                elo_system=elo_system,
                thresholds=BettingThresholds(
                    threshold=0.60,
                    min_edge=0.05,
                    max_edge=1.0,
                    market_confidence_cutoff=0.55,
                    enable_high_edge_disagreement=False,
                    high_edge_threshold=0.10,
                ),
            )
        )

    elo_system.predict.assert_called()
    assert len(results) == 1
    assert results[0]["side"] == "home"


def test_find_opportunities_market_below_cutoff_no_bet():
    """Test that no bet when edge is below min_edge threshold."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "kalshi-4",
                "game_date": today,
                "home_team_name": "Lakers",
                "away_team_name": "Celtics",
                "status": "Scheduled",
            }
        ]
    )
    # Market is close to Elo - edge below min_edge threshold
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.72,  # ~58% implied
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 2.38,  # ~42% implied
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo says home wins with 60% - edge is only ~2% (below 5% min_edge)
    elo_system = SimpleNamespace(
        predict=lambda home, away: 0.60,
        get_rating=lambda team: 1520 if team == "Lakers" else 1500,
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            config=BettingOpportunityConfig(
                sport="nba",
                elo_system=elo_system,
                thresholds=BettingThresholds(
                    threshold=0.65,
                    min_edge=0.05,
                    max_edge=1.0,
                    market_confidence_cutoff=0.55,
                    enable_high_edge_disagreement=False,
                    high_edge_threshold=0.10,
                ),
            )
        )

    # No bet because edge (~2%) is below min_edge (5%)
    assert results == []


def test_find_opportunities_confidence_levels():
    """Test that confidence is assigned based on edge size (positive EV)."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "kalshi-5",
                "game_date": today,
                "home_team_name": "Lakers",
                "away_team_name": "Celtics",
                "status": "Scheduled",
            }
        ]
    )
    # Market says home wins with 60%
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.67,  # ~60% implied
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 2.50,  # ~40% implied
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo predicts home with 65% - edge ~5% over market's 60%
    elo_system = SimpleNamespace(
        predict=lambda home, away: 0.65,
        get_rating=lambda team: 1550 if team == "Lakers" else 1500,
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            config=BettingOpportunityConfig(
                sport="nba",
                elo_system=elo_system,
                thresholds=BettingThresholds(
                    threshold=0.60,
                    min_edge=0.03,
                    max_edge=1.0,
                    market_confidence_cutoff=0.55,
                    enable_high_edge_disagreement=False,
                    high_edge_threshold=0.10,
                ),
            )
        )

    assert len(results) == 1
    # Edge is ~5% (0.65 - 0.60), which is < 8% → LOW confidence
    assert results[0]["confidence"] == "LOW"


def test_find_opportunities_away_team_agreement():
    """Test betting on away team when Elo finds positive EV on away side."""
    today = datetime.now().strftime("%Y-%m-%d")
    games_df = pd.DataFrame(
        [
            {
                "game_id": "kalshi-6",
                "game_date": today,
                "home_team_name": "Lakers",
                "away_team_name": "Celtics",
                "status": "Scheduled",
            }
        ]
    )
    # Market says away (Celtics) wins with 65%
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 2.86,  # ~35% implied
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 1.54,  # ~65% implied
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo also predicts away wins (home win prob = 30%, away = 70%)
    # Away edge: 70% - 65% = 5% positive edge on away
    elo_system = SimpleNamespace(
        predict=lambda home, away: 0.30,
        get_rating=lambda team: 1450 if team == "Lakers" else 1600,
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            config=BettingOpportunityConfig(
                sport="nba",
                elo_system=elo_system,
                thresholds=BettingThresholds(
                    threshold=0.60,
                    min_edge=0.05,
                    max_edge=1.0,
                    market_confidence_cutoff=0.55,
                    enable_high_edge_disagreement=False,
                    high_edge_threshold=0.10,
                ),
            )
        )

    assert len(results) == 1
    assert results[0]["side"] == "away"
    assert results[0]["bet_on"] == "Celtics"
