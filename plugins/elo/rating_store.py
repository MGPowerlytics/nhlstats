"""
RatingStore - Manages storage and retrieval of Elo ratings.

This class handles the persistence and retrieval of Elo ratings,
separating storage concerns from calculation logic.
"""

from typing import Dict, Optional

from plugins.elo.elo_dataclasses import EloConfig
from plugins.utils import DictStoreMixin


class RatingStore(DictStoreMixin):
    """
    Manages storage and retrieval of Elo ratings.

    This class follows the Single Responsibility Principle by focusing
    solely on rating storage operations.
    """

    def __init__(self, config: Optional[EloConfig] = None):
        """
        Initialize rating store.

        Args:
            config: EloConfig object with initial rating parameter
        """
        if not config:
            config = EloConfig()
        self.config = config
        self.ratings: Dict[str, float] = {}

    def get_rating(self, team: str) -> float:
        """
        Get current Elo rating for a team/player.

        Args:
            team: Name of team/player

        Returns:
            Current Elo rating
        """
        if team not in self.ratings:
            self.ratings[team] = self.config.initial_rating
        return self.ratings[team]

    def set_rating(self, team: str, rating: float) -> None:
        """
        Set Elo rating for a team/player.

        Uses the generic store_in_dict() method from DictStoreMixin
        to eliminate code duplication while maintaining domain-specific
        naming and type hints.

        Args:
            team: Name of team/player
            rating: New Elo rating

        Raises:
            TypeError: If rating is not numeric
            ValueError: If rating is negative or team name is empty
        """
        if not isinstance(rating, (int, float)):
            raise TypeError(f"Rating must be numeric, got {type(rating).__name__}")
        if rating < 0:
            raise ValueError(f"Rating cannot be negative: {rating}")
        if not team:
            raise ValueError("Team name cannot be empty")
        self.store_in_dict("ratings", team, rating)

    def update_rating(self, team: str, delta: float) -> float:
        """
        Update Elo rating by adding delta.

        Args:
            team: Name of team/player
            delta: Change to apply to rating

        Returns:
            New rating after update
        """
        current = self.get_rating(team)
        new_rating = current + delta
        self.set_rating(team, new_rating)
        return new_rating

    def get_all_ratings(self) -> Dict[str, float]:
        """
        Get all current ratings.

        Returns:
            Dictionary mapping team/player names to their current ratings
        """
        return dict(self.ratings)

    def clear_ratings(self) -> None:
        """Clear all ratings from store."""
        self.ratings.clear()

    def has_rating(self, team: str) -> bool:
        """
        Check if a team has a rating stored.

        Args:
            team: Name of team/player

        Returns:
            True if rating exists, False otherwise
        """
        return team in self.ratings

    def get_rating_or_default(self, team: str, default: float) -> float:
        """
        Get rating or return default if not found.

        Args:
            team: Name of team/player
            default: Default rating to return if team not found

        Returns:
            Team rating or default
        """
        return self.ratings.get(team, default)
