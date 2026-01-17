"""
NHL TrueSkill Rating System

Implements a TrueSkill-based rating system for NHL players that:
- Tracks individual player skill ratings over time
- Updates ratings based on game outcomes
- Weights player contributions by time on ice
- Handles team ratings as aggregation of player ratings
- Accounts for home ice advantage

TrueSkill represents each player's skill as a Gaussian distribution:
- μ (mu): Mean skill level
- σ (sigma): Uncertainty in skill estimate

For more info: https://www.microsoft.com/en-us/research/project/trueskill-ranking-system/
"""

import trueskill
import duckdb
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict


class NHLTrueSkillRatings:
    """Manage TrueSkill ratings for NHL players"""
    
    def __init__(self, db_path: str = "data/nhlstats.duckdb"):
        """
        Initialize TrueSkill rating system for NHL
        
        Args:
            db_path: Path to DuckDB database with NHL data
        """
        self.db_path = Path(db_path)
        self.conn = None
        
        # TrueSkill environment settings for NHL
        # Using higher draw probability since NHL games can go to OT/SO
        self.env = trueskill.TrueSkill(
            mu=25.0,              # Initial mean skill
            sigma=25.0/3,         # Initial skill uncertainty
            beta=25.0/6,          # Skill variance per level
            tau=25.0/300,         # Dynamics factor (skill change over time)
            draw_probability=0.10, # ~10% of NHL games go to OT/SO
        )
        
        # Player ratings: {player_id: Rating}
        self.player_ratings: Dict[int, trueskill.Rating] = {}
        
        # Rating history: {player_id: [(date, mu, sigma)]}
        self.rating_history: Dict[int, List[Tuple[str, float, float]]] = defaultdict(list)
        
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False
        
    def connect(self):
        """Connect to DuckDB and ensure rating tables exist"""
        self.conn = duckdb.connect(str(self.db_path))
        self._create_rating_tables()
        print(f"Connected to {self.db_path}")
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            
    def _create_rating_tables(self):
        """Create tables to store TrueSkill ratings"""
        
        # Current player ratings table (without foreign key constraint for standalone use)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS player_trueskill_ratings (
                player_id INTEGER PRIMARY KEY,
                mu DOUBLE NOT NULL,
                sigma DOUBLE NOT NULL,
                skill_estimate DOUBLE NOT NULL,  -- mu - 3*sigma (conservative)
                games_played INTEGER DEFAULT 0,
                last_updated TIMESTAMP
            )
        """)
        
        # Rating history table (without foreign key constraints for standalone use)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS player_trueskill_history (
                player_id INTEGER NOT NULL,
                game_id VARCHAR NOT NULL,
                game_date DATE NOT NULL,
                mu_before DOUBLE NOT NULL,
                sigma_before DOUBLE NOT NULL,
                mu_after DOUBLE NOT NULL,
                sigma_after DOUBLE NOT NULL,
                toi_seconds INTEGER,
                team_won BOOLEAN NOT NULL,
                PRIMARY KEY (player_id, game_id)
            )
        """)
        
        # Create indexes for efficient querying
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rating_history_player 
            ON player_trueskill_history(player_id, game_date)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trueskill_skill 
            ON player_trueskill_ratings(skill_estimate DESC)
        """)
        
    def get_or_create_rating(self, player_id: int) -> trueskill.Rating:
        """
        Get player's current rating or create new one with default values
        
        Args:
            player_id: NHL player ID
            
        Returns:
            TrueSkill Rating object
        """
        if player_id not in self.player_ratings:
            # Check if rating exists in database
            result = self.conn.execute("""
                SELECT mu, sigma FROM player_trueskill_ratings 
                WHERE player_id = ?
            """, [player_id]).fetchone()
            
            if result:
                self.player_ratings[player_id] = self.env.create_rating(mu=result[0], sigma=result[1])
            else:
                # Create new rating with default values
                self.player_ratings[player_id] = self.env.create_rating()
                
        return self.player_ratings[player_id]
    
    def calculate_team_rating(self, player_ids: List[int], weights: Optional[List[float]] = None) -> float:
        """
        Calculate team rating as weighted average of player ratings
        
        Args:
            player_ids: List of player IDs on the team
            weights: Optional weights for each player (e.g., TOI proportion)
            
        Returns:
            Team skill estimate (conservative: mu - 3*sigma)
        """
        if not player_ids:
            return self.env.mu  # Default rating
            
        if weights is None:
            weights = [1.0] * len(player_ids)
            
        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            weights = [1.0] * len(player_ids)
            total_weight = len(player_ids)
            
        normalized_weights = [w / total_weight for w in weights]
        
        # Calculate weighted average of skill estimates
        team_skill = 0.0
        for player_id, weight in zip(player_ids, normalized_weights):
            rating = self.get_or_create_rating(player_id)
            # Conservative estimate: mu - 3*sigma
            skill_estimate = rating.mu - 3 * rating.sigma
            team_skill += skill_estimate * weight
            
        return team_skill
    
    def update_game_ratings(self, game_id: str, home_won: bool) -> Tuple[int, int]:
        """
        Update player ratings based on game outcome
        
        Args:
            game_id: NHL game ID
            home_won: Whether home team won (True) or away team won (False)
            
        Returns:
            Tuple of (home_players_updated, away_players_updated)
        """
        # Get game info and player stats
        game_data = self.conn.execute("""
            SELECT 
                g.game_id,
                g.game_date,
                g.home_team_id,
                g.away_team_id,
                g.home_score,
                g.away_score
            FROM games g
            WHERE g.game_id = ?
        """, [game_id]).fetchone()
        
        if not game_data:
            print(f"Game {game_id} not found")
            return 0, 0
            
        game_id, game_date, home_team_id, away_team_id, home_score, away_score = game_data
        
        # Get player stats for this game
        player_stats = self.conn.execute("""
            SELECT 
                player_id,
                team_id,
                toi_seconds,
                toi_goalie_seconds
            FROM player_game_stats
            WHERE game_id = ?
            AND (toi_seconds > 0 OR toi_goalie_seconds > 0)
        """, [game_id]).fetchall()
        
        if not player_stats:
            print(f"No player stats found for game {game_id}")
            return 0, 0
        
        # Organize players by team
        home_players = []
        away_players = []
        home_toi = []
        away_toi = []
        
        for player_id, team_id, toi_skater, toi_goalie in player_stats:
            toi = toi_skater if toi_skater else toi_goalie
            if toi is None or toi == 0:
                continue
                
            if team_id == home_team_id:
                home_players.append(player_id)
                home_toi.append(toi)
            elif team_id == away_team_id:
                away_players.append(player_id)
                away_toi.append(toi)
        
        if not home_players or not away_players:
            print(f"Missing player data for game {game_id}")
            return 0, 0
        
        # Get ratings before update
        home_ratings_before = [self.get_or_create_rating(pid) for pid in home_players]
        away_ratings_before = [self.get_or_create_rating(pid) for pid in away_players]
        
        # Update ratings based on outcome
        if home_won:
            # Home team won
            home_ratings_after, away_ratings_after = self.env.rate(
                [home_ratings_before],
                [away_ratings_before],
                ranks=[0, 1],  # Lower rank = better (winner = 0)
                weights=[home_toi, away_toi]
            )
        else:
            # Away team won
            home_ratings_after, away_ratings_after = self.env.rate(
                [home_ratings_before],
                [away_ratings_before],
                ranks=[1, 0],  # Away team won
                weights=[home_toi, away_toi]
            )
        
        # Update player ratings in memory and database
        for i, player_id in enumerate(home_players):
            self._update_player_rating(
                player_id, 
                home_ratings_before[i],
                home_ratings_after[0][i],
                game_id,
                game_date,
                home_toi[i],
                home_won
            )
            
        for i, player_id in enumerate(away_players):
            self._update_player_rating(
                player_id,
                away_ratings_before[i],
                away_ratings_after[0][i],
                game_id,
                game_date,
                away_toi[i],
                not home_won
            )
        
        return len(home_players), len(away_players)
    
    def _update_player_rating(
        self,
        player_id: int,
        rating_before: trueskill.Rating,
        rating_after: trueskill.Rating,
        game_id: str,
        game_date: str,
        toi_seconds: int,
        team_won: bool
    ):
        """Update player rating in memory and database"""
        
        # Update in-memory rating
        self.player_ratings[player_id] = rating_after
        
        # Update rating history
        self.rating_history[player_id].append((
            game_date,
            rating_after.mu,
            rating_after.sigma
        ))
        
        # Update current rating in database
        skill_estimate = rating_after.mu - 3 * rating_after.sigma
        self.conn.execute("""
            INSERT OR REPLACE INTO player_trueskill_ratings 
            (player_id, mu, sigma, skill_estimate, games_played, last_updated)
            VALUES (?, ?, ?, ?, 
                COALESCE((SELECT games_played FROM player_trueskill_ratings WHERE player_id = ?), 0) + 1,
                CURRENT_TIMESTAMP)
        """, [player_id, rating_after.mu, rating_after.sigma, skill_estimate, player_id])
        
        # Insert into history table
        self.conn.execute("""
            INSERT OR REPLACE INTO player_trueskill_history
            (player_id, game_id, game_date, mu_before, sigma_before, 
             mu_after, sigma_after, toi_seconds, team_won)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            player_id, game_id, game_date,
            rating_before.mu, rating_before.sigma,
            rating_after.mu, rating_after.sigma,
            toi_seconds, team_won
        ])
    
    def process_season(self, season: int, game_type: int = 2) -> Dict[str, int]:
        """
        Process all games in a season to calculate ratings
        
        Args:
            season: Season year (e.g., 2023 for 2023-24 season)
            game_type: 2 = regular season, 3 = playoffs
            
        Returns:
            Dictionary with processing statistics
        """
        # Get all completed games for the season, ordered by date
        games = self.conn.execute("""
            SELECT game_id, home_team_id, away_team_id, home_score, away_score, game_date
            FROM games
            WHERE season = ?
            AND game_type = ?
            AND game_state = 'OFF'
            AND home_score IS NOT NULL
            AND away_score IS NOT NULL
            ORDER BY game_date, game_id
        """, [season, game_type]).fetchall()
        
        stats = {
            'games_processed': 0,
            'games_skipped': 0,
            'players_updated': 0
        }
        
        print(f"Processing {len(games)} games from {season} season (type {game_type})...")
        
        for i, (game_id, home_team_id, away_team_id, home_score, away_score, game_date) in enumerate(games, 1):
            if i % 100 == 0:
                print(f"  Processed {i}/{len(games)} games...")
                
            try:
                home_won = home_score > away_score
                home_updated, away_updated = self.update_game_ratings(game_id, home_won)
                
                if home_updated > 0 and away_updated > 0:
                    stats['games_processed'] += 1
                    stats['players_updated'] += home_updated + away_updated
                else:
                    stats['games_skipped'] += 1
                    
            except Exception as e:
                print(f"  Error processing game {game_id}: {e}")
                stats['games_skipped'] += 1
        
        print(f"Season {season} complete!")
        print(f"  Games processed: {stats['games_processed']}")
        print(f"  Games skipped: {stats['games_skipped']}")
        print(f"  Player ratings updated: {stats['players_updated']}")
        
        return stats
    
    def get_top_players(self, limit: int = 50, min_games: int = 10) -> List[Dict]:
        """
        Get top rated players
        
        Args:
            limit: Number of players to return
            min_games: Minimum games played to be included
            
        Returns:
            List of player info with ratings
        """
        results = self.conn.execute("""
            SELECT 
                r.player_id,
                p.first_name,
                p.last_name,
                p.position_code,
                r.mu,
                r.sigma,
                r.skill_estimate,
                r.games_played,
                r.last_updated
            FROM player_trueskill_ratings r
            JOIN players p ON r.player_id = p.player_id
            WHERE r.games_played >= ?
            ORDER BY r.skill_estimate DESC
            LIMIT ?
        """, [min_games, limit]).fetchall()
        
        top_players = []
        for row in results:
            top_players.append({
                'player_id': row[0],
                'first_name': row[1],
                'last_name': row[2],
                'position': row[3],
                'mu': row[4],
                'sigma': row[5],
                'skill_estimate': row[6],
                'games_played': row[7],
                'last_updated': row[8]
            })
            
        return top_players
    
    def export_ratings(self, output_file: str):
        """
        Export all ratings to JSON file
        
        Args:
            output_file: Path to output JSON file
        """
        results = self.conn.execute("""
            SELECT 
                r.player_id,
                p.first_name,
                p.last_name,
                p.position_code,
                r.mu,
                r.sigma,
                r.skill_estimate,
                r.games_played
            FROM player_trueskill_ratings r
            JOIN players p ON r.player_id = p.player_id
            ORDER BY r.skill_estimate DESC
        """).fetchall()
        
        ratings_data = []
        for row in results:
            ratings_data.append({
                'player_id': row[0],
                'name': f"{row[1]} {row[2]}",
                'position': row[3],
                'mu': row[4],
                'sigma': row[5],
                'skill_estimate': row[6],
                'games_played': row[7]
            })
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(ratings_data, f, indent=2)
            
        print(f"Exported {len(ratings_data)} player ratings to {output_file}")


def main():
    """Example usage of NHL TrueSkill ratings"""
    
    # Initialize rating system
    with NHLTrueSkillRatings() as ratings:
        
        # Process 2023-24 regular season
        stats = ratings.process_season(season=2023, game_type=2)
        
        # Get top 50 players
        print("\n" + "="*80)
        print("TOP 50 NHL PLAYERS BY TRUESKILL RATING")
        print("="*80)
        
        top_players = ratings.get_top_players(limit=50, min_games=20)
        
        for i, player in enumerate(top_players, 1):
            name = f"{player['first_name']} {player['last_name']}"
            pos = player['position'] or '??'
            skill = player['skill_estimate']
            mu = player['mu']
            sigma = player['sigma']
            games = player['games_played']
            
            print(f"{i:2d}. {name:25s} {pos:3s} | "
                  f"Skill: {skill:6.2f} | μ: {mu:6.2f} | σ: {sigma:5.2f} | "
                  f"Games: {games:3d}")
        
        # Export all ratings
        ratings.export_ratings("data/nhl_trueskill_ratings.json")


if __name__ == "__main__":
    main()
