"""
EloCalculator - Pure mathematical Elo rating calculations.

This class contains only the mathematical formulas for Elo calculations,
with no state or side effects. It follows the Single Responsibility Principle
by focusing solely on calculations.
"""

import math
from typing import Optional

from plugins.elo.elo_dataclasses import (
    GameResult,
    EloConfig,
    ELO_RATING_SCALE,
    ELO_EXPONENT_BASE,
    MOV_MULTIPLIER_CONSTANT,
    MOV_ELO_SCALING_FACTOR,
    MOV_MINIMUM_VALUE,
    MOV_LOG_OFFSET,
)


class EloCalculator:
    """
    Pure mathematical Elo rating calculations.

    This class contains only stateless mathematical operations for Elo calculations.
    It follows the Single Responsibility Principle and can be used by any Elo system.
    """

    def __init__(self, config: Optional[EloConfig] = None):
        """
        Initialize Elo calculator with configuration.

        Args:
            config: EloConfig object with calculation parameters
        """
        if not config:
            config = EloConfig()
        self.config = config

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score (probability of team A winning).

        Args:
            rating_a: Elo rating of team A
            rating_b: Elo rating of team B

        Returns:
            Probability (0.0 to 1.0) of team A winning
        """
        return 1.0 / (
            1.0 + ELO_EXPONENT_BASE ** ((rating_b - rating_a) / ELO_RATING_SCALE)
        )

    def apply_home_advantage(
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
        return home_rating + self.config.home_advantage

    def calculate_rating_change(
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
            k_factor = self.config.k_factor
        return k_factor * (actual - expected)

    def calculate_mov_multiplier(self, result: GameResult, elo_diff: float) -> float:
        """
        Calculate Margin of Victory (MOV) multiplier.
        Used primarily for NFL and MLB to account for blowout wins.

        Args:
            result: GameResult containing scores
            elo_diff: Difference in Elo ratings (home_rating - away_rating)

        Returns:
            Multiplier to apply to the rating change
        """
        if result.home_score is None or result.away_score is None:
            return 1.0

        mov = abs(result.home_score - result.away_score)
        # Standard formula from FiveThirtyEight
        # multiplier = log(mov + 1) * (MOV_MULTIPLIER_CONSTANT / (elo_diff * MOV_ELO_SCALING_FACTOR + MOV_MULTIPLIER_CONSTANT))
        multiplier = math.log(max(mov, MOV_MINIMUM_VALUE) + MOV_LOG_OFFSET) * (
            MOV_MULTIPLIER_CONSTANT
            / ((MOV_ELO_SCALING_FACTOR * elo_diff) + MOV_MULTIPLIER_CONSTANT)
        )
        return multiplier

    def calculate_expected_home_win_probability(
        self, home_rating: float, away_rating: float, is_neutral: bool = False
    ) -> float:
        """
        Calculate probability of home team winning.

        Args:
            home_rating: Home team's base rating
            away_rating: Away team's rating
            is_neutral: Whether the game is at a neutral site

        Returns:
            Probability (0.0 to 1.0) of home team winning
        """
        adjusted_home_rating = self.apply_home_advantage(home_rating, is_neutral)
        return self.expected_score(adjusted_home_rating, away_rating)
