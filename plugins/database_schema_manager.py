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
        tables.extend(self._get_stats_table_definitions())
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
            # Ligue 1 games table
            "CREATE TABLE IF NOT EXISTS ligue1_games (game_id VARCHAR PRIMARY KEY, game_date DATE, "
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
            # WNCAAB games table
            "CREATE TABLE IF NOT EXISTS wncaab_games (game_id VARCHAR PRIMARY KEY, game_date DATE, "
            "season INTEGER, home_team VARCHAR, away_team VARCHAR, home_score INTEGER, "
            "away_score INTEGER, is_neutral BOOLEAN)",
            # Unrivaled games table
            "CREATE TABLE IF NOT EXISTS unrivaled_games (game_id VARCHAR PRIMARY KEY, game_date DATE, "
            "season INTEGER, home_team VARCHAR, away_team VARCHAR, home_score INTEGER, "
            "away_score INTEGER, is_neutral BOOLEAN)",
            # CBA games table
            "CREATE TABLE IF NOT EXISTS cba_games (game_id VARCHAR PRIMARY KEY, game_date DATE, "
            "season INTEGER, home_team VARCHAR, away_team VARCHAR, home_score INTEGER, "
            "away_score INTEGER, is_neutral BOOLEAN, status VARCHAR)",
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
            "is_pregame BOOLEAN DEFAULT TRUE, external_id VARCHAR, loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            # Diagnostic results table (P&L diagnostics per sport per run)
            "CREATE TABLE IF NOT EXISTS diagnostic_results (id SERIAL PRIMARY KEY, "
            "run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, sport TEXT NOT NULL, settled_bets INTEGER, "
            "wins INTEGER, losses INTEGER, roi FLOAT, real_clv FLOAT, p_value FLOAT, "
            "passes_gate BOOLEAN, avg_hours_before_game FLOAT, timing_roi_under_2hr FLOAT, "
            "timing_roi_over_8hr FLOAT, bets_with_closing_price INTEGER, bets_flagged_stale INTEGER, "
            "recommendation TEXT, elo_replay_divergence FLOAT)",
            # Composite index for diagnostic results lookups by sport and date
            "CREATE INDEX IF NOT EXISTS idx_diagnostic_results_sport_date ON diagnostic_results (sport, run_date)",
        ]

    def _get_stats_table_definitions(self) -> List[str]:
        """Get SQL definitions for team/player game stats and audit tables.

        Returns:
            List of SQL CREATE TABLE and CREATE INDEX statements for stats tables.
            See docs/TEAM_GAME_STATS_SPEC.md for the full column contract.
        """
        return [
            # ------------------------------------------------------------------
            # Core cross-sport team stats (one row per team per game)
            # ------------------------------------------------------------------
            """CREATE TABLE IF NOT EXISTS team_game_stats (
                game_id       VARCHAR      NOT NULL,
                sport         VARCHAR      NOT NULL,
                team          VARCHAR      NOT NULL,
                opponent      VARCHAR      NOT NULL,
                is_home       BOOLEAN      NOT NULL,
                game_date     DATE         NOT NULL,
                season        VARCHAR      NOT NULL,
                points_for    INTEGER,
                points_against INTEGER,
                won           BOOLEAN,
                off_rating    NUMERIC(6,2),
                def_rating    NUMERIC(6,2),
                pace          NUMERIC(6,2),
                margin        INTEGER,
                created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
                updated_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
                PRIMARY KEY (game_id, team),
                FOREIGN KEY (game_id) REFERENCES unified_games(game_id)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_tgs_sport_date   ON team_game_stats (sport, game_date)",
            "CREATE INDEX IF NOT EXISTS idx_tgs_team_date    ON team_game_stats (team, game_date)",
            "CREATE INDEX IF NOT EXISTS idx_tgs_sport_season ON team_game_stats (sport, season)",
            # ------------------------------------------------------------------
            # NBA extension — advanced box-score metrics
            # ------------------------------------------------------------------
            """CREATE TABLE IF NOT EXISTS nba_team_game_stats_ext (
                game_id     VARCHAR      NOT NULL,
                team        VARCHAR      NOT NULL,
                fg_pct      NUMERIC(5,4),
                fg3m        INTEGER,
                fg3a        INTEGER,
                fg3_pct     NUMERIC(5,4),
                ast         INTEGER,
                reb         INTEGER,
                oreb        INTEGER,
                dreb        INTEGER,
                stl         INTEGER,
                blk         INTEGER,
                tov         INTEGER,
                pf          INTEGER,
                ts_pct      NUMERIC(5,4),
                efg_pct     NUMERIC(5,4),
                usage_pct   NUMERIC(5,4),
                PRIMARY KEY (game_id, team),
                FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
            )""",
            # ------------------------------------------------------------------
            # NHL extension — shots, special teams, physical play
            # ------------------------------------------------------------------
            """CREATE TABLE IF NOT EXISTS nhl_team_game_stats_ext (
                game_id            VARCHAR      NOT NULL,
                team               VARCHAR      NOT NULL,
                shots              INTEGER,
                sog                INTEGER,
                hits               INTEGER,
                blocks             INTEGER,
                pim                INTEGER,
                faceoff_pct        NUMERIC(5,4),
                pp_goals           INTEGER,
                pp_opportunities   INTEGER,
                pp_pct             NUMERIC(5,4),
                pk_goals_against   INTEGER,
                pk_opportunities   INTEGER,
                pk_pct             NUMERIC(5,4),
                shooting_pct       NUMERIC(5,4),
                PRIMARY KEY (game_id, team),
                FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
            )""",
            # ------------------------------------------------------------------
            # MLB extension — batting and pitching box-score
            # ------------------------------------------------------------------
            """CREATE TABLE IF NOT EXISTS mlb_team_game_stats_ext (
                game_id       VARCHAR      NOT NULL,
                team          VARCHAR      NOT NULL,
                hits          INTEGER,
                errors        INTEGER,
                lob           INTEGER,
                doubles       INTEGER,
                triples       INTEGER,
                home_runs     INTEGER,
                rbi           INTEGER,
                stolen_bases  INTEGER,
                strikeouts    INTEGER,
                walks         INTEGER,
                at_bats       INTEGER,
                obp           NUMERIC(5,4),
                slg           NUMERIC(5,4),
                ops           NUMERIC(5,4),
                woba          NUMERIC(5,4),
                era           NUMERIC(6,2),
                PRIMARY KEY (game_id, team),
                FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
            )""",
            # ------------------------------------------------------------------
            # NFL extension — passing, rushing, situational
            # ------------------------------------------------------------------
            """CREATE TABLE IF NOT EXISTS nfl_team_game_stats_ext (
                game_id                  VARCHAR      NOT NULL,
                team                     VARCHAR      NOT NULL,
                passing_yards            INTEGER,
                passing_tds              INTEGER,
                passing_ints             INTEGER,
                rushing_yards            INTEGER,
                rushing_tds              INTEGER,
                rushing_attempts         INTEGER,
                total_yards              INTEGER,
                turnovers                INTEGER,
                third_down_conversions   INTEGER,
                third_down_attempts      INTEGER,
                third_down_pct           NUMERIC(5,4),
                time_of_possession       INTEGER,
                penalties                INTEGER,
                penalty_yards            INTEGER,
                sacks_allowed            INTEGER,
                first_downs              INTEGER,
                PRIMARY KEY (game_id, team),
                FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
            )""",
            # ------------------------------------------------------------------
            # Soccer extension — EPL and Ligue 1 share this table (sport col
            # in team_game_stats disambiguates)
            # ------------------------------------------------------------------
            """CREATE TABLE IF NOT EXISTS soccer_team_game_stats_ext (
                game_id          VARCHAR      NOT NULL,
                team             VARCHAR      NOT NULL,
                shots            INTEGER,
                shots_on_target  INTEGER,
                possession_pct   NUMERIC(5,4),
                passes           INTEGER,
                pass_accuracy    NUMERIC(5,4),
                xg               NUMERIC(6,3),
                xga              NUMERIC(6,3),
                fouls            INTEGER,
                yellow_cards     INTEGER,
                red_cards        INTEGER,
                corners          INTEGER,
                offsides         INTEGER,
                saves            INTEGER,
                PRIMARY KEY (game_id, team),
                FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
            )""",
            # ------------------------------------------------------------------
            # NCAAB extension — mirrors NBA, simpler (no usage_pct)
            # ------------------------------------------------------------------
            """CREATE TABLE IF NOT EXISTS ncaab_team_game_stats_ext (
                game_id   VARCHAR      NOT NULL,
                team      VARCHAR      NOT NULL,
                fg_pct    NUMERIC(5,4),
                fg3m      INTEGER,
                fg3a      INTEGER,
                fg3_pct   NUMERIC(5,4),
                ast       INTEGER,
                reb       INTEGER,
                stl       INTEGER,
                blk       INTEGER,
                tov       INTEGER,
                pf        INTEGER,
                ts_pct    NUMERIC(5,4),
                efg_pct   NUMERIC(5,4),
                PRIMARY KEY (game_id, team),
                FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
            )""",
            # ------------------------------------------------------------------
            # WNCAAB extension — same shape as NCAAB
            # ------------------------------------------------------------------
            """CREATE TABLE IF NOT EXISTS wncaab_team_game_stats_ext (
                game_id   VARCHAR      NOT NULL,
                team      VARCHAR      NOT NULL,
                fg_pct    NUMERIC(5,4),
                fg3m      INTEGER,
                fg3a      INTEGER,
                fg3_pct   NUMERIC(5,4),
                ast       INTEGER,
                reb       INTEGER,
                stl       INTEGER,
                blk       INTEGER,
                tov       INTEGER,
                pf        INTEGER,
                ts_pct    NUMERIC(5,4),
                efg_pct   NUMERIC(5,4),
                PRIMARY KEY (game_id, team),
                FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
            )""",
            # ------------------------------------------------------------------
            # Tennis player-level match stats (one row per player per match)
            # ------------------------------------------------------------------
            """CREATE TABLE IF NOT EXISTS tennis_player_match_stats (
                game_id                 VARCHAR      NOT NULL,
                player_name             VARCHAR      NOT NULL,
                aces                    INTEGER,
                double_faults           INTEGER,
                first_serve_pct         NUMERIC(5,4),
                first_serve_won_pct     NUMERIC(5,4),
                second_serve_won_pct    NUMERIC(5,4),
                break_points_saved      INTEGER,
                break_points_faced      INTEGER,
                winners                 INTEGER,
                unforced_errors         INTEGER,
                sets_won                INTEGER,
                games_won               INTEGER,
                won                     BOOLEAN,
                created_at              TIMESTAMP    NOT NULL DEFAULT NOW(),
                PRIMARY KEY (game_id, player_name),
                FOREIGN KEY (game_id) REFERENCES unified_games(game_id)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_tpms_game_id ON tennis_player_match_stats (game_id)",
            "CREATE INDEX IF NOT EXISTS idx_tpms_player  ON tennis_player_match_stats (player_name)",
            # ------------------------------------------------------------------
            # Bet reconciliation audit — immutable append-only log
            # ------------------------------------------------------------------
            """CREATE TABLE IF NOT EXISTS bet_reconciliation_audit (
                audit_id          SERIAL       PRIMARY KEY,
                bet_id            VARCHAR      NOT NULL,
                field_changed     VARCHAR      NOT NULL,
                old_value         TEXT,
                new_value         TEXT,
                source            VARCHAR      NOT NULL,
                reconciled_at     TIMESTAMP    NOT NULL DEFAULT NOW(),
                reason            TEXT,
                discrepancy_type  VARCHAR,
                run_id            VARCHAR
            )""",
            "CREATE INDEX IF NOT EXISTS idx_bra_bet_id         ON bet_reconciliation_audit (bet_id)",
            "CREATE INDEX IF NOT EXISTS idx_bra_reconciled_at  ON bet_reconciliation_audit (reconciled_at)",
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
