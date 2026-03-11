"""
EloDataclasses - Common dataclasses used across the Elo system.

This module contains all the shared dataclasses to avoid circular dependencies
and provide a single source of truth for data structures.
"""

from typing import Optional, Union
from dataclasses import dataclass
from datetime import datetime


# Elo system constants - fundamental parameters that affect all predictions
# These values are standard in Elo rating systems and can be tuned per sport
DEFAULT_K_FACTOR: float = 20.0  # How quickly ratings adjust to new results
DEFAULT_HOME_ADVANTAGE: float = 100.0  # Elo points advantage for home team
DEFAULT_INITIAL_RATING: float = 1500.0  # Starting rating for new teams/players

# Mathematical constants for Elo probability calculation
ELO_RATING_SCALE: float = 400.0  # Standard Elo rating scale factor
ELO_EXPONENT_BASE: float = 10.0  # Base for exponent in Elo probability formula

# Margin of Victory (MOV) multiplier constants (from FiveThirtyEight formula)
MOV_MULTIPLIER_CONSTANT: float = 2.2  # Constant in MOV multiplier denominator
MOV_ELO_SCALING_FACTOR: float = (
    0.001  # Scaling factor for Elo difference in MOV formula
)
MOV_MINIMUM_VALUE: int = 1  # Minimum MOV value to avoid log(0) in calculation
MOV_LOG_OFFSET: float = 1.0  # Offset in log(mov + 1) formula


@dataclass
class Matchup:
    """Represents a matchup between two teams/players."""

    home_team: str
    away_team: str
    is_neutral: bool = False
    game_date: Optional[datetime] = None


@dataclass
class GameScores:
    """Represents game scores for backward compatibility updates."""

    home_score: float
    away_score: float

    @property
    def home_won(self) -> bool:
        """Determine if home team won based on scores."""
        return self.home_score > self.away_score


@dataclass
class GameResult:
    """Represents the result of a game for Elo updates."""

    home_won: Union[bool, float]
    home_score: Optional[float] = None
    away_score: Optional[float] = None


@dataclass
class EloConfig:
    """Configuration parameters for an Elo rating system."""

    k_factor: float = DEFAULT_K_FACTOR
    home_advantage: float = DEFAULT_HOME_ADVANTAGE
    initial_rating: float = DEFAULT_INITIAL_RATING


@dataclass
class UpdateArgs:
    """Encapsulates all possible arguments for Elo update methods.

    This class eliminates feature envy by providing a clean interface
    for passing update arguments instead of using **kwargs.
    """

    home_team: Optional[Union[Matchup, str]] = None
    away_team: Optional[Union[GameResult, str, bool, float]] = None
    home_won: Optional[Union[bool, float]] = None
    is_neutral: bool = False
    matchup: Optional[Matchup] = None
    result: Optional[GameResult] = None
    home_score: Optional[float] = None
    away_score: Optional[float] = None
    home_win: Optional[Union[bool, float]] = None

    @classmethod
    def from_kwargs(cls, **kwargs) -> "UpdateArgs":
        """Create UpdateArgs from keyword arguments."""
        return cls(**kwargs)

    def extract_matchup_info(self) -> tuple[str, str, bool]:
        """
        Extract home team, away team, and is_neutral from UpdateArgs.

        Returns:
            Tuple of (home_team_str, away_team_str, is_neutral)

        Raises:
            ValueError: If UpdateArgs doesn't contain valid team information
        """
        # Extract from Matchup object if present
        if self.matchup is not None:
            return (
                self.matchup.home_team,
                self.matchup.away_team,
                self.matchup.is_neutral,
            )

        # Extract from home_team/away_team strings if present
        if isinstance(self.home_team, str):
            home_team_str = self.home_team
            away_team_str = self.away_team if isinstance(self.away_team, str) else ""
            return (home_team_str, away_team_str, self.is_neutral)

        raise ValueError(
            "UpdateArgs must contain either home_team/away_team strings or a Matchup object"
        )

    def extract_score_info(self) -> tuple[float, float]:
        """
        Extract home score and away score from UpdateArgs.

        Returns:
            Tuple of (home_score_val, away_score_val)

        Raises:
            ValueError: If UpdateArgs doesn't contain valid score information
        """
        # Extract from direct score fields if present
        if self.home_score is not None and self.away_score is not None:
            return (self.home_score, self.away_score)

        # Extract from GameResult if present
        if self.result is not None:
            home_score_val = self.result.home_score or 0.0
            away_score_val = self.result.away_score or 0.0
            return (home_score_val, away_score_val)

        raise ValueError("UpdateArgs must contain scores")
