"""Upcoming Games — next 48 hours with Elo win probabilities per sport."""

import streamlit as st
import pandas as pd

from dashboard.data_layer import (
    DashboardDataError,
    get_upcoming_games,
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

DISPLAY_COLUMNS = [
    "away_team",
    "away_elo_prob",
    "home_team",
    "home_elo_prob",
    "prob_diff",
    "game_date",
    "game_time_et",
]


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


def _format_prob(value: float | None) -> str:
    """Format a probability as a percentage string."""
    if value is None:
        return "N/A"
    return f"{value:.1%}"


def _highlight_diff(value: float | None) -> str:
    """Return a CSS color based on which side is favoured."""
    if value is None:
        return ""
    if value > 0:
        return "color: green"
    if value < 0:
        return "color: red"
    return "color: gray"


def render() -> None:
    st.title("Upcoming Games")
    st.caption("Games starting in the next 48 hours with Elo win probabilities.")

    sport = st.selectbox("Sport", SPORT_OPTIONS)

    try:
        games = get_upcoming_games(sport)
    except DashboardDataError as exc:
        _render_state(exc.payload)
        return

    if games.empty:
        _render_state(
            games.attrs.get("empty_state")
            or {
                "kind": "no_upcoming_games",
                "title": "No upcoming games",
                "message": f"No upcoming games are scheduled for {sport}.",
                "action": "Check back later or select a different sport.",
                "severity": "info",
            }
        )
        return

    st.subheader(f"{sport} — {len(games)} game{'s' if len(games) != 1 else ''}")
    st.caption("Source: unified_games joined with current elo_ratings.")

    # Build display dataframe with formatted columns
    display = games[DISPLAY_COLUMNS].copy()
    display = display.rename(
        columns={
            "away_team": "Away Team",
            "away_elo_prob": "Away Elo Prob",
            "home_team": "Home Team",
            "home_elo_prob": "Home Elo Prob",
            "prob_diff": "Prob Diff",
            "game_date": "Game Date",
            "game_time_et": "Game Time (ET)",
        }
    )

    # Format probabilities and apply conditional styling
    fmt_cols = ["Away Elo Prob", "Home Elo Prob", "Prob Diff"]

    styled = display.style.format(
        {col: _format_prob for col in fmt_cols},
        na_rep="N/A",
    ).map(
        lambda val: _highlight_diff(val) if pd.notna(val) else "",
        subset=["Prob Diff"],
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Away Elo Prob": st.column_config.NumberColumn(width="small"),
            "Home Elo Prob": st.column_config.NumberColumn(width="small"),
            "Prob Diff": st.column_config.NumberColumn(width="small"),
        },
    )

    # Probability bar chart
    if len(games) > 0:
        st.divider()
        chart_data = games.copy()
        chart_data["matchup"] = chart_data["away_team"] + " @ " + chart_data["home_team"]
        chart_data = chart_data.sort_values("commence_time_utc")

        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                y=chart_data["matchup"],
                x=chart_data["home_elo_prob"],
                name="Home Win Prob",
                orientation="h",
                marker_color="steelblue",
                text=chart_data["home_elo_prob"].apply(
                    lambda v: f"{v:.0%}" if pd.notna(v) else "N/A"
                ),
                textposition="inside",
            )
        )
        fig.add_trace(
            go.Bar(
                y=chart_data["matchup"],
                x=chart_data["away_elo_prob"],
                name="Away Win Prob",
                orientation="h",
                marker_color="lightcoral",
                text=chart_data["away_elo_prob"].apply(
                    lambda v: f"{v:.0%}" if pd.notna(v) else "N/A"
                ),
                textposition="inside",
            )
        )
        fig.update_layout(
            barmode="stack",
            title=f"{sport} Upcoming Games — Elo Win Probabilities",
            xaxis=dict(title="Win Probability", tickformat=".0%", range=[0, 1]),
            yaxis=dict(title=""),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=max(300, len(chart_data) * 50),
        )
        st.plotly_chart(fig, use_container_width=True)
