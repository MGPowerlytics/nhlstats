"""Unit tests for plugins.elo.mlb_pitcher_elo and mlb_ensemble."""

from __future__ import annotations

from datetime import date

import pytest

from plugins.elo.mlb_ensemble import MLBEnsembleModel, MLBPredictionContext
from plugins.elo.mlb_pitcher_elo import PitcherEloLadder


# ---------------------------------------------------------------------------
# PitcherEloLadder
# ---------------------------------------------------------------------------


class TestPitcherEloLadder:
    def test_unknown_pitcher_returns_initial(self):
        l = PitcherEloLadder()
        assert l.get_rating("999") == 1500.0
        assert l.get_rating(None) == 1500.0

    def test_no_adjustment_when_pitcher_missing(self):
        l = PitcherEloLadder()
        assert l.matchup_adjustment(None, "12") == 0.0
        assert l.matchup_adjustment("12", None) == 0.0

    def test_winner_gains_loser_loses(self):
        l = PitcherEloLadder()
        l.update("home_p", "away_p", home_won=True)
        assert l.get_rating("home_p") > 1500
        assert l.get_rating("away_p") < 1500
        # Symmetric magnitude
        delta_h = l.get_rating("home_p") - 1500
        delta_a = 1500 - l.get_rating("away_p")
        assert delta_h == pytest.approx(delta_a)

    def test_matchup_adjustment_signs(self):
        l = PitcherEloLadder()
        # Inflate home pitcher
        for _ in range(10):
            l.update("ace", "scrub", home_won=True)
        assert l.matchup_adjustment("ace", "scrub") > 0
        assert l.matchup_adjustment("scrub", "ace") < 0

    def test_update_with_missing_pitcher_is_noop(self):
        l = PitcherEloLadder()
        before = l.all_ratings()
        l.update(None, "p", True)
        l.update("p", None, True)
        assert l.all_ratings() == before


# ---------------------------------------------------------------------------
# MLBEnsembleModel
# ---------------------------------------------------------------------------


class TestMLBEnsembleModel:
    def test_predict_returns_valid_probability(self):
        m = MLBEnsembleModel()
        ctx = MLBPredictionContext(home_team="LAD", away_team="SDP")
        p = m.predict(ctx)
        assert 0.0 < p < 1.0

    def test_default_home_advantage_makes_prediction_above_half(self):
        m = MLBEnsembleModel()
        ctx = MLBPredictionContext(home_team="X", away_team="Y")
        # Both teams unknown → equal Elo, only home advantage applies
        assert m.predict(ctx) > 0.5

    def test_pitcher_advantage_lifts_prediction(self):
        m = MLBEnsembleModel()
        # Make home pitcher much better
        for _ in range(20):
            m.pitcher_elo.update("ace", "scrub", home_won=True)
        ctx_with = MLBPredictionContext(
            home_team="X",
            away_team="Y",
            home_pitcher_id="ace",
            away_pitcher_id="scrub",
        )
        ctx_without = MLBPredictionContext(home_team="X", away_team="Y")
        assert m.predict(ctx_with) > m.predict(ctx_without)

    def test_market_blend_pulls_toward_market(self):
        m = MLBEnsembleModel()
        ctx = MLBPredictionContext(
            home_team="X",
            away_team="Y",
            market_prob=0.20,
            market_blend_weight=1.0,
        )
        assert m.predict(ctx) == pytest.approx(0.20)

    def test_observe_updates_all_layers(self):
        m = MLBEnsembleModel()
        ctx = MLBPredictionContext(
            home_team="A",
            away_team="B",
            home_pitcher_id="hp",
            away_pitcher_id="ap",
        )
        m.observe(ctx, home_won=True, game_date=date(2024, 5, 1),
                  home_score=5, away_score=2)
        assert m.team_elo.get_rating("A") > 1500
        assert m.team_elo.get_rating("B") < 1500
        assert m.pitcher_elo.get_rating("hp") > 1500
        assert m.pitcher_elo.get_rating("ap") < 1500
        assert m.form.win_pct("A") == 1.0
        assert m.form.win_pct("B") == 0.0

    def test_back_to_back_rest_penalizes(self):
        m = MLBEnsembleModel()
        ctx_first = MLBPredictionContext(home_team="A", away_team="B")
        m.observe(ctx_first, home_won=True, game_date=date(2024, 5, 1))

        # next-day game: home on B2B (0 rest), away well-rested
        next_ctx = MLBPredictionContext(
            home_team="A",
            away_team="C",
            home_rest_days=0,
            away_rest_days=2,
        )
        same_rested = MLBPredictionContext(
            home_team="A",
            away_team="C",
            home_rest_days=2,
            away_rest_days=2,
        )
        assert m.predict(next_ctx) < m.predict(same_rested)
