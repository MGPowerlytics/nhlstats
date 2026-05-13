"""Bet Detail drill-down for governed recommendation and placement rows."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from dashboard.data_layer import (
    DashboardDataError,
    DashboardEmptyState,
    get_bet_detail,
)


def _state_text(payload: dict[str, str | None]) -> str:
    """Build compact display text from a sanitized data-layer state payload."""

    title = payload.get("title") or "Dashboard state"
    message = payload.get("message")
    return title if not message else f"{title}: {message}"


def _render_state(
    payload: dict[str, str | None], selected_bet_id: str | None = None
) -> None:
    """Render governed empty/error states without exposing raw exceptions."""

    body = _state_text(payload)
    if selected_bet_id and payload.get("kind") == "bet_not_found":
        body = f"{body} Selected bet: {selected_bet_id}"

    if payload.get("severity") == "error":
        st.error(body)
    elif payload.get("severity") == "warning":
        st.warning(body)
    else:
        st.info(body)

    action = payload.get("action")
    kind = payload.get("kind")
    if action:
        st.caption(action)
    if kind:
        st.caption(f"State: {kind}")


def _fallback_bet_not_found() -> dict[str, str | None]:
    """Return an explicit not-found state for legacy empty exceptions."""

    return {
        "kind": "bet_not_found",
        "title": "Bet not found",
        "message": "The selected bet is not available in the governed detail view.",
        "action": "Return to recent activity and choose an available bet.",
        "severity": "info",
    }


def _no_bet_details() -> dict[str, str | None]:
    """Return an explicit no-detail state when the data layer has no row payload."""

    return {
        "kind": "no_bet_details",
        "title": "No bet details",
        "message": "No governed bet detail rows are available yet.",
        "action": "Run recommendation ingestion before opening bet details.",
        "severity": "info",
    }


def _format_percent(value: Any) -> str:
    """Format nullable probability-like values."""

    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.1%}"


def _format_currency(value: Any) -> str:
    """Format nullable dollar values."""

    if value is None or pd.isna(value):
        return "—"
    return f"${float(value):,.2f}"


def _format_signed_currency(value: Any) -> str:
    """Format nullable profit values with an explicit sign."""

    if value is None or pd.isna(value):
        return "—"
    amount = float(value)
    sign = "+" if amount > 0 else ""
    return f"{sign}${amount:,.2f}"


def _format_market_price(value: Any) -> str:
    """Format nullable yes/no ask values without assuming a unit scale."""

    if value is None or pd.isna(value):
        return "—"
    price = float(value)
    return str(int(price)) if price.is_integer() else f"{price:.2f}"


def _format_text(value: Any) -> str:
    """Format nullable display text."""

    if value is None or pd.isna(value):
        return "—"
    text = str(value)
    return text if text else "—"


def _render_back_button() -> None:
    """Return to the parent dashboard page when requested."""

    if st.button("← Back"):
        st.session_state["show_bet_detail"] = None
        st.rerun()


def _render_summary_metrics(bet: dict[str, Any]) -> None:
    """Render the top-level recommendation and placement summary."""

    status = _format_text(bet.get("status"))
    normalized_status = status.lower()
    profit = bet.get("profit_dollars")
    profit_delta_color = "off"
    if normalized_status in {"won", "win", "settled_won"}:
        profit_delta_color = "normal"
    elif normalized_status in {"lost", "loss", "settled_lost"}:
        profit_delta_color = "inverse"

    cols = st.columns(4)
    cols[0].metric("Bet ID", _format_text(bet.get("bet_id")))
    cols[1].metric(
        "Teams",
        f"{_format_text(bet.get('home_team'))} vs {_format_text(bet.get('away_team'))}",
    )
    cols[2].metric("Bet On", _format_text(bet.get("bet_on")))
    cols[3].metric("Status", status)

    cols = st.columns(4)
    cols[0].metric("Elo Probability", _format_percent(bet.get("elo_prob")))
    cols[1].metric("Market Probability", _format_percent(bet.get("market_prob")))
    cols[2].metric("Edge", _format_percent(bet.get("edge")))
    cols[3].metric("EV", _format_currency(bet.get("expected_value")))

    cols = st.columns(4)
    cols[0].metric("Kelly", _format_percent(bet.get("kelly_fraction")))
    cols[1].metric("Confidence", _format_text(bet.get("confidence")))
    cols[2].metric("Yes Ask", _format_market_price(bet.get("yes_ask")))
    cols[3].metric("No Ask", _format_market_price(bet.get("no_ask")))

    cols = st.columns(4)
    cols[0].metric("Cost", _format_currency(bet.get("cost_dollars")))
    cols[1].metric("Payout", _format_currency(bet.get("payout_dollars")))
    cols[2].metric(
        "Profit",
        _format_signed_currency(profit),
        delta_color=profit_delta_color,
    )
    cols[3].metric("Ticker", _format_text(bet.get("ticker")))


def _render_detail_fields(
    bet: dict[str, Any],
    execution_link: dict[str, Any],
    clv_evidence: dict[str, Any],
) -> None:
    """Render traceability fields that are clearer as text than KPI tiles."""

    st.subheader("Traceability")
    st.write(f"Recommendation date: {_format_text(bet.get('recommendation_date'))}")
    st.write(f"Placed time: {_format_text(bet.get('placed_time_utc'))}")
    st.write(f"Created at: {_format_text(bet.get('created_at'))}")
    st.write("Linkage status: " f"{_format_text(execution_link.get('linkage_status'))}")
    st.write("Linkage basis: " f"{_format_text(execution_link.get('linkage_basis'))}")
    st.write(
        "Entry quote role: " f"{_format_text(execution_link.get('entry_quote_role'))}"
    )
    st.write(
        "Entry price source: "
        f"{_format_text(execution_link.get('entry_price_source'))}"
    )
    st.write(
        "Entry quote source: "
        f"{_format_text(execution_link.get('entry_quote_source_system'))}"
    )
    st.write(
        "Entry quote bookmaker: "
        f"{_format_text(execution_link.get('entry_quote_bookmaker'))}"
    )
    st.write(
        "Close-line source type: "
        f"{_format_text(clv_evidence.get('clv_source_type'))}"
    )
    st.write(
        "Closing quote source: "
        f"{_format_text(clv_evidence.get('closing_quote_source'))}"
    )
    st.write(
        "Close price role: " f"{_format_text(clv_evidence.get('close_price_role'))}"
    )
    st.write(
        "Selected close rule: "
        f"{_format_text(clv_evidence.get('selected_close_rule'))}"
    )
    st.write(
        "CLV evidence tier: " f"{_format_text(clv_evidence.get('clv_evidence_tier'))}"
    )


def render_bet_detail(bet_id: str) -> None:
    """Render the full bet traceability view for a selected bet ID."""

    st.header(f"Bet Detail: {bet_id}")

    try:
        detail = get_bet_detail(bet_id)
    except DashboardDataError as exc:
        _render_state(exc.payload, bet_id)
        return
    except DashboardEmptyState as exc:
        _render_state(exc.payload, bet_id)
        return
    except ValueError:
        _render_state(_fallback_bet_not_found(), bet_id)
        return

    empty_state = detail.get("empty_state")
    bet = detail.get("bet") or {}
    execution_link = detail.get("execution_link") or {}
    clv_evidence = detail.get("clv_evidence") or {}
    if empty_state or not bet:
        _render_state(empty_state or _no_bet_details(), bet_id)
        return

    _render_back_button()
    _render_summary_metrics(bet)
    st.divider()
    _render_detail_fields(bet, execution_link, clv_evidence)
