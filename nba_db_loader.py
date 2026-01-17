"""
NBA Data Loader for DuckDB
Loads JSON data from daily downloads into normalized DuckDB schema
"""

import json
from pathlib import Path
from datetime import datetime
import duckdb
from typing import Optional


class NBADatabaseLoader:
    """Load NBA data into DuckDB"""
    
    def __init__(self, db_path: str = "data/nbastats.duckdb"):
        self.db_path = Path(db_path)
        self.conn = None
        
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is always closed"""
        self.close()
        return False
        
    def connect(self):
        """Connect to DuckDB and initialize schema"""
        self.conn = duckdb.connect(str(self.db_path))
        
        # Load schema
        schema_file = Path(__file__).parent / "nba_db_schema.sql"
        with open(schema_file) as f:
            self.conn.execute(f.read())
        
        print(f"Connected to DuckDB: {self.db_path}")
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            
    def load_date(self, date_str: str, data_dir: Path = Path("data")):
        """Load all NBA data for a specific date"""
        games_dir = data_dir / "nba" / date_str
        
        if not games_dir.exists():
            print(f"No NBA data found for {date_str}")
            return 0
            
        # Load scoreboard to get game list
        scoreboard_file = games_dir / f"scoreboard_{date_str}.json"
        if not scoreboard_file.exists():
            print(f"No scoreboard found for {date_str}")
            return 0
            
        with open(scoreboard_file) as f:
            scoreboard = json.load(f)
        
        # Extract game IDs from scoreboard
        game_ids = []
        if 'resultSets' in scoreboard:
            for result_set in scoreboard['resultSets']:
                if result_set['name'] == 'GameHeader':
                    headers = result_set['headers']
                    game_id_idx = headers.index('GAME_ID')
                    game_date_idx = headers.index('GAME_DATE_EST')
                    home_team_idx = headers.index('HOME_TEAM_ID')
                    visitor_team_idx = headers.index('VISITOR_TEAM_ID')
                    game_status_idx = headers.index('GAME_STATUS_TEXT')
                    
                    for row in result_set['rowSet']:
                        game_id = str(row[game_id_idx])
                        game_ids.append(game_id)
                        
                        # Insert game record
                        self._insert_game(
                            game_id=game_id,
                            game_date=date_str,
                            game_status=row[game_status_idx],
                            home_team_id=row[home_team_idx],
                            away_team_id=row[visitor_team_idx]
                        )
        
        print(f"  Found {len(game_ids)} games for {date_str}")
        
        # Load boxscore and play-by-play for each game
        for game_id in game_ids:
            self._load_boxscore(game_id, games_dir)
            self._load_playbyplay(game_id, games_dir)
        
        return len(game_ids)
    
    def _insert_game(self, game_id, game_date, game_status, home_team_id, away_team_id):
        """Insert or update game record"""
        # Determine if playoffs based on game ID (playoffs start with 004)
        playoffs = game_id.startswith('004')
        
        # Extract season from game_id (first 4 digits after '00' or '004')
        season = f"20{game_id[3:5]}-{int(game_id[3:5]) + 1}"
        
        self.conn.execute("""
            INSERT OR REPLACE INTO games 
            (game_id, game_date, season, game_status, home_team_id, away_team_id, playoffs)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [game_id, game_date, season, game_status, home_team_id, away_team_id, playoffs])
    
    def _load_boxscore(self, game_id, games_dir):
        """Load boxscore data for a game"""
        boxscore_file = games_dir / f"boxscore_{game_id}.json"
        if not boxscore_file.exists():
            return
        
        try:
            with open(boxscore_file) as f:
                boxscore = json.load(f)
            
            if 'resultSets' not in boxscore:
                return
            
            # Find PlayerStats and TeamStats result sets
            for result_set in boxscore['resultSets']:
                if result_set['name'] == 'PlayerStats':
                    self._insert_player_stats(game_id, result_set)
                elif result_set['name'] == 'TeamStats':
                    self._insert_team_stats(game_id, result_set)
                    
        except Exception as e:
            print(f"    Warning: Error loading boxscore for {game_id}: {e}")
    
    def _insert_player_stats(self, game_id, result_set):
        """Insert player stats from boxscore"""
        headers = result_set['headers']
        
        # Map headers to indices
        indices = {h: i for i, h in enumerate(headers)}
        
        for row in result_set['rowSet']:
            try:
                self.conn.execute("""
                    INSERT INTO player_stats 
                    (game_id, team_id, player_id, player_name, start_position, minutes,
                     fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct,
                     oreb, dreb, reb, ast, stl, blk, turnover, pf, pts, plus_minus)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    game_id,
                    row[indices.get('TEAM_ID', 0)],
                    row[indices.get('PLAYER_ID', 1)],
                    row[indices.get('PLAYER_NAME', 2)],
                    row[indices.get('START_POSITION', 3)],
                    row[indices.get('MIN', 4)],
                    row[indices.get('FGM', 5)],
                    row[indices.get('FGA', 6)],
                    row[indices.get('FG_PCT', 7)],
                    row[indices.get('FG3M', 8)],
                    row[indices.get('FG3A', 9)],
                    row[indices.get('FG3_PCT', 10)],
                    row[indices.get('FTM', 11)],
                    row[indices.get('FTA', 12)],
                    row[indices.get('FT_PCT', 13)],
                    row[indices.get('OREB', 14)],
                    row[indices.get('DREB', 15)],
                    row[indices.get('REB', 16)],
                    row[indices.get('AST', 17)],
                    row[indices.get('STL', 18)],
                    row[indices.get('BLK', 19)],
                    row[indices.get('TO', 20)],
                    row[indices.get('PF', 21)],
                    row[indices.get('PTS', 22)],
                    row[indices.get('PLUS_MINUS', 23)]
                ])
            except Exception as e:
                print(f"      Warning: Error inserting player stat: {e}")
    
    def _insert_team_stats(self, game_id, result_set):
        """Insert team stats from boxscore"""
        headers = result_set['headers']
        indices = {h: i for i, h in enumerate(headers)}
        
        for row in result_set['rowSet']:
            try:
                self.conn.execute("""
                    INSERT INTO team_stats 
                    (game_id, team_id, team_name, team_abbreviation,
                     fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct,
                     oreb, dreb, reb, ast, stl, blk, turnover, pf, pts, plus_minus)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    game_id,
                    row[indices.get('TEAM_ID', 0)],
                    row[indices.get('TEAM_NAME', 1)],
                    row[indices.get('TEAM_ABBREVIATION', 2)],
                    row[indices.get('FGM', 3)],
                    row[indices.get('FGA', 4)],
                    row[indices.get('FG_PCT', 5)],
                    row[indices.get('FG3M', 6)],
                    row[indices.get('FG3A', 7)],
                    row[indices.get('FG3_PCT', 8)],
                    row[indices.get('FTM', 9)],
                    row[indices.get('FTA', 10)],
                    row[indices.get('FT_PCT', 11)],
                    row[indices.get('OREB', 12)],
                    row[indices.get('DREB', 13)],
                    row[indices.get('REB', 14)],
                    row[indices.get('AST', 15)],
                    row[indices.get('STL', 16)],
                    row[indices.get('BLK', 17)],
                    row[indices.get('TO', 18)],
                    row[indices.get('PF', 19)],
                    row[indices.get('PTS', 20)],
                    row[indices.get('PLUS_MINUS', 21)]
                ])
            except Exception as e:
                print(f"      Warning: Error inserting team stat: {e}")
    
    def _load_playbyplay(self, game_id, games_dir):
        """Load play-by-play data for a game"""
        pbp_file = games_dir / f"playbyplay_{game_id}.json"
        if not pbp_file.exists():
            return
        
        try:
            with open(pbp_file) as f:
                pbp_data = json.load(f)
            
            # NBA CDN format
            if 'game' in pbp_data and 'actions' in pbp_data['game']:
                actions = pbp_data['game']['actions']
                
                for action in actions:
                    self._insert_play_event(game_id, action)
                    
        except Exception as e:
            print(f"    Warning: Error loading play-by-play for {game_id}: {e}")
    
    def _insert_play_event(self, game_id, action):
        """Insert a single play-by-play event"""
        try:
            self.conn.execute("""
                INSERT INTO play_by_play 
                (game_id, action_number, period, clock, time_actual, team_id,
                 player_id, player_name, action_type, sub_type, description,
                 score_home, score_away, shot_result, shot_distance, shot_x, shot_y,
                 assist_player_id, assist_player_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                game_id,
                action.get('actionNumber'),
                action.get('period'),
                action.get('clock'),
                action.get('timeActual'),
                action.get('teamId'),
                action.get('personId'),
                action.get('playerNameI') or action.get('playerName'),
                action.get('actionType'),
                action.get('subType'),
                action.get('description'),
                action.get('scoreHome'),
                action.get('scoreAway'),
                action.get('shotResult'),
                action.get('shotDistance'),
                action.get('x'),
                action.get('y'),
                action.get('assistPersonId'),
                action.get('assistPlayerNameInitial')
            ])
        except Exception as e:
            print(f"      Warning: Error inserting play event: {e}")


def load_nba_data_for_date(date_str: str, db_path: str = "data/nbastats.duckdb"):
    """
    Load all NBA data for a specific date into DuckDB
    
    Args:
        date_str: Date in YYYY-MM-DD format
        db_path: Path to DuckDB database file
        
    Returns:
        Number of games loaded
    """
    with NBADatabaseLoader(db_path) as loader:
        games_count = loader.load_date(date_str)
        print(f"Loaded {games_count} games for {date_str}")
        return games_count


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python nba_db_loader.py YYYY-MM-DD")
        sys.exit(1)
    
    date = sys.argv[1]
    load_nba_data_for_date(date)
