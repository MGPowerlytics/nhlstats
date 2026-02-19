"""
CBA Elo Rating System - Chinese Basketball Association

Production-ready Elo rating system for CBA predictions.
Inherits from BaseEloRating for unified interface.
"""

from plugins.elo.base_elo_rating import BaseEloRating
from typing import Dict, Union
import pandas as pd


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
        self.game_history = []
        self.team_history: Dict[str, list] = {}

    def get_rating(self, team: str) -> float:
        """
        Get current Elo rating for a team.

        Args:
            team: Team name

        Returns:
            Current Elo rating
        """
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score (probability of team A winning).

        Args:
            rating_a: Elo rating of team A
            rating_b: Elo rating of team B

        Returns:
            Probability (0.0 to 1.0) of team A winning
        """
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def predict(
        self, home_team: str, away_team: str, is_neutral: bool = False
    ) -> float:
        """
        Predict probability of home team winning.

        Args:
            home_team: Home team name
            away_team: Away team name
            is_neutral: Whether the game is at a neutral site

        Returns:
            Probability (0.0 to 1.0) of home team winning
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        if not is_neutral:
            home_rating += self.home_advantage

        return self.expected_score(home_rating, away_rating)

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
        # Alias home_win
        if home_won is None and "home_win" in kwargs:
            home_won = kwargs["home_win"]
        elif home_won is None:
            raise ValueError("Must provide home_won")

        if home_team == away_team:
            raise ValueError("Home and away teams cannot be the same")

        # Get current ratings
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home advantage for calculation
        calc_home_rating = home_rating
        if not is_neutral:
            calc_home_rating += self.home_advantage

        # Calculate expected score
        expected_home = self.expected_score(calc_home_rating, away_rating)

        # Convert home_won to actual score (1.0 for home win, 0.0 for away win)
        actual_home = 1.0 if home_won else 0.0

        # Calculate rating change
        change = self._calculate_rating_change(expected_home, actual_home)

        # Apply changes
        self.ratings[home_team] = home_rating + change
        self.ratings[away_team] = away_rating - change

        # Record game history
        self.game_history.append(
            {
                "home_team": home_team,
                "away_team": away_team,
                "home_won": bool(home_won),
                "home_rating_before": home_rating,
                "away_rating_before": away_rating,
                "home_rating_after": self.ratings[home_team],
                "away_rating_after": self.ratings[away_team],
                "rating_change": change,
                "expected_home": expected_home,
            }
        )

        # Track team history
        for team, before, after in [
            (home_team, home_rating, self.ratings[home_team]),
            (away_team, away_rating, self.ratings[away_team]),
        ]:
            if team not in self.team_history:
                self.team_history[team] = []
            self.team_history[team].append(
                {"rating_before": before, "rating_after": after}
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
        return self.k_factor * (actual_score - expected_score)

    def get_all_ratings(self) -> Dict[str, float]:
        """
        Get all current ratings.

        Returns:
            Dictionary mapping team names to ratings
        """
        return dict(self.ratings)

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
