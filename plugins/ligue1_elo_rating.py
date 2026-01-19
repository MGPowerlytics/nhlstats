"""
Ligue 1 (French Soccer) Elo Rating System

3-way prediction model for French Ligue 1 (Home/Draw/Away).
Similar to EPL implementation with draw probability from rating difference.
"""

import math
from typing import Dict, Tuple

class Ligue1EloRating:
    """
    Elo rating system for French Ligue 1 soccer.
    
    Uses 3-way prediction model accounting for draws.
    """
    
    def __init__(self, k_factor: int = 20, home_advantage: float = 60, initial_rating: float = 1500):
        """
        Initialize Ligue 1 Elo rating system.
        
        Args:
            k_factor: Rating adjustment factor (20 is standard)
            home_advantage: Elo points added for home field (60 for soccer)
            initial_rating: Starting rating for new teams (1500 is standard)
        """
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings = {}
    
    def get_rating(self, team: str) -> float:
        """Get current Elo rating for a team."""
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]
    
    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score using standard Elo formula.
        
        Returns probability between 0.0 and 1.0.
        """
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    
    def predict(self, home_team: str, away_team: str) -> float:
        """
        Predict probability of home team winning (ignoring draws).
        
        Args:
            home_team: Home team name
            away_team: Away team name
            
        Returns:
            Probability of home win (0.0 to 1.0)
        """
        home_rating = self.get_rating(home_team) + self.home_advantage
        away_rating = self.get_rating(away_team)
        return self.expected_score(home_rating, away_rating)
    
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
        draw_prob = 0.25 * math.exp(-(rating_diff / 200) ** 2)
        draw_prob = max(0.05, min(0.30, draw_prob))  # Clamp between 5-30%
        
        # Calculate win probabilities from remaining probability
        remaining_prob = 1.0 - draw_prob
        base_home_prob = self.expected_score(home_rating, away_rating)
        
        home_prob = base_home_prob * remaining_prob
        away_prob = (1 - base_home_prob) * remaining_prob
        
        return {
            'home': home_prob,
            'draw': draw_prob,
            'away': away_prob
        }
    
    def predict_probs(self, home_team: str, away_team: str) -> Dict[str, float]:
        """Alias for predict_3way for consistency."""
        return self.predict_3way(home_team, away_team)
    
    def update(self, home_team: str, away_team: str, outcome: str) -> Dict[str, float]:
        """
        Update ratings after a match.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            outcome: Match result ('home', 'draw', or 'away')
            
        Returns:
            Dictionary with rating changes
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)
        
        # Expected scores (with home advantage)
        expected_home = self.expected_score(
            home_rating + self.home_advantage,
            away_rating
        )
        expected_away = 1 - expected_home
        
        # Actual scores
        if outcome == 'home':
            actual_home, actual_away = 1.0, 0.0
        elif outcome == 'away':
            actual_home, actual_away = 0.0, 1.0
        else:  # draw
            actual_home, actual_away = 0.5, 0.5
        
        # Calculate rating changes
        home_change = self.k_factor * (actual_home - expected_home)
        away_change = self.k_factor * (actual_away - expected_away)
        
        # Update ratings
        self.ratings[home_team] = home_rating + home_change
        self.ratings[away_team] = away_rating + away_change
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'home_rating_change': home_change,
            'away_rating_change': away_change,
            'home_new_rating': self.ratings[home_team],
            'away_new_rating': self.ratings[away_team]
        }


if __name__ == '__main__':
    # Test the system
    elo = Ligue1EloRating()
    
    print("🇫🇷 Ligue 1 Elo Rating System Test\n")
    
    # Simulate some matches
    matches = [
        ('PSG', 'Marseille', 'home'),
        ('Lyon', 'Monaco', 'draw'),
        ('Lille', 'Nice', 'away'),
        ('PSG', 'Lyon', 'home'),
    ]
    
    for home, away, outcome in matches:
        probs = elo.predict_3way(home, away)
        print(f"{away} @ {home}")
        print(f"  Prediction: H: {probs['home']:.1%}, D: {probs['draw']:.1%}, A: {probs['away']:.1%}")
        
        result = elo.update(home, away, outcome)
        print(f"  Actual: {outcome.upper()}")
        print(f"  Rating changes: {home} {result['home_rating_change']:+.1f}, {away} {result['away_rating_change']:+.1f}")
        print()
    
    print("\nFinal Ratings:")
    for team in sorted(elo.ratings.keys(), key=lambda t: elo.ratings[t], reverse=True):
        print(f"  {team}: {elo.ratings[team]:.0f}")
