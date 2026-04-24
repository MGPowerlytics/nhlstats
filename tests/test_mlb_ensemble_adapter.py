"""Tests for :class:`MLBEnsembleAdapter`.

Covers:
* Drop-in compatibility with the standard Elo interface used by
  ``OddsComparator`` (``ratings`` dict, ``predict(home, away)``).
* Population from a fake DB returning canned ``mlb_games``/``unified_games``
  rows.
* Graceful degradation when the side-information caches are empty.
* Pythagorean / rest signal actually moves the prediction relative to a
  bare Elo baseline.
"""

from datetime import date

import pandas as pd
import pytest

from plugins.elo.mlb_ensemble_adapter import (
    MLBEnsembleAdapter,
    _TeamSeasonStats,
    _rest_days,
)


class _FakeDB:
    """Minimal stand-in for :class:`DBManager` used by the adapter."""

    def __init__(self, games_df: pd.DataFrame, venues_df: pd.DataFrame):
        self._games = games_df
        self._venues = venues_df
        self.calls = []

    def fetch_df(self, query: str, params=None):
        self.calls.append((query, params))
        if "FROM mlb_games" in query:
            return self._games.copy()
        if "FROM unified_games" in query:
            return self._venues.copy()
        return pd.DataFrame()


def _make_games_df(rows):
    return pd.DataFrame(
        rows,
        columns=["game_date", "home_team", "away_team", "home_score", "away_score"],
    )


def _make_venues_df(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "home_team",
            "away_team",
            "venue",
            "home_pitcher_id",
            "away_pitcher_id",
        ],
    )


def test_ratings_property_is_drop_in_for_elo_system():
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Yankees": 1550.0, "Red Sox": 1480.0}
    assert adapter.ratings["Yankees"] == 1550.0
    # Underlying ensemble's team_elo must be backing the dict
    assert adapter.ensemble.team_elo.get_rating("Yankees") == 1550.0


def test_get_rating_is_available_for_odds_comparator():
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Yankees": 1550.0, "Red Sox": 1480.0}

    assert adapter.get_rating("Yankees") == 1550.0
    assert adapter.get_all_ratings()["Red Sox"] == 1480.0


def test_predict_with_no_context_uses_pure_team_elo():
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Yankees": 1600.0, "Red Sox": 1500.0}
    p = adapter.predict("Yankees", "Red Sox")
    # With +20 home advantage and a 100-pt Elo gap, home should be heavily favored
    assert 0.6 < p < 0.75


def test_populate_from_db_aggregates_runs_and_last_game():
    games = _make_games_df(
        [
            (date(2026, 4, 1), "Yankees", "Red Sox", 5, 2),
            (date(2026, 4, 2), "Yankees", "Red Sox", 3, 4),
            (date(2026, 4, 3), "Red Sox", "Yankees", 7, 6),
        ]
    )
    venues = _make_venues_df([("Yankees", "Red Sox", "Yankee Stadium", None, None)])
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Yankees": 1500.0, "Red Sox": 1500.0}
    adapter.populate_from_db(_FakeDB(games, venues), reference_date=date(2026, 4, 5))

    yankees = adapter.team_stats["Yankees"]
    assert yankees.runs_scored == 14.0  # 5 + 3 + 6
    assert yankees.runs_allowed == 13.0  # 2 + 4 + 7
    assert yankees.last_game_date == date(2026, 4, 3)
    assert adapter.venues[("Yankees", "Red Sox")] == "Yankee Stadium"


def test_predict_uses_pythagorean_signal_when_available():
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Yankees": 1500.0, "Red Sox": 1500.0}
    baseline = adapter.predict("Yankees", "Red Sox")

    # Yankees: dominant run differential (300 RS, 100 RA)
    # Red Sox: bad differential (100 RS, 300 RA)
    adapter.team_stats = {
        "Yankees": _TeamSeasonStats(
            runs_scored=300, runs_allowed=100, last_game_date=date(2026, 4, 4)
        ),
        "Red Sox": _TeamSeasonStats(
            runs_scored=100, runs_allowed=300, last_game_date=date(2026, 4, 4)
        ),
    }
    adapter.reference_date = date(2026, 4, 5)
    boosted = adapter.predict("Yankees", "Red Sox")
    assert boosted > baseline + 0.02, (
        f"Pythagorean signal should lift home prob; baseline={baseline:.3f} "
        f"boosted={boosted:.3f}"
    )


def test_predict_uses_park_factor_when_venue_known():
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Rockies": 1520.0, "Padres": 1500.0}
    # Without venue, prediction is plain Elo + HA
    no_venue = adapter.predict("Rockies", "Padres")

    adapter.venues[("Rockies", "Padres")] = "Coors Field"
    with_venue = adapter.predict("Rockies", "Padres")
    # Coors Field amplifies offensive disparity (home has higher rating)
    assert with_venue >= no_venue


def test_rest_days_helper_clips_and_handles_none():
    assert _rest_days(None, date(2026, 4, 5)) == 2  # neutral default
    assert _rest_days(date(2026, 4, 4), date(2026, 4, 5)) == 0  # back-to-back
    assert _rest_days(date(2026, 4, 1), date(2026, 4, 5)) == 3  # three days off
    assert _rest_days(date(2026, 1, 1), date(2026, 4, 5)) == 7  # capped at 7


def test_populate_from_db_empty_results_does_not_crash():
    empty_games = _make_games_df([])
    empty_venues = _make_venues_df([])
    adapter = MLBEnsembleAdapter()
    adapter.populate_from_db(
        _FakeDB(empty_games, empty_venues), reference_date=date(2026, 4, 5)
    )
    assert adapter.team_stats == {}
    assert adapter.venues == {}
    # Predict still works (degrades to plain Elo)
    adapter.ratings = {"A": 1500.0, "B": 1500.0}
    p = adapter.predict("A", "B")
    assert 0.5 < p < 0.6  # only home advantage in play


def test_unknown_team_falls_back_to_default_rating():
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Yankees": 1500.0}
    # Unknown opponent — should not raise
    p = adapter.predict("Yankees", "Phantom Team")
    assert 0.0 < p < 1.0


def test_populate_from_db_populates_recent_form_tracker():
    """``populate_from_db`` must seed ``ensemble.form`` chronologically.

    Previously only ``team_stats`` was populated, leaving the form tracker
    empty so it contributed 0 to every prediction. This test guards that
    regression: after replaying three games where the Yankees go 2-1 and
    the Red Sox go 1-2, the rolling win pcts should reflect those records.
    """
    games = _make_games_df(
        [
            (date(2026, 4, 1), "Yankees", "Red Sox", 5, 2),  # NYY win
            (date(2026, 4, 2), "Yankees", "Red Sox", 3, 4),  # BOS win
            (date(2026, 4, 3), "Red Sox", "Yankees", 6, 7),  # NYY win
        ]
    )
    venues = _make_venues_df([])
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Yankees": 1500.0, "Red Sox": 1500.0}
    adapter.populate_from_db(_FakeDB(games, venues), reference_date=date(2026, 4, 5))

    form = adapter.ensemble.form
    assert form.win_pct("Yankees") == pytest.approx(2 / 3)
    assert form.win_pct("Red Sox") == pytest.approx(1 / 3)


def test_populate_from_db_filters_out_spring_training():
    """Adapter's mlb_games query must restrict to regular/postseason game_types.

    Spring training (S), exhibition (E), and All-Star (A) games inflate
    pythagorean stats and pollute the form tracker. The main MLB Elo training
    query already filters via ``_get_mlb_query``; the adapter must do the same
    so the ensemble's side information stays consistent with the team Elo
    backbone.
    """
    games = _make_games_df([])
    venues = _make_venues_df([])
    db = _FakeDB(games, venues)
    adapter = MLBEnsembleAdapter()
    adapter.populate_from_db(db, reference_date=date(2026, 4, 5))

    mlb_calls = [q for q, _ in db.calls if "FROM mlb_games" in q]
    assert mlb_calls, "Adapter must query mlb_games"
    query = mlb_calls[0]
    assert "game_type IN" in query, (
        "Adapter mlb_games query must filter game_type to exclude spring "
        "training / exhibitions / All-Star games"
    )
    for code in ("'R'", "'D'", "'L'", "'W'", "'F'"):
        assert code in query, f"Allowed game_type {code} missing from filter"


def test_populate_from_db_form_is_idempotent():
    """Re-populating must not double-count results into the form tracker."""
    games = _make_games_df(
        [
            (date(2026, 4, 1), "Yankees", "Red Sox", 5, 2),
            (date(2026, 4, 2), "Yankees", "Red Sox", 6, 1),
        ]
    )
    venues = _make_venues_df([])
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Yankees": 1500.0, "Red Sox": 1500.0}
    db = _FakeDB(games, venues)
    adapter.populate_from_db(db, reference_date=date(2026, 4, 5))
    adapter.populate_from_db(db, reference_date=date(2026, 4, 5))

    form = adapter.ensemble.form
    # Yankees should still be 2-0 (not 4-0)
    assert form.win_pct("Yankees") == pytest.approx(1.0)
    assert len(form._records["Yankees"]) == 2
    assert len(form._records["Red Sox"]) == 2


def test_adapter_has_real_rating_present():
    """MLBEnsembleAdapter.has_real_rating returns True for loaded teams."""
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Los Angeles Dodgers": 1550.0, "New York Yankees": 1600.0}
    assert adapter.has_real_rating("Los Angeles Dodgers") is True
    assert adapter.has_real_rating("New York Yankees") is True


def test_adapter_has_real_rating_absent():
    """MLBEnsembleAdapter.has_real_rating returns False for unknown teams."""
    adapter = MLBEnsembleAdapter()
    adapter.ratings = {"Los Angeles Dodgers": 1550.0}
    assert adapter.has_real_rating("Fake Team") is False
    assert adapter.has_real_rating("") is False


def test_adapter_has_real_rating_empty_store():
    """has_real_rating returns False when no ratings have been loaded."""
    adapter = MLBEnsembleAdapter()
    assert adapter.has_real_rating("Los Angeles Dodgers") is False
