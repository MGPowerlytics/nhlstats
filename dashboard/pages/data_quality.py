"""Data Quality — system health scores, missing data alerts, odds freshness."""

import streamlit as st
import plotly.express as px
import pandas as pd

from dashboard.data_layer import get_data_quality_report


def render():
    st.title("Data Quality")

    report = get_data_quality_report()
    overall = report.get("overall_health", 0)
    sports = report.get("sports", [])

    # Overall health gauge
    st.metric("Overall Health Score", f"{overall}/100")

    # Health bar chart
    if sports:
        sport_df = pd.DataFrame(sports)
        fig = px.bar(
            sport_df, x="sport", y="health_score",
            title="Health Score by Sport",
            labels={"sport": "Sport", "health_score": "Health Score"},
            color="health_score",
            color_continuous_scale=["red", "yellow", "green"],
            range_color=[0, 100],
        )
        fig.add_hline(y=80, line_dash="dash", line_color="green", annotation_text="Healthy")
        fig.add_hline(y=50, line_dash="dash", line_color="red", annotation_text="Warning")
        st.plotly_chart(fig, use_container_width=True)

    # Per-sport details
    st.subheader("Per-Sport Details")
    for s in sports:
        health = s["health_score"]
        with st.expander(f"{s['sport']} — Health: {health}/100"):
            cols = st.columns(3)
            cols[0].metric("Missing Games", s.get("missing_games", 0))
            cols[1].metric("Stale Elo Ratings", s.get("stale_elo", 0))
            cols[2].metric("Odds Freshness", f"{s.get('odds_freshness_minutes', 'N/A')} min")
            st.caption(f"Last game: {s.get('last_game_date', 'N/A')}")

            issues = s.get("issues", [])
            if issues:
                st.warning("Issues: " + ", ".join(issues))
            else:
                st.success("No issues detected")
