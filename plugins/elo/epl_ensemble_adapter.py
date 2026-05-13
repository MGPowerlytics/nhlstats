"""EPL ensemble adapter preserving the Elo interface used by the DAG."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from plugins.elo.epl_elo_rating import EPLEloRating
from plugins.elo.epl_ensemble import EPLEnsembleModel


@dataclass
class _EPLTeamStats:
    """Rolling per-team season aggregates for EPL."""

    games_played: int = 0
    goals_for: float = 0.0
    goals_against: float = 0.0
    wins: float = 0.0
    recent_results: list[float] = field(default_factory=list)


@dataclass
class EPLEnsembleAdapter:
    """Drop-in EPL predictor combining Elo, form, and bookmaker context."""

    elo: EPLEloRating = field(default_factory=EPLEloRating)
    ensemble: EPLEnsembleModel = field(default_factory=EPLEnsembleModel)
    team_stats: dict[str, _EPLTeamStats] = field(default_factory=dict)
    bookmaker_probs: dict[tuple[str, str], dict[str, float]] = field(
        default_factory=dict
    )
    reference_date: date | None = None
    auto_train: bool = True

    def __post_init__(self) -> None:
        """Load or train the underlying ensemble when enabled."""
        if self.auto_train:
            self.ensemble.ensure_trained()

    @property
    def ratings(self) -> dict[str, float]:
        """Expose the underlying Elo ratings dict for drop-in compatibility."""
        return self.elo.ratings

    @ratings.setter
    def ratings(self, new_ratings: dict[str, float]) -> None:
        self.elo.ratings = dict(new_ratings or {})

    def get_rating(self, team: str) -> float:
        """Return the current Elo rating for a team."""
        return self.elo.get_rating(team)

    def get_all_ratings(self) -> dict[str, float]:
        """Return all currently loaded Elo ratings."""
        return self.elo.get_all_ratings()

    def has_real_rating(self, team: str) -> bool:
        """Delegate real-rating detection to the underlying Elo system."""
        return self.elo.has_real_rating(team)

    def predict_probs(
        self, home_team: str, away_team: str
    ) -> tuple[float, float, float]:
        """Predict Home/Draw/Away probabilities."""
        home_elo_prob, draw_elo_prob, away_elo_prob = self.elo.predict_probs(
            home_team,
            away_team,
        )

        # NEW: Calibrate Home win probability
        try:
            from plugins.probability_calibration import ProbabilityCalibrator
            from plugins.db_manager import default_db
            calibrator = ProbabilityCalibrator(db=default_db)
            home_elo_prob = calibrator.calibrate("epl", home_elo_prob)
            # Re-normalize draw and away to accommodate the new home prob
            rem = 1.0 - home_elo_prob
            total_rem = draw_elo_prob + away_elo_prob
            if total_rem > 0:
                draw_elo_prob = (draw_elo_prob / total_rem) * rem
                away_elo_prob = (away_elo_prob / total_rem) * rem
        except Exception:
            pass

        home_stats = self.team_stats.get(home_team, _EPLTeamStats())
        away_stats = self.team_stats.get(away_team, _EPLTeamStats())
        bookmaker_probs = self.bookmaker_probs.get(
            (home_team, away_team),
            {"home": 0.45, "draw": 0.25, "away": 0.30},
        )

        features = {
            "elo_prob_home": home_elo_prob,
            "elo_prob_draw": draw_elo_prob,
            "elo_prob_away": away_elo_prob,
            "elo_diff": self.elo.get_rating(home_team) - self.elo.get_rating(away_team),
            "home_form": _recent_form(home_stats),
            "away_form": _recent_form(away_stats),
            "home_avg_gf": _goal_average(
                home_stats.goals_for, home_stats.games_played, 1.4
            ),
            "away_avg_gf": _goal_average(
                away_stats.goals_for, away_stats.games_played, 1.2
            ),
            "home_avg_ga": _goal_average(
                home_stats.goals_against,
                home_stats.games_played,
                1.2,
            ),
            "away_avg_ga": _goal_average(
                away_stats.goals_against,
                away_stats.games_played,
                1.4,
            ),
            "bookmaker_prob_home": bookmaker_probs["home"],
            "bookmaker_prob_draw": bookmaker_probs["draw"],
            "bookmaker_prob_away": bookmaker_probs["away"],
        }

        probabilities = self.ensemble.predict_probs(features)
        return (
            probabilities["home"],
            probabilities["draw"],
            probabilities["away"],
        )

    def predict(
        self, home_team: str, away_team: str, is_neutral: bool = False
    ) -> float:
        """Return the home-win probability for compatibility with Elo callers."""
        home_prob, _, _ = self.predict_probs(home_team, away_team)
        if is_neutral:
            return self.elo.predict(home_team, away_team, is_neutral=True)
        return home_prob

    def predict_3way(self, home_team: str, away_team: str) -> dict[str, float]:
        """Return Home/Draw/Away probabilities in dict form."""
        home_prob, draw_prob, away_prob = self.predict_probs(home_team, away_team)
        return {"home": home_prob, "draw": draw_prob, "away": away_prob}

    def update(self, home_team: str, away_team: str, home_won: Any, **kwargs) -> Any:
        """Update the underlying Elo system after a result."""
        return self.elo.update(home_team, away_team, home_won, **kwargs)

    def populate_from_db(
        self,
        db: Any,
        season_year: int | None = None,
        reference_date: date | None = None,
    ) -> None:
        """Populate rolling team context and upcoming bookmaker probabilities."""
        ref = reference_date or date.today()
        self.reference_date = ref
        year = season_year or (ref.year if ref.month >= 8 else ref.year - 1)

        self._load_team_stats(db, year, ref)
        self._load_bookmaker_odds(db, ref)

    def _load_team_stats(self, db: Any, year: int, ref: date) -> None:
        """Aggregate current-season EPL team form and goal rates."""
        query = """
            SELECT game_date, home_team, away_team, home_score, away_score, result
            FROM epl_games
            WHERE game_date < :ref
              AND (EXTRACT(YEAR FROM game_date) = :year OR EXTRACT(YEAR FROM game_date) = :year + 1)
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND result IS NOT NULL
            ORDER BY game_date
        """
        frame = db.fetch_df(query, {"year": int(year), "ref": ref})
        if frame is None or frame.empty:
            self.team_stats = {}
            return

        stats: dict[str, _EPLTeamStats] = {}

        for row in frame.itertuples(index=False):
            home_team = row.home_team
            away_team = row.away_team
            home_score = float(row.home_score)
            away_score = float(row.away_score)
            result = str(row.result)

            home_stats = stats.setdefault(home_team, _EPLTeamStats())
            away_stats = stats.setdefault(away_team, _EPLTeamStats())

            home_stats.games_played += 1
            home_stats.goals_for += home_score
            home_stats.goals_against += away_score

            away_stats.games_played += 1
            away_stats.goals_for += away_score
            away_stats.goals_against += home_score

            if result == "H":
                home_stats.wins += 1.0
                home_stats.recent_results.append(1.0)
                away_stats.recent_results.append(0.0)
            elif result == "A":
                away_stats.wins += 1.0
                home_stats.recent_results.append(0.0)
                away_stats.recent_results.append(1.0)
            else:
                home_stats.wins += 0.5
                away_stats.wins += 0.5
                home_stats.recent_results.append(0.5)
                away_stats.recent_results.append(0.5)

            if len(home_stats.recent_results) > 5:
                home_stats.recent_results.pop(0)
            if len(away_stats.recent_results) > 5:
                away_stats.recent_results.pop(0)

        self.team_stats = stats

    def _load_bookmaker_odds(self, db: Any, ref: date) -> None:
        """Load consensus bookmaker probabilities for upcoming EPL matchups."""
        query = """
            SELECT
                u.home_team_name,
                u.away_team_name,
                o.outcome_name,
                o.price
            FROM unified_games u
            JOIN game_odds o ON u.game_id = o.game_id
            WHERE u.sport = 'EPL'
              AND u.game_date >= :ref
              AND u.game_date < :ref + interval '7 days'
              AND o.market_name = '3-way'
            ORDER BY o.last_update DESC
        """
        frame = db.fetch_df(query, {"ref": ref})
        if frame is None or frame.empty:
            self.bookmaker_probs = {}
            return

        bookmaker_probs: dict[tuple[str, str], dict[str, float]] = {}
        for (home_team, away_team), matchup_frame in frame.groupby(
            ["home_team_name", "away_team_name"]
        ):
            outcome_probs: dict[str, float] = {}
            for outcome_name, outcome_frame in matchup_frame.groupby("outcome_name"):
                normalized_name = str(outcome_name).strip().lower()
                price = float(outcome_frame["price"].iloc[0])
                if price <= 0:
                    continue
                if normalized_name in {"home", "h"}:
                    outcome_probs["home"] = 1.0 / price
                elif normalized_name in {"draw", "d"}:
                    outcome_probs["draw"] = 1.0 / price
                elif normalized_name in {"away", "a"}:
                    outcome_probs["away"] = 1.0 / price

            if not outcome_probs:
                continue

            probs = np.array(
                [
                    outcome_probs.get("home", 0.45),
                    outcome_probs.get("draw", 0.25),
                    outcome_probs.get("away", 0.30),
                ],
                dtype=float,
            )
            probs /= probs.sum()
            bookmaker_probs[(home_team, away_team)] = {
                "home": float(probs[0]),
                "draw": float(probs[1]),
                "away": float(probs[2]),
            }

        self.bookmaker_probs = bookmaker_probs


def _recent_form(team_stats: _EPLTeamStats) -> float:
    """Return mean recent result points or the neutral fallback."""
    if not team_stats.recent_results:
        return 0.5
    return float(np.mean(team_stats.recent_results))


def _goal_average(total_goals: float, games_played: int, default: float) -> float:
    """Return per-game goals or a deterministic fallback."""
    if games_played <= 0:
        return default
    return total_goals / games_played
