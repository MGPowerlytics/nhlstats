"""
Database Schema Manager for sports betting system.
Handles creation and management of database tables for all sports.
"""

from typing import List
from plugins.db_manager import DBManager


class DatabaseSchemaManager:
    """Manages database schema creation and updates for sports data."""

    def __init__(self, db: DBManager) -> None:
        """Initialize with database manager.

        Args:
            db: Database manager instance
        """
        self.db = db
        self._schema_initialized = False

    def initialize_schema(self) -> None:
        """Initialize all database tables if they don't exist."""
        if self._schema_initialized:
            return

        tables = self._get_table_definitions()
        for sql in tables:
            self.db.execute(sql)

        self._schema_initialized = True
        print("✓ PostgreSQL Schema initialized.")

    def _get_table_definitions(self) -> List[str]:
        """Get SQL definitions for all database tables.

        Returns:
            List of SQL CREATE TABLE statements
        """
        tables = []
        tables.extend(self._get_core_table_definitions())
        tables.extend(self._get_sport_specific_table_definitions())
        tables.extend(self._get_unified_table_definitions())
        return tables

    def _get_core_table_definitions(self) -> List[str]:
        """Get SQL definitions for core database tables.

        Returns:
            List of SQL CREATE TABLE statements for core tables
        """
        return [
            # Core games table for NHL
            "CREATE TABLE IF NOT EXISTS games (game_id VARCHAR PRIMARY KEY, season INTEGER, game_type VARCHAR, "
            "game_date DATE, start_time_utc TIMESTAMP, venue VARCHAR, venue_location VARCHAR, "
            "home_team_id INTEGER, home_team_abbrev VARCHAR, home_team_name VARCHAR, "
            "away_team_id INTEGER, away_team_abbrev VARCHAR, away_team_name VARCHAR, "
            "home_score INTEGER, away_score INTEGER, winning_team_id INTEGER, losing_team_id INTEGER, "
            "game_outcome_type VARCHAR, game_state VARCHAR, period_count INTEGER)",
            # Teams table
            "CREATE TABLE IF NOT EXISTS teams (team_id INTEGER PRIMARY KEY, team_abbrev VARCHAR, "
            "team_name VARCHAR, team_common_name VARCHAR)",
        ]

    def _get_sport_specific_table_definitions(self) -> List[str]:
        """Get SQL definitions for sport-specific database tables.

        Returns:
            List of SQL CREATE TABLE statements for sport-specific tables
        """
        return [
            # MLB games table
            "CREATE TABLE IF NOT EXISTS mlb_games (game_id INTEGER PRIMARY KEY, game_date DATE, "
            "season INTEGER, game_type VARCHAR, home_team VARCHAR, away_team VARCHAR, "
            "home_score INTEGER, away_score INTEGER, status VARCHAR)",
            # NFL games table
            "CREATE TABLE IF NOT EXISTS nfl_games (game_id VARCHAR PRIMARY KEY, game_date DATE, "
            "season INTEGER, week INTEGER, game_type VARCHAR, home_team VARCHAR, away_team VARCHAR, "
            "home_score INTEGER, away_score INTEGER, status VARCHAR)",
            # EPL games table
            "CREATE TABLE IF NOT EXISTS epl_games (game_id VARCHAR PRIMARY KEY, game_date DATE, "
            "season VARCHAR, home_team VARCHAR, away_team VARCHAR, home_score INTEGER, "
            "away_score INTEGER, result VARCHAR)",
            # Tennis games table
            "CREATE TABLE IF NOT EXISTS tennis_games (game_id VARCHAR PRIMARY KEY, game_date DATE, "
            "season VARCHAR, tour VARCHAR, tournament VARCHAR, surface VARCHAR, winner VARCHAR, "
            "loser VARCHAR, score VARCHAR)",
            # NCAAB games table
            "CREATE TABLE IF NOT EXISTS ncaab_games (game_id VARCHAR PRIMARY KEY, game_date DATE, "
            "season INTEGER, home_team VARCHAR, away_team VARCHAR, home_score INTEGER, "
            "away_score INTEGER, is_neutral BOOLEAN)",
        ]

    def _get_unified_table_definitions(self) -> List[str]:
        """Get SQL definitions for unified database tables.

        Returns:
            List of SQL CREATE TABLE statements for unified tables
        """
        return [
            # Unified games table (all sports)
            "CREATE TABLE IF NOT EXISTS unified_games (game_id VARCHAR PRIMARY KEY, sport VARCHAR NOT NULL, "
            "game_date DATE NOT NULL, season INTEGER, status VARCHAR, home_team_id VARCHAR, "
            "home_team_name VARCHAR, away_team_id VARCHAR, away_team_name VARCHAR, home_score INTEGER, "
            "away_score INTEGER, commence_time TIMESTAMP, venue VARCHAR, loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            # Game odds table
            "CREATE TABLE IF NOT EXISTS game_odds (odds_id VARCHAR PRIMARY KEY, game_id VARCHAR NOT NULL, "
            "bookmaker VARCHAR NOT NULL, market_name VARCHAR NOT NULL, outcome_name VARCHAR, "
            "price DECIMAL(10, 4) NOT NULL, line DECIMAL(10, 4), last_update TIMESTAMP, "
            "is_pregame BOOLEAN DEFAULT TRUE, loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        ]

    def is_schema_initialized(self) -> bool:
        """Check if schema has been initialized.

        Returns:
            True if schema has been initialized, False otherwise
        """
        return self._schema_initialized

    def reset_schema_state(self) -> None:
        """Reset schema initialization state (for testing)."""
        self._schema_initialized = False
