"""Governed tennis model-vs-market evaluation dashboard page."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from dashboard import data_layer
from dashboard.data_layer import DashboardDataError
from dashboard.shared import render_state


DISPLAY_COLUMNS = [
    "run_date",
    "data_source",
    "model_version",
    "holdout_rows",
    "betmgm_holdout_rows",
    "beats_betmgm",
    "ensemble_market_log_loss",
    "betmgm_log_loss",
    "ensemble_vs_betmgm_log_loss_delta",
    "ensemble_market_brier",
    "betmgm_brier",
    "ensemble_vs_betmgm_brier_delta",
    "ensemble_market_accuracy",
    "betmgm_accuracy",
    "ensemble_vs_betmgm_accuracy_delta",
]


def render() -> None:
    """Render the tennis model-health evidence table."""
    st.title("Tennis Model Health")
    st.caption(
        "Production-only governed holdout evidence comparing the tennis ensemble against calibrated Elo and the market baseline."
    )

    try:
        health = data_layer.get_tennis_model_health()
    except DashboardDataError as exc:
        render_state(exc.payload)
        return

    if health.empty:
        render_state(
            health.attrs.get("empty_state")
            or {
                "kind": "no_tennis_model_health",
                "title": "No production tennis model health snapshots",
                "message": "No production PostgreSQL tennis model-vs-market evaluation rows are available yet.",
                "action": "Ensure Kalshi tennis markets are being fetched and run scripts/train_tennis_probability_model.py without --evaluate-only to publish production evidence to PostgreSQL.",
                "severity": "info",
            }
        )
        return

    latest = health.iloc[0]
    verdict = (
        "beats market on shared holdout rows"
        if bool(latest["beats_betmgm"])
        else "does not yet beat market on shared holdout rows"
    )
    st.subheader(f"Latest tennis evaluation — {verdict}")
    st.caption(
        f"Source: {latest['data_source']} | Shared market rows: {int(latest['betmgm_holdout_rows'])}"
    )
    st.caption(
        "Calibration metrics (log loss and Brier) are the primary quality bar; accuracy is shown as secondary context only."
    )

    display = health[DISPLAY_COLUMNS].rename(
        columns={
            "run_date": "Run Date",
            "data_source": "Data Source",
            "model_version": "Model Version",
            "holdout_rows": "Holdout Rows",
            "betmgm_holdout_rows": "Market Rows",
            "beats_betmgm": "Beats Market",
            "ensemble_market_log_loss": "Ensemble Log Loss",
            "betmgm_log_loss": "Market Log Loss",
            "ensemble_vs_betmgm_log_loss_delta": "Log Loss Delta",
            "ensemble_market_brier": "Ensemble Brier",
            "betmgm_brier": "Market Brier",
            "ensemble_vs_betmgm_brier_delta": "Brier Delta",
            "ensemble_market_accuracy": "Ensemble Accuracy",
            "betmgm_accuracy": "Market Accuracy",
            "ensemble_vs_betmgm_accuracy_delta": "Accuracy Delta",
        }
    )
    st.dataframe(
        display.style.format(
            {
                "Ensemble Log Loss": _format_float,
                "Market Log Loss": _format_float,
                "Log Loss Delta": _format_float,
                "Ensemble Brier": _format_float,
                "Market Brier": _format_float,
                "Brier Delta": _format_float,
                "Ensemble Accuracy": _format_pct,
                "Market Accuracy": _format_pct,
                "Accuracy Delta": _format_pct,
            },
            na_rep="N/A",
        ),
        use_container_width=True,
        hide_index=True,
    )


def _format_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.1%}"


def _format_float(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.4f}"
