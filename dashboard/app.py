"""NHLStats Dashboard — multi-sport betting analytics.

Entry point for Streamlit. Handles sidebar navigation, auto-refresh,
and delegates to page modules in dashboard/pages/.
"""

import sys
import os
import time

# Ensure plugins and dashboard are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))

import streamlit as st

st.set_page_config(
    page_title="NHLStats Dashboard",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.data_layer import bust_cache

# Per-page metadata: (module_path, refresh_seconds)
PAGE_MAP: dict[str, tuple[str, int]] = {
    "Portfolio":             ("dashboard.pages.portfolio",            30),
    "Live Markets":          ("dashboard.pages.live_markets",         30),
    "Tennis Predictions":    ("dashboard.pages.tennis_predictions",    30),
    "Tennis Model Health":   ("dashboard.pages.tennis_model_health", 300),
    "Upcoming Games":        ("dashboard.pages.upcoming_games",      300),
    "Rankings":              ("dashboard.pages.rankings",            300),
    "Calibration":           ("dashboard.pages.calibration",        3600),
    "Data Quality":          ("dashboard.pages.data_quality",        300),
}

PAGE_REFRESH: dict[str, int] = {
    name: seconds for name, (_, seconds) in PAGE_MAP.items()
}


def render_sidebar() -> str:
    """Render sidebar navigation. Returns the selected page name."""
    with st.sidebar:
        st.title("🏒 NHLStats")
        st.caption("Multi-Sport Betting Analytics")

        page = st.radio(
            "Navigation",
            [
                "Portfolio",
                "Live Markets",
                "Tennis Predictions",
                "Tennis Model Health",
                "Upcoming Games",
                "Rankings",
                "Calibration",
                "Data Quality",
            ],
            index=0,
        )

        st.divider()

        # Refresh controls
        refresh_seconds = PAGE_REFRESH.get(page, 0)
        st.caption(
            f"Auto-refresh: {refresh_seconds}s"
            if refresh_seconds
            else "Auto-refresh: off"
        )

        if st.button("🔄 Refresh Now", use_container_width=True):
            bust_cache()
            st.rerun()

        st.divider()
        st.caption("Data freshness indicators:")
        st.caption("🟢 Fresh   🟡 Stale   🔴 Outdated")

    return page


def auto_refresh_loop(page: str):
    """Sleep and trigger rerun at the page's refresh interval."""
    if os.getenv("DASHBOARD_DISABLE_AUTO_REFRESH"):
        return

    seconds = PAGE_REFRESH.get(page, 0)
    if seconds <= 0:
        return  # manual-only pages

    # Show a countdown placeholder at the bottom of the sidebar
    placeholder = st.sidebar.empty()
    for remaining in range(seconds, 0, -1):
        placeholder.caption(f"Next refresh in {remaining}s...")
        time.sleep(1)

    bust_cache()
    placeholder.empty()
    st.rerun()


def main():
    page = render_sidebar()

    # Lazy-load the selected page module via dictionary dispatch
    module_path = PAGE_MAP.get(page, PAGE_MAP["Portfolio"])[0]
    render = __import__(module_path, fromlist=["render"]).render
    render()

    # Handle bet detail drill-down via query params
    query_params = st.query_params
    if "bet_id" in query_params:
        from dashboard.pages.bet_detail import render_bet_detail

        render_bet_detail(query_params["bet_id"])
    # Check session state for bet detail navigation from other pages
    if st.session_state.get("show_bet_detail"):
        bet_id = st.session_state["show_bet_detail"]
        from dashboard.pages.bet_detail import render_bet_detail

        render_bet_detail(bet_id)

    auto_refresh_loop(page)


if __name__ == "__main__":
    main()
