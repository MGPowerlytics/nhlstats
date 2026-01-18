"""
Database Loader for NHL, MLB, and NFL data.
Loads JSON/CSV data from daily downloads into normalized DuckDB schema.
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
        """Connect to DuckDB and initialize schema with timeout"""
        import time
        max_retries = 30
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.conn = duckdb.connect(str(self.db_path))
                break
            except Exception as e:
                if 'lock' in str(e).lower() and attempt < max_retries - 1:
                    print(f"  Database locked, waiting {retry_delay}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                else:
                    raise
        
        # Create tables if not exist (NHL)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id VARCHAR PRIMARY KEY,
                season INTEGER,
                game_type VARCHAR,
                game_date DATE,
                start_time_utc TIMESTAMP,
                venue VARCHAR,
                venue_location VARCHAR,
                home_team_id INTEGER,
                home_team_abbrev VARCHAR,
                home_team_name VARCHAR,
                away_team_id INTEGER,
                away_team_abbrev VARCHAR,
                away_team_name VARCHAR,
                home_score INTEGER,
                away_score INTEGER,
                winning_team_id INTEGER,
                losing_team_id INTEGER,
                game_outcome_type VARCHAR,
                game_state VARCHAR,
                period_count INTEGER
            );
            
            CREATE TABLE IF NOT EXISTS teams (
                team_id INTEGER PRIMARY KEY,
                team_abbrev VARCHAR,
                team_name VARCHAR,
                team_common_name VARCHAR
            );

            CREATE TABLE IF NOT EXISTS mlb_games (
                game_id INTEGER PRIMARY KEY,
                game_date DATE,
                season INTEGER,
                game_type VARCHAR,
                home_team VARCHAR,
                away_team VARCHAR,
                home_score INTEGER,
                away_score INTEGER,
                status VARCHAR
            );

            CREATE TABLE IF NOT EXISTS nfl_games (
                game_id VARCHAR PRIMARY KEY,
                game_date DATE,
                season INTEGER,
                week INTEGER,
                game_type VARCHAR,
                home_team VARCHAR,
                away_team VARCHAR,
                home_score INTEGER,
                away_score INTEGER,
                status VARCHAR
            );

            CREATE TABLE IF NOT EXISTS epl_games (
                game_id VARCHAR PRIMARY KEY,
                game_date DATE,
                season VARCHAR,
                home_team VARCHAR,
                away_team VARCHAR,
                home_score INTEGER,
                away_score INTEGER,
                result VARCHAR
            );

            CREATE TABLE IF NOT EXISTS tennis_games (
                game_id VARCHAR PRIMARY KEY,
                game_date DATE,
                season VARCHAR,
                tour VARCHAR,
                tournament VARCHAR,
                surface VARCHAR,
                winner VARCHAR,
                loser VARCHAR,
                score VARCHAR
            );

            CREATE TABLE IF NOT EXISTS ncaab_games (
                game_id VARCHAR PRIMARY KEY,
                game_date DATE,
                season INTEGER,
                home_team VARCHAR,
                away_team VARCHAR,
                home_score INTEGER,
                away_score INTEGER,
                is_neutral BOOLEAN
            );
        """)
        
        print(f"Connected to DuckDB: {self.db_path}")
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            
    def load_date(self, date_str: str, data_dir: Path = Path("data")):
        """Load all NHL data for a specific date"""
        games_loaded = 0
        
        # --- NHL Loading ---
        games_dir = data_dir / "games" / date_str
        if games_dir.exists():
            # Find all game IDs for this date
            game_files = list(games_dir.glob("*_boxscore.json"))
            
            for boxscore_file in game_files:
                game_id = boxscore_file.stem.replace("_boxscore", "")
                
                try:
                    # Load boxscore (game info + stats)
                    self._load_boxscore(game_id, boxscore_file)
                    games_loaded += 1
                    
                except Exception as e:
                    print(f"  Error loading NHL game {game_id}: {e}")
        
        # --- MLB Loading ---
        mlb_dir = data_dir / "mlb"
        # Try to load from date subdirectory first, then fall back to root directory
        mlb_schedule = mlb_dir / date_str / f"schedule_{date_str}.json"
        if not mlb_schedule.exists():
            mlb_schedule = mlb_dir / f"schedule_{date_str}.json"
        
        if mlb_schedule.exists():
            try:
                self._load_mlb_schedule(mlb_schedule)
                print(f"  Loaded MLB schedule for {date_str}")
            except Exception as e:
                print(f"  Error loading MLB schedule for {date_str}: {e}")
                
        # --- NFL Loading ---
        nfl_dir = data_dir / "nfl" / date_str
        nfl_schedule = nfl_dir / f"schedule_{date_str}.json"
        if nfl_schedule.exists():
            try:
                self._load_nfl_schedule(nfl_schedule)
                print(f"  Loaded NFL schedule for {date_str}")
            except Exception as e:
                print(f"  Error loading NFL schedule for {date_str}: {e}")
                
        # --- Other Sports (File-based, load incremental or full) ---
        # For EPL, Tennis, NCAAB, the daily download updates the main CSVs.
        # So we just trigger their loaders which handle "INSERT OR REPLACE".
        
        try:
            self.load_epl_history(target_date=date_str)
            games_loaded += 1
        except Exception as e:
            print(f"  Error loading EPL daily: {e}")
            
        try:
            self.load_tennis_history(target_date=date_str)
            games_loaded += 1
        except Exception as e:
            print(f"  Error loading Tennis daily: {e}")
            
        try:
            self.load_ncaab_history(target_date=date_str)
            games_loaded += 1
        except Exception as e:
            print(f"  Error loading NCAAB daily: {e}")

        return games_loaded

    def _load_mlb_schedule(self, file_path: Path):
        """Load MLB schedule JSON into DuckDB"""
        with open(file_path) as f:
            data = json.load(f)
            
        if 'dates' not in data or not data['dates']:
            return
            
        for game in data['dates'][0].get('games', []):
            try:
                game_pk = game['gamePk']
                game_date_str = game['officialDate']
                season = int(game['season'])
                game_type = game['gameType']
                status = game['status']['abstractGameState']
                
                home_team = game['teams']['home']['team']['name']
                away_team = game['teams']['away']['team']['name']
                
                home_score = game['teams']['home'].get('score')
                away_score = game['teams']['away'].get('score')
                
                self.conn.execute("""
                    INSERT OR REPLACE INTO mlb_games (
                        game_id, game_date, season, game_type,
                        home_team, away_team, home_score, away_score, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_pk, game_date_str, season, game_type,
                    home_team, away_team, home_score, away_score, status
                ))
            except Exception as e:
                print(f"    Error loading MLB game {game.get('gamePk')}: {e}")

    def _load_nfl_schedule(self, file_path: Path):
        """Load NFL schedule JSON into DuckDB"""
        with open(file_path) as f:
            games = json.load(f)
            
        for game in games:
            try:
                game_id = game['game_id']
                season = game['season']
                game_type = game['game_type']
                week = game['week']
                
                # Convert gameday timestamp (ms) to date string
                # Note: some files might have YYYY-MM-DD string, others timestamp
                gameday = game['gameday']
                if isinstance(gameday, (int, float)):
                    # Assuming ms timestamp
                    game_date = datetime.fromtimestamp(gameday / 1000.0).strftime('%Y-%m-%d')
                else:
                    game_date = str(gameday).split('T')[0]
                
                home_team = game['home_team']
                away_team = game['away_team']
                home_score = game.get('home_score')
                away_score = game.get('away_score')
                
                # Infer status
                status = 'Final' if home_score is not None and away_score is not None else 'Scheduled'
                
                self.conn.execute("""
                    INSERT OR REPLACE INTO nfl_games (
                        game_id, game_date, season, week, game_type,
                        home_team, away_team, home_score, away_score, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_id, game_date, season, week, game_type,
                    home_team, away_team, home_score, away_score, status
                ))
            except Exception as e:
                print(f"    Error loading NFL game {game.get('game_id')}: {e}")

    def load_epl_history(self, data_dir: Path = Path("data/epl"), target_date: Optional[str] = None):
        """Load all available EPL CSV data into DuckDB"""
        if not data_dir.exists():
            return
            
        csv_files = list(data_dir.glob("E0_*.csv"))
        for csv_file in csv_files:
            try:
                self._load_epl_csv(csv_file, target_date)
                if not target_date: # Only print on full load to avoid log spam
                    print(f"  Loaded EPL data from {csv_file.name}")
            except Exception as e:
                print(f"  Error loading EPL file {csv_file.name}: {e}")

    def load_tennis_history(self, data_dir: Path = Path("data/tennis"), target_date: Optional[str] = None):
        """Load all available Tennis CSV data into DuckDB"""
        if not data_dir.exists():
            return
            
        csv_files = list(data_dir.glob("*_*.csv")) # matches atp_21.csv, wta_24.csv
        for csv_file in csv_files:
            try:
                self._load_tennis_csv(csv_file, target_date)
                if not target_date:
                    print(f"  Loaded Tennis data from {csv_file.name}")
            except Exception as e:
                print(f"  Error loading Tennis file {csv_file.name}: {e}")

    def load_ncaab_history(self, target_date: Optional[str] = None):
        """Load all available NCAAB data into DuckDB using plugin"""
        from ncaab_games import NCAABGames
        
        try:
            ncaab = NCAABGames()
            # This handles downloading and parsing internally
            df = ncaab.load_games()
            
            if df.empty:
                if not target_date:
                    print("  No NCAAB games found to load.")
                return

            # Filter by date if requested
            if target_date:
                target_dt = datetime.strptime(target_date, '%Y-%m-%d')
                df = df[df['date'] == target_dt]
                if df.empty:
                    return

            if not target_date:
                print(f"  Parsed {len(df)} NCAAB games. Loading into DB...")
            
            # Batch insert for speed
            for _, row in df.iterrows():
                try:
                    game_date = row['date'].strftime('%Y-%m-%d')
                    
                    # Create unique ID: NCAAB_{DATE}_{HOME}_{AWAY}
                    h_slug = "".join(x for x in str(row['home_team']) if x.isalnum())
                    a_slug = "".join(x for x in str(row['away_team']) if x.isalnum())
                    game_id = f"NCAAB_{game_date}_{h_slug}_{a_slug}"
                    
                    self.conn.execute("""
                        INSERT OR REPLACE INTO ncaab_games (
                            game_id, game_date, season,
                            home_team, away_team, home_score, away_score, is_neutral
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game_id, game_date, int(row['season']),
                        row['home_team'], row['away_team'],
                        int(row['home_score']), int(row['away_score']),
                        bool(row['neutral'])
                    ))
                except Exception as e:
                    # Ignore occasional duplicates or data errors
                    pass
                    
            print(f"  Successfully loaded NCAAB history.")
            
        except Exception as e:
            print(f"  Error loading NCAAB history: {e}")

    def _load_tennis_csv(self, file_path: Path, target_date: Optional[str] = None):
        """Load Tennis CSV into DuckDB"""
        import pandas as pd
        
        # Extract metadata (atp_21.csv -> tour=atp, season=21)
        parts = file_path.stem.split('_')
        if len(parts) < 2: return
        tour = parts[0].upper()
        season = parts[1]
        
        try:
            df = pd.read_csv(file_path, encoding='latin1')
        except:
            df = pd.read_csv(file_path)
            
        # Parse dates (DD/MM/YYYY usually)
        if 'Date' not in df.columns: return
        
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        
        if target_date:
            target_dt = datetime.strptime(target_date, '%Y-%m-%d')
            df = df[df['Date'] == target_dt]
            if df.empty:
                return
        
        for _, row in df.iterrows():
            if pd.isna(row['Date']) or pd.isna(row['Winner']) or pd.isna(row['Loser']):
                continue
                
            game_date = row['Date'].strftime('%Y-%m-%d')
            winner = str(row['Winner']).strip()
            loser = str(row['Loser']).strip()
            tournament = str(row.get('Tournament', '')).strip()
            surface = str(row.get('Surface', 'Unknown')).strip()
            score = str(row.get('Score', '')).strip()
            
            # Create unique ID: TENNIS_{TOUR}_{DATE}_{WINNER}_{LOSER}
            # Remove spaces/special chars from names for ID
            w_slug = "".join(x for x in winner if x.isalnum())
            l_slug = "".join(x for x in loser if x.isalnum())
            game_id = f"TENNIS_{tour}_{game_date}_{w_slug}_{l_slug}"
            
            try:
                self.conn.execute("""
                    INSERT OR REPLACE INTO tennis_games (
                        game_id, game_date, season, tour,
                        tournament, surface, winner, loser, score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_id, game_date, season, tour,
                    tournament, surface, winner, loser, score
                ))
            except Exception as e:
                # ignore duplicate key errors if simple retry
                pass

    def _load_epl_csv(self, file_path: Path, target_date: Optional[str] = None):
        """Load EPL CSV into DuckDB"""
        import pandas as pd
        
        # Extract season from filename (E0_2122.csv -> 2122)
        season_code = file_path.stem.replace("E0_", "")
        
        df = pd.read_csv(file_path)
        # Parse dates (DD/MM/YYYY)
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True)
        
        if target_date:
            target_dt = datetime.strptime(target_date, '%Y-%m-%d')
            df = df[df['Date'] == target_dt]
            if df.empty:
                return

        for _, row in df.iterrows():
            if pd.isna(row['FTHG']):
                continue
                
            game_date = row['Date'].strftime('%Y-%m-%d')
            home_team = row['HomeTeam']
            away_team = row['AwayTeam']
            
            # Create unique ID
            game_id = f"EPL_{game_date}_{home_team.replace(' ', '')}_{away_team.replace(' ', '')}"
            
            self.conn.execute("""
                INSERT OR REPLACE INTO epl_games (
                    game_id, game_date, season,
                    home_team, away_team, home_score, away_score, result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id, game_date, season_code,
                home_team, away_team, int(row['FTHG']), int(row['FTAG']), row['FTR']
            ))
        
    def _load_boxscore(self, game_id: str, file_path: Path):
        """Load game info and stats from boxscore JSON"""
        with open(file_path) as f:
            data = json.load(f)
            
        # Extract season (e.g. 20232024 -> 2023)
        season_full = str(data.get('season', ''))
        season = int(season_full[:4]) if len(season_full) >= 4 else None
            
        # Build parameters tuple
        params = (
            game_id,
            season,
            data.get('gameType'),
            data.get('gameDate'),
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
        if data['homeTeam'].get('score') is not None and data['awayTeam'].get('score') is not None:
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
