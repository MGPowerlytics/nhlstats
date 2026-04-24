"""
Tests for validate_unified_games_coverage_for_stats().

Uses mocked database queries to verify coverage calculation and status
assignment without requiring a live PostgreSQL connection.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_returning(rows: list[tuple]) -> MagicMock:
    """Build a mock DBManager whose execute().fetchall() returns *rows*.

    Args:
        rows: List of (sport, season, actual_count) tuples.

    Returns:
        Mock DBManager.
    """
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = rows
    return db


# ---------------------------------------------------------------------------
# Coverage calculation tests
# ---------------------------------------------------------------------------


class TestValidateUnifiedGamesCoverage:
    """Tests for validate_unified_games_coverage_for_stats()."""

    def test_full_nba_season_is_ok(self):
        """1230 NBA games in a season → coverage 100% → status 'ok'."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        db = _make_db_returning([("NBA", 2024, 1230)])
        result = validate_unified_games_coverage_for_stats(db=db)

        assert "NBA" in result
        assert 2024 in result["NBA"]
        entry = result["NBA"][2024]
        assert entry["actual"] == 1230
        assert entry["expected"] == 1230
        assert abs(entry["coverage_pct"] - 1.0) < 1e-4
        assert entry["status"] == "ok"

    def test_partial_coverage_is_warn(self):
        """82% coverage (between 70% and 90%) → status 'warn'."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        actual = int(1230 * 0.82)
        db = _make_db_returning([("NBA", 2023, actual)])
        result = validate_unified_games_coverage_for_stats(db=db)

        entry = result["NBA"][2023]
        assert entry["status"] == "warn"
        assert abs(entry["coverage_pct"] - (actual / 1230)) < 0.01

    def test_low_coverage_is_fail(self):
        """50% coverage (below 70%) → status 'fail'."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        actual = int(1230 * 0.50)
        db = _make_db_returning([("NBA", 2022, actual)])
        result = validate_unified_games_coverage_for_stats(db=db)

        entry = result["NBA"][2022]
        assert entry["status"] == "fail"

    def test_exactly_90_pct_is_ok(self):
        """Exactly 90% coverage must return 'ok' (>= threshold)."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        actual = int(1230 * 0.90)
        db = _make_db_returning([("NBA", 2024, actual)])
        result = validate_unified_games_coverage_for_stats(db=db)

        assert result["NBA"][2024]["status"] == "ok"

    def test_multiple_sports_returned(self):
        """Multiple sports must all appear in output."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        db = _make_db_returning(
            [
                ("NBA", 2024, 1200),
                ("NHL", 2024, 1312),
                ("EPL", 2024, 340),
            ]
        )
        result = validate_unified_games_coverage_for_stats(db=db)
        assert "NBA" in result
        assert "NHL" in result
        assert "EPL" in result

    def test_sport_filter_applied(self):
        """When sports=['NBA'], other sports must be excluded."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        db = _make_db_returning(
            [
                ("NBA", 2024, 1200),
                ("NHL", 2024, 1312),
            ]
        )
        result = validate_unified_games_coverage_for_stats(sports=["NBA"], db=db)
        assert "NBA" in result
        assert "NHL" not in result

    def test_season_filter_applied(self):
        """When seasons=[2024], other seasons must be excluded."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        db = _make_db_returning(
            [
                ("NBA", 2023, 1200),
                ("NBA", 2024, 1230),
            ]
        )
        result = validate_unified_games_coverage_for_stats(seasons=[2024], db=db)
        assert 2024 in result["NBA"]
        assert 2023 not in result.get("NBA", {})

    def test_db_error_returns_error_dict(self):
        """DB exception must be caught and returned as {'error': ...}."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        db = MagicMock()
        db.execute.side_effect = Exception("connection refused")
        result = validate_unified_games_coverage_for_stats(db=db)
        assert "error" in result

    def test_empty_db_returns_empty_dict(self):
        """Empty unified_games → empty report (no error)."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        db = _make_db_returning([])
        result = validate_unified_games_coverage_for_stats(db=db)
        assert isinstance(result, dict)
        assert "error" not in result
        assert len(result) == 0

    def test_unknown_sport_gets_full_coverage(self):
        """Sport not in EXPECTED_GAME_COUNTS (expected=0) → coverage 1.0 → 'ok'."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        db = _make_db_returning([("UnknownSport", 2024, 50)])
        result = validate_unified_games_coverage_for_stats(db=db)
        entry = result["UnknownSport"][2024]
        assert entry["coverage_pct"] == 1.0
        assert entry["status"] == "ok"

    def test_nhl_full_season(self):
        """NHL 1312 games → 100% coverage → 'ok'."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        db = _make_db_returning([("NHL", 2024, 1312)])
        result = validate_unified_games_coverage_for_stats(db=db)
        assert result["NHL"][2024]["status"] == "ok"
        assert result["NHL"][2024]["coverage_pct"] == 1.0

    def test_coverage_pct_rounded_to_4dp(self):
        """coverage_pct must be rounded to 4 decimal places."""
        from plugins.data_validation import validate_unified_games_coverage_for_stats

        db = _make_db_returning([("NBA", 2024, 1100)])
        result = validate_unified_games_coverage_for_stats(db=db)
        pct = result["NBA"][2024]["coverage_pct"]
        assert pct == round(1100 / 1230, 4)
