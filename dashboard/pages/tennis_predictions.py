"""Current actionable tennis betting predictions."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from dashboard import data_layer
from dashboard.data_layer import DashboardDataError


DISPLAY_COLUMNS = [
    "home_team",
    "away_team",
    "bet_on",
    "model_prob",
    "market_prob",
    "edge",
    "expected_value",
    "kelly_fraction",
    "confidence",
    "ticker",
    "bet_id",
]


def render() -> None:
    """Render current-run actionable tennis prediction table."""
    st.title("Tennis Predictions")
    st.caption(
        "Latest actionable TENNIS bets from the current run, ordered by model edge."
    )

    try:
        predictions = data_layer.get_tomorrow_tennis_predictions()
    except DashboardDataError as exc:
        _render_state(exc.payload)
        return

    if predictions.empty:
        _render_state(
            predictions.attrs.get("empty_state")
            or {
                "kind": "no_tennis_predictions",
                "title": "No actionable tennis predictions",
                "message": "No governed actionable TENNIS predictions are available for the current run date.",
                "action": "Run tennis market ingestion and recommendation loading before placing bets.",
                "severity": "info",
            }
        )
        return

    st.subheader(
        f"Current actionable tennis bets — {len(predictions)} "
        f"prediction{'s' if len(predictions) != 1 else ''}"
    )
    st.caption("Source: dashboard_tennis_predictions_v1.")
    display = predictions[DISPLAY_COLUMNS].rename(
        columns={
            "home_team": "Player A",
            "away_team": "Player B",
            "bet_on": "Bet On",
            "model_prob": "Model Prob",
            "market_prob": "Market Prob",
            "edge": "Edge",
            "expected_value": "Expected Value",
            "kelly_fraction": "Kelly Fraction",
            "confidence": "Confidence",
            "ticker": "Ticker",
            "bet_id": "Bet ID",
        }
    )
    st.dataframe(
        display.style.format(
            {
                "Model Prob": _format_pct,
                "Market Prob": _format_pct,
                "Edge": _format_pct,
                "Expected Value": _format_pct,
                "Kelly Fraction": _format_pct,
            },
            na_rep="N/A",
        ),
        use_container_width=True,
        hide_index=True,
    )


def _state_text(payload: dict[str, str | None]) -> str:
    parts = [
        payload.get("kind"),
        payload.get("title"),
        payload.get("message"),
        payload.get("action"),
    ]
    return " — ".join(str(part) for part in parts if part)


def _render_state(payload: dict[str, str | None]) -> None:
    message = _state_text(payload)
    if payload.get("severity") == "error":
        st.error(message)
    else:
        st.info(message)


def _format_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.1%}"
