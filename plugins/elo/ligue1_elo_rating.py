"""
Ligue 1 (French Soccer) Elo Rating System.

3-way prediction model for French Ligue 1 (Home/Draw/Away).
Similar to EPL implementation with draw probability from rating difference.
Inherits from BaseEloRating for unified interface.
"""

import math
from typing import Dict, Union

from plugins.elo.soccer_elo_rating import SoccerEloRating


class Ligue1EloRating(SoccerEloRating):
    """
    Elo rating system for French Ligue 1 soccer.

    Uses 3-way prediction model accounting for draws.
    Inherits from SoccerEloRating for unified interface.
    """

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 60.0,
        initial_rating: float = 1500.0,
    ):
        """
        Initialize Ligue 1 Elo rating system.

        Args:
            k_factor: Rating adjustment factor (20 is standard)
            home_advantage: Elo points added for home field (60 for soccer)
            initial_rating: Starting rating for new teams (1500 is standard)
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating,
            draw_coefficient=0.25,
            draw_width=200.0,
        )

    # Soccer-specific methods (maintain backward compatibility)

    # Legacy update method for backward compatibility
    def legacy_update(
        self, home_team: str, away_team: str, outcome: str
    ) -> Dict[str, float]:
        """
        Legacy update method for backward compatibility.

        Args:
            home_team: Home team name
            away_team: Away team name
            outcome: Match result ('home', 'draw', or 'away')

        Returns:
            Dictionary with rating changes and new ratings
        """
        # Convert legacy outcome to home_won
        if outcome == "home":
            home_won = True
        elif outcome == "away":
            home_won = False
        else:  # draw
            home_won = 0.5

        # Call the new update method
        self.update(home_team, away_team, home_won)

        # Return legacy format
        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_rating_change": self.k_factor
            * (0.5 if outcome == "draw" else (1.0 if outcome == "home" else 0.0)),
            "away_rating_change": self.k_factor
            * (0.5 if outcome == "draw" else (1.0 if outcome == "away" else 0.0)),
            "home_new_rating": self.ratings[home_team],
            "away_new_rating": self.ratings[away_team],
        }


if __name__ == "__main__":
    # Test the system
    elo = Ligue1EloRating()

    print("🇫🇷 Ligue 1 Elo Rating System Test\n")

    # Simulate some matches
    matches = [
        ("PSG", "Marseille", "home"),
        ("Lyon", "Monaco", "draw"),
        ("Lille", "Nice", "away"),
        ("PSG", "Lyon", "home"),
    ]

    for home, away, outcome in matches:
        probs = elo.predict_3way(home, away)
        print(f"{away} @ {home}")
        print(
            f"  Prediction: H: {probs['home']:.1%}, D: {probs['draw']:.1%}, A: {probs['away']:.1%}"
        )

        result = elo.legacy_update(home, away, outcome)
        print(f"  Actual: {outcome.upper()}")
        print(
            f"  Rating changes: {home} {result['home_rating_change']:+.1f}, {away} {result['away_rating_change']:+.1f}"
        )
        print()

    print("\nFinal Ratings:")
    for team in sorted(elo.ratings.keys(), key=lambda t: elo.ratings[t], reverse=True):
        print(f"  {team}: {elo.ratings[team]:.0f}")
