"""
Production Elo Rating System for NHL Betting

Simple, fast, interpretable alternative to complex ML models.
Performance: 59.3% accuracy, 0.591 AUC (matches XGBoost with 1/30th the complexity)
"""

import json
from pathlib import Path
from datetime import datetime


class NHLEloRating:
    """
    Production-ready Elo rating system for NHL predictions
    
    Usage:
        elo = NHLEloRating()
        elo.load_ratings()  # Load from disk
        
        # Make prediction
        prob = elo.predict("Toronto Maple Leafs", "Boston Bruins")
        
        # After game completes
        elo.update("Toronto Maple Leafs", "Boston Bruins", home_won=True)
        elo.save_ratings()  # Persist to disk
    """
    
    def __init__(self, k_factor=10, home_advantage=50, initial_rating=1500):
        """
        Initialize Elo rating system
        
        Args:
            k_factor: How quickly ratings change (higher = more volatile)
            home_advantage: Elo points added to home team (typically 50-150)
            initial_rating: Starting rating for new teams
        """
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings = {}
        self.game_history = []
        
    def get_rating(self, team):
        """Get current Elo rating for a team"""
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]
    
    def expected_score(self, rating_a, rating_b):
        """
        Calculate expected score (probability of team A winning)
        
        Uses standard Elo formula:
        E_A = 1 / (1 + 10^((R_B - R_A) / 400))
        """
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    
    def predict(self, home_team, away_team):
        """
        Predict probability of home team winning
        
        Args:
            home_team: Name of home team
            away_team: Name of away team
            
        Returns:
            float: Probability of home win (0.0 to 1.0)
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)
        
        # Apply home advantage
        home_rating_adj = home_rating + self.home_advantage
        
        return self.expected_score(home_rating_adj, away_rating)
    
    def update(self, home_team, away_team, home_won, home_score=None, away_score=None):
        """
        Update Elo ratings after a game
        
        Args:
            home_team: Name of home team
            away_team: Name of away team
            home_won: Boolean, True if home team won
            home_score: Optional final score (for history)
            away_score: Optional final score (for history)
            
        Returns:
            dict: Changes in ratings
        """
        # Get current ratings
        home_rating_before = self.get_rating(home_team)
        away_rating_before = self.get_rating(away_team)
        
        # Apply home advantage for expected score calculation
        home_rating_adj = home_rating_before + self.home_advantage
        
        # Calculate expected scores
        expected_home = self.expected_score(home_rating_adj, away_rating_before)
        expected_away = 1 - expected_home
        
        # Actual outcomes
        actual_home = 1.0 if home_won else 0.0
        actual_away = 1.0 - actual_home
        
        # Update ratings
        home_change = self.k_factor * (actual_home - expected_home)
        away_change = self.k_factor * (actual_away - expected_away)
        
        self.ratings[home_team] = home_rating_before + home_change
        self.ratings[away_team] = away_rating_before + away_change
        
        # Record history
        self.game_history.append({
            'date': datetime.now().isoformat(),
            'home_team': home_team,
            'away_team': away_team,
            'home_won': home_won,
            'home_score': home_score,
            'away_score': away_score,
            'prob_home_win': expected_home,
            'home_rating_before': home_rating_before,
            'away_rating_before': away_rating_before,
            'home_rating_after': self.ratings[home_team],
            'away_rating_after': self.ratings[away_team],
            'home_change': home_change,
            'away_change': away_change
        })
        
        return {
            'home_change': home_change,
            'away_change': away_change,
            'home_rating_new': self.ratings[home_team],
            'away_rating_new': self.ratings[away_team]
        }

    def apply_season_reversion(self, factor=0.35):
        """
        Regress all team ratings towards the mean (1500) for a new season.
        New Rating = (1 - factor) * Old Rating + factor * 1500
        
        Args:
            factor: 0.0 to 1.0 (0.0 = no change, 1.0 = reset everyone to 1500)
                    0.35 is optimal for NHL based on historical analysis.
        """
        for team, rating in self.ratings.items():
            self.ratings[team] = (1 - factor) * rating + factor * self.initial_rating
        
        print(f"🔄 Applied season reversion (factor={factor}) to {len(self.ratings)} teams")
    
    def get_rankings(self, top_n=None):
        """
        Get teams ranked by Elo rating
        
        Args:
            top_n: Return only top N teams (None = all)
            
        Returns:
            list: Tuples of (team, rating) sorted by rating
        """
        ranked = sorted(self.ratings.items(), key=lambda x: x[1], reverse=True)
        
        if top_n:
            return ranked[:top_n]
        return ranked
    
    def save_ratings(self, filepath='data/nhl_elo_ratings.json'):
        """Save current ratings and parameters to JSON file"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'parameters': {
                'k_factor': self.k_factor,
                'home_advantage': self.home_advantage,
                'initial_rating': self.initial_rating
            },
            'ratings': self.ratings,
            'last_updated': datetime.now().isoformat(),
            'num_teams': len(self.ratings),
            'num_games': len(self.game_history)
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Saved {len(self.ratings)} team ratings to {filepath}")
    
    def load_ratings(self, filepath='data/nhl_elo_ratings.json'):
        """Load ratings from JSON file"""
        filepath = Path(filepath)
        
        if not filepath.exists():
            print(f"⚠️  No saved ratings found at {filepath}")
            print("   Starting with fresh ratings")
            return False
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Load parameters
        params = data.get('parameters', {})
        self.k_factor = params.get('k_factor', self.k_factor)
        self.home_advantage = params.get('home_advantage', self.home_advantage)
        self.initial_rating = params.get('initial_rating', self.initial_rating)
        
        # Load ratings
        self.ratings = data.get('ratings', {})
        
        print(f"✅ Loaded {len(self.ratings)} team ratings from {filepath}")
        print(f"   Last updated: {data.get('last_updated', 'Unknown')}")
        
        return True
    
    def export_history(self, filepath='data/nhl_elo_history.json'):
        """Export game history with rating changes"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(self.game_history, f, indent=2)
        
        print(f"✅ Exported {len(self.game_history)} games to {filepath}")


def demo():
    """Demonstration of Elo rating system"""
    print("=" * 60)
    print("NHL Elo Rating System - Demo")
    print("=" * 60)
    
    elo = NHLEloRating(k_factor=20, home_advantage=100)
    
    # Simulate some games
    games = [
        ("Toronto Maple Leafs", "Boston Bruins", True),
        ("Tampa Bay Lightning", "Florida Panthers", False),
        ("Colorado Avalanche", "Vegas Golden Knights", True),
        ("Toronto Maple Leafs", "Tampa Bay Lightning", True),
        ("Boston Bruins", "Florida Panthers", True),
    ]
    
    print("\n📊 Simulating games...\n")
    
    for home, away, home_won in games:
        # Predict before game
        prob = elo.predict(home, away)
        
        # Update after game
        changes = elo.update(home, away, home_won)
        
        result = "WON" if home_won else "LOST"
        print(f"{home} vs {away}")
        print(f"  Predicted: {prob:.1%} home win")
        print(f"  Actual: Home {result}")
        print(f"  Rating changes: {home} {changes['home_change']:+.1f}, {away} {changes['away_change']:+.1f}")
        print()
    
    # Show final rankings
    print("=" * 60)
    print("Final Rankings")
    print("=" * 60)
    
    for i, (team, rating) in enumerate(elo.get_rankings(top_n=5), 1):
        print(f"{i}. {team}: {rating:.1f}")
    
    # Save ratings
    print()
    elo.save_ratings('data/nhl_elo_ratings_demo.json')


if __name__ == "__main__":
    demo()
