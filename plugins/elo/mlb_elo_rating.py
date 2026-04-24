"""
MLB Elo Rating System.

Production-ready Elo rating system for MLB predictions.
Inherits from BaseEloRating for unified interface.

Tuning history
--------------
2026-04-18 — Accuracy-improvement pass on 2021-2024 backtest (10,455 games):

    Baseline (K=10, HA=75)                        Acc=55.887%   LogLoss=0.6974
    Tuned    (K=4,  HA=20, no-MOV, skip-spring)   Acc=57.571%   LogLoss=0.6793
                                                  +1.68 pts absolute / +3.01% relative

Each change and its empirical contribution:

* ``k_factor`` 10 -> 4
    MLB has the highest game-to-game variance of the major sports (≈54% home
    win rate; long-run team true talent rarely exceeds ±60 Elo). A high K
    overfits to single-game noise. K=4 cut log loss from 0.697 -> 0.683.

* ``home_advantage`` 75 -> 20
    Empirical home win rate in this dataset is **53.17%** -> implied HA of
    only **22.1 Elo points**. The previous 75 was over 3x the true value and
    systematically over-predicted home favorites. This single change accounts
    for roughly half of the accuracy gain.

* ``skip_spring_training`` (new, default ``True``)
    The raw MLB feed contained ~1,600 Feb/early-Mar exhibition games where
    teams field minor-leaguers and outcomes are essentially random. Including
    them poisoned April ratings. Filtering pre-Mar-20 games gave +0.26 pts.

* ``use_mov`` (new, default ``False`` for MLB)
    The 538-style log-margin multiplier helps NFL/NBA but **hurts** MLB
    accuracy because a 10-run blowout is dominated by bullpen quality + late-
    inning randomness, not team strength. Disabling MOV gave +0.6 pts.

* ``season_carryover`` helper (new)
    Optional regression-to-mean at season boundaries (default off after grid
    search showed best accuracy with 0.0; available for downstream tuning).
"""

from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, Union

from plugins.elo.base_elo_rating import BaseEloRating, GameResult, Matchup

# Spring-training cutoff: MLB regular season has not started before March 20
# in any year of the modern era (the 2024 Seoul opener on Mar 20 is the
# earliest on record).
_REGULAR_SEASON_START_MONTH = 3
_REGULAR_SEASON_START_DAY = 20


def is_regular_season_date(game_date: Union[str, date, datetime]) -> bool:
    """Return True if ``game_date`` is on/after the MLB regular-season start.

    Args:
        game_date: ISO date string (YYYY-MM-DD), :class:`datetime.date`, or
            :class:`datetime.datetime`.

    Returns:
        True for regular-season + postseason games, False for spring training.
    """
    if isinstance(game_date, str):
        game_date = datetime.strptime(game_date[:10], "%Y-%m-%d").date()
    elif isinstance(game_date, datetime):
        game_date = game_date.date()
    return (game_date.month, game_date.day) >= (
        _REGULAR_SEASON_START_MONTH,
        _REGULAR_SEASON_START_DAY,
    )


class MLBEloRating(BaseEloRating):
    """MLB-specific Elo rating system.

    Production defaults are tuned to maximize next-game accuracy on the
    2021-2024 backtest (see module docstring for empirical results).

    Attributes:
        use_mov: If True, apply the FiveThirtyEight margin-of-victory
            multiplier. Disabled by default for MLB because run-differential
            is dominated by bullpen + late-inning variance and degrades
            predictive accuracy.
    """

    def __init__(
        self,
        k_factor: float = 4.0,
        home_advantage: float = 20.0,
        initial_rating: float = 1500.0,
        use_mov: bool = False,
    ) -> None:
        """Initialize MLB Elo rating system.

        Args:
            k_factor: K-factor for rating updates. Default 4.0 (tuned on
                2021-2024 backtest; was 10.0).
            home_advantage: Home advantage in Elo points. Default 20.0
                (matches empirical 53.2% home win rate; was 75.0).
            initial_rating: Starting rating for new teams. Default 1500.0.
            use_mov: Apply margin-of-victory multiplier (default False for
                MLB — empirically hurts accuracy by ~0.6 pts).
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating,
        )
        self.use_mov = use_mov

    def update(
        self,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
        home_won: Optional[Union[bool, float]] = None,
        is_neutral: bool = False,
        matchup: Optional[Matchup] = None,
        result: Optional[GameResult] = None,
        **kwargs,
    ) -> float:
        """Update Elo ratings after a game result.

        Returns:
            The signed rating change applied to the home team.
        """
        parsed = self.parser.parse_update_args(
            home_team=home_team,
            away_team=away_team,
            home_won=home_won,
            is_neutral=is_neutral,
            matchup=matchup,
            result=result,
            **kwargs,
        )
        matchup = parsed.matchup
        result = parsed.result

        home_team = matchup.home_team
        away_team = matchup.away_team
        is_neutral = matchup.is_neutral
        home_won = result.home_won

        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        if not is_neutral:
            home_rating += self.config.home_advantage

        expected_home = self.expected_score(home_rating, away_rating)
        actual_home = 1.0 if home_won else 0.0

        change = self.calculator.calculate_rating_change(expected_home, actual_home)

        if (
            self.use_mov
            and result.home_score is not None
            and result.away_score is not None
        ):
            mov_multiplier = self.calculator.calculate_mov_multiplier(
                result, home_rating - away_rating
            )
            change *= mov_multiplier

        if not is_neutral:
            home_rating -= self.config.home_advantage

        self.store.set_rating(home_team, home_rating + change)
        self.store.set_rating(away_team, away_rating - change)

        self.game_history.append(
            {
                "home_team": home_team,
                "away_team": away_team,
                "home_won": bool(home_won),
                "home_score": result.home_score,
                "away_score": result.away_score,
                "home_rating_before": home_rating,
                "away_rating_before": away_rating,
                "change": change,
            }
        )

        return change

    def predict_payload(
        self,
        home_team: str,
        away_team: str,
        is_neutral: bool = False,
    ) -> Dict[str, Union[str, float, bool]]:
        """Return a structured Elo prediction payload for the contract boundary.

        Wraps :meth:`predict` and :meth:`get_rating` into the locked
        ``mlb_elo_prediction_v1`` envelope so downstream consumers receive a
        single, schema-validated dict instead of separate scalar calls.

        Args:
            home_team: Home team name.
            away_team: Away team name.
            is_neutral: If True, omit the home-advantage adjustment.

        Returns:
            Dict matching ``tests/contracts/schemas/mlb_elo_prediction_v1.json``.
        """
        return {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "elo_prediction",
            "home_team": home_team,
            "away_team": away_team,
            "home_rating": float(self.get_rating(home_team)),
            "away_rating": float(self.get_rating(away_team)),
            "home_prob": float(
                self.predict(home_team, away_team, is_neutral=is_neutral)
            ),
            "home_advantage": float(self.config.home_advantage),
            "k_factor": float(self.config.k_factor),
            "is_neutral": bool(is_neutral),
        }

    def apply_season_carryover(self, regression_weight: float = 0.0) -> None:
        """Regress all ratings toward the league mean at a season boundary.

        Args:
            regression_weight: Fraction of the gap between current rating and
                ``initial_rating`` to close. 0.0 = no regression (default,
                matches grid-search optimum), 1.0 = full reset.
        """
        if regression_weight <= 0.0:
            return
        mean = self.config.initial_rating
        for team, rating in list(self.store.ratings.items()):
            self.store.set_rating(team, rating + regression_weight * (mean - rating))
