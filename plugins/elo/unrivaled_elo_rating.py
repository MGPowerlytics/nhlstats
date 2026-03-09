"""
Unrivaled Basketball Elo Rating System.

Unrivaled is a 3x3 women's professional basketball league where all games
are played at a neutral site. The rating system accounts for:
- No home advantage (all games at same venue)
- Higher variance due to 3x3 format (slightly higher K-factor)
- Small league (6 teams) for faster convergence
"""

from typing import Dict, Union

from plugins.elo.base_elo_rating import BaseEloRating


class UnrivaledEloRating(BaseEloRating):
    """
    Unrivaled Basketball Elo Rating System.

    Implements the unified Elo interface for Unrivaled 3x3 basketball.
    All games are treated as neutral site since they're played at the
    same venue.
    """

    def __init__(
        self,
        k_factor: float = 24.0,
        home_advantage: float = 0.0,
        initial_rating: float = 1500.0,
    ) -> None:
        """
        Initialize Unrivaled Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default 24.0, higher than
                     standard due to 3x3 variance and small sample sizes)
            home_advantage: Home advantage in Elo points (default 0.0, since
                           all games are at neutral site)
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
        home_win: Union[bool, float] = None,
        **kwargs,
    ) -> float:
        """
        Update Elo ratings after a game result.

        Args:
            home_team: Name of home team (first listed team)
            away_team: Name of away team (second listed team)
            home_won: True/1.0 if home team won, False/0.0 if away team won
            is_neutral: Whether the game was at a neutral site (effectively
                       always True for Unrivaled)
            home_win: Alias for home_won (backward compatibility)
            **kwargs: Additional arguments (ignored)

        Returns:
            The rating change applied to home team
        """
        # Handle aliasing for backward compatibility
        if home_won is None and home_win is not None:
            home_won = home_win
        elif home_won is None and "home_win" in kwargs:
            home_won = kwargs["home_win"]
        elif home_won is None:
            raise ValueError("Must provide home_won")

        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home advantage for expected score calculation
        adjusted_home = home_rating
        if not is_neutral:
            adjusted_home += self.home_advantage

        expected_home = self.expected_score(adjusted_home, away_rating)
        actual_home = 1.0 if home_won else 0.0
        change = self.k_factor * (actual_home - expected_home)

        # Update ratings
        self.ratings[home_team] = home_rating + change
        self.ratings[away_team] = away_rating - change

        return change


# Known Unrivaled teams (2025 inaugural season)
UNRIVALED_TEAMS = {
    "Rose BC",
    "Lunar Owls BC",
    "Phantom BC",
    "Mist BC",
    "Vinyl BC",
    "Laces BC",
}


def calculate_current_elo_ratings():
    """
    Calculate current Elo ratings from historical game data.

    Loads all Unrivaled games and processes them chronologically
    to compute current ratings for all teams.

    Returns:
        UnrivaledEloRating: Elo rating system with current ratings
    """
    from unrivaled_games import UnrivaledGames

    unrivaled = UnrivaledGames()
    df = unrivaled.load_games()

    if df.empty:
        print("⚠️ No Unrivaled games found")
        return UnrivaledEloRating()

    elo = UnrivaledEloRating()

    # Sort by date
    df = df.sort_values("date")

    for _, game in df.iterrows():
        home_score = game["home_score"]
        away_score = game["away_score"]

        if home_score > away_score:
            result = 1.0
        else:
            result = 0.0

        # All Unrivaled games are effectively neutral site
        elo.update(
            game["home_team"],
            game["away_team"],
            home_won=result,
            is_neutral=True,
        )

    return elo
