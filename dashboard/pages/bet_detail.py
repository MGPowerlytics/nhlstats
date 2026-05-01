"""Bet Detail drill-down — every number that went into a bet placement decision."""

import streamlit as st
import plotly.express as px
import pandas as pd

from dashboard.data_layer import get_bet_detail


def render_bet_detail(bet_id: str):
    """Render the full bet traceability view for a given bet_id."""
    st.header(f"Bet Detail: {bet_id}")

    try:
        detail = get_bet_detail(bet_id)
    except ValueError:
        st.error(f"Bet not found: {bet_id}")
        if st.button("Back"):
            st.session_state["show_bet_detail"] = None
            st.rerun()
        return

    bet = detail["bet"]
    odds = detail.get("odds", [])
    elo_snapshot = detail.get("elo_snapshot", {})
    elo_history = detail.get("elo_history", [])
    recent_form = detail.get("recent_form", {})

    # Back button
    if st.button("← Back"):
        st.session_state["show_bet_detail"] = None
        st.rerun()

    # --- Header bar ---
    cols = st.columns(5)
    cols[0].metric("Sport", bet.get("sport", "N/A"))
    cols[1].metric("Market", bet.get("market", "N/A"))
    cols[2].metric("Placed", str(bet.get("placed_at", ""))[:16])
    status = bet.get("status", "PENDING")
    if status == "WON":
        payout_display = f"+${bet.get('payout', 0) - bet.get('stake', 0):.2f}"
        cols[3].metric("Result", status, delta=payout_display, delta_color="normal")
    elif status == "LOST":
        cols[3].metric("Result", status, delta=f"-${bet.get('stake', 0):.2f}", delta_color="inverse")
    else:
        cols[3].metric("Result", status)
    cols[4].metric("Stake", f"${bet.get('stake', 0):.2f}")

    st.divider()

    # --- The Decision ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("The Decision")
        edge = bet.get("edge", 0) or 0
        elo_prob = bet.get("elo_prob", 0) or 0
        market_prob = bet.get("market_prob", 0) or 0
        st.metric("Elo Probability", f"{elo_prob:.1%}")
        st.metric("Market Implied Probability", f"{market_prob:.1%}")
        st.metric("Edge", f"{edge:.1%}", delta=f"{edge:.1%}")
        st.metric("Confidence", bet.get("confidence", "N/A"))
        st.metric("Kelly Fraction", f"{bet.get('kelly_fraction', 0):.2f}")
        st.metric("Stake", f"${bet.get('stake', 0):.2f}")

    with col_b:
        st.subheader("Elo Rating Snapshot")
        st.metric(elo_snapshot.get("team_a_name", "Team A"),
                  f"{elo_snapshot.get('team_a_rating', 0):.0f}")
        st.metric(elo_snapshot.get("team_b_name", "Team B"),
                  f"{elo_snapshot.get('team_b_rating', 0):.0f}")
        st.caption(f"Rating diff: {elo_snapshot.get('rating_diff', 0):+.0f} | "
                   f"Home adv: {elo_snapshot.get('home_advantage', 0):+.0f} | "
                   f"Effective: {elo_snapshot.get('effective_diff', 0):+.0f}")

    st.divider()

    # --- Odds Comparison ---
    st.subheader("Odds Comparison (at placement time)")
    if odds:
        odds_df = pd.DataFrame(odds)
        display_df = odds_df.rename(columns={
            "source": "Source", "price": "Price", "implied_prob": "Implied Prob",
            "timestamp": "Timestamp",
        })
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No odds data available for this bet.")

    st.divider()

    # --- Elo History Chart ---
    st.subheader("Elo Rating History (30 days before bet)")
    if elo_history:
        hist_df = pd.DataFrame(elo_history)
        fig = px.line(
            hist_df, x="date", y="rating", color="team",
            title="Elo Rating Trend",
            labels={"date": "Date", "rating": "Elo Rating", "team": "Team"},
        )
        placed = bet.get("placed_at", "")
        if placed:
            fig.add_vline(x=placed, line_dash="dash", line_color="red",
                          annotation_text="Bet Placed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No Elo history available.")

    # --- Recent Form ---
    st.subheader("Recent Form")
    form_a, form_b = st.columns(2)

    with form_a:
        team_a_data = recent_form.get("team_a", {})
        st.write(f"**{team_a_data.get('team', 'Team A')}** ({team_a_data.get('record', '0-0')})")
        games_a = team_a_data.get("games", [])
        if games_a:
            for g in games_a:
                icon = "🟢" if g["result"] == "W" else ("🔴" if g["result"] == "L" else "⚪")
                st.write(f"{icon} {g['result']} vs {g['opponent']} {g['score']}")

    with form_b:
        team_b_data = recent_form.get("team_b", {})
        st.write(f"**{team_b_data.get('team', 'Team B')}** ({team_b_data.get('record', '0-0')})")
        games_b = team_b_data.get("games", [])
        if games_b:
            for g in games_b:
                icon = "🟢" if g["result"] == "W" else ("🔴" if g["result"] == "L" else "⚪")
                st.write(f"{icon} {g['result']} vs {g['opponent']} {g['score']}")
