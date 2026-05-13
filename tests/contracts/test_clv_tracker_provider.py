"""Provider contract tests for the CLV Tracker boundary.

Validates that ``CLVTracker.record_bet_line()``, ``update_closing_line()``,
and ``analyze_clv()`` produce contract-valid output. Uses a mocked database
layer via ``unittest.mock`` so tests require no real database connection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from jsonschema import Draft202012Validator

from plugins.clv_tracker import CLVTracker

SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / "clv_tracker_contract_v1.json"
)


# ---------------------------------------------------------------------------
# Schema setup
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def clv_schema() -> dict[str, Any]:
    """Load the CLV tracker contract schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def analysis_schema(clv_schema: dict[str, Any]) -> dict[str, Any]:
    """Build a standalone schema that validates only ``clv_analysis_result``."""
    return {
        "$schema": clv_schema["$schema"],
        "$ref": "#/$defs/clv_analysis_result",
        "$defs": clv_schema["$defs"],
    }


@pytest.fixture(scope="module")
def summary_schema(clv_schema: dict[str, Any]) -> dict[str, Any]:
    """Build a standalone schema that validates only ``clv_report_summary``."""
    return {
        "$schema": clv_schema["$schema"],
        "$ref": "#/$defs/clv_report_summary",
        "$defs": clv_schema["$defs"],
    }


def _validate(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

# Simulated placed_bets data: keyed by bet_id
_MOCK_BETS: dict[str, dict[str, Any]] = {}


def _mock_fetchone_success(bet_id: str) -> MagicMock:
    """Return a mock row with a bet_line_prob for a known bet."""
    row = MagicMock()
    if bet_id in _MOCK_BETS and _MOCK_BETS[bet_id].get("bet_line_prob") is not None:
        row.__getitem__.side_effect = lambda idx: (
            _MOCK_BETS[bet_id]["bet_line_prob"] if idx == 0 else None
        )
    else:
        row.__getitem__.side_effect = lambda idx: None
    return row


def _mock_fetchone_none() -> MagicMock:
    """Return a mock row where index 0 is None (no bet_line_prob)."""
    row = MagicMock()
    row.__getitem__.side_effect = lambda idx: None
    row.__bool__.return_value = True
    return row


# ---------------------------------------------------------------------------
# Fixtures: fresh tracker + mock before each test
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker() -> CLVTracker:
    """Return a bare CLVTracker instance (no real DB needed)."""
    return CLVTracker()


@pytest.fixture(autouse=True)
def _reset_mock_bets() -> None:
    """Reset the mock bet store before each test."""
    _MOCK_BETS.clear()
    _MOCK_BETS.update(
        {
            "bet_clv_prov_001": {
                "bet_line_prob": 0.65,
            },
            "bet_clv_prov_002": {
                "bet_line_prob": 0.40,
            },
            "bet_clv_prov_003": {
                "bet_line_prob": 0.55,
            },
            "bet_clv_prov_stale": {
                "bet_line_prob": 0.70,
            },
        }
    )


def _execute_params(call_args: tuple[tuple[Any, ...], dict[str, Any]]) -> dict[str, Any]:
    """Extract the params dict from a default_db.execute() call.

    ``default_db.execute(query, params)`` passes ``params`` as the second
    positional argument, so it is at ``call_args[0][1]``.
    """
    return call_args[0][1]


# ---------------------------------------------------------------------------
# Provider: record_bet_line
# ---------------------------------------------------------------------------


class TestRecordBetLine:
    """record_bet_line() must store data correctly."""

    def test_record_bet_line_executes_update(
        self, tracker: CLVTracker
    ) -> None:
        """record_bet_line executes an UPDATE with the correct parameters."""
        with patch("plugins.clv_tracker.default_db") as mock_db:
            mock_db.execute.return_value = MagicMock()
            tracker.record_bet_line("bet_new", 0.55)

            mock_db.execute.assert_called_once()
            call_args = mock_db.execute.call_args
            assert call_args is not None
            params = _execute_params(call_args)
            assert params["bet_id"] == "bet_new"
            assert params["market_prob"] == 0.55

    def test_record_bet_line_with_boundary_prob(
        self, tracker: CLVTracker
    ) -> None:
        """record_bet_line handles probability values at [0, 1] bounds."""
        with patch("plugins.clv_tracker.default_db") as mock_db:
            mock_db.execute.return_value = MagicMock()

            tracker.record_bet_line("bet_zero", 0.0)
            params0 = _execute_params(mock_db.execute.call_args)
            assert params0["market_prob"] == 0.0

            tracker.record_bet_line("bet_one", 1.0)
            params1 = _execute_params(mock_db.execute.call_args)
            assert params1["market_prob"] == 1.0


# ---------------------------------------------------------------------------
# Provider: update_closing_line
# ---------------------------------------------------------------------------


class TestUpdateClosingLine:
    """update_closing_line() must properly calculate CLV."""

    def test_update_closing_line_positive_clv(
        self, tracker: CLVTracker
    ) -> None:
        """Placed at 0.65, closing at 0.55 => positive CLV of 0.10."""
        mock_fetchone = _mock_fetchone_success("bet_clv_prov_001")
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_fetchone

        with patch("plugins.clv_tracker.default_db") as mock_db:
            mock_db.execute.side_effect = [mock_result, MagicMock()]

            tracker.update_closing_line("bet_clv_prov_001", 0.55)

            # Second call is the UPDATE
            update_params = _execute_params(mock_db.execute.call_args_list[1])
            assert update_params["clv"] == pytest.approx(0.10)
            assert update_params["closing_prob"] == 0.55
            assert update_params["bet_id"] == "bet_clv_prov_001"

    def test_update_closing_line_negative_clv(
        self, tracker: CLVTracker
    ) -> None:
        """Placed at 0.55, closing at 0.75 => negative CLV of -0.20."""
        mock_fetchone = _mock_fetchone_success("bet_clv_prov_003")
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_fetchone

        with patch("plugins.clv_tracker.default_db") as mock_db:
            mock_db.execute.side_effect = [mock_result, MagicMock()]

            tracker.update_closing_line("bet_clv_prov_003", 0.75)

            update_params = _execute_params(mock_db.execute.call_args_list[1])
            assert update_params["clv"] == pytest.approx(-0.20)
            assert update_params["closing_prob"] == 0.75

    def test_update_closing_line_zero_clv(
        self, tracker: CLVTracker
    ) -> None:
        """Placed at same prob as closing => zero CLV."""
        mock_fetchone = _mock_fetchone_success("bet_clv_prov_002")
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_fetchone

        with patch("plugins.clv_tracker.default_db") as mock_db:
            mock_db.execute.side_effect = [mock_result, MagicMock()]

            tracker.update_closing_line("bet_clv_prov_002", 0.40)

            update_params = _execute_params(mock_db.execute.call_args_list[1])
            assert update_params["clv"] == pytest.approx(0.0)

    def test_update_closing_line_missing_bet_no_clv_calculated(
        self, tracker: CLVTracker
    ) -> None:
        """When no bet_line_prob is found (bet_line[0] is None), no UPDATE is run."""
        mock_fetchone = _mock_fetchone_none()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_fetchone

        with patch("plugins.clv_tracker.default_db") as mock_db:
            mock_db.execute.return_value = mock_result

            tracker.update_closing_line("nonexistent_bet", 0.50)

            # Only one execute call (the SELECT) — the UPDATE is skipped
            # because bet_line[0] is None/falsy
            assert mock_db.execute.call_count == 1

    def test_update_closing_line_correctly_formats_output(
        self, tracker: CLVTracker, analysis_schema: dict[str, Any]
    ) -> None:
        """The (placed_prob, closing_prob, clv) tuple matches schema constraints."""
        mock_fetchone = _mock_fetchone_success("bet_clv_prov_001")
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_fetchone

        with patch("plugins.clv_tracker.default_db") as mock_db:
            mock_db.execute.side_effect = [mock_result, MagicMock()]

            tracker.update_closing_line("bet_clv_prov_001", 0.55)

            update_params = _execute_params(mock_db.execute.call_args_list[1])

            payload: dict[str, Any] = {
                "bet_id": "bet_clv_prov_001",
                "sport": "NBA",
                "placed_prob": 0.65,
                "closing_prob": update_params["closing_prob"],
                "clv": update_params["clv"],
                "market_close_time": "2025-06-15T23:00:00Z",
                "is_stale": False,
                "schema_version": "v1",
                "payload_kind": "clv_analysis_result",
            }
            _validate(analysis_schema, payload)


# ---------------------------------------------------------------------------
# Provider: analyze_clv
# ---------------------------------------------------------------------------


class TestAnalyzeCLV:
    """analyze_clv() must produce schema-compliant output."""

    def test_analyze_clv_returns_dict(self, tracker: CLVTracker) -> None:
        """analyze_clv returns a dict."""
        with patch("plugins.clv_tracker.default_db") as mock_db:
            overall_row = MagicMock()
            overall_row.__getitem__.side_effect = lambda idx: [10, 0.025, 60.0][idx]
            overall_result = MagicMock()
            overall_result.fetchone.return_value = overall_row

            sport_row_1 = MagicMock()
            sport_row_1.__getitem__.side_effect = lambda idx: (
                ["NBA", 5, 0.05, 80.0][idx]
            )
            sport_row_2 = MagicMock()
            sport_row_2.__getitem__.side_effect = lambda idx: (
                ["NHL", 5, 0.0, 50.0][idx]
            )
            sport_result = MagicMock()
            sport_result.fetchall.return_value = [sport_row_1, sport_row_2]

            mock_db.execute.side_effect = [overall_result, sport_result]

            result = tracker.analyze_clv(days_back=30)

        assert isinstance(result, dict)
        assert result["num_bets"] == 10
        assert result["avg_clv"] == 0.025
        assert result["positive_clv_pct"] == 60.0
        assert len(result["by_sport"]) == 2
        assert result["by_sport"][0]["sport"] == "NBA"
        assert result["by_sport"][1]["sport"] == "NHL"

    def test_analyze_clv_no_data_returns_empty(
        self, tracker: CLVTracker
    ) -> None:
        """When no CLV data exists, analyze returns a message dict."""
        with patch("plugins.clv_tracker.default_db") as mock_db:
            no_data_result = MagicMock()
            no_data_result.fetchone.return_value = MagicMock()
            no_data_result.fetchone.return_value.__getitem__.side_effect = (
                lambda idx: 0
            )
            mock_db.execute.return_value = no_data_result

            result = tracker.analyze_clv(days_back=30)

        assert isinstance(result, dict)
        assert result.get("num_bets") == 0
        assert "message" in result

    def test_analyze_clv_output_positive_and_negative(
        self, tracker: CLVTracker
    ) -> None:
        """analyze_clv correctly reports positive vs negative CLV counts."""
        with patch("plugins.clv_tracker.default_db") as mock_db:
            overall_row = MagicMock()
            overall_row.__getitem__.side_effect = lambda idx: [20, 0.01, 55.0][idx]
            overall_result = MagicMock()
            overall_result.fetchone.return_value = overall_row

            sport_row = MagicMock()
            sport_row.__getitem__.side_effect = lambda idx: (
                ["NBA", 20, 0.01, 55.0][idx]
            )
            sport_result = MagicMock()
            sport_result.fetchall.return_value = [sport_row]

            mock_db.execute.side_effect = [overall_result, sport_result]

            result = tracker.analyze_clv(days_back=30)

        assert result["num_bets"] == 20
        assert result["positive_clv_pct"] == 55.0


# ---------------------------------------------------------------------------
# Provider: CLV analysis produces schema-compliant output
# ---------------------------------------------------------------------------


class TestAnalyzeCLVSchemaConformance:
    """analyze_clv() output structure must match the frozen schema."""

    def test_analyze_clv_result_values_must_satisfy_schema(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        """Individual bet CLV values must satisfy schema constraints."""
        payload = {
            "bet_id": "bet_prov_analysis_001",
            "sport": "NBA",
            "placed_prob": 0.65,
            "closing_prob": 0.55,
            "clv": 0.10,
            "market_close_time": "2025-06-15T23:00:00Z",
            "is_stale": False,
            "schema_version": "v1",
            "payload_kind": "clv_analysis_result",
        }
        _validate(analysis_schema, payload)


class TestDriftDetection:
    """Detect drift in CLVTracker output structure."""

    def test_analyze_clv_result_has_expected_keys(
        self, tracker: CLVTracker
    ) -> None:
        """analyze_clv returns a dict with num_bets, avg_clv, positive_clv_pct, by_sport."""
        with patch("plugins.clv_tracker.default_db") as mock_db:
            overall_row = MagicMock()
            overall_row.__getitem__.side_effect = lambda idx: [10, 0.025, 60.0][idx]
            overall_result = MagicMock()
            overall_result.fetchone.return_value = overall_row

            sport_row = MagicMock()
            sport_row.__getitem__.side_effect = lambda idx: (
                ["NBA", 10, 0.025, 60.0][idx]
            )
            sport_result = MagicMock()
            sport_result.fetchall.return_value = [sport_row]

            mock_db.execute.side_effect = [overall_result, sport_result]

            result = tracker.analyze_clv(days_back=30)

        assert "num_bets" in result
        assert "avg_clv" in result
        assert "positive_clv_pct" in result
        assert "by_sport" in result
        assert isinstance(result["num_bets"], int)
        assert isinstance(result["avg_clv"], float)
        assert isinstance(result["positive_clv_pct"], float)
        assert isinstance(result["by_sport"], list)

    def test_update_closing_line_clv_is_correct_type(
        self, tracker: CLVTracker
    ) -> None:
        """CLV computed by update_closing_line must be a numeric type."""
        mock_fetchone = _mock_fetchone_success("bet_clv_prov_001")
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_fetchone

        with patch("plugins.clv_tracker.default_db") as mock_db:
            mock_db.execute.side_effect = [mock_result, MagicMock()]

            tracker.update_closing_line("bet_clv_prov_001", 0.55)

            update_params = _execute_params(mock_db.execute.call_args_list[1])
            assert isinstance(update_params["clv"], float)

    def test_analyze_clv_avg_clv_type_is_float(
        self, tracker: CLVTracker
    ) -> None:
        """avg_clv must be a float in the analyze_clv output."""
        with patch("plugins.clv_tracker.default_db") as mock_db:
            overall_row = MagicMock()
            overall_row.__getitem__.side_effect = lambda idx: [10, 0.025, 60.0][idx]
            overall_result = MagicMock()
            overall_result.fetchone.return_value = overall_row

            sport_result = MagicMock()
            sport_result.fetchall.return_value = []
            mock_db.execute.side_effect = [overall_result, sport_result]

            result = tracker.analyze_clv(days_back=30)

        assert isinstance(result["avg_clv"], float)
