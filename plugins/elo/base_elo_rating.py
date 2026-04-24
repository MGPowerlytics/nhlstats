"""
BaseEloRating - Abstract base class for all sport-specific Elo rating systems.

This provides a unified interface for Elo rating calculations across all sports.
All sport-specific Elo classes should inherit from this base class.

Refactored version (2026-03-05): Extracted responsibilities to separate classes:
- EloCalculator: Pure mathematical calculations
- ArgumentParser: Argument parsing and validation
- RatingStore: Rating storage and retrieval
- BaseEloRating: Abstract interface and coordination
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Union, List, Any

# Import from shared dataclasses module to avoid circular dependencies
from plugins.elo.elo_dataclasses import (
    Matchup,
    GameResult,
    EloConfig,
    GameScores,
    UpdateArgs,
)
from plugins.elo.elo_calculator import EloCalculator
from plugins.elo.argument_parser import ArgumentParser
from plugins.elo.rating_store import RatingStore


class BaseEloRating(ABC):
    """
    Abstract base class for Elo rating systems.

    All sport-specific Elo implementations must inherit from this class
    and implement all abstract methods.

    This refactored version delegates responsibilities to specialized classes:
    - EloCalculator: Mathematical calculations
    - ArgumentParser: Argument parsing
    - RatingStore: Rating storage
    """

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 100.0,
        initial_rating: float = 1500.0,
        config: Optional[EloConfig] = None,
    ) -> None:
        """
        Initialize Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default: 20.0)
            home_advantage: Home advantage in Elo points (default: 100.0)
            initial_rating: Initial rating for new teams/players (default: 1500.0)
            config: Optional EloConfig object (takes precedence over individual params)

        Note: For better code organization, prefer using EloConfig dataclass.
        """
        # Ensure we have an EloConfig object
        if not config:
            config = EloConfig(
                k_factor=k_factor,
                home_advantage=home_advantage,
                initial_rating=initial_rating,
            )

        # Initialize specialized components
        self.config = config
        self.calculator = EloCalculator(config)
        self.parser = ArgumentParser()
        self.store = RatingStore(config)

        # Initialize history tracking (used by some sports for analytics)
        self.game_history: List[Dict[str, Any]] = []
        self.team_history: Dict[str, List[Dict[str, Any]]] = {}

    @classmethod
    def from_config(cls, config: EloConfig) -> "BaseEloRating":
        """
        Create an Elo rating system from an EloConfig object.

        This is the preferred way to initialize when you have configuration
        parameters that are used together.

        Args:
            config: EloConfig object with all configuration parameters

        Returns:
            New Elo rating system instance
        """
        return cls(config=config)

    @property
    def k_factor(self) -> float:
        """Get K-factor for rating updates (backward compatibility)."""
        return self.config.k_factor

    @property
    def home_advantage(self) -> float:
        """Get home advantage in Elo points (backward compatibility)."""
        return self.config.home_advantage

    @property
    def initial_rating(self) -> float:
        """Get initial rating for new teams/players (backward compatibility)."""
        return self.config.initial_rating

    @property
    def ratings(self) -> Dict[str, float]:
        """Get all ratings dictionary (backward compatibility)."""
        return self.store.ratings

    @ratings.setter
    def ratings(self, value: Dict[str, float]) -> None:
        """Set all ratings (backward compatibility)."""
        self.store.ratings.clear()
        self.store.ratings.update(value)

    def set_rating(self, team: str, rating: float) -> None:
        """Set rating for a team/player (backward compatibility)."""
        self.store.set_rating(team, rating)

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
        home_rating = self.store.get_rating(home_team)
        away_rating = self.store.get_rating(away_team)

        return self.calculator.calculate_expected_home_win_probability(
            home_rating, away_rating, is_neutral
        )

    @abstractmethod
    def update(
        self,
        home_team: Optional[Union[Matchup, str]] = None,
        away_team: Optional[Union[GameResult, str, bool, float]] = None,
        home_won: Optional[Union[bool, float]] = None,
        **kwargs,
    ) -> Optional[float]:
        """
        Update Elo ratings after a game result.

        This method should be overridden by subclasses to provide specific
        Elo update logic. They can call _update_ratings_base for standard math.
        """
        parsed = self.parser.parse_update_args(
            home_team=home_team, away_team=away_team, home_won=home_won, **kwargs
        )
        return self._update_ratings_base(parsed.matchup, parsed.result)

    def _update_ratings_base(self, matchup: Matchup, result: GameResult) -> float:
        """
        Core Elo rating update logic shared across all sports.

        Args:
            matchup: Matchup object
            result: GameResult object

        Returns:
            Rating change (positive for home win, negative for away win)
        """
        home_team = matchup.home_team
        away_team = matchup.away_team
        is_neutral = matchup.is_neutral
        home_won = result.home_won

        # Validate that teams are different
        if home_team == away_team:
            raise ValueError(f"Home and away teams cannot be the same: {home_team}")

        # Get current ratings
        home_rating = self.store.get_rating(home_team)
        away_rating = self.store.get_rating(away_team)

        # Apply home advantage
        if not is_neutral:
            home_rating += self.config.home_advantage

        # Calculate expected score
        expected_home = self.calculator.expected_score(home_rating, away_rating)

        # Convert home_won to actual score
        actual_home = 1.0 if home_won else 0.0

        # Calculate rating change
        change = self.calculator.calculate_rating_change(expected_home, actual_home)

        # Apply changes (remove home advantage first)
        if not is_neutral:
            home_rating -= self.config.home_advantage

        self.store.update_rating(home_team, change)
        self.store.update_rating(away_team, -change)

        return change

    def legacy_update(
        self,
        home_team: str,
        away_team: str,
        home_won: Optional[Union[bool, float]] = None,
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
        home_team: Optional[Union[str, UpdateArgs]] = None,
        away_team: Optional[str] = None,
        home_score: Optional[float] = None,
        away_score: Optional[float] = None,
        update_args: Optional[UpdateArgs] = None,
        **kwargs,
    ) -> None:
        """
        Update with scores (backward compatibility).

        Supports both primitive parameters (for backward compatibility) and
        UpdateArgs dataclass (for cleaner new code).

        Args:
            home_team: Name of home team (or UpdateArgs object if using dataclass)
            away_team: Name of away team (ignored if home_team is UpdateArgs)
            home_score: Home team score (ignored if home_team is UpdateArgs)
            away_score: Away team score (ignored if home_team is UpdateArgs)
            update_args: UpdateArgs dataclass containing all parameters
            **kwargs: Additional arguments passed to update()
        """
        # Handle UpdateArgs dataclass
        if isinstance(home_team, UpdateArgs):
            update_args = home_team
            # Extract parameters using UpdateArgs methods
            home_team_str, away_team_str, is_neutral = (
                update_args.extract_matchup_info()
            )
            home_score_val, away_score_val = update_args.extract_score_info()
        else:
            # Handle primitive parameters (backward compatibility)
            if (
                home_team is None
                or away_team is None
                or home_score is None
                or away_score is None
            ):
                raise ValueError("Must provide all primitive parameters or UpdateArgs")

            home_team_str = home_team
            away_team_str = away_team
            home_score_val = home_score
            away_score_val = away_score
            is_neutral = kwargs.get("is_neutral", False)

        # Create GameScores and Matchup objects
        scores = GameScores(home_score=home_score_val, away_score=away_score_val)
        matchup = Matchup(
            home_team=home_team_str, away_team=away_team_str, is_neutral=is_neutral
        )

        # Use the overloaded version that accepts dataclasses
        self._update_with_dataclasses(matchup, scores, **kwargs)

    def _update_with_dataclasses(
        self,
        matchup: Matchup,
        scores: GameScores,
        **kwargs,
    ) -> None:
        """
        Update with dataclasses (internal method).

        Args:
            matchup: Matchup object containing home_team, away_team, and is_neutral
            scores: GameScores object containing home_score and away_score
            **kwargs: Additional arguments passed to update()
        """
        # Create GameResult object from scores
        result = GameResult(
            home_won=scores.home_won,
            home_score=scores.home_score,
            away_score=scores.away_score,
        )

        # Use the unified update method with dataclasses
        self.update(matchup=matchup, result=result, **kwargs)

    def get_rating(self, team: str) -> float:
        """
        Get current Elo rating for a team/player.

        Args:
            team: Name of team/player

        Returns:
            Current Elo rating
        """
        return self.store.get_rating(team)

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score (probability of team A winning).

        Args:
            rating_a: Elo rating of team A
            rating_b: Elo rating of team B

        Returns:
            Probability (0.0 to 1.0) of team A winning
        """
        return self.calculator.expected_score(rating_a, rating_b)

    def has_real_rating(self, team: str) -> bool:
        """Check if a team has a real (non-default) rating stored.

        This is the safe guard against betting on teams that only have the
        ``initial_rating`` default — i.e. teams the Elo system has never
        processed a game for.  Unlike ``get_rating``, this method does **not**
        insert a default entry into the store.

        Args:
            team: Name of team/player.

        Returns:
            True if the team's rating was computed from at least one game,
            False if the team is unknown to the Elo system.
        """
        return self.store.has_rating(team)

    def get_all_ratings(self) -> Dict[str, float]:
        """
        Get all current ratings.

        Returns:
            Dictionary mapping team/player names to their current ratings
        """
        return self.store.get_all_ratings()


class StandardEloRating(BaseEloRating):
    """
    Standard Elo rating system implementation.
    Concrete subclass of BaseEloRating with the default update behavior.
    """

    def update(
        self,
        home_team: Optional[Union[Matchup, str]] = None,
        away_team: Optional[Union[GameResult, str, bool, float]] = None,
        home_won: Optional[Union[bool, float]] = None,
        **kwargs,
    ) -> Optional[float]:
        """Implement abstract update method by calling super().update()."""
        return super().update(
            home_team=home_team, away_team=away_team, home_won=home_won, **kwargs
        )
