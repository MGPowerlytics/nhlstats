"""
Tests for soccer, CBB, and tennis box-score fetchers.

Covers parsing logic and skip-missing-game behaviour without requiring
live network connections or a real PostgreSQL database.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from io import StringIO

import pandas as pd
import pytest

# Ensure plugins/ is importable when running pytest from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Shared mock DB fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_db():
    """Return a mock DBManager that reports *no* valid game IDs by default."""
    db = MagicMock()
    # simulate unified_games returning no rows (skip-missing-game scenario)
    db.execute.return_value.fetchall.return_value = []
    return db


@pytest.fixture()
def mock_db_with_game(mock_db):
    """Return a mock DBManager that validates the game_id 'GAME_ID_1'."""
    mock_db.execute.return_value.fetchall.return_value = [("GAME_ID_1",)]
    return mock_db


# ===========================================================================
# Soccer Box Score Fetcher
# ===========================================================================


class TestSoccerBoxScoreFetcherParsing:
    """Unit tests for SoccerBoxScoreFetcher CSV parsing logic."""

    def _make_row(self, **kwargs) -> "pd.Series":
        """Build a minimal football-data.co.uk style CSV row."""
        defaults = {
            "Date": pd.Timestamp("2023-10-28"),
            "HomeTeam": "Arsenal",
            "AwayTeam": "Chelsea",
            "FTHG": 2,
            "FTAG": 1,
            "FTR": "H",
            "HS": 14,
            "AS": 8,
            "HST": 7,
            "AST": 3,
            "HF": 10,
            "AF": 12,
            "HY": 1,
            "AY": 2,
            "HR": 0,
            "AR": 0,
            "HC": 5,
            "AC": 3,
        }
        defaults.update(kwargs)
        return pd.Series(defaults)

    def test_build_team_rows_returns_two_dicts(self, mock_db):
        """_build_team_rows should return exactly two dicts (home, away)."""
        from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

        fetcher = SoccerBoxScoreFetcher(sport="EPL", db=mock_db)
        row = self._make_row()
        result = fetcher._build_team_rows(row)

        assert len(result) == 2
        home, away = result
        assert home["is_home"] is True
        assert away["is_home"] is False

    def test_build_team_rows_goals_and_result(self, mock_db):
        """Home team wins; points_for/against and won flag must be correct."""
        from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

        fetcher = SoccerBoxScoreFetcher(sport="EPL", db=mock_db)
        row = self._make_row(FTHG=3, FTAG=0, FTR="H")
        home, away = fetcher._build_team_rows(row)

        assert home["points_for"] == 3
        assert home["points_against"] == 0
        assert home["won"] is True
        assert away["won"] is False
        assert home["margin"] == 3
        assert away["margin"] == -3

    def test_build_team_rows_draw(self, mock_db):
        """Draw result — both won flags False."""
        from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

        fetcher = SoccerBoxScoreFetcher(sport="EPL", db=mock_db)
        row = self._make_row(FTHG=1, FTAG=1, FTR="D")
        home, away = fetcher._build_team_rows(row)

        assert home["won"] is False
        assert away["won"] is False

    def test_build_team_rows_ext_shots(self, mock_db):
        """Extension dict contains shots and corners from CSV."""
        from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

        fetcher = SoccerBoxScoreFetcher(sport="EPL", db=mock_db)
        row = self._make_row(HS=12, AS=6, HC=7, AC=2)
        home, away = fetcher._build_team_rows(row)

        assert home["ext"]["shots"] == 12
        assert away["ext"]["shots"] == 6
        assert home["ext"]["corners"] == 7
        assert away["ext"]["corners"] == 2

    def test_build_team_rows_sport_label(self, mock_db):
        """sport field must match fetcher.SPORT."""
        from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

        fetcher = SoccerBoxScoreFetcher(sport="Ligue1", db=mock_db)
        row = self._make_row()
        home, _ = fetcher._build_team_rows(row)
        assert home["sport"] == "Ligue1"

    def test_game_id_format(self, mock_db):
        """game_id must follow {league_code}_{YYYYMMDD}_{HA}_{AA} pattern."""
        from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

        fetcher = SoccerBoxScoreFetcher(sport="EPL", db=mock_db)
        row = self._make_row()
        home, _ = fetcher._build_team_rows(row)
        parts = home["game_id"].split("_")
        assert len(parts) == 4
        assert parts[0] == "E0"
        assert len(parts[1]) == 8  # YYYYMMDD

    def test_season_label_august_match(self, mock_db):
        """Match in August 2023 should be in season '2023-24'."""
        from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

        fetcher = SoccerBoxScoreFetcher(sport="EPL", db=mock_db)
        row = self._make_row(Date=pd.Timestamp("2023-08-12"))
        home, _ = fetcher._build_team_rows(row)
        assert home["season"] == "2023-24"

    def test_season_label_february_match(self, mock_db):
        """Match in February 2024 should be in season '2023-24'."""
        from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

        fetcher = SoccerBoxScoreFetcher(sport="EPL", db=mock_db)
        row = self._make_row(Date=pd.Timestamp("2024-02-10"))
        home, _ = fetcher._build_team_rows(row)
        assert home["season"] == "2023-24"


class TestSoccerBoxScoreUpsertSkipsMissingGame:
    """upsert_rows must skip rows whose game_id is absent from unified_games."""

    def test_skip_all_when_no_valid_ids(self, mock_db):
        """All rows skipped when unified_games returns empty."""
        from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

        fetcher = SoccerBoxScoreFetcher(sport="EPL", db=mock_db)
        row = {
            "game_id": "E0_20231028_ARS_CHE",
            "sport": "EPL",
            "team": "Arsenal",
            "opponent": "Chelsea",
            "is_home": True,
            "game_date": date(2023, 10, 28),
            "season": "2023-24",
            "points_for": 2,
            "points_against": 1,
            "won": True,
            "margin": 1,
            "ext": {"shots": 14},
        }
        count = fetcher.upsert_rows([row])
        assert count == 0

    def test_upsert_when_game_id_valid(self):
        """upsert_rows calls db.execute when game_id exists in unified_games."""
        from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [("E0_20231028_ARS_CHE",)]

        fetcher = SoccerBoxScoreFetcher(sport="EPL", db=db)
        row = {
            "game_id": "E0_20231028_ARS_CHE",
            "sport": "EPL",
            "team": "Arsenal",
            "opponent": "Chelsea",
            "is_home": True,
            "game_date": date(2023, 10, 28),
            "season": "2023-24",
            "points_for": 2,
            "points_against": 1,
            "won": True,
            "margin": 1,
            "ext": {},
        }
        count = fetcher.upsert_rows([row])
        assert count == 1


# ===========================================================================
# CBB Box Score Fetcher
# ===========================================================================


_ESPN_SUMMARY_FIXTURE = {
    "header": {
        "competitions": [
            {
                "date": "2024-01-15T22:00:00Z",
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": "78",
                        "team": {"displayName": "Duke Blue Devils"},
                    },
                    {
                        "homeAway": "away",
                        "score": "65",
                        "team": {"displayName": "UNC Tar Heels"},
                    },
                ],
            }
        ]
    },
    "boxscore": {
        "teams": [
            {
                "team": {"displayName": "Duke Blue Devils"},
                "statistics": [
                    {"name": "fieldGoalsMade", "displayValue": "30"},
                    {"name": "fieldGoalsAttempted", "displayValue": "60"},
                    {"name": "threePointFieldGoalsMade", "displayValue": "8"},
                    {"name": "threePointFieldGoalsAttempted", "displayValue": "20"},
                    {"name": "freeThrowsMade", "displayValue": "10"},
                    {"name": "freeThrowsAttempted", "displayValue": "12"},
                    {"name": "assists", "displayValue": "15"},
                    {"name": "totalRebounds", "displayValue": "35"},
                    {"name": "offensiveRebounds", "displayValue": "10"},
                    {"name": "steals", "displayValue": "7"},
                    {"name": "blocks", "displayValue": "4"},
                    {"name": "turnovers", "displayValue": "10"},
                    {"name": "fouls", "displayValue": "18"},
                    {"name": "points", "displayValue": "78"},
                ],
            },
            {
                "team": {"displayName": "UNC Tar Heels"},
                "statistics": [
                    {"name": "fieldGoalsMade", "displayValue": "25"},
                    {"name": "fieldGoalsAttempted", "displayValue": "58"},
                    {"name": "threePointFieldGoalsMade", "displayValue": "5"},
                    {"name": "threePointFieldGoalsAttempted", "displayValue": "15"},
                    {"name": "freeThrowsMade", "displayValue": "10"},
                    {"name": "freeThrowsAttempted", "displayValue": "14"},
                    {"name": "assists", "displayValue": "12"},
                    {"name": "totalRebounds", "displayValue": "30"},
                    {"name": "offensiveRebounds", "displayValue": "8"},
                    {"name": "steals", "displayValue": "5"},
                    {"name": "blocks", "displayValue": "2"},
                    {"name": "turnovers", "displayValue": "12"},
                    {"name": "fouls", "displayValue": "20"},
                    {"name": "points", "displayValue": "65"},
                ],
            },
        ]
    },
}


class TestCBBBoxScoreFetcherParsing:
    """Tests for CBBBoxScoreFetcher ESPN parsing logic."""

    def test_parse_summary_returns_two_rows(self, mock_db):
        """_parse_summary must return exactly two team dicts."""
        from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

        fetcher = CBBBoxScoreFetcher(sport="NCAAB", db=mock_db)
        rows = fetcher._parse_summary(_ESPN_SUMMARY_FIXTURE, "espn_12345")
        assert len(rows) == 2

    def test_parse_summary_team_names(self, mock_db):
        """Team names must be extracted from ESPN JSON."""
        from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

        fetcher = CBBBoxScoreFetcher(sport="NCAAB", db=mock_db)
        rows = fetcher._parse_summary(_ESPN_SUMMARY_FIXTURE, "espn_12345")
        team_names = {r["team"] for r in rows}
        assert "Duke Blue Devils" in team_names
        assert "UNC Tar Heels" in team_names

    def test_parse_summary_home_away_flags(self, mock_db):
        """is_home must be set correctly from competitor homeAway field."""
        from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

        fetcher = CBBBoxScoreFetcher(sport="NCAAB", db=mock_db)
        rows = fetcher._parse_summary(_ESPN_SUMMARY_FIXTURE, "espn_12345")
        home_rows = [r for r in rows if r["is_home"]]
        assert len(home_rows) == 1
        assert home_rows[0]["team"] == "Duke Blue Devils"

    def test_parse_summary_won_flag(self, mock_db):
        """Winner must have won=True, loser won=False."""
        from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

        fetcher = CBBBoxScoreFetcher(sport="NCAAB", db=mock_db)
        rows = fetcher._parse_summary(_ESPN_SUMMARY_FIXTURE, "espn_12345")
        by_team = {r["team"]: r for r in rows}
        assert by_team["Duke Blue Devils"]["won"] is True
        assert by_team["UNC Tar Heels"]["won"] is False

    def test_parse_summary_ext_stats(self, mock_db):
        """ext dict must contain fg3m, ast, reb, tov."""
        from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

        fetcher = CBBBoxScoreFetcher(sport="NCAAB", db=mock_db)
        rows = fetcher._parse_summary(_ESPN_SUMMARY_FIXTURE, "espn_12345")
        duke = next(r for r in rows if r["team"] == "Duke Blue Devils")
        assert duke["ext"]["fg3m"] == 8
        assert duke["ext"]["ast"] == 15
        assert duke["ext"]["reb"] == 35

    def test_parse_statistics_fg_percentage(self, mock_db):
        """fg_pct must equal FGM/FGA."""
        from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

        fetcher = CBBBoxScoreFetcher(sport="NCAAB", db=mock_db)
        rows = fetcher._parse_summary(_ESPN_SUMMARY_FIXTURE, "espn_12345")
        duke = next(r for r in rows if r["team"] == "Duke Blue Devils")
        expected_fg_pct = round(30 / 60, 4)
        assert abs(duke["ext"]["fg_pct"] - expected_fg_pct) < 1e-3

    def test_wncaab_ext_table(self, mock_db):
        """WNCAAB fetcher must target wncaab_team_game_stats_ext."""
        from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

        fetcher = CBBBoxScoreFetcher(sport="WNCAAB", db=mock_db)
        assert fetcher.EXT_TABLE == "wncaab_team_game_stats_ext"

    def test_fetch_game_stats_strips_espn_prefix(self, mock_db):
        """fetch_game_stats must handle 'espn_' prefix in game_id."""
        from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

        fetcher = CBBBoxScoreFetcher(sport="NCAAB", db=mock_db)
        with patch.object(
            fetcher, "_fetch_espn_summary", return_value=_ESPN_SUMMARY_FIXTURE
        ) as mock_fetch:
            rows = fetcher.fetch_game_stats("espn_401503425")
        mock_fetch.assert_called_once_with("401503425")
        assert len(rows) == 2


class TestCBBBoxScoreUpsertSkipsMissingGame:
    """upsert_rows must skip rows whose game_id is absent from unified_games."""

    def test_skip_all_when_no_valid_ids(self, mock_db):
        """All rows skipped when unified_games has no matching game_id."""
        from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

        fetcher = CBBBoxScoreFetcher(sport="NCAAB", db=mock_db)
        rows = [
            {
                "game_id": "espn_99999",
                "sport": "NCAAB",
                "team": "Team A",
                "opponent": "Team B",
                "is_home": True,
                "game_date": date(2024, 1, 15),
                "season": "2023-24",
                "points_for": 78,
                "points_against": 65,
                "won": True,
                "off_rating": 110.0,
                "def_rating": 92.0,
                "pace": 68.0,
                "margin": 13,
                "ext": {},
            }
        ]
        count = fetcher.upsert_rows(rows)
        assert count == 0

    def test_upsert_proceeds_with_valid_game_id(self):
        """upsert_rows inserts when game_id is found in unified_games."""
        from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [("espn_401503425",)]
        fetcher = CBBBoxScoreFetcher(sport="NCAAB", db=db)
        rows = [
            {
                "game_id": "espn_401503425",
                "sport": "NCAAB",
                "team": "Duke Blue Devils",
                "opponent": "UNC Tar Heels",
                "is_home": True,
                "game_date": date(2024, 1, 15),
                "season": "2023-24",
                "points_for": 78,
                "points_against": 65,
                "won": True,
                "off_rating": 110.0,
                "def_rating": 92.0,
                "pace": 68.0,
                "margin": 13,
                "ext": {},
            }
        ]
        count = fetcher.upsert_rows(rows)
        assert count == 1


# ===========================================================================
# Tennis Box Score Fetcher
# ===========================================================================


def _make_atp_df() -> pd.DataFrame:
    """Create a minimal Sackmann-style ATP matches DataFrame."""
    return pd.DataFrame(
        [
            {
                "tourney_id": "2023-560",
                "tourney_name": "Australian Open",
                "tourney_date": 20230116,
                "match_num": "R128_0001",
                "winner_name": "Novak Djokovic",
                "loser_name": "Enzo Couacaud",
                "score": "6-1 6-1 6-2",
                "w_ace": 10,
                "w_df": 2,
                "w_svpt": 80,
                "w_1stIn": 55,
                "w_1stWon": 45,
                "w_2ndWon": 18,
                "w_bpSaved": 3,
                "w_bpFaced": 4,
                "l_ace": 1,
                "l_df": 4,
                "l_svpt": 60,
                "l_1stIn": 30,
                "l_1stWon": 15,
                "l_2ndWon": 10,
                "l_bpSaved": 0,
                "l_bpFaced": 8,
            }
        ]
    )


class TestTennisBoxScoreFetcherParsing:
    """Tests for TennisBoxScoreFetcher CSV parsing logic."""

    def test_parse_match_row_returns_two_dicts(self, mock_db):
        """_parse_match_row must return exactly two player dicts."""
        from plugins.stats.tennis_box_score import TennisBoxScoreFetcher

        fetcher = TennisBoxScoreFetcher(tour="atp", db=mock_db)
        df = _make_atp_df()
        rows = fetcher._parse_match_row(df.iloc[0], "atp_2023-560_R128_0001")
        assert len(rows) == 2

    def test_parse_match_row_winner_won_true(self, mock_db):
        """Winner dict must have won=True."""
        from plugins.stats.tennis_box_score import TennisBoxScoreFetcher

        fetcher = TennisBoxScoreFetcher(tour="atp", db=mock_db)
        df = _make_atp_df()
        winner, loser = fetcher._parse_match_row(df.iloc[0], "atp_2023-560_R128_0001")
        assert winner["won"] is True
        assert loser["won"] is False

    def test_parse_match_row_player_names(self, mock_db):
        """Player names must be extracted correctly."""
        from plugins.stats.tennis_box_score import TennisBoxScoreFetcher

        fetcher = TennisBoxScoreFetcher(tour="atp", db=mock_db)
        df = _make_atp_df()
        winner, loser = fetcher._parse_match_row(df.iloc[0], "atp_2023-560_R128_0001")
        assert winner["player_name"] == "Novak Djokovic"
        assert loser["player_name"] == "Enzo Couacaud"

    def test_parse_match_row_aces(self, mock_db):
        """Aces must be parsed from w_ace / l_ace columns."""
        from plugins.stats.tennis_box_score import TennisBoxScoreFetcher

        fetcher = TennisBoxScoreFetcher(tour="atp", db=mock_db)
        df = _make_atp_df()
        winner, loser = fetcher._parse_match_row(df.iloc[0], "atp_2023-560_R128_0001")
        assert winner["aces"] == 10
        assert loser["aces"] == 1

    def test_parse_match_row_first_serve_pct(self, mock_db):
        """first_serve_pct = w_1stIn / w_svpt."""
        from plugins.stats.tennis_box_score import TennisBoxScoreFetcher

        fetcher = TennisBoxScoreFetcher(tour="atp", db=mock_db)
        df = _make_atp_df()
        winner, _ = fetcher._parse_match_row(df.iloc[0], "atp_2023-560_R128_0001")
        expected = round(55 / 80, 4)
        assert abs(winner["first_serve_pct"] - expected) < 1e-3

    def test_parse_score_winner_sets(self, mock_db):
        """Winner must get 3 sets from a 3-0 result '6-1 6-1 6-2'."""
        from plugins.stats.tennis_box_score import _parse_score

        sets_won, games_won = _parse_score("6-1 6-1 6-2", winner=True)
        assert sets_won == 3
        assert games_won == 18  # 6+6+6

    def test_parse_score_loser_games(self, mock_db):
        """Loser must get correct games from '6-1 6-1 6-2'."""
        from plugins.stats.tennis_box_score import _parse_score

        sets_won, games_won = _parse_score("6-1 6-1 6-2", winner=False)
        assert sets_won == 0
        assert games_won == 4  # 1+1+2

    def test_parse_score_five_set_match(self, mock_db):
        """Five-set result parsed correctly for winner."""
        from plugins.stats.tennis_box_score import _parse_score

        sets_won, games_won = _parse_score("6-4 4-6 6-3 3-6 7-5", winner=True)
        assert sets_won == 3

    def test_parse_score_retirement(self, mock_db):
        """RET suffix handled gracefully — partial sets where winner leads are counted."""
        from plugins.stats.tennis_box_score import _parse_score

        # "6-2 3-1 RET": winner completed set 1 (6-2) and leads 3-1 in set 2
        sets_won, games_won = _parse_score("6-2 3-1 RET", winner=True)
        # Both '6-2' and '3-1' have left > right, so sets_won=2 from parser
        assert sets_won == 2
        assert games_won == 9  # 6+3


class TestTennisBoxScoreUpsertSkipsMissingGame:
    """upsert_rows must skip rows absent from unified_games."""

    def test_skip_when_no_valid_ids(self, mock_db):
        """All rows are skipped when no game_id exists in unified_games."""
        from plugins.stats.tennis_box_score import TennisBoxScoreFetcher

        fetcher = TennisBoxScoreFetcher(tour="atp", db=mock_db)
        rows = [
            {
                "game_id": "atp_2023-560_R128_0001",
                "player_name": "Novak Djokovic",
                "aces": 10,
                "double_faults": 2,
                "first_serve_pct": 0.6875,
                "first_serve_won_pct": 0.8182,
                "second_serve_won_pct": 0.72,
                "break_points_saved": 3,
                "break_points_faced": 4,
                "winners": None,
                "unforced_errors": None,
                "sets_won": 3,
                "games_won": 18,
                "won": True,
            }
        ]
        count = fetcher.upsert_rows(rows)
        assert count == 0

    def test_upsert_proceeds_with_valid_game_id(self):
        """upsert_rows inserts when game_id is present in unified_games."""
        from plugins.stats.tennis_box_score import TennisBoxScoreFetcher

        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [("atp_2023-560_R128_0001",)]
        fetcher = TennisBoxScoreFetcher(tour="atp", db=db)
        rows = [
            {
                "game_id": "atp_2023-560_R128_0001",
                "player_name": "Novak Djokovic",
                "aces": 10,
                "double_faults": 2,
                "first_serve_pct": 0.6875,
                "first_serve_won_pct": 0.8182,
                "second_serve_won_pct": 0.72,
                "break_points_saved": 3,
                "break_points_faced": 4,
                "winners": None,
                "unforced_errors": None,
                "sets_won": 3,
                "games_won": 18,
                "won": True,
            }
        ]
        count = fetcher.upsert_rows(rows)
        assert count == 1

    def test_fetch_date_range_with_mocked_csv(self, mock_db, tmp_path):
        """fetch_date_range loads CSV and filters by tourney_date."""
        from plugins.stats.tennis_box_score import TennisBoxScoreFetcher

        # Write a fake CSV to a temp data dir
        tour_dir = tmp_path / "atp"
        tour_dir.mkdir()
        df = _make_atp_df()
        csv_path = tour_dir / "atp_matches_2023.csv"
        df.to_csv(csv_path, index=False)

        fetcher = TennisBoxScoreFetcher(tour="atp", data_dir=tmp_path, db=mock_db)
        rows = fetcher.fetch_date_range(date(2023, 1, 1), date(2023, 3, 31))
        # Should produce 2 rows (winner + loser) for the one match in fixture
        assert len(rows) == 2
        player_names = {r["player_name"] for r in rows}
        assert "Novak Djokovic" in player_names
        assert "Enzo Couacaud" in player_names
