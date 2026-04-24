"""
Tests for NBABoxScoreFetcher and NHLBoxScoreFetcher.

All external API calls (nba_api endpoints, requests.get) and database
operations (DBManager.execute, DBManager.fetch_df) are mocked so no
real network or database connections are required.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Shared test data helpers
# ---------------------------------------------------------------------------


def _make_trad_df() -> pd.DataFrame:
    """Minimal BoxScoreTraditionalV2 team_stats DataFrame."""
    return pd.DataFrame(
        {
            "GAME_ID": ["0022300001", "0022300001"],
            "TEAM_ID": [1610612747, 1610612738],  # LAL (home), BOS (away)
            "TEAM_ABBREVIATION": ["LAL", "BOS"],
            "TEAM_CITY": ["Los Angeles", "Boston"],
            "TEAM_NAME": ["Lakers", "Celtics"],
            "MIN": ["240:00", "240:00"],
            "FGM": [42, 38],
            "FGA": [90, 85],
            "FG_PCT": [0.467, 0.447],
            "FG3M": [12, 10],
            "FG3A": [30, 28],
            "FG3_PCT": [0.400, 0.357],
            "FTM": [16, 14],
            "FTA": [20, 18],
            "FT_PCT": [0.800, 0.778],
            "OREB": [8, 6],
            "DREB": [32, 30],
            "REB": [40, 36],
            "AST": [25, 22],
            "STL": [7, 5],
            "BLK": [4, 3],
            "TO": [12, 14],
            "PF": [18, 20],
            "PTS": [112, 100],
            "PLUS_MINUS": [12, -12],
        }
    )


def _make_summary_df() -> pd.DataFrame:
    """Minimal BoxScoreTraditionalV2 game_summary DataFrame."""
    return pd.DataFrame(
        {
            "GAME_DATE_EST": ["2024-01-20T00:00:00"],
            "GAME_ID": ["0022300001"],
            "HOME_TEAM_ID": [1610612747],  # LAL is home
            "VISITOR_TEAM_ID": [1610612738],
            "SEASON": ["2023"],
            "GAME_STATUS_ID": [3],
            "GAME_STATUS_TEXT": ["Final"],
        }
    )


def _make_adv_df(efg_pct=0.533, ts_pct=0.571) -> pd.DataFrame:
    """Minimal BoxScoreAdvancedV2 team_stats DataFrame."""
    return pd.DataFrame(
        {
            "GAME_ID": ["0022300001", "0022300001"],
            "TEAM_ID": [1610612747, 1610612738],
            "TEAM_ABBREVIATION": ["LAL", "BOS"],
            "OFF_RATING": [112.5, 100.2],
            "DEF_RATING": [100.2, 112.5],
            "PACE": [98.5, 98.5],
            "EFG_PCT": [efg_pct, 0.506],
            "TS_PCT": [ts_pct, 0.538],
            "USG_PCT": [0.200, 0.200],
        }
    )


def _make_adv_df_no_computed() -> pd.DataFrame:
    """Advanced DataFrame with NaN for EFG_PCT / TS_PCT to force local computation."""
    import numpy as np

    df = _make_adv_df()
    df["EFG_PCT"] = float("nan")
    df["TS_PCT"] = float("nan")
    return df


def _nba_mocks(trad_df=None, summary_df=None, adv_df=None):
    """Return a context-manager tuple for patching nba_api endpoints."""
    trad_df = trad_df if trad_df is not None else _make_trad_df()
    summary_df = summary_df if summary_df is not None else _make_summary_df()
    adv_df = adv_df if adv_df is not None else _make_adv_df()

    mock_trad_instance = MagicMock()
    mock_trad_instance.team_stats.get_data_frame.return_value = trad_df
    mock_trad_instance.game_summary.get_data_frame.return_value = summary_df

    mock_adv_instance = MagicMock()
    mock_adv_instance.team_stats.get_data_frame.return_value = adv_df

    return mock_trad_instance, mock_adv_instance


def _nhl_boxscore_json() -> dict:
    """Representative NHL API /v1/gamecenter/{id}/boxscore response."""
    return {
        "id": 2023020001,
        "season": 20232024,
        "gameType": 2,
        "gameDate": "2023-10-11",
        "homeTeam": {
            "id": 6,
            "abbrev": "BOS",
            "score": 4,
            "sog": 31,
            "powerPlayConversion": "1/3",
        },
        "awayTeam": {
            "id": 3,
            "abbrev": "NYR",
            "score": 1,
            "sog": 25,
            "powerPlayConversion": "0/2",
        },
        "teamGameStats": [
            {"category": "sog", "homeValue": "31", "awayValue": "25"},
            {
                "category": "faceoffWinningPctg",
                "homeValue": "56.67",
                "awayValue": "43.33",
            },
            {"category": "powerPlay", "homeValue": "1/3", "awayValue": "0/2"},
            {"category": "pim", "homeValue": "4", "awayValue": "6"},
            {"category": "hits", "homeValue": "23", "awayValue": "18"},
            {"category": "blockedShots", "homeValue": "12", "awayValue": "15"},
            {"category": "giveaways", "homeValue": "3", "awayValue": "5"},
            {"category": "takeaways", "homeValue": "2", "awayValue": "4"},
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_db() -> MagicMock:
    """DBManager mock with fetch_df returning a non-empty DataFrame by default."""
    db = MagicMock()
    # By default the game exists in unified_games
    db.fetch_df.return_value = pd.DataFrame({"1": [1]})
    db.execute.return_value = None
    return db


@pytest.fixture()
def nba_fetcher(mock_db) -> "NBABoxScoreFetcher":
    from plugins.stats.nba_box_score import NBABoxScoreFetcher

    fetcher = NBABoxScoreFetcher(db=mock_db)
    # Disable actual sleeping
    fetcher._rate_limit = MagicMock()
    return fetcher


@pytest.fixture()
def nhl_fetcher(mock_db) -> "NHLBoxScoreFetcher":
    from plugins.stats.nhl_box_score import NHLBoxScoreFetcher

    fetcher = NHLBoxScoreFetcher(db=mock_db)
    # Disable actual sleeping
    fetcher._rate_limit = MagicMock()
    return fetcher


# ===========================================================================
# NBA Tests
# ===========================================================================


class TestNBABoxScoreFetcher:
    def test_nba_parse_boxscore_extracts_both_teams(self, nba_fetcher):
        """fetch_game_stats returns two rows (home + away) with correct teams."""
        mock_trad, mock_adv = _nba_mocks()

        with (
            patch(
                "plugins.stats.nba_box_score.boxscoretraditionalv2.BoxScoreTraditionalV2",
                return_value=mock_trad,
            ),
            patch(
                "plugins.stats.nba_box_score.boxscoreadvancedv2.BoxScoreAdvancedV2",
                return_value=mock_adv,
            ),
        ):
            rows = nba_fetcher.fetch_game_stats("0022300001")

        assert len(rows) == 2

        teams = {r["team"] for r in rows}
        assert teams == {"LAL", "BOS"}

        home = next(r for r in rows if r["team"] == "LAL")
        away = next(r for r in rows if r["team"] == "BOS")

        assert home["is_home"] is True
        assert away["is_home"] is False
        assert home["opponent"] == "BOS"
        assert away["opponent"] == "LAL"
        assert home["points_for"] == 112
        assert away["points_for"] == 100
        assert home["won"] is True
        assert away["won"] is False
        assert home["game_date"] == "2024-01-20"
        assert home["season"] == "2023"
        assert home["sport"] == "NBA"

    def test_nba_computes_efg_and_ts(self, nba_fetcher):
        """When advanced stats are NaN, eFG% and TS% are computed locally."""
        mock_trad, mock_adv = _nba_mocks(adv_df=_make_adv_df_no_computed())

        with (
            patch(
                "plugins.stats.nba_box_score.boxscoretraditionalv2.BoxScoreTraditionalV2",
                return_value=mock_trad,
            ),
            patch(
                "plugins.stats.nba_box_score.boxscoreadvancedv2.BoxScoreAdvancedV2",
                return_value=mock_adv,
            ),
        ):
            rows = nba_fetcher.fetch_game_stats("0022300001")

        lal = next(r for r in rows if r["team"] == "LAL")
        ext = lal["ext"]

        # eFG% = (FGM + 0.5 * FG3M) / FGA = (42 + 6) / 90 = 48/90 ≈ 0.5333
        expected_efg = (42 + 0.5 * 12) / 90
        assert abs(ext["efg_pct"] - round(expected_efg, 4)) < 1e-4

        # TS% = PTS / (2 * (FGA + 0.44 * FTA)) = 112 / (2 * (90 + 8.8)) = 112/197.6
        expected_ts = 112 / (2 * (90 + 0.44 * 20))
        assert abs(ext["ts_pct"] - round(expected_ts, 4)) < 1e-4

    def test_nba_upsert_uses_on_conflict(self, nba_fetcher, mock_db):
        """upsert_rows executes INSERT … ON CONFLICT SQL for both tables."""
        mock_trad, mock_adv = _nba_mocks()

        with (
            patch(
                "plugins.stats.nba_box_score.boxscoretraditionalv2.BoxScoreTraditionalV2",
                return_value=mock_trad,
            ),
            patch(
                "plugins.stats.nba_box_score.boxscoreadvancedv2.BoxScoreAdvancedV2",
                return_value=mock_adv,
            ),
        ):
            rows = nba_fetcher.fetch_game_stats("0022300001")

        count = nba_fetcher.upsert_rows(rows)

        assert count == 2  # two teams upserted

        sql_calls = [str(c) for c in mock_db.execute.call_args_list]
        assert any(
            "ON CONFLICT" in s for s in sql_calls
        ), "Expected ON CONFLICT in SQL calls, got: " + str(sql_calls)
        # Both team_game_stats and nba_team_game_stats_ext should be written
        assert any("team_game_stats" in s for s in sql_calls)
        assert any("nba_team_game_stats_ext" in s for s in sql_calls)

    def test_nba_skips_game_not_in_unified_games(self, nba_fetcher, mock_db, caplog):
        """upsert_rows skips rows whose game_id is absent from unified_games."""
        # Simulate game not found
        mock_db.fetch_df.return_value = pd.DataFrame()

        mock_trad, mock_adv = _nba_mocks()

        with (
            patch(
                "plugins.stats.nba_box_score.boxscoretraditionalv2.BoxScoreTraditionalV2",
                return_value=mock_trad,
            ),
            patch(
                "plugins.stats.nba_box_score.boxscoreadvancedv2.BoxScoreAdvancedV2",
                return_value=mock_adv,
            ),
        ):
            rows = nba_fetcher.fetch_game_stats("0022300001")

        with caplog.at_level(logging.WARNING, logger="plugins.stats.nba_box_score"):
            count = nba_fetcher.upsert_rows(rows)

        assert count == 0
        assert mock_db.execute.call_count == 0
        assert any("not found in unified_games" in msg for msg in caplog.messages)


# ===========================================================================
# NHL Tests
# ===========================================================================


class TestNHLBoxScoreFetcher:
    def test_nhl_parse_boxscore_extracts_corsi_proxy(self, nhl_fetcher):
        """fetch_game_stats computes correct partial Corsi proxy in ext.shots."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = _nhl_boxscore_json()

        with patch("plugins.stats.nhl_box_score.requests.get", return_value=mock_resp):
            rows = nhl_fetcher.fetch_game_stats("2023020001")

        assert len(rows) == 2
        bos = next(r for r in rows if r["team"] == "BOS")
        nyr = next(r for r in rows if r["team"] == "NYR")

        # BOS home: shots = BOS_sog + NYR_blockedShots = 31 + 15 = 46
        assert bos["ext"]["shots"] == 31 + 15
        assert bos["ext"]["sog"] == 31
        assert bos["ext"]["blocks"] == 12  # BOS's defensive blocks

        # NYR away: shots = NYR_sog + BOS_blockedShots = 25 + 12 = 37
        assert nyr["ext"]["shots"] == 25 + 12
        assert nyr["ext"]["sog"] == 25

        # Basic game fields
        assert bos["is_home"] is True
        assert nyr["is_home"] is False
        assert bos["points_for"] == 4
        assert nyr["points_for"] == 1
        assert bos["won"] is True
        assert nyr["won"] is False
        assert bos["season"] == "2023"

        # Power-play fields
        assert bos["ext"]["pp_goals"] == 1
        assert bos["ext"]["pp_opportunities"] == 3
        assert abs(bos["ext"]["pp_pct"] - round(1 / 3, 4)) < 1e-4

        # PK mirrors opponent's PP
        assert bos["ext"]["pk_goals_against"] == 0
        assert nyr["ext"]["pk_goals_against"] == 1

    def test_nhl_rate_limit_called(self, nhl_fetcher):
        """_rate_limit is invoked before each API request in fetch_game_stats."""
        # Replace _rate_limit with a real mock so we can count calls
        rate_limit_mock = MagicMock()
        nhl_fetcher._rate_limit = rate_limit_mock

        mock_resp = MagicMock()
        mock_resp.json.return_value = _nhl_boxscore_json()

        with patch("plugins.stats.nhl_box_score.requests.get", return_value=mock_resp):
            nhl_fetcher.fetch_game_stats("2023020001")

        rate_limit_mock.assert_called()
        assert rate_limit_mock.call_count >= 1

    def test_nhl_skips_game_not_in_unified_games(self, nhl_fetcher, mock_db, caplog):
        """upsert_rows skips rows whose game_id is absent from unified_games."""
        mock_db.fetch_df.return_value = pd.DataFrame()

        mock_resp = MagicMock()
        mock_resp.json.return_value = _nhl_boxscore_json()

        with patch("plugins.stats.nhl_box_score.requests.get", return_value=mock_resp):
            rows = nhl_fetcher.fetch_game_stats("2023020001")

        with caplog.at_level(logging.WARNING, logger="plugins.stats.nhl_box_score"):
            count = nhl_fetcher.upsert_rows(rows)

        assert count == 0
        assert mock_db.execute.call_count == 0
        assert any("not found in unified_games" in msg for msg in caplog.messages)

    def test_nhl_upsert_uses_on_conflict(self, nhl_fetcher, mock_db):
        """upsert_rows executes INSERT … ON CONFLICT for both tables."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = _nhl_boxscore_json()

        with patch("plugins.stats.nhl_box_score.requests.get", return_value=mock_resp):
            rows = nhl_fetcher.fetch_game_stats("2023020001")

        count = nhl_fetcher.upsert_rows(rows)

        assert count == 2

        sql_calls = [str(c) for c in mock_db.execute.call_args_list]
        assert any("ON CONFLICT" in s for s in sql_calls)
        assert any("team_game_stats" in s for s in sql_calls)
        assert any("nhl_team_game_stats_ext" in s for s in sql_calls)

    def test_nhl_faceoff_pct_normalised(self, nhl_fetcher):
        """faceoff_pct is stored as a decimal (0–1), not percentage (0–100)."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = _nhl_boxscore_json()

        with patch("plugins.stats.nhl_box_score.requests.get", return_value=mock_resp):
            rows = nhl_fetcher.fetch_game_stats("2023020001")

        bos = next(r for r in rows if r["team"] == "BOS")
        # 56.67% → 0.5667
        assert bos["ext"]["faceoff_pct"] <= 1.0
        assert abs(bos["ext"]["faceoff_pct"] - 0.5667) < 0.001
