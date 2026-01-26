"""
EPL (English Premier League) Elo Rating System.

Production-ready Elo rating system for EPL predictions.
Inherits from BaseEloRating for unified interface.
Handles 3-way outcomes (Home, Draw, Away).
"""

import math
from typing import Dict, Union

from plugins.elo.base_elo_rating import BaseEloRating


class EPLEloRating(BaseEloRating):
    """
    EPL-specific Elo rating system with 3-way outcome support.

    This class extends BaseEloRating with soccer-specific functionality
    for handling draws and 3-way predictions while maintaining the
    unified interface.
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
        )

    def predict(
        self, home_team: str, away_team: str, is_neutral: bool = False
    ) -> float:
        """
        Predict probability of home team winning.

        Args:
            home_team: Name of home team
            away_team: Name of away team
            is_neutral: Whether the game is at a neutral site (no home advantage)

        Returns:
            float: Probability of home win (0.0 to 1.0)
        """
        # Get base ratings
        rh = self.get_rating(home_team)
        ra = self.get_rating(away_team)

        # Apply home advantage if not neutral
        if not is_neutral:
            rh = self._apply_home_advantage(rh, is_neutral=False)

        # Calculate expected score (home win probability ignoring draws)
        return self.expected_score(rh, ra)

    def update(
        self,
        home_team: str,
        away_team: str,
        home_won: Union[bool, float],
        is_neutral: bool = False,
    ) -> None:
        """
        Update Elo ratings after a game result.

        Args:
            home_team: Name of home team
            away_team: Name of away team
            home_won: Whether home team won (True/False) or score margin (float)
            is_neutral: Whether the game was at a neutral site
        """
        # Get current ratings
        rh = self.get_rating(home_team)
        ra = self.get_rating(away_team)

        # Apply home advantage if not neutral
        home_rating = rh
        if not is_neutral:
            home_rating = self._apply_home_advantage(rh, is_neutral=False)

        # Calculate expected score for home team
        expected_home = self.expected_score(home_rating, ra)

        # Determine actual score based on home_won
        if isinstance(home_won, bool):
            actual_home = 1.0 if home_won else 0.0
        else:
            # For score margin, use logistic transformation
            # Max margin effect capped at 2.0 (equivalent to ~0.88 probability)
            margin = min(max(home_won, -2.0), 2.0)
            actual_home = 1.0 / (1.0 + math.exp(-margin))

        # Calculate rating changes
        home_change = self._calculate_rating_change(expected_home, actual_home)
        self._calculate_rating_change(1.0 - expected_home, 1.0 - actual_home)

        # Update ratings
        self.ratings[home_team] = rh + home_change
        self.ratings[away_team] = ra - home_change  # Conservation of points

    def get_rating(self, team: str) -> float:
        """
        Get current Elo rating for a team.

        Args:
            team: Name of team

        Returns:
            float: Current Elo rating
        """
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score (probability of team A winning).

        Uses standard Elo formula:
        E_A = 1 / (1 + 10^((R_B - R_A) / 400))

        Args:
            rating_a: Rating of team A
            rating_b: Rating of team B

        Returns:
            float: Probability of team A winning (0.0 to 1.0)
        """
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def get_all_ratings(self) -> Dict[str, float]:
        """
        Get all current ratings.

        Returns:
            Dict[str, float]: Copy of all team ratings
        """
        return self.ratings.copy()

    # Soccer-specific methods (maintain backward compatibility)

    def predict_probs(self, home_team: str, away_team: str) -> tuple:
        """
        Predict probabilities for Home Win, Draw, Away Win.

        Returns: (p_home, p_draw, p_away)
        """
        rh = self.get_rating(home_team)
        ra = self.get_rating(away_team)

        # Apply home advantage
        dr = rh + self.home_advantage - ra

        # 1. Calculate Expected Points (standard Elo win prob)
        # Expected points = P(Home) + 0.5 * P(Draw)
        expected_points = 1 / (1 + 10 ** (-dr / 400))

        # 2. Estimate Draw Probability
        # Draw is most likely when teams are equal strength.
        # Historical average draw rate ~25-28%
        # Model: Normal distribution shape centered at 0 difference
        p_draw = 0.28 * math.exp(-((dr / 280) ** 2))

        # 3. Derive Win/Loss probs
        # P(Home) = ExpPoints - 0.5 * P(Draw)
        # But ensure non-negative
        p_home = max(0.01, expected_points - 0.5 * p_draw)
        p_away = max(0.01, 1.0 - p_home - p_draw)

        # Normalize to sum to 1.0 just in case
        total = p_home + p_draw + p_away
        return (p_home / total, p_draw / total, p_away / total)

    def predict_3way(self, home_team: str, away_team: str) -> Dict[str, float]:
        """
        Predict 3-way outcome as dict.

        Returns: {'home': p_home, 'draw': p_draw, 'away': p_away}
        """
        p_home, p_draw, p_away = self.predict_probs(home_team, away_team)
        return {"home": p_home, "draw": p_draw, "away": p_away}

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
