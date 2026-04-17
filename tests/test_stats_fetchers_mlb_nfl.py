"""
Unit tests for MLB and NFL box-score fetchers.

Tests are fully offline — all external I/O (HTTP requests, nfl_data_py
imports) is mocked.  DBManager is replaced with a lightweight MagicMock so no
PostgreSQL connection is required.

Test matrix
-----------
MLB
  test_mlb_parse_boxscore_extracts_both_teams   — two dicts with correct keys
  test_mlb_woba_derived                         — woba present and > 0
  test_mlb_skips_game_not_in_unified_games      — returns [] + logs warning

NFL
  test_nfl_aggregates_pbp_to_team_game          — two dicts with passing_yards
  test_nfl_epa_computed                         — epa_offense_mean in ext
  test_nfl_skips_game_not_in_unified_games      — returns [] + logs warning
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Ensure plugins/ is importable in direct test runs
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


# ---------------------------------------------------------------------------
# Helpers — fake API responses
# ---------------------------------------------------------------------------

_MLB_GAME_ID = "745431"

_FAKE_LIVE_FEED: dict[str, Any] = {
    "gameData": {
        "datetime": {"officialDate": "2024-05-10"},
        "status": {"detailedState": "Final"},
        "teams": {
            "home": {"abbreviation": "NYY", "name": "New York Yankees"},
            "away": {"abbreviation": "BOS", "name": "Boston Red Sox"},
        },
    },
    "liveData": {
        "linescore": {
            "teams": {
                "home": {"runs": 5},
                "away": {"runs": 3},
            }
        },
        "boxscore": {},
    },
}

_FAKE_BOXSCORE: dict[str, Any] = {
    "teams": {
        "home": {
            "team": {"abbreviation": "NYY"},
            "teamStats": {
                "batting": {
                    "runs": 5,
                    "hits": 10,
                    "doubles": 2,
                    "triples": 0,
                    "homeRuns": 2,
                    "baseOnBalls": 3,
                    "hitByPitch": 1,
                    "sacFlies": 0,
                    "atBats": 33,
                    "strikeOuts": 8,
                    "leftOnBase": 7,
                    "rbi": 5,
                    "stolenBases": 1,
                    "avg": ".303",
                    "obp": "0.352",
                    "slg": "0.545",
                },
                "pitching": {
                    "strikeOuts": 10,
                    "baseOnBalls": 3,
                    "homeRuns": 1,
                    "earnedRuns": 2,
                    "hits": 8,
                    "inningsPitched": "9.0",
                },
                "fielding": {"errors": 1},
            },
        },
        "away": {
            "team": {"abbreviation": "BOS"},
            "teamStats": {
                "batting": {
                    "runs": 3,
                    "hits": 7,
                    "doubles": 1,
                    "triples": 0,
                    "homeRuns": 1,
                    "baseOnBalls": 2,
                    "hitByPitch": 0,
                    "sacFlies": 1,
                    "atBats": 30,
                    "strikeOuts": 10,
                    "leftOnBase": 6,
                    "rbi": 3,
                    "stolenBases": 0,
                    "avg": ".233",
                    "obp": "0.300",
                    "slg": "0.367",
                },
                "pitching": {
                    "strikeOuts": 8,
                    "baseOnBalls": 3,
                    "homeRuns": 2,
                    "earnedRuns": 5,
                    "hits": 10,
                    "inningsPitched": "8.1",
                },
                "fielding": {"errors": 0},
            },
        },
    }
}


def _make_mlb_mock_db(game_in_unified: bool = True) -> MagicMock:
    """Return a MagicMock DBManager.

    Args:
        game_in_unified: Whether to simulate the game existing in unified_games.

    Returns:
        MagicMock that returns a row (or None) on execute().fetchone().
    """
    db = MagicMock()
    result = MagicMock()
    result.fetchone.return_value = (1,) if game_in_unified else None
    db.execute.return_value = result
    return db


def _make_requests_mock(live_data: dict, boxscore_data: dict) -> MagicMock:
    """Return a MagicMock for ``requests.get`` that serves fake API responses.

    First call returns the live-feed payload, second call returns the boxscore
    payload (matching the order in ``MLBBoxScoreFetcher.fetch_game_stats``).

    Args:
        live_data: Payload for the live-feed endpoint.
        boxscore_data: Payload for the boxscore endpoint.

    Returns:
        MagicMock callable.
    """
    live_resp = MagicMock()
    live_resp.json.return_value = live_data
    live_resp.raise_for_status.return_value = None

    bs_resp = MagicMock()
    bs_resp.json.return_value = boxscore_data
    bs_resp.raise_for_status.return_value = None

    mock = MagicMock(side_effect=[live_resp, bs_resp])
    return mock


# ---------------------------------------------------------------------------
# MLB tests
# ---------------------------------------------------------------------------


class TestMLBBoxScoreFetcher:
    """Tests for MLBBoxScoreFetcher."""

    def _make_fetcher(self, game_in_unified: bool = True):
        """Construct a fetcher with a mocked DBManager."""
        from plugins.stats.mlb_box_score import MLBBoxScoreFetcher

        db = _make_mlb_mock_db(game_in_unified=game_in_unified)
        return MLBBoxScoreFetcher(db=db)

    def test_mlb_parse_boxscore_extracts_both_teams(self):
        """fetch_game_stats returns exactly two dicts with required core keys."""
        fetcher = self._make_fetcher()
        with patch(
            "requests.get", _make_requests_mock(_FAKE_LIVE_FEED, _FAKE_BOXSCORE)
        ):
            rows = fetcher.fetch_game_stats(_MLB_GAME_ID)

        assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"

        teams = {r["team"] for r in rows}
        assert "NYY" in teams
        assert "BOS" in teams

        required_core = {
            "game_id",
            "sport",
            "team",
            "opponent",
            "is_home",
            "game_date",
            "season",
            "points_for",
            "points_against",
            "won",
            "margin",
        }
        required_ext = {
            "hits",
            "errors",
            "lob",
            "doubles",
            "triples",
            "home_runs",
            "rbi",
            "stolen_bases",
            "strikeouts",
            "walks",
            "at_bats",
            "obp",
            "slg",
            "ops",
            "woba",
            "era",
        }

        for row in rows:
            assert required_core.issubset(
                row.keys()
            ), f"Missing core keys: {required_core - row.keys()}"
            assert "ext" in row
            assert required_ext.issubset(
                row["ext"].keys()
            ), f"Missing ext keys: {required_ext - row['ext'].keys()}"

        home_row = next(r for r in rows if r["team"] == "NYY")
        assert home_row["is_home"] is True
        assert home_row["points_for"] == 5
        assert home_row["points_against"] == 3
        assert home_row["won"] is True
        assert home_row["margin"] == 2
        assert home_row["game_date"] == date(2024, 5, 10)
        assert home_row["season"] == "2024"

        away_row = next(r for r in rows if r["team"] == "BOS")
        assert away_row["is_home"] is False
        assert away_row["points_for"] == 3
        assert away_row["won"] is False

    def test_mlb_woba_derived(self):
        """woba in the ext dict is derived and non-negative."""
        fetcher = self._make_fetcher()
        with patch(
            "requests.get", _make_requests_mock(_FAKE_LIVE_FEED, _FAKE_BOXSCORE)
        ):
            rows = fetcher.fetch_game_stats(_MLB_GAME_ID)

        assert len(rows) == 2
        for row in rows:
            woba = row["ext"]["woba"]
            assert isinstance(woba, float), f"woba should be float, got {type(woba)}"
            assert woba >= 0.0, f"woba should be non-negative, got {woba}"

        # Winning team NYY had hits=10, HR=2, 2B=2, BB=3, HBP=1, AB=33, SF=0
        # singles = 10 - 2 - 0 - 2 = 6
        # numerator = 0.69*3 + 0.722*1 + 0.880*6 + 1.249*2 + 2.031*2
        # denominator = 33 + 3 + 0 + 1 = 37
        home_row = next(r for r in rows if r["team"] == "NYY")
        assert home_row["ext"]["woba"] > 0.0

    def test_mlb_era_computed(self):
        """era = earned_runs / innings_pitched * 9."""
        fetcher = self._make_fetcher()
        with patch(
            "requests.get", _make_requests_mock(_FAKE_LIVE_FEED, _FAKE_BOXSCORE)
        ):
            rows = fetcher.fetch_game_stats(_MLB_GAME_ID)

        home_row = next(r for r in rows if r["team"] == "NYY")
        # ip=9.0, er=2 → ERA = 2.0
        assert abs(home_row["ext"]["era"] - 2.0) < 0.01

    def test_mlb_skips_game_not_in_unified_games(self, caplog):
        """fetch_game_stats returns [] and logs a warning for unknown game_id."""
        import logging

        fetcher = self._make_fetcher(game_in_unified=False)

        with caplog.at_level(logging.WARNING, logger="plugins.stats.mlb_box_score"):
            with patch("requests.get") as mock_get:
                rows = fetcher.fetch_game_stats("999999")

        assert rows == [], f"Expected empty list, got {rows}"
        # requests.get should not have been called
        mock_get.assert_not_called()
        assert any("not in unified_games" in m for m in caplog.messages)

    def test_mlb_upsert_rows_calls_db(self):
        """upsert_rows calls db.execute twice per row (core + ext)."""
        from plugins.stats.mlb_box_score import MLBBoxScoreFetcher

        db = _make_mlb_mock_db()
        fetcher = MLBBoxScoreFetcher(db=db)

        fake_row = {
            "game_id": "745431",
            "sport": "MLB",
            "team": "NYY",
            "opponent": "BOS",
            "is_home": True,
            "game_date": date(2024, 5, 10),
            "season": "2024",
            "points_for": 5,
            "points_against": 3,
            "won": True,
            "margin": 2,
            "ext": {
                "hits": 10,
                "errors": 1,
                "lob": 7,
                "doubles": 2,
                "triples": 0,
                "home_runs": 2,
                "rbi": 5,
                "stolen_bases": 1,
                "strikeouts": 8,
                "walks": 3,
                "at_bats": 33,
                "obp": 0.352,
                "slg": 0.545,
                "ops": 0.897,
                "woba": 0.360,
                "era": 2.0,
            },
        }

        count = fetcher.upsert_rows([fake_row])
        assert count == 1
        # Should have been called at least twice: core upsert + ext upsert
        assert db.execute.call_count >= 2

    def test_mlb_upsert_empty_rows_returns_zero(self):
        """upsert_rows([]) returns 0 without calling the DB."""
        from plugins.stats.mlb_box_score import MLBBoxScoreFetcher

        db = _make_mlb_mock_db()
        fetcher = MLBBoxScoreFetcher(db=db)
        assert fetcher.upsert_rows([]) == 0


# ---------------------------------------------------------------------------
# NFL helpers
# ---------------------------------------------------------------------------

_NFL_GAME_ID = "2023_01_KC_DET"

_FAKE_SCHEDULE_DF = pd.DataFrame(
    [
        {
            "game_id": _NFL_GAME_ID,
            "gameday": "2023-09-07",
            "home_team": "DET",
            "away_team": "KC",
            "home_score": 21,
            "away_score": 20,
            "season": 2023,
            "week": 1,
        }
    ]
)

_FAKE_PBP_DF = pd.DataFrame(
    [
        # Play 1: KC pass play, 15 yards gain, EPA +0.8, success
        {
            "game_id": _NFL_GAME_ID,
            "posteam": "KC",
            "defteam": "DET",
            "play_type": "pass",
            "pass": 1,
            "rush": 0,
            "passing_yards": 15,
            "rushing_yards": 0,
            "yards_gained": 15,
            "epa": 0.8,
            "touchdown": 0,
            "interception": 0,
            "fumble_lost": 0,
            "third_down_converted": 0,
            "third_down_failed": 0,
            "first_down_rush": 0,
            "first_down_pass": 1,
            "first_down_penalty": 0,
            "penalty": 0,
            "penalty_team": None,
            "penalty_yards": 0,
            "sack": 0,
            "down": 1,
        },
        # Play 2: KC rush play, 5 yards, EPA -0.2
        {
            "game_id": _NFL_GAME_ID,
            "posteam": "KC",
            "defteam": "DET",
            "play_type": "run",
            "pass": 0,
            "rush": 1,
            "passing_yards": 0,
            "rushing_yards": 5,
            "yards_gained": 5,
            "epa": -0.2,
            "touchdown": 0,
            "interception": 0,
            "fumble_lost": 0,
            "third_down_converted": 1,
            "third_down_failed": 0,
            "first_down_rush": 1,
            "first_down_pass": 0,
            "first_down_penalty": 0,
            "penalty": 0,
            "penalty_team": None,
            "penalty_yards": 0,
            "sack": 0,
            "down": 3,
        },
        # Play 3: DET pass, 8 yards, EPA +0.3
        {
            "game_id": _NFL_GAME_ID,
            "posteam": "DET",
            "defteam": "KC",
            "play_type": "pass",
            "pass": 1,
            "rush": 0,
            "passing_yards": 8,
            "rushing_yards": 0,
            "yards_gained": 8,
            "epa": 0.3,
            "touchdown": 1,
            "interception": 0,
            "fumble_lost": 0,
            "third_down_converted": 0,
            "third_down_failed": 0,
            "first_down_rush": 0,
            "first_down_pass": 1,
            "first_down_penalty": 0,
            "penalty": 0,
            "penalty_team": None,
            "penalty_yards": 0,
            "sack": 0,
            "down": 1,
        },
        # Play 4: KC penalty
        {
            "game_id": _NFL_GAME_ID,
            "posteam": "KC",
            "defteam": "DET",
            "play_type": "no_play",
            "pass": 0,
            "rush": 0,
            "passing_yards": 0,
            "rushing_yards": 0,
            "yards_gained": 0,
            "epa": 0.0,
            "touchdown": 0,
            "interception": 0,
            "fumble_lost": 0,
            "third_down_converted": 0,
            "third_down_failed": 0,
            "first_down_rush": 0,
            "first_down_pass": 0,
            "first_down_penalty": 0,
            "penalty": 1,
            "penalty_team": "KC",
            "penalty_yards": 10,
            "sack": 0,
            "down": 2,
        },
    ]
)


def _make_nfl_mock_db(game_in_unified: bool = True) -> MagicMock:
    """Return a MagicMock DBManager for NFL tests.

    Args:
        game_in_unified: Whether to simulate the game in unified_games.

    Returns:
        MagicMock with execute().fetchone() configured.
    """
    db = MagicMock()
    result = MagicMock()
    result.fetchone.return_value = (1,) if game_in_unified else None
    db.execute.return_value = result
    return db


# ---------------------------------------------------------------------------
# NFL tests
# ---------------------------------------------------------------------------


class TestNFLBoxScoreFetcher:
    """Tests for NFLBoxScoreFetcher."""

    def setup_method(self):
        """Clear module-level schedule/pbp caches before each test."""
        from plugins.stats import nfl_box_score

        nfl_box_score._clear_caches()

    def _make_fetcher(self, game_in_unified: bool = True):
        from plugins.stats.nfl_box_score import NFLBoxScoreFetcher

        db = _make_nfl_mock_db(game_in_unified=game_in_unified)
        return NFLBoxScoreFetcher(db=db)

    def test_nfl_aggregates_pbp_to_team_game(self):
        """fetch_game_stats returns two dicts with aggregated passing/rushing yards."""
        fetcher = self._make_fetcher()

        with patch("plugins.stats.nfl_box_score.nfl") as mock_nfl, patch(
            "plugins.stats.nfl_box_score._NFL_DATA_AVAILABLE", True
        ):
            mock_nfl.import_schedules.return_value = _FAKE_SCHEDULE_DF.copy()
            mock_nfl.import_pbp_data.return_value = _FAKE_PBP_DF.copy()

            rows = fetcher.fetch_game_stats(_NFL_GAME_ID)

        assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"

        teams = {r["team"] for r in rows}
        assert "KC" in teams
        assert "DET" in teams

        required_core = {
            "game_id",
            "sport",
            "team",
            "opponent",
            "is_home",
            "game_date",
            "season",
            "points_for",
            "points_against",
            "won",
            "margin",
        }
        required_ext = {
            "passing_yards",
            "rushing_yards",
            "turnovers",
            "third_down_pct",
            "epa_offense_mean",
            "success_rate",
        }

        for row in rows:
            assert required_core.issubset(
                row.keys()
            ), f"Missing core keys: {required_core - row.keys()}"
            assert "ext" in row
            assert required_ext.issubset(
                row["ext"].keys()
            ), f"Missing ext keys: {required_ext - row['ext'].keys()}"

        home_row = next(r for r in rows if r["team"] == "DET")
        assert home_row["is_home"] is True
        assert home_row["points_for"] == 21
        assert home_row["points_against"] == 20
        assert home_row["won"] is True
        assert home_row["margin"] == 1
        assert home_row["game_date"] == date(2023, 9, 7)
        assert home_row["season"] == "2023"

        # KC had play 1 (pass, 15 yds) and play 2 (rush, 5 yds)
        kc_row = next(r for r in rows if r["team"] == "KC")
        assert kc_row["ext"]["passing_yards"] == 15
        assert kc_row["ext"]["rushing_yards"] == 5

        # DET had play 3 (pass, 8 yds)
        det_row = next(r for r in rows if r["team"] == "DET")
        assert det_row["ext"]["passing_yards"] == 8

    def test_nfl_epa_computed(self):
        """ext dict includes epa_offense_mean derived from PBP."""
        fetcher = self._make_fetcher()

        with patch("plugins.stats.nfl_box_score.nfl") as mock_nfl, patch(
            "plugins.stats.nfl_box_score._NFL_DATA_AVAILABLE", True
        ):
            mock_nfl.import_schedules.return_value = _FAKE_SCHEDULE_DF.copy()
            mock_nfl.import_pbp_data.return_value = _FAKE_PBP_DF.copy()

            rows = fetcher.fetch_game_stats(_NFL_GAME_ID)

        assert len(rows) == 2

        for row in rows:
            ext = row["ext"]
            assert "epa_offense_mean" in ext
            assert isinstance(ext["epa_offense_mean"], float)
            assert "success_rate" in ext
            # success_rate must be in [0, 1]
            assert 0.0 <= ext["success_rate"] <= 1.0

        # KC plays 1, 2, and 4 (penalty, posteam=KC) have epa 0.8, -0.2, 0.0 → mean = 0.2
        kc_row = next(r for r in rows if r["team"] == "KC")
        assert abs(kc_row["ext"]["epa_offense_mean"] - 0.2) < 0.01

    def test_nfl_skips_game_not_in_unified_games(self, caplog):
        """fetch_game_stats returns [] and logs warning for unknown game_id."""
        import logging

        fetcher = self._make_fetcher(game_in_unified=False)

        with caplog.at_level(logging.WARNING, logger="plugins.stats.nfl_box_score"):
            with patch("plugins.stats.nfl_box_score._NFL_DATA_AVAILABLE", True):
                with patch("plugins.stats.nfl_box_score.nfl") as mock_nfl:
                    rows = fetcher.fetch_game_stats("2023_01_BAD_BAD")

        assert rows == [], f"Expected empty list, got {rows}"
        mock_nfl.import_schedules.assert_not_called()
        assert any("not in unified_games" in m for m in caplog.messages)

    def test_nfl_upsert_rows_calls_db(self):
        """upsert_rows calls db.execute at least twice per row."""
        from plugins.stats.nfl_box_score import NFLBoxScoreFetcher

        db = _make_nfl_mock_db()
        fetcher = NFLBoxScoreFetcher(db=db)

        fake_row = {
            "game_id": _NFL_GAME_ID,
            "sport": "NFL",
            "team": "KC",
            "opponent": "DET",
            "is_home": False,
            "game_date": date(2023, 9, 7),
            "season": "2023",
            "points_for": 20,
            "points_against": 21,
            "won": False,
            "margin": -1,
            "ext": {
                "passing_yards": 300,
                "passing_tds": 2,
                "passing_ints": 1,
                "rushing_yards": 80,
                "rushing_tds": 0,
                "rushing_attempts": 20,
                "total_yards": 380,
                "turnovers": 1,
                "third_down_conversions": 5,
                "third_down_attempts": 12,
                "third_down_pct": 0.4167,
                "time_of_possession": None,
                "penalties": 4,
                "penalty_yards": 35,
                "sacks_allowed": 2,
                "first_downs": 18,
                "epa_offense_mean": 0.12,
                "epa_defense_mean": -0.12,
                "success_rate": 0.47,
            },
        }

        count = fetcher.upsert_rows([fake_row])
        assert count == 1
        assert db.execute.call_count >= 2

    def test_nfl_upsert_empty_rows_returns_zero(self):
        """upsert_rows([]) returns 0."""
        from plugins.stats.nfl_box_score import NFLBoxScoreFetcher

        db = _make_nfl_mock_db()
        fetcher = NFLBoxScoreFetcher(db=db)
        assert fetcher.upsert_rows([]) == 0

    def test_nfl_season_parsing(self):
        """_season_from_game_id correctly extracts the year."""
        from plugins.stats.nfl_box_score import _season_from_game_id

        assert _season_from_game_id("2023_01_DET_KC") == 2023
        assert _season_from_game_id("2024_18_NYG_PHI") == 2024
