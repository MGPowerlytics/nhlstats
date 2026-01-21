"""
Test-Driven Development: NHL Shift Data Collection

Tests to ensure:
1. Shift data is collected daily
2. Shift data aligns with games and play-by-play events
3. Database has complete shift data from 2021-2022 season onwards
4. Data integrity and consistency
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import os


class TestNHLShiftDataCollection:
    """TDD tests for NHL shift data collection and alignment."""

    @pytest.fixture
    def db_engine(self):
        """Create database engine for testing."""
        # For local testing, override host to localhost
        import os

        os.environ["POSTGRES_HOST"] = "localhost"

        from plugins.db_manager import DBManager

        db = DBManager()
        return db.get_engine()

    def test_player_shifts_table_exists(self, db_engine):
        """player_shifts table should exist in database."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'player_shifts' AND table_schema = 'public'
            """
                )
            )
            tables = [row[0] for row in result]
            assert (
                "player_shifts" in tables
            ), "player_shifts table not found in database"

    def test_shift_data_from_2021_season(self, db_engine):
        """Database should contain shift data from 2021-2022 season onwards."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM player_shifts
                WHERE game_id LIKE '2021%'
            """
                )
            )
            count_2021 = result.scalar()

            assert count_2021 > 0, "No shift data found for 2021-2022 season"
            assert (
                count_2021 > 100000
            ), f"Insufficient 2021-2022 shift data (found {count_2021} shifts, expected >100000)"

    def test_shift_data_from_2022_season(self, db_engine):
        """Database should contain shift data from 2022-2023 season."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM player_shifts
                WHERE game_id LIKE '2022%'
            """
                )
            )
            count = result.scalar()
            assert (
                count > 100000
            ), f"Insufficient 2022-2023 shift data (found {count} shifts)"

    def test_shift_data_from_2023_season(self, db_engine):
        """Database should contain shift data from 2023-2024 season."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM player_shifts
                WHERE game_id LIKE '2023%'
            """
                )
            )
            count = result.scalar()
            assert (
                count > 100000
            ), f"Insufficient 2023-2024 shift data (found {count} shifts)"

    def test_shift_data_from_current_season(self, db_engine):
        """Database should contain shift data from current 2024-2025 season."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM player_shifts
                WHERE game_id LIKE '2024%'
            """
                )
            )
            count = result.scalar()
            assert count > 0, "No shift data found for 2024-2025 season"

    def test_minimum_games_with_shift_data(self, db_engine):
        """Database should have shift data for minimum number of games."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(DISTINCT game_id)
                FROM player_shifts
            """
                )
            )
            game_count = result.scalar()

            # Should have ~4000+ games with shift data (similar to play-by-play)
            assert (
                game_count >= 4000
            ), f"Insufficient game coverage in shifts (found {game_count} games, expected >=4000)"

    def test_shifts_align_with_play_events_games(self, db_engine):
        """Games with shift data should align with games that have play-by-play events."""
        with db_engine.connect() as conn:
            # Get count of games with shifts
            result = conn.execute(
                text(
                    """
                SELECT COUNT(DISTINCT game_id)
                FROM player_shifts
            """
                )
            )
            shift_games = result.scalar()

            # Get count of games with events
            result = conn.execute(
                text(
                    """
                SELECT COUNT(DISTINCT game_id)
                FROM play_events
            """
                )
            )
            event_games = result.scalar()

            # Get count of games with both
            result = conn.execute(
                text(
                    """
                SELECT COUNT(DISTINCT ps.game_id)
                FROM player_shifts ps
                WHERE EXISTS (
                    SELECT 1 FROM play_events pe
                    WHERE pe.game_id = ps.game_id
                )
            """
                )
            )
            common_games = result.scalar()

            # At least 90% of shift games should have play-by-play events
            alignment_ratio = common_games / shift_games if shift_games > 0 else 0
            assert (
                alignment_ratio >= 0.90
            ), f"Poor alignment between shifts and events: {alignment_ratio:.1%} (expected >=90%)"

    def test_recent_shift_data_exists(self, db_engine):
        """Shift data should exist for recent games."""
        with db_engine.connect() as conn:
            # Check for shifts in current season
            result = conn.execute(
                text(
                    """
                SELECT COUNT(DISTINCT game_id)
                FROM player_shifts
                WHERE game_id LIKE '2024%'
            """
                )
            )
            current_season_games = result.scalar()

            assert (
                current_season_games > 100
            ), f"Insufficient current season shift data ({current_season_games} games, expected >100)"

    def test_shift_coverage_by_season(self, db_engine):
        """Verify shift data coverage for each season since 2021-2022."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT
                    LEFT(game_id, 4) as season,
                    COUNT(DISTINCT game_id) as games,
                    COUNT(*) as shifts
                FROM player_shifts
                WHERE game_id ~ '^202[1-4]'
                GROUP BY LEFT(game_id, 4)
                ORDER BY season
            """
                )
            )

            seasons = list(result)

            # Should have data for 2021, 2022, 2023, 2024
            season_years = [s[0] for s in seasons]
            assert "2021" in season_years, "Missing 2021-2022 season shift data"
            assert "2022" in season_years, "Missing 2022-2023 season shift data"
            assert "2023" in season_years, "Missing 2023-2024 season shift data"
            assert "2024" in season_years, "Missing 2024-2025 season shift data"

            # Each season should have reasonable number of games and shifts
            for season, games, shifts in seasons:
                assert (
                    games >= 100
                ), f"Season {season}: insufficient games with shifts ({games}, expected >=100)"
                assert (
                    shifts >= 100000
                ), f"Season {season}: insufficient shifts ({shifts}, expected >=100000)"

    def test_shifts_match_play_events_for_same_games(self, db_engine):
        """For games with both shifts and events, verify they're for the same games."""
        with db_engine.connect() as conn:
            # Sample 10 games and check alignment
            result = conn.execute(
                text(
                    """
                SELECT ps.game_id,
                       COUNT(DISTINCT ps.shift_id) as shift_count,
                       COUNT(DISTINCT pe.event_id) as event_count
                FROM player_shifts ps
                JOIN play_events pe ON ps.game_id = pe.game_id
                WHERE ps.game_id LIKE '2024%'
                GROUP BY ps.game_id
                ORDER BY ps.game_id DESC
                LIMIT 10
            """
                )
            )

            games = list(result)

            assert len(games) > 0, "No games found with both shifts and events"

            for game_id, shift_count, event_count in games:
                # Each game should have reasonable number of shifts and events
                assert shift_count > 0, f"Game {game_id}: no shifts found (expected >0)"
                assert event_count > 0, f"Game {game_id}: no events found (expected >0)"
                # Typical NHL game has 700-900 shifts and 200-400 events
                assert 300 <= shift_count <= 1500, (
                    f"Game {game_id}: unusual shift count {shift_count} "
                    f"(expected 300-1500)"
                )


class TestNHLShiftDataQuality:
    """Tests for shift data quality and integrity."""

    @pytest.fixture
    def db_engine(self):
        """Create database engine for testing."""
        import os

        os.environ["POSTGRES_HOST"] = "localhost"

        from plugins.db_manager import DBManager

        db = DBManager()
        return db.get_engine()

    def test_no_null_game_ids_in_shifts(self, db_engine):
        """All shifts should have valid game IDs."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM player_shifts
                WHERE game_id IS NULL OR game_id = ''
            """
                )
            )
            null_count = result.scalar()
            assert null_count == 0, f"Found {null_count} shifts with NULL/empty game_id"

    def test_no_null_player_ids_in_shifts(self, db_engine):
        """All shifts should have valid player IDs."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM player_shifts
                WHERE player_id IS NULL
            """
                )
            )
            null_count = result.scalar()
            assert null_count == 0, f"Found {null_count} shifts with NULL player_id"

    def test_shifts_per_game_reasonable(self, db_engine):
        """Average shifts per game should be within reasonable range."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT AVG(shift_count)::INTEGER as avg_shifts
                FROM (
                    SELECT game_id, COUNT(*) as shift_count
                    FROM player_shifts
                    GROUP BY game_id
                ) subq
            """
                )
            )
            avg_shifts = result.scalar()

            # NHL games typically have 700-900 shifts total
            assert (
                600 <= avg_shifts <= 1200
            ), f"Average shifts per game out of range: {avg_shifts} (expected 600-1200)"

    def test_valid_period_values(self, db_engine):
        """Shifts should have valid period values (1-3 regular, 4+ for OT)."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT DISTINCT period
                FROM player_shifts
                WHERE period IS NOT NULL
                ORDER BY period
            """
                )
            )
            periods = [row[0] for row in result]

            # Should have periods 1, 2, 3 at minimum (4+ for OT)
            assert 1 in periods, "Missing period 1 shifts"
            assert 2 in periods, "Missing period 2 shifts"
            assert 3 in periods, "Missing period 3 shifts"

            # All periods should be valid (1-10, allowing for multiple OT periods)
            for period in periods:
                assert (
                    1 <= period <= 10
                ), f"Invalid period value: {period} (expected 1-10)"

    def test_shifts_have_duration(self, db_engine):
        """Most shifts should have duration data."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT
                    COUNT(*) as total_shifts,
                    COUNT(*) FILTER (WHERE duration IS NOT NULL AND duration != '') as with_duration
                FROM player_shifts
            """
                )
            )
            total, with_duration = result.fetchone()

            duration_ratio = with_duration / total if total > 0 else 0
            # At least 80% should have duration
            assert (
                duration_ratio >= 0.80
            ), f"Too many shifts without duration: {duration_ratio:.1%} have duration (expected >=80%)"

    def test_game_has_players_from_both_teams(self, db_engine):
        """Most games should have shifts from players on both teams."""
        with db_engine.connect() as conn:
            # Count games with both teams vs single team
            result = conn.execute(
                text(
                    """
                SELECT
                    COUNT(*) FILTER (WHERE team_count = 2) as both_teams,
                    COUNT(*) FILTER (WHERE team_count = 1) as one_team,
                    COUNT(*) as total
                FROM (
                    SELECT game_id, COUNT(DISTINCT team_id) as team_count
                    FROM player_shifts
                    WHERE game_id LIKE '2024%'
                    GROUP BY game_id
                ) subq
            """
                )
            )

            both_teams, one_team, total = result.fetchone()

            # At least 95% of games should have both teams
            both_teams_ratio = both_teams / total if total > 0 else 0
            assert (
                both_teams_ratio >= 0.95
            ), f"Too many games with incomplete shift data: {both_teams_ratio:.1%} have both teams (expected >=95%)"

    def test_shifts_span_full_game(self, db_engine):
        """Shifts should exist across all periods of a game."""
        with db_engine.connect() as conn:
            # Check a recent game
            result = conn.execute(
                text(
                    """
                SELECT game_id,
                       ARRAY_AGG(DISTINCT period ORDER BY period) as periods
                FROM player_shifts
                WHERE game_id LIKE '2024%'
                GROUP BY game_id
                HAVING COUNT(DISTINCT period) >= 3
                LIMIT 5
            """
                )
            )

            games = list(result)

            assert len(games) > 0, "No recent games found with shifts across periods"

            for game_id, periods in games:
                # Should have at least periods 1, 2, 3
                assert (
                    1 in periods
                ), f"Game {game_id}: missing period 1 shifts (periods: {periods})"
                assert (
                    2 in periods
                ), f"Game {game_id}: missing period 2 shifts (periods: {periods})"
                assert (
                    3 in periods
                ), f"Game {game_id}: missing period 3 shifts (periods: {periods})"
