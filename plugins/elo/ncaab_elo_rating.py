"""
NCAAB Elo Rating System

Production-ready Elo rating system for NCAA Basketball predictions.
Inherits from BaseEloRating for unified interface.
"""

from plugins.elo.base_elo_rating import BaseEloRating
from typing import Dict, Union


class NCAABEloRating(BaseEloRating):
    """NCAAB-specific Elo rating system."""

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 100.0,
        initial_rating: float = 1500.0,
    ) -> None:
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating,
        )

    def get_rating(self, team: str) -> float:
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def predict(
        self, home_team: str, away_team: str, is_neutral: bool = False
    ) -> float:
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
        home_win: Union[bool, float] = None,
        **kwargs,
    ) -> None:
        # Handle aliasing
        if home_won is None and home_win is not None:
            home_won = home_win
        elif home_won is None and "home_win" in kwargs:
            home_won = kwargs["home_win"]
        elif home_won is None:
            raise ValueError("Must provide home_won")

        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        if not is_neutral:
            home_rating += self.home_advantage

        expected_home = self.expected_score(home_rating, away_rating)
        actual_home = 1.0 if home_won else 0.0
        change = self._calculate_rating_change(expected_home, actual_home)

        if not is_neutral:
            home_rating -= self.home_advantage

        self.ratings[home_team] = home_rating + change
        self.ratings[away_team] = away_rating - change

        return change

    def get_all_ratings(self) -> Dict[str, float]:
        return self.ratings.copy()

    def legacy_update(
        self, home_team: str, away_team: str, home_won: bool = None, **kwargs
    ) -> None:
        self.update(home_team, away_team, home_won, is_neutral=False, **kwargs)
