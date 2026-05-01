"""Live Markets — today's games, Elo probabilities, odds, and active recommendations."""

import streamlit as st
import pandas as pd

from dashboard.data_layer import get_today_games, get_bet_recommendations


def render():
    st.title("Live Markets")

    sport_filter = st.selectbox(
        "Sport",
        ["All", "NBA", "NHL", "MLB", "NFL", "NCAAB", "WNCAAB", "TENNIS", "EPL", "Ligue1", "CBA", "Unrivaled"],
    )
    sport = None if sport_filter == "All" else sport_filter

    # Today's games
    st.subheader("Today's Games")
    games = get_today_games(sport)
    if not games.empty:
        display_cols = ["start_time", "sport", "home_team", "away_team",
                        "home_elo", "away_elo", "home_win_prob",
                        "edge", "edge_side", "confidence"]
        available = [c for c in display_cols if c in games.columns]
        display = games[available].copy()
        if "start_time" in display.columns:
            display["start_time"] = display["start_time"].astype(str).str[:16]
        if "home_win_prob" in display.columns:
            display["home_win_prob"] = (display["home_win_prob"] * 100).round(1).astype(str) + "%"
        if "edge" in display.columns:
            display["edge"] = (display["edge"] * 100).round(1).astype(str) + "%"

        def color_edge(val):
            if val is None or val == "":
                return ""
            try:
                v = float(str(val).rstrip("%"))
                if v >= 8: return "background-color: #1b5e20"
                if v >= 3: return "background-color: #33691e"
                return ""
            except ValueError:
                return ""

        styled = display.style.applymap(color_edge, subset=["edge"] if "edge" in display.columns else [])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.caption("No games scheduled for today.")

    st.divider()

    # Active recommendations
    st.subheader("Active Bet Recommendations")
    recs = get_bet_recommendations(sport)
    if not recs.empty:
        rec_cols = ["sport", "game_id", "bet_on", "side", "elo_prob", "market_prob",
                     "edge", "expected_value", "kelly_fraction", "confidence", "bookmaker"]
        available = [c for c in rec_cols if c in recs.columns]
        display = recs[available].copy()
        if "elo_prob" in display.columns:
            display["elo_prob"] = (display["elo_prob"] * 100).round(1).astype(str) + "%"
        if "market_prob" in display.columns:
            display["market_prob"] = (display["market_prob"] * 100).round(1).astype(str) + "%"
        if "edge" in display.columns:
            display["edge"] = (display["edge"] * 100).round(1).astype(str) + "%"
        if "expected_value" in display.columns:
            display["expected_value"] = (display["expected_value"] * 100).round(1).astype(str) + "%"

        def color_confidence(val):
            if val == "HIGH": return "background-color: #1b5e20; color: white"
            if val == "MEDIUM": return "background-color: #f57f17; color: black"
            if val == "LOW": return "background-color: #b71c1c; color: white"
            return ""

        styled = display.style.applymap(color_confidence, subset=["confidence"] if "confidence" in display.columns else [])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.caption("No active recommendations.")
