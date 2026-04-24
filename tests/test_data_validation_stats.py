"""Tests for wave-3 team_game_stats validation in plugins/data_validation.py.

All DB interactions are mocked so no live PostgreSQL connection is required.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.data_validation import (
    _season_date_range,
    validate_all_sports_stats,
    validate_team_game_stats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(query_map: dict) -> MagicMock:
    """Build a mock DBManager whose execute() returns canned results.

    Args:
        query_map: Mapping of substring → list of rows (each row a tuple).
            The first substring that appears in the query is used.
    """
    db = MagicMock()

    def _execute(sql: str, params=None):
        for key, rows in query_map.items():
            if key in sql:
                result = MagicMock()
                result.fetchone.return_value = rows[0] if rows else None
                result.fetchall.return_value = rows
                return result
        # Default: return a single-row (0,)
        result = MagicMock()
        result.fetchone.return_value = (0,)
        result.fetchall.return_value = [(0,)]
        return result

    db.execute.side_effect = _execute
    return db


# ---------------------------------------------------------------------------
# 1. Season boundary logic – Soccer
# ---------------------------------------------------------------------------


class TestSeasonBoundary:
    """Verify _season_date_range returns correct date windows."""

    def test_epl_season_format(self):
        start, end = _season_date_range("EPL", "2023-2024")
        assert start == "2023-08-01"
        assert end == "2024-05-31"

    def test_ligue1_season_format(self):
        start, end = _season_date_range("Ligue1", "2022-2023")
        assert start == "2022-08-01"
        assert end == "2023-05-31"

    def test_tennis_calendar_year(self):
        start, end = _season_date_range("Tennis", "2024")
        assert start == "2024-01-01"
        assert end == "2024-12-31"

    def test_nba_season_oct_to_jun(self):
        start, end = _season_date_range("NBA", "2023-2024")
        assert start == "2023-10-01"
        assert end == "2024-06-30"

    def test_mlb_season_year_only(self):
        start, end = _season_date_range("MLB", "2024")
        assert start == "2024-03-01"
        assert end == "2024-10-31"

    def test_nfl_season_crosses_year(self):
        start, end = _season_date_range("NFL", "2023")
        assert start == "2023-09-01"
        assert end == "2024-02-28"

    def test_nhl_season_format(self):
        start, end = _season_date_range("NHL", "2023-2024")
        assert start == "2023-10-01"
        assert end == "2024-06-30"

    def test_invalid_soccer_season_raises(self):
        with pytest.raises(ValueError, match="YYYY-YYYY"):
            _season_date_range("EPL", "2024")

    def test_unknown_sport_raises(self):
        with pytest.raises(ValueError, match="Unknown sport"):
            _season_date_range("RUGBY", "2024")


# ---------------------------------------------------------------------------
# 2. Empty data returns warning/fail
# ---------------------------------------------------------------------------


class TestEmptyData:
    """When no rows exist, row_count check fails and coverage fails."""

    def test_zero_rows_row_count_fails(self):
        db = _make_db(
            {
                "COUNT(*) FROM team_game_stats": [(0,)],
                "COUNT(DISTINCT ts.game_id)": [(0, 100)],
                "LEFT JOIN unified_games": [(0,)],
            }
        )
        report = validate_team_game_stats("NBA", db=db)
        row_check = next(c for c in report.checks if c.name == "row_count")
        assert not row_check.passed

    def test_zero_coverage_produces_error(self):
        """0/100 games covered → below 80% → severity error."""
        db = _make_db(
            {
                "COUNT(*) FROM team_game_stats": [(0,)],
                "COUNT(DISTINCT": [(0, 100)],
                "WHERE ug.game_id IS NULL": [(0,)],
            }
        )
        # patch date_filter away and check coverage directly
        db2 = MagicMock()
        call_count = [0]

        def _execute(sql, params=None):
            call_count[0] += 1
            result = MagicMock()
            if "COUNT(*) FROM team_game_stats" in sql and "game_id" not in sql:
                result.fetchone.return_value = (0,)
            elif "COUNT(DISTINCT" in sql:
                result.fetchone.return_value = (0, 100)
            else:
                result.fetchone.return_value = (0,)
            return result

        db2.execute.side_effect = _execute
        report = validate_team_game_stats("NBA", db=db2)
        cov_check = next(c for c in report.checks if c.name == "stats_coverage")
        assert not cov_check.passed
        assert cov_check.severity == "error"

    def test_empty_report_has_warnings_or_errors(self):
        """Empty DB → at least one warning or error in the report."""
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = (0,)
        db.execute.return_value.fetchall.return_value = []
        report = validate_team_game_stats("NHL", db=db)
        has_issue = bool(report.warnings) or bool(report.errors)
        assert has_issue


# ---------------------------------------------------------------------------
# 3. Full coverage (≥ 95%) returns ok
# ---------------------------------------------------------------------------


class TestFullCoverage:
    """When stats cover ≥ 95% of unified_games, coverage check passes."""

    def _build_full_db(self, sport: str = "NBA") -> MagicMock:
        db = MagicMock()

        def _execute(sql, params=None):
            result = MagicMock()
            if "COUNT(*) FROM team_game_stats" in sql and "IS NULL" not in sql:
                result.fetchone.return_value = (200,)
            elif "COUNT(DISTINCT" in sql:
                # 200 stats games out of 200 total → 100%
                result.fetchone.return_value = (200, 200)
            elif "IS NULL" in sql:
                result.fetchone.return_value = (0,)
            else:
                result.fetchone.return_value = (0,)
            return result

        db.execute.side_effect = _execute
        return db

    def test_full_coverage_check_passes(self):
        report = validate_team_game_stats("NBA", db=self._build_full_db())
        cov_check = next(c for c in report.checks if c.name == "stats_coverage")
        assert cov_check.passed

    def test_full_coverage_no_errors(self):
        report = validate_team_game_stats("NBA", db=self._build_full_db())
        assert not report.errors

    def test_coverage_pct_stored_in_stats(self):
        report = validate_team_game_stats("NBA", db=self._build_full_db())
        assert report.stats.get("coverage_pct", 0) >= 0.95


# ---------------------------------------------------------------------------
# 4. FK violation caught
# ---------------------------------------------------------------------------


class TestFKViolation:
    """Orphan rows (stats without unified_games) must fail fk_integrity check."""

    def _build_fk_db(self, orphans: int = 5) -> MagicMock:
        db = MagicMock()

        def _execute(sql, params=None):
            result = MagicMock()
            if "COUNT(*) FROM team_game_stats" in sql and "IS NULL" not in sql:
                result.fetchone.return_value = (100,)
            elif "COUNT(DISTINCT" in sql:
                result.fetchone.return_value = (95, 100)
            elif "IS NULL" in sql:
                # FK check – return orphan count
                result.fetchone.return_value = (orphans,)
            else:
                result.fetchone.return_value = (0,)
            return result

        db.execute.side_effect = _execute
        return db

    def test_orphan_rows_fail_fk_check(self):
        report = validate_team_game_stats("NHL", db=self._build_fk_db(orphans=3))
        fk_check = next(c for c in report.checks if c.name == "fk_integrity")
        assert not fk_check.passed
        assert fk_check.severity == "error"

    def test_orphan_count_stored(self):
        report = validate_team_game_stats("NHL", db=self._build_fk_db(orphans=7))
        assert report.stats.get("orphan_rows") == 7

    def test_no_orphans_passes(self):
        report = validate_team_game_stats("NHL", db=self._build_fk_db(orphans=0))
        fk_check = next(c for c in report.checks if c.name == "fk_integrity")
        assert fk_check.passed


# ---------------------------------------------------------------------------
# 5. Non-null violation caught
# ---------------------------------------------------------------------------


class TestNonNullViolation:
    """NULL values in key metrics should produce a failed check."""

    def _build_null_db(self, null_count: int = 10) -> MagicMock:
        db = MagicMock()

        def _execute(sql, params=None):
            result = MagicMock()
            if (
                "COUNT(*) FROM team_game_stats" in sql
                and "IS NULL" not in sql
                and "game_id IS NULL" not in sql
            ):
                result.fetchone.return_value = (100,)
            elif "COUNT(DISTINCT" in sql:
                result.fetchone.return_value = (100, 100)
            elif "game_id IS NULL" in sql:
                # FK check
                result.fetchone.return_value = (0,)
            elif "IS NULL" in sql:
                # Non-null field check
                result.fetchone.return_value = (null_count,)
            else:
                result.fetchone.return_value = (0,)
            return result

        db.execute.side_effect = _execute
        return db

    def test_null_efg_pct_fails(self):
        report = validate_team_game_stats("NBA", db=self._build_null_db(null_count=5))
        null_check = next(
            (c for c in report.checks if c.name == "non_null_efg_pct"), None
        )
        assert null_check is not None, "non_null_efg_pct check not found"
        assert not null_check.passed

    def test_null_message_contains_count(self):
        report = validate_team_game_stats("NBA", db=self._build_null_db(null_count=5))
        null_check = next(c for c in report.checks if c.name == "non_null_efg_pct")
        assert "5" in null_check.message

    def test_zero_nulls_passes(self):
        report = validate_team_game_stats("NBA", db=self._build_null_db(null_count=0))
        null_check = next(c for c in report.checks if c.name == "non_null_efg_pct")
        assert null_check.passed

    def test_nhl_checks_corsi_fields(self):
        report = validate_team_game_stats("NHL", db=self._build_null_db(null_count=2))
        check_names = {c.name for c in report.checks}
        assert "non_null_corsi_for" in check_names
        assert "non_null_corsi_against" in check_names

    def test_tennis_checks_aces(self):
        report = validate_team_game_stats(
            "Tennis", db=self._build_null_db(null_count=1)
        )
        check_names = {c.name for c in report.checks}
        assert "non_null_aces" in check_names


# ---------------------------------------------------------------------------
# 6. Season boundary integration
# ---------------------------------------------------------------------------


class TestSeasonBoundaryIntegration:
    """validate_team_game_stats passes season params to SQL correctly."""

    def test_season_dates_stored_in_stats(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = (100,)
        report = validate_team_game_stats("EPL", season="2023-2024", db=db)
        assert report.stats.get("season_start") == "2023-08-01"
        assert report.stats.get("season_end") == "2024-05-31"

    def test_invalid_season_returns_error_check(self):
        db = MagicMock()
        report = validate_team_game_stats("EPL", season="2024", db=db)
        err_check = next(
            (c for c in report.checks if c.name == "season_boundary"), None
        )
        assert err_check is not None
        assert not err_check.passed
        # DB should not have been queried
        db.execute.assert_not_called()

    def test_soccer_season_date_filter_applied(self):
        """Verify start_date/end_date params are passed to execute calls."""
        captured_params: list = []
        db = MagicMock()

        def _execute(sql, params=None):
            captured_params.append(params or {})
            result = MagicMock()
            result.fetchone.return_value = (50,)
            return result

        db.execute.side_effect = _execute
        validate_team_game_stats("EPL", season="2022-2023", db=db)
        # At least one call should carry start_date / end_date
        params_with_dates = [p for p in captured_params if "start_date" in p]
        assert params_with_dates, "No DB call included start_date param"
        assert params_with_dates[0]["start_date"] == "2022-08-01"


# ---------------------------------------------------------------------------
# 7. validate_all_sports_stats convenience
# ---------------------------------------------------------------------------


class TestValidateAllSportsStats:
    """validate_all_sports_stats returns a report per sport."""

    def test_returns_dict_of_reports(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = (0,)
        db.execute.return_value.fetchall.return_value = []
        result = validate_all_sports_stats(db=db)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_all_sports_present(self):
        from plugins.data_validation import _ALL_STATS_SPORTS

        db = MagicMock()
        db.execute.return_value.fetchone.return_value = (0,)
        result = validate_all_sports_stats(db=db)
        for sport in _ALL_STATS_SPORTS:
            assert sport in result, f"{sport} missing from validate_all_sports_stats"

    def test_each_value_is_report(self):
        from plugins.data_validation import DataValidationReport

        db = MagicMock()
        db.execute.return_value.fetchone.return_value = (0,)
        result = validate_all_sports_stats(db=db)
        for sport, rpt in result.items():
            assert isinstance(
                rpt, DataValidationReport
            ), f"{sport} did not return DataValidationReport"


# ---------------------------------------------------------------------------
# 8. Warning band (80–95%)
# ---------------------------------------------------------------------------


class TestWarningBand:
    """Coverage between 80-95% should produce a warning, not an error."""

    def _build_warn_db(
        self, stats_games: int = 87, total_games: int = 100
    ) -> MagicMock:
        db = MagicMock()

        def _execute(sql, params=None):
            result = MagicMock()
            if (
                "COUNT(*) FROM team_game_stats" in sql
                and "IS NULL" not in sql
                and "game_id IS NULL" not in sql
            ):
                result.fetchone.return_value = (stats_games,)
            elif "COUNT(DISTINCT" in sql:
                result.fetchone.return_value = (stats_games, total_games)
            elif "IS NULL" in sql:
                result.fetchone.return_value = (0,)
            else:
                result.fetchone.return_value = (0,)
            return result

        db.execute.side_effect = _execute
        return db

    def test_87pct_coverage_is_warning_not_error(self):
        report = validate_team_game_stats("MLB", db=self._build_warn_db())
        cov_check = next(c for c in report.checks if c.name == "stats_coverage")
        assert not cov_check.passed
        assert cov_check.severity == "warning"
