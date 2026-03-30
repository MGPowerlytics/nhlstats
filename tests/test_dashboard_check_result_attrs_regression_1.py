"""Regression test for ISSUE-001 — CheckResult attributes accessed as dict keys.

The dashboard's _display_data_quality_summary and _display_detailed_validation_reports
were calling check.get("severity") / check["name"] etc., treating CheckResult (a
dataclass) as a dict. This caused AttributeError on the Data Quality page.

Regression: ISSUE-001 — CheckResult attrs accessed as dict keys
Found by /qa on 2026-03-30
Report: .gstack/qa-reports/qa-report-localhost-8501-2026-03-30.md
"""

import sys
import os
from unittest.mock import MagicMock, patch
import pytest

# ---------------------------------------------------------------------------
# Mock streamlit before importing dashboard_app
# ---------------------------------------------------------------------------
st = MagicMock()


def _cache_decorator(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return lambda f: f


st.cache_data = _cache_decorator
sys.modules["streamlit"] = st

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "../dashboard"))

import dashboard.dashboard_app as dashboard_app
from plugins.data_validation import CheckResult


class TestCheckResultAttributeAccess:
    """Verify dashboard functions access CheckResult fields as attributes, not dict keys."""

    def _make_check(
        self, name: str, passed: bool, message: str, severity: str = "info"
    ) -> CheckResult:
        return CheckResult(name=name, passed=passed, message=message, severity=severity)

    def test_check_result_has_no_get_method(self) -> None:
        """CheckResult is a dataclass, not a dict — .get() must not exist."""
        check = self._make_check("Test", True, "All good", "info")
        assert not hasattr(check, "get"), (
            "CheckResult should not have a .get() method; "
            "code calling check.get() will raise AttributeError"
        )

    def test_check_result_attributes_accessible(self) -> None:
        """All four CheckResult fields are accessible as attributes."""
        check = self._make_check("Row count", False, "Only 10 rows", "error")
        assert check.name == "Row count"
        assert check.passed is False
        assert check.message == "Only 10 rows"
        assert check.severity == "error"

    def test_check_result_default_severity(self) -> None:
        """Severity defaults to 'info' when not specified."""
        check = self._make_check("Elo file", True, "File exists")
        assert check.severity == "info"

    def test_display_data_quality_summary_accepts_check_results(self) -> None:
        """_display_data_quality_summary must not raise AttributeError on CheckResult objects.

        Previously, the function called check.get("severity") which fails on a dataclass.
        After the fix it uses check.severity directly.

        The function takes Dict[str, report] where each report has .checks (List[CheckResult])
        and .stats (Dict).
        """
        checks = [
            self._make_check("Row count", True, "14000 rows", "info"),
            self._make_check("Missing dates", False, "3 gaps found", "warning"),
            self._make_check("Null values", False, "Critical nulls", "error"),
        ]

        # Build a minimal mock report object matching the ValidationReport interface
        mock_report = MagicMock()
        mock_report.checks = checks
        mock_report.stats = {"rows": 14000, "sports": 3}

        all_reports = {"nhl": mock_report}

        # The function renders via streamlit — all st.* calls are mocked.
        # We only care that no AttributeError / TypeError is raised.
        try:
            dashboard_app._display_data_quality_summary(all_reports)
        except AttributeError as exc:
            pytest.fail(
                f"_display_data_quality_summary raised AttributeError: {exc}\n"
                "Likely calling .get() or dict-style access on a CheckResult dataclass."
            )

    def test_severity_variants_handled(self) -> None:
        """All expected severity values are valid string attributes."""
        for severity in ("info", "warning", "error", "critical"):
            check = self._make_check("Test", True, "msg", severity)
            # Attribute access must not raise
            assert check.severity == severity
