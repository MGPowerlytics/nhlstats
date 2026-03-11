"""
Database Loader for NHL, MLB, and NFL data.
Loads JSON/CSV data from daily downloads into normalized PostgreSQL schema.
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Dict, Callable
from plugins.db_manager import DBManager, default_db
from database_schema_manager import DatabaseSchemaManager
from nba_data_loader import NBADataLoader
from plugins.utils import create_entity_upserter, get_nested_value
from csv_history_loader import CSVHistoryLoader


from sqlalchemy import text


class LegacyConnWrapper:
    """Wrapper for SQLAlchemy connection to maintain execute() syntax in tests."""

    def __init__(self, connection: Any) -> None:
        self._conn = connection

    def execute(self, query: str, params: Optional[dict] = None) -> Any:
        if isinstance(query, str):
            # Basic translation for common test queries
            sql = query.strip().upper()
            if sql == "SHOW TABLES":
                query = "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
            elif sql.startswith("DESCRIBE "):
                table = query.split()[1].strip('"').strip("'")
                query = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table.lower()}'"
            elif "INSERT OR REPLACE" in sql:
                query = query.replace("INSERT OR REPLACE", "INSERT")

            query = text(query)

        try:
            res = self._conn.execute(query, params or {})
            try:
                self._conn.commit()
            except Exception:
                pass
            return res
        except Exception:
            # For tests expecting duckdb exceptions, we might need more mapping
            raise

    def commit(self):
        try:
            self._conn.commit()
        except Exception:
            pass

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def close(self):
        self._conn.close()

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying connection."""
        return getattr(self._conn, name)


class DatabaseLoaderBase:
    """Base class for database loading operations with connection management."""

    def __init__(
        self, db_path: Optional[str] = None, db_manager: Optional[DBManager] = None, sport: Optional[str] = None
    ) -> None:
        # Store db_path for tests that check loader.db_path
        self.db_path = Path(db_path) if db_path else Path("data/nhlstats.duckdb")
        self._conn = None
        self._schema_initialized = False
        self.db = db_manager or default_db
        self.sport = sport.lower() if sport else None

    @property
    def conn(self):
        """Mock connection property for tests"""
        if not self._schema_initialized:
            self.connect()
        if self._conn is None:
            self._conn = LegacyConnWrapper(self.db.engine.connect())
        return self._conn

    def __enter__(self) -> "DatabaseLoaderBase":
        """Context manager enter method."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[Any],
    ) -> bool:
        """Context manager exit method."""
        self.close()
        return False

    def connect(self) -> None:
        """Initialize schema if tables don't exist"""
        if self._schema_initialized:
            return

        # For PostgreSQL, we rely on external schema initialization
        # This method exists for backward compatibility with tests
        self._schema_initialized = True

    def close(self) -> None:
        """Close database connection"""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


class NHLDatabaseLoader(DatabaseLoaderBase):
    """Load sports data into PostgreSQL"""

    def __init__(
        self, db_path: Optional[str] = None, db_manager: Optional[DBManager] = None
    ) -> None:
        """Initialize NHL database loader with schema manager.

        Args:
            db_path: Optional database path (for backward compatibility)
            db_manager: Optional database manager instance
        """
        super().__init__(db_path, db_manager)
        self.schema_manager = DatabaseSchemaManager(self.db)

        # Create CSV history loader for CSV data processing
        self.csv_loader = CSVHistoryLoader(self.db)

        # Create reusable upsert function for game data
        self._upsert_game_data = create_entity_upserter(
            table_name="games",
            conflict_column="game_id",
            update_columns=[
                "season",
                "game_type",
                "game_date",
                "home_score",
                "away_score",
                "game_state",
            ],
        )

    def connect(self):
        """Initialize schema if tables don't exist"""
        if self._schema_initialized:
            return

        # Use schema manager to initialize tables
        self.schema_manager.initialize_schema()
        self._schema_initialized = True

    def _load_nhl_date(self, date_str: str, data_dir: Path) -> int:
        """Load NHL boxscores for a specific date."""
        games_loaded = 0
        games_dir = data_dir / "games" / date_str
        if games_dir.exists():
            game_files = list(games_dir.glob("*_boxscore.json"))
            for boxscore_file in game_files:
                game_id = boxscore_file.stem.replace("_boxscore", "")
                try:
                    self._load_boxscore(game_id, boxscore_file)
                    games_loaded += 1
                except Exception as e:
                    print(f"  Error loading NHL game {game_id}: {e}")
        return games_loaded

    def _load_sport_json_date(
        self,
        sport: str,
        date_str: str,
        data_dir: Path,
        loader_func: Callable,
        filename_prefix: str = "schedule",
    ) -> int:
        """Generic loader for sports with JSON date-based schedules/scoreboards."""
        sport_dir = data_dir / sport / date_str
        schedule_file = sport_dir / f"{filename_prefix}_{date_str}.json"

        # Fallback to direct sport directory (some legacy structures)
        if not schedule_file.exists():
            schedule_file = data_dir / sport / f"{filename_prefix}_{date_str}.json"

        if schedule_file.exists():
            try:
                loader_func(schedule_file)
                print(f"  Loaded {sport.upper()} {filename_prefix} for {date_str}")
                return 1
            except Exception as e:
                print(
                    f"  Error loading {sport.upper()} {filename_prefix} for {date_str}: {e}"
                )
        return 0

    def _load_nba_date(self, date_str: str, data_dir: Path) -> int:
        """Load NBA scoreboard for a specific date."""
        # Create NBA data loader instance
        nba_loader = NBADataLoader(self.db)

        # Create wrapper function that uses NBADataLoader
        def load_nba_scoreboard_wrapper(file_path: Path) -> None:
            nba_loader.load_nba_scoreboard(file_path)

        return self._load_sport_json_date(
            "nba", date_str, data_dir, load_nba_scoreboard_wrapper, "scoreboard"
        )

    def load_date(self, date_str: str, data_dir: Path = Path("data")) -> int:
        """Load all sports data for a specific date"""
        games_loaded = 0

        # Primary sports with structured JSON directories
        games_loaded += self._load_nhl_date(date_str, data_dir)
        games_loaded += self._load_nba_date(date_str, data_dir)
        games_loaded += self._load_sport_json_date(
            "mlb", date_str, data_dir, self._load_mlb_schedule
        )
        games_loaded += self._load_sport_json_date(
            "nfl", date_str, data_dir, self._load_nfl_schedule
        )

        # Other sports using history loaders
        history_loaders = [
            ("EPL", lambda: self.load_csv_history("EPL", target_date=date_str)),
            ("Tennis", lambda: self.load_csv_history("Tennis", target_date=date_str)),
            ("NCAAB", lambda: self.load_ncaab_history(target_date=date_str)),
        ]

        for sport_name, loader_func in history_loaders:
            try:
                loader_func()
                games_loaded += 1
            except Exception as e:
                print(f"  Error loading {sport_name} daily: {e}")

        return games_loaded

    def _load_mlb_schedule(self, file_path: Path):
        """Load MLB schedule JSON into PostgreSQL"""
        with open(file_path) as f:
            data = json.load(f)

        if "dates" not in data or not data["dates"]:
            return

        for game in data["dates"][0].get("games", []):
            try:
                params = {
                    "game_id": game["gamePk"],
                    "game_date": game["officialDate"],
                    "season": int(game["season"]),
                    "game_type": game["gameType"],
                    "home_team": game["teams"]["home"]["team"]["name"],
                    "away_team": game["teams"]["away"]["team"]["name"],
                    "home_score": game["teams"]["home"].get("score"),
                    "away_score": game["teams"]["away"].get("score"),
                    "status": game["status"]["abstractGameState"],
                }

                self.db.execute(
                    """
                    INSERT INTO mlb_games (
                        game_id, game_date, season, game_type,
                        home_team, away_team, home_score, away_score, status
                    ) VALUES (:game_id, :game_date, :season, :game_type, :home_team, :away_team, :home_score, :away_score, :status)
                    ON CONFLICT (game_id) DO UPDATE SET
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score,
                        status = EXCLUDED.status
                """,
                    params,
                )
            except Exception as e:
                print(f"    Error loading MLB game {game.get('gamePk')}: {e}")

    def _load_nfl_schedule(self, file_path: Path):
        """Load NFL schedule JSON into PostgreSQL"""
        with open(file_path) as f:
            games = json.load(f)

        for game in games:
            try:
                gameday = game["gameday"]
                if isinstance(gameday, (int, float)):
                    game_date = datetime.fromtimestamp(gameday / 1000.0).strftime(
                        "%Y-%m-%d"
                    )
                else:
                    game_date = str(gameday).split("T")[0]

                params = {
                    "game_id": game["game_id"],
                    "game_date": game_date,
                    "season": game["season"],
                    "week": game["week"],
                    "game_type": game["game_type"],
                    "home_team": game["home_team"],
                    "away_team": game["away_team"],
                    "home_score": game.get("home_score"),
                    "away_score": game.get("away_score"),
                    "status": "Final"
                    if game.get("home_score") is not None
                    else "Scheduled",
                }

                self.db.execute(
                    """
                    INSERT INTO nfl_games (
                        game_id, game_date, season, week, game_type,
                        home_team, away_team, home_score, away_score, status
                    ) VALUES (:game_id, :game_date, :season, :week, :game_type, :home_team, :away_team, :home_score, :away_score, :status)
                    ON CONFLICT (game_id) DO UPDATE SET
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score,
                        status = EXCLUDED.status
                """,
                    params,
                )
            except Exception as e:
                print(f"    Error loading NFL game {game.get('game_id')}: {e}")

    def _load_history_from_dir(
        self,
        data_dir: Path,
        pattern: str,
        loader_func: Any,
        sport_name: str,
        target_date: Optional[str] = None,
    ):
        """Generic CSV history loader to reduce code duplication."""
        # Delegate to CSVHistoryLoader
        self.csv_loader._load_history_from_dir(
            data_dir, pattern, loader_func, sport_name, target_date
        )

    def _get_csv_history_config(self, sport: str) -> Dict[str, Any]:
        """Get configuration for CSV history loading for a specific sport.

        Args:
            sport: Sport name ("EPL" or "Tennis")

        Returns:
            Dictionary with keys: data_dir, pattern, loader_func, sport_name
        """
        # Delegate to CSVHistoryLoader
        return self.csv_loader._get_csv_history_config(sport)

    def load_csv_history(
        self,
        sport: str,
        data_dir: Optional[Path] = None,
        target_date: Optional[str] = None,
    ) -> None:
        """Load all available CSV data for a specific sport into PostgreSQL.

        Args:
            sport: Sport name ("EPL" or "Tennis")
            data_dir: Optional directory containing CSV files. If None, uses default from config.
            target_date: Optional date filter in YYYY-MM-DD format.
        """
        # Delegate to CSVHistoryLoader
        self.csv_loader.load_csv_history(sport, data_dir, target_date)

    def load_ncaab_history(self, target_date: Optional[str] = None) -> None:
        """Load all available NCAAB data into PostgreSQL"""
        from ncaab_games import NCAABGames

        try:
            ncaab = NCAABGames()
            df = ncaab.load_games()
            if df.empty:
                return

            if target_date:
                target_dt = datetime.strptime(target_date, "%Y-%m-%d")
                df = df[df["date"] == target_dt]
                if df.empty:
                    return

            for _, row in df.iterrows():
                self._process_ncaab_row(row)
        except Exception as e:
            print(f"  Error loading NCAAB history: {e}")

    def _process_csv_row(self, sport: str, row: pd.Series, **kwargs) -> None:
        """
        Process a single CSV game row and upsert into database.

        Args:
            sport: Sport name (e.g., 'ncaab', 'tennis', 'epl')
            row: Pandas Series containing game data
            **kwargs: Additional parameters to pass to the processor
        """
        # Delegate to CSVHistoryLoader
        self.csv_loader._process_csv_row(sport, row, **kwargs)

    def _process_ncaab_row(self, row: pd.Series) -> None:
        """Process a single NCAAB game row and upsert into database."""
        # Delegate to CSVHistoryLoader
        self.csv_loader._process_ncaab_row(row)

    def _load_sport_csv_file(
        self, sport: str, file_path: Path, target_date: Optional[str] = None
    ) -> None:
        """Load sport CSV file into PostgreSQL.

        Args:
            sport: Sport name (e.g., 'tennis', 'epl')
            file_path: Path to the CSV file
            target_date: Optional date filter in YYYY-MM-DD format
        """
        # Delegate to CSVHistoryLoader
        self.csv_loader._load_csv_for_sport(sport, file_path, target_date)

    def _load_boxscore_data(self, file_path: Path) -> Dict[str, Any]:
        """Load boxscore JSON data from file.

        Args:
            file_path: Path to the boxscore JSON file

        Returns:
            Dictionary containing the parsed JSON data
        """
        with open(file_path) as f:
            return json.load(f)

    @staticmethod
    def _extract_game_params(game_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract game parameters from boxscore JSON data.

        Args:
            game_id: Unique identifier for the game
            data: Parsed boxscore JSON data

        Returns:
            Dictionary of game parameters for database insertion
        """
        season = NHLDatabaseLoader._extract_season(data)
        home_team_info = NHLDatabaseLoader._extract_team_info(data, "homeTeam")
        away_team_info = NHLDatabaseLoader._extract_team_info(data, "awayTeam")
        game_info = NHLDatabaseLoader._extract_game_info(data)

        return {
            "game_id": game_id,
            "season": season,
            **game_info,
            **home_team_info,
            **away_team_info,
        }

    @staticmethod
    def _extract_season(data: Dict[str, Any]) -> Optional[int]:
        """Extract season year from data.

        Args:
            data: Parsed boxscore JSON data

        Returns:
            Season year as integer, or None if not available
        """
        season_full = str(data.get("season", ""))
        return int(season_full[:4]) if len(season_full) >= 4 else None

    @staticmethod
    def _extract_team_info(data: Dict[str, Any], team_key: str) -> Dict[str, Any]:
        """Extract team information from data.

        Args:
            data: Parsed boxscore JSON data
            team_key: Key for team data ("homeTeam" or "awayTeam")

        Returns:
            Dictionary with team_id, team_abbrev, team_name, and score
        """
        team_data = data.get(team_key, {})
        prefix = "home_" if team_key == "homeTeam" else "away_"

        return {
            f"{prefix}team_id": get_nested_value(data, team_key, "id"),
            f"{prefix}team_abbrev": get_nested_value(data, team_key, "abbrev"),
            f"{prefix}team_name": NHLDatabaseLoader._extract_team_name(team_data),
            f"{prefix}score": get_nested_value(data, team_key, "score"),
        }

    @staticmethod
    def _extract_game_info(data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract game metadata from data.

        Args:
            data: Parsed boxscore JSON data

        Returns:
            Dictionary with game_type, game_date, venue, etc.
        """
        return {
            "game_type": str(data.get("gameType")),
            "game_date": data.get("gameDate"),
            "start_time_utc": data.get("startTimeUTC"),
            "venue": get_nested_value(data, "venue", "default"),
            "venue_location": get_nested_value(data, "venueLocation", "default"),
            "game_outcome_type": get_nested_value(
                data, "gameOutcome", "lastPeriodType"
            ),
            "game_state": data.get("gameState"),
            "period_count": get_nested_value(data, "periodDescriptor", "number"),
        }

    @staticmethod
    def _extract_team_name(team_data: Dict[str, Any]) -> str:
        """Extract team name from team data dictionary.

        Args:
            team_data: Team data dictionary from NHL API

        Returns:
            Formatted team name
        """
        place_name = team_data.get("placeName", {}).get("default", "")
        common_name = team_data.get("commonName", {}).get("default", "")
        return f"{place_name} {common_name}".strip()

    # _upsert_game_data is created dynamically in __init__ using create_entity_upserter

    def _update_winner_info(self, game_id: str, data: Dict[str, Any]) -> None:
        """Update winner and loser information in the database.

        Args:
            game_id: Unique identifier for the game
            data: Parsed boxscore JSON data
        """
        if (
            data["homeTeam"].get("score") is not None
            and data["awayTeam"].get("score") is not None
        ):
            if data["homeTeam"]["score"] > data["awayTeam"]["score"]:
                win_id, lose_id = data["homeTeam"]["id"], data["awayTeam"]["id"]
            else:
                win_id, lose_id = data["awayTeam"]["id"], data["homeTeam"]["id"]

            self.db.execute(
                """
                UPDATE games
                SET winning_team_id = :win_id, losing_team_id = :lose_id
                WHERE game_id = :game_id
            """,
                {"win_id": win_id, "lose_id": lose_id, "game_id": game_id},
            )

    def _load_boxscore(self, game_id: str, file_path: Path):
        """Load game info and stats from boxscore JSON into PostgreSQL"""
        # Load data from file
        data = self._load_boxscore_data(file_path)

        # Extract game parameters
        params = NHLDatabaseLoader._extract_game_params(game_id, data)

        # Insert/update game data
        self._upsert_game_data(self.db, params)

        # Update winner information if scores are available
        self._update_winner_info(game_id, data)
