"""
Ligue 1 (French Soccer) Elo Rating System.

3-way prediction model for French Ligue 1 (Home/Draw/Away).
Similar to EPL implementation with draw probability from rating difference.
Inherits from BaseEloRating for unified interface.
"""

import math
from typing import Dict, Union

from plugins.elo.base_elo_rating import BaseEloRating


class Ligue1EloRating(BaseEloRating):
    """
    Elo rating system for French Ligue 1 soccer.

    Uses 3-way prediction model accounting for draws.
    Inherits from BaseEloRating for unified interface.
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
        )

    def predict(
        self, home_team: str, away_team: str, is_neutral: bool = False
    ) -> float:
        """
        Predict probability of home team winning (ignoring draws).

        Args:
            home_team: Home team name
            away_team: Away team name
            is_neutral: Whether the game is at a neutral site

        Returns:
            Probability of home win (0.0 to 1.0)
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home advantage if not neutral
        if not is_neutral:
            home_rating = self._apply_home_advantage(home_rating, is_neutral=False)

        return self.expected_score(home_rating, away_rating)

    def update(
        self,
        home_team: str,
        away_team: str,
        home_won: Union[bool, float],
        is_neutral: bool = False,
    ) -> None:
        """
        Update ratings after a match.

        Args:
            home_team: Home team name
            away_team: Away team name
            home_won: Whether home team won (True/False) or score margin (float)
            is_neutral: Whether the game was at a neutral site
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home advantage if not neutral
        adjusted_home_rating = home_rating
        if not is_neutral:
            adjusted_home_rating = self._apply_home_advantage(
                home_rating, is_neutral=False
            )

        # Expected scores (with home advantage)
        expected_home = self.expected_score(adjusted_home_rating, away_rating)
        expected_away = 1.0 - expected_home

        # Determine actual scores based on home_won
        if isinstance(home_won, bool):
            actual_home = 1.0 if home_won else 0.0
            actual_away = 0.0 if home_won else 1.0
        else:
            # For score margin, use logistic transformation
            # Max margin effect capped at 2.0 (equivalent to ~0.88 probability)
            margin = min(max(home_won, -2.0), 2.0)
            actual_home = 1.0 / (1.0 + math.exp(-margin))
            actual_away = 1.0 - actual_home

        # Calculate rating changes
        home_change = self._calculate_rating_change(expected_home, actual_home)
        away_change = self._calculate_rating_change(expected_away, actual_away)

        # Update ratings
        self.ratings[home_team] = home_rating + home_change
        self.ratings[away_team] = away_rating + away_change

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
        Calculate expected score using standard Elo formula.

        Returns probability between 0.0 and 1.0.
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

    def predict_3way(self, home_team: str, away_team: str) -> Dict[str, float]:
        """
        Predict 3-way outcome probabilities (Home/Draw/Away).

        Uses Gaussian model for draw probability based on rating difference.
        Draw probability is higher when teams are evenly matched.

        Args:
            home_team: Home team name
            away_team: Away team name

        Returns:
            Dictionary with 'home', 'draw', 'away' probabilities (sum = 1.0)
        """
        home_rating = self.get_rating(home_team) + self.home_advantage
        away_rating = self.get_rating(away_team)
        rating_diff = abs(home_rating - away_rating)

        # Draw probability: Gaussian model based on rating difference
        # Peak at ~25% for evenly matched teams, drops to ~5% for large gaps
        # NOTE: Model rarely predicts draws due to home advantage (60pts) making
        # home win probability typically higher than draw probability. This results
        # in 44.1% accuracy but strong home bias (85% home predictions vs 39% actual).
        # Increasing draw coefficients improves distribution but lowers accuracy.
        draw_prob = 0.25 * math.exp(-((rating_diff / 200) ** 2))
        draw_prob = max(0.05, min(0.30, draw_prob))  # Clamp between 5-30%

        # Calculate win probabilities from remaining probability
        remaining_prob = 1.0 - draw_prob
        base_home_prob = self.expected_score(home_rating, away_rating)

        home_prob = base_home_prob * remaining_prob
        away_prob = (1.0 - base_home_prob) * remaining_prob

        return {"home": home_prob, "draw": draw_prob, "away": away_prob}

    def predict_probs(self, home_team: str, away_team: str) -> Dict[str, float]:
        """Alias for predict_3way for consistency."""
        return self.predict_3way(home_team, away_team)

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
