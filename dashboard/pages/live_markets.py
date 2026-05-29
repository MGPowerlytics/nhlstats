"""Live Markets — governed market, game, odds, and recommendation context."""

import pandas as pd
import streamlit as st

from dashboard import data_layer
from dashboard.shared import render_state


DISPLAY_COLUMNS = [
    "game_date",
    "commence_time",
    "home_team_name",
    "away_team_name",
    "market_external_id",
    "ticker",
    "bookmaker",
    "market_name",
    "outcome_name",
    "price",
    "last_update",
    "edge",
    "expected_value",
    "confidence",
    "recommendation_bet_id",
]


def _display_frame(markets: pd.DataFrame) -> pd.DataFrame:
    """Return the Live Markets display frame without fabricating fields."""

    available_columns = [
        column for column in DISPLAY_COLUMNS if column in markets.columns
    ]
    display = markets[available_columns].copy()
    for column in ("game_date", "commence_time", "last_update"):
        if column in display.columns:
            display[column] = display[column].map(
                lambda value: "" if pd.isna(value) else str(value)
            )
    return display


def render():
    st.title("Live Markets")

    try:
        markets = data_layer.get_live_markets()
    except data_layer.DashboardDataError as exc:
        render_state(exc.payload)
        return

    st.subheader("Governed Live Markets")
    if markets.empty:
        render_state(
            markets.attrs.get("empty_state")
            or {
                "kind": "no_live_markets",
                "title": "No live markets",
                "message": "No governed live market rows are available right now.",
                "action": "Wait for market ingestion to complete or refresh later.",
                "severity": "info",
            }
        )
        return

    st.dataframe(_display_frame(markets), use_container_width=True, hide_index=True)
