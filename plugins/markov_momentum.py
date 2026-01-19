"""Markov Momentum overlay for Elo.

This module implements a lightweight per-team first-order Markov model over
recent outcomes to provide a *momentum* adjustment on top of Elo.

The core idea:
- Track, per team, conditional win rates based on the team's *previous* outcome.
  Specifically, estimate:
    P(win | prev=win) and P(win | prev=loss)
- At prediction time, compute a logit adjustment:

    p_markov = sigmoid(logit(p_elo) + delta)

  where delta is proportional to the difference between the home team's and
  away team's conditional-next-win logits.

This is designed to be:
- Online (updated sequentially game-by-game)
- Leakage-safe (only uses outcomes strictly before the game being predicted)
- Minimal dependencies (pure Python)

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import math


def _clamp_prob(p: float, eps: float = 1e-6) -> float:
    """Clamp probability into (eps, 1-eps) to avoid infinities."""

    return min(1.0 - eps, max(eps, float(p)))


def logit(p: float) -> float:
    """Compute logit(p) with numerical safety."""

    p = _clamp_prob(p)
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""

    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass
class _Counts:
    wins: int = 0
    games: int = 0

    def update(self, win: bool) -> None:
        self.games += 1
        self.wins += int(bool(win))


@dataclass
class MarkovMomentum:
    """Per-team Markov momentum model.

    Args:
        alpha: Scaling factor for momentum impact on the Elo logit.
        smoothing: Strength of the global-prior smoothing. Higher values shrink
            team-specific conditional win rates more toward the global
            conditional win rate.

    """

    alpha: float = 0.35
    smoothing: float = 2.0

    last_outcome: Dict[str, Optional[int]] = field(default_factory=dict)
    team_counts: Dict[Tuple[str, int], _Counts] = field(default_factory=dict)
    global_counts: Dict[int, _Counts] = field(
        default_factory=lambda: {0: _Counts(), 1: _Counts()}
    )

    def _get_prev(self, team: str) -> Optional[int]:
        return self.last_outcome.get(team)

    def _counts_for(self, team: str, prev: int) -> _Counts:
        key = (team, prev)
        if key not in self.team_counts:
            self.team_counts[key] = _Counts()
        return self.team_counts[key]

    def _smoothed_p_win(self, team: str, prev: int) -> float:
        """Smoothed estimate of P(win | prev).

        Uses a global conditional win rate as a prior:
            p = (wins_team + k * p_global) / (games_team + k)
        """

        team_c = self._counts_for(team, prev)
        global_c = self.global_counts[prev]

        p_global = 0.5 if global_c.games == 0 else global_c.wins / global_c.games
        k = float(self.smoothing)

        return (team_c.wins + k * p_global) / (team_c.games + k)

    def predict_logit_adjustment(self, home_team: str, away_team: str) -> float:
        """Compute the logit adjustment to add to an Elo logit.

        If either team has no previous outcome recorded, returns 0.0.
        """

        home_prev = self._get_prev(home_team)
        away_prev = self._get_prev(away_team)

        if home_prev is None or away_prev is None:
            return 0.0

        p_home = self._smoothed_p_win(home_team, int(home_prev))
        p_away = self._smoothed_p_win(away_team, int(away_prev))

        return float(self.alpha * (logit(p_home) - logit(p_away)))

    def apply(self, elo_prob: float, home_team: str, away_team: str) -> float:
        """Return Markov-adjusted probability given a baseline Elo probability."""

        delta = self.predict_logit_adjustment(home_team, away_team)
        return float(sigmoid(logit(elo_prob) + delta))

    def update_game(self, home_team: str, away_team: str, home_win: bool) -> None:
        """Update Markov transitions and last outcomes after a completed game."""

        away_win = not bool(home_win)

        home_prev = self._get_prev(home_team)
        away_prev = self._get_prev(away_team)

        if home_prev in (0, 1):
            self._counts_for(home_team, int(home_prev)).update(home_win)
            self.global_counts[int(home_prev)].update(home_win)

        if away_prev in (0, 1):
            self._counts_for(away_team, int(away_prev)).update(away_win)
            self.global_counts[int(away_prev)].update(away_win)

        self.last_outcome[home_team] = 1 if home_win else 0
        self.last_outcome[away_team] = 1 if away_win else 0
