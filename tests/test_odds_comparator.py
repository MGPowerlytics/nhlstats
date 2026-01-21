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
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.9,
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 2.1,
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

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
            threshold=0.65,
            min_edge=0.05,
            use_sharp_confirmation=False,
        )

    assert len(results) == 1
    assert results[0]["bookmaker"] == "Kalshi"
    assert results[0]["bet_on"] in ["Lakers", "Celtics"]


def test_find_opportunities_epl_3way():
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
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.8,
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "draw",
                "price": 3.4,
                "last_update": "now",
                "external_id": "kalshi-draw",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 4.2,
                "last_update": "now",
                "external_id": "kalshi-away",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    elo_system = SimpleNamespace(
        predict_3way=lambda home, away: {"home": 0.7, "draw": 0.2, "away": 0.1}
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="epl",
            elo_ratings={"Arsenal": 1600, "Chelsea": 1500},
            elo_system=elo_system,
            threshold=0.55,
            min_edge=0.05,
            use_sharp_confirmation=False,
        )

    assert results
    assert all("market_odds" in bet for bet in results)


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
        threshold=0.65,
        min_edge=0.05,
    )

    assert results == []


def test_get_best_odds_handles_exception():
    class ErrorDB:
        def fetch_df(self, query, params=None):
            raise RuntimeError("db error")

    comparator = OddsComparator(db_manager=ErrorDB())

    assert comparator.get_best_odds("game-1") == {}


def test_find_opportunities_skips_when_no_odds():
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
            threshold=0.65,
            min_edge=0.05,
            use_sharp_confirmation=False,
        )

    assert results == []


def test_find_opportunities_named_outcomes_resolve():
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
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "Arsenal",
                "price": 1.8,
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "Chelsea",
                "price": 4.2,
                "last_update": "now",
                "external_id": "kalshi-away",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "Draw",
                "price": 3.4,
                "last_update": "now",
                "external_id": "kalshi-draw",
            },
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    elo_system = SimpleNamespace(
        predict_3way=lambda home, away: {"home": 0.7, "draw": 0.2, "away": 0.1}
    )

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="epl",
            elo_ratings={"Arsenal": 1600, "Chelsea": 1500},
            elo_system=elo_system,
            threshold=0.55,
            min_edge=0.05,
            use_sharp_confirmation=False,
        )

    assert results


def test_find_opportunities_sharp_confirmation_blocks():
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
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.9,
                "last_update": "now",
                "external_id": "kalshi-home",
            },
            {
                "bookmaker": "pinnacle",
                "outcome_name": "home",
                "price": 1.95,
                "last_update": "now",
                "external_id": "sharp-home",
            },
        ]
    )

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
            threshold=0.65,
            min_edge=0.05,
            use_sharp_confirmation=True,
        )

    assert results == []


def test_find_opportunities_tennis_tour_selection():
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
    odds_df = pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 1.9,
                "last_update": "now",
                "external_id": "kalshi-home",
            }
        ]
    )

    def frame_for_query(params=None):
        return odds_df

    db = DummyDB({"FROM unified_games": games_df, "FROM game_odds": frame_for_query})
    comparator = OddsComparator(db_manager=db)
    elo_system = MagicMock()
    elo_system.predict.return_value = 0.8

    with patch("plugins.odds_comparator.NamingResolver.resolve", return_value=None):
        results = comparator.find_opportunities(
            sport="tennis",
            elo_ratings={},
            elo_system=elo_system,
            threshold=0.65,
            min_edge=0.05,
            use_sharp_confirmation=False,
        )

    elo_system.predict.assert_called()
    assert results
