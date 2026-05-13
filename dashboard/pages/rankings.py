"""Rankings — current governed Elo ratings and team comparison tool."""

import streamlit as st
import plotly.express as px
import pandas as pd

from dashboard.data_layer import (
    DashboardDataError,
    get_current_elo_ratings,
    get_elo_history,
)


SPORT_OPTIONS = [
    "NBA",
    "NHL",
    "MLB",
    "NFL",
    "NCAAB",
    "WNCAAB",
    "TENNIS",
    "EPL",
    "LIGUE1",
]
RANKING_DISPLAY_COLUMNS = [
    "rank",
    "sport",
    "entity_type",
    "entity_name",
    "rating",
    "games_played",
    "valid_from",
    "valid_to",
    "created_at",
]


def _state_text(payload: dict[str, str | None]) -> str:
    """Build a compact, sanitized state message from a data-layer payload."""

    parts = [
        payload.get("kind"),
        payload.get("title"),
        payload.get("message"),
        payload.get("action"),
    ]
    return " — ".join(str(part) for part in parts if part)


def _render_state(payload: dict[str, str | None]) -> None:
    """Render an explicit governed empty/error state."""

    message = _state_text(payload)
    if payload.get("severity") == "error":
        st.error(message)
    else:
        st.info(message)


def _empty_rankings_payload(sport: str) -> dict[str, str | None]:
    """Return the fallback no-rankings state when the frame lacks attrs."""

    return {
        "kind": "no_rankings",
        "title": "No rankings",
        "message": f"No governed active ranking rows are available for {sport}.",
        "action": "Run rating ingestion before comparing teams.",
        "severity": "info",
    }


def _display_rankings_table(ratings: pd.DataFrame) -> None:
    """Render governed ranking fields supported by dashboard_rankings_v1."""

    available = [c for c in RANKING_DISPLAY_COLUMNS if c in ratings.columns]
    display = ratings[available].copy()
    st.dataframe(
        display.style.format({"rating": "{:.0f}", "games_played": "{:.0f}"}),
        use_container_width=True,
        hide_index=True,
    )


def render():
    st.title("Elo Rankings")

    sport = st.selectbox("Sport", SPORT_OPTIONS)

    try:
        ratings = get_current_elo_ratings(sport)
    except DashboardDataError as exc:
        _render_state(exc.payload)
        return

    if not ratings.empty:
        st.subheader(f"{sport} Ratings ({len(ratings)} active rows)")
        st.caption("Source: governed dashboard_rankings_v1 active Elo read model.")
        _display_rankings_table(ratings)

        # Rating distribution chart
        fig = px.bar(
            ratings,
            x="entity_name",
            y="rating",
            title=f"{sport} Elo Ratings",
            labels={"entity_name": "Team / Entity", "rating": "Elo Rating"},
            color="rating",
            color_continuous_scale="viridis",
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

        # Team comparison tool
        st.divider()
        st.subheader("Team Comparison")
        teams = ratings["entity_name"].dropna().astype(str).tolist()
        if len(teams) >= 2:
            col_a, col_b = st.columns(2)
            team_a = col_a.selectbox("Team A", teams, key="team_a")
            team_b = col_b.selectbox("Team B", teams, key="team_b", index=1)

            if team_a and team_b and team_a != team_b:
                a_rating = float(
                    ratings[ratings["entity_name"] == team_a]["rating"].iloc[0]
                )
                b_rating = float(
                    ratings[ratings["entity_name"] == team_b]["rating"].iloc[0]
                )
                diff = a_rating - b_rating
                prob_a = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
                prob_b = 1.0 - prob_a

                c1, c2, c3 = st.columns(3)
                c1.metric(team_a, f"{a_rating:.0f}")
                c2.metric(
                    "Head-to-Head Prediction",
                    f"{team_a if prob_a > prob_b else team_b} wins",
                )
                c3.metric(team_b, f"{b_rating:.0f}")
                st.write(f"{team_a}: {prob_a:.1%} | {team_b}: {prob_b:.1%}")

                # Rating history overlay
                hist_a = get_elo_history(team_a, sport, days=30)
                hist_b = get_elo_history(team_b, sport, days=30)
                if not hist_a.empty and not hist_b.empty:
                    combined = pd.concat([hist_a, hist_b])
                    fig = px.line(
                        combined,
                        x="date",
                        y="rating",
                        color="team",
                        title=f"30-Day Rating History: {team_a} vs {team_b}",
                        labels={"date": "Date", "rating": "Rating", "team": "Team"},
                    )
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("At least two active ranking rows are required for comparison.")
    else:
        _render_state(
            ratings.attrs.get("empty_state") or _empty_rankings_payload(sport)
        )
