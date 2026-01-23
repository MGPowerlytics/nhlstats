"""
Test-Driven Development: NHL Play-by-Play Data Collection

Tests to ensure:
1. Play-by-play data is collected daily
2. Database has complete data from 2021-2022 season onwards
3. Data is being loaded into PostgreSQL
4. File structure is maintained properly

NOTE: These are integration tests that require production PostgreSQL with NHL data.
"""

import os
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# Skip these tests unless running against production database
pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_HOST") != "postgres",
    reason="Integration tests require production PostgreSQL database with NHL data"
)


class TestNHLPlayByPlayCollection:
    """TDD tests for NHL play-by-play data collection and database loading."""

    @pytest.fixture
    def db_engine(self):
        """Create database engine for testing."""
        # For local testing, override host to localhost
        import os

        os.environ["POSTGRES_HOST"] = "localhost"

        from plugins.db_manager import DBManager

        db = DBManager()
        return db.get_engine()

    def test_play_events_table_exists(self, db_engine):
        """play_events table should exist in database."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'play_events' AND table_schema = 'public'
            """
                )
            )
            tables = [row[0] for row in result]
            assert "play_events" in tables, "play_events table not found in database"

    def test_play_events_has_data_from_2021_season(self, db_engine):
        """Database should contain play-by-play data from 2021-2022 season onwards."""
        with db_engine.connect() as conn:
            # Game IDs starting with 2021 indicate 2021-2022 season
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM play_events
                WHERE game_id LIKE '2021%'
            """
                )
            )
            count_2021 = result.scalar()

            assert count_2021 > 0, "No play-by-play data found for 2021-2022 season"
            assert (
                count_2021 > 10000
            ), f"Insufficient 2021-2022 season data (found {count_2021} events, expected >10000)"

    def test_play_events_has_data_from_2022_season(self, db_engine):
        """Database should contain data from 2022-2023 season."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM play_events
                WHERE game_id LIKE '2022%'
            """
                )
            )
            count = result.scalar()
            assert (
                count > 10000
            ), f"Insufficient 2022-2023 season data (found {count} events)"

    def test_play_events_has_data_from_2023_season(self, db_engine):
        """Database should contain data from 2023-2024 season."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM play_events
                WHERE game_id LIKE '2023%'
            """
                )
            )
            count = result.scalar()
            assert (
                count > 10000
            ), f"Insufficient 2023-2024 season data (found {count} events)"

    def test_play_events_has_current_season_data(self, db_engine):
        """Database should contain data from current 2024-2025 season."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM play_events
                WHERE game_id LIKE '2024%'
            """
                )
            )
            count = result.scalar()
            assert count > 0, "No play-by-play data found for 2024-2025 season"

    def test_play_events_minimum_total_games(self, db_engine):
        """Database should have minimum number of games with events."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(DISTINCT game_id)
                FROM play_events
            """
                )
            )
            game_count = result.scalar()

            # Since 2021-2022: ~82 games/team * 32 teams / 2 * 4 seasons = ~5200 games
            # Using conservative estimate of 4000+ games
            assert (
                game_count >= 4000
            ), f"Insufficient game coverage (found {game_count} games, expected >=4000)"

    def test_recent_data_folders_exist(self):
        """Local data folders should exist for recent dates."""
        data_dir = Path("data/games")
        assert data_dir.exists(), "data/games directory does not exist"

        # Check last 3 days
        today = datetime.now().date()
        for days_ago in range(3):
            date = today - timedelta(days=days_ago)
            date_str = date.strftime("%Y-%m-%d")
            date_folder = data_dir / date_str

            # At least one of the recent days should have a folder
            # (some days may not have games)

        # Check that we have at least SOME recent folders
        recent_folders = [
            f for f in data_dir.iterdir() if f.is_dir() and f.name.startswith("202")
        ]

        assert len(recent_folders) > 0, "No date folders found in data/games/"

        # Check most recent folder is within last 7 days
        most_recent = max([f.name for f in recent_folders if len(f.name) == 10])
        most_recent_date = datetime.strptime(most_recent, "%Y-%m-%d").date()
        days_since_last = (today - most_recent_date).days

        assert (
            days_since_last <= 7
        ), f"Most recent data is {days_since_last} days old (last: {most_recent})"

    def test_data_files_have_correct_format(self):
        """Play-by-play JSON files should follow naming convention."""
        data_dir = Path("data/games")

        # Find a recent date folder
        recent_folders = sorted(
            [f for f in data_dir.iterdir() if f.is_dir() and f.name.startswith("202")],
            reverse=True,
        )[:5]

        playbyplay_files = []
        for folder in recent_folders:
            pbp_files = list(folder.glob("*_playbyplay.json"))
            playbyplay_files.extend(pbp_files)

        if len(playbyplay_files) > 0:
            # Check file naming convention: GAMEID_playbyplay.json
            sample_file = playbyplay_files[0]
            assert (
                "_playbyplay.json" in sample_file.name
            ), f"File doesn't match naming convention: {sample_file.name}"

            game_id = sample_file.name.split("_")[0]
            assert game_id.isdigit(), f"Game ID should be numeric: {game_id}"
            assert len(game_id) == 10, f"Game ID should be 10 digits: {game_id}"

    def test_nhl_game_events_class_exists(self):
        """NHLGameEvents class should be importable."""
        from plugins.nhl_game_events import NHLGameEvents

        assert NHLGameEvents is not None

    def test_nhl_game_events_has_required_methods(self):
        """NHLGameEvents should have all required methods for data collection."""
        from plugins.nhl_game_events import NHLGameEvents

        required_methods = [
            "get_schedule_by_date",
            "get_game_data",
            "download_game",
            "download_games_for_date",
            "download_season",
        ]

        for method in required_methods:
            assert hasattr(
                NHLGameEvents, method
            ), f"NHLGameEvents missing required method: {method}"

    def test_dag_has_nhl_download_task(self):
        """DAG should have task for downloading NHL games."""
        # Import DAG file
        import sys
        from pathlib import Path

        dag_path = Path(__file__).parent.parent / "dags"
        sys.path.insert(0, str(dag_path))

        # Read DAG file content
        dag_file = dag_path / "multi_sport_betting_workflow.py"
        content = dag_file.read_text()

        # Check that NHL is in the sports list
        assert '"nhl"' in content.lower(), "DAG missing NHL in sports configuration"

        # Check that download_games tasks are created
        assert (
            'task_id=f"{sport}_download_games"' in content
            or 'f"{sport}_download_games"' in content
        ), "DAG not creating download_games tasks"

        # Check for nhl_game_events module usage
        assert (
            "nhl_game_events" in content.lower()
        ), "DAG not configured to use nhl_game_events module"

    def test_play_events_coverage_by_season(self, db_engine):
        """Verify event coverage for each season since 2021-2022."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT
                    LEFT(game_id, 4) as season,
                    COUNT(DISTINCT game_id) as games,
                    COUNT(*) as events
                FROM play_events
                WHERE game_id ~ '^202[1-4]'
                GROUP BY LEFT(game_id, 4)
                ORDER BY season
            """
                )
            )

            seasons = list(result)

            # Should have data for 2021, 2022, 2023, 2024
            season_years = [s[0] for s in seasons]
            assert "2021" in season_years, "Missing 2021-2022 season data"
            assert "2022" in season_years, "Missing 2022-2023 season data"
            assert "2023" in season_years, "Missing 2023-2024 season data"
            assert "2024" in season_years, "Missing 2024-2025 season data"

            # Each season should have reasonable number of games
            for season, games, events in seasons:
                assert (
                    games >= 100
                ), f"Season {season}: insufficient games ({games}, expected >=100)"
                assert (
                    events >= 20000
                ), f"Season {season}: insufficient events ({events}, expected >=20000)"


class TestNHLDataConsistency:
    """Tests for data consistency and quality."""

    @pytest.fixture
    def db_engine(self):
        """Create database engine for testing."""
        # For local testing, override host to localhost
        import os

        os.environ["POSTGRES_HOST"] = "localhost"

        from plugins.db_manager import DBManager

        db = DBManager()
        return db.get_engine()

    def test_no_null_game_ids(self, db_engine):
        """All play events should have valid game IDs."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(*)
                FROM play_events
                WHERE game_id IS NULL OR game_id = ''
            """
                )
            )
            null_count = result.scalar()
            assert null_count == 0, f"Found {null_count} events with NULL/empty game_id"

    def test_events_per_game_reasonable(self, db_engine):
        """Average events per game should be within reasonable range."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT AVG(event_count)::INTEGER as avg_events
                FROM (
                    SELECT game_id, COUNT(*) as event_count
                    FROM play_events
                    GROUP BY game_id
                ) subq
            """
                )
            )
            avg_events = result.scalar()

            # NHL games typically have 200-400 events
            assert (
                150 <= avg_events <= 500
            ), f"Average events per game out of range: {avg_events} (expected 150-500)"

    def test_event_types_exist(self, db_engine):
        """Play events should have various event types (shots, goals, etc.)."""
        with db_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT COUNT(DISTINCT type_desc_key)
                FROM play_events
                WHERE type_desc_key IS NOT NULL
            """
                )
            )
            type_count = result.scalar()

            # Should have multiple event types (shot, goal, hit, penalty, faceoff, etc.)
            assert (
                type_count >= 5
            ), f"Found only {type_count} event types (expected >=5)"
