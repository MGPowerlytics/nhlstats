"""
Manages the database schema for the multi-sport betting system (PostgreSQL).
Defines and creates unified tables for games and betting odds across all sports.
"""

from db_manager import DBManager, default_db
import logging

logger = logging.getLogger(__name__)

class DatabaseSchemaManager:
    """
    Manages the creation and updates of the unified database schema in PostgreSQL.
    """

    def __init__(self, db_manager: DBManager = default_db):
        """
        Initializes the DatabaseSchemaManager with the DBManager.
        """
        self.db = db_manager

    def create_unified_tables(self) -> None:
        """
        Creates or updates the unified `unified_games` and `game_odds` tables.
        """
        print("⚙️ Creating/Updating unified database tables in PostgreSQL...")

        # unified_games table: Centralized game schedule for all sports
        self.db.execute("""
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
        self.db.execute("""
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
                external_id VARCHAR,                 -- External ID from the source

                FOREIGN KEY (game_id) REFERENCES unified_games(game_id)
            );
        """)
        print("  ✓ 'game_odds' table ensured.")

        # Indexes
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_unified_games_date ON unified_games(game_date);")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_unified_games_sport ON unified_games(sport);")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_game_odds_game_id ON game_odds(game_id);")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_game_odds_bookmaker ON game_odds(bookmaker);")

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
        manager = DatabaseSchemaManager()
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
