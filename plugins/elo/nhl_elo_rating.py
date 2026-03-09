"""
Production Elo Rating System for NHL Betting

Simple, fast, interpretable alternative to complex ML models.
Performance: 59.3% accuracy, 0.591 AUC (matches XGBoost with 1/30th the complexity)
"""

import json
from pathlib import Path
from datetime import datetime
from plugins.elo.base_elo_rating import BaseEloRating, Matchup, GameResult, EloConfig
from typing import Dict, Optional, Union


class NHLEloRating(BaseEloRating):
    """
    NHL-specific Elo rating system with recency weighting.

    Features:
    - Recency weighting (more recent games matter more)
    - Game history tracking
    - File-based rating persistence
    - Season reversion
    """

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 65.0,
        initial_rating: float = 1500.0,
        recency_weight: float = 1.0,
        config: Optional[EloConfig] = None,
    ) -> None:
        """
        Initialize NHL Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default 20.0)
            home_advantage: Home advantage in Elo points (default 65.0)
                Reduced from 100.0 based on empirical NHL home win rates (~55%)
                and sports analytics research showing NHL has lower home advantage
                than NBA due to travel patterns, ice standardization, and parity.
            initial_rating: Initial rating for new teams (default 1500.0)
            recency_weight: Weight for recency adjustment (default 1.0)
            config: Optional EloConfig object
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating,
            config=config,
        )
        self.recency_weight = recency_weight
        self.last_game_date: Optional[datetime] = None

    def update(
        self,
        matchup: Optional[Union[Matchup, str]] = None,
        result: Optional[Union[GameResult, str, bool, float]] = None,
        home_won: Optional[Union[bool, float]] = None,
        **kwargs,
    ) -> float:
        """
        Update Elo ratings after a game with recency weighting.
        """
        parsed = self.parser.parse_update_args(
            matchup=matchup, result=result, home_won=home_won, **kwargs
        )
        matchup = parsed.matchup
        result = parsed.result

        home_team = matchup.home_team
        away_team = matchup.away_team
        is_neutral = matchup.is_neutral
        home_won = result.home_won
        game_date = matchup.game_date or kwargs.get("game_date")

        # Get current ratings
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home advantage
        if not is_neutral:
            home_rating += self.config.home_advantage

        # Calculate expected score
        expected_home = self.expected_score(home_rating, away_rating)

        # Convert home_won to actual score
        actual_home = 1.0 if home_won else 0.0

        # Calculate base rating change
        change = self.calculator.calculate_rating_change(expected_home, actual_home)

        # Apply recency weighting if we have game dates
        if game_date and self.last_game_date:
            days_diff = (game_date - self.last_game_date).days
            recency_factor = max(
                0.5, min(1.5, 1.0 + self.recency_weight * (days_diff / 365.0))
            )
            change *= recency_factor

        # Apply changes (remove home advantage first)
        if not is_neutral:
            home_rating -= self.config.home_advantage

        self.store.set_rating(home_team, home_rating + change)
        self.store.set_rating(away_team, away_rating - change)

        # Update game history
        self.game_history.append(
            {
                "home_team": home_team,
                "away_team": away_team,
                "home_won": bool(home_won),
                "home_score": result.home_score,
                "away_score": result.away_score,
                "game_date": game_date,
                "change": change,
            }
        )

        if game_date:
            self.last_game_date = game_date

        return change

    def load_ratings(self, filepath: Union[str, Path]) -> bool:
        """
        Load ratings from JSON file.

        Args:
            filepath: Path to JSON file with ratings
        """
        path = Path(filepath)
        if not path.exists():
            return False

        with open(path, "r") as f:
            data = json.load(f)

        ratings_data = data.get("ratings", {})
        ratings_data = {k: float(v) for k, v in ratings_data.items()}
        self.store.ratings = ratings_data

        # Load parameters
        params = data.get("parameters", {})
        if params:
            self.config.k_factor = params.get("k_factor", self.config.k_factor)
            self.config.home_advantage = params.get(
                "home_advantage", self.config.home_advantage
            )
            self.config.initial_rating = params.get(
                "initial_rating", self.config.initial_rating
            )

        # Load history if present
        self.game_history = data.get("game_history", [])
        # Parse dates in history
        for rec in self.game_history:
            self._parse_history_record_date(rec)

        return True

    def _parse_history_record_date(self, record: Dict) -> None:
        """Helper to parse game_date in a history record."""
        if not record.get("game_date"):
            return
        try:
            record["game_date"] = datetime.fromisoformat(record["game_date"])
        except (ValueError, TypeError):
            pass

    def save_ratings(self, filepath: Union[str, Path]) -> bool:
        """
        Save ratings to JSON file.

        Args:
            filepath: Path to save JSON file
        """
        path = Path(filepath)
        # Serialize history with date strings
        history_serializable = []
        for record in self.game_history:
            rec = record.copy()
            if rec.get("game_date") and isinstance(rec["game_date"], datetime):
                rec["game_date"] = rec["game_date"].isoformat()
            history_serializable.append(rec)

        data = {
            "parameters": {
                "k_factor": self.k_factor,
                "home_advantage": self.home_advantage,
                "initial_rating": self.initial_rating,
            },
            "ratings": self.ratings,
            "game_history": history_serializable,
            "timestamp": datetime.now().isoformat(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return True

    def apply_season_reversion(self, reversion_factor: float = 0.75) -> None:
        """
        Apply season-to-season rating reversion.

        Args:
            reversion_factor: Factor to revert toward initial rating (default 0.75)
        """
        for team in self.store.ratings:
            current = self.store.ratings[team]
            reverted = (
                self.config.initial_rating
                + (current - self.config.initial_rating) * reversion_factor
            )
            self.store.ratings[team] = reverted

    def export_history(self, filepath: Union[str, Path]) -> None:
        """
        Export game history to JSON file.

        Args:
            filepath: Path to save JSON file
        """
        path = Path(filepath)
        # Convert datetime objects to strings for JSON serialization
        history_serializable = []
        for record in self.game_history:
            rec = record.copy()
            if rec.get("game_date"):
                rec["game_date"] = rec["game_date"].isoformat()
            history_serializable.append(rec)

        with open(path, "w") as f:
            json.dump(history_serializable, f, indent=2)

    def get_recent_games(self, n: int = 10) -> list:
        """
        Get the most recent N games.

        Args:
            n: Number of games to return

        Returns:
            List of recent game records (newest first)
        """
        # Return last n games, reversed (newest first)
        return self.game_history[-n:][::-1]
