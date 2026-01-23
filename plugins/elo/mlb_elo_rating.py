"""
MLB Elo Rating System

Production-ready Elo rating system for MLB predictions.
Inherits from BaseEloRating for unified interface.
"""

from .base_elo_rating import BaseEloRating
from typing import Dict, Optional, Union
import json
from pathlib import Path
import pandas as pd
import numpy as np
import math


class MLBEloRating(BaseEloRating):
    """
    MLB-specific Elo rating system.

    Features:
    - Standard Elo with K=20, home advantage=50
    - Lower home advantage than other sports
    - Game history tracking
    """

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 50.0,
        initial_rating: float = 1500.0
    ) -> None:
        """
        Initialize MLB Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default 20.0)
            home_advantage: Home advantage in Elo points (default 50.0)
            initial_rating: Initial rating for new teams (default 1500.0)
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating
        )
        self.game_history = []

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

    def predict(self, home_team: str, away_team: str, is_neutral: bool = False) -> float:
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
        **kwargs
    ) -> None:
        """
        Update Elo ratings after a game result.
        """
        # Handle positional args for scores (legacy support)
        # Check if home_won is actually home_score (int/float > 1 usually, or if is_neutral is a score)
        home_score = kwargs.get('home_score')
        away_score = kwargs.get('away_score')

        real_home_won = home_won
        real_is_neutral = is_neutral

        if home_score is None and away_score is None:
            # Check if home_won and is_neutral look like scores
            if isinstance(home_won, (int, float)) and isinstance(is_neutral, (int, float)):
                # Heuristic: if both are numbers and not booleans (bool is int, but we can check)
                # If is_neutral is a number > 1 (unlikely for boolean flag which is 0/1), it's likely away_score
                # Or if home_won is > 1.
                if home_won > 1 or is_neutral > 1:
                    home_score = home_won
                    away_score = is_neutral
                    real_home_won = None
                    real_is_neutral = False # Default

        # If home_won not provided, determine from scores
        if real_home_won is None and home_score is not None and away_score is not None:
            real_home_won = home_score > away_score
        elif real_home_won is None:
            # Check for legacy alias
            if 'home_win' in kwargs:
                real_home_won = kwargs['home_win']
            else:
                raise ValueError("Must provide home_won or scores")

        # Get current ratings
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home advantage
        if not real_is_neutral:
            home_rating += self.home_advantage

        # Calculate expected score
        expected_home = self.expected_score(home_rating, away_rating)

        # Convert home_won to actual score
        actual_home = 1.0 if real_home_won else 0.0

        # Calculate rating change
        change = self._calculate_rating_change(expected_home, actual_home)

        # Simple MOV multiplier if scores provided
        if home_score is not None and away_score is not None:
            mov = abs(home_score - away_score)
            mov_multiplier = math.log(max(mov, 1) + 1.0) * (2.2 / ((0.001 * (home_rating - away_rating)) + 2.2))
            change *= mov_multiplier

        # Apply changes (remove home advantage first)
        if not real_is_neutral:
            home_rating -= self.home_advantage

        self.ratings[home_team] = home_rating + change
        self.ratings[away_team] = away_rating - change

        # Record game history
        self.game_history.append({
            'home_team': home_team,
            'away_team': away_team,
            'home_won': bool(real_home_won),
            'home_score': home_score,
            'away_score': away_score,
            'home_rating_before': home_rating,
            'away_rating_before': away_rating,
            'change': change
        })

    def get_all_ratings(self) -> Dict[str, float]:
        """
        Get all current ratings.

        Returns:
            Dictionary mapping team names to their current ratings
        """
        return self.ratings.copy()

    def legacy_update(self, home_team: str, away_team: str, home_won: bool = None, **kwargs) -> None:
        """
        Legacy update method for backward compatibility.

        Args:
            home_team: Home team name
            away_team: Away team name
            home_won: True if home team won
            **kwargs: Additional args like scores
        """
        self.update(home_team, away_team, home_won, is_neutral=False, **kwargs)
