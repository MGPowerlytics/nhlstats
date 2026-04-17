"""
MLB Elo Rating System

Production-ready Elo rating system for MLB predictions.
Inherits from BaseEloRating for unified interface.
"""

from plugins.elo.base_elo_rating import BaseEloRating, Matchup, GameResult
from typing import Dict, Union, Optional
from pathlib import Path


class MLBEloRating(BaseEloRating):
    """
    MLB-specific Elo rating system.

    Features:
    - Standard Elo with K=10, home advantage=75 (updated from K=20, HA=50)
    - Lower home advantage than other sports
    - Game history tracking
    """

    def __init__(
        self,
        k_factor: float = 10.0,  # Updated from 20.0
        home_advantage: float = 75.0,  # Updated from 50.0
        initial_rating: float = 1500.0,
    ) -> None:
        """
        Initialize MLB Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default 10.0)
            home_advantage: Home advantage in Elo points (default 75.0)
            initial_rating: Initial rating for new teams (default 1500.0)
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating,
        )

    def update(
        self,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
        home_won: Optional[Union[bool, float]] = None,
        is_neutral: bool = False,
        matchup: Optional[Matchup] = None,
        result: Optional[GameResult] = None,
        **kwargs,
    ) -> float:
        """
        Update Elo ratings after a game result with MLB-specific MOV multiplier.
        """
        parsed = self.parser.parse_update_args(
            home_team=home_team,
            away_team=away_team,
            home_won=home_won,
            is_neutral=is_neutral,
            matchup=matchup,
            result=result,
            **kwargs,
        )
        matchup = parsed.matchup
        result = parsed.result

        home_team = matchup.home_team
        away_team = matchup.away_team
        is_neutral = matchup.is_neutral
        home_won = result.home_won

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

        # Apply MOV multiplier if scores provided
        if result.home_score is not None and result.away_score is not None:
            mov_multiplier = self.calculator.calculate_mov_multiplier(
                result, home_rating - away_rating
            )
            change *= mov_multiplier

        # Apply changes (remove home advantage first)
        if not is_neutral:
            home_rating -= self.config.home_advantage

        self.store.set_rating(home_team, home_rating + change)
        self.store.set_rating(away_team, away_rating - change)

        # Record game history
        self.game_history.append(
            {
                "home_team": home_team,
                "away_team": away_team,
                "home_won": bool(home_won),
                "home_score": result.home_score,
                "away_score": result.away_score,
                "home_rating_before": home_rating,
                "away_rating_before": away_rating,
                "change": change,
            }
        )

        return change


def calculate_current_elo_ratings(output_path=None):
    """
    Calculate current Elo ratings for MLB based on games in database.

    Args:
        output_path (str, optional): Path to save CSV of ratings.

    Returns:
        MLBEloRating instance with updated ratings, or None if no games.
    """
    from plugins.db_manager import default_db

    elo = MLBEloRating()
    # Query mlb_games table
    query = """
        SELECT game_date, home_team, away_team, home_score, away_score
        FROM mlb_games
        WHERE game_date IS NOT NULL
        ORDER BY game_date
    """
    df = default_db.fetch_df(query)
    if df.empty:
        print("No MLB games found in database")
        return None

    for _, row in df.iterrows():
        home_team = row["home_team"]
        away_team = row["away_team"]
        home_score = row["home_score"]
        away_score = row["away_score"]
        home_won = (
            home_score > away_score
            if home_score is not None and away_score is not None
            else None
        )
        if home_won is None:
            continue
        elo.update(
            home_team, away_team, home_won, home_score=home_score, away_score=away_score
        )

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write("team,rating\n")
            for team, rating in sorted(elo.ratings.items(), key=lambda x: x[0]):
                f.write(f"{team},{rating:.2f}\n")
        print(f"Saved MLB Elo ratings to {output_path}")

    return elo


def create_team_factors_table():
    """Create team_factors table if it doesn't exist."""
    query = """
    CREATE TABLE IF NOT EXISTS team_factors (
        factor_id SERIAL PRIMARY KEY,
        team_id VARCHAR NOT NULL,
        game_date DATE NOT NULL,
        season INTEGER,
        team_name VARCHAR,
        venue VARCHAR,
        runs_per_game DECIMAL(5,3),
        obp DECIMAL(5,3),
        slg DECIMAL(5,3),
        ops DECIMAL(5,3),
        wOBA DECIMAL(5,3),
        wRC_plus INTEGER,
        era DECIMAL(5,3),
        fip DECIMAL(5,3),
        whip DECIMAL(5,3),
        strikeouts_per_nine DECIMAL(5,2),
        walks_per_nine DECIMAL(5,2),
        defensive_runs_saved INTEGER,
        ultimate_zone_rating DECIMAL(5,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(team_id, game_date)
    );
    """
    default_db.execute(query)
