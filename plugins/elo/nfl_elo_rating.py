"""
NFL Elo Rating System

Production-ready Elo rating system for NFL predictions.
Inherits from BaseEloRating for unified interface.
"""

from .base_elo_rating import BaseEloRating
from typing import Dict, Union
import math


class NFLEloRating(BaseEloRating):
    """NFL-specific Elo rating system."""

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 65.0,
        initial_rating: float = 1500.0
    ) -> None:
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating
        )

    def get_rating(self, team: str) -> float:
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def predict(self, home_team: str, away_team: str, is_neutral: bool = False) -> float:
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
        **kwargs
    ) -> None:
        # Handle kwargs for backward compatibility
        home_score = kwargs.get('home_score')
        away_score = kwargs.get('away_score')

        real_home_won = home_won
        real_is_neutral = is_neutral

        if home_score is None and away_score is None:
            # Check positional args
            if isinstance(home_won, (int, float)) and isinstance(is_neutral, (int, float)):
                if home_won > 1 or is_neutral > 1:
                    home_score = home_won
                    away_score = is_neutral
                    real_home_won = None
                    real_is_neutral = False

        # If home_won not provided, determine from scores
        if real_home_won is None and home_score is not None and away_score is not None:
            real_home_won = home_score > away_score
        elif real_home_won is None:
             if 'home_win' in kwargs:
                real_home_won = kwargs['home_win']
             else:
                raise ValueError("Must provide home_won or scores")

        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        if not real_is_neutral:
            home_rating += self.home_advantage

        expected_home = self.expected_score(home_rating, away_rating)
        actual_home = 1.0 if real_home_won else 0.0
        change = self._calculate_rating_change(expected_home, actual_home)

        # Simple MOV multiplier if scores provided
        import math
        if home_score is not None and away_score is not None:
            mov = abs(home_score - away_score)
            mov_multiplier = math.log(max(mov, 1) + 1.0) * (2.2 / ((0.001 * (home_rating - away_rating)) + 2.2))
            change *= mov_multiplier

        if not real_is_neutral:
            home_rating -= self.home_advantage

        self.ratings[home_team] = home_rating + change
        self.ratings[away_team] = away_rating - change

    def get_all_ratings(self) -> Dict[str, float]:
        return self.ratings.copy()

    def legacy_update(self, home_team: str, away_team: str, home_won: bool = None, **kwargs) -> None:
        self.update(home_team, away_team, home_won, is_neutral=False, **kwargs)
