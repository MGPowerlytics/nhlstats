"""Focused unit tests for the Portfolio Streamlit page."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from dashboard.data_layer import DashboardDataError, DashboardStatePayload
from dashboard.pages import portfolio


@dataclass
class FakeColumn:
    """Small Streamlit column test double."""

    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]]

    def metric(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("metric", args, kwargs))


@dataclass
class FakeStreamlit:
    """Streamlit test double that records rendered content."""

    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(
        default_factory=list
    )

    def title(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("title", args, kwargs))

    def columns(self, spec: Any) -> list[FakeColumn]:
        count = spec if isinstance(spec, int) else len(spec)
        return [FakeColumn(self.calls) for _ in range(count)]

    def metric(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("metric", args, kwargs))

    def divider(self) -> None:
        self.calls.append(("divider", (), {}))

    def subheader(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("subheader", args, kwargs))

    def plotly_chart(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("plotly_chart", args, kwargs))

    def dataframe(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("dataframe", args, kwargs))

    def info(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("info", args, kwargs))

    def error(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("error", args, kwargs))


class FakeFigure:
    """Plotly figure test double."""

    def update_layout(self, **_: Any) -> None:
        return None


def _portfolio_snapshots_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "snapshot_hour_utc": datetime(2026, 5, 3, 11, tzinfo=timezone.utc),
                "balance_dollars": 1100.0,
                "portfolio_value_dollars": 1450.0,
                "cumulative_deposits_dollars": 1000.0,
                "realized_profit_dollars": 225.0,
                "open_risk_dollars": 60.0,
                "settled_bet_count": 9,
                "open_bet_count": 1,
                "roi": 0.45,
                "created_at_utc": datetime(2026, 5, 3, 11, 1, tzinfo=timezone.utc),
                "timestamp": "2026-05-03T11:00:00+00:00",
                "portfolio_value": 1450.0,
            },
            {
                "snapshot_hour_utc": datetime(2026, 5, 3, 12, tzinfo=timezone.utc),
                "balance_dollars": 1200.0,
                "portfolio_value_dollars": 1500.0,
                "cumulative_deposits_dollars": 1000.0,
                "realized_profit_dollars": 250.0,
                "open_risk_dollars": 75.0,
                "settled_bet_count": 10,
                "open_bet_count": 2,
                "roi": 0.5,
                "created_at_utc": datetime(2026, 5, 3, 12, 1, tzinfo=timezone.utc),
                "timestamp": "2026-05-03T12:00:00+00:00",
                "portfolio_value": 1500.0,
            },
        ]
    )


def _summary() -> dict[str, Any]:
    return {
        "portfolio_value": 1500.0,
        "daily_pnl": 250.0,
        "open_bets_count": 2,
        "total_exposure": 75.0,
        "win_rate": 0.0,
        "total_bets": 12,
        "settled_count": 10,
        "empty_state": None,
    }


def _governed_portfolio_risk_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sport": "NHL",
                "market_type": None,
                "cohort_type": "all",
                "evidence_dimension": "portfolio_risk",
                "canonical_game_id": None,
                "market_ticker": None,
                "selection_key": None,
                "source_relation": "placed_bets",
                "source_record_id": "NHL",
                "evidence_state_scope": "sport",
                "evidence_state": "blocked",
                "evidence_state_reason": "NHL remains blocked until governed approval evidence exists.",
                "evidence_state_as_of": "2026-05-12T00:00:00Z",
                "evidence_state_source_artifact": "docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md",
                "governance_status": "descriptive_only",
                "descriptive_only_flag": True,
                "contamination_flag": False,
                "contamination_reason": None,
                "excluded_from_approval_flag": True,
                "observed_at": "2026-05-03T14:15:00Z",
                "loaded_at": "2026-05-03T14:01:00Z",
                "last_updated_at": "2026-05-03T14:15:00Z",
                "snapshot_hour_utc": "2026-05-03T14:00:00Z",
                "open_exposure_flag": True,
                "open_exposure_amount": 22.0,
                "position_status": "open",
                "exposure_inclusion_state": "included_open_risk",
                "sport_exposure_amount": 22.0,
                "same_event_exposure_amount": None,
                "same_side_exposure_amount": None,
                "existing_position_flag": True,
                "resting_order_exposure_amount": 10.0,
                "resting_order_count": 1,
                "executed_unsettled_exposure_amount": 12.0,
                "executed_unsettled_count": 1,
                "exposure_state": "mixed_open_exposure",
                "daily_risk_cap_dollars": 368.94,
                "remaining_daily_risk_budget_dollars": 346.94,
                "peak_portfolio_value_dollars": 1600.0,
                "current_portfolio_value_dollars": 1475.75,
                "drawdown_amount_dollars": 124.25,
                "drawdown_ratio": 0.07765625,
                "drawdown_state": "drawdown_active",
                "risk_of_ruin_state": "capital_available",
                "portfolio_guardrail_state": "eligible",
                "portfolio_guardrail_reason_code": None,
                "portfolio_guardrail_reason_detail": None,
                "concentration_bucket": "same_side",
                "concentration_state": "descriptive_only_no_governed_limit",
                "existing_position_state": "mixed_open_exposure",
                "same_match_conflict": True,
                "rejection_reason_code": "missing_evidence",
                "rejection_reason_detail": "NHL remains blocked until governed approval evidence exists.",
                "operator_semantics_version": "portfolio_risk_state_v1",
                "bankroll_source": "portfolio_value_snapshots",
                "bankroll_amount": 1475.75,
                "bankroll_observed_at": "2026-05-03T14:00:00Z",
                "bankroll_snapshot_id": "2026-05-03T14:00:00",
            }
        ]
    )


def _blocked_drawdown_governed_portfolio_risk_frame() -> pd.DataFrame:
    frame = _governed_portfolio_risk_frame().copy()
    frame.loc[:, "portfolio_guardrail_state"] = "blocked_drawdown"
    frame.loc[:, "portfolio_guardrail_reason_code"] = "drawdown_gate_blocked"
    frame.loc[:, "portfolio_guardrail_reason_detail"] = (
        "Explicit governed drawdown regime is active for new approvals."
    )
    frame.loc[:, "rejection_reason_code"] = "drawdown_gate_blocked"
    frame.loc[:, "rejection_reason_detail"] = (
        "Explicit governed drawdown regime is active for new approvals."
    )
    return frame


def _rendered_text(fake_st: FakeStreamlit) -> str:
    return "\n".join(
        str(arg)
        for _, args, kwargs in fake_st.calls
        for arg in (*args, *kwargs.values())
    )


def test_portfolio_page_renders_seeded_state_from_data_layer(
    monkeypatch,
) -> None:
    """Seeded portfolio state renders value, balance, deposits, P&L, ROI, and risk."""

    fake_st = FakeStreamlit()
    monkeypatch.setattr(portfolio, "st", fake_st)
    monkeypatch.setattr(portfolio, "get_portfolio_summary", _summary)
    monkeypatch.setattr(
        portfolio,
        "get_portfolio_snapshots",
        lambda hours=168: _portfolio_snapshots_frame(),
    )
    monkeypatch.setattr(
        portfolio,
        "get_governed_portfolio_risk_state",
        _governed_portfolio_risk_frame,
    )
    monkeypatch.setattr(portfolio.px, "area", lambda *args, **kwargs: FakeFigure())

    portfolio.render()

    metric_labels = [args[0] for name, args, _ in fake_st.calls if name == "metric"]
    assert "Portfolio Value" in metric_labels
    assert "Balance" in metric_labels
    assert "Deposits" in metric_labels
    assert "Realized P&L" in metric_labels
    assert "ROI" in metric_labels
    assert "Open Risk" in metric_labels
    assert "Position Summary" in _rendered_text(fake_st)
    assert "$22.00" in _rendered_text(fake_st)
    assert "governed open exposure of $22.00" in _rendered_text(fake_st)
    assert any(name == "plotly_chart" for name, _, _ in fake_st.calls)
    assert any(name == "dataframe" for name, _, _ in fake_st.calls)


def test_portfolio_page_surfaces_governed_exposure_truth_and_rejections(
    monkeypatch,
) -> None:
    """Portfolio page renders governed exposure truth alongside legacy KPIs."""

    fake_st = FakeStreamlit()
    monkeypatch.setattr(portfolio, "st", fake_st)
    monkeypatch.setattr(portfolio, "get_portfolio_summary", _summary)
    monkeypatch.setattr(
        portfolio,
        "get_portfolio_snapshots",
        lambda hours=168: _portfolio_snapshots_frame(),
    )
    monkeypatch.setattr(
        portfolio,
        "get_governed_portfolio_risk_state",
        _governed_portfolio_risk_frame,
    )
    monkeypatch.setattr(portfolio.px, "area", lambda *args, **kwargs: FakeFigure())

    portfolio.render()

    rendered = _rendered_text(fake_st)
    assert "Governed Risk State" in rendered
    assert "Governed open exposure totals $22.00" in rendered
    assert "resting-order exposure" in rendered
    assert "executed-unsettled" in rendered.lower()
    assert "drawdown_active" in rendered
    assert "Portfolio guardrail code: none." in rendered
    assert "Portfolio guardrail detail: none." in rendered
    assert "drawdown_gate_blocked" not in rendered
    assert "missing_evidence" in rendered
    assert "NHL remains blocked until governed approval evidence exists." in rendered


def test_portfolio_page_surfaces_explicit_drawdown_guardrail_detail(
    monkeypatch,
) -> None:
    """Portfolio page renders explicit drawdown guardrail messaging when blocked."""

    fake_st = FakeStreamlit()
    monkeypatch.setattr(portfolio, "st", fake_st)
    monkeypatch.setattr(portfolio, "get_portfolio_summary", _summary)
    monkeypatch.setattr(
        portfolio,
        "get_portfolio_snapshots",
        lambda hours=168: _portfolio_snapshots_frame(),
    )
    monkeypatch.setattr(
        portfolio,
        "get_governed_portfolio_risk_state",
        _blocked_drawdown_governed_portfolio_risk_frame,
    )
    monkeypatch.setattr(portfolio.px, "area", lambda *args, **kwargs: FakeFigure())

    portfolio.render()

    rendered = _rendered_text(fake_st)
    assert "drawdown_gate_blocked" in rendered
    assert (
        "Portfolio guardrail detail: Explicit governed drawdown regime is active for new approvals."
        in rendered
    )


def test_portfolio_page_renders_explicit_no_snapshots_empty_state(
    monkeypatch,
) -> None:
    """Zero governed portfolio rows render no_portfolio_snapshots explicitly."""

    empty_state = {
        "kind": "no_portfolio_snapshots",
        "title": "No portfolio snapshots",
        "message": "No governed portfolio snapshots are available yet.",
        "action": "Run the portfolio snapshot ingestion before relying on dashboard KPIs.",
        "severity": "info",
    }
    fake_st = FakeStreamlit()
    monkeypatch.setattr(portfolio, "st", fake_st)
    monkeypatch.setattr(
        portfolio,
        "get_portfolio_summary",
        lambda: {**_summary(), "portfolio_value": 0.0, "empty_state": empty_state},
    )
    empty_snapshots = pd.DataFrame()
    empty_snapshots.attrs["empty_state"] = empty_state
    monkeypatch.setattr(
        portfolio, "get_portfolio_snapshots", lambda hours=168: empty_snapshots
    )
    monkeypatch.setattr(
        portfolio, "get_governed_portfolio_risk_state", lambda: pd.DataFrame()
    )

    portfolio.render()

    rendered = _rendered_text(fake_st)
    assert "no_portfolio_snapshots" in rendered
    assert "No portfolio snapshots" in rendered
    assert not any(name == "plotly_chart" for name, _, _ in fake_st.calls)


def test_portfolio_page_renders_sanitized_data_layer_errors(
    monkeypatch,
) -> None:
    """Portfolio page displays only sanitized data-layer error payloads."""

    raw_tokens = ("SELECT", "postgresql://", "password", "Traceback")
    payload = DashboardStatePayload(
        kind="dashboard_query_failed",
        title="Dashboard query failed",
        message="The governed read model dashboard_portfolio_v1 could not be read.",
        action="Check dashboard data-layer logs and read-model migrations.",
        severity="error",
    )
    fake_st = FakeStreamlit()
    monkeypatch.setattr(portfolio, "st", fake_st)
    monkeypatch.setattr(
        portfolio,
        "get_portfolio_summary",
        lambda: (_ for _ in ()).throw(DashboardDataError(payload)),
    )
    monkeypatch.setattr(
        portfolio, "get_governed_portfolio_risk_state", lambda: pd.DataFrame()
    )

    portfolio.render()

    rendered = _rendered_text(fake_st)
    assert "dashboard_query_failed" in rendered
    assert "Dashboard query failed" in rendered
    for token in raw_tokens:
        assert token not in rendered
    assert any(name == "error" for name, _, _ in fake_st.calls)


def test_portfolio_page_has_no_direct_sql_or_source_table_references() -> None:
    """The page remains bound to data_layer helpers, not source tables or SQL."""

    source = Path(portfolio.__file__).read_text(encoding="utf-8")
    forbidden = (
        "SELECT ",
        " FROM ",
        "JOIN ",
        "portfolio_value_snapshots",
        "placed_bets",
    )
    for token in forbidden:
        assert token not in source
