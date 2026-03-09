"""Tests for NBADataLoader class."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
from plugins.nba_data_loader import NBADataLoader


class TestNBADataLoader:
    """Test suite for NBADataLoader class."""

    def test_init(self):
        """Test NBADataLoader initialization."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)
        assert loader.db == mock_db

    def test_ensure_nba_games_table_exists(self):
        """Test table creation method."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)

        loader._ensure_nba_games_table_exists()

        # Verify execute was called with correct SQL
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS nba_games" in call_args

    def test_normalize_game_status(self):
        """Test game status normalization."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)

        # Test various status texts
        assert loader._normalize_game_status("Final") == "Final"
        assert loader._normalize_game_status("Game Final") == "Final"
        assert loader._normalize_game_status("In Progress") == "Live"
        assert loader._normalize_game_status("Live") == "Live"
        assert loader._normalize_game_status("7:30 pm ET") == "Scheduled"
        assert loader._normalize_game_status("2:00 am ET") == "Scheduled"
        assert loader._normalize_game_status("Unknown Status") == "Live"

    def test_extract_espn_competitors(self):
        """Test ESPN competitor extraction."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)

        # Create mock ESPN event
        event = {
            "competitions": [{
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {"abbreviation": "LAL"},
                        "score": "105"
                    },
                    {
                        "homeAway": "away",
                        "team": {"abbreviation": "BOS"},
                        "score": "98"
                    }
                ]
            }]
        }

        home_team, away_team, home_score, away_score = loader._extract_espn_competitors(event)

        assert home_team == "LAL"
        assert away_team == "BOS"
        assert home_score == 105
        assert away_score == 98

    def test_extract_espn_competitors_no_competitions(self):
        """Test ESPN competitor extraction when no competitions exist."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)

        event = {}

        home_team, away_team, home_score, away_score = loader._extract_espn_competitors(event)

        assert home_team is None
        assert away_team is None
        assert home_score == 0
        assert away_score == 0

    def test_parse_espn_game_event(self):
        """Test ESPN game event parsing."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)

        # Create mock ESPN event
        event = {
            "id": "401585",
            "date": "2026-02-04T00:00Z",
            "season": {"year": 2026},
            "status": {"type": {"description": "Final"}},
            "competitions": [{
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {"abbreviation": "LAL"},
                        "score": "105"
                    },
                    {
                        "homeAway": "away",
                        "team": {"abbreviation": "BOS"},
                        "score": "98"
                    }
                ]
            }]
        }

        params = loader._parse_espn_game_event(event)

        assert params is not None
        assert params["game_id"] == "401585"
        assert params["game_date"] == "2026-02-04"
        assert params["season"] == 2026
        assert params["home_team"] == "LAL"
        assert params["away_team"] == "BOS"
        assert params["home_score"] == 105
        assert params["away_score"] == 98
        assert params["status"] == "Final"

    def test_parse_espn_game_event_missing_teams(self):
        """Test ESPN game event parsing when teams are missing."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)

        # Create mock ESPN event without teams
        event = {
            "id": "401585",
            "date": "2026-02-04T00:00Z",
            "season": {"year": 2026},
            "status": {"type": {"description": "Final"}},
            "competitions": [{"competitors": []}]
        }

        params = loader._parse_espn_game_event(event)

        assert params is None

    def test_insert_or_update_nba_game(self):
        """Test NBA game insertion/update."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)

        params = {
            "game_id": "401585",
            "game_date": "2026-02-04",
            "season": 2026,
            "game_type": "Regular",
            "home_team": "LAL",
            "away_team": "BOS",
            "home_score": 105,
            "away_score": 98,
            "status": "Final"
        }

        loader._insert_or_update_nba_game(params)

        # Verify execute was called with correct parameters
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "INSERT INTO nba_games" in call_args[0][0]
        # The params are passed as the second positional argument
        assert len(call_args[0]) >= 2
        assert call_args[0][1] == params

    def test_build_scores_map(self):
        """Test building scores map from line score data."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)

        line_score = {
            "headers": ["GAME_ID", "TEAM_ID", "PTS"],
            "rowSet": [
                ["0022301234", 1610612747, 105],
                ["0022301234", 1610612738, 98]
            ]
        }

        l_cols = {"GAME_ID": 0, "TEAM_ID": 1, "PTS": 2}
        scores_map = loader._build_scores_map(line_score, l_cols)

        assert "0022301234" in scores_map
        assert scores_map["0022301234"][1610612747] == 105
        assert scores_map["0022301234"][1610612738] == 98

    def test_extract_team_abbreviations(self):
        """Test team abbreviation extraction."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)

        line_score = {
            "headers": ["TEAM_ID", "TEAM_ABBREVIATION"],
            "rowSet": [
                [1610612747, "LAL"],
                [1610612738, "BOS"]
            ]
        }

        l_cols = {"TEAM_ID": 0, "TEAM_ABBREVIATION": 1}
        home_team, away_team = loader._extract_team_abbreviations(
            1610612747, 1610612738, line_score, l_cols
        )

        assert home_team == "LAL"
        assert away_team == "BOS"

    def test_extract_team_abbreviations_no_line_score(self):
        """Test team abbreviation extraction without line score."""
        mock_db = Mock()
        loader = NBADataLoader(mock_db)

        home_team, away_team = loader._extract_team_abbreviations(
            1610612747, 1610612738, None, {}
        )

        assert home_team == "1610612747"
        assert away_team == "1610612738"
