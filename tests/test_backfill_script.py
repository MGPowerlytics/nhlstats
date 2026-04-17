"""Unit tests for scripts/backfill_team_game_stats.py.

Tests cover:
    (a) argparse help exits 0 and lists all required flags.
    (b) dry-run mode: DBManager.execute / fetch_df are never called.
    (c) Progress file: load_progress / save_progress round-trip.
    (d) build_fetcher: correct class instantiated per sport.
    (e) fetch_with_backoff: retries on retryable errors, gives up after MAX_RETRIES.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Ensure repo root is on sys.path so we can import the script module.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# We import the script as a module; its top-level imports are guarded so we
# patch out the DB before the module tries to connect.
with patch("plugins.db_manager.DBManager"):
    import scripts.backfill_team_game_stats as bfill

# Re-import helpers directly for clarity.
from scripts.backfill_team_game_stats import (  # noqa: E402
    PROGRESS_FILE,
    SUPPORTED_SPORTS,
    SportSummary,
    build_fetcher,
    fetch_with_backoff,
    load_progress,
    main,
    save_progress,
)


# ===========================================================================
# (a) Argparse: --help exits 0 and lists all expected flags
# ===========================================================================


class TestArgparseHelp:
    """Verify that --help works correctly and documents all required flags."""

    def test_help_exit_zero(self):
        """--help must exit with code 0."""
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "backfill_team_game_stats.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        assert (
            result.returncode == 0
        ), f"--help exited {result.returncode}: {result.stderr}"

    def test_help_contains_sport_flag(self):
        """--help output must mention --sport."""
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "backfill_team_game_stats.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        assert "--sport" in result.stdout

    def test_help_contains_all_required_flags(self):
        """--help must list all six required flags."""
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "backfill_team_game_stats.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        output = result.stdout
        for flag in [
            "--sport",
            "--start",
            "--end",
            "--dry-run",
            "--resume",
            "--verbose",
        ]:
            assert flag in output, f"Flag {flag!r} not found in --help output"

    def test_help_lists_supported_sports(self):
        """--help must enumerate each supported sport."""
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "backfill_team_game_stats.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        for sport in SUPPORTED_SPORTS:
            assert sport in result.stdout, f"Sport {sport!r} not found in --help output"


# ===========================================================================
# (b) Dry-run mode: nothing written to DB
# ===========================================================================


class TestDryRun:
    """Verify that --dry-run writes nothing to the database."""

    def _make_mock_db(self, game_rows: list[dict]) -> MagicMock:
        """Return a mock DBManager that returns *game_rows* from fetch_df."""
        mock_db = MagicMock()
        mock_db.fetch_df.return_value = pd.DataFrame(game_rows)
        return mock_db

    def test_dry_run_does_not_call_execute(self, tmp_path):
        """In dry-run mode, db.execute (upsert path) must never be called."""
        mock_db = self._make_mock_db(
            [{"game_id": "NBA_TEST_001", "game_date": date(2024, 1, 1)}]
        )
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_game_stats.return_value = [
            {"game_id": "NBA_TEST_001", "team_id": "LAL", "is_home": True}
        ]
        mock_fetcher.upsert_rows.return_value = 1
        mock_fetcher.RATE_LIMIT_SECONDS = 0.0
        mock_fetcher._last_request_ts = 0.0
        mock_fetcher._rate_limit = MagicMock()

        with patch.object(
            bfill, "build_fetcher", return_value=mock_fetcher
        ), patch.object(bfill, "DBManager", return_value=mock_db):
            main(
                sport="nba",
                start=date(2024, 1, 1),
                end=date(2024, 1, 1),
                dry_run=True,
                resume=False,
            )

        # fetch_df is called to enumerate games (read-only), but execute/upsert_rows must NOT be called.
        mock_fetcher.fetch_game_stats.assert_not_called()
        mock_fetcher.upsert_rows.assert_not_called()
        mock_db.execute.assert_not_called()

    def test_dry_run_does_not_write_progress_file(self, tmp_path):
        """Dry-run must not create or update the progress file."""
        mock_db = self._make_mock_db(
            [{"game_id": "NHL_TEST_001", "game_date": date(2024, 1, 1)}]
        )
        progress_path = tmp_path / "progress.json"

        with patch.object(
            bfill, "build_fetcher", return_value=MagicMock()
        ), patch.object(bfill, "DBManager", return_value=mock_db), patch.object(
            bfill, "PROGRESS_FILE", progress_path
        ), patch.object(
            bfill, "save_progress"
        ) as mock_save:
            main(
                sport="nhl",
                start=date(2024, 1, 1),
                end=date(2024, 1, 1),
                dry_run=True,
                resume=False,
            )

        mock_save.assert_not_called()

    def test_dry_run_prints_games(self, capsys):
        """Dry-run should print a line per game with [DRY-RUN] prefix."""
        mock_db = MagicMock()
        mock_db.fetch_df.return_value = pd.DataFrame(
            [
                {"game_id": "NBA_DRY_001", "game_date": date(2024, 1, 1)},
                {"game_id": "NBA_DRY_002", "game_date": date(2024, 1, 1)},
            ]
        )

        with patch.object(
            bfill, "build_fetcher", return_value=MagicMock()
        ), patch.object(bfill, "DBManager", return_value=mock_db), patch.object(
            bfill, "save_progress"
        ):
            main(
                sport="nba",
                start=date(2024, 1, 1),
                end=date(2024, 1, 1),
                dry_run=True,
                resume=False,
            )

        captured = capsys.readouterr()
        assert "[DRY-RUN]" in captured.out
        assert "NBA_DRY_001" in captured.out
        assert "NBA_DRY_002" in captured.out


# ===========================================================================
# (c) Resume file: load_progress / save_progress round-trip
# ===========================================================================


class TestProgressFile:
    """Verify progress file read/write behaviour."""

    def test_save_and_load_round_trip(self, tmp_path):
        """Progress saved via save_progress must be identical when loaded."""
        path = tmp_path / "progress.json"
        original = {"nba": "2024-01-15", "nhl": "2024-01-10"}
        save_progress(path, original)
        loaded = load_progress(path)
        assert loaded == original

    def test_load_missing_file_returns_empty_dict(self, tmp_path):
        """load_progress on a non-existent file must return {}."""
        path = tmp_path / "does_not_exist.json"
        result = load_progress(path)
        assert result == {}

    def test_load_corrupt_file_returns_empty_dict(self, tmp_path):
        """load_progress on malformed JSON must return {} (no crash)."""
        path = tmp_path / "corrupt.json"
        path.write_text("NOT VALID JSON {{{}}", encoding="utf-8")
        result = load_progress(path)
        assert result == {}

    def test_save_creates_parent_directory(self, tmp_path):
        """save_progress must create intermediate directories."""
        path = tmp_path / "nested" / "dir" / "progress.json"
        save_progress(path, {"nba": "2024-01-01"})
        assert path.exists()
        assert json.loads(path.read_text())["nba"] == "2024-01-01"

    def test_resume_advances_start_date(self, tmp_path):
        """With --resume and a progress file, start date must advance past last completed date."""
        mock_db = MagicMock()
        # Return empty DataFrame — simulates no games in the advanced window
        mock_db.fetch_df.return_value = pd.DataFrame(columns=["game_id", "game_date"])

        progress = {"nba": "2024-01-05"}
        progress_path = tmp_path / "progress.json"
        save_progress(progress_path, progress)

        with patch.object(
            bfill, "build_fetcher", return_value=MagicMock()
        ), patch.object(bfill, "DBManager", return_value=mock_db), patch.object(
            bfill, "PROGRESS_FILE", progress_path
        ):
            main(
                sport="nba",
                start=date(2024, 1, 1),  # before last completed
                end=date(2024, 1, 10),
                dry_run=False,
                resume=True,
            )

        # fetch_df must have been called with start=2024-01-06 (day after last completed)
        call_kwargs = mock_db.fetch_df.call_args
        params = call_kwargs[1]["params"] if call_kwargs[1] else call_kwargs[0][1]
        assert (
            params["start"] == "2024-01-06"
        ), f"Expected start=2024-01-06 after resume, got {params['start']}"


# ===========================================================================
# (d) build_fetcher: returns correct class per sport
# ===========================================================================


class TestBuildFetcher:
    """Verify build_fetcher maps sport keys to correct fetcher classes."""

    @pytest.mark.parametrize(
        "sport_key, expected_class_name",
        [
            ("nba", "NBABoxScoreFetcher"),
            ("nhl", "NHLBoxScoreFetcher"),
            ("mlb", "MLBBoxScoreFetcher"),
            ("nfl", "NFLBoxScoreFetcher"),
            ("epl", "SoccerBoxScoreFetcher"),
            ("ligue1", "SoccerBoxScoreFetcher"),
            ("ncaab", "CBBBoxScoreFetcher"),
            ("wncaab", "CBBBoxScoreFetcher"),
            ("tennis", "TennisBoxScoreFetcher"),
        ],
    )
    def test_correct_class_instantiated(self, sport_key: str, expected_class_name: str):
        """build_fetcher must return the expected fetcher class for each sport."""
        mock_db = MagicMock()
        fetcher = build_fetcher(sport_key, mock_db)
        assert (
            type(fetcher).__name__ == expected_class_name
        ), f"Sport {sport_key!r}: expected {expected_class_name}, got {type(fetcher).__name__}"

    def test_soccer_epl_sport_attribute(self):
        """SoccerBoxScoreFetcher for 'epl' must have SPORT='EPL'."""
        fetcher = build_fetcher("epl", MagicMock())
        assert fetcher.SPORT == "EPL"

    def test_soccer_ligue1_sport_attribute(self):
        """SoccerBoxScoreFetcher for 'ligue1' must have SPORT='Ligue1'."""
        fetcher = build_fetcher("ligue1", MagicMock())
        assert fetcher.SPORT == "Ligue1"

    def test_cbb_ncaab_sport_attribute(self):
        """CBBBoxScoreFetcher for 'ncaab' must have SPORT='NCAAB'."""
        fetcher = build_fetcher("ncaab", MagicMock())
        assert fetcher.SPORT == "NCAAB"

    def test_cbb_wncaab_sport_attribute(self):
        """CBBBoxScoreFetcher for 'wncaab' must have SPORT='WNCAAB'."""
        fetcher = build_fetcher("wncaab", MagicMock())
        assert fetcher.SPORT == "WNCAAB"

    def test_unknown_sport_raises(self):
        """build_fetcher must raise ValueError for an unrecognised sport."""
        with pytest.raises(ValueError, match="Unknown sport"):
            build_fetcher("cricket", MagicMock())


# ===========================================================================
# (e) fetch_with_backoff: retry and give-up behaviour
# ===========================================================================


class TestFetchWithBackoff:
    """Verify exponential backoff and retry logic."""

    def test_success_on_first_try(self):
        """Successful fetch must return rows without sleeping."""
        fetcher = MagicMock()
        fetcher._rate_limit = MagicMock()
        fetcher._last_request_ts = 0.0
        expected_rows = [{"game_id": "G1", "team_id": "LAL"}]
        fetcher.fetch_game_stats.return_value = expected_rows

        with patch("time.sleep") as mock_sleep:
            result = fetch_with_backoff(fetcher, "G1")

        assert result == expected_rows
        mock_sleep.assert_not_called()

    def test_retries_on_429(self):
        """fetch_with_backoff must retry on 429-like errors and succeed."""
        fetcher = MagicMock()
        fetcher._rate_limit = MagicMock()
        fetcher._last_request_ts = 0.0
        expected_rows = [{"game_id": "G2"}]
        fetcher.fetch_game_stats.side_effect = [
            Exception("HTTP 429 Too Many Requests"),
            expected_rows,
        ]

        with patch("time.sleep"):
            result = fetch_with_backoff(fetcher, "G2")

        assert result == expected_rows
        assert fetcher.fetch_game_stats.call_count == 2

    def test_returns_none_after_max_retries(self):
        """fetch_with_backoff must return None when all retries are exhausted."""
        fetcher = MagicMock()
        fetcher._rate_limit = MagicMock()
        fetcher._last_request_ts = 0.0
        fetcher.fetch_game_stats.side_effect = Exception("503 Service Unavailable")

        with patch("time.sleep"):
            result = fetch_with_backoff(fetcher, "G3")

        assert result is None
        assert fetcher.fetch_game_stats.call_count == bfill._MAX_RETRIES + 1

    def test_non_retryable_error_fails_immediately(self):
        """Non-retryable errors must not trigger retries."""
        fetcher = MagicMock()
        fetcher._rate_limit = MagicMock()
        fetcher._last_request_ts = 0.0
        fetcher.fetch_game_stats.side_effect = ValueError("invalid game_id format")

        with patch("time.sleep") as mock_sleep:
            result = fetch_with_backoff(fetcher, "BAD_ID")

        assert result is None
        assert fetcher.fetch_game_stats.call_count == 1  # no retries
        mock_sleep.assert_not_called()
