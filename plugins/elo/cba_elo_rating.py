"""
CBA Elo Rating System - Chinese Basketball Association

Production-ready Elo rating system for CBA predictions.
Inherits from BaseEloRating for unified interface.
"""

from plugins.elo.base_elo_rating import BaseEloRating
from typing import Dict, Union
import pandas as pd
from dataclasses import dataclass


@dataclass
class EloUpdateParams:
    """Parameters for Elo rating update calculation."""

    home_team: str
    away_team: str
    home_won: Union[bool, float]
    is_neutral: bool
    home_rating_before: float
    away_rating_before: float


@dataclass
class GameHistoryParams:
    """Parameters for recording game history."""

    home_team: str
    away_team: str
    home_won: Union[bool, float]
    home_rating_before: float
    away_rating_before: float
    home_rating_after: float
    away_rating_after: float
    change: float
    expected_home: float


class CBAEloRating(BaseEloRating):
    """
    CBA-specific Elo rating system.

    Features:
    - Standard Elo with K=20, home advantage=80 (strong home advantage in China)
    - Margin of victory adjustment
    - Season-to-season regression
    - Game history tracking

    CBA League Notes:
    - 20 teams in the league
    - Season runs October to April
    - Very strong home court advantage in Chinese basketball
    """

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 80.0,  # Strong home advantage in CBA
        initial_rating: float = 1500.0,
    ) -> None:
        """
        Initialize CBA Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default 20.0)
            home_advantage: Home advantage in Elo points (default 80.0)
            initial_rating: Initial rating for new teams (default 1500.0)
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating,
        )

    def update(
        self,
        home_team: str,
        away_team: str,
        home_won: Union[bool, float] = None,
        is_neutral: bool = False,
        **kwargs,
    ) -> None:
        """
        Update Elo ratings after a game result.

        Args:
            home_team: Home team name
            away_team: Away team name
            home_won: True/1.0 if home team won, False/0.0 if away team won
            is_neutral: Whether the game was at a neutral site
            **kwargs: Additional arguments (e.g., home_win as alias)
        """
        # Validate and normalize arguments
        home_won = self._validate_and_normalize_args(
            home_team, away_team, home_won, kwargs
        )

        # Get current ratings before update
        home_rating_before = self.get_rating(home_team)
        away_rating_before = self.get_rating(away_team)

        # Create parameter object for Elo calculation
        elo_params = EloUpdateParams(
            home_team=home_team,
            away_team=away_team,
            home_won=home_won,
            is_neutral=is_neutral,
            home_rating_before=home_rating_before,
            away_rating_before=away_rating_before,
        )

        # Calculate updated ratings
        home_rating_after, away_rating_after, change, expected_home = (
            self._calculate_elo_update(elo_params)
        )

        # Apply changes
        self.store.set_rating(home_team, home_rating_after)
        self.store.set_rating(away_team, away_rating_after)

        # Create parameter object for game history
        history_params = GameHistoryParams(
            home_team=home_team,
            away_team=away_team,
            home_won=home_won,
            home_rating_before=home_rating_before,
            away_rating_before=away_rating_before,
            home_rating_after=home_rating_after,
            away_rating_after=away_rating_after,
            change=change,
            expected_home=expected_home,
        )

        # Record history
        self._record_game_history(history_params)

        self._track_team_history(home_team, home_rating_before, home_rating_after)
        self._track_team_history(away_team, away_rating_before, away_rating_after)

    def _validate_and_normalize_args(
        self,
        home_team: str,
        away_team: str,
        home_won: Union[bool, float, None],
        kwargs: dict,
    ) -> Union[bool, float]:
        """Validate arguments and normalize home_won value."""
        # Alias home_win
        if home_won is None and "home_win" in kwargs:
            home_won = kwargs["home_win"]
        elif home_won is None:
            raise ValueError("Must provide home_won")

        if home_team == away_team:
            raise ValueError("Home and away teams cannot be the same")

        return home_won

    def _calculate_elo_update(
        self, params: EloUpdateParams
    ) -> tuple[float, float, float, float]:
        """Calculate Elo rating update."""
        # Apply home advantage for calculation
        calc_home_rating = params.home_rating_before
        if not params.is_neutral:
            calc_home_rating += self.config.home_advantage

        # Calculate expected score
        expected_home = self.expected_score(calc_home_rating, params.away_rating_before)

        # Convert home_won to actual score (1.0 for home win, 0.0 for away win)
        actual_home = 1.0 if params.home_won else 0.0

        # Calculate rating change
        change = self._calculate_rating_change(expected_home, actual_home)

        # Calculate new ratings
        home_rating_after = params.home_rating_before + change
        away_rating_after = params.away_rating_before - change

        return home_rating_after, away_rating_after, change, expected_home

    def _record_game_history(self, params: GameHistoryParams) -> None:
        """Record game history entry."""
        self.game_history.append(
            {
                "home_team": params.home_team,
                "away_team": params.away_team,
                "home_won": bool(params.home_won),
                "home_rating_before": params.home_rating_before,
                "away_rating_before": params.away_rating_before,
                "home_rating_after": params.home_rating_after,
                "away_rating_after": params.away_rating_after,
                "rating_change": params.change,
                "expected_home": params.expected_home,
            }
        )

    def _track_team_history(
        self, team: str, rating_before: float, rating_after: float
    ) -> None:
        """Track team rating history."""
        if team not in self.team_history:
            self.team_history[team] = []
        self.team_history[team].append(
            {"rating_before": rating_before, "rating_after": rating_after}
        )

    def _calculate_rating_change(
        self, expected_score: float, actual_score: float
    ) -> float:
        """
        Calculate the rating change based on expected vs actual score.

        Args:
            expected_score: Expected probability of winning
            actual_score: Actual result (1.0 for win, 0.0 for loss)

        Returns:
            Rating change value
        """
        return self.config.k_factor * (actual_score - expected_score)

    def apply_season_reversion(self, reversion_factor: float = 0.33) -> None:
        """
        Apply season reversion to all ratings.

        Regresses all ratings toward the mean to account for roster changes
        and uncertainty heading into a new season.

        Args:
            reversion_factor: How much to revert toward mean (0.33 = 1/3 reversion)
        """
        if not self.ratings:
            return

        mean_rating = sum(self.ratings.values()) / len(self.ratings)
        for team in self.ratings:
            self.ratings[team] = (
                self.ratings[team] * (1 - reversion_factor)
                + mean_rating * reversion_factor
            )

    def get_team_history(self, team: str) -> list:
        """
        Get the rating history for a specific team.

        Args:
            team: Team name

        Returns:
            List of rating records for the team
        """
        return self.team_history.get(team, [])

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert current ratings to a pandas DataFrame.

        Returns:
            DataFrame with team names and ratings
        """
        return pd.DataFrame(
            [
                {"team": team, "rating": rating}
                for team, rating in sorted(
                    self.ratings.items(), key=lambda x: x[1], reverse=True
                )
            ]
        )
