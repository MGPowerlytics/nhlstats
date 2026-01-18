"""NFL Elo Rating System for predicting game outcomes."""

import duckdb
from pathlib import Path
from datetime import datetime

class NFLEloRating:
    def __init__(self, k_factor=20, home_advantage=65, initial_rating=1500):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings = {}
    
    def get_rating(self, team):
        """Get current Elo rating for a team."""
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]
    
    def expected_score(self, rating_a, rating_b):
        """Calculate expected score for team A vs team B."""
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    
    def update(self, home_team, away_team, home_score, away_score):
        """Update Elo ratings after a game."""
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)
        
        # Apply home advantage
        home_expected = self.expected_score(home_rating + self.home_advantage, away_rating)
        away_expected = 1 - home_expected
        
        # Determine actual scores (1 for win, 0 for loss)
        if home_score > away_score:
            home_actual = 1
            away_actual = 0
        else:
            home_actual = 0
            away_actual = 1
        
        # Update ratings
        self.ratings[home_team] = home_rating + self.k_factor * (home_actual - home_expected)
        self.ratings[away_team] = away_rating + self.k_factor * (away_actual - away_expected)
    
    def predict(self, home_team, away_team):
        """Predict probability of home team winning."""
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)
        return self.expected_score(home_rating + self.home_advantage, away_rating)


def load_nfl_games_from_db(db_path='data/nhlstats.duckdb'):
    """Load historical NFL games from DuckDB."""
    try:
        conn = duckdb.connect(str(Path(db_path)))
        
        # Check if NFL tables exist
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        
        if 'nfl_games' not in table_names:
            print("⚠️ No nfl_games table found")
            return []
        
        # Load completed games ordered by date
        query = """
            SELECT 
                game_date,
                home_team,
                away_team,
                home_score,
                away_score
            FROM nfl_games
            WHERE home_score IS NOT NULL 
              AND away_score IS NOT NULL
              AND status = 'Final'
            ORDER BY game_date, game_id
        """
        
        games = conn.execute(query).fetchall()
        conn.close()
        
        print(f"✓ Loaded {len(games)} completed NFL games")
        return games
        
    except Exception as e:
        print(f"⚠️ Error loading NFL games: {e}")
        return []


def calculate_current_elo_ratings(output_path='data/nfl_current_elo_ratings.csv'):
    """Calculate current Elo ratings for all NFL teams."""
    games = load_nfl_games_from_db()
    
    if not games:
        print("⚠️ No games to process")
        return None
    
    elo = NFLEloRating(k_factor=20, home_advantage=65)
    
    # Process all historical games
    for game_date, home_team, away_team, home_score, away_score in games:
        elo.update(home_team, away_team, home_score, away_score)
    
    # Save current ratings
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write('team,rating\n')
        for team in sorted(elo.ratings.keys()):
            f.write(f'{team},{elo.ratings[team]:.2f}\n')
    
    print(f"✓ Saved current Elo ratings to {output_path}")
    print(f"✓ Processed {len(elo.ratings)} teams")
    
    return elo


if __name__ == '__main__':
    elo_system = calculate_current_elo_ratings()
    
    if elo_system:
        print("\nTop 10 NFL Teams by Elo:")
        top_teams = sorted(elo_system.ratings.items(), key=lambda x: x[1], reverse=True)[:10]
        for i, (team, rating) in enumerate(top_teams, 1):
            print(f"{i}. {team}: {rating:.1f}")
