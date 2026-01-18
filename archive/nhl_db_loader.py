"""
NHL Data Loader for DuckDB
Loads JSON/CSV data from daily downloads into normalized DuckDB schema
"""

import json
import csv
from pathlib import Path
from datetime import datetime
import duckdb
from typing import Optional


class NHLDatabaseLoader:
    """Load NHL data into DuckDB"""
    
    def __init__(self, db_path: str = "data/nhlstats.duckdb"):
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
        schema_file = Path(__file__).parent / "nhl_db_schema.sql"
        with open(schema_file) as f:
            self.conn.execute(f.read())
        
        print(f"Connected to DuckDB: {self.db_path}")
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            
    def load_date(self, date_str: str, data_dir: Path = Path("data")):
        """Load all NHL data for a specific date"""
        games_dir = data_dir / "games" / date_str
        shifts_dir = data_dir / "shifts" / date_str
        
        if not games_dir.exists():
            print(f"No game data found for {date_str}")
            return 0
            
        games_loaded = 0
        
        # Find all game IDs for this date
        game_files = list(games_dir.glob("*_boxscore.json"))
        
        for boxscore_file in game_files:
            game_id = boxscore_file.stem.replace("_boxscore", "")
            
            try:
                # Load boxscore (game info + stats)
                self._load_boxscore(game_id, boxscore_file)
                
                # Load play-by-play
                pbp_file = games_dir / f"{game_id}_playbyplay.json"
                if pbp_file.exists():
                    self._load_playbyplay(game_id, pbp_file)
                    
                # Load shifts
                shifts_file = shifts_dir / f"{game_id}_shifts.csv"
                if shifts_file.exists():
                    self._load_shifts(game_id, shifts_file)
                    
                games_loaded += 1
                print(f"  Loaded game {game_id}")
                
            except Exception as e:
                print(f"  Error loading game {game_id}: {e}")
                
        return games_loaded
        
    def _load_boxscore(self, game_id: str, file_path: Path):
        """Load game info and stats from boxscore JSON"""
        with open(file_path) as f:
            data = json.load(f)
            
        # Build parameters tuple
        params = (
            game_id,
            data['season'],
            data['gameType'],
            data['gameDate'],
            data.get('startTimeUTC'),
            data.get('venue', {}).get('default'),
            data.get('venueLocation', {}).get('default'),
            data['homeTeam']['id'],
            data['homeTeam']['abbrev'],
            f"{data['homeTeam'].get('placeName', {}).get('default', '')} {data['homeTeam'].get('commonName', {}).get('default', '')}".strip(),
            data['awayTeam']['id'],
            data['awayTeam']['abbrev'],
            f"{data['awayTeam'].get('placeName', {}).get('default', '')} {data['awayTeam'].get('commonName', {}).get('default', '')}".strip(),
            data['homeTeam'].get('score'),
            data['awayTeam'].get('score'),
            None,  # winning_team_id (computed below)
            None,  # losing_team_id
            data.get('gameOutcome', {}).get('lastPeriodType'),
            data.get('gameState'),
            data.get('periodDescriptor', {}).get('number'),
        )
        
        # Insert game record
        self.conn.execute('''INSERT INTO games (
            game_id, season, game_type, game_date, start_time_utc,
            venue, venue_location,
            home_team_id, home_team_abbrev, home_team_name,
            away_team_id, away_team_abbrev, away_team_name,
            home_score, away_score,
            winning_team_id, losing_team_id, game_outcome_type,
            game_state, period_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (game_id) DO UPDATE SET
            season=excluded.season, game_type=excluded.game_type,
            game_date=excluded.game_date, home_score=excluded.home_score,
            away_score=excluded.away_score, game_state=excluded.game_state
        ''', params)
        
        # Update winning/losing teams
        if data['homeTeam'].get('score') and data['awayTeam'].get('score'):
            if data['homeTeam']['score'] > data['awayTeam']['score']:
                winning_team = data['homeTeam']['id']
                losing_team = data['awayTeam']['id']
            else:
                winning_team = data['awayTeam']['id']
                losing_team = data['homeTeam']['id']
                
            self.conn.execute("""
                UPDATE games 
                SET winning_team_id = ?, losing_team_id = ?
                WHERE game_id = ?
            """, (winning_team, losing_team, game_id))
        
        # Insert teams if not exists
        for team_key in ['homeTeam', 'awayTeam']:
            team = data[team_key]
            team_name = f"{team.get('placeName', {}).get('default', '')} {team.get('commonName', {}).get('default', '')}".strip()
            self.conn.execute("""
                INSERT OR IGNORE INTO teams (team_id, team_abbrev, team_name, team_common_name)
                VALUES (?, ?, ?, ?)
            """, (
                team['id'],
                team['abbrev'],
                team_name,
                team.get('commonName', {}).get('default')
            ))
            
        # Load team stats
        self._load_team_stats(game_id, data)
        
        # Load player stats
        self._load_player_stats(game_id, data)
        
    def _load_team_stats(self, game_id: str, data: dict):
        """Load team-level stats from boxscore"""
        for team_key, is_home in [('homeTeam', True), ('awayTeam', False)]:
            team = data[team_key]
            
            # Extract stats from summary
            if 'summary' in data and team_key in data['summary']:
                stats = data['summary'][team_key]
                
                self.conn.execute("""
                    INSERT OR REPLACE INTO game_team_stats VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    game_id,
                    team['id'],
                    is_home,
                    team.get('score'),
                    stats.get('sog'),  # shots on goal
                    stats.get('blockedShots'),
                    stats.get('powerPlayGoals'),
                    stats.get('powerPlayOpportunities'),
                    stats.get('powerPlayPct'),
                    stats.get('penaltyKillPct'),
                    stats.get('pim'),
                    stats.get('faceoffWinningPctg'),
                    stats.get('hits'),
                ))
                
    def _load_player_stats(self, game_id: str, data: dict):
        """Load player-level stats from boxscore"""
        if 'playerByGameStats' not in data:
            return
            
        for team_key in ['awayTeam', 'homeTeam']:
            if team_key not in data['playerByGameStats']:
                continue
                
            team_data = data['playerByGameStats'][team_key]
            team_id = data[team_key]['id']
            
            # Process forwards and defense
            for position_group in ['forwards', 'defense', 'goalies']:
                if position_group not in team_data:
                    continue
                    
                for player in team_data[position_group]:
                    self._insert_player(player, team_id)
                    self._insert_player_game_stats(game_id, player, team_id, position_group)
                    
    def _insert_player(self, player: dict, team_id: int):
        """Insert or update player master record"""
        self.conn.execute("""
            INSERT OR IGNORE INTO players (
                player_id, first_name, last_name, sweater_number, position_code
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            player['playerId'],
            player.get('firstName', {}).get('default'),
            player.get('lastName', {}).get('default'),
            player.get('sweaterNumber'),
            player.get('positionCode')
        ))
        
    def _insert_player_game_stats(self, game_id: str, player: dict, team_id: int, position_group: str):
        """Insert player game statistics"""
        if position_group == 'goalies':
            # Goalie stats
            self.conn.execute("""
                INSERT OR REPLACE INTO player_game_stats (
                    game_id, player_id, team_id, position,
                    shots_against, goals_against, saves, save_pct, toi_goalie_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                player['playerId'],
                team_id,
                player.get('positionCode'),
                player.get('shotsAgainst'),
                player.get('goalsAgainst'),
                player.get('saves'),
                player.get('savePctg'),
                self._parse_toi(player.get('toi'))
            ))
        else:
            # Skater stats
            self.conn.execute("""
                INSERT OR REPLACE INTO player_game_stats (
                    game_id, player_id, team_id, position,
                    goals, assists, points, plus_minus, shots, hits, blocked_shots, pim,
                    toi_seconds, power_play_goals, power_play_points, shorthanded_goals,
                    game_winning_goals, faceoff_wins, faceoff_attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                player['playerId'],
                team_id,
                player.get('positionCode'),
                player.get('goals', 0),
                player.get('assists', 0),
                player.get('points', 0),
                player.get('plusMinus', 0),
                player.get('shots', 0),
                player.get('hits', 0),
                player.get('blockedShots', 0),
                player.get('pim', 0),
                self._parse_toi(player.get('toi')),
                player.get('powerPlayGoals', 0),
                player.get('powerPlayPoints', 0),
                player.get('shorthandedGoals', 0),
                player.get('gameWinningGoals', 0),
                player.get('faceoffWins', 0),
                player.get('faceoffs', 0)
            ))
            
    def _load_playbyplay(self, game_id: str, file_path: Path):
        """Load play-by-play events"""
        with open(file_path) as f:
            data = json.load(f)
            
        if 'plays' not in data:
            return
            
        for play in data['plays']:
            # Extract player IDs for goals
            scoring_player_id = None
            assist1_player_id = None
            assist2_player_id = None
            
            if 'details' in play and 'scoringPlayerId' in play['details']:
                scoring_player_id = play['details']['scoringPlayerId']
                if 'assists' in play['details'] and len(play['details']['assists']) > 0:
                    assist1_player_id = play['details']['assists'][0].get('playerId')
                    if len(play['details']['assists']) > 1:
                        assist2_player_id = play['details']['assists'][1].get('playerId')
                        
            self.conn.execute("""
                INSERT OR IGNORE INTO play_events (
                    event_id, game_id, period, period_type, time_in_period, time_remaining,
                    sort_order, type_code, type_desc_key, event_owner_team_id,
                    scoring_player_id, assist1_player_id, assist2_player_id, shot_type,
                    penalty_player_id, penalty_type, penalty_duration,
                    x_coord, y_coord, zone_code, home_team_defending_side,
                    away_score, home_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                play['eventId'],
                game_id,
                play['periodDescriptor']['number'],
                play['periodDescriptor'].get('periodType'),
                play.get('timeInPeriod'),
                play.get('timeRemaining'),
                play.get('sortOrder'),
                play['typeCode'],
                play['typeDescKey'],
                play.get('details', {}).get('eventOwnerTeamId'),
                scoring_player_id,
                assist1_player_id,
                assist2_player_id,
                play.get('details', {}).get('shotType'),
                play.get('details', {}).get('committedByPlayerId'),  # penalty player
                play.get('details', {}).get('descKey'),  # penalty type
                play.get('details', {}).get('duration'),  # penalty duration
                play.get('details', {}).get('xCoord'),
                play.get('details', {}).get('yCoord'),
                play.get('details', {}).get('zoneCode'),
                play.get('homeTeamDefendingSide'),
                play.get('awayScore'),
                play.get('homeScore')
            ))
            
    def _load_shifts(self, game_id: str, file_path: Path):
        """Load player shift data from CSV"""
        with open(file_path, newline='') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                shift_id = f"{game_id}_{row['id']}"
                
                self.conn.execute("""
                    INSERT OR IGNORE INTO player_shifts (
                        shift_id, game_id, player_id, team_id, period, shift_number,
                        start_time, end_time, duration, event_number, event_description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    shift_id,
                    game_id,
                    int(row['playerId']),
                    int(row['teamId']),
                    int(row['period']),
                    int(row['shiftNumber']),
                    row['startTime'],
                    row['endTime'],
                    row['duration'],
                    row.get('eventNumber') if row.get('eventNumber') else None,
                    row.get('eventDescription')
                ))
                
    def _parse_toi(self, toi_str: Optional[str]) -> Optional[int]:
        """Parse time on ice string (MM:SS) to seconds"""
        if not toi_str:
            return None
        try:
            parts = toi_str.split(':')
            return int(parts[0]) * 60 + int(parts[1])
        except:
            return None
            

def load_nhl_data_for_date(date_str: str, db_path: str = "data/nhlstats.duckdb"):
    """
    Load all NHL data for a specific date into DuckDB
    
    Args:
        date_str: Date in YYYY-MM-DD format
        db_path: Path to DuckDB database file
        
    Returns:
        Number of games loaded
    """
    with NHLDatabaseLoader(db_path) as loader:
        games_count = loader.load_date(date_str)
        print(f"Loaded {games_count} games for {date_str}")
        return games_count


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python nhl_db_loader.py YYYY-MM-DD")
        sys.exit(1)
        
    date_str = sys.argv[1]
    load_nhl_data_for_date(date_str)
