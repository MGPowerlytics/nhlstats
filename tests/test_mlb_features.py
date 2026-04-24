"""Unit tests for plugins.elo.mlb_features."""

from __future__ import annotations

from datetime import date

import pytest

from plugins.elo.mlb_features import (
    MAX_FEATURE_ELO,
    PARK_FACTORS,
    bayesian_shrink,
    bullpen_elo_adjustment,
    park_factor_elo_adjustment,
    pythagorean_elo_adjustment,
    pythagorean_win_pct,
    RecentFormTracker,
    rest_elo_adjustment,
    RestTracker,
)


# ---------------------------------------------------------------------------
# Pythagorean
# ---------------------------------------------------------------------------


class TestPythagorean:
    def test_zero_inputs_neutral(self):
        assert pythagorean_win_pct(0, 0) == 0.5

    def test_equal_runs_returns_half(self):
        assert pythagorean_win_pct(500, 500) == pytest.approx(0.5)

    def test_more_runs_scored_increases_pct(self):
        assert pythagorean_win_pct(600, 500) > 0.5

    def test_negative_clamped_to_zero(self):
        assert pythagorean_win_pct(-10, 100) == pytest.approx(0.0)

    def test_adjustment_zero_when_equal(self):
        assert pythagorean_elo_adjustment(500, 500, 500, 500) == pytest.approx(0.0)

    def test_adjustment_favors_better_pythag(self):
        adj = pythagorean_elo_adjustment(600, 500, 500, 600)
        assert adj > 0  # home is the better pythagorean team

    def test_adjustment_capped(self):
        adj = pythagorean_elo_adjustment(2000, 100, 100, 2000)
        assert abs(adj) <= MAX_FEATURE_ELO


# ---------------------------------------------------------------------------
# Park factors
# ---------------------------------------------------------------------------


class TestParkFactors:
    def test_unknown_venue_zero(self):
        assert park_factor_elo_adjustment("Mars Stadium", 1600, 1500) == 0.0

    def test_none_venue_zero(self):
        assert park_factor_elo_adjustment(None, 1600, 1500) == 0.0

    def test_neutral_park_zero(self):
        # Find a venue with factor 1.00 — none in current map, simulate via key
        PARK_FACTORS["NeutralPark"] = 1.00
        try:
            assert park_factor_elo_adjustment("NeutralPark", 1600, 1500) == 0.0
        finally:
            PARK_FACTORS.pop("NeutralPark")

    def test_hitter_park_amplifies_offense_gap(self):
        # Coors (factor 1.20) with home offense better → positive adj
        adj = park_factor_elo_adjustment("Coors Field", 1600, 1500)
        assert adj > 0

    def test_pitcher_park_dampens(self):
        # Oracle Park (factor 0.92) with home offense better → negative adj
        adj = park_factor_elo_adjustment("Oracle Park", 1600, 1500)
        assert adj < 0


# ---------------------------------------------------------------------------
# Bullpen
# ---------------------------------------------------------------------------


class TestBullpen:
    def test_zero_era_returns_zero(self):
        assert bullpen_elo_adjustment(0, 3.5) == 0.0
        assert bullpen_elo_adjustment(3.5, 0) == 0.0

    def test_better_home_bullpen_positive(self):
        # home 3.0, away 4.0 → home advantaged
        assert bullpen_elo_adjustment(3.0, 4.0) > 0

    def test_capped(self):
        assert abs(bullpen_elo_adjustment(0.5, 9.0)) <= MAX_FEATURE_ELO


# ---------------------------------------------------------------------------
# Rest
# ---------------------------------------------------------------------------


class TestRest:
    def test_equal_rest_zero(self):
        assert rest_elo_adjustment(1, 1) == 0.0

    def test_home_more_rested_positive(self):
        assert rest_elo_adjustment(2, 0) > 0

    def test_saturates_at_two(self):
        # 5 vs 0 == 2 vs 0 (saturated)
        assert rest_elo_adjustment(5, 0) == rest_elo_adjustment(2, 0)


# ---------------------------------------------------------------------------
# Recent form
# ---------------------------------------------------------------------------


class TestRecentForm:
    def test_no_history_zero_adjustment(self):
        f = RecentFormTracker()
        assert f.elo_adjustment("A", "B") == 0.0
        assert f.win_pct("A") is None

    def test_window_caps_records(self):
        f = RecentFormTracker(window=3)
        for _ in range(5):
            f.update("A", True)
        assert f.win_pct("A") == 1.0
        # only 3 records retained
        assert len(f._records["A"]) == 3

    def test_better_form_positive_adjustment(self):
        f = RecentFormTracker(window=10)
        for _ in range(10):
            f.update("Hot", True)
            f.update("Cold", False)
        assert f.elo_adjustment("Hot", "Cold") > 0

    def test_symmetric(self):
        f = RecentFormTracker(window=10)
        for _ in range(10):
            f.update("Hot", True)
            f.update("Cold", False)
        assert f.elo_adjustment("Hot", "Cold") == pytest.approx(
            -f.elo_adjustment("Cold", "Hot")
        )


# ---------------------------------------------------------------------------
# Rest tracker
# ---------------------------------------------------------------------------


class TestRestTracker:
    def test_first_game_neutral(self):
        rt = RestTracker()
        assert rt.days_rest("A", date(2024, 5, 1)) == 2

    def test_back_to_back(self):
        rt = RestTracker()
        rt.record("A", date(2024, 5, 1))
        assert rt.days_rest("A", date(2024, 5, 2)) == 0

    def test_two_days_rest(self):
        rt = RestTracker()
        rt.record("A", date(2024, 5, 1))
        assert rt.days_rest("A", date(2024, 5, 4)) == 2

    def test_capped_at_seven(self):
        rt = RestTracker()
        rt.record("A", date(2024, 5, 1))
        assert rt.days_rest("A", date(2024, 6, 1)) == 7


# ---------------------------------------------------------------------------
# Bayesian shrinkage
# ---------------------------------------------------------------------------


class TestBayesianShrink:
    def test_zero_games_returns_prior(self):
        assert bayesian_shrink(1700, 1500, games_played=0) == pytest.approx(1500)

    def test_many_games_returns_rating(self):
        out = bayesian_shrink(1700, 1500, games_played=1000)
        assert out > 1690  # nearly fully trusts the rating

    def test_partial_shrinkage(self):
        out = bayesian_shrink(1700, 1500, games_played=30, prior_strength=30)
        assert out == pytest.approx(1600)  # exact 50/50
