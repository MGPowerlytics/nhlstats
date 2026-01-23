"""
NBA Elo Rating System

Production-ready Elo rating system for NBA predictions.
Inherits from BaseEloRating for unified interface.
"""

from .base_elo_rating import BaseEloRating
from typing import Dict, Optional, Union
import json
from pathlib import Path
import pandas as pd
import numpy as np


class NBAEloRating(BaseEloRating):
    """
    NBA-specific Elo rating system.

    Features:
    - Standard Elo with K=20, home advantage=100
    - Margin of victory adjustment
    - Season-to-season regression
    - Game history tracking
    """

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 100.0,
        initial_rating: float = 1500.0
    ) -> None:
        """
        Initialize NBA Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default 20.0)
            home_advantage: Home advantage in Elo points (default 100.0)
            initial_rating: Initial rating for new teams (default 1500.0)
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating
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

        Args:
            home_team: Home team name
            away_team: Away team name
            home_won: True/1.0 if home team won, False/0.0 if away team won
            is_neutral: Whether the game was at a neutral site
            **kwargs: Additional arguments
        """
        # Alias home_win
        if home_won is None and 'home_win' in kwargs:
            home_won = kwargs['home_win']
        elif home_won is None:
             raise ValueError("Must provide home_won")

        if home_team == away_team:
            raise ValueError("Home and away teams cannot be the same")

        # Get current ratings
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home advantage
        if not is_neutral:
            home_rating += self.home_advantage

        # Calculate expected score
        expected_home = self.expected_score(home_rating, away_rating)

        # Convert home_won to actual score (1.0 for home win, 0.0 for away win)
        actual_home = 1.0 if home_won else 0.0

        # Calculate rating change
        change = self._calculate_rating_change(expected_home, actual_home)

        # Apply changes (remove home advantage first)
        if not is_neutral:
            home_rating -= self.home_advantage

        self.ratings[home_team] = home_rating + change
        self.ratings[away_team] = away_rating - change

        # Record game history
        self.game_history.append({
            'home_team': home_team,
            'away_team': away_team,
            'home_won': bool(home_won),
            'home_rating_before': home_rating,
            'away_rating_before': away_rating,
            'change': change
        })

        return change

    def get_all_ratings(self) -> Dict[str, float]:
        """
        Get all current ratings.

        Returns:
            Dictionary mapping team names to their current ratings
        """
        return self.ratings.copy()

    def legacy_update(self, home_team: str, away_team: str, home_won: bool, **kwargs) -> None:
        """
        Legacy update method for backward compatibility.

        Args:
            home_team: Home team name
            away_team: Away team name
            home_won: True if home team won
        """
        self.update(home_team, away_team, home_won, is_neutral=False, **kwargs)

    def evaluate_on_games(self, games: pd.DataFrame) -> Dict[str, Union[float, pd.DataFrame]]:
        """
        Evaluate Elo predictions on historical games.

        Args:
            games: DataFrame with columns ['home_team', 'away_team', 'home_won']

        Returns:
            Dictionary with accuracy metrics and predictions DataFrame
        """
        results = []
        for _, row in games.iterrows():
            pred = self.predict(row['home_team'], row['away_team'])
            results.append({
                'home_team': row['home_team'],
                'away_team': row['away_team'],
                'home_won': row['home_won'],
                'prediction': pred,
                'correct': (pred > 0.5) == row['home_won']
            })

        df = pd.DataFrame(results)
        accuracy = df['correct'].mean() if not df.empty else 0.0

        auc = 0.5
        if not df.empty and 'prediction' in df.columns and 'home_won' in df.columns:
            try:
                from sklearn.metrics import roc_auc_score
                # Ensure we have both classes
                if len(df['home_won'].unique()) > 1:
                    auc = roc_auc_score(df['home_won'].astype(int), df['prediction'])
            except ImportError:
                pass
            except Exception:
                pass

        return {
            'accuracy': accuracy,
            'auc': auc,
            'actuals': df['home_won'] if not df.empty else [],
            'predictions': df
        }
