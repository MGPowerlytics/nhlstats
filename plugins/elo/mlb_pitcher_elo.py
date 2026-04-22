"""Starting-pitcher Elo ladder for MLB.

Rationale
---------
The starting pitcher is the single largest within-game variable in MLB,
explaining ~25-30% of game-outcome variance (FanGraphs WAR breakdown).
A team-only Elo system implicitly averages over the entire rotation,
which is wrong on any specific day — Gerrit Cole vs Wade Miley is a
materially different matchup than the Yankees-Brewers team averages.

This module maintains a *separate* Elo ladder keyed by pitcher ID and
exposes a helper that returns an Elo-point adjustment for the home team
based on the matchup's starting pitcher gap.

Calibration
-----------
* K-factor 6 (slightly higher than team Elo because pitchers throw only
  ~30 starts/yr — fewer observations need more responsive updates).
* New-pitcher prior 1500.
* Output adjustment is dampened by ``pitcher_weight=0.35`` because the
  pitcher's contribution is only one component of run prevention.

The pitcher Elo ladder is updated using *runs allowed by the team's
pitching while that pitcher was in the game*, but for simplicity (and
because we lack per-inning data in the games table) we attribute the
team's full run-allowed total to the starter on each end. This is a
known approximation; if we later add per-pitcher IP from the boxscore,
swap to a per-IP weighting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class PitcherEloLadder:
    """Lightweight Elo ladder keyed by pitcher identifier."""

    k_factor: float = 6.0
    initial_rating: float = 1500.0
    pitcher_weight: float = 0.35
    _ratings: Dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------
    def get_rating(self, pitcher_id: Optional[str]) -> float:
        """Return current Elo for ``pitcher_id`` (or initial if unknown)."""
        if pitcher_id is None:
            return self.initial_rating
        return self._ratings.get(str(pitcher_id), self.initial_rating)

    def matchup_adjustment(
        self,
        home_pitcher_id: Optional[str],
        away_pitcher_id: Optional[str],
    ) -> float:
        """Return Elo points to add to the home team for this matchup.

        Positive = home pitcher is the better one.
        Returns 0.0 when either pitcher is unknown (no information).
        """
        if not home_pitcher_id or not away_pitcher_id:
            return 0.0
        h = self.get_rating(home_pitcher_id)
        a = self.get_rating(away_pitcher_id)
        return (h - a) * self.pitcher_weight

    # ------------------------------------------------------------------
    # Update API
    # ------------------------------------------------------------------
    def update(
        self,
        home_pitcher_id: Optional[str],
        away_pitcher_id: Optional[str],
        home_won: bool,
    ) -> None:
        """Update both pitcher ratings after a game result.

        Pitchers are credited / debited symmetrically using the standard
        Elo update with no home advantage (the team-Elo layer already
        applies it).
        """
        if not home_pitcher_id or not away_pitcher_id:
            return
        hpid, apid = str(home_pitcher_id), str(away_pitcher_id)
        h = self.get_rating(hpid)
        a = self.get_rating(apid)
        expected_h = 1.0 / (1.0 + 10.0 ** ((a - h) / 400.0))
        actual_h = 1.0 if home_won else 0.0
        change = self.k_factor * (actual_h - expected_h)
        self._ratings[hpid] = h + change
        self._ratings[apid] = a - change

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def all_ratings(self) -> Dict[str, float]:
        """Return a copy of the underlying rating map."""
        return dict(self._ratings)
