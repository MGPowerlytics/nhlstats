"""
EPL (English Premier League) Elo Rating System.

Production-ready Elo rating system for EPL predictions.
Inherits from BaseEloRating for unified interface.
Handles 3-way outcomes (Home, Draw, Away).
"""

from typing import Union

from plugins.elo.soccer_elo_rating import SoccerEloRating


class EPLEloRating(SoccerEloRating):
    """
    EPL-specific Elo rating system with 3-way outcome support.

    This class extends SoccerEloRating with EPL-specific draw probability
    parameters while maintaining the unified interface.
    """

    def __init__(
        self,
        k_factor: float = 40.0,
        home_advantage: float = 80.0,
        initial_rating: float = 1500.0,
    ):
        """
        Initialize EPL Elo rating system with optimized parameters.

        Args:
            k_factor: How quickly ratings change (40 is optimized for EPL)
            home_advantage: Elo points added for home field (80 is optimized for EPL)
            initial_rating: Starting rating for new teams (1500 is standard)
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating,
            draw_coefficient=0.20,
            draw_width=200.0,
        )

    def apply_seasonal_reversion(self, factor: float = 0.1):
        """
        Apply reversion towards the mean (1500) at season start.

        Args:
            factor: Strength of reversion (0.1 is optimized for EPL)
        """
        for team in self.ratings:
            self.ratings[team] = self.ratings[team] * (1 - factor) + 1500 * factor

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


def calculate_current_elo_ratings(csv_path: str = None) -> EPLEloRating:
    """Calculate current ratings from historical data.

    Returns:
        EPLEloRating: Elo rating system with ratings calculated from historical data.
    """
    from plugins.epl_games import EPLGames
    import pandas as pd

    epl_games = EPLGames()
    df = epl_games.load_games()
    df = df.sort_values("date")

    # Identify seasons for reversion
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["season"] = df.apply(
        lambda row: f"{row['year']-1}-{row['year']}"
        if row["month"] < 8
        else f"{row['year']}-{row['year']+1}",
        axis=1,
    )

    elo = EPLEloRating()
    current_season = None

    for _, game in df.iterrows():
        if current_season is None:
            current_season = game["season"]
        elif game["season"] != current_season:
            elo.apply_seasonal_reversion(factor=0.1)
            current_season = game["season"]

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
