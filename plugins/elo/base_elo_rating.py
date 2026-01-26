"""
BaseEloRating - Abstract base class for all sport-specific Elo rating systems.

This provides a unified interface for Elo rating calculations across all sports.
All sport-specific Elo classes should inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Union


class BaseEloRating(ABC):
    """
    Abstract base class for Elo rating systems.

    All sport-specific Elo implementations must inherit from this class
    and implement all abstract methods.
    """

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 100.0,
        initial_rating: float = 1500.0,
    ) -> None:
        """
        Initialize Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default 20.0)
            home_advantage: Home advantage in Elo points (default 100.0)
            initial_rating: Initial rating for new teams/players (default 1500.0)
        """
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings: Dict[str, float] = {}

    @abstractmethod
    def predict(
        self, home_team: str, away_team: str, is_neutral: bool = False
    ) -> float:
        """
        Predict probability of home team winning.

        Args:
            home_team: Name of home team/player
            away_team: Name of away team/player
            is_neutral: Whether the game is at a neutral site

        Returns:
            Probability (0.0 to 1.0) of home team winning
        """
        pass

    @abstractmethod
    def update(
        self,
        home_team: str,
        away_team: str,
        home_won: Union[bool, float],
        is_neutral: bool = False,
        **kwargs,
    ) -> None:
        """
        Update Elo ratings after a game result.

        Args:
            home_team: Name of home team/player
            away_team: Name of away team/player
            home_won: True/1.0 if home team won, False/0.0 if away team won
            is_neutral: Whether the game was at a neutral site
            **kwargs: Additional arguments
        """
        pass

    def legacy_update(
        self,
        home_team: str,
        away_team: str,
        home_won: Union[bool, float] = None,
        **kwargs,
    ) -> None:
        """
        Legacy update method for backward compatibility.
        """
        self.update(home_team, away_team, home_won, **kwargs)

    # Alias for backward compatibility
    update_legacy = legacy_update

    def update_with_scores(
        self,
        home_team: str,
        away_team: str,
        home_score: float,
        away_score: float,
        **kwargs,
    ) -> None:
        """
        Update with scores (backward compatibility).
        """
        # Determine winner from scores
        home_won = home_score > away_score
        self.update(
            home_team,
            away_team,
            home_won,
            home_score=home_score,
            away_score=away_score,
            **kwargs,
        )

    @abstractmethod
    def get_rating(self, team: str) -> float:
        """
        Get current Elo rating for a team/player.

        Args:
            team: Name of team/player

        Returns:
            Current Elo rating
        """
        pass

    @abstractmethod
    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score (probability of team A winning).

        Args:
            rating_a: Elo rating of team A
            rating_b: Elo rating of team B

        Returns:
            Probability (0.0 to 1.0) of team A winning
        """
        pass

    @abstractmethod
    def get_all_ratings(self) -> Dict[str, float]:
        """
        Get all current ratings.

        Returns:
            Dictionary mapping team/player names to their current ratings
        """
        pass

    def _apply_home_advantage(
        self, home_rating: float, is_neutral: bool = False
    ) -> float:
        """
        Apply home advantage to rating.

        Args:
            home_rating: Home team's base rating
            is_neutral: Whether the game is at a neutral site

        Returns:
            Home team's rating with home advantage applied
        """
        if is_neutral:
            return home_rating
        return home_rating + self.home_advantage

    def _calculate_rating_change(
        self, expected: float, actual: float, k_factor: Optional[float] = None
    ) -> float:
        """
        Calculate rating change based on expected vs actual result.

        Args:
            expected: Expected score (probability of winning)
            actual: Actual result (1.0 for win, 0.0 for loss)
            k_factor: Optional K-factor override

        Returns:
            Rating change (positive for winner, negative for loser)
        """
        if k_factor is None:
            k_factor = self.k_factor
        return k_factor * (actual - expected)
