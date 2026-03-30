import sys
import os

# Add both parent directory (for 'plugins.' prefix) and plugins directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "../plugins"))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from plugins.db_manager import default_db

try:
    from plugins.pnl_diagnostic import generate_timing_heatmap_data, run_diagnostic
except ImportError:  # pragma: no cover
    generate_timing_heatmap_data = None  # type: ignore[assignment]
    run_diagnostic = None  # type: ignore[assignment]


@dataclass
class FinancialMetrics:
    """Dataclass to hold overall financial performance metrics."""

    total_invested: float
    total_profit: float
    total_roi: float
    win_rate: float


@dataclass
class SimulationConfig:
    """Configuration for a rating simulation."""

    league: str
    home_adv: float
    k_factor: Optional[float] = None
    tau: Optional[float] = None


@dataclass
class ChartConfig:
    """Configuration for rendering a Plotly chart."""

    chart_type: str
    chart_kwargs: Dict[str, Any]
    title: Optional[str] = None
    header_level: str = "subheader"
    add_hline: Optional[float] = None
    add_vline: Optional[float] = None
    hline_color: str = "red"
    vline_color: str = "red"
    add_diagonal: bool = False


# Dashboard configuration constants
RANDOM_SEED = 42  # For reproducible random operations
DECILE_COUNT = 10  # Number of deciles for probability analysis
PERCENTAGE_MULTIPLIER = 100  # Convert decimal to percentage
AMERICAN_ODDS_VALUE = 110  # Standard -110 odds for ROI calculation
ODDS_PAYOUT_RATIO = 0.909  # Payout ratio for -110 odds (1/1.1)
BREAKEVEN_PROBABILITY = 0.5238  # Breakeven probability for -110 odds (110/(110+100))
SAMPLE_SIZE_THRESHOLD = 1000  # Threshold for downsampling large datasets

# UI Layout constants
SYNC_BUTTON_LAYOUT = [3, 1]
FILTER_CONTROL_COLUMNS = 3
DEFAULT_DATAFRAME_HEIGHT = 600
SMALL_DATAFRAME_HEIGHT = 400
FINANCIAL_METRIC_COLUMNS = 4
CLV_METRIC_COLUMNS = 4
EV_METRIC_COLUMNS = 4
ELO_METRIC_COLUMNS = 4
HEALTH_SCORE_MAX = 100
EV_BUCKET_BINS = [-0.5, 0, 0.05, 0.10, 0.15, 0.20, 0.50]
EV_BUCKET_LABELS = ["<0%", "0-5%", "5-10%", "10-15%", "15-20%", "20%+"]
CLV_ANALYSIS_DAYS_DEFAULT = 365
CLV_HISTOGRAM_BINS = 50
EV_HISTOGRAM_BINS = 30

# Sport-specific default parameters
DEFAULT_K_FACTOR = 20
DEFAULT_HOME_ADVANTAGE_GENERIC = 50
DEFAULT_HOME_ADVANTAGE_NHL = 100
DEFAULT_HOME_ADVANTAGE_NBA = 100
DEFAULT_HOME_ADVANTAGE_NFL = 65
DEFAULT_HOME_ADVANTAGE_SOCCER = 60  # EPL, Ligue1
DEFAULT_HOME_ADVANTAGE_TENNIS = 0
DEFAULT_HOME_ADVANTAGE_COLLEGE_BASKETBALL = 100  # NCAAB, WNCAAB
DEFAULT_K_FACTOR_TENNIS = 32
DEFAULT_GLICKO2_HOME_ADVANTAGE = 100
GLICKO2_TAU_MIN = 0.3
GLICKO2_TAU_MAX = 1.2
GLICKO2_TAU_DEFAULT = 0.5
GLICKO2_TAU_STEP = 0.1

# Mapping of dashboard league names to database sport values
SPORT_DB_MAPPING = {
    "NHL": "NHL",
    "MLB": "MLB",
    "NFL": "NFL",
    "NBA": "NBA",
    "EPL": "EPL",
    "Tennis": "TENNIS",
    "NCAAB": "NCAAB",
    "WNCAAB": "WNCAAB",
    "Ligue1": "LIGUE1",
    "CBA": "CBA",
    "Unrivaled": "UNRIVALED",
}


def _render_plotly_chart(
    df: pd.DataFrame,
    config: ChartConfig,
) -> None:
    """Helper to render a Plotly chart in Streamlit with consistent styling.

    Args:
        df: DataFrame containing the data to plot
        config: Configuration for the chart
    """
    if config.title:
        if config.header_level == "header":
            st.header(config.title)
        elif config.header_level == "subheader":
            st.subheader(config.title)

    if df.empty:
        return

    # Map chart type to Plotly Express function
    chart_funcs = {
        "histogram": px.histogram,
        "line": px.line,
        "bar": px.bar,
        "scatter": px.scatter,
    }

    if config.chart_type not in chart_funcs:
        st.error(f"Unsupported chart type: {config.chart_type}")
        return

    fig = chart_funcs[config.chart_type](df, **config.chart_kwargs)

    # Add reference lines
    if config.add_hline is not None:
        fig.add_hline(
            y=config.add_hline, line_dash="dash", line_color=config.hline_color
        )
    if config.add_vline is not None:
        fig.add_vline(
            x=config.add_vline, line_dash="dash", line_color=config.vline_color
        )
    if config.add_diagonal:
        fig.add_shape(
            type="line", x0=0, y0=0, x1=1, y1=1, line=dict(color="Red", dash="dash")
        )

    st.plotly_chart(fig, use_container_width=True)


def _render_query_chart(
    query: str,
    config: ChartConfig,
    error_message: Optional[str] = None,
) -> None:
    """Helper to fetch data from database and render a Plotly chart.

    Args:
        query: SQL query to fetch data
        config: Configuration for the chart
        error_message: Custom error message if data fetch fails
    """
    try:
        df = default_db.fetch_df(query)
        _render_plotly_chart(df, config)
    except Exception as e:
        msg = error_message if error_message else f"Error loading {config.title}"
        st.error(f"{msg}: {e}")


STANDARD_GAME_QUERY = """
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

TENNIS_GAME_QUERY = """
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

try:
    from plugins.elo import CBAEloRating
except ImportError:
    CBAEloRating = None

try:
    from plugins.elo import UnrivaledEloRating
except ImportError:
    UnrivaledEloRating = None

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

# --- Configuration ---
st.set_page_config(
    page_title="Sports Betting Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Helper Functions ---


@st.cache_data
def load_data(league: str) -> pd.DataFrame:
    """Load game data from the unified_games table in PostgreSQL.

    Args:
        league: Dashboard league name (e.g., 'NHL', 'Tennis')

    Returns:
        DataFrame with game results
    """
    sport = SPORT_DB_MAPPING.get(league)
    if not sport:
        return pd.DataFrame()

    # Determine which query to use
    query = TENNIS_GAME_QUERY if league == "Tennis" else STANDARD_GAME_QUERY

    try:
        games_df = default_db.fetch_df(query, {"sport": sport})
        if not games_df.empty:
            games_df["game_date"] = pd.to_datetime(games_df["game_date"])
        return games_df
    except Exception as e:
        st.error(f"Error loading {league} data: {e}")
        return pd.DataFrame()


def _get_rating_class_for_league(league: str, rating_type: str = "Elo"):
    """Get the appropriate Rating class for a given league."""
    if rating_type == "Elo":
        league_to_class = {
            "MLB": MLBEloRating,
            "NHL": NHLEloRating,
            "NFL": NFLEloRating,
            "NBA": NBAEloRating,
            "EPL": EPLEloRating,
            "Tennis": TennisEloRating,
            "NCAAB": NCAABEloRating,
            "WNCAAB": WNCAABEloRating,
            "Ligue1": Ligue1EloRating,
            "CBA": CBAEloRating,
            "Unrivaled": UnrivaledEloRating,
        }
    else:  # Glicko-2
        league_to_class = {
            "MLB": MLBGlicko2Rating,
            "NHL": NHLGlicko2Rating,
            "NFL": NFLGlicko2Rating,
            "NBA": NBAGlicko2Rating,
        }
    return league_to_class.get(league)


def _prepare_tennis_data(games_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare tennis data by randomizing winner/loser positions to avoid bias."""
    np.random.seed(RANDOM_SEED)
    swap_mask = np.random.random(len(games_df)) > 0.5
    games_df = games_df.copy()

    real_winners = games_df["home_team"].copy()
    real_losers = games_df["away_team"].copy()

    games_df.loc[swap_mask, "home_team"] = real_losers[swap_mask]
    games_df.loc[swap_mask, "away_team"] = real_winners[swap_mask]
    games_df.loc[swap_mask, "home_win"] = 0

    return games_df


def _get_predict_args(league: str, game: Dict[str, Any]) -> Dict[str, Any]:
    """Get arguments for the predict method based on league."""
    if league == "NCAAB":
        return {"is_neutral": game.get("is_neutral", False)}
    elif league == "WNCAAB":
        return {"is_neutral": game.get("neutral_site", False)}
    else:
        return {}


def _get_update_args(league: str, game: Dict[str, Any]) -> Dict[str, Any]:
    """Get arguments for the update method based on league."""
    # Start with base arguments used by most sports
    args = {
        "home_team": game["home_team"],
        "away_team": game["away_team"],
        "home_won": game["home_win"],
    }

    if league in ["EPL", "Ligue1"]:
        # Soccer leagues use "H"/"A" strings for home_won
        args["home_won"] = "H" if game["home_win"] == 1 else "A"
    elif league == "Tennis":
        # Tennis uses winner/loser instead of home/away
        winner = game["home_team"] if game["home_win"] == 1 else game["away_team"]
        loser = game["away_team"] if game["home_win"] == 1 else game["home_team"]
        args["home_team"] = winner
        args["away_team"] = loser
        args["home_won"] = True
    elif league in ["MLB", "NFL"]:
        # MLB/NFL use scores for margin-of-victory multiplier
        args["home_won"] = game["home_score"] > game["away_score"]
        args["home_score"] = game["home_score"]
        args["away_score"] = game["away_score"]
    elif league in ["NCAAB", "WNCAAB"]:
        # College basketball with neutral site support
        is_neutral = (
            game.get("is_neutral", False)
            if league == "NCAAB"
            else game.get("neutral_site", False)
        )
        args["is_neutral"] = is_neutral

    return args


@st.cache_data
def run_elo_simulation(
    games_df: pd.DataFrame, config: SimulationConfig
) -> pd.DataFrame:
    """Run Elo simulation for the selected league."""
    if games_df.empty:
        return games_df

    # Tennis Specific: Randomize winner/loser positions to avoid bias
    if config.league == "Tennis":
        games_df = _prepare_tennis_data(games_df)

    # Get Elo class for league
    elo_class = _get_rating_class_for_league(config.league, rating_type="Elo")
    if not elo_class:
        return games_df

    # Initialize Elo system
    # Tennis doesn't use home advantage
    if config.league == "Tennis":
        elo = elo_class(k_factor=config.k_factor)
    else:
        elo = elo_class(k_factor=config.k_factor, home_advantage=config.home_adv)

    probs = []

    # Process games
    for _, game in games_df.iterrows():
        # Predict
        predict_args = _get_predict_args(config.league, game)
        prob = elo.predict(game["home_team"], game["away_team"], **predict_args)
        probs.append(prob)

        # Update
        update_args = _get_update_args(config.league, game)
        elo.update(**update_args)

    games_df["elo_prob"] = probs
    return games_df


@st.cache_data
def run_glicko2_simulation(
    games_df: pd.DataFrame, config: SimulationConfig
) -> pd.DataFrame:
    """Run Glicko-2 simulation for the selected league."""
    if games_df.empty:
        return games_df

    # Initialize Glicko-2 system
    glicko_class = _get_rating_class_for_league(config.league, rating_type="Glicko-2")
    if not glicko_class:
        return games_df

    glicko = glicko_class()
    glicko.home_advantage = config.home_adv
    glicko.TAU = config.tau
    probs = []

    for _, game in games_df.iterrows():
        prob = glicko.predict(game["home_team"], game["away_team"])
        probs.append(prob)
        glicko.update(game["home_team"], game["away_team"], game["home_win"])

    games_df["glicko2_prob"] = probs
    return games_df


def _assign_deciles(df: pd.DataFrame, column: str = "elo_prob") -> pd.DataFrame:
    """Assign deciles to a DataFrame based on a probability column."""
    if df.empty or column not in df.columns or df[column].isna().all():
        return pd.DataFrame()

    df = df.copy()
    try:
        df["decile"] = (
            pd.qcut(df[column], q=DECILE_COUNT, labels=False, duplicates="drop") + 1
        )
    except (ValueError, KeyError):
        # Fallback to simple binning if qcut fails
        try:
            df["decile"] = pd.cut(df[column], bins=DECILE_COUNT, labels=False) + 1
        except (ValueError, KeyError):
            # If both fail, return empty dataframe
            return pd.DataFrame()
    return df


def calculate_deciles(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate lift/gain metrics by decile."""
    df = _assign_deciles(df)
    if df.empty or "decile" not in df.columns:
        return pd.DataFrame()

    baseline = df["home_win"].mean()
    results = []

    for decile in sorted(df["decile"].unique()):
        subset = df[df["decile"] == decile]
        games = len(subset)
        wins = subset["home_win"].sum()
        win_rate = wins / games if games > 0 else 0
        avg_prob = subset["elo_prob"].mean()
        lift = win_rate / baseline if baseline > 0 else 0

        # ROI using -110 odds: payout = ODDS_PAYOUT_RATIO per dollar bet
        roi_110 = (
            (win_rate * ODDS_PAYOUT_RATIO) - (1 - win_rate)
        ) * PERCENTAGE_MULTIPLIER

        # -110 odds equivalent probability (breakeven point)
        odds_110_prob = AMERICAN_ODDS_VALUE / (
            AMERICAN_ODDS_VALUE + PERCENTAGE_MULTIPLIER
        )  # 52.38%

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
    df: pd.DataFrame,
    kalshi_prices: List[float] = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1],
) -> pd.DataFrame:
    """Calculate ROI matrix for deciles vs Kalshi price points."""
    df = _assign_deciles(df)
    if df.empty or "decile" not in df.columns or "home_win" not in df.columns:
        return pd.DataFrame()

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
            roi = (
                ((win_rate / kalshi_price) - 1) * PERCENTAGE_MULTIPLIER
                if kalshi_price > 0
                else 0
            )

            row_data[f"{int(kalshi_price * PERCENTAGE_MULTIPLIER)}¢"] = f"{roi:+.1f}%"

        results.append(row_data)

    # Convert to DataFrame
    matrix_df = pd.DataFrame(results)
    if not matrix_df.empty:
        matrix_df = matrix_df.set_index("Decile")

    return matrix_df


def calculate_cumulative_gain(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate cumulative gain curve data."""
    if df.empty:
        return pd.DataFrame()

    # Check if required columns exist
    if "elo_prob" not in df.columns or "home_win" not in df.columns:
        return pd.DataFrame()

    # Check if elo_prob has valid data
    if df["elo_prob"].isna().all():
        return pd.DataFrame()

    df_sorted = df.sort_values("elo_prob", ascending=False)
    df_sorted["cumulative_games"] = np.arange(1, len(df_sorted) + 1)
    df_sorted["cumulative_wins"] = df_sorted["home_win"].cumsum()

    df_sorted["pct_games"] = df_sorted["cumulative_games"] / len(df_sorted)
    df_sorted["pct_wins_captured"] = (
        df_sorted["cumulative_wins"] / df_sorted["home_win"].sum()
    )

    if len(df_sorted) > SAMPLE_SIZE_THRESHOLD:
        return df_sorted.iloc[:: int(len(df_sorted) / SAMPLE_SIZE_THRESHOLD)]
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
        from plugins.portfolio_snapshots import load_snapshots_since
    except Exception:
        return pd.DataFrame()

    since_utc = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)
    return load_snapshots_since(since_utc=since_utc)


def _render_sync_button() -> None:
    """Render the sync button for Kalshi data."""
    col1, col2 = st.columns(SYNC_BUTTON_LAYOUT)
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


def _calculate_portfolio_metrics(
    snapshots_df: pd.DataFrame, eastern_tz: ZoneInfo
) -> tuple[float | None, datetime | None]:
    """Calculate portfolio metrics from snapshots data.

    Args:
        snapshots_df: DataFrame with portfolio snapshots
        eastern_tz: Eastern timezone object

    Returns:
        Tuple of (latest_portfolio_value, latest_snapshot_time_et)
    """
    latest_portfolio_value = None
    latest_snapshot_time_et = None

    if not snapshots_df.empty:
        snapshots_df["snapshot_hour_utc"] = pd.to_datetime(
            snapshots_df["snapshot_hour_utc"], utc=True
        )
        last_row = snapshots_df.iloc[-1]
        latest_portfolio_value = float(last_row.get("portfolio_value_dollars", 0.0))
        latest_snapshot_time_et = last_row["snapshot_hour_utc"].tz_convert(eastern_tz)

    return latest_portfolio_value, latest_snapshot_time_et


def _calculate_open_games_count(betting_df: pd.DataFrame) -> int:
    """Calculate the number of open games from betting data.

    Args:
        betting_df: DataFrame with betting results

    Returns:
        Number of open games
    """
    open_bets_df = (
        betting_df[betting_df["status"] == "open"]
        if "status" in betting_df.columns
        else betting_df.iloc[0:0]
    )
    return (
        int(open_bets_df["ticker"].nunique()) if "ticker" in open_bets_df.columns else 0
    )


def _render_portfolio_metrics(
    latest_portfolio_value: float | None,
    latest_snapshot_time_et: datetime | None,
    open_games: int,
) -> None:
    """Render portfolio metrics in two columns.

    Args:
        latest_portfolio_value: Latest portfolio value or None
        latest_snapshot_time_et: Latest snapshot time in ET or None
        open_games: Number of open games
    """
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


def _render_portfolio_chart(snapshots_df: pd.DataFrame, eastern_tz: ZoneInfo) -> None:
    """Render portfolio value time series chart.

    Args:
        snapshots_df: DataFrame with portfolio snapshots
        eastern_tz: Eastern timezone object
    """
    if not snapshots_df.empty:
        plot_df = snapshots_df.copy()
        plot_df["snapshot_hour_et"] = plot_df["snapshot_hour_utc"].dt.tz_convert(
            eastern_tz
        )
        fig = px.line(
            plot_df,
            x="snapshot_hour_et",
            y="portfolio_value_dollars",
            title="Hourly Portfolio Value (ET)",
        )
        st.plotly_chart(fig, use_container_width=True)


def _render_filters(betting_df: pd.DataFrame) -> tuple[str, str, str, pd.DataFrame]:
    """Render filter controls and return filtered data.

    Args:
        betting_df: DataFrame with betting results

    Returns:
        Tuple of (selected_sport, selected_date, selected_status, filtered_df)
    """
    st.subheader("Filters")
    f1, f2, f3 = st.columns(FILTER_CONTROL_COLUMNS)

    with f1:
        sports = ["All"] + sorted(betting_df["sport"].dropna().unique().tolist())
        selected_sport_value = st.selectbox("Sport", sports, key="sport_filter_v2_db")
        selected_sport: str = (
            selected_sport_value if selected_sport_value is not None else "All"
        )

    with f2:
        dates = ["All"] + sorted(
            betting_df["placed_date"].dropna().unique().tolist(), reverse=True
        )
        selected_date_value = st.selectbox("Date", dates, key="date_filter_v2_db")
        selected_date: str = (
            selected_date_value if selected_date_value is not None else "All"
        )

    with f3:
        statuses = ["All"] + sorted(betting_df["status"].dropna().unique().tolist())
        selected_status_value = st.selectbox(
            "Status", statuses, key="status_filter_v2_db"
        )
        selected_status: str = (
            selected_status_value if selected_status_value is not None else "All"
        )

    # Apply filters
    filtered_df = betting_df.copy()
    if selected_sport != "All":
        filtered_df = filtered_df[filtered_df["sport"] == selected_sport]
    if selected_date != "All":
        filtered_df = filtered_df[filtered_df["placed_date"] == selected_date]
    if selected_status != "All":
        filtered_df = filtered_df[filtered_df["status"] == selected_status]

    return selected_sport, selected_date, selected_status, filtered_df


def _render_overview_tab(betting_df: pd.DataFrame) -> None:
    """Render the overview tab with bet outcomes pie chart.

    Args:
        betting_df: DataFrame with betting results
    """
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


def _render_all_bets_tab(filtered_df: pd.DataFrame) -> None:
    """Render the all bets tab with filtered data.

    Args:
        filtered_df: Filtered DataFrame with betting results
    """
    st.dataframe(
        filtered_df.sort_values("placed_date", ascending=False),
        use_container_width=True,
        height=DEFAULT_DATAFRAME_HEIGHT,
    )


def betting_performance_page_v2():
    """Enhanced betting performance page (Postgres + portfolio snapshots)."""
    st.title("🎰 Betting Performance Tracker")
    eastern = ZoneInfo("America/New_York")

    # Render sync button
    _render_sync_button()

    # Load betting data
    betting_df = _load_betting_results_from_db()
    if betting_df.empty:
        st.warning(
            "No betting data available. Click 'Sync from Kalshi' to load your bets."
        )
        return

    # Load portfolio snapshots and calculate metrics
    snapshots_df = _load_portfolio_snapshots()
    latest_portfolio_value, latest_snapshot_time_et = _calculate_portfolio_metrics(
        snapshots_df, eastern
    )

    # Calculate open games count
    open_games = _calculate_open_games_count(betting_df)

    # Render portfolio metrics
    _render_portfolio_metrics(
        latest_portfolio_value, latest_snapshot_time_et, open_games
    )

    # Render portfolio chart
    _render_portfolio_chart(snapshots_df, eastern)

    # Render filters and get filtered data
    _, _, _, filtered_df = _render_filters(betting_df)

    # Render tabs
    tab1, tab2 = st.tabs(["📊 Overview", "📋 All Bets"])
    with tab1:
        _render_overview_tab(betting_df)
    with tab2:
        _render_all_bets_tab(filtered_df)


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

    # Calculate all metrics and portfolio value
    daily_pl, weekly_pl, monthly_pl = _calculate_pl_time_series(settled_bets)
    sport_pl = _calculate_sport_performance(settled_bets)
    metrics = _calculate_overall_metrics(settled_bets)
    portfolio_data = _calculate_portfolio_value()

    # Display metrics
    _display_financial_metrics(portfolio_data, metrics, settled_bets)

    # P&L Time Series
    _display_pl_time_series(daily_pl, weekly_pl, monthly_pl)

    # ROI by Sport
    _display_sport_performance(sport_pl)


def _calculate_pl_time_series(
    settled_bets: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calculate daily, weekly, and monthly P&L time series."""
    # Use settlement date (updated_at) instead of placed_date for P&L tracking
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

    return daily_pl, weekly_pl, monthly_pl


def _calculate_sport_performance(settled_bets: pd.DataFrame) -> pd.DataFrame:
    """Calculate ROI and win rate by sport."""
    sport_pl = (
        settled_bets.groupby("sport")
        .agg({"profit_dollars": "sum", "cost_dollars": "sum", "contracts": "sum"})
        .reset_index()
    )
    sport_pl["roi"] = (
        sport_pl["profit_dollars"] / sport_pl["cost_dollars"]
    ) * PERCENTAGE_MULTIPLIER
    sport_pl["win_rate"] = (
        settled_bets[settled_bets["status"] == "won"].groupby("sport").size()
        / settled_bets.groupby("sport").size()
        * PERCENTAGE_MULTIPLIER
    )
    return sport_pl


def _calculate_overall_metrics(
    settled_bets: pd.DataFrame,
) -> FinancialMetrics:
    """Calculate overall financial metrics."""
    total_invested = settled_bets["cost_dollars"].sum()
    total_profit = settled_bets["profit_dollars"].sum()
    total_roi = (
        (total_profit / total_invested) * PERCENTAGE_MULTIPLIER
        if total_invested > 0
        else 0
    )
    win_rate = (
        len(settled_bets[settled_bets["status"] == "won"])
        / len(settled_bets)
        * PERCENTAGE_MULTIPLIER
    )
    return FinancialMetrics(
        total_invested=total_invested,
        total_profit=total_profit,
        total_roi=total_roi,
        win_rate=win_rate,
    )


def _get_latest_cash_snapshot() -> Optional[pd.DataFrame]:
    """Fetch the latest cash balance snapshot from the database."""
    return default_db.fetch_df(
        """
        SELECT
            ROUND(balance_dollars::numeric, 2) as cash_balance,
            snapshot_hour_utc
        FROM portfolio_value_snapshots
        ORDER BY snapshot_hour_utc DESC
        LIMIT 1
    """
    )


def _get_open_positions_value() -> float:
    """Fetch the total value of open positions from the database."""
    open_bets_df = default_db.fetch_df(
        """
        SELECT
            ROUND(SUM(cost_dollars)::numeric, 2) as open_positions_value
        FROM placed_bets
        WHERE status = 'open'
    """
    )
    if not open_bets_df.empty and open_bets_df.iloc[0]["open_positions_value"]:
        return float(open_bets_df.iloc[0]["open_positions_value"])
    return 0.0


def _calculate_portfolio_value() -> dict:
    """Calculate portfolio value: cash balance + open positions value."""
    try:
        cash_df = _get_latest_cash_snapshot()
        open_value = _get_open_positions_value()

        if cash_df is not None and not cash_df.empty:
            cash_balance = float(cash_df.iloc[0]["cash_balance"])
            snapshot_time = cash_df.iloc[0]["snapshot_hour_utc"]
            if isinstance(snapshot_time, str):
                snapshot_time = datetime.fromisoformat(snapshot_time)

            balance_timestamp = (
                snapshot_time.strftime("%Y-%m-%d %I:%M %p")
                if snapshot_time
                else "unknown"
            )

            # Calculate portfolio value
            portfolio_value = cash_balance + open_value

            return {
                "kalshi_balance": portfolio_value,
                "cash_balance": cash_balance,
                "open_value": open_value,
                "balance_timestamp": balance_timestamp,
                "balance_help": f"Portfolio value as of {balance_timestamp}: ${cash_balance:.2f} cash + ${open_value:.2f} in open bets",
                "success": True,
            }
        else:
            return {
                "kalshi_balance": None,
                "balance_timestamp": None,
                "balance_help": None,
                "success": False,
            }
    except Exception as e:
        return {
            "kalshi_balance": None,
            "balance_timestamp": None,
            "balance_help": f"Error calculating balance: {e}",
            "success": False,
        }


def _display_financial_metrics(
    portfolio_data: dict,
    metrics: FinancialMetrics,
    settled_bets: pd.DataFrame,
) -> None:
    """Display financial metrics in columns."""
    col1, col2, col3, col4 = st.columns(FINANCIAL_METRIC_COLUMNS)
    with col1:
        if (
            portfolio_data.get("success")
            and portfolio_data["kalshi_balance"] is not None
        ):
            st.metric(
                "Portfolio Value",
                f"${portfolio_data['kalshi_balance']:,.2f}",
                help=portfolio_data["balance_help"],
            )
        else:
            st.metric(
                "Total Invested",
                f"${metrics.total_invested:,.2f}",
                help="Sum of all bet costs (portfolio snapshot unavailable)",
            )
    with col2:
        st.metric(
            "Total P&L",
            f"${metrics.total_profit:,.2f}",
            delta=f"{metrics.total_roi:+.1f}%",
        )
    with col3:
        st.metric("Win Rate", f"{metrics.win_rate:.1f}%")
    with col4:
        st.metric("Total Bets", len(settled_bets))


def _display_pl_time_series(
    daily_pl: pd.DataFrame, weekly_pl: pd.DataFrame, monthly_pl: pd.DataFrame
) -> None:
    """Display P&L time series charts."""
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


def _display_sport_performance(sport_pl: pd.DataFrame) -> None:
    """Display sport performance charts and tables."""
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


def _run_data_validations(sports: List[str]) -> Dict[str, Any]:
    """Import validation functions and run validations for each sport.

    Args:
        sports: List of sports to validate.

    Returns:
        Dict[str, Any]: Validation reports for each sport.
    """
    try:
        from plugins.data_validation import (
            validate_nhl_data,
            validate_mlb_data,
            validate_nfl_data,
        )
    except ImportError:
        st.error("Data validation module not available.")
        return {}

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
        return {}

    return all_reports


def _display_data_quality_summary(all_reports: Dict[str, Any]) -> None:
    """Display overall data quality summary and health score gauge.

    Args:
        all_reports: Validation reports for each sport.
    """
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
                    (passed_checks / total_checks * PERCENTAGE_MULTIPLIER)
                    if total_checks > 0
                    else 0
                ),
            }
        )

    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True)

    fig = px.bar(
        summary_df,
        x="Sport",
        y="Health Score",
        title="Data Quality Health Score (%)",
        color="Health Score",
        color_continuous_scale="RdYlGn",
        range_y=[0, HEALTH_SCORE_MAX],
    )
    st.plotly_chart(fig, use_container_width=True)


def _display_detailed_validation_reports(all_reports: Dict[str, Any]) -> None:
    """Display detailed validation reports for each sport.

    Args:
        all_reports: Validation reports for each sport.
    """
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


def data_quality_page():
    """Data quality monitoring dashboard."""
    st.title("🔍 Data Quality Dashboard")

    # Run validations
    all_reports = _run_data_validations(["nhl", "mlb", "nfl"])
    if not all_reports:
        return

    # Summary metrics
    _display_data_quality_summary(all_reports)

    # Detailed reports
    _display_detailed_validation_reports(all_reports)


def clv_analysis_page():
    """Display CLV (Closing Line Value) analysis dashboard."""
    clv_data = _load_clv_data()
    if clv_data is None:
        return

    _display_overall_clv_metrics(clv_data)
    _display_clv_by_sport(clv_data)
    _display_clv_chart("distribution")
    _display_clv_vs_win_rate_correlation()
    _display_clv_chart("trend_over_time")


def _load_clv_data() -> Optional[Dict[str, Any]]:
    """Load CLV data from CLV tracker.

    Returns:
        Optional[Dict[str, Any]]: CLV analysis data or None if unavailable.
    """
    try:
        from plugins.clv_tracker import CLVTracker
    except ImportError:
        st.error("CLV tracker module not available.")
        return None

    tracker = CLVTracker()
    clv_data = tracker.analyze_clv(days_back=CLV_ANALYSIS_DAYS_DEFAULT)

    if clv_data.get("num_bets", 0) == 0:
        st.warning(
            "No CLV data available. CLV data needs to be backfilled from historical betting lines."
        )
        return None

    return clv_data


def _display_overall_clv_metrics(clv_data: Dict[str, Any]) -> None:
    """Display overall CLV metrics in a 4-column layout.

    Args:
        clv_data: CLV analysis data dictionary.
    """
    col1, col2, col3, col4 = st.columns(CLV_METRIC_COLUMNS)
    with col1:
        st.metric("Total Bets with CLV", clv_data["num_bets"])
    with col2:
        st.metric("Average CLV", f"{clv_data['avg_clv']:+.2%}")
    with col3:
        st.metric("Positive CLV %", f"{clv_data['positive_clv_pct']:.1f}%")
    with col4:
        edge_indicator = "✅" if clv_data["avg_clv"] > 0 else "❌"
        st.metric("Beating Market", edge_indicator)


def _display_clv_by_sport(clv_data: Dict[str, Any]) -> None:
    """Display CLV performance by sport as a bar chart.

    Args:
        clv_data: CLV analysis data dictionary.
    """
    sport_clv_df = pd.DataFrame(clv_data["by_sport"])
    _render_plotly_chart(
        df=sport_clv_df,
        config=ChartConfig(
            chart_type="bar",
            chart_kwargs={
                "x": "sport",
                "y": "avg_clv",
                "title": "Average CLV by Sport",
                "color": "avg_clv",
                "color_continuous_scale": "RdYlGn",
            },
            title="CLV Performance by Sport",
            add_hline=0,
        ),
    )


def _display_clv_analysis(
    query: str,
    config: ChartConfig,
    error_message: str,
) -> None:
    """Display CLV analysis chart with given configuration.

    Args:
        query: SQL query to fetch CLV data
        config: Chart configuration
        error_message: Error message to display if query fails
    """
    _render_query_chart(
        query=query,
        config=config,
    )


_CLV_ANALYSIS_CONFIGS = {
    "distribution": {
        "query": """
            SELECT clv FROM placed_bets
            WHERE clv IS NOT NULL
            ORDER BY clv
        """,
        "config": ChartConfig(
            chart_type="histogram",
            chart_kwargs={
                "nbins": 50,
                "labels": {"clv": "CLV (%)"},
            },
            add_vline=0,
        ),
        "error_message": "Error loading CLV distribution",
    },
    "trend_over_time": {
        "query": """
            SELECT
                DATE_TRUNC('month', placed_date) as month,
                COUNT(*) as num_bets,
                AVG(clv) as avg_clv,
                SUM(CASE WHEN clv > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as positive_pct
            FROM placed_bets
            WHERE clv IS NOT NULL AND status IN ('won', 'lost')
            GROUP BY DATE_TRUNC('month', placed_date)
            ORDER BY month
        """,
        "config": ChartConfig(
            chart_type="line",
            title="CLV Trend Over Time",
            chart_kwargs={
                "x": "month",
                "y": "avg_clv",
                "title": "Average CLV Over Time",
                "markers": True,
            },
            add_hline=0,
        ),
        "error_message": "Error loading CLV time series",
    },
}


def _display_clv_chart(config_key: str) -> None:
    """Display CLV chart based on configuration key.

    Args:
        config_key: Key from _CLV_ANALYSIS_CONFIGS dictionary
    """
    if config_key not in _CLV_ANALYSIS_CONFIGS:
        st.error(f"Invalid CLV chart configuration key: {config_key}")
        return

    config_data = _CLV_ANALYSIS_CONFIGS[config_key]
    _display_clv_analysis(
        query=config_data["query"],
        config=config_data["config"],
        error_message=config_data["error_message"],
    )


def _display_clv_vs_win_rate_correlation() -> None:
    """Display correlation between CLV categories and actual win rates."""
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


def _load_ev_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load EV data from placed bets table.

    Returns:
        Tuple of (ev_df, ev_with_data) where:
        - ev_df: All settled bets with cost > 0
        - ev_with_data: Subset with expected_value not null
    """
    ev_query = """
        SELECT
            sport,
            placed_date,
            ticker,
            cost_dollars,
            profit_dollars,
            elo_prob,
            market_prob,
            edge,
            expected_value,
            kelly_fraction,
            status
        FROM placed_bets
        WHERE status IN ('won', 'lost')
          AND cost_dollars > 0
        ORDER BY placed_date DESC
    """

    try:
        ev_df = default_db.fetch_df(ev_query)
    except Exception as e:
        st.error(f"Error loading EV data: {e}")
        return pd.DataFrame(), pd.DataFrame()

    if ev_df.empty:
        st.warning("No settled bets with EV data available.")
        return pd.DataFrame(), pd.DataFrame()

    # Calculate actual ROI
    ev_df["actual_roi"] = ev_df["profit_dollars"] / ev_df["cost_dollars"]

    # Filter to bets with EV data
    ev_with_data = ev_df[ev_df["expected_value"].notna()].copy()

    return ev_df, ev_with_data


def _display_overall_ev_metrics(
    ev_df: pd.DataFrame, ev_with_data: pd.DataFrame
) -> None:
    """Display overall EV performance metrics."""
    st.subheader("Overall EV Performance")

    total_staked = ev_df["cost_dollars"].sum()
    total_profit = ev_df["profit_dollars"].sum()
    overall_roi = total_profit / total_staked if total_staked > 0 else 0

    col1, col2, col3, col4 = st.columns(EV_METRIC_COLUMNS)
    with col1:
        st.metric("Total Bets", len(ev_df))
    with col2:
        st.metric("Total Staked", f"${total_staked:,.2f}")
    with col3:
        st.metric("Total Profit", f"${total_profit:,.2f}")
    with col4:
        st.metric("Actual ROI", f"{overall_roi:.2%}")

    if not ev_with_data.empty:
        avg_predicted_ev = ev_with_data["expected_value"].mean()
        st.metric(
            "Avg Predicted EV",
            f"{avg_predicted_ev:.2%}",
            delta=f"{avg_predicted_ev - overall_roi:+.2%} vs actual",
            help="Difference between predicted EV and actual ROI (negative = conservative, positive = overconfident)",
        )


def _calculate_sport_ev_stats(ev_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate sport-level EV performance statistics.

    Args:
        ev_df: DataFrame containing EV data.

    Returns:
        pd.DataFrame: Aggregated sport-level statistics.
    """
    sport_ev = (
        ev_df.groupby("sport")
        .agg(
            {
                "cost_dollars": "sum",
                "profit_dollars": "sum",
                "expected_value": "mean",
                "ticker": "count",
            }
        )
        .reset_index()
    )
    sport_ev.columns = ["sport", "staked", "profit", "avg_ev", "num_bets"]
    sport_ev["actual_roi"] = sport_ev["profit"] / sport_ev["staked"]
    sport_ev["calibration_error"] = sport_ev["avg_ev"] - sport_ev["actual_roi"]

    # Replace NaN with 0 for sports without EV predictions
    return sport_ev.fillna(0)


def _render_ev_by_sport_chart(sport_ev: pd.DataFrame) -> None:
    """Render the ROI vs Predicted EV comparison chart.

    Args:
        sport_ev: DataFrame with aggregated sport statistics.
    """
    fig = px.bar(
        sport_ev,
        x="sport",
        y=["actual_roi", "avg_ev"],
        title="Actual ROI vs Predicted EV by Sport",
        barmode="group",
        labels={"value": "Return %", "variable": "Metric"},
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_ev_by_sport_table(sport_ev: pd.DataFrame) -> None:
    """Render the detailed sport-level performance table.

    Args:
        sport_ev: DataFrame with aggregated sport statistics.
    """
    sport_display = sport_ev[
        [
            "sport",
            "num_bets",
            "staked",
            "profit",
            "actual_roi",
            "avg_ev",
            "calibration_error",
        ]
    ].copy()
    sport_display.columns = [
        "Sport",
        "Bets",
        "Staked ($)",
        "Profit ($)",
        "Actual ROI",
        "Predicted EV",
        "Calibration Error",
    ]
    st.dataframe(
        sport_display.style.format(
            {
                "Staked ($)": "${:,.2f}",
                "Profit ($)": "${:,.2f}",
                "Actual ROI": "{:.2%}",
                "Predicted EV": "{:.2%}",
                "Calibration Error": "{:+.2%}",
            }
        ),
        use_container_width=True,
    )


def _display_ev_by_sport(ev_df: pd.DataFrame) -> None:
    """Display EV performance analysis by sport."""
    st.subheader("EV Performance by Sport")
    sport_ev = _calculate_sport_ev_stats(ev_df)
    _render_ev_by_sport_chart(sport_ev)
    _render_ev_by_sport_table(sport_ev)


def _display_ev_distribution(ev_with_data: pd.DataFrame) -> None:
    """Display histogram of EV distribution."""
    _render_plotly_chart(
        df=ev_with_data,
        config=ChartConfig(
            chart_type="histogram",
            chart_kwargs={
                "x": "expected_value",
                "nbins": EV_HISTOGRAM_BINS,
                "title": "Distribution of Predicted Expected Values",
                "labels": {"expected_value": "Expected Value (%)"},
            },
            title="EV Distribution",
            add_vline=0,
        ),
    )


def _display_ev_calibration_by_bucket(ev_with_data: pd.DataFrame) -> None:
    """Display EV calibration analysis by bucket."""
    if ev_with_data.empty:
        return

    st.subheader("EV Calibration by Bucket")
    st.caption("Are bets with higher predicted EV actually returning more?")

    # Create EV buckets
    ev_with_data["ev_bucket"] = pd.cut(
        ev_with_data["expected_value"],
        bins=EV_BUCKET_BINS,
        labels=EV_BUCKET_LABELS,
    )

    # Calculate bucket statistics
    bucket_stats = (
        ev_with_data.groupby("ev_bucket", observed=True)
        .agg(
            {
                "cost_dollars": "sum",
                "profit_dollars": "sum",
                "expected_value": "mean",
                "ticker": "count",
            }
        )
        .reset_index()
    )
    bucket_stats.columns = ["bucket", "staked", "profit", "avg_ev", "num_bets"]
    bucket_stats["actual_roi"] = bucket_stats["profit"] / bucket_stats["staked"]

    # Display bar chart
    fig = px.bar(
        bucket_stats,
        x="bucket",
        y=["actual_roi", "avg_ev"],
        title="Actual vs Predicted Return by EV Bucket",
        barmode="group",
        labels={"value": "Return %", "bucket": "EV Bucket"},
    )
    st.plotly_chart(fig, use_container_width=True)


def _display_weekly_ev_trend(ev_df: pd.DataFrame) -> None:
    """Display weekly EV trend over time."""
    if ev_df.empty:
        return

    st.subheader("EV Trend Over Time")

    # Calculate weekly aggregates
    ev_df["week"] = pd.to_datetime(ev_df["placed_date"]).dt.to_period("W").astype(str)
    weekly_ev = (
        ev_df.groupby("week")
        .agg({"cost_dollars": "sum", "profit_dollars": "sum", "expected_value": "mean"})
        .reset_index()
    )
    weekly_ev["actual_roi"] = weekly_ev["profit_dollars"] / weekly_ev["cost_dollars"]

    # Display line chart
    fig = px.line(
        weekly_ev,
        x="week",
        y=["actual_roi", "expected_value"],
        title="Weekly Actual ROI vs Predicted EV",
        markers=True,
        labels={"value": "Return %", "week": "Week"},
    )
    fig.add_hline(y=0, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)


def _display_ev_bet_details(ev_df: pd.DataFrame) -> None:
    """Display detailed bet data in expandable section."""
    if ev_df.empty:
        return

    st.subheader("Bet Details")
    with st.expander("View Individual Bets"):
        display_cols = [
            "placed_date",
            "sport",
            "ticker",
            "cost_dollars",
            "profit_dollars",
            "elo_prob",
            "market_prob",
            "edge",
            "expected_value",
            "status",
        ]
        available_cols = [c for c in display_cols if c in ev_df.columns]
        st.dataframe(
            ev_df[available_cols].sort_values("placed_date", ascending=False),
            use_container_width=True,
            height=SMALL_DATAFRAME_HEIGHT,
        )


def ev_analysis_page():
    """Expected Value (EV) analysis dashboard - compares predicted vs actual returns."""
    st.title("📊 Expected Value Analysis")
    st.caption("Compare predicted EV to actual returns to validate model calibration")

    # Load EV data
    ev_df, ev_with_data = _load_ev_data()

    if ev_df.empty:
        return  # Warning already shown in _load_ev_data

    # Display all analysis sections
    _display_overall_ev_metrics(ev_df, ev_with_data)
    _display_ev_by_sport(ev_df)
    _display_ev_distribution(ev_with_data)
    _display_ev_calibration_by_bucket(ev_with_data)
    _display_weekly_ev_trend(ev_df)
    _display_ev_bet_details(ev_df)


def _get_default_elo_parameters(league: str) -> tuple[float, float]:
    """Get default K-factor and home advantage for a given league.

    Args:
        league: Sport league name

    Returns:
        Tuple of (default_k, default_home)
    """
    # Mapping of league to (k_factor, home_advantage)
    league_params = {
        "NHL": (DEFAULT_K_FACTOR, DEFAULT_HOME_ADVANTAGE_NHL),
        "NBA": (DEFAULT_K_FACTOR, DEFAULT_HOME_ADVANTAGE_NBA),
        "NFL": (DEFAULT_K_FACTOR, DEFAULT_HOME_ADVANTAGE_NFL),
        "EPL": (DEFAULT_K_FACTOR, DEFAULT_HOME_ADVANTAGE_SOCCER),
        "Ligue1": (DEFAULT_K_FACTOR, DEFAULT_HOME_ADVANTAGE_SOCCER),
        "Tennis": (DEFAULT_K_FACTOR_TENNIS, DEFAULT_HOME_ADVANTAGE_TENNIS),
        "NCAAB": (DEFAULT_K_FACTOR, DEFAULT_HOME_ADVANTAGE_COLLEGE_BASKETBALL),
        "WNCAAB": (DEFAULT_K_FACTOR, DEFAULT_HOME_ADVANTAGE_COLLEGE_BASKETBALL),
    }

    return league_params.get(league, (DEFAULT_K_FACTOR, DEFAULT_HOME_ADVANTAGE_GENERIC))


def _run_glicko2_simulation_if_enabled(
    enable_glicko2: bool,
    filtered_data: pd.DataFrame,
    config: SimulationConfig,
    simulated_data: pd.DataFrame,
) -> pd.DataFrame:
    """Run Glicko-2 simulation if enabled for the league.

    Args:
        enable_glicko2: Whether Glicko-2 is enabled
        filtered_data: Filtered game data
        config: Simulation configuration
        simulated_data: DataFrame with Elo simulation results

    Returns:
        Updated simulated_data with Glicko-2 probabilities if applicable
    """
    if not enable_glicko2 or config.league not in ["NBA", "NHL", "MLB", "NFL"]:
        simulated_data["glicko2_prob"] = None
        return simulated_data

    with st.spinner("Running Glicko-2 Simulation..."):
        simulated_data_glicko2 = run_glicko2_simulation(filtered_data, config)
        if "glicko2_prob" in simulated_data_glicko2.columns:
            simulated_data["glicko2_prob"] = simulated_data_glicko2["glicko2_prob"]
        else:
            simulated_data["glicko2_prob"] = None

    return simulated_data


def _get_elo_sidebar_configuration(raw_data: pd.DataFrame, league: str):
    """Get simulation configuration from sidebar.

    Returns:
        tuple: (selected_season, cutoff_date, k_factor, home_adv,
                enable_glicko2, glicko2_tau, glicko2_home_adv)
    """
    # Date and season selection
    min_date = raw_data["game_date"].min().date()
    max_date = raw_data["game_date"].max().date()
    available_seasons = sorted(raw_data["season"].unique().tolist(), reverse=True)
    available_seasons.insert(0, "All Time")

    selected_season = st.sidebar.selectbox("Season", available_seasons)
    cutoff_date = st.sidebar.date_input(
        "Analysis Up To Date", value=max_date, min_value=min_date, max_value=max_date
    )

    # Get default parameters
    default_k, default_home = _get_default_elo_parameters(league)

    # Elo parameters
    with st.sidebar.expander("Elo Parameters"):
        k_factor = st.number_input("K-Factor", value=default_k)
        home_adv = st.number_input("Home Advantage", value=default_home)

    # Glicko-2 parameters
    with st.sidebar.expander("Glicko-2 Parameters"):
        enable_glicko2 = st.checkbox("Enable Glicko-2 Comparison", value=True)
        glicko2_tau = st.slider(
            "System Volatility (τ)",
            GLICKO2_TAU_MIN,
            GLICKO2_TAU_MAX,
            GLICKO2_TAU_DEFAULT,
            GLICKO2_TAU_STEP,
        )
        glicko2_home_adv = st.number_input(
            "Home Advantage (Glicko-2)", value=default_home
        )

    return (
        selected_season,
        cutoff_date,
        k_factor,
        home_adv,
        enable_glicko2,
        glicko2_tau,
        glicko2_home_adv,
    )


def _filter_elo_data(
    raw_data: pd.DataFrame, selected_season: str, cutoff_date: datetime.date
) -> pd.DataFrame:
    """Filter raw data based on season and cutoff date."""
    if selected_season != "All Time":
        filtered_data = raw_data[raw_data["season"] == selected_season].copy()
    else:
        filtered_data = raw_data.copy()

    filtered_data = filtered_data[
        filtered_data["game_date"].dt.date <= cutoff_date
    ].copy()

    return filtered_data


def elo_analysis_page() -> None:
    """Render the Elo Analysis dashboard page."""
    league = _select_league_from_sidebar()

    raw_data = _load_league_data(league)
    if raw_data.empty:
        return

    config = _get_elo_configuration(raw_data, league)

    filtered_data = _filter_elo_data_by_config(raw_data, config)
    if filtered_data.empty:
        return

    simulated_data = _run_elo_simulations(filtered_data, league, config)

    metrics = _calculate_elo_metrics(simulated_data)

    _render_elo_dashboard(league, config, simulated_data, metrics)


def _select_league_from_sidebar() -> str:
    """Select league from sidebar dropdown.

    Returns:
        Selected league string.
    """
    st.sidebar.title("Configuration")
    return st.sidebar.selectbox(
        "Select League",
        [
            "MLB",
            "NHL",
            "NFL",
            "NBA",
            "EPL",
            "Tennis",
            "NCAAB",
            "WNCAAB",
            "Ligue1",
            "Unrivaled",
            "CBA",
        ],
    )


def _load_league_data(league: str) -> pd.DataFrame:
    """Load data for the selected league.

    Args:
        league: Selected league string.

    Returns:
        DataFrame with league data, or empty DataFrame if no data found.
    """
    with st.spinner(f"Loading {league} data..."):
        raw_data = load_data(league)

    if raw_data.empty:
        st.warning(
            f"No data found for {league}. Please ensure data is backfilled into unified_games."
        )
        st.stop()

    return raw_data


def _get_elo_configuration(raw_data: pd.DataFrame, league: str) -> dict:
    """Get Elo configuration from sidebar.

    Args:
        raw_data: DataFrame with league data.
        league: Selected league string.

    Returns:
        Dictionary with configuration values.
    """
    (
        selected_season,
        cutoff_date,
        k_factor,
        home_adv,
        enable_glicko2,
        glicko2_tau,
        glicko2_home_adv,
    ) = _get_elo_sidebar_configuration(raw_data, league)

    return {
        "selected_season": selected_season,
        "cutoff_date": cutoff_date,
        "k_factor": k_factor,
        "home_adv": home_adv,
        "enable_glicko2": enable_glicko2,
        "glicko2_tau": glicko2_tau,
        "glicko2_home_adv": glicko2_home_adv,
    }


def _filter_elo_data_by_config(raw_data: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Filter data based on configuration.

    Args:
        raw_data: DataFrame with league data.
        config: Configuration dictionary.

    Returns:
        Filtered DataFrame, or empty DataFrame if no games match criteria.
    """
    filtered_data = _filter_elo_data(
        raw_data, config["selected_season"], config["cutoff_date"]
    )

    if filtered_data.empty:
        st.warning("No games found matching criteria.")
        st.stop()

    return filtered_data


def _run_elo_simulations(
    filtered_data: pd.DataFrame, league: str, config: dict
) -> pd.DataFrame:
    """Run Elo and Glicko-2 simulations.

    Args:
        filtered_data: Filtered DataFrame with game data.
        league: Selected league string.
        config: Configuration dictionary.

    Returns:
        DataFrame with simulation results.
    """
    # Run Elo simulation
    with st.spinner("Running Elo Simulation..."):
        elo_config = SimulationConfig(
            league=league, home_adv=config["home_adv"], k_factor=config["k_factor"]
        )
        simulated_data = run_elo_simulation(filtered_data, elo_config)

    # Run Glicko-2 simulation if enabled
    glicko_config = SimulationConfig(
        league=league, home_adv=config["glicko2_home_adv"], tau=config["glicko2_tau"]
    )
    simulated_data = _run_glicko2_simulation_if_enabled(
        config["enable_glicko2"],
        filtered_data,
        glicko_config,
        simulated_data,
    )

    return simulated_data


def _calculate_elo_metrics(simulated_data: pd.DataFrame) -> dict:
    """Calculate Elo performance metrics.

    Args:
        simulated_data: DataFrame with simulation results.

    Returns:
        Dictionary with calculated metrics.
    """
    decile_stats = calculate_deciles(simulated_data)
    gain_curve = calculate_cumulative_gain(simulated_data)
    roi_matrix = calculate_decile_probability_roi_matrix(simulated_data)

    return {
        "decile_stats": decile_stats,
        "gain_curve": gain_curve,
        "roi_matrix": roi_matrix,
    }


def _render_elo_dashboard(
    league: str, config: dict, simulated_data: pd.DataFrame, metrics: dict
) -> None:
    """Render the Elo analysis dashboard.

    Args:
        league: Selected league string.
        config: Configuration dictionary.
        simulated_data: DataFrame with simulation results.
        metrics: Dictionary with calculated metrics.
    """
    _render_elo_analysis_dashboard(
        league=league,
        selected_season=config["selected_season"],
        cutoff_date=config["cutoff_date"],
        simulated_data=simulated_data,
        decile_stats=metrics["decile_stats"],
        gain_curve=metrics["gain_curve"],
        roi_matrix=metrics["roi_matrix"],
    )


def _render_elo_analysis_dashboard(
    league: str,
    selected_season: str,
    cutoff_date: datetime.date,
    simulated_data: pd.DataFrame,
    decile_stats: pd.DataFrame,
    gain_curve: pd.DataFrame,
    roi_matrix: pd.DataFrame,
) -> None:
    """Render the Elo analysis dashboard UI.

    Args:
        league: Sport league name
        selected_season: Selected season or "All Time"
        cutoff_date: Analysis cutoff date
        simulated_data: DataFrame with simulation results
        decile_stats: Decile performance statistics
        gain_curve: Cumulative gain curve data
        roi_matrix: ROI matrix data
    """
    # Title and header
    st.title(f"{league} Betting Analytics Dashboard")
    st.markdown(
        f"Analysis for **{selected_season}** up to **{cutoff_date}** ({len(simulated_data)} games)"
    )

    # KPIs
    _render_elo_kpis(simulated_data, decile_stats)

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "Lift Chart",
            "Calibration",
            "ROI Analysis",
            "Cumulative Gain",
            "Elo vs Glicko-2",
            "Game Details",
            "Season Analysis",
        ]
    )

    with tab1:
        _render_lift_chart_tab(decile_stats)

    with tab2:
        _render_calibration_tab(decile_stats)

    with tab3:
        _render_roi_analysis(decile_stats)

    with tab4:
        _render_gain_curve_tab(gain_curve)

    with tab5:
        _render_elo_vs_glicko2_comparison(simulated_data)

    with tab6:
        _render_detailed_statistics(decile_stats, roi_matrix)

    with tab7:
        _render_season_timing_analysis(simulated_data)


def _render_chart_tab(
    df: pd.DataFrame,
    config: ChartConfig,
) -> None:
    """Render a chart tab with standardized configuration.

    Args:
        df: DataFrame containing the data to plot
        config: Chart configuration object
    """
    _render_plotly_chart(df=df, config=config)


# Chart configurations for common dashboard visualizations
_CHART_CONFIGS: Dict[str, Dict[str, Any]] = {
    "lift_chart": {
        "chart_type": "bar",
        "chart_kwargs": {
            "x": "Decile",
            "y": "Lift",
            "color": "Lift",
            "color_continuous_scale": "RdYlGn",
        },
        "title": "Lift by Elo Probability Decile",
        "add_hline": 1.0,
    },
    "calibration_plot": {
        "chart_type": "scatter",
        "chart_kwargs": {"x": "Avg Prob", "y": "Win Rate", "size": "Games"},
        "title": "Calibration Plot",
        "add_diagonal": True,
    },
    "gain_curve": {
        "chart_type": "line",
        "chart_kwargs": {"x": "pct_games", "y": "pct_wins_captured"},
        "title": "Cumulative Gain Curve",
        "add_diagonal": True,
    },
}


def _render_standard_chart_tab(
    df: pd.DataFrame, chart_type: str, **kwargs: Any
) -> None:
    """
    Render a standard chart tab using predefined configuration.

    Args:
        df: DataFrame containing the data to plot
        chart_type: Type of chart to render ("lift_chart", "calibration_plot", "gain_curve")
        **kwargs: Optional overrides for chart configuration
    """
    if chart_type not in _CHART_CONFIGS:
        raise ValueError(
            f"Unknown chart type: {chart_type}. "
            f"Available types: {list(_CHART_CONFIGS.keys())}"
        )

    config_dict = _CHART_CONFIGS[chart_type].copy()
    config_dict.update(kwargs)  # Allow overrides

    # Create ChartConfig object from configuration dictionary
    chart_config = ChartConfig(
        chart_type=str(config_dict["chart_type"]),
        chart_kwargs=dict(config_dict["chart_kwargs"]),
        title=str(config_dict["title"]),
        add_hline=config_dict.get("add_hline"),
        add_diagonal=bool(config_dict.get("add_diagonal", False)),
    )

    _render_chart_tab(df=df, config=chart_config)


def _render_lift_chart_tab(decile_stats: pd.DataFrame) -> None:
    """Render the Lift Chart tab content.

    Args:
        decile_stats: Decile performance statistics
    """
    _render_standard_chart_tab(df=decile_stats, chart_type="lift_chart")


def _render_calibration_tab(decile_stats: pd.DataFrame) -> None:
    """Render the Calibration Plot tab content.

    Args:
        decile_stats: Decile performance statistics
    """
    _render_standard_chart_tab(df=decile_stats, chart_type="calibration_plot")


def _render_gain_curve_tab(gain_curve: pd.DataFrame) -> None:
    """Render the Cumulative Gain Curve tab content.

    Args:
        gain_curve: Cumulative gain curve data
    """
    _render_standard_chart_tab(df=gain_curve, chart_type="gain_curve")


def _render_elo_kpis(simulated_data: pd.DataFrame, decile_stats: pd.DataFrame) -> None:
    """Render Elo analysis KPIs."""
    cols = st.columns(ELO_METRIC_COLUMNS)
    baseline_win_rate = simulated_data["home_win"].mean()

    if not decile_stats.empty:
        top_decile = decile_stats.iloc[-1]
        cols[0].metric("Baseline Win Rate", f"{baseline_win_rate:.1%}")
        cols[1].metric("Top Decile Win Rate", f"{top_decile['Win Rate']:.1%}")
        cols[2].metric("Top Decile Lift", f"{top_decile['Lift']:.2f}x")
        cols[3].metric("Top Decile ROI (-110)", top_decile["ROI (-110)"])


def _render_roi_analysis(decile_stats: pd.DataFrame) -> None:
    """Render ROI analysis visualization."""
    st.header("ROI by Decile")
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


def _render_elo_vs_glicko2_comparison(simulated_data: pd.DataFrame) -> None:
    """Render Elo vs Glicko-2 comparison."""
    st.header("Elo vs Glicko-2 Comparison")

    if "glicko2_prob" not in simulated_data.columns:
        st.info("Glicko-2 simulation data not available for this league.")
        return

    if simulated_data["glicko2_prob"].notna().any():
        # Ensure elo_prob exists before comparison
        if "elo_prob" not in simulated_data.columns:
            st.error("Elo probability data is missing. Cannot compare models.")
            return

        comp_df = simulated_data[simulated_data["glicko2_prob"].notna()].copy()

        # Check for required columns in comp_df
        if "elo_prob" not in comp_df.columns or "home_win" not in comp_df.columns:
            st.error("Required columns for comparison are missing.")
            return

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


def _render_detailed_statistics(
    decile_stats: pd.DataFrame, roi_matrix: pd.DataFrame
) -> None:
    """Render detailed statistics tab."""
    st.header("Game Details")
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
            st.info("ROI matrix requires sufficient data across probability spectrum.")


def _render_season_timing_analysis(simulated_data: pd.DataFrame) -> None:
    """Render season timing analysis."""
    st.header("Season Analysis")
    if not simulated_data.empty:
        viz_df = simulated_data.copy()
        viz_df["season_rank"] = viz_df.groupby("season")["game_date"].rank(
            method="dense"
        )
        season_max = viz_df.groupby("season")["season_rank"].transform("max")
        viz_df["Season Progress (%)"] = (viz_df["season_rank"] / season_max) * 100
        viz_df["Progress Bin"] = (
            pd.cut(viz_df["Season Progress (%)"], bins=DECILE_COUNT, labels=False) + 1
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
        # timing_df variable was created but never used - removed to fix lint warning


# ---------------------------------------------------------------------------
# Diagnostic Report page (TODO-005 / TODO-007)
# ---------------------------------------------------------------------------

# Columns to display in the per-sport diagnostic summary table
_DIAGNOSTIC_DISPLAY_COLUMNS = [
    "sport",
    "settled_bets",
    "roi",
    "real_clv",
    "p_value",
    "recommendation",
    "elo_replay_divergence",
]

# Human-readable labels for the per-sport table
_DIAGNOSTIC_COLUMN_LABELS: Dict[str, str] = {
    "sport": "Sport",
    "settled_bets": "Bets",
    "roi": "ROI",
    "real_clv": "Real CLV",
    "p_value": "p-value",
    "recommendation": "Recommendation",
    "elo_replay_divergence": "Elo Divergence",
}


def _load_diagnostic_data() -> pd.DataFrame:
    """Load the most recent diagnostic results from the database.

    Queries the ``diagnostic_results`` table and returns one row per sport
    (the most recent run).

    Returns:
        DataFrame with diagnostic metrics, or an empty DataFrame on error.
    """
    query = """
        SELECT sport, settled_bets, roi, real_clv, p_value,
               recommendation, elo_replay_divergence,
               timing_roi_under_2hr, timing_roi_over_8hr,
               bets_with_closing_price, run_date
        FROM diagnostic_results
        ORDER BY run_date DESC
    """
    try:
        df = default_db.fetch_df(query)
        if df is None or df.empty:
            return pd.DataFrame()
        # Keep latest run per sport
        df["run_date"] = pd.to_datetime(df["run_date"], errors="coerce")
        df = df.sort_values("run_date", ascending=False)
        df = df.drop_duplicates(subset=["sport"], keep="first")
        return df
    except Exception:
        return pd.DataFrame()


def _display_diagnostic_summary_metrics(diag_df: pd.DataFrame) -> None:
    """Render top-level summary metrics for the diagnostic page.

    Args:
        diag_df: DataFrame of the latest per-sport diagnostic results.
    """
    last_run = diag_df["run_date"].max() if "run_date" in diag_df.columns else None
    run_label = str(last_run) if last_run is not None and pd.notna(last_run) else "N/A"

    total_sports = len(diag_df)
    continue_count = int((diag_df["recommendation"] == "CONTINUE").sum())
    pause_count = int((diag_df["recommendation"] == "PAUSE").sum())

    avg_divergence = diag_df["elo_replay_divergence"].mean()
    avg_divergence_label = (
        f"{avg_divergence:.1f}" if pd.notna(avg_divergence) else "N/A"
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Last Run", run_label)
    with col2:
        st.metric("Sports Analyzed", total_sports)
    with col3:
        st.metric("✅ CONTINUE / 🛑 PAUSE", f"{continue_count} / {pause_count}")
    with col4:
        st.metric("Avg Elo Replay Divergence", avg_divergence_label)


def _display_diagnostic_table(diag_df: pd.DataFrame) -> None:
    """Render the per-sport qualification gates table.

    Args:
        diag_df: DataFrame of the latest per-sport diagnostic results.
    """
    st.subheader("Per-Sport Qualification Gates")

    available_cols = [c for c in _DIAGNOSTIC_DISPLAY_COLUMNS if c in diag_df.columns]
    display_df = diag_df[available_cols].copy()
    display_df = display_df.rename(columns=_DIAGNOSTIC_COLUMN_LABELS)

    # Format ROI and CLV as percentages
    for pct_col in ("ROI", "Real CLV"):
        if pct_col in display_df.columns:
            display_df[pct_col] = display_df[pct_col].apply(
                lambda v: f"{v:.1%}" if pd.notna(v) else "N/A"
            )

    if "p-value" in display_df.columns:
        display_df["p-value"] = display_df["p-value"].apply(
            lambda v: f"{v:.3f}" if pd.notna(v) else "N/A"
        )

    if "Elo Divergence" in display_df.columns:
        display_df["Elo Divergence"] = display_df["Elo Divergence"].apply(
            lambda v: f"{v:.1f}" if pd.notna(v) else "N/A"
        )

    st.dataframe(display_df, use_container_width=True)


def _display_timing_heatmap() -> None:
    """Render the ROI × Sport × Timing Window heatmap.

    Fetches heatmap data from ``generate_timing_heatmap_data()`` and renders
    a Plotly heatmap with a red-to-green colour scale.
    """
    if generate_timing_heatmap_data is None:
        st.warning("Timing heatmap data unavailable (pnl_diagnostic not importable).")
        return

    heatmap_df = generate_timing_heatmap_data()

    if heatmap_df.empty:
        st.info("No timing data available for heatmap.")
        return

    st.subheader("ROI by Sport × Timing Window")

    # Convert fractional ROI to percentages for display
    plot_df = heatmap_df.multiply(100)

    fig = px.imshow(
        plot_df,
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        labels={"color": "ROI (%)"},
        title="ROI by Sport × Timing Window",
        text_auto=".1f",
    )
    fig.update_layout(
        xaxis_title="Timing Window",
        yaxis_title="Sport",
    )
    st.plotly_chart(fig, use_container_width=True)


def diagnostic_report_page() -> None:
    """Diagnostic Report dashboard page.

    Displays per-sport qualification gates (Bootstrap CI, p-value,
    recommendation), Elo replay divergence, last-run timestamp, a
    "Run Diagnostic" button, and a timing heatmap.
    """
    st.title("🔬 Diagnostic Report")

    # --- Run Diagnostic button ---
    if st.button("▶ Run Diagnostic"):
        if run_diagnostic is None:
            st.error("Diagnostic module not available.")
        else:
            try:
                with st.spinner("Running full P&L diagnostic…"):
                    run_diagnostic()
                st.success("Diagnostic complete. Refresh to see updated results.")
            except Exception as exc:
                st.error(f"Diagnostic failed: {exc}")

    # --- Load data ---
    diag_df = _load_diagnostic_data()

    if diag_df.empty:
        st.warning(
            "No diagnostic results found. "
            "Click '▶ Run Diagnostic' to generate a report."
        )
        return

    # --- Summary metrics row ---
    _display_diagnostic_summary_metrics(diag_df)

    # --- Per-sport qualification table ---
    _display_diagnostic_table(diag_df)

    # --- Timing heatmap ---
    _display_timing_heatmap()


def main():
    """Main dashboard entry point."""
    # Dispatch dictionary mapping page names to their functions
    page_handlers = {
        "Elo Analysis": elo_analysis_page,
        "Betting Performance": betting_performance_page_v2,
        "Financial Performance": financial_performance_page,
        "Data Quality": data_quality_page,
        "CLV Analysis": clv_analysis_page,
        "EV Analysis": ev_analysis_page,
        "Diagnostic Report": diagnostic_report_page,
    }

    page = st.sidebar.radio(
        "📍 Navigation",
        list(page_handlers.keys()),
        index=0,
    )

    # Get and call the appropriate handler function
    handler = page_handlers.get(page, elo_analysis_page)
    handler()


if __name__ == "__main__":
    main()
