"""
Production Elo Rating System for NHL Betting

Simple, fast, interpretable alternative to complex ML models.
Performance: 59.3% accuracy, 0.591 AUC (matches XGBoost with 1/30th the complexity)
"""

import json
from pathlib import Path
from datetime import datetime
from .base_elo_rating import BaseEloRating
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
        home_advantage: float = 100.0,
        initial_rating: float = 1500.0,
        recency_weight: float = 1.0
    ) -> None:
        """
        Initialize NHL Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default 20.0)
            home_advantage: Home advantage in Elo points (default 100.0)
            initial_rating: Initial rating for new teams (default 1500.0)
            recency_weight: Weight for recency adjustment (default 1.0)
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating
        )
        self.recency_weight = recency_weight
        self.game_history = []
        self.last_game_date: Optional[datetime] = None

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
        home_score: Optional[float] = None,
        away_score: Optional[float] = None,
        game_date: Optional[datetime] = None,
        **kwargs
    ) -> None:
        """
        Update Elo ratings after a game with recency weighting.

        Args:
            home_team: Name of home team
            away_team: Name of away team
            home_won: Boolean, True if home team won
            is_neutral: Whether the game was at a neutral site
            home_score: Home team score (optional)
            away_score: Away team score (optional)
            game_date: Date of the game (optional)
        """
        # Alias home_win
        if home_won is None and 'home_win' in kwargs:
            home_won = kwargs['home_win']
        elif home_won is None:
             raise ValueError("Must provide home_won")

        # Get current ratings
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home advantage
        if not is_neutral:
            home_rating += self.home_advantage

        # Calculate expected score
        expected_home = self.expected_score(home_rating, away_rating)

        # Convert home_won to actual score
        actual_home = 1.0 if home_won else 0.0

        # Calculate base rating change
        change = self._calculate_rating_change(expected_home, actual_home)

        # Apply recency weighting if we have game dates
        if game_date and self.last_game_date:
            days_diff = (game_date - self.last_game_date).days
            recency_factor = max(0.5, min(1.5, 1.0 + self.recency_weight * (days_diff / 365.0)))
            change *= recency_factor

        # Apply changes (remove home advantage first)
        if not is_neutral:
            home_rating -= self.home_advantage

        self.ratings[home_team] = home_rating + change
        self.ratings[away_team] = away_rating - change

        # Update game history
        self.game_history.append({
            'home_team': home_team,
            'away_team': away_team,
            'home_won': bool(home_won),
            'home_score': home_score,
            'away_score': away_score,
            'game_date': game_date,
            'change': change
        })

        if game_date:
            self.last_game_date = game_date

        return change

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
        """
        self.update(home_team, away_team, home_won, is_neutral=False, **kwargs)

    def load_ratings(self, filepath: Union[str, Path]) -> bool:
        """
        Load ratings from JSON file.

        Args:
            filepath: Path to JSON file with ratings
        """
        path = Path(filepath)
        if path.exists():
            with open(path, 'r') as f:
                data = json.load(f)
                self.ratings = data.get('ratings', {})
                self.ratings = {k: float(v) for k, v in self.ratings.items()}

                # Load parameters
                params = data.get('parameters', {})
                if params:
                    self.k_factor = params.get('k_factor', self.k_factor)
                    self.home_advantage = params.get('home_advantage', self.home_advantage)
                    self.initial_rating = params.get('initial_rating', self.initial_rating)

                # Load history if present
                self.game_history = data.get('game_history', [])
                # Parse dates in history
                for rec in self.game_history:
                    if rec.get('game_date'):
                        try:
                            rec['game_date'] = datetime.fromisoformat(rec['game_date'])
                        except (ValueError, TypeError):
                            pass
            return True
        return False

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
            if rec.get('game_date') and isinstance(rec['game_date'], datetime):
                rec['game_date'] = rec['game_date'].isoformat()
            history_serializable.append(rec)

        data = {
            'parameters': {
                'k_factor': self.k_factor,
                'home_advantage': self.home_advantage,
                'initial_rating': self.initial_rating
            },
            'ratings': self.ratings,
            'game_history': history_serializable,
            'timestamp': datetime.now().isoformat()
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return True

    def apply_season_reversion(self, reversion_factor: float = 0.75) -> None:
        """
        Apply season-to-season rating reversion.

        Args:
            reversion_factor: Factor to revert toward initial rating (default 0.75)
        """
        for team in self.ratings:
            current = self.ratings[team]
            reverted = self.initial_rating + (current - self.initial_rating) * reversion_factor
            self.ratings[team] = reverted

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
            if rec.get('game_date'):
                rec['game_date'] = rec['game_date'].isoformat()
            history_serializable.append(rec)

        with open(path, 'w') as f:
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
