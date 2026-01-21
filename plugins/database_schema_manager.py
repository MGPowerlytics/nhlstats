"""
Manages the database schema for the multi-sport betting system.
Defines and creates unified tables for games and betting odds across all sports.
"""

import duckdb
from pathlib import Path
from typing import Optional

class DatabaseSchemaManager:
    """
    Manages the creation and updates of the unified database schema.
    """

    def __init__(self, db_path: str = "data/nhlstats.duckdb"):
        """
        Initializes the DatabaseSchemaManager with the path to the DuckDB database.

        Args:
            db_path: The path to the DuckDB database file.
        """
        self.db_path = Path(db_path)
        self.conn = None

    def __enter__(self):
        """
        Establishes a connection to the DuckDB database when entering the context.
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Closes the database connection when exiting the context.
        """
        self.close()
        # Do not suppress exceptions
        return False

    def connect(self) -> None:
        """
        Connects to the DuckDB database, creating it if it doesn't exist.
        Includes a retry mechanism for database lock issues.
        """
        import time
        max_retries = 30
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                self.conn = duckdb.connect(str(self.db_path))
                print(f"✓ Connected to DuckDB: {self.db_path}")
                break
            except Exception as e:
                if 'lock' in str(e).lower() and attempt < max_retries - 1:
                    print(f"  ⚠️ Database locked, waiting {retry_delay}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                else:
                    raise

    def close(self) -> None:
        """
        Closes the database connection if it's open.
        """
        if self.conn:
            self.conn.close()
            self.conn = None
            print("✓ DuckDB connection closed.")

    def create_unified_tables(self) -> None:
        """
        Creates or updates the unified `unified_games` and `game_odds` tables.
        """
        if not self.conn:
            raise ConnectionError("Not connected to DuckDB. Call .connect() first.")

        print("⚙️ Creating/Updating unified database tables...")

        # unified_games table: Centralized game schedule for all sports
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS unified_games (
                game_id VARCHAR PRIMARY KEY,         -- Unique ID (e.g., NHL_20240120_LAK_BOS)
                sport VARCHAR NOT NULL,              -- e.g., 'NHL', 'NBA', 'MLB', 'NCAAB', 'TENNIS', 'EPL', 'LIGUE1', 'NFL'
                game_date DATE NOT NULL,
                season INTEGER,                      -- e.g., 2023 for 2023-2024 season
                status VARCHAR,                      -- e.g., 'Scheduled', 'Final', 'InProgress'
                home_team_id VARCHAR,                -- Normalized team identifier
                home_team_name VARCHAR,
                away_team_id VARCHAR,                -- Normalized team identifier
                away_team_name VARCHAR,
                home_score INTEGER,
                away_score INTEGER,
                commence_time TIMESTAMP,             -- Original UTC start time
                venue VARCHAR,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("  ✓ 'unified_games' table ensured.")

        # game_odds table: Stores odds from various bookmakers, linked to unified_games
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS game_odds (
                odds_id VARCHAR PRIMARY KEY,         -- Unique ID for this specific odds record
                game_id VARCHAR NOT NULL,            -- Foreign key to unified_games
                bookmaker VARCHAR NOT NULL,          -- e.g., 'Kalshi', 'BetMGM', 'DraftKings', 'SBR'
                market_name VARCHAR NOT NULL,        -- e.g., 'moneyline', 'spread', 'total'
                outcome_name VARCHAR,                -- e.g., 'home_team_win', 'away_team_win', 'draw', 'over', 'under'
                price DECIMAL(10, 4) NOT NULL,       -- American or Decimal odds (store as decimal for consistency)
                line DECIMAL(10, 4),                 -- e.g., -1.5 for spread, 5.5 for total
                last_update TIMESTAMP,               -- When these odds were last updated/fetched
                is_pregame BOOLEAN DEFAULT TRUE,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (game_id) REFERENCES unified_games(game_id)
            );
        """)
        print("  ✓ 'game_odds' table ensured.")

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_unified_games_date ON unified_games(game_date);
            CREATE INDEX IF NOT EXISTS idx_unified_games_sport ON unified_games(sport);
            CREATE INDEX IF NOT EXISTS idx_game_odds_game_id ON game_odds(game_id);
            CREATE INDEX IF NOT EXISTS idx_game_odds_bookmaker ON game_odds(bookmaker);
        """)
        print("  ✓ Indexes ensured.")
        print("✅ Unified tables and indexes created/updated successfully.")


def main():
    """
    Main function to create/update the unified database tables.
    """
    print("=" * 80)
    print("🚀 Running Database Schema Manager")
    print("=" * 80)
    try:
        with DatabaseSchemaManager() as manager:
            manager.create_unified_tables()
        print("\n" + "=" * 80)
        print("🎉 Database schema management complete!")
        print("=" * 80)
    except Exception as e:
        print(f"❌ An error occurred during schema management: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
