"""
Migrates existing sport-specific game data into the unified_games table.
"""

import duckdb
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

class GameDataMigrator:
    """
    Migrates game data from various sport-specific tables into the unified_games table.
    """

    def __init__(self, db_path: str = "data/nhlstats.duckdb"):
        """
        Initializes the GameDataMigrator with the path to the DuckDB database.

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

    def __exit__(self, *args):
        """
        Closes the database connection when exiting the context.
        """
        self.close()
        # Do not suppress exceptions
        return False

    def connect(self) -> None:
        """
        Connects to the DuckDB database.
        """
        self.conn = duckdb.connect(str(self.db_path))
        print(f"✓ Connected to DuckDB: {self.db_path}")

    def close(self) -> None:
        """
        Closes the database connection if it's open.
        """
        if self.conn:
            self.conn.close()
            self.conn = None
            print("✓ DuckDB connection closed.")

    def check_source_tables(self) -> bool:
        """
        Checks for the existence and row count of source tables.

        Returns:
            True if all tables exist, False otherwise.
        """
        if not self.conn:
            raise ConnectionError("Not connected to DuckDB. Call .connect() first.")

        print("🔎 Checking source tables...")
        tables_to_check = [
            "games", "mlb_games", "nfl_games",
            "epl_games", "tennis_games", "ncaab_games"
        ]
        all_tables_exist = True

        for table_name in tables_to_check:
            try:
                count = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                print(f"  - Table '{table_name}' found with {count} rows.")
            except duckdb.CatalogException:
                print(f"  - ⚠️ Table '{table_name}' not found.")
                all_tables_exist = False

        if not all_tables_exist:
            print("  ❌ Some source tables are missing. Migration might be incomplete.")

        return all_tables_exist

    def _generate_game_id(self, sport: str, game_date: str, home_team: str, away_team: str) -> str:
        """
        Generates a consistent and unique game_id.
        Format: SPORT_YYYYMMDD_HOMEABBREV_AWAYABBREV
        """
        date_str = datetime.strptime(game_date, '%Y-%m-%d').strftime('%Y%m%d')
        # Simple slugification for team names
        home_slug = "".join(filter(str.isalnum, home_team)).upper()
        away_slug = "".join(filter(str.isalnum, away_team)).upper()
        return f"{sport.upper()}_{date_str}_{home_slug}_{away_slug}"

    def migrate_all_sports_games(self) -> int:
        """
        Migrates games from all supported sport-specific tables into `unified_games`.

        Returns:
            The total number of games inserted/updated.
        """
        if not self.conn:
            raise ConnectionError("Not connected to DuckDB. Call .connect() first.")

        total_migrated = 0
        print("⚙️ Migrating game data to 'unified_games' table...")

        # NHL Games
        total_migrated += self._migrate_nhl_games()
        # MLB Games
        total_migrated += self._migrate_mlb_games()
        # NFL Games
        total_migrated += self._migrate_nfl_games()
        # EPL Games
        total_migrated += self._migrate_epl_games()
        # Tennis Games
        total_migrated += self._migrate_tennis_games()
        # NCAAB Games
        total_migrated += self._migrate_ncaab_games()

        print(f"✅ Total {total_migrated} games migrated to 'unified_games'.")
        return total_migrated

    def _migrate_nhl_games(self) -> int:
        """Migrates NHL games from 'games' table."""
        print("  Migrating NHL games...")
        query = """
            SELECT
                game_date,
                season,
                game_state AS status,
                home_team_abbrev AS home_team_id,
                home_team_name,
                away_team_abbrev AS away_team_id,
                away_team_name,
                home_score,
                away_score,
                start_time_utc AS commence_time,
                venue
            FROM games;
        """
        records = self.conn.execute(query).fetchall()
        migrated_count = 0
        for rec in records:
            game_date_str = rec[0].strftime('%Y-%m-%d') if rec[0] else None
            if not game_date_str: continue

            game_id = self._generate_game_id('NHL', game_date_str, rec[3], rec[5])

            self.conn.execute("""
                INSERT OR REPLACE INTO unified_games (
                    game_id, sport, game_date, season, status,
                    home_team_id, home_team_name, away_team_id, away_team_name,
                    home_score, away_score, commence_time, venue
                ) VALUES (?, 'NHL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                game_date_str,
                rec[1],  # season
                rec[2],  # status
                rec[3],  # home_team_id (abbrev)
                rec[4],  # home_team_name
                rec[5],  # away_team_id (abbrev)
                rec[6],  # away_team_name
                rec[7],  # home_score
                rec[8],  # away_score
                rec[9],  # commence_time
                rec[10] # venue
            ))
            migrated_count += 1
        print(f"  ✓ Migrated {migrated_count} NHL games.")
        return migrated_count

    def _migrate_mlb_games(self) -> int:
        """Migrates MLB games from 'mlb_games' table."""
        print("  Migrating MLB games...")
        query = """
            SELECT
                game_date,
                season,
                status,
                home_team,
                away_team,
                home_score,
                away_score
            FROM mlb_games;
        """
        records = self.conn.execute(query).fetchall()
        migrated_count = 0
        for rec in records:
            game_date_str = rec[0].strftime('%Y-%m-%d') if rec[0] else None
            if not game_date_str: continue

            game_id = self._generate_game_id('MLB', game_date_str, rec[3], rec[4])

            self.conn.execute("""
                INSERT OR REPLACE INTO unified_games (
                    game_id, sport, game_date, season, status,
                    home_team_id, home_team_name, away_team_id, away_team_name,
                    home_score, away_score
                ) VALUES (?, 'MLB', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                game_date_str,
                rec[1],  # season
                rec[2],  # status
                rec[3],  # home_team_id (name)
                rec[3],  # home_team_name
                rec[4],  # away_team_id (name)
                rec[4],  # away_team_name
                rec[5],  # home_score
                rec[6]   # away_score
            ))
            migrated_count += 1
        print(f"  ✓ Migrated {migrated_count} MLB games.")
        return migrated_count

    def _migrate_nfl_games(self) -> int:
        """Migrates NFL games from 'nfl_games' table."""
        print("  Migrating NFL games...")
        query = """
            SELECT
                game_date,
                season,
                status,
                home_team,
                away_team,
                home_score,
                away_score
            FROM nfl_games;
        """
        records = self.conn.execute(query).fetchall()
        migrated_count = 0
        for rec in records:
            game_date_str = rec[0].strftime('%Y-%m-%d') if rec[0] else None
            if not game_date_str: continue

            game_id = self._generate_game_id('NFL', game_date_str, rec[3], rec[4])

            self.conn.execute("""
                INSERT OR REPLACE INTO unified_games (
                    game_id, sport, game_date, season, status,
                    home_team_id, home_team_name, away_team_id, away_team_name,
                    home_score, away_score
                ) VALUES (?, 'NFL', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                game_date_str,
                rec[1],  # season
                rec[2],  # status
                rec[3],  # home_team_id (name)
                rec[3],  # home_team_name
                rec[4],  # away_team_id (name)
                rec[4],  # away_team_name
                rec[5],  # home_score
                rec[6]   # away_score
            ))
            migrated_count += 1
        print(f"  ✓ Migrated {migrated_count} NFL games.")
        return migrated_count

    def _migrate_epl_games(self) -> int:
        """Migrates EPL games from 'epl_games' table."""
        print("  Migrating EPL games...")
        query = """
            SELECT
                game_date,
                season,
                result AS status,
                home_team,
                away_team,
                home_score,
                away_score
            FROM epl_games;
        """
        records = self.conn.execute(query).fetchall()
        migrated_count = 0
        for rec in records:
            game_date_str = rec[0].strftime('%Y-%m-%d') if rec[0] else None
            if not game_date_str: continue

            game_id = self._generate_game_id('EPL', game_date_str, rec[3], rec[4])

            self.conn.execute("""
                INSERT OR REPLACE INTO unified_games (
                    game_id, sport, game_date, season, status,
                    home_team_id, home_team_name, away_team_id, away_team_name,
                    home_score, away_score
                ) VALUES (?, 'EPL', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                game_date_str,
                int(rec[1]) if rec[1] and isinstance(rec[1], str) and rec[1].isdigit() else None, # season
                rec[2],  # status
                rec[3],  # home_team_id (name)
                rec[3],  # home_team_name
                rec[4],  # away_team_id (name)
                rec[4],  # away_team_name
                rec[5],  # home_score
                rec[6]   # away_score
            ))
            migrated_count += 1
        print(f"  ✓ Migrated {migrated_count} EPL games.")
        return migrated_count

    def _migrate_tennis_games(self) -> int:
        """Migrates Tennis games from 'tennis_games' table."""
        print("  Migrating Tennis games...")
        query = """
            SELECT
                game_date,
                tour,
                winner,
                loser,
                (SELECT NULL) AS score
            FROM tennis_games;
        """
        records = self.conn.execute(query).fetchall()
        migrated_count = 0
        for rec in records:
            game_date_str = rec[0].strftime('%Y-%m-%d') if rec[0] else None
            if not game_date_str: continue

            # For tennis, we treat winner/loser as home/away for game_id generation
            game_id = self._generate_game_id('TENNIS', game_date_str, rec[2], rec[3])

            # Tennis doesn't have traditional home/away scores, so we'll leave them null
            # And status can be inferred from score presence
            status = 'Final' if rec[4] else 'Scheduled'
            season = rec[0].year if rec[0] else None

            self.conn.execute("""
                INSERT OR REPLACE INTO unified_games (
                    game_id, sport, game_date, season, status,
                    home_team_id, home_team_name, away_team_id, away_team_name,
                    home_score, away_score, venue
                ) VALUES (?, 'TENNIS', ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """, (
                game_id,
                game_date_str,
                season,  # season derived from date
                status,  # status
                rec[2],  # winner as home_team
                rec[2],  # winner name
                rec[3],  # loser as away_team
                rec[3],  # loser name
                rec[1],  # tour as venue (for lack of better place)
            ))
            migrated_count += 1
        print(f"  ✓ Migrated {migrated_count} Tennis games.")
        return migrated_count

    def _migrate_ncaab_games(self) -> int:
        """Migrates NCAAB games from 'ncaab_games' table."""
        print("  Migrating NCAAB games...")
        query = """
            SELECT
                game_date,
                season,
                home_team,
                away_team,
                home_score,
                away_score
            FROM ncaab_games;
        """
        records = self.conn.execute(query).fetchall()
        migrated_count = 0
        for rec in records:
            game_date_str = rec[0].strftime('%Y-%m-%d') if rec[0] else None
            if not game_date_str: continue

            game_id = self._generate_game_id('NCAAB', game_date_str, rec[2], rec[3])

            # Status can be inferred from score presence
            status = 'Final' if rec[4] is not None and rec[5] is not None else 'Scheduled'

            self.conn.execute("""
                INSERT OR REPLACE INTO unified_games (
                    game_id, sport, game_date, season, status,
                    home_team_id, home_team_name, away_team_id, away_team_name,
                    home_score, away_score
                ) VALUES (?, 'NCAAB', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                game_date_str,
                rec[1],  # season
                status,  # status
                rec[2],  # home_team_id (name)
                rec[2],  # home_team_name
                rec[3],  # away_team_id (name)
                rec[3],  # away_team_name
                rec[4],  # home_score
                rec[5]   # away_score
            ))
            migrated_count += 1
        print(f"  ✓ Migrated {migrated_count} NCAAB games.")
        return migrated_count


def main():
    """
    Main function to run the game data migration.
    """
    print("=" * 80)
    print("🔄 Running Game Data Migrator")
    print("=" * 80)
    try:
        with GameDataMigrator() as migrator:
            migrator.check_source_tables()
            migrator.migrate_all_sports_games()
        print("\n" + "=" * 80)
        print("🎉 Game data migration complete!")
        print("=" * 80)
    except Exception as e:
        print(f"❌ An error occurred during game data migration: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
