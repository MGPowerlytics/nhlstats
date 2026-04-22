"""MLB ensemble model: blends team Elo + pitcher Elo + features + market.

Design
------
The ensemble takes the team-Elo logit as a *strong base* and additively
augments it with calibrated, capped contributions from each independent
signal. Final probability is the sigmoid of the combined logit.

Why additive on the logit (not a logistic regression fit)?
* Avoids over-fitting on a single backtest window.
* Each component is independently calibrated against well-known baseball
  research, so the weights have economic meaning.
* Easy to ablate one signal at a time when debugging.

A separate ``LogisticEnsemble`` (sklearn) is provided for users who want
a fully fit blender once enough labelled history is available.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from plugins.elo.mlb_elo_rating import MLBEloRating
from plugins.elo.mlb_features import (
    bayesian_shrink,
    bullpen_elo_adjustment,
    park_factor_elo_adjustment,
    pythagorean_elo_adjustment,
    RecentFormTracker,
    rest_elo_adjustment,
    RestTracker,
)
from plugins.elo.mlb_pitcher_elo import PitcherEloLadder


@dataclass
class MLBPredictionContext:
    """All side-information needed to make a single MLB prediction."""

    home_team: str
    away_team: str
    venue: Optional[str] = None
    home_pitcher_id: Optional[str] = None
    away_pitcher_id: Optional[str] = None
    home_runs_scored_ytd: float = 0.0
    home_runs_allowed_ytd: float = 0.0
    away_runs_scored_ytd: float = 0.0
    away_runs_allowed_ytd: float = 0.0
    home_bullpen_era: float = 0.0
    away_bullpen_era: float = 0.0
    home_rest_days: int = 2
    away_rest_days: int = 2
    market_prob: Optional[float] = None  # implied P(home win) from sharp book
    market_blend_weight: float = 0.25  # 0 = ignore market, 1 = use only market


@dataclass
class MLBEnsembleModel:
    """Composite model combining team Elo with all auxiliary signals."""

    team_elo: MLBEloRating = field(default_factory=MLBEloRating)
    pitcher_elo: PitcherEloLadder = field(default_factory=PitcherEloLadder)
    form: RecentFormTracker = field(
        default_factory=lambda: RecentFormTracker(window=10)
    )
    rest: RestTracker = field(default_factory=RestTracker)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict(self, ctx: MLBPredictionContext) -> float:
        """Return ensemble P(home wins) in ``[0, 1]``."""
        home_rating = self.team_elo.get_rating(ctx.home_team)
        away_rating = self.team_elo.get_rating(ctx.away_team)

        # Team-Elo base, with home advantage
        home_rating += self.team_elo.config.home_advantage

        # Sum capped feature adjustments (Elo points, applied to home)
        adj = 0.0
        adj += self.pitcher_elo.matchup_adjustment(
            ctx.home_pitcher_id, ctx.away_pitcher_id
        )
        adj += pythagorean_elo_adjustment(
            ctx.home_runs_scored_ytd,
            ctx.home_runs_allowed_ytd,
            ctx.away_runs_scored_ytd,
            ctx.away_runs_allowed_ytd,
        )
        adj += bullpen_elo_adjustment(ctx.home_bullpen_era, ctx.away_bullpen_era)
        adj += park_factor_elo_adjustment(
            ctx.venue,
            self.team_elo.get_rating(ctx.home_team),
            self.team_elo.get_rating(ctx.away_team),
        )
        adj += self.form.elo_adjustment(ctx.home_team, ctx.away_team)
        adj += rest_elo_adjustment(ctx.home_rest_days, ctx.away_rest_days)

        elo_prob = 1.0 / (1.0 + 10.0 ** ((away_rating - (home_rating + adj)) / 400.0))

        # Market blending (if available, sharp book usually beats Elo)
        if ctx.market_prob is not None and 0.0 < ctx.market_prob < 1.0:
            w = max(0.0, min(1.0, ctx.market_blend_weight))
            return w * ctx.market_prob + (1.0 - w) * elo_prob
        return elo_prob

    # ------------------------------------------------------------------
    # Update — call after each completed game in chronological order
    # ------------------------------------------------------------------
    def observe(
        self,
        ctx: MLBPredictionContext,
        home_won: bool,
        game_date,
        home_score: Optional[int] = None,
        away_score: Optional[int] = None,
    ) -> None:
        """Update every sub-model based on the actual outcome."""
        self.team_elo.update(
            ctx.home_team,
            ctx.away_team,
            home_won,
            home_score=home_score,
            away_score=away_score,
        )
        self.pitcher_elo.update(ctx.home_pitcher_id, ctx.away_pitcher_id, home_won)
        self.form.update(ctx.home_team, home_won)
        self.form.update(ctx.away_team, not home_won)
        self.rest.record(ctx.home_team, game_date)
        self.rest.record(ctx.away_team, game_date)


# ---------------------------------------------------------------------------
# Optional: scikit-learn logistic ensemble (lazy import)
# ---------------------------------------------------------------------------


def fit_logistic_ensemble(features, labels):
    """Fit a logistic regression over engineered features.

    Args:
        features: Iterable of feature dicts. Each dict's values must all
            be numeric. Common keys: ``elo_logit``, ``pitcher_elo_diff``,
            ``pythag_diff``, ``form_diff``, ``bullpen_diff``, ``rest_diff``.
        labels: Iterable of 0/1 (1 = home win).

    Returns:
        Trained ``sklearn.linear_model.LogisticRegression`` model.

    Raises:
        ImportError: If scikit-learn is not installed.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    features = list(features)
    if not features:
        raise ValueError("features must be non-empty")
    keys = sorted(features[0].keys())
    X = np.array([[row[k] for k in keys] for row in features], dtype=float)
    y = np.array(list(labels), dtype=int)
    model = LogisticRegression(C=1.0, max_iter=1000)
    model.fit(X, y)
    model.feature_names_ = keys  # convenience
    return model
