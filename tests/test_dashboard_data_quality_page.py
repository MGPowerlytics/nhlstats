"""Focused unit tests for the governed Data Quality Streamlit page."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dashboard import data_layer
from dashboard.pages import data_quality


class FakeStreamlit:
    """Capture Streamlit calls made by the Data Quality page."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def title(self, value: str) -> None:
        self.calls.append(("title", value))

    def metric(self, label: str, value: Any, **kwargs: Any) -> None:
        self.calls.append(("metric", (label, value, kwargs)))

    def subheader(self, value: str) -> None:
        self.calls.append(("subheader", value))

    def dataframe(self, value: Any, **kwargs: Any) -> None:
        self.calls.append(("dataframe", value))
        self.calls.append(("dataframe_kwargs", kwargs))

    def info(self, value: str) -> None:
        self.calls.append(("info", value))

    def warning(self, value: str) -> None:
        self.calls.append(("warning", value))

    def error(self, value: str) -> None:
        self.calls.append(("error", value))

    def success(self, value: str) -> None:
        self.calls.append(("success", value))

    def caption(self, value: str) -> None:
        self.calls.append(("caption", value))


def _check(
    *,
    check_name: str = "view_exists",
    relation_name: str = "dashboard_portfolio_v1",
    relation_type: str = "view",
    status: str = "pass",
    row_count: int | None = 1,
    freshness_timestamp: str | None = "2026-05-03T14:00:00+00:00",
    max_allowed_lag_minutes: int | None = 120,
    actual_lag_minutes: int | None = 15,
    message: str = "Check passed.",
    checked_at_utc: str = "2026-05-03T14:15:00+00:00",
) -> dict[str, Any]:
    return {
        "check_name": check_name,
        "relation_name": relation_name,
        "relation_type": relation_type,
        "status": status,
        "row_count": row_count,
        "freshness_timestamp": freshness_timestamp,
        "max_allowed_lag_minutes": max_allowed_lag_minutes,
        "actual_lag_minutes": actual_lag_minutes,
        "message": message,
        "checked_at_utc": checked_at_utc,
    }


def _render_with(monkeypatch, payload: dict[str, Any] | data_layer.DashboardDataError):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(data_quality, "st", fake_st)

    def fake_report() -> dict[str, Any]:
        if isinstance(payload, data_layer.DashboardDataError):
            raise payload
        return payload

    monkeypatch.setattr(data_quality, "get_data_quality_report", fake_report)
    data_quality.render()
    return fake_st


def _rendered_text(fake_st: FakeStreamlit) -> str:
    return "\n".join(str(item) for call in fake_st.calls for item in call)


def test_data_quality_page_renders_all_ok_seeded_checks(monkeypatch) -> None:
    """All passing checks render governed freshness, row count, relation type, and message."""

    fake_st = _render_with(
        monkeypatch,
        {
            "overall_health": 100,
            "checks": [
                _check(
                    check_name="freshness_portfolio_value_snapshots",
                    relation_name="portfolio_value_snapshots",
                    relation_type="table",
                    row_count=24,
                    actual_lag_minutes=10,
                    message="Freshness within threshold.",
                ),
                _check(
                    check_name="view_exists_dashboard_portfolio",
                    relation_name="dashboard_portfolio_v1",
                    relation_type="view",
                    row_count=24,
                    freshness_timestamp=None,
                    max_allowed_lag_minutes=None,
                    actual_lag_minutes=None,
                    message="View exists.",
                ),
            ],
            "empty_state": None,
        },
    )

    assert ("success", "All governed data-quality checks are passing.") in fake_st.calls
    dataframe_calls = [call for call in fake_st.calls if call[0] == "dataframe"]
    assert len(dataframe_calls) == 1
    displayed = dataframe_calls[0][1]
    assert list(displayed.columns) == [
        "Status",
        "Check",
        "Relation",
        "Type",
        "Rows",
        "Freshness Timestamp",
        "Lag (min)",
        "Max Lag (min)",
        "Message",
        "Checked At",
    ]
    assert displayed.iloc[0]["Status"] == "PASS"
    assert displayed.iloc[0]["Type"] == "table"
    assert displayed.iloc[0]["Rows"] == 24
    assert displayed.iloc[0]["Freshness Timestamp"] == "2026-05-03T14:00:00+00:00"
    assert displayed.iloc[0]["Message"] == "Freshness within threshold."


def test_data_quality_page_renders_degraded_warn_and_fail_checks(monkeypatch) -> None:
    """Warn/fail checks render as visible degraded health, not all-good state."""

    fake_st = _render_with(
        monkeypatch,
        {
            "overall_health": 30,
            "checks": [
                _check(
                    relation_name="game_odds",
                    relation_type="table",
                    status="warn",
                    row_count=0,
                    actual_lag_minutes=180,
                    message="Rows are stale.",
                ),
                _check(
                    relation_name="dashboard_live_markets_v1",
                    relation_type="view",
                    status="fail",
                    row_count=0,
                    message="Required view has no rows.",
                ),
            ],
            "empty_state": None,
        },
    )

    rendered_text = _rendered_text(fake_st)
    assert "Degraded checks: 1 warning, 1 failure." in rendered_text
    assert "WARN" in rendered_text
    assert "FAIL" in rendered_text
    assert "Rows are stale." in rendered_text
    assert "Required view has no rows." in rendered_text


def test_data_quality_page_renders_zero_check_contract_error(monkeypatch) -> None:
    """Zero checks are a hard visible contract error, not an empty/all-good state."""

    error = data_layer.DashboardDataError(
        data_layer.DashboardStatePayload(
            kind="dashboard_contract_mismatch",
            title="Dashboard contract mismatch",
            message="dashboard data-quality checks are unavailable.",
            action="Update the read-model migration or dashboard mapper.",
            severity="error",
        )
    )
    fake_st = _render_with(monkeypatch, error)

    rendered_text = _rendered_text(fake_st)
    assert "Dashboard contract mismatch" in rendered_text
    assert "dashboard data-quality checks are unavailable." in rendered_text
    assert "All governed data-quality checks are passing" not in rendered_text
    assert not [call for call in fake_st.calls if call[0] == "dataframe"]


def test_data_quality_page_renders_sanitized_data_layer_failure(monkeypatch) -> None:
    """Data-layer failures show sanitized payloads without raw SQL or secrets."""

    error = data_layer.DashboardDataError(
        data_layer.DashboardStatePayload(
            kind="dashboard_query_failed",
            title="Dashboard query failed",
            message="The governed data quality checks could not be read.",
            action="Check dashboard data-layer logs and read-model migrations.",
            severity="error",
        )
    )
    fake_st = _render_with(monkeypatch, error)

    rendered_text = _rendered_text(fake_st)
    assert "dashboard_query_failed" in rendered_text
    assert "Dashboard query failed" in rendered_text
    assert "SELECT" not in rendered_text
    assert "password" not in rendered_text
    assert "postgresql://" not in rendered_text


def test_data_quality_page_has_no_direct_sql_or_source_table_references() -> None:
    """The page remains bound to data_layer helpers, not source tables or SQL."""

    source = Path(data_quality.__file__).read_text(encoding="utf-8")
    forbidden = (
        "SELECT ",
        " FROM ",
        "JOIN ",
        "portfolio_value_snapshots",
        "placed_bets",
        "bet_recommendations",
        "game_odds",
        "elo_ratings",
    )
    for token in forbidden:
        assert token not in source
