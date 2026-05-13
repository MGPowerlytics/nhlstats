"""Focused regression tests for the EPL ensemble model and adapter."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from plugins.elo.epl_ensemble import EPLEnsembleModel
from plugins.elo.epl_ensemble_adapter import EPLEnsembleAdapter


class _IdentityScaler:
    """Simple stand-in that returns input values unchanged."""

    def transform(self, frame):
        return frame.values


class _FixedClassifier:
    """Predicts one fixed away/draw/home probability vector."""

    classes_ = np.array([0, 1, 2])

    def __init__(self, probabilities):
        self._probabilities = np.array([probabilities], dtype=float)

    def predict_proba(self, _values):
        return self._probabilities


class _FakeDB:
    """Minimal stand-in for DBManager used by the adapter."""

    def __init__(self, games_df: pd.DataFrame, odds_df: pd.DataFrame):
        self._games = games_df
        self._odds = odds_df

    def fetch_df(self, query: str, params=None):
        if "FROM epl_games" in query:
            return self._games.copy()
        if "FROM unified_games" in query:
            return self._odds.copy()
        raise AssertionError(f"Unexpected query: {query}")


def _make_games_df(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "game_date",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "result",
        ],
    )


def _make_odds_df(rows):
    return pd.DataFrame(
        rows,
        columns=["home_team_name", "away_team_name", "outcome_name", "price"],
    )


def test_ensemble_model_blends_classifier_and_bookmaker_probabilities():
    model = EPLEnsembleModel(auto_train=False)
    model.model = _FixedClassifier([0.20, 0.30, 0.50])
    model.scaler = _IdentityScaler()
    model.is_trained = True
    model.classes_ = [0, 1, 2]

    probabilities = model.predict_probs(
        {
            "elo_prob_home": 0.55,
            "elo_prob_draw": 0.20,
            "elo_prob_away": 0.25,
            "elo_diff": 50.0,
            "home_form": 0.8,
            "away_form": 0.2,
            "home_avg_gf": 1.8,
            "away_avg_gf": 1.1,
            "home_avg_ga": 0.9,
            "away_avg_ga": 1.5,
            "bookmaker_prob_home": 0.40,
            "bookmaker_prob_draw": 0.25,
            "bookmaker_prob_away": 0.35,
        }
    )

    assert probabilities["home"] == pytest.approx(0.47)
    assert probabilities["draw"] == pytest.approx(0.285)
    assert probabilities["away"] == pytest.approx(0.245)
    assert sum(probabilities.values()) == pytest.approx(1.0)


def test_adapter_ratings_and_has_real_rating_delegate_to_underlying_elo():
    adapter = EPLEnsembleAdapter(
        auto_train=False, ensemble=EPLEnsembleModel(auto_train=False)
    )
    adapter.ratings = {"Arsenal": 1540.0, "Liverpool": 1510.0}

    assert adapter.get_rating("Arsenal") == pytest.approx(1540.0)
    assert adapter.get_all_ratings()["Liverpool"] == pytest.approx(1510.0)
    assert adapter.has_real_rating("Arsenal") is True
    assert adapter.has_real_rating("Ghost FC") is False


def test_populate_from_db_aggregates_team_stats_and_bookmaker_probs():
    games = _make_games_df(
        [
            (date(2026, 1, 10), "Arsenal", "Liverpool", 2, 1, "H"),
            (date(2026, 1, 17), "Liverpool", "Arsenal", 1, 1, "D"),
            (date(2026, 1, 24), "Chelsea", "Arsenal", 0, 3, "A"),
        ]
    )
    odds = _make_odds_df(
        [
            ("Arsenal", "Liverpool", "Home", 2.0),
            ("Arsenal", "Liverpool", "Draw", 3.5),
            ("Arsenal", "Liverpool", "Away", 3.8),
        ]
    )
    adapter = EPLEnsembleAdapter(
        auto_train=False, ensemble=EPLEnsembleModel(auto_train=False)
    )

    adapter.populate_from_db(_FakeDB(games, odds), reference_date=date(2026, 1, 30))

    arsenal = adapter.team_stats["Arsenal"]
    assert arsenal.games_played == 3
    assert arsenal.goals_for == pytest.approx(6.0)
    assert arsenal.goals_against == pytest.approx(2.0)
    assert arsenal.recent_results == [1.0, 0.5, 1.0]

    probs = adapter.bookmaker_probs[("Arsenal", "Liverpool")]
    assert probs["home"] > probs["away"]
    assert sum(probs.values()) == pytest.approx(1.0)


def test_predict_3way_uses_ensemble_output():
    model = EPLEnsembleModel(auto_train=False)
    model.model = _FixedClassifier([0.25, 0.25, 0.50])
    model.scaler = _IdentityScaler()
    model.is_trained = True
    model.classes_ = [0, 1, 2]
    adapter = EPLEnsembleAdapter(auto_train=False, ensemble=model)
    adapter.ratings = {"Arsenal": 1540.0, "Liverpool": 1510.0}
    adapter.team_stats["Arsenal"] = type(
        "Stats",
        (),
        {
            "games_played": 5,
            "goals_for": 9.0,
            "goals_against": 4.0,
            "recent_results": [1.0, 1.0, 0.5, 1.0, 0.0],
        },
    )()
    adapter.team_stats["Liverpool"] = type(
        "Stats",
        (),
        {
            "games_played": 5,
            "goals_for": 7.0,
            "goals_against": 6.0,
            "recent_results": [0.0, 0.5, 1.0, 0.0, 1.0],
        },
    )()
    adapter.bookmaker_probs[("Arsenal", "Liverpool")] = {
        "home": 0.42,
        "draw": 0.27,
        "away": 0.31,
    }

    probabilities = adapter.predict_3way("Arsenal", "Liverpool")

    assert probabilities["home"] > probabilities["away"]
    assert sum(probabilities.values()) == pytest.approx(1.0)
