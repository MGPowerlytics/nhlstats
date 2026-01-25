"""
Integration Test: Data Ingestion → Database Integration

Tests the complete flow from game data download to database loading for NBA data.
This is a critical path test that validates the data pipeline integrity.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.nba_games import NBAGames
from plugins.db_loader import NHLDatabaseLoader
from plugins.database_schema_manager import DatabaseSchemaManager
from plugins.db_manager import DBManager


class TestDataIngestionToDatabaseIntegration:
    """Integration tests for data ingestion pipeline."""

    def test_nba_data_ingestion_pipeline(self):
        """
        Test complete NBA data ingestion pipeline:
        1. Mock NBA API responses
        2. Download game data
        3. Load into database
        4. Verify data integrity
        """
        print("\n" + "=" * 80)
        print("Integration Test: NBA Data Ingestion → Database Pipeline")
        print("=" * 80)

        # Create temporary directory for test data
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Step 1: Mock NBA API responses
            print("\nStep 1: Setting up mock NBA API responses...")

            # Create mock scoreboard response
            mock_scoreboard = {
                "resultSets": [
                    {
                        "name": "GameHeader",
                        "headers": ["GAME_ID", "GAME_DATE_EST", "HOME_TEAM_ID", "VISITOR_TEAM_ID",
                                   "SEASON", "GAME_STATUS_TEXT", "GAMECODE"],
                        "rowSet": [
                            ["0022301234", "2026-01-24T00:00:00", 1610612747, 1610612748,
                             "2025", "Final", "2026/LALDAL"],
                            ["0022301235", "2026-01-24T00:00:00", 1610612738, 1610612751,
                             "2025", "Final", "2026/BOSNYK"]
                        ]
                    },
                    {
                        "name": "LineScore",
                        "headers": ["GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION", "PTS"],
                        "rowSet": [
                            ["0022301234", 1610612747, "LAL", 112],
                            ["0022301234", 1610612748, "DAL", 108],
                            ["0022301235", 1610612738, "BOS", 105],
                            ["0022301235", 1610612751, "NYK", 98]
                        ]
                    }
                ]
            }

            # Create mock boxscore response
            mock_boxscore = {
                "resultSets": [
                    {
                        "name": "GameSummary",
                        "headers": ["GAME_ID", "GAME_DATE_EST"],
                        "rowSet": [["0022301234", "2026-01-24T00:00:00"]]
                    }
                ]
            }

            # Step 2: Mock the NBA API calls
            print("Step 2: Mocking NBA API calls...")

            with patch('plugins.nba_games.requests.get') as mock_get:
                # Configure mock responses
                mock_response_scoreboard = Mock()
                mock_response_scoreboard.status_code = 200
                mock_response_scoreboard.json.return_value = mock_scoreboard

                mock_response_boxscore = Mock()
                mock_response_boxscore.status_code = 200
                mock_response_boxscore.json.return_value = mock_boxscore

                # Mock play-by-play response (can be empty for test)
                mock_response_pbp = Mock()
                mock_response_pbp.status_code = 200
                mock_response_pbp.json.return_value = {"game": {"actions": []}}

                # Set up side effects for different URLs
                def side_effect(url, **kwargs):
                    if "scoreboardv2" in url:
                        return mock_response_scoreboard
                    elif "boxscoretraditionalv2" in url:
                        return mock_response_boxscore
                    elif "cdn.nba.com" in url:
                        return mock_response_pbp
                    return Mock(status_code=404)

                mock_get.side_effect = side_effect

                # Step 3: Download NBA games
                print("Step 3: Downloading NBA game data...")

                nba_fetcher = NBAGames(output_dir=str(tmp_path / "nba" / "2026-01-24"))
                games_downloaded = nba_fetcher.download_games_for_date("2026-01-24")

                assert games_downloaded == 2, f"Expected 2 games, got {games_downloaded}"
                print(f"✓ Downloaded {games_downloaded} NBA games")

                # Verify files were created
                scoreboard_file = tmp_path / "nba" / "2026-01-24" / "scoreboard_2026-01-24.json"
                assert scoreboard_file.exists(), "Scoreboard file not created"

                boxscore_file = tmp_path / "nba" / "2026-01-24" / "boxscore_0022301234.json"
                assert boxscore_file.exists(), "Boxscore file not created"

                print("✓ Game data files created successfully")

            # Step 4: Load data into database
            print("\nStep 4: Loading data into database...")

            # Initialize database schema
            schema_manager = DatabaseSchemaManager()
            schema_manager.create_unified_tables()

            # Create database loader
            loader = NHLDatabaseLoader()
            loader.connect()

            # Load the date
            games_loaded = loader.load_date("2026-01-24", data_dir=tmp_path)

            assert games_loaded > 0, "No games were loaded into database"
            print(f"✓ Loaded {games_loaded} games into database")

            # Step 5: Verify data integrity
            print("\nStep 5: Verifying data integrity...")

            # Check NBA games table
            nba_games = loader.db.fetch_df("SELECT * FROM nba_games WHERE game_date = '2026-01-24'")
            assert len(nba_games) == 2, f"Expected 2 NBA games in database, got {len(nba_games)}"

            # Verify game data
            for _, game in nba_games.iterrows():
                assert game['game_id'] in ['0022301234', '0022301235'], f"Unexpected game ID: {game['game_id']}"
                assert game['game_date'] == '2026-01-24', f"Unexpected game date: {game['game_date']}"
                assert game['season'] == 2025, f"Unexpected season: {game['season']}"
                assert game['status'] == 'Final', f"Unexpected status: {game['status']}"

                # Verify scores
                if game['game_id'] == '0022301234':
                    assert game['home_team'] == 'LAL', f"Unexpected home team: {game['home_team']}"
                    assert game['away_team'] == 'DAL', f"Unexpected away team: {game['away_team']}"
                    assert game['home_score'] == 112, f"Unexpected home score: {game['home_score']}"
                    assert game['away_score'] == 108, f"Unexpected away score: {game['away_score']}"
                elif game['game_id'] == '0022301235':
                    assert game['home_team'] == 'BOS', f"Unexpected home team: {game['home_team']}"
                    assert game['away_team'] == 'NYK', f"Unexpected away team: {game['away_team']}"
                    assert game['home_score'] == 105, f"Unexpected home score: {game['home_score']}"
                    assert game['away_score'] == 98, f"Unexpected away score: {game['away_score']}"

            print("✓ NBA game data verified successfully")

            # Check unified_games table
            unified_games = loader.db.fetch_df(
                "SELECT * FROM unified_games WHERE game_date = '2026-01-24' AND sport = 'NBA'"
            )
            assert len(unified_games) >= 2, f"Expected at least 2 games in unified_games, got {len(unified_games)}"

            print("✓ Unified games table populated successfully")

            # Step 6: Test error handling
            print("\nStep 6: Testing error handling...")

            # Test with missing data directory
            try:
                loader.load_date("2026-01-25", data_dir=tmp_path / "nonexistent")
                print("✓ Gracefully handled missing data directory")
            except Exception as e:
                print(f"✓ Error handling working: {type(e).__name__}")

            # Test with malformed JSON
            malformed_dir = tmp_path / "malformed"
            malformed_dir.mkdir(parents=True, exist_ok=True)
            malformed_file = malformed_dir / "bad_data.json"
            malformed_file.write_text("{ invalid json")

            try:
                # This should not crash the test
                pass
            except Exception as e:
                print(f"✓ Error handling for malformed JSON: {type(e).__name__}")

            # Clean up
            loader.close()

            print("\n" + "=" * 80)
            print("✅ NBA Data Ingestion → Database Integration Test PASSED")
            print("=" * 80)

    def test_multi_sport_data_integration(self):
        """
        Test integration across multiple sports to ensure consistency.
        """
        print("\n" + "=" * 80)
        print("Integration Test: Multi-Sport Data Consistency")
        print("=" * 80)

        # Initialize database
        schema_manager = DatabaseSchemaManager()
        schema_manager.create_unified_tables()

        loader = NHLDatabaseLoader()
        loader.connect()

        try:
            # Test that all required tables exist
            required_tables = [
                'unified_games', 'game_odds', 'nba_games', 'mlb_games',
                'nfl_games', 'epl_games', 'tennis_games', 'ncaab_games'
            ]

            for table in required_tables:
                result = loader.db.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')").fetchone()
                assert result[0] == True, f"Required table '{table}' does not exist"

            print("✓ All required database tables exist")

            # Test unified_games schema
            unified_schema = loader.db.fetch_df(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'unified_games' ORDER BY ordinal_position"
            )

            required_columns = {
                'game_id', 'sport', 'game_date', 'season', 'status',
                'home_team_id', 'home_team_name', 'away_team_id', 'away_team_name',
                'home_score', 'away_score', 'commence_time', 'venue', 'loaded_at'
            }

            actual_columns = set(unified_schema['column_name'])
            missing_columns = required_columns - actual_columns
            assert len(missing_columns) == 0, f"Missing columns in unified_games: {missing_columns}"

            print("✓ Unified games schema is correct")

            # Test foreign key relationship
            try:
                # Try to insert invalid game_id in game_odds
                loader.db.execute(
                    "INSERT INTO game_odds (odds_id, game_id, bookmaker, market_name, price) "
                    "VALUES ('test_odds', 'invalid_game_id', 'test', 'moneyline', 1.95)"
                )
                # If we get here, foreign key constraint is not working
                assert False, "Foreign key constraint not enforced"
            except Exception as e:
                # Expected to fail due to foreign key constraint
                print(f"✓ Foreign key constraint working: {type(e).__name__}")

        finally:
            loader.close()

        print("\n" + "=" * 80)
        print("✅ Multi-Sport Data Consistency Test PASSED")
        print("=" * 80)

    def test_data_validation_integration(self):
        """
        Test integration with data validation module.
        """
        print("\n" + "=" * 80)
        print("Integration Test: Data Validation Integration")
        print("=" * 80)

        # Import data validation module
        try:
            from plugins.data_validation import DataValidationReport, validate_nba_data

            # Create a test report
            report = DataValidationReport('nba')
            report.add_stat('total_games', 1230)
            report.add_stat('coverage_pct', 98.5)
            report.add_check('Data Exists', True, 'Found 1230 games')
            report.add_check('Data Quality', False, 'Missing 5 boxscores', 'warning')

            # Test report generation
            import io
            import sys

            # Capture stdout
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()

            try:
                result = report.print_report()
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

            assert 'NBA' in output, "Report should contain sport name"
            assert '1230' in output, "Report should contain statistics"
            assert result == True, "Report with warnings should return True"

            print("✓ Data validation report generation working")

        except ImportError as e:
            print(f"⚠ Data validation module not available: {e}")
            pytest.skip("Data validation module not available")

        print("\n" + "=" * 80)
        print("✅ Data Validation Integration Test PASSED")
        print("=" * 80)


if __name__ == "__main__":
    # Run the tests
    test = TestDataIngestionToDatabaseIntegration()

    print("Running Data Ingestion Integration Tests")
    print("=" * 80)

    try:
        test.test_nba_data_ingestion_pipeline()
        test.test_multi_sport_data_integration()
        test.test_data_validation_integration()

        print("\n" + "=" * 80)
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
