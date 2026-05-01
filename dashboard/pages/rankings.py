"""Rankings — current Elo ratings, team comparison tool."""

import streamlit as st
import plotly.express as px
import pandas as pd

from dashboard.data_layer import get_current_elo_ratings, get_elo_history


def render():
    st.title("Elo Rankings")

    sport = st.selectbox(
        "Sport",
        ["NBA", "NHL", "MLB", "NFL", "NCAAB", "WNCAAB", "TENNIS", "EPL", "Ligue1", "CBA", "Unrivaled"],
    )

    ratings = get_current_elo_ratings(sport)

    if not ratings.empty:
        st.subheader(f"{sport} Ratings ({len(ratings)} teams)")
        display_cols = ["rank", "team", "rating", "last_updated"]
        available = [c for c in display_cols if c in ratings.columns]
        st.dataframe(
            ratings[available].style.format({"rating": "{:.0f}"}),
            use_container_width=True, hide_index=True,
        )

        # Rating distribution chart
        fig = px.bar(
            ratings, x="team", y="rating",
            title=f"{sport} Elo Ratings",
            labels={"team": "Team", "rating": "Elo Rating"},
            color="rating",
            color_continuous_scale="viridis",
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

        # Team comparison tool
        st.divider()
        st.subheader("Team Comparison")
        teams = ratings["team"].tolist()
        col_a, col_b = st.columns(2)
        team_a = col_a.selectbox("Team A", teams, key="team_a")
        team_b = col_b.selectbox("Team B", teams, key="team_b",
                                 index=min(1, len(teams) - 1))

        if team_a and team_b and team_a != team_b:
            a_rating = float(ratings[ratings["team"] == team_a]["rating"].iloc[0])
            b_rating = float(ratings[ratings["team"] == team_b]["rating"].iloc[0])
            diff = a_rating - b_rating
            prob_a = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
            prob_b = 1.0 - prob_a

            c1, c2, c3 = st.columns(3)
            c1.metric(team_a, f"{a_rating:.0f}")
            c2.metric("Head-to-Head Prediction",
                      f"{team_a if prob_a > prob_b else team_b} wins")
            c3.metric(team_b, f"{b_rating:.0f}")
            st.write(f"{team_a}: {prob_a:.1%} | {team_b}: {prob_b:.1%}")

            # Rating history overlay
            hist_a = get_elo_history(team_a, sport, days=30)
            hist_b = get_elo_history(team_b, sport, days=30)
            if not hist_a.empty and not hist_b.empty:
                combined = pd.concat([hist_a, hist_b])
                fig = px.line(
                    combined, x="date", y="rating", color="team",
                    title=f"30-Day Rating History: {team_a} vs {team_b}",
                    labels={"date": "Date", "rating": "Rating", "team": "Team"},
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"No Elo ratings found for {sport}.")
