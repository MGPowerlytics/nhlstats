import json
from pathlib import Path
from datetime import datetime

class NCAABEloRating:
    """NCAA Basketball Elo Rating System."""
    
    def __init__(self, k_factor=20, home_advantage=100, initial_rating=1500):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings = {}
        
    def get_rating(self, team):
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]
        
    def predict(self, home_team, away_team, is_neutral=False):
        """Predict home team win probability."""
        rh = self.get_rating(home_team)
        ra = self.get_rating(away_team)
        
        ha = 0 if is_neutral else self.home_advantage
        
        dr = rh + ha - ra
        return 1 / (1 + 10 ** (-dr / 400))
        
    def update(self, home_team, away_team, home_win, is_neutral=False):
        """
        Update ratings based on game result.
        home_win: 1.0 (win), 0.0 (loss)
        """
        rh = self.get_rating(home_team)
        ra = self.get_rating(away_team)
        
        ha = 0 if is_neutral else self.home_advantage
        
        dr = rh + ha - ra
        expected_home = 1 / (1 + 10 ** (-dr / 400))
        
        actual_home = float(home_win)
        
        change = self.k_factor * (actual_home - expected_home)
        
        self.ratings[home_team] = rh + change
        self.ratings[away_team] = ra - change
        
        return change

def calculate_current_elo_ratings():
    from ncaab_games import NCAABGames
    
    ncaab = NCAABGames()
    df = ncaab.load_games()
    
    elo = NCAABEloRating()
    
    # Sort by date
    df = df.sort_values('date')
    
    last_season = None
    
    for _, game in df.iterrows():
        # Optional: Season Reversion?
        # College rosters churn a lot.
        current_season = game.get('season')
        if current_season and current_season != last_season:
             if last_season is not None:
                 # Revert towards mean
                 for t in elo.ratings:
                     elo.ratings[t] = 0.65 * elo.ratings[t] + 0.35 * 1500
             last_season = current_season

        # Win = 1 if home score > away score
        # Note: In Massey data, scores are present
        h_score = game['home_score']
        a_score = game['away_score']
        neutral = game['neutral']
        
        if h_score > a_score:
            res = 1.0
        else:
            res = 0.0
            
        elo.update(game['home_team'], game['away_team'], res, is_neutral=neutral)
        
    return elo

if __name__ == "__main__":
    elo = calculate_current_elo_ratings()
    print("Top 10 NCAAB Teams:")
    ranked = sorted(elo.ratings.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (t, r) in enumerate(ranked, 1):
        print(f"{i}. {t}: {r:.1f}")
