"""Calibration — model accuracy, calibration curves, edge-vs-ROI analysis."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from dashboard.data_layer import get_calibration_data


def render():
    st.title("Model Calibration")

    sport_filter = st.selectbox(
        "Sport",
        ["All", "NBA", "NHL", "MLB", "NFL", "NCAAB", "WNCAAB", "TENNIS", "EPL", "Ligue1", "CBA", "Unrivaled"],
    )
    sport = None if sport_filter == "All" else sport_filter

    data = get_calibration_data(sport)
    by_sport = data.get("by_sport", [])
    buckets = data.get("buckets", [])
    bets = data.get("bets", [])

    # By-sport summary
    st.subheader("Performance by Sport")
    if by_sport:
        sport_df = pd.DataFrame(by_sport)
        display = sport_df.copy()
        display["win_rate"] = (display["win_rate"] * 100).round(1).astype(str) + "%"
        display["avg_edge"] = (display["avg_edge"] * 100).round(1).astype(str) + "%"
        display["roi"] = (display["roi"] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True, hide_index=True)

        # ROI by sport bar chart
        fig = px.bar(
            sport_df, x="sport", y="roi",
            title="ROI by Sport",
            labels={"sport": "Sport", "roi": "ROI"},
            color="roi",
            color_continuous_scale=["red", "lightgray", "green"],
        )
        st.plotly_chart(fig, use_container_width=True)

    # Calibration curve
    st.subheader("Calibration Curve")
    if buckets:
        bucket_df = pd.DataFrame(buckets)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[(b["predicted_min"] + b["predicted_max"]) / 2 for b in buckets],
            y=[b["actual_win_rate"] for b in buckets],
            mode="lines+markers",
            name="Actual Win Rate",
        ))
        fig.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1], mode="lines",
            line=dict(dash="dash", color="gray"),
            name="Perfect Calibration",
        ))
        fig.update_layout(
            xaxis_title="Predicted Probability",
            yaxis_title="Actual Win Rate",
            xaxis=dict(range=[0, 1]),
            yaxis=dict(range=[0, 1]),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Edge vs ROI scatter
    st.subheader("Edge vs Actual ROI")
    if bets:
        bets_df = pd.DataFrame(bets)
        bets_df["roi"] = (bets_df["payout"] - bets_df["stake"]) / bets_df["stake"]
        bets_df["result_code"] = bets_df["result"].map({"WON": 1, "LOST": 0})

        fig = px.scatter(
            bets_df, x="edge", y="roi", color="sport",
            title="Edge vs Actual ROI per Bet",
            labels={"edge": "Predicted Edge", "roi": "Actual ROI", "sport": "Sport"},
            opacity=0.6,
        )
        fig.add_hline(y=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No settled bets available for calibration analysis.")
