"""
EPL (English Premier League) Elo Rating System.

Production-ready Elo rating system for EPL predictions.
Inherits from BaseEloRating for unified interface.
Handles 3-way outcomes (Home, Draw, Away).
"""

import math
from typing import Dict, Union

from plugins.elo.soccer_elo_rating import SoccerEloRating


class EPLEloRating(SoccerEloRating):
    """
    EPL-specific Elo rating system with 3-way outcome support.

    This class extends SoccerEloRating with EPL-specific draw probability
    parameters while maintaining the unified interface.
    """

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 60.0,
        initial_rating: float = 1500.0,
    ):
        """
        Initialize EPL Elo rating system.

        Args:
            k_factor: How quickly ratings change (20 is standard for soccer)
            home_advantage: Elo points added for home field (60 for soccer)
            initial_rating: Starting rating for new teams (1500 is standard)
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating,
            draw_coefficient=0.28,
            draw_width=280.0,
        )

    # Legacy update method for backward compatibility
    def legacy_update(
        self, home_team: str, away_team: str, result: Union[str, int]
    ) -> float:
        """
        Legacy update method for backward compatibility.

        result: 'H' (Home Win), 'D' (Draw), 'A' (Away Win)
        OR
        result: 1 (Home Win), 0 (Away/Draw) - IF binary only available (imperfect)

        Returns: rating change
        """
        # Convert legacy result to home_won boolean
        if result == "H" or result == 1:
            home_won = True
        elif result == "A" or result == 0:
            home_won = False
        elif result == "D":
            # For draws, use 0.5 actual score
            home_won = 0.5
        else:
            home_won = False

        # Call the new update method
        self.update(home_team, away_team, home_won)

        # Return approximate change (for backward compatibility)
        return self.k_factor * (0.5 if result == "D" else (1.0 if home_won else 0.0))


def calculate_current_elo_ratings(csv_path="data/epl/E0.csv"):
    """Calculate current ratings from season CSV."""
    from epl_games import EPLGames

    epl_games = EPLGames()
    df = epl_games.load_games()

    elo = EPLEloRating()

    for _, game in df.iterrows():
        elo.legacy_update(game["home_team"], game["away_team"], game["result"])

    return elo


if __name__ == "__main__":
    # Test
    elo = calculate_current_elo_ratings()
    print("Top 5 Teams:")
    ranked = sorted(elo.ratings.items(), key=lambda x: x[1], reverse=True)[:5]
    for team, r in ranked:
        print(f"{team}: {r:.1f}")

    # Example Prediction
    h, a = "Man City", "Liverpool"
    ph, pd_prob, pa = elo.predict_probs(h, a)
    print(f"\n{h} vs {a}:")
    print(f"Home: {ph:.1%}, Draw: {pd_prob:.1%}, Away: {pa:.1%}")
