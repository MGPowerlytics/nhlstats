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

    def rating_payload(self, pitcher_id: str) -> Dict[str, object]:
        """Return a structured pitcher-rating payload for the contract boundary.

        Args:
            pitcher_id: Identifier for the pitcher (string-coerced).

        Returns:
            Dict matching ``mlb_pitcher_elo_v1.json::$defs.pitcher_rating``.
        """
        return {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "pitcher_rating",
            "pitcher_id": str(pitcher_id),
            "rating": float(self.get_rating(pitcher_id)),
            "k_factor": float(self.k_factor),
            "pitcher_weight": float(self.pitcher_weight),
        }

    def matchup_payload(
        self,
        home_pitcher_id: Optional[str],
        away_pitcher_id: Optional[str],
    ) -> Dict[str, object]:
        """Return a structured pitcher-matchup payload for the contract boundary.

        The ``adjustment_elo`` field carries the value of
        :meth:`matchup_adjustment` so consumers can validate it as part of
        a single dict.

        Args:
            home_pitcher_id: Home starter id (may be None).
            away_pitcher_id: Away starter id (may be None).

        Returns:
            Dict matching ``mlb_pitcher_elo_v1.json::$defs.pitcher_matchup``.
        """
        return {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "pitcher_matchup",
            "home_pitcher_id": (
                str(home_pitcher_id) if home_pitcher_id is not None else None
            ),
            "away_pitcher_id": (
                str(away_pitcher_id) if away_pitcher_id is not None else None
            ),
            "home_rating": float(self.get_rating(home_pitcher_id)),
            "away_rating": float(self.get_rating(away_pitcher_id)),
            "adjustment_elo": float(
                self.matchup_adjustment(home_pitcher_id, away_pitcher_id)
            ),
            "pitcher_weight": float(self.pitcher_weight),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save_ratings(self, file_path: str = "data/mlb_pitcher_elo_ratings.csv") -> None:
        """Save all pitcher ratings to a CSV file."""
        import pandas as pd
        from pathlib import Path

        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(
            [{"pitcher_id": pid, "rating": r} for pid, r in self._ratings.items()]
        )
        if not df.empty:
            df.sort_values("rating", ascending=False, inplace=True)
        df.to_csv(file_path, index=False)

    def load_ratings(self, file_path: str = "data/mlb_pitcher_elo_ratings.csv") -> None:
        """Load pitcher ratings from a CSV file."""
        import os
        import pandas as pd

        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                self._ratings = dict(zip(df["pitcher_id"].astype(str), df["rating"]))
            except Exception as e:
                print(f"  ⚠️  Could not load pitcher ratings: {e}")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def all_ratings(self) -> Dict[str, float]:
        """Return a copy of the underlying rating map."""
        return dict(self._ratings)
