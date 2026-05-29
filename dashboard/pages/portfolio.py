"""Portfolio Overview — governed portfolio health, P&L, and open risk."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data_layer import (
    DashboardDataError,
    get_governed_portfolio_risk_state,
    get_portfolio_snapshots,
    get_portfolio_summary,
)
from dashboard.shared import render_state


def _money(value: Any) -> str:
    """Format a numeric value as dollars."""

    return f"${float(value or 0.0):,.2f}"


def _percent(value: Any) -> str:
    """Format a nullable decimal ratio as a percentage."""

    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.1%}"


def _latest_snapshot(snapshots: pd.DataFrame) -> dict[str, Any]:
    """Return the newest governed portfolio snapshot as a plain dictionary."""

    if snapshots.empty:
        return {}
    return snapshots.sort_values("snapshot_hour_utc").iloc[-1].to_dict()


def _render_error(error: DashboardDataError) -> None:
    """Render a sanitized data-layer error without exposing exception internals."""

    payload = getattr(error, "payload", None)
    if isinstance(payload, dict):
        render_state(payload)
        return
    st.error("dashboard_query_failed — Dashboard query failed")


def _governed_open_exposure(
    governed_risk: pd.DataFrame, fallback_value: float | int
) -> float:
    """Return the governed open exposure total, or the legacy fallback value."""

    if governed_risk.empty:
        return float(fallback_value or 0.0)
    return float(governed_risk["open_exposure_amount"].fillna(0.0).sum())


def _render_kpis(
    summary: dict[str, Any], latest: dict[str, Any], governed_risk: pd.DataFrame
) -> None:
    """Render top-level portfolio KPI cards."""

    portfolio_value = latest.get(
        "portfolio_value_dollars", summary.get("portfolio_value", 0.0)
    )
    realized_profit = latest.get(
        "realized_profit_dollars", summary.get("daily_pnl", 0.0)
    )
    open_risk = _governed_open_exposure(
        governed_risk,
        latest.get("open_risk_dollars", summary.get("total_exposure", 0.0)),
    )

    cols = st.columns(4)
    cols[0].metric("Portfolio Value", _money(portfolio_value))
    cols[1].metric("Balance", _money(latest.get("balance_dollars", 0.0)))
    cols[2].metric("Deposits", _money(latest.get("cumulative_deposits_dollars", 0.0)))
    cols[3].metric("Realized P&L", _money(realized_profit))

    cols = st.columns(4)
    cols[0].metric("ROI", _percent(latest.get("roi")))
    cols[1].metric("Open Risk", _money(open_risk))
    cols[2].metric("Open Positions", int(summary.get("open_bets_count", 0)))
    cols[3].metric("Settled Positions", int(summary.get("settled_count", 0)))


def _render_position_summary(
    summary: dict[str, Any], latest: dict[str, Any], governed_risk: pd.DataFrame
) -> None:
    """Render the position-count summary supported by the portfolio read model."""

    st.subheader("Position Summary")
    open_count = int(latest.get("open_bet_count", summary.get("open_bets_count", 0)))
    settled_count = int(
        latest.get("settled_bet_count", summary.get("settled_count", 0))
    )
    open_risk = _governed_open_exposure(
        governed_risk,
        latest.get("open_risk_dollars", summary.get("total_exposure", 0.0)),
    )
    position_rows = pd.DataFrame(
        [
            {"Status": "Open", "Positions": open_count, "Amount": _money(open_risk)},
            {
                "Status": "Settled",
                "Positions": settled_count,
                "Amount": _money(latest.get("realized_profit_dollars", 0.0)),
            },
        ]
    )
    st.dataframe(position_rows, use_container_width=True, hide_index=True)
    st.info(
        f"{open_count} open positions with governed open exposure of {_money(open_risk)}"
    )


def _render_governed_risk_state(governed_risk: pd.DataFrame) -> None:
    """Render approval-facing governed exposure truth and rejection semantics."""

    st.subheader("Governed Risk State")
    if governed_risk.empty:
        st.info("No governed portfolio risk rows are available yet.")
        return

    display = governed_risk.loc[
        :,
        [
            "sport",
            "open_exposure_amount",
            "resting_order_exposure_amount",
            "executed_unsettled_exposure_amount",
            "remaining_daily_risk_budget_dollars",
            "drawdown_state",
            "drawdown_amount_dollars",
            "risk_of_ruin_state",
            "portfolio_guardrail_state",
            "portfolio_guardrail_reason_code",
            "portfolio_guardrail_reason_detail",
            "exposure_state",
            "rejection_reason_code",
            "rejection_reason_detail",
        ],
    ].rename(
        columns={
            "sport": "Sport",
            "open_exposure_amount": "Governed Open Exposure",
            "resting_order_exposure_amount": "Resting Order Exposure",
            "executed_unsettled_exposure_amount": "Executed-Unsettled Exposure",
            "remaining_daily_risk_budget_dollars": "Remaining Daily Risk Budget",
            "drawdown_state": "Drawdown State",
            "drawdown_amount_dollars": "Drawdown Amount",
            "risk_of_ruin_state": "Risk-of-Ruin State",
            "portfolio_guardrail_state": "Portfolio Guardrail State",
            "portfolio_guardrail_reason_code": "Portfolio Guardrail Code",
            "portfolio_guardrail_reason_detail": "Portfolio Guardrail Detail",
            "exposure_state": "Exposure State",
            "rejection_reason_code": "Rejection Code",
            "rejection_reason_detail": "Rejection Detail",
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    governed_open = float(governed_risk["open_exposure_amount"].fillna(0.0).sum())
    resting = float(governed_risk["resting_order_exposure_amount"].fillna(0.0).sum())
    executed = float(
        governed_risk["executed_unsettled_exposure_amount"].fillna(0.0).sum()
    )
    rejection_codes = ", ".join(
        sorted(
            {
                str(code)
                for code in governed_risk["rejection_reason_code"].dropna().tolist()
                if str(code)
            }
        )
    )
    rejection_detail = next(
        (
            str(detail)
            for detail in governed_risk["rejection_reason_detail"].dropna().tolist()
            if str(detail)
        ),
        "No rejection detail available.",
    )
    drawdown_state = next(
        (
            str(state)
            for state in governed_risk["drawdown_state"].dropna().tolist()
            if str(state)
        ),
        "drawdown_state_unavailable",
    )
    guardrail_code = next(
        (
            str(code)
            for code in governed_risk["portfolio_guardrail_reason_code"]
            .dropna()
            .tolist()
            if str(code)
        ),
        "none",
    )
    guardrail_detail = next(
        (
            str(detail)
            for detail in governed_risk["portfolio_guardrail_reason_detail"]
            .dropna()
            .tolist()
            if str(detail)
        ),
        "none",
    )
    risk_of_ruin_state = next(
        (
            str(state)
            for state in governed_risk["risk_of_ruin_state"].dropna().tolist()
            if str(state)
        ),
        "risk_of_ruin_state_unavailable",
    )
    st.info(
        "Governed open exposure totals "
        f"{_money(governed_open)} and includes {_money(resting)} in resting-order exposure "
        f"and {_money(executed)} in executed-unsettled exposure. "
        f"Drawdown state: {drawdown_state}. "
        f"Risk-of-ruin state: {risk_of_ruin_state}. "
        f"Portfolio guardrail code: {guardrail_code}. "
        f"Portfolio guardrail detail: {guardrail_detail}. "
        f"Rejection state: {rejection_codes or 'none'}. "
        f"Primary rejection detail: {rejection_detail}"
    )


def _render_value_chart(snapshots: pd.DataFrame) -> None:
    """Render portfolio value history or an explicit empty state."""

    st.subheader("Portfolio Value")
    if snapshots.empty:
        render_state(snapshots.attrs.get("empty_state"))
        return

    fig = px.area(
        snapshots,
        x="timestamp",
        y="portfolio_value",
        title="Portfolio Value (7 days)",
        labels={"timestamp": "Time", "portfolio_value": "Value ($)"},
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def render() -> None:
    """Render the Portfolio page from governed data-layer read models."""

    st.title("Portfolio Overview")

    try:
        summary = get_portfolio_summary()
        if summary.get("empty_state"):
            render_state(summary["empty_state"])
            return

        snapshots = get_portfolio_snapshots(hours=168)
        governed_risk = get_governed_portfolio_risk_state()
    except DashboardDataError as error:
        _render_error(error)
        return

    if snapshots.empty:
        render_state(snapshots.attrs.get("empty_state"))
        return

    latest = _latest_snapshot(snapshots)
    _render_kpis(summary, latest, governed_risk)
    st.divider()
    _render_value_chart(snapshots)
    st.divider()
    _render_position_summary(summary, latest, governed_risk)
    st.divider()
    _render_governed_risk_state(governed_risk)
