#!/usr/bin/env python3
"""
NHL Player Glicko-2 Ratings.

Glicko-2 is an extension of the Elo rating system that includes:
- Rating (r): Like Elo
- Rating Deviation (RD): Uncertainty in rating (like TrueSkill's sigma)
- Volatility (σ): Consistency of performance over time
"""

import duckdb
import glicko2
from collections import defaultdict
import pandas as pd
import numpy as np
from pathlib import Path


class NHLGlicko2:
    """Calculate Glicko-2 ratings for NHL players."""
    
    def __init__(self, db_path='data/nhlstats.duckdb'):
        self.conn = duckdb.connect(db_path)
        self.env = glicko2.Glicko2()
        self.player_ratings = defaultdict(lambda: self.env.create_rating())
        self.player_names = {}
        self.player_teams = {}
        
    def load_player_info(self):
        """Load player names and basic info."""
        print("📋 Loading player information...")
        
        query = """
        SELECT DISTINCT 
            pgs.player_id,
            p.first_name,
            p.last_name,
            p.position_code,
            pgs.team_id
        FROM player_game_stats pgs
        LEFT JOIN players p ON pgs.player_id = p.player_id
        WHERE pgs.player_id IS NOT NULL
        """
        
        df = self.conn.execute(query).fetchdf()
        
        for _, row in df.iterrows():
            player_id = row['player_id']
            first = row['first_name'] if pd.notna(row['first_name']) else ''
            last = row['last_name'] if pd.notna(row['last_name']) else ''
            
            if first or last:
                self.player_names[player_id] = f"{first} {last}".strip()
            else:
                self.player_names[player_id] = f"Player {player_id}"
            
            if pd.notna(row['team_id']):
                self.player_teams[player_id] = row['team_id']
        
        print(f"✅ Loaded {len(self.player_names)} players")
    
    def calculate_player_performance_weight(self, stats):
        """Calculate a player's performance weight."""
        toi = stats.get('toi_seconds', 0) or 0
        if toi == 0:
            return 0.1
        
        toi_weight = min(toi / 1200.0, 1.5)
        
        goals = stats.get('goals', 0) or 0
        assists = stats.get('assists', 0) or 0
        plus_minus = stats.get('plus_minus', 0) or 0
        shots = stats.get('shots', 0) or 0
        
        if stats.get('position') == 'G':
            saves = stats.get('saves', 0) or 0
            save_pct = stats.get('save_pct', 0) or 0
            if saves > 0:
                goalie_weight = (saves / 30.0) * (save_pct if save_pct else 0.9)
                return min(goalie_weight, 2.0)
        
        performance = (goals * 3.0 + assists * 2.0 + plus_minus * 0.5 + shots * 0.2)
        final_weight = toi_weight * (1.0 + performance / 10.0)
        
        return max(min(final_weight, 2.0), 0.1)
    
    def process_games(self, start_date=None, end_date=None, limit=None):
        """Process games chronologically to update Glicko-2 ratings."""
        print("\n🏒 Processing NHL games for Glicko-2 ratings...")
        
        query = """
        SELECT 
            g.game_id,
            g.game_date,
            g.home_team_id,
            g.away_team_id,
            g.home_score,
            g.away_score
        FROM games g
        WHERE g.game_type = 2
        AND g.game_state = 'OFF'
        """
        
        if start_date:
            query += f" AND g.game_date >= '{start_date}'"
        if end_date:
            query += f" AND g.game_date <= '{end_date}'"
        
        query += " ORDER BY g.game_date, g.game_id"
        
        if limit:
            query += f" LIMIT {limit}"
        
        games_df = self.conn.execute(query).fetchdf()
        
        print(f"📊 Found {len(games_df)} games to process")
        
        if len(games_df) == 0:
            print("⚠️  No games found!")
            return
        
        print(f"📅 Date range: {games_df['game_date'].min()} to {games_df['game_date'].max()}")
        
        games_processed = 0
        
        for _, game in games_df.iterrows():
            game_id = game['game_id']
            home_team = game['home_team_id']
            away_team = game['away_team_id']
            home_score = game['home_score']
            away_score = game['away_score']
            
            player_stats_query = f"""
            SELECT 
                player_id,
                team_id,
                position,
                toi_seconds,
                goals,
                assists,
                plus_minus,
                shots,
                saves,
                goals_against,
                save_pct
            FROM player_game_stats
            WHERE game_id = '{game_id}'
            AND player_id IS NOT NULL
            """
            
            player_stats = self.conn.execute(player_stats_query).fetchdf()
            
            if len(player_stats) == 0:
                continue
            
            home_players = player_stats[player_stats['team_id'] == home_team]
            away_players = player_stats[player_stats['team_id'] == away_team]
            
            if len(home_players) == 0 or len(away_players) == 0:
                continue
            
            # Determine outcome for each player
            if home_score > away_score:
                home_outcome = 1.0  # Win
                away_outcome = 0.0  # Loss
            elif away_score > home_score:
                home_outcome = 0.0  # Loss
                away_outcome = 1.0  # Win
            else:
                continue  # No draws in NHL
            
            # Update ratings for home players
            for _, p_stats in home_players.iterrows():
                player_id = p_stats['player_id']
                rating = self.player_ratings[player_id]
                
                # Create a virtual "team opponent" rating based on average away team
                avg_opponent_rating = np.mean([self.player_ratings[p].mu 
                                              for p in away_players['player_id'].tolist() 
                                              if p in self.player_ratings])
                opponent = self.env.create_rating(mu=avg_opponent_rating)
                
                # Update rating
                new_rating = self.env.rate_1vs1(rating, opponent, home_outcome == 1.0)
                self.player_ratings[player_id] = new_rating
            
            # Update ratings for away players
            for _, p_stats in away_players.iterrows():
                player_id = p_stats['player_id']
                rating = self.player_ratings[player_id]
                
                avg_opponent_rating = np.mean([self.player_ratings[p].mu 
                                              for p in home_players['player_id'].tolist()
                                              if p in self.player_ratings])
                opponent = self.env.create_rating(mu=avg_opponent_rating)
                
                new_rating = self.env.rate_1vs1(rating, opponent, away_outcome == 1.0)
                self.player_ratings[player_id] = new_rating
            
            games_processed += 1
            
            if games_processed % 100 == 0:
                print(f"  Processed {games_processed}/{len(games_df)} games...")
        
        print(f"✅ Processed {games_processed} games")
        print(f"📈 Tracked {len(self.player_ratings)} players")
    
    def get_team_average_rating(self, team_id, recent_games=20):
        """Calculate average Glicko-2 rating for a team."""
        query = f"""
        SELECT DISTINCT player_id
        FROM player_game_stats
        WHERE team_id = {team_id}
        ORDER BY game_id DESC
        LIMIT {recent_games}
        """
        
        players = self.conn.execute(query).fetchdf()
        
        if len(players) == 0:
            return None
        
        ratings = []
        for _, row in players.iterrows():
            player_id = row['player_id']
            if player_id in self.player_ratings:
                rating = self.player_ratings[player_id]
                # Conservative estimate: mu - 2*phi (RD)
                ratings.append(rating.mu - 2 * rating.phi)
        
        return np.mean(ratings) if ratings else None
    
    def save_ratings(self, filename='data/nhl_glicko2_ratings.csv'):
        """Save all player ratings to CSV."""
        results = []
        
        for player_id, rating in self.player_ratings.items():
            player_name = self.player_names.get(player_id, f"Unknown {player_id}")
            team_id = self.player_teams.get(player_id, 'N/A')
            
            results.append({
                'player_id': player_id,
                'player_name': player_name,
                'team_id': team_id,
                'rating_mu': rating.mu,
                'rating_phi': rating.phi,
                'rating_sigma': rating.sigma,
                'conservative_rating': rating.mu - 2 * rating.phi
            })
        
        df = pd.DataFrame(results)
        df = df.sort_values('conservative_rating', ascending=False)
        df.to_csv(filename, index=False)
        
        print(f"\n💾 Saved {len(df)} player ratings to {filename}")
        
        return df


if __name__ == '__main__':
    print("=" * 80)
    print("🏒 NHL GLICKO-2 PLAYER RATINGS")
    print("=" * 80)
    
    glicko = NHLGlicko2()
    glicko.load_player_info()
    glicko.process_games()
    glicko.save_ratings()
    
    print("\n✅ Glicko-2 calculation complete!")
