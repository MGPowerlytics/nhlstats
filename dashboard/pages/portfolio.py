"""Portfolio Overview — the home page. Portfolio health, P&L, open bets, win rate."""

import streamlit as st
import plotly.express as px
import pandas as pd

from dashboard.data_layer import (
    get_portfolio_summary,
    get_placed_bets,
    get_portfolio_snapshots,
)


def render():
    st.title("Portfolio Overview")

    summary = get_portfolio_summary()

    # KPI cards
    cols = st.columns(4)
    cols[0].metric("Portfolio Value", f"${summary['portfolio_value']:,.2f}",
                   delta=f"${summary['daily_pnl']:+,.2f} today")
    cols[1].metric("Open Bets", summary["open_bets_count"],
                   delta=f"${summary['total_exposure']:,.2f} exposed")
    cols[2].metric("Win Rate", f"{summary['win_rate']:.1%}",
                   help=f"{summary['settled_count']} settled bets")
    cols[3].metric("Total Bets", summary["total_bets"])

    st.divider()

    # Portfolio value chart
    st.subheader("Portfolio Value")
    snapshots = get_portfolio_snapshots(hours=168)
    if not snapshots.empty:
        fig = px.area(
            snapshots, x="timestamp", y="portfolio_value",
            title="Portfolio Value (7 days)",
            labels={"timestamp": "Time", "portfolio_value": "Value ($)"},
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No portfolio snapshot data available.")

    # P&L by sport
    st.subheader("P&L by Sport")
    bets_df = get_placed_bets(limit=500)
    if not bets_df.empty:
        settled = bets_df[bets_df["status"].isin(["WON", "LOST"])].copy()
        if not settled.empty:
            settled["pnl"] = settled.apply(
                lambda r: (r["payout"] - r["stake"]) if r["status"] == "WON" else -r["stake"],
                axis=1,
            )
            sport_pnl = settled.groupby("sport")["pnl"].sum().reset_index()
            sport_pnl = sport_pnl.sort_values("pnl", ascending=True)
            fig = px.bar(
                sport_pnl, x="pnl", y="sport", orientation="h",
                title="Total P&L by Sport",
                labels={"pnl": "P&L ($)", "sport": "Sport"},
                color="pnl",
                color_continuous_scale=["red", "lightgray", "green"],
            )
            st.plotly_chart(fig, use_container_width=True)

    # Recent bets table
    st.subheader("Recent Activity")
    recent = get_placed_bets(limit=50)
    if not recent.empty:
        display_cols = ["placed_at", "sport", "market", "team", "stake", "status",
                        "edge", "elo_prob", "market_prob", "confidence"]
        available = [c for c in display_cols if c in recent.columns]
        display = recent[available].copy()
        if "placed_at" in display.columns:
            display["placed_at"] = display["placed_at"].astype(str).str[:16]
        if "edge" in display.columns:
            display["edge"] = (display["edge"] * 100).round(1).astype(str) + "%"
        if "elo_prob" in display.columns:
            display["elo_prob"] = (display["elo_prob"] * 100).round(1).astype(str) + "%"
        if "market_prob" in display.columns:
            display["market_prob"] = (display["market_prob"] * 100).round(1).astype(str) + "%"

        for idx, row in display.iterrows():
            cols = st.columns([8, 2])
            cols[0].write(
                f"{row.get('placed_at', '')} | {row.get('sport', '')} | "
                f"{row.get('market', '')} | ${row.get('stake', 0):.2f} | "
                f"{row.get('status', '')}"
            )
            bet_id = recent.iloc[idx]["bet_id"]
            if cols[1].button("Details", key=f"detail_{bet_id}"):
                st.session_state["show_bet_detail"] = bet_id
                st.rerun()
    else:
        st.caption("No bets placed yet.")
