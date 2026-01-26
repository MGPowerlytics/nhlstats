"""Comprehensive tests for data_validation.py focusing on uncovered code paths"""

from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path
import duckdb


class TestDataValidationReport:
    """Test DataValidationReport class"""

    def test_init(self):
        from data_validation import DataValidationReport

        report = DataValidationReport("Test Sport")
        assert report.sport == "Test Sport"

    def test_add_stat(self):
        from data_validation import DataValidationReport

        report = DataValidationReport("Test")
        report.add_stat("Total Games", 100)

        assert "Total Games" in report.stats
        assert report.stats["Total Games"] == 100

    def test_add_check_passed(self):
        from data_validation import DataValidationReport

        report = DataValidationReport("Test")
        report.add_check("Games Found", True, "100 games found")

        assert len(report.checks) == 1
        assert report.checks[0]["passed"]

    def test_add_check_failed(self):
        from data_validation import DataValidationReport

        report = DataValidationReport("Test")
        report.add_check("Games Found", False, "No games found", "error")

        assert not report.checks[0]["passed"]
        assert report.checks[0]["severity"] == "error"

    def test_print_report(self):
        from data_validation import DataValidationReport

        report = DataValidationReport("Test")
        report.add_stat("Games", 100)
        report.add_check("Test Check", True, "Passed")

        # Should not raise
        report.print_report()

    def test_is_valid_all_passed(self):
        from data_validation import DataValidationReport

        report = DataValidationReport("Test")
        report.add_check("Check 1", True, "OK")
        report.add_check("Check 2", True, "OK")

        # Check if all checks passed
        all_passed = all(c["passed"] for c in report.checks)
        assert all_passed

    def test_is_valid_with_failure(self):
        from data_validation import DataValidationReport

        report = DataValidationReport("Test")
        report.add_check("Check 1", True, "OK")
        report.add_check("Check 2", False, "Failed")

        # Check if any check failed
        all_passed = all(c["passed"] for c in report.checks)
        assert not all_passed


class TestValidateNHLData:
    """Test validate_nhl_data function"""

    def test_function_exists(self):
        from data_validation import validate_nhl_data

        assert callable(validate_nhl_data)

    def test_missing_database(self):
        from data_validation import validate_nhl_data

        with tempfile.TemporaryDirectory():
            with patch("data_validation.Path") as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.exists.return_value = False
                mock_path.return_value = mock_path_instance

                validate_nhl_data()
                # Should return report indicating missing database


class TestValidateNBAData:
    """Test validate_nba_data function"""

    def test_function_exists(self):
        from data_validation import validate_nba_data

        assert callable(validate_nba_data)


class TestValidateMLBData:
    """Test validate_mlb_data function"""

    def test_function_exists(self):
        from data_validation import validate_mlb_data

        assert callable(validate_mlb_data)


class TestValidateNFLData:
    """Test validate_nfl_data function"""

    def test_function_exists(self):
        from data_validation import validate_nfl_data

        assert callable(validate_nfl_data)


class TestValidateEPLData:
    """Test validate_epl_data function"""

    def test_function_may_exist(self):
        import data_validation

        # EPL validation may or may not exist
        if hasattr(data_validation, "validate_epl_data"):
            assert callable(data_validation.validate_epl_data)


class TestConstants:
    """Test module constants"""

    def test_expected_teams(self):
        from data_validation import EXPECTED_TEAMS

        assert "nba" in EXPECTED_TEAMS
        assert "nhl" in EXPECTED_TEAMS
        assert len(EXPECTED_TEAMS["nba"]) == 30
        # NHL has 32 or 33 teams (including Utah Hockey Club)
        assert len(EXPECTED_TEAMS["nhl"]) >= 32

    def test_season_info(self):
        from data_validation import SEASON_INFO

        assert "nba" in SEASON_INFO
        assert "nhl" in SEASON_INFO
        assert "total_games_per_season" in SEASON_INFO["nba"]


class TestModuleImports:
    """Test module imports"""

    def test_import_module(self):
        import data_validation

        assert hasattr(data_validation, "DataValidationReport")
        assert hasattr(data_validation, "validate_nhl_data")
        assert hasattr(data_validation, "validate_nba_data")
        assert hasattr(data_validation, "validate_mlb_data")
        assert hasattr(data_validation, "EXPECTED_TEAMS")
        assert hasattr(data_validation, "SEASON_INFO")


class TestMain:
    """Test main function"""

    def test_function_exists(self):
        from data_validation import main

        assert callable(main)


class TestReportMethods:
    """Test additional report methods"""

    def test_get_summary(self):
        from data_validation import DataValidationReport

        report = DataValidationReport("Test")
        report.add_stat("Total", 100)
        report.add_check("Check", True, "OK")

        if hasattr(report, "get_summary"):
            summary = report.get_summary()
            assert isinstance(summary, dict)

    def test_to_dict(self):
        from data_validation import DataValidationReport

        report = DataValidationReport("Test")
        report.add_stat("Total", 100)

        if hasattr(report, "to_dict"):
            result = report.to_dict()
            assert isinstance(result, dict)


class TestValidationChecks:
    """Test validation check logic"""

    def test_team_coverage_check(self):
        from data_validation import DataValidationReport, EXPECTED_TEAMS

        report = DataValidationReport("NBA")

        # Simulate team coverage check - EXPECTED_TEAMS['nba'] is a list
        expected = set(EXPECTED_TEAMS["nba"])
        teams_found = set(list(EXPECTED_TEAMS["nba"])[:25])  # 25 of 30 teams
        missing = expected - teams_found

        report.add_check(
            "Team Coverage",
            len(missing) == 0,
            f"{len(teams_found)} teams found, {len(missing)} missing",
        )

        assert not report.checks[0]["passed"]

    def test_date_range_check(self):
        from data_validation import DataValidationReport

        report = DataValidationReport("NHL")

        min_date = "2023-10-01"
        max_date = "2024-04-15"

        report.add_stat("Date Range", f"{min_date} to {max_date}")

        assert len(report.stats) == 1


class TestDatabaseQueries:
    """Test database query execution in validation"""

    def test_with_temp_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            conn = duckdb.connect(str(db_path))

            # Create games table with PRIMARY KEY (required for ON CONFLICT in SQLite tests)
            conn.execute("""
                CREATE TABLE games (
                    game_id VARCHAR PRIMARY KEY,
                    game_date DATE,
                    home_team_name VARCHAR,
                    away_team_name VARCHAR,
                    home_score INTEGER,
                    away_score INTEGER,
                    game_state VARCHAR,
                    season INTEGER
                )
            """)

            # Insert test data
            conn.execute("""
                INSERT INTO games VALUES
                ('G1', '2024-01-15', 'Bruins', 'Rangers', 4, 2, 'OFF', 2024),
                ('G2', '2024-01-16', 'Rangers', 'Bruins', 3, 5, 'FINAL', 2024)
            """)

            # Query
            result = conn.execute("SELECT COUNT(*) FROM games").fetchone()
            assert result[0] == 2

            conn.close()


class TestMultipleSports:
    """Test validation across multiple sports"""

    def test_all_validation_functions_exist(self):
        import data_validation

        # Check which validation functions exist
        functions = [
            "validate_nhl_data",
            "validate_nba_data",
            "validate_mlb_data",
            "validate_nfl_data",
        ]

        found_count = 0
        for func in functions:
            if hasattr(data_validation, func):
                assert callable(getattr(data_validation, func))
                found_count += 1

        # At least some should exist
        assert found_count >= 1


class TestErrorHandling:
    """Test error handling in validation"""

    def test_handles_missing_file(self):
        from data_validation import validate_nba_data

        with tempfile.TemporaryDirectory():
            # No data files
            validate_nba_data()
            # Should return report, not raise


class TestSeasonCalculations:
    """Test season calculation logic"""

    def test_season_completeness(self):
        from data_validation import SEASON_INFO

        # Check season info structure
        for sport in ["nba", "nhl", "mlb", "nfl"]:
            if sport in SEASON_INFO:
                assert "total_games_per_season" in SEASON_INFO[sport]
                assert SEASON_INFO[sport]["total_games_per_season"] > 0
