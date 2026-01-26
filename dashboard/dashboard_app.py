import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import sys
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Add plugins to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../plugins"))

# Import Elo classes dynamically
try:
    from plugins.elo import MLBEloRating
except ImportError:
    MLBEloRating = None

try:
    from plugins.elo import NHLEloRating
except ImportError:
    NHLEloRating = None

try:
    from plugins.elo import NFLEloRating
except ImportError:
    NFLEloRating = None

try:
    from plugins.elo import NBAEloRating
except ImportError:
    NBAEloRating = None

try:
    from plugins.elo import EPLEloRating
except ImportError:
    EPLEloRating = None

try:
    from plugins.elo import TennisEloRating
except ImportError:
    TennisEloRating = None

try:
    from plugins.elo import NCAABEloRating
except ImportError:
    NCAABEloRating = None

try:
    from plugins.elo import Ligue1EloRating
except ImportError:
    Ligue1EloRating = None

try:
    from plugins.elo import WNCAABEloRating
except ImportError:
    WNCAABEloRating = None

# Import Glicko-2 classes
try:
    from glicko2_rating import (
        NBAGlicko2Rating,
        NHLGlicko2Rating,
        MLBGlicko2Rating,
        NFLGlicko2Rating,
    )
except ImportError:
    NBAGlicko2Rating = None
    NHLGlicko2Rating = None
    MLBGlicko2Rating = None
    NFLGlicko2Rating = None

from db_manager import default_db

# --- Configuration ---
st.set_page_config(
    page_title="Sports Betting Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Helper Functions ---


@st.cache_data
def load_data(league):
    """Load game data from the unified_games table in PostgreSQL."""
    # Map dashboard league names to database sport values
    sport_map = {
        "NHL": "NHL",
        "MLB": "MLB",
        "NFL": "NFL",
        "NBA": "NBA",
        "EPL": "EPL",
        "Tennis": "TENNIS",
        "NCAAB": "NCAAB",
        "WNCAAB": "WNCAAB",
        "Ligue1": "LIGUE1",
    }

    sport = sport_map.get(league)
    if not sport:
        return pd.DataFrame()

    query = """
        SELECT
            game_date,
            season,
            home_team_name as home_team,
            away_team_name as away_team,
            home_score,
            away_score,
            CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM unified_games
        WHERE sport = :sport
          AND status IN ('FINAL', 'OFF', 'Final')
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        ORDER BY game_date
    """

    # Special handling for Tennis
    if league == "Tennis":
        query = """
            SELECT
                game_date,
                season,
                home_team_name as home_team,
                away_team_name as away_team,
                1 as home_win,
                0 as home_score,
                0 as away_score
            FROM unified_games
            WHERE sport = 'TENNIS'
            ORDER BY game_date
        """

    try:
        games_df = default_db.fetch_df(query, {"sport": sport})
        if not games_df.empty:
            games_df["game_date"] = pd.to_datetime(games_df["game_date"])
        return games_df
    except Exception as e:
        st.error(f"Error loading {league} data: {e}")
        return pd.DataFrame()


@st.cache_data
def run_elo_simulation(games_df, league, k_factor, home_adv):
    """Run Elo simulation for the selected league."""
    if games_df.empty:
        return games_df

    # Tennis Specific: Randomize winner/loser positions to avoid bias
    if league == "Tennis":
        np.random.seed(42)
        swap_mask = np.random.random(len(games_df)) > 0.5
        games_df = games_df.copy()

        real_winners = games_df["home_team"].copy()
        real_losers = games_df["away_team"].copy()

        games_df.loc[swap_mask, "home_team"] = real_losers[swap_mask]
        games_df.loc[swap_mask, "away_team"] = real_winners[swap_mask]
        games_df.loc[swap_mask, "home_win"] = 0

    # Initialize Elo system
    if league == "MLB" and MLBEloRating:
        elo = MLBEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == "NHL" and NHLEloRating:
        elo = NHLEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == "NFL" and NFLEloRating:
        elo = NFLEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == "NBA" and NBAEloRating:
        elo = NBAEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == "EPL" and EPLEloRating:
        elo = EPLEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == "Tennis" and TennisEloRating:
        elo = TennisEloRating(k_factor=k_factor)
    elif league == "NCAAB" and NCAABEloRating:
        elo = NCAABEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == "WNCAAB" and WNCAABEloRating:
        elo = WNCAABEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == "Ligue1" and Ligue1EloRating:
        elo = Ligue1EloRating(k_factor=k_factor, home_advantage=home_adv)
    else:
        return games_df

    probs = []

    # Process games
    for _, game in games_df.iterrows():
        # Predict
        if league == "NCAAB":
            prob = elo.predict(
                game["home_team"],
                game["away_team"],
                is_neutral=game.get("is_neutral", False),
            )
        elif league == "WNCAAB":
            prob = elo.predict(
                game["home_team"],
                game["away_team"],
                is_neutral=game.get("neutral_site", False),
            )
        else:
            prob = elo.predict(game["home_team"], game["away_team"])
        probs.append(prob)

        # Update
        if league == "NBA":
            elo.update(game["home_team"], game["away_team"], game["home_win"])
        elif league == "NHL":
            elo.update(game["home_team"], game["away_team"], game["home_win"])
        elif league == "NCAAB":
            elo.update(
                game["home_team"],
                game["away_team"],
                game["home_win"],
                is_neutral=game.get("is_neutral", False),
            )
        elif league == "WNCAAB":
            elo.update(
                game["home_team"],
                game["away_team"],
                game["home_win"],
                is_neutral=game.get("neutral_site", False),
            )
        elif league == "EPL":
            elo.update(
                game["home_team"],
                game["away_team"],
                "H" if game["home_win"] == 1 else "A",
            )
        elif league == "Ligue1":
            elo.update(
                game["home_team"],
                game["away_team"],
                "H" if game["home_win"] == 1 else "A",
            )
        elif league == "Tennis":
            winner = game["home_team"] if game["home_win"] == 1 else game["away_team"]
            loser = game["away_team"] if game["home_win"] == 1 else game["home_team"]
            elo.update(winner, loser)
        elif league == "MLB" or league == "NFL":
            elo.update(
                game["home_team"],
                game["away_team"],
                game["home_score"],
                game["away_score"],
            )

    games_df["elo_prob"] = probs
    return games_df


@st.cache_data
def run_glicko2_simulation(games_df, league, tau=0.5, home_adv=100):
    """Run Glicko-2 simulation for the selected league."""
    if games_df.empty:
        return games_df

    # Initialize Glicko-2 system
    if league == "MLB" and MLBGlicko2Rating:
        glicko = MLBGlicko2Rating()
    elif league == "NHL" and NHLGlicko2Rating:
        glicko = NHLGlicko2Rating()
    elif league == "NFL" and NFLGlicko2Rating:
        glicko = NFLGlicko2Rating()
    elif league == "NBA" and NBAGlicko2Rating:
        glicko = NBAGlicko2Rating()
    else:
        return games_df

    glicko.home_advantage = home_adv
    glicko.TAU = tau
    probs = []

    for _, game in games_df.iterrows():
        prob = glicko.predict(game["home_team"], game["away_team"])
        probs.append(prob)
        glicko.update(game["home_team"], game["away_team"], game["home_win"])

    games_df["glicko2_prob"] = probs
    return games_df


def calculate_deciles(df):
    """Calculate lift/gain metrics by decile."""
    if df.empty or "elo_prob" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    try:
        df["decile"] = (
            pd.qcut(df["elo_prob"], q=10, labels=False, duplicates="drop") + 1
        )
    except ValueError:
        df["decile"] = pd.cut(df["elo_prob"], bins=10, labels=False) + 1

    baseline = df["home_win"].mean()
    results = []

    for decile in sorted(df["decile"].unique()):
        subset = df[df["decile"] == decile]
        games = len(subset)
        wins = subset["home_win"].sum()
        win_rate = wins / games if games > 0 else 0
        avg_prob = subset["elo_prob"].mean()
        lift = win_rate / baseline if baseline > 0 else 0
        roi_110 = ((win_rate * 0.909) - (1 - win_rate)) * 100

        # -110 odds equivalent probability (breakeven point)
        odds_110_prob = 110 / (110 + 100)  # 52.38%

        # ROI using -110 odds: payout = 0.909 per dollar bet
        roi_110 = ((win_rate * 0.909) - (1 - win_rate)) * 100

        results.append(
            {
                "Decile": decile,
                "Games": games,
                "Wins": wins,
                "Win Rate": win_rate,
                "Avg Prob": avg_prob,
                "Kalshi Prob": f"{odds_110_prob:.1%}",
                "Lift": lift,
                "ROI (-110)": f"{roi_110:.1f}%",
                "Baseline": baseline,
                "Min Prob": subset["elo_prob"].min(),
                "Max Prob": subset["elo_prob"].max(),
            }
        )

    return pd.DataFrame(results)


def calculate_decile_probability_roi_matrix(
    df, kalshi_prices=[0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
):
    """Calculate ROI matrix for deciles vs Kalshi price points.

    Shows what ROI would be for games in each decile if Kalshi priced them
    at different probability levels (contract prices).

    Args:
        df: DataFrame with 'elo_prob' and 'home_win' columns
        kalshi_prices: List of hypothetical Kalshi contract prices (probabilities)

    Returns:
        DataFrame with deciles as rows and Kalshi prices as columns, ROI values in cells
    """
    if df.empty or "elo_prob" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    try:
        df["decile"] = (
            pd.qcut(df["elo_prob"], q=10, labels=False, duplicates="drop") + 1
        )
    except ValueError:
        df["decile"] = pd.cut(df["elo_prob"], bins=10, labels=False) + 1

    results = []

    for decile in sorted(df["decile"].unique()):
        decile_data = df[df["decile"] == decile]
        games = len(decile_data)

        if games == 0:
            continue

        wins = decile_data["home_win"].sum()
        win_rate = wins / games

        row_data = {"Decile": decile}

        for kalshi_price in kalshi_prices:
            # ROI calculation: if we pay kalshi_price for a contract worth $1 on win
            # Expected return = win_rate * 1 + (1 - win_rate) * 0 = win_rate
            # Cost = kalshi_price
            # ROI = (return - cost) / cost = (win_rate / kalshi_price) - 1
            roi = ((win_rate / kalshi_price) - 1) * 100 if kalshi_price > 0 else 0

            row_data[f"{int(kalshi_price * 100)}¢"] = f"{roi:+.1f}%"

        results.append(row_data)

    # Convert to DataFrame
    matrix_df = pd.DataFrame(results)
    matrix_df = matrix_df.set_index("Decile")

    return matrix_df


def calculate_cumulative_gain(df):
    """Calculate cumulative gain curve data."""
    if df.empty:
        return pd.DataFrame()

    df_sorted = df.sort_values("elo_prob", ascending=False)
    df_sorted["cumulative_games"] = np.arange(1, len(df_sorted) + 1)
    df_sorted["cumulative_wins"] = df_sorted["home_win"].cumsum()

    df_sorted["pct_games"] = df_sorted["cumulative_games"] / len(df_sorted)
    df_sorted["pct_wins_captured"] = (
        df_sorted["cumulative_wins"] / df_sorted["home_win"].sum()
    )

    if len(df_sorted) > 1000:
        return df_sorted.iloc[:: int(len(df_sorted) / 1000)]
    return df_sorted


# --- Betting Performance Logic ---


@st.cache_data
def _load_betting_results_from_db() -> pd.DataFrame:
    if not default_db.table_exists("placed_bets"):
        return pd.DataFrame()
    return default_db.fetch_df(
        """
        SELECT *
        FROM placed_bets
        ORDER BY placed_date DESC, created_at DESC
        """
    )


@st.cache_data
def _load_portfolio_snapshots(hours_back: int = 7 * 24) -> pd.DataFrame:
    try:
        from portfolio_snapshots import load_snapshots_since
    except Exception:
        return pd.DataFrame()

    since_utc = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)
    return load_snapshots_since(since_utc=since_utc)


def betting_performance_page_v2():
    """Enhanced betting performance page (Postgres + portfolio snapshots)."""
    st.title("🎰 Betting Performance Tracker")
    eastern = ZoneInfo("America/New_York")

    # Sync button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Sync from Kalshi"):
            with st.spinner("Syncing bets from Kalshi API..."):
                import subprocess

                result = subprocess.run(
                    ["python3", "plugins/bet_tracker.py"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    st.success("✅ Synced successfully!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Error: {result.stderr}")

    betting_df = _load_betting_results_from_db()
    if betting_df.empty:
        st.warning(
            "No betting data available. Click 'Sync from Kalshi' to load your bets."
        )
        return

    # Portfolio value time series
    snapshots_df = _load_portfolio_snapshots()
    latest_portfolio_value = None
    latest_snapshot_time_et = None
    if not snapshots_df.empty:
        snapshots_df["snapshot_hour_utc"] = pd.to_datetime(
            snapshots_df["snapshot_hour_utc"], utc=True
        )
        last_row = snapshots_df.iloc[-1]
        latest_portfolio_value = float(last_row.get("portfolio_value_dollars", 0.0))
        latest_snapshot_time_et = last_row["snapshot_hour_utc"].tz_convert(eastern)

    open_bets_df = (
        betting_df[betting_df["status"] == "open"]
        if "status" in betting_df.columns
        else betting_df.iloc[0:0]
    )
    open_games = (
        int(open_bets_df["ticker"].nunique()) if "ticker" in open_bets_df.columns else 0
    )

    # Metrics
    col1, col2 = st.columns(2)
    with col1:
        if latest_portfolio_value is None:
            st.metric("Portfolio Value", "(no snapshots)")
        else:
            suffix = (
                f"as of {latest_snapshot_time_et.strftime('%Y-%m-%d %I:%M %p ET')}"
                if latest_snapshot_time_et
                else ""
            )
            st.metric("Portfolio Value", f"${latest_portfolio_value:,.2f}", help=suffix)
    with col2:
        st.metric("Open Games", open_games)

    if not snapshots_df.empty:
        plot_df = snapshots_df.copy()
        plot_df["snapshot_hour_et"] = plot_df["snapshot_hour_utc"].dt.tz_convert(
            eastern
        )
        fig = px.line(
            plot_df,
            x="snapshot_hour_et",
            y="portfolio_value_dollars",
            title="Hourly Portfolio Value (ET)",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Filters
    st.subheader("Filters")
    f1, f2, f3 = st.columns(3)
    with f1:
        sports = ["All"] + sorted(betting_df["sport"].dropna().unique().tolist())
        selected_sport = st.selectbox("Sport", sports, key="sport_filter_v2_db")
    with f2:
        dates = ["All"] + sorted(
            betting_df["placed_date"].dropna().unique().tolist(), reverse=True
        )
        selected_date = st.selectbox("Date", dates, key="date_filter_v2_db")
    with f3:
        statuses = ["All"] + sorted(betting_df["status"].dropna().unique().tolist())
        selected_status = st.selectbox("Status", statuses, key="status_filter_v2_db")

    filtered_df = betting_df.copy()
    if selected_sport != "All":
        filtered_df = filtered_df[filtered_df["sport"] == selected_sport]
    if selected_date != "All":
        filtered_df = filtered_df[filtered_df["placed_date"] == selected_date]
    if selected_status != "All":
        filtered_df = filtered_df[filtered_df["status"] == selected_status]

    tab1, tab2 = st.tabs(["📊 Overview", "📋 All Bets"])
    with tab1:
        wins = len(betting_df[betting_df["status"] == "won"])
        losses = len(betting_df[betting_df["status"] == "lost"])
        open_bets = len(betting_df[betting_df["status"] == "open"])
        wl_data = pd.DataFrame(
            {"Status": ["Won", "Lost", "Open"], "Count": [wins, losses, open_bets]}
        )
        fig = px.pie(
            wl_data,
            values="Count",
            names="Status",
            title="Bet Outcomes",
            color="Status",
            color_discrete_map={"Won": "green", "Lost": "red", "Open": "gray"},
        )
        st.plotly_chart(fig, use_container_width=True)
    with tab2:
        st.dataframe(
            filtered_df.sort_values("placed_date", ascending=False),
            use_container_width=True,
            height=600,
        )


def financial_performance_page():
    """Financial performance dashboard with P&L analysis."""
    st.title("💰 Financial Performance")

    # Load betting data
    betting_df = _load_betting_results_from_db()
    if betting_df.empty:
        st.warning("No betting data available.")
        return

    # Calculate P&L metrics
    settled_bets = betting_df[betting_df["status"].isin(["won", "lost"])].copy()

    if settled_bets.empty:
        st.info("No settled bets to analyze.")
        return

    # Use settlement date (updated_at) instead of placed_date for P&L tracking
    # This shows when profits/losses actually occurred, not when bets were placed
    settled_bets["date"] = pd.to_datetime(settled_bets["updated_at"]).dt.date
    daily_pl = settled_bets.groupby("date")["profit_dollars"].sum().reset_index()
    daily_pl["cumulative_pl"] = daily_pl["profit_dollars"].cumsum()

    # Weekly P&L (by settlement date)
    settled_bets["week"] = (
        pd.to_datetime(settled_bets["updated_at"]).dt.to_period("W").astype(str)
    )
    weekly_pl = settled_bets.groupby("week")["profit_dollars"].sum().reset_index()
    weekly_pl["cumulative_pl"] = weekly_pl["profit_dollars"].cumsum()

    # Monthly P&L (by settlement date)
    settled_bets["month"] = (
        pd.to_datetime(settled_bets["updated_at"]).dt.to_period("M").astype(str)
    )
    monthly_pl = settled_bets.groupby("month")["profit_dollars"].sum().reset_index()
    monthly_pl["cumulative_pl"] = monthly_pl["profit_dollars"].cumsum()

    # ROI by sport
    sport_pl = (
        settled_bets.groupby("sport")
        .agg({"profit_dollars": "sum", "cost_dollars": "sum", "contracts": "sum"})
        .reset_index()
    )
    sport_pl["roi"] = (sport_pl["profit_dollars"] / sport_pl["cost_dollars"]) * 100
    sport_pl["win_rate"] = (
        settled_bets[settled_bets["status"] == "won"].groupby("sport").size()
        / settled_bets.groupby("sport").size()
        * 100
    )

    # Overall metrics
    total_invested = settled_bets["cost_dollars"].sum()
    total_profit = settled_bets["profit_dollars"].sum()
    total_roi = (total_profit / total_invested) * 100 if total_invested > 0 else 0
    win_rate = (
        len(settled_bets[settled_bets["status"] == "won"]) / len(settled_bets) * 100
    )

    # Calculate portfolio value: cash balance + open positions value
    # Portfolio Value = what user sees in Kalshi = cash + market value of open bets
    try:
        # Get cash balance from latest snapshot
        cash_df = default_db.fetch_df(
            """
            SELECT
                ROUND(balance_dollars::numeric, 2) as cash_balance,
                snapshot_hour_utc
            FROM portfolio_value_snapshots
            ORDER BY snapshot_hour_utc DESC
            LIMIT 1
        """
        )

        # Get value of open positions (capital tied up in bets)
        open_bets_df = default_db.fetch_df(
            """
            SELECT
                ROUND(SUM(cost_dollars)::numeric, 2) as open_positions_value
            FROM placed_bets
            WHERE status = 'open'
        """
        )

        if not cash_df.empty:
            cash_balance = float(cash_df.iloc[0]["cash_balance"])
            snapshot_time = cash_df.iloc[0]["snapshot_hour_utc"]
            if isinstance(snapshot_time, str):
                from datetime import datetime

                snapshot_time = datetime.fromisoformat(snapshot_time)
            balance_timestamp = (
                snapshot_time.strftime("%Y-%m-%d %I:%M %p")
                if snapshot_time
                else "unknown"
            )

            # Calculate portfolio value
            open_value = (
                float(open_bets_df.iloc[0]["open_positions_value"])
                if not open_bets_df.empty
                and open_bets_df.iloc[0]["open_positions_value"]
                else 0.0
            )
            portfolio_value = cash_balance + open_value

            # For display
            kalshi_balance = portfolio_value
            balance_help = f"Portfolio value as of {balance_timestamp}: ${cash_balance:.2f} cash + ${open_value:.2f} in open bets"
        else:
            kalshi_balance = None
            balance_timestamp = None
            balance_help = None
    except Exception as e:
        kalshi_balance = None
        balance_timestamp = None
        balance_help = f"Error calculating balance: {e}"

    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if kalshi_balance is not None:
            st.metric(
                "Portfolio Value",
                f"${kalshi_balance:,.2f}",
                help=balance_help,
            )
        else:
            st.metric(
                "Total Invested",
                f"${total_invested:,.2f}",
                help="Sum of all bet costs (portfolio snapshot unavailable)",
            )
    with col2:
        st.metric("Total P&L", f"${total_profit:,.2f}", delta=f"{total_roi:+.1f}%")
    with col3:
        st.metric("Win Rate", f"{win_rate:.1f}%")
    with col4:
        st.metric("Total Bets", len(settled_bets))

    # P&L Time Series
    st.subheader("Profit & Loss Over Time (by Settlement Date)")
    st.caption(
        "📊 Charts show when bets were settled/paid out, not when they were placed"
    )
    tab1, tab2, tab3 = st.tabs(["Daily", "Weekly", "Monthly"])

    with tab1:
        fig = px.line(
            daily_pl, x="date", y="cumulative_pl", title="Daily Cumulative P&L"
        )
        fig.add_bar(x=daily_pl["date"], y=daily_pl["profit_dollars"], name="Daily P&L")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig = px.line(
            weekly_pl, x="week", y="cumulative_pl", title="Weekly Cumulative P&L"
        )
        fig.add_bar(
            x=weekly_pl["week"], y=weekly_pl["profit_dollars"], name="Weekly P&L"
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        fig = px.line(
            monthly_pl, x="month", y="cumulative_pl", title="Monthly Cumulative P&L"
        )
        fig.add_bar(
            x=monthly_pl["month"], y=monthly_pl["profit_dollars"], name="Monthly P&L"
        )
        st.plotly_chart(fig, use_container_width=True)

    # ROI by Sport
    st.subheader("Performance by Sport")
    fig = px.bar(
        sport_pl,
        x="sport",
        y="roi",
        title="ROI by Sport (%)",
        color="roi",
        color_continuous_scale="RdYlGn",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Sport details table
    st.subheader("Sport Performance Details")
    sport_display = sport_pl[
        ["sport", "profit_dollars", "cost_dollars", "roi", "win_rate", "contracts"]
    ].copy()
    sport_display.columns = [
        "Sport",
        "Profit ($)",
        "Cost ($)",
        "ROI (%)",
        "Win Rate (%)",
        "Total Contracts",
    ]
    sport_display = sport_display.round(2)
    st.dataframe(sport_display, use_container_width=True)


def data_quality_page():
    """Data quality monitoring dashboard."""
    st.title("🔍 Data Quality Dashboard")

    # Import validation functions
    try:
        from data_validation import (
            validate_nhl_data,
            validate_mlb_data,
            validate_nfl_data,
        )
    except ImportError:
        st.error("Data validation module not available.")
        return

    # Run validations for each sport
    sports = ["nhl", "mlb", "nfl"]
    validation_functions = {
        "nhl": validate_nhl_data,
        "mlb": validate_mlb_data,
        "nfl": validate_nfl_data,
    }

    all_reports = {}
    for sport in sports:
        try:
            report = validation_functions[sport]()
            all_reports[sport] = report
        except Exception as e:
            st.error(f"Error validating {sport.upper()}: {e}")
            continue

    if not all_reports:
        st.warning("No validation reports available.")
        return

    # Summary metrics
    st.subheader("Data Quality Summary")

    summary_data = []
    for sport, report in all_reports.items():
        checks = report.checks
        total_checks = len(checks)
        passed_checks = sum(1 for check in checks if check.get("severity") == "info")
        warning_checks = sum(
            1 for check in checks if check.get("severity") == "warning"
        )
        error_checks = sum(1 for check in checks if check.get("severity") == "error")

        summary_data.append(
            {
                "Sport": sport.upper(),
                "Total Checks": total_checks,
                "Passed": passed_checks,
                "Warnings": warning_checks,
                "Errors": error_checks,
                "Health Score": (
                    (passed_checks / total_checks * 100) if total_checks > 0 else 0
                ),
            }
        )

    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True)

    # Health score gauge
    fig = px.bar(
        summary_df,
        x="Sport",
        y="Health Score",
        title="Data Quality Health Score (%)",
        color="Health Score",
        color_continuous_scale="RdYlGn",
        range_y=[0, 100],
    )
    st.plotly_chart(fig, use_container_width=True)

    # Detailed reports
    st.subheader("Detailed Validation Reports")
    for sport, report in all_reports.items():
        with st.expander(f"{sport.upper()} Validation Details"):
            # Statistics
            if report.stats:
                st.write("**Statistics:**")
                stats_df = pd.DataFrame(
                    list(report.stats.items()), columns=["Metric", "Value"]
                )
                st.dataframe(stats_df, use_container_width=True)

            # Checks
            if report.checks:
                st.write("**Validation Checks:**")
                checks_data = []
                for check in report.checks:
                    checks_data.append(
                        {
                            "Check": check.get("name", "Unknown"),
                            "Status": check.get("severity", "unknown"),
                            "Message": check.get("message", ""),
                            "Passed": "✅" if check.get("passed", False) else "❌",
                        }
                    )
                checks_df = pd.DataFrame(checks_data)
                st.dataframe(checks_df, use_container_width=True)


def clv_analysis_page():
    """CLV (Closing Line Value) analysis dashboard."""
    st.title("📈 CLV Analysis - Edge Validation")

    # Import CLV tracker
    try:
        from clv_tracker import CLVTracker
    except ImportError:
        st.error("CLV tracker module not available.")
        return

    # Load CLV data
    tracker = CLVTracker()
    clv_data = tracker.analyze_clv(days_back=365)

    if clv_data.get("num_bets", 0) == 0:
        st.warning(
            "No CLV data available. CLV data needs to be backfilled from historical betting lines."
        )
        return

    # Overall CLV metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Bets with CLV", clv_data["num_bets"])
    with col2:
        st.metric("Average CLV", f"{clv_data['avg_clv']:+.2%}")
    with col3:
        st.metric("Positive CLV %", f"{clv_data['positive_clv_pct']:.1f}%")
    with col4:
        edge_indicator = "✅" if clv_data["avg_clv"] > 0 else "❌"
        st.metric("Beating Market", edge_indicator)

    # CLV by sport
    st.subheader("CLV Performance by Sport")
    sport_clv_df = pd.DataFrame(clv_data["by_sport"])
    fig = px.bar(
        sport_clv_df,
        x="sport",
        y="avg_clv",
        title="Average CLV by Sport",
        color="avg_clv",
        color_continuous_scale="RdYlGn",
    )
    fig.add_hline(y=0, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

    # CLV distribution
    st.subheader("CLV Distribution")
    # Load raw CLV data for histogram
    clv_query = """
        SELECT clv FROM placed_bets
        WHERE clv IS NOT NULL
        AND status IN ('won', 'lost')
    """
    try:
        raw_clv_df = default_db.fetch_df(clv_query)
        if not raw_clv_df.empty:
            fig = px.histogram(
                raw_clv_df,
                x="clv",
                nbins=50,
                title="CLV Distribution (Percentage Points)",
                labels={"clv": "CLV (%)"},
            )
            fig.add_vline(x=0, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading CLV distribution: {e}")

    # CLV vs Win Rate correlation
    st.subheader("CLV vs Actual Performance")
    correlation_query = """
        SELECT
            CASE WHEN clv >= 0 THEN 'Positive CLV' ELSE 'Negative CLV' END as clv_category,
            COUNT(*) as num_bets,
            AVG(CASE WHEN status = 'won' THEN 1.0 ELSE 0.0 END) as win_rate,
            AVG(clv) as avg_clv
        FROM placed_bets
        WHERE clv IS NOT NULL AND status IN ('won', 'lost')
        GROUP BY CASE WHEN clv >= 0 THEN 'Positive CLV' ELSE 'Negative CLV' END
    """
    try:
        correlation_df = default_db.fetch_df(correlation_query)
        if not correlation_df.empty:
            fig = px.bar(
                correlation_df,
                x="clv_category",
                y="win_rate",
                title="Win Rate by CLV Category",
                color="clv_category",
                labels={"win_rate": "Win Rate (%)"},
            )
            st.plotly_chart(fig, use_container_width=True)

            st.write("**CLV Correlation Analysis:**")
            st.dataframe(correlation_df.round(4), use_container_width=True)
    except Exception as e:
        st.error(f"Error loading CLV correlation: {e}")

    # CLV over time
    st.subheader("CLV Trend Over Time")
    time_query = """
        SELECT
            DATE_TRUNC('month', placed_date) as month,
            COUNT(*) as num_bets,
            AVG(clv) as avg_clv,
            SUM(CASE WHEN clv > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as positive_pct
        FROM placed_bets
        WHERE clv IS NOT NULL AND status IN ('won', 'lost')
        GROUP BY DATE_TRUNC('month', placed_date)
        ORDER BY month
    """
    try:
        time_df = default_db.fetch_df(time_query)
        if not time_df.empty:
            fig = px.line(
                time_df,
                x="month",
                y="avg_clv",
                title="Average CLV Over Time",
                markers=True,
            )
            fig.add_hline(y=0, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading CLV time series: {e}")


# --- Sidebar & Routing ---

page = st.sidebar.radio(
    "📍 Navigation",
    [
        "Elo Analysis",
        "Betting Performance",
        "Financial Performance",
        "Data Quality",
        "CLV Analysis",
    ],
    index=0,
)

if page == "Betting Performance":
    betting_performance_page_v2()
elif page == "Financial Performance":
    financial_performance_page()
elif page == "Data Quality":
    data_quality_page()
elif page == "CLV Analysis":
    clv_analysis_page()
else:
    st.sidebar.title("Configuration")
    league = st.sidebar.selectbox(
        "Select League",
        ["MLB", "NHL", "NFL", "NBA", "EPL", "Tennis", "NCAAB", "WNCAAB", "Ligue1"],
    )

    with st.spinner(f"Loading {league} data..."):
        raw_data = load_data(league)

    if raw_data.empty:
        st.warning(
            f"No data found for {league}. Please ensure data is backfilled into unified_games."
        )
        st.stop()

    min_date = raw_data["game_date"].min().date()
    max_date = raw_data["game_date"].max().date()
    available_seasons = sorted(raw_data["season"].unique().tolist(), reverse=True)
    available_seasons.insert(0, "All Time")

    selected_season = st.sidebar.selectbox("Season", available_seasons)
    cutoff_date = st.sidebar.date_input(
        "Analysis Up To Date", value=max_date, min_value=min_date, max_value=max_date
    )

    # Defaults
    default_k = 20
    default_home = 50
    if league == "NHL":
        default_home = 100
    if league == "NBA":
        default_home = 100
    if league == "NFL":
        default_home = 65
    if league in ["EPL", "Ligue1"]:
        default_home = 60
    if league == "Tennis":
        default_home = 0
        default_k = 32
    if league in ["NCAAB", "WNCAAB"]:
        default_home = 100

    with st.sidebar.expander("Elo Parameters"):
        k_factor = st.number_input("K-Factor", value=default_k)
        home_adv = st.number_input("Home Advantage", value=default_home)

    with st.sidebar.expander("Glicko-2 Parameters"):
        enable_glicko2 = st.checkbox("Enable Glicko-2 Comparison", value=True)
        glicko2_tau = st.slider("System Volatility (τ)", 0.3, 1.2, 0.5, 0.1)
        glicko2_home_adv = st.number_input(
            "Home Advantage (Glicko-2)", value=default_home
        )

    if selected_season != "All Time":
        filtered_data = raw_data[raw_data["season"] == selected_season].copy()
    else:
        filtered_data = raw_data.copy()

    filtered_data = filtered_data[
        filtered_data["game_date"].dt.date <= cutoff_date
    ].copy()

    if filtered_data.empty:
        st.warning("No games found matching criteria.")
        st.stop()

    with st.spinner("Running Elo Simulation..."):
        simulated_data = run_elo_simulation(filtered_data, league, k_factor, home_adv)

    if enable_glicko2 and league in ["NBA", "NHL", "MLB", "NFL"]:
        with st.spinner("Running Glicko-2 Simulation..."):
            simulated_data_glicko2 = run_glicko2_simulation(
                filtered_data, league, glicko2_tau, glicko2_home_adv
            )
            if "glicko2_prob" in simulated_data_glicko2.columns:
                simulated_data["glicko2_prob"] = simulated_data_glicko2["glicko2_prob"]
    else:
        simulated_data["glicko2_prob"] = None

    decile_stats = calculate_deciles(simulated_data)
    gain_curve = calculate_cumulative_gain(simulated_data)
    roi_matrix = calculate_decile_probability_roi_matrix(simulated_data)

    st.title(f"{league} Betting Analytics Dashboard")
    st.markdown(
        f"Analysis for **{selected_season}** up to **{cutoff_date}** ({len(simulated_data)} games)"
    )

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    baseline_win_rate = simulated_data["home_win"].mean()
    if not decile_stats.empty:
        top_decile = decile_stats.iloc[-1]
        col1.metric("Baseline Win Rate", f"{baseline_win_rate:.1%}")
        col2.metric("Top Decile Win Rate", f"{top_decile['Win Rate']:.1%}")
        col3.metric("Top Decile Lift", f"{top_decile['Lift']:.2f}x")
        col4.metric("Top Decile ROI (-110)", top_decile["ROI (-110)"])

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "Lift Chart",
            "Calibration",
            "ROI Analysis",
            "Cumulative Gain",
            "Elo vs Glicko-2",
            "Details",
            "Season Timing",
        ]
    )

    with tab1:
        st.header("Lift by Probability Decile")
        if not decile_stats.empty:
            fig = px.bar(
                decile_stats,
                x="Decile",
                y="Lift",
                color="Lift",
                color_continuous_scale="RdYlGn",
            )
            fig.add_hline(y=1.0, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("Model Calibration")
        if not decile_stats.empty:
            fig = px.scatter(decile_stats, x="Avg Prob", y="Win Rate", size="Games")
            fig.add_shape(
                type="line", x0=0, y0=0, x1=1, y1=1, line=dict(color="Red", dash="dash")
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.header("ROI Analysis (-110 Odds)")
        if not decile_stats.empty:
            # Extract ROI percentage values for plotting
            decile_stats_copy = decile_stats.copy()
            decile_stats_copy["ROI Value"] = (
                decile_stats_copy["ROI (-110)"].str.rstrip("%").astype(float)
            )
            fig = px.bar(
                decile_stats_copy,
                x="Decile",
                y="ROI Value",
                color="ROI Value",
                color_continuous_scale="RdYlGn",
            )
            fig.add_hline(y=0, line_color="black")
            st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.header("Cumulative Gain Curve")
        if not gain_curve.empty:
            fig = px.line(gain_curve, x="pct_games", y="pct_wins_captured")
            fig.add_shape(
                type="line", x0=0, y0=0, x1=1, y1=1, line=dict(color="Red", dash="dash")
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab5:
        st.header("Elo vs Glicko-2 Comparison")
        if simulated_data["glicko2_prob"].notna().any():
            comp_df = simulated_data[simulated_data["glicko2_prob"].notna()].copy()
            elo_acc = ((comp_df["elo_prob"] > 0.5) == comp_df["home_win"]).mean()
            gl_acc = ((comp_df["glicko2_prob"] > 0.5) == comp_df["home_win"]).mean()
            col1, col2 = st.columns(2)
            col1.metric("Elo Accuracy", f"{elo_acc:.1%}")
            col2.metric(
                "Glicko-2 Accuracy",
                f"{gl_acc:.1%}",
                delta=f"{(gl_acc - elo_acc) * 100:.1f} pts",
            )
            fig = px.scatter(comp_df, x="elo_prob", y="glicko2_prob", color="home_win")
            fig.add_shape(
                type="line", x0=0, y0=0, x1=1, y1=1, line=dict(color="Red", dash="dash")
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Comparison available for major sports with Glicko-2 enabled.")

    with tab6:
        st.header("Detailed Statistics")
        if not decile_stats.empty:
            st.subheader("Decile Performance")
            st.dataframe(decile_stats, use_container_width=True)

            st.subheader("ROI by Decile at Different Kalshi Prices")
            st.markdown(
                "**Rows**: Elo probability deciles | **Columns**: Kalshi contract prices (home team win odds) | **Values**: ROI if betting at that price"
            )
            if not roi_matrix.empty:
                st.dataframe(roi_matrix, use_container_width=True)
            else:
                st.info(
                    "ROI matrix requires sufficient data across probability spectrum."
                )

    with tab7:
        st.header("Predictive Power Over Season")
        if not simulated_data.empty:
            viz_df = simulated_data.copy()
            viz_df["season_rank"] = viz_df.groupby("season")["game_date"].rank(
                method="dense"
            )
            season_max = viz_df.groupby("season")["season_rank"].transform("max")
            viz_df["Season Progress (%)"] = (viz_df["season_rank"] / season_max) * 100
            viz_df["Progress Bin"] = (
                pd.cut(viz_df["Season Progress (%)"], bins=10, labels=False) + 1
            ) * 10
            timing_stats = []
            for bin_val in sorted(viz_df["Progress Bin"].unique()):
                subset = viz_df[viz_df["Progress Bin"] == bin_val]
                if subset.empty:
                    continue
                brier = ((subset["elo_prob"] - subset["home_win"]) ** 2).mean()
                timing_stats.append(
                    {
                        "Progress (%)": bin_val,
                        "Brier Score": brier,
                        "Games": len(subset),
                    }
                )
            timing_df = pd.DataFrame(timing_stats)
            if not timing_df.empty:
                fig = px.line(
                    timing_df, x="Progress (%)", y="Brier Score", markers=True
                )
                st.plotly_chart(fig, use_container_width=True)
