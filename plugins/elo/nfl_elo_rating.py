"""
NFL Elo Rating System

Production-ready Elo rating system for NFL predictions.
Inherits from BaseEloRating for unified interface.
"""

from plugins.elo.base_elo_rating import BaseEloRating, Matchup, GameResult
from typing import Dict, Union, Optional


class NFLEloRating(BaseEloRating):
    """NFL-specific Elo rating system."""

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 65.0,
        initial_rating: float = 1500.0,
    ) -> None:
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
        Update Elo ratings after a game result with NFL-specific MOV multiplier.
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

        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        if not is_neutral:
            home_rating += self.config.home_advantage

        expected_home = self.expected_score(home_rating, away_rating)
        actual_home = 1.0 if home_won else 0.0
        change = self.calculator.calculate_rating_change(expected_home, actual_home)

        # Apply MOV multiplier if scores provided
        if result.home_score is not None and result.away_score is not None:
            mov_multiplier = self.calculator.calculate_mov_multiplier(
                result, home_rating - away_rating
            )
            change *= mov_multiplier

        if not is_neutral:
            home_rating -= self.config.home_advantage

        self.store.set_rating(home_team, home_rating + change)
        self.store.set_rating(away_team, away_rating - change)

        return change


def calculate_current_elo_ratings(output_path=None):
    """
    Calculate current Elo ratings for NFL based on games in database.

    Args:
        output_path (str, optional): Path to save CSV of ratings.

    Returns:
        NFLEloRating instance with updated ratings, or None if no games.
    """
    from plugins.db_manager import default_db
    from pathlib import Path

    elo = NFLEloRating()
    # Query nfl_games table
    query = """
        SELECT game_date, home_team, away_team, home_score, away_score
        FROM nfl_games
        WHERE game_date IS NOT NULL
        ORDER BY game_date
    """
    df = default_db.fetch_df(query)
    if df.empty:
        print("No NFL games found in database")
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
        print(f"Saved NFL Elo ratings to {output_path}")

    return elo
