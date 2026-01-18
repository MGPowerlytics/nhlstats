import json
from pathlib import Path
from datetime import datetime
import math

class EPLEloRating:
    """
    Elo rating system for EPL (English Premier League).
    Handles 3-way outcomes (Home, Draw, Away).
    """
    
    def __init__(self, k_factor=20, home_advantage=60, initial_rating=1500):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings = {}
        
    def get_rating(self, team):
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]
        
    def predict_probs(self, home_team, away_team):
        """
        Predict probabilities for Home Win, Draw, Away Win.
        Returns: (p_home, p_draw, p_away)
        """
        rh = self.get_rating(home_team)
        ra = self.get_rating(away_team)
        
        dr = rh + self.home_advantage - ra
        
        # 1. Calculate Expected Points (standard Elo win prob)
        # Expected points = P(Home) + 0.5 * P(Draw)
        expected_points = 1 / (1 + 10 ** (-dr / 400))
        
        # 2. Estimate Draw Probability
        # Draw is most likely when teams are equal strength.
        # Historical average draw rate ~25-28%
        # Model: Normal distribution shape centered at 0 difference
        p_draw = 0.28 * math.exp(- (dr / 280) ** 2)
        
        # 3. Derive Win/Loss probs
        # P(Home) = ExpPoints - 0.5 * P(Draw)
        # But ensure non-negative
        p_home = max(0.01, expected_points - 0.5 * p_draw)
        p_away = max(0.01, 1.0 - p_home - p_draw)
        
        # Normalize to sum to 1.0 just in case
        total = p_home + p_draw + p_away
        return (p_home/total, p_draw/total, p_away/total)
    
    def predict(self, home_team, away_team):
        """
        Wrapper to return just home win probability for compatibility.
        """
        probs = self.predict_probs(home_team, away_team)
        return probs[0]
        
    def update(self, home_team, away_team, result):
        """
        Update ratings based on result.
        result: 'H' (Home Win), 'D' (Draw), 'A' (Away Win)
        OR
        result: 1 (Home Win), 0 (Away/Draw) - IF binary only available (imperfect)
        """
        rh = self.get_rating(home_team)
        ra = self.get_rating(away_team)
        
        # Calculate expected points
        dr = rh + self.home_advantage - ra
        expected_points = 1 / (1 + 10 ** (-dr / 400))
        
        # Actual points
        if result == 'H' or result == 1:
            actual_points = 1.0
        elif result == 'D':
            actual_points = 0.5
        elif result == 'A':
            actual_points = 0.0
        else:
            # Fallback for binary input 0 where we don't know if it was D or A
            # If we are forced to treat it as loss, we lose information.
            actual_points = 0.0
            
        # Update
        change = self.k_factor * (actual_points - expected_points)
        
        self.ratings[home_team] = rh + change
        self.ratings[away_team] = ra - change
        
        return change

def calculate_current_elo_ratings(csv_path='data/epl/E0.csv'):
    """Calculate current ratings from season CSV."""
    from epl_games import EPLGames
    
    epl_games = EPLGames()
    df = epl_games.load_games()
    
    elo = EPLEloRating()
    
    for _, game in df.iterrows():
        elo.update(game['home_team'], game['away_team'], game['result'])
        
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
