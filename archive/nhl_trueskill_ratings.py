#!/usr/bin/env python3
"""
NHL Player TrueSkill Ratings using Microsoft's TrueSkill algorithm.

TrueSkill is a Bayesian skill rating system that accounts for:
- Team performance (not just individual)
- Uncertainty in ratings (sigma value)
- Player contributions based on ice time and stats
"""
import duckdb
import trueskill
from trueskill import Rating, rate
from collections import defaultdict
from datetime import datetime
import pandas as pd


class NHLTrueSkill:
    """Calculate TrueSkill ratings for NHL players."""
    
    def __init__(self, db_path='data/nhlstats.duckdb'):
        self.conn = duckdb.connect(db_path)
        # TrueSkill environment (default: mu=25, sigma=25/3)
        self.env = trueskill.TrueSkill(draw_probability=0.0)  # No draws in NHL (OT/SO breaks ties)
        self.player_ratings = defaultdict(lambda: self.env.create_rating())
        self.player_names = {}
        self.player_teams = {}
        
    def load_player_info(self):
        """Load player names and basic info."""
        print("📋 Loading player information...")
        
        # Get player names from most recent stats
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
        """
        Calculate a player's performance weight for the game.
        Higher weight = more contribution to team performance.
        """
        # Base weight on ice time
        toi = stats.get('toi_seconds', 0) or 0
        if toi == 0:
            return 0.1  # Minimal weight if no ice time
        
        # Normalize to [0, 1] where 1200 seconds (20 min) = 1.0
        toi_weight = min(toi / 1200.0, 1.5)  # Cap at 1.5 for players with extra ice time
        
        # Performance multipliers
        goals = stats.get('goals', 0) or 0
        assists = stats.get('assists', 0) or 0
        plus_minus = stats.get('plus_minus', 0) or 0
        shots = stats.get('shots', 0) or 0
        
        # Goalie specific
        if stats.get('position') == 'G':
            saves = stats.get('saves', 0) or 0
            ga = stats.get('goals_against', 0) or 0
            save_pct = stats.get('save_pct', 0) or 0
            
            if saves > 0:
                # Goalie weight based on saves and save percentage
                goalie_weight = (saves / 30.0) * (save_pct if save_pct else 0.9)
                return min(goalie_weight, 2.0)  # Goalies can have higher impact
        
        # Skater performance score
        performance = (goals * 3.0 + assists * 2.0 + plus_minus * 0.5 + shots * 0.2)
        
        # Combine TOI weight with performance
        final_weight = toi_weight * (1.0 + performance / 10.0)
        
        return max(min(final_weight, 2.0), 0.1)  # Clamp between 0.1 and 2.0
    
    def process_games(self, start_date=None, end_date=None, limit=None):
        """
        Process games chronologically to update TrueSkill ratings.
        
        Args:
            start_date: Start date (YYYY-MM-DD) or None for all
            end_date: End date (YYYY-MM-DD) or None for latest
            limit: Max number of games to process
        """
        print("\n🏒 Processing NHL games for TrueSkill ratings...")
        
        # Build query
        query = """
        SELECT 
            g.game_id,
            g.game_date,
            g.home_team_id,
            g.away_team_id,
            g.home_score,
            g.away_score
        FROM games g
        WHERE g.game_type = 2  -- Regular season
        AND g.game_state = 'OFF'  -- Finished games only
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
            
            # Get player stats for this game
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
            
            # Group players by team
            home_players = player_stats[player_stats['team_id'] == home_team]
            away_players = player_stats[player_stats['team_id'] == away_team]
            
            if len(home_players) == 0 or len(away_players) == 0:
                continue
            
            # Build rating groups with weights
            home_ratings = []
            away_ratings = []
            
            for _, p_stats in home_players.iterrows():
                player_id = p_stats['player_id']
                weight = self.calculate_player_performance_weight(p_stats.to_dict())
                rating = self.player_ratings[player_id]
                home_ratings.append((rating, weight))
            
            for _, p_stats in away_players.iterrows():
                player_id = p_stats['player_id']
                weight = self.calculate_player_performance_weight(p_stats.to_dict())
                rating = self.player_ratings[player_id]
                away_ratings.append((rating, weight))
            
            # Determine winner (home team = rank 0, away team = rank 1 if home wins)
            if home_score > away_score:
                ranks = [0, 1]  # Home wins
            elif away_score > home_score:
                ranks = [1, 0]  # Away wins
            else:
                # Should not happen (no draws in NHL)
                continue
            
            # Update ratings using TrueSkill
            try:
                # Unpack ratings and weights
                home_rating_list = [r for r, _ in home_ratings]
                away_rating_list = [r for r, _ in away_ratings]
                home_weights = [w for _, w in home_ratings]
                away_weights = [w for _, w in away_ratings]
                
                # Rate the teams
                rated = self.env.rate(
                    [home_rating_list, away_rating_list],
                    ranks=ranks,
                    weights=[home_weights, away_weights]
                )
                
                # Update player ratings
                new_home_ratings, new_away_ratings = rated
                
                for i, (_, p_stats) in enumerate(home_players.iterrows()):
                    player_id = p_stats['player_id']
                    self.player_ratings[player_id] = new_home_ratings[i]
                
                for i, (_, p_stats) in enumerate(away_players.iterrows()):
                    player_id = p_stats['player_id']
                    self.player_ratings[player_id] = new_away_ratings[i]
                
                games_processed += 1
                
                if games_processed % 100 == 0:
                    print(f"  Processed {games_processed}/{len(games_df)} games...")
                
            except Exception as e:
                print(f"⚠️  Error processing game {game_id}: {e}")
                continue
        
        print(f"✅ Processed {games_processed} games")
        print(f"📈 Tracked {len(self.player_ratings)} players")
    
    def get_top_players(self, n=10, min_games=10, position=None):
        """
        Get top N players by TrueSkill rating.
        
        Args:
            n: Number of players to return
            min_games: Minimum games played (based on sigma convergence)
            position: Filter by position ('C', 'LW', 'RW', 'D', 'G') or None for all
        
        Returns:
            DataFrame with top players
        """
        print(f"\n🏆 Top {n} Players by TrueSkill Rating")
        
        results = []
        
        for player_id, rating in self.player_ratings.items():
            # Filter by uncertainty (sigma) - players with sigma > 8.0 haven't played enough
            if rating.sigma > (25/3 - min_games/3):  # Sigma decreases with games played
                continue
            
            player_name = self.player_names.get(player_id, f"Unknown {player_id}")
            team_id = self.player_teams.get(player_id, 'N/A')
            
            # Get player position
            pos_query = f"""
            SELECT position_code 
            FROM players 
            WHERE player_id = {player_id}
            """
            try:
                pos_result = self.conn.execute(pos_query).fetchone()
                player_position = pos_result[0] if pos_result else 'N/A'
            except:
                player_position = 'N/A'
            
            # Filter by position if specified
            if position and player_position != position:
                continue
            
            # TrueSkill metric: conservative skill estimate (mu - 3*sigma)
            conservative_rating = rating.mu - 3 * rating.sigma
            
            results.append({
                'player_id': player_id,
                'player_name': player_name,
                'position': player_position,
                'team_id': team_id,
                'rating_mu': rating.mu,
                'rating_sigma': rating.sigma,
                'conservative_rating': conservative_rating,
                'exposure': rating.exposure
            })
        
        # Sort by conservative rating (mu - 3*sigma)
        df = pd.DataFrame(results)
        if len(df) == 0:
            return df
        
        df = df.sort_values('conservative_rating', ascending=False).head(n)
        
        return df
    
    def get_team_average_rating(self, team_id):
        """Calculate average TrueSkill rating for a team's current roster."""
        query = f"""
        SELECT DISTINCT player_id
        FROM player_game_stats
        WHERE team_id = {team_id}
        ORDER BY game_id DESC
        LIMIT 20  -- Recent players
        """
        
        players = self.conn.execute(query).fetchdf()
        
        if len(players) == 0:
            return None
        
        total_rating = 0
        count = 0
        
        for _, row in players.iterrows():
            player_id = row['player_id']
            if player_id in self.player_ratings:
                rating = self.player_ratings[player_id]
                total_rating += rating.mu - 3 * rating.sigma
                count += 1
        
        return total_rating / count if count > 0 else None
    
    def save_ratings(self, filename='data/nhl_trueskill_ratings.csv'):
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
                'rating_sigma': rating.sigma,
                'conservative_rating': rating.mu - 3 * rating.sigma,
                'exposure': rating.exposure
            })
        
        df = pd.DataFrame(results)
        df = df.sort_values('conservative_rating', ascending=False)
        df.to_csv(filename, index=False)
        
        print(f"\n💾 Saved {len(df)} player ratings to {filename}")
        
        return df


def main():
    """Run TrueSkill rating calculation."""
    print("=" * 80)
    print("🏒 NHL TRUESKILL PLAYER RATINGS")
    print("=" * 80)
    
    # Initialize
    ts = NHLTrueSkill()
    
    # Load player info
    ts.load_player_info()
    
    # Process all games (or specify date range)
    # For faster testing, use: start_date='2024-01-01'
    ts.process_games()
    
    # Get top 10 overall players
    top_players = ts.get_top_players(n=10, min_games=20)
    
    print("\n" + "=" * 80)
    print("🏆 TOP 10 NHL PLAYERS (by TrueSkill Rating)")
    print("=" * 80)
    print(top_players.to_string(index=False))
    
    # Get top goalies
    print("\n" + "=" * 80)
    print("🥅 TOP 5 GOALIES")
    print("=" * 80)
    top_goalies = ts.get_top_players(n=5, min_games=10, position='G')
    if len(top_goalies) > 0:
        print(top_goalies.to_string(index=False))
    else:
        print("No goalies found")
    
    # Get top forwards
    print("\n" + "=" * 80)
    print("🎯 TOP 5 CENTERS")
    print("=" * 80)
    top_centers = ts.get_top_players(n=5, min_games=20, position='C')
    if len(top_centers) > 0:
        print(top_centers.to_string(index=False))
    else:
        print("No centers found")
    
    # Save all ratings
    ts.save_ratings()
    
    print("\n" + "=" * 80)
    print("✅ TrueSkill calculation complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
