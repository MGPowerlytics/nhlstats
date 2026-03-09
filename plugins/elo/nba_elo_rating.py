"""
NBA Elo Rating System

Production-ready Elo rating system for NBA predictions.
Inherits from BaseEloRating for unified interface.
"""

from plugins.elo.base_elo_rating import BaseEloRating, Matchup, GameResult
from typing import Dict, Union, Optional
import pandas as pd


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
        initial_rating: float = 1500.0,
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
            initial_rating=initial_rating,
        )

    def update(
        self,
        home_team: str,
        away_team: str,
        home_won: Union[bool, float] = None,
        is_neutral: bool = False,
        **kwargs,
    ) -> float:
        """
        Update Elo ratings after a game result with history tracking.

        Args:
            home_team: Home team name
            away_team: Away team name
            home_won: True/1.0 if home team won, False/0.0 if away team won
            is_neutral: Whether the game was at a neutral site
            **kwargs: Additional arguments
        """
        # Save ratings before update
        home_rating_before = self.get_rating(home_team)
        away_rating_before = self.get_rating(away_team)

        # Use base update for actual calculation
        change = super().update(
            home_team=home_team,
            away_team=away_team,
            home_won=home_won,
            is_neutral=is_neutral,
            **kwargs,
        )

        # Record game history
        self.game_history.append(
            {
                "home_team": home_team,
                "away_team": away_team,
                "home_won": bool(home_won),
                "home_rating_before": home_rating_before,
                "away_rating_before": away_rating_before,
                "change": change,
            }
        )

        return change

    def evaluate_on_games(
        self, games: pd.DataFrame
    ) -> Dict[str, Union[float, pd.DataFrame]]:
        """
        Evaluate Elo predictions on historical games.

        Args:
            games: DataFrame with columns ['home_team', 'away_team', 'home_won']

        Returns:
            Dictionary with accuracy metrics and predictions DataFrame
        """
        results = []
        for _, row in games.iterrows():
            pred = self.predict(row["home_team"], row["away_team"])
            results.append(
                {
                    "home_team": row["home_team"],
                    "away_team": row["away_team"],
                    "home_won": row["home_won"],
                    "prediction": pred,
                    "correct": (pred > 0.5) == row["home_won"],
                }
            )

        df = pd.DataFrame(results)
        accuracy = df["correct"].mean() if not df.empty else 0.0

        auc = 0.5
        if not df.empty and "prediction" in df.columns and "home_won" in df.columns:
            try:
                from sklearn.metrics import roc_auc_score

                # Ensure we have both classes
                if len(df["home_won"].unique()) > 1:
                    auc = roc_auc_score(df["home_won"].astype(int), df["prediction"])
            except ImportError:
                pass
            except Exception:
                pass

        return {
            "accuracy": accuracy,
            "auc": auc,
            "actuals": df["home_won"] if not df.empty else [],
            "predictions": df,
        }
