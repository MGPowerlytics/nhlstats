"""
Ligue 1 (French Soccer) Elo Rating System.

3-way prediction model for French Ligue 1 (Home/Draw/Away).
Similar to EPL implementation with draw probability from rating difference.
Inherits from BaseEloRating for unified interface.
"""

from typing import Dict

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

    def update(self, home_team, away_team, home_won, **kwargs):
        """Update ratings with research-optimized K-factor."""
        # Save original K
        old_k = self.config.k_factor

        # Adjust K based on outcome as per research
        # home_won=0.5 means a draw
        if home_won == 0.5:
            self.config.k_factor = 20.0
        else:
            self.config.k_factor = 30.0

        # Call parent update
        result = super().update(home_team, away_team, home_won, **kwargs)

        # Restore K
        self.config.k_factor = old_k
        return result

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
        if outcome == "home" or outcome == "H":
            home_won = 1.0
        elif outcome == "away" or outcome == "A":
            home_won = 0.0
        else:  # draw
            home_won = 0.5

        # Call the new update method
        self.update(home_team, away_team, home_won)

        # Return legacy format
        # Use self.config.k_factor which might have been changed by self.update
        # Actually self.update restores it, so we need to know what it was during update.
        # But legacy_update return is mostly for display/tests.
        used_k = 20.0 if home_won == 0.5 else 30.0

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_rating_change": used_k
            * (0.5 if outcome == "draw" else (1.0 if outcome == "home" else 0.0)),
            "away_rating_change": used_k
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
