"""Tests for OddsComparator core logic."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from pathlib import Path
import sys

import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

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
    """Test market agreement strategy: bet when Elo and market agree."""
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
    elo_system = SimpleNamespace(predict=lambda home, away: 0.65)

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="nba",
            elo_ratings={"Lakers": 1550, "Celtics": 1500},
            elo_system=elo_system,
            market_confidence_cutoff=0.55,
        )

    assert len(results) == 1
    assert results[0]["bookmaker"] == "Kalshi"
    assert results[0]["bet_on"] == "Lakers"  # Both agree home wins
    assert results[0]["side"] == "home"


def test_find_opportunities_epl_3way():
    """Test market agreement for soccer 3-way markets."""
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
        predict_3way=lambda home, away: {"home": 0.65, "draw": 0.20, "away": 0.15}
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="epl",
            elo_ratings={"Arsenal": 1600, "Chelsea": 1500},
            elo_system=elo_system,
            market_confidence_cutoff=0.55,
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
        sport="nba",
        elo_ratings={},
        elo_system=elo_system,
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
            sport="nba",
            elo_ratings={"Lakers": 1550, "Celtics": 1500},
            elo_system=elo_system,
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
    # Elo also predicts Arsenal (home) with 65%
    elo_system = SimpleNamespace(
        predict_3way=lambda home, away: {"home": 0.65, "draw": 0.20, "away": 0.15}
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="epl",
            elo_ratings={"Arsenal": 1600, "Chelsea": 1500},
            elo_system=elo_system,
            market_confidence_cutoff=0.55,
        )

    assert results


def test_find_opportunities_no_bet_when_disagreement():
    """Test that no bet is placed when Elo and market disagree on the winner."""
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
    # Elo predicts home wins with 70% - disagrees with market!
    elo_system = SimpleNamespace(predict=lambda home, away: 0.70)

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="nba",
            elo_ratings={"Lakers": 1550, "Celtics": 1500},
            elo_system=elo_system,
            market_confidence_cutoff=0.55,
        )

    # No bet because Elo says home (70%) but market says away (60%)
    assert results == []


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
    comparator = OddsComparator(db_manager=db)
    elo_system = MagicMock()
    # Elo also predicts home with 65%
    elo_system.predict.return_value = 0.65

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="tennis",
            elo_ratings={},
            elo_system=elo_system,
            market_confidence_cutoff=0.55,
        )

    elo_system.predict.assert_called()
    assert len(results) == 1
    assert results[0]["side"] == "home"


def test_find_opportunities_market_below_cutoff_no_bet():
    """Test that no bet is placed when market confidence is below cutoff (coin flip)."""
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
    # Market is close to 50/50 - below the 55% cutoff
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.92,  # ~52% implied - below 55% cutoff
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 2.08,  # ~48% implied
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo says home wins with 60%
    elo_system = SimpleNamespace(predict=lambda home, away: 0.60)

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="nba",
            elo_ratings={"Lakers": 1550, "Celtics": 1500},
            elo_system=elo_system,
            market_confidence_cutoff=0.55,
        )

    # No bet because market prob (52%) is below cutoff (55%)
    assert results == []


def test_find_opportunities_confidence_levels():
    """Test that confidence is assigned based on agreement strength."""
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
    # Market says home wins with 62%
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.61,  # ~62% implied
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 2.63,  # ~38% implied
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    # Elo predicts home with 65% - very close to market's 62%
    elo_system = SimpleNamespace(predict=lambda home, away: 0.65)

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="nba",
            elo_ratings={"Lakers": 1550, "Celtics": 1500},
            elo_system=elo_system,
            market_confidence_cutoff=0.55,
        )

    assert len(results) == 1
    # Agreement diff is ~3% (0.65 - 0.62), should be HIGH confidence
    assert results[0]["confidence"] == "HIGH"
    assert "agreement_diff" in results[0]


def test_find_opportunities_away_team_agreement():
    """Test betting on away team when both Elo and market agree away wins."""
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
    # Elo also predicts away wins (home win prob = 30%, so away = 70%)
    elo_system = SimpleNamespace(predict=lambda home, away: 0.30)

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="nba",
            elo_ratings={"Lakers": 1450, "Celtics": 1600},
            elo_system=elo_system,
            market_confidence_cutoff=0.55,
        )

    assert len(results) == 1
    assert results[0]["side"] == "away"
    assert results[0]["bet_on"] == "Celtics"
