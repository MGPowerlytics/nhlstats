import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import duckdb
import sys
import os
from pathlib import Path
from datetime import datetime, date

# Add plugins to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'plugins'))

# Import Elo classes dynamically
try:
    from mlb_elo_rating import MLBEloRating
except ImportError:
    MLBEloRating = None

try:
    from nhl_elo_rating import NHLEloRating
except ImportError:
    NHLEloRating = None
    
try:
    from nfl_elo_rating import NFLEloRating
except ImportError:
    NFLEloRating = None
    
try:
    from nba_elo_rating import NBAEloRating, load_nba_games_from_json
except ImportError:
    NBAEloRating = None

try:
    from epl_elo_rating import EPLEloRating
except ImportError:
    EPLEloRating = None

try:
    from tennis_elo_rating import TennisEloRating
except ImportError:
    TennisEloRating = None

# --- Configuration ---
st.set_page_config(
    page_title="Sports Betting Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions ---

@st.cache_data
def load_data(league, db_path='data/nhlstats.duckdb'):
    """Load game data from DuckDB or JSON based on league."""
    games_df = pd.DataFrame()
    
    if league == 'NHL':
        if not os.path.exists(db_path):
            return pd.DataFrame()
            
        conn = duckdb.connect(db_path, read_only=True)
        query = """
            SELECT 
                game_date,
                season,
                home_team_name as home_team,
                away_team_name as away_team,
                home_score,
                away_score,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM games
            WHERE game_state IN ('FINAL', 'OFF')
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND (game_type = '02' OR game_type = 2) -- Regular season
            ORDER BY game_date
        """
        try:
            games_df = conn.execute(query).fetchdf()
        except Exception as e:
            st.error(f"Error loading NHL data: {e}")
        finally:
            conn.close()
            
    elif league == 'MLB':
        if not os.path.exists(db_path):
            return pd.DataFrame()
            
        conn = duckdb.connect(db_path, read_only=True)
        query = """
            SELECT 
                game_date,
                season,
                home_team,
                away_team,
                home_score,
                away_score,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM mlb_games
            WHERE status = 'Final'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND game_type = 'R' -- Regular season
            ORDER BY game_date
        """
        try:
            games_df = conn.execute(query).fetchdf()
        except Exception as e:
            st.error(f"Error loading MLB data: {e}")
        finally:
            conn.close()

    elif league == 'NFL':
        if not os.path.exists(db_path):
            return pd.DataFrame()
            
        conn = duckdb.connect(db_path, read_only=True)
        query = """
            SELECT 
                game_date,
                season,
                home_team,
                away_team,
                home_score,
                away_score,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM nfl_games
            WHERE status = 'Final'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND game_type = 'REG' -- Regular season
            ORDER BY game_date
        """
        try:
            games_df = conn.execute(query).fetchdf()
        except Exception as e:
            st.error(f"Error loading NFL data: {e}")
        finally:
            conn.close()
            
    elif league == 'NBA':
        try:
            games_df = load_nba_games_from_json()
            if not games_df.empty:
                # Ensure date column is datetime
                games_df['game_date'] = pd.to_datetime(games_df['game_date'])
                # Extract season if not present (simple approximation)
                if 'season' not in games_df.columns:
                    games_df['season'] = games_df['game_date'].apply(lambda d: d.year if d.month > 9 else d.year - 1)
        except Exception as e:
            st.error(f"Error loading NBA data: {e}")
            
    elif league == 'EPL':
        if not os.path.exists(db_path):
            return pd.DataFrame()
            
        conn = duckdb.connect(db_path, read_only=True)
        query = """
            SELECT 
                game_date,
                season,
                home_team,
                away_team,
                home_score,
                away_score,
                result,
                CASE WHEN result = 'H' THEN 1 ELSE 0 END as home_win
            FROM epl_games
            WHERE result IS NOT NULL
            ORDER BY game_date
        """
        try:
            games_df = conn.execute(query).fetchdf()
        except Exception as e:
            st.error(f"Error loading EPL data: {e}")
        finally:
            conn.close()

    elif league == 'Tennis':
        if not os.path.exists(db_path):
            return pd.DataFrame()
            
        conn = duckdb.connect(db_path, read_only=True)
        query = """
            SELECT 
                game_date,
                season,
                winner as home_team, -- Using 'home_team' field for winner for compatibility
                loser as away_team, -- Using 'away_team' field for loser
                1 as home_win, -- Winner always wins in this view
                0 as home_score, -- Placeholder
                0 as away_score  -- Placeholder
            FROM tennis_games
            ORDER BY game_date
        """
        try:
            games_df = conn.execute(query).fetchdf()
            # Randomize "home" (Player A) vs "away" (Player B) for proper Elo simulation
            # Otherwise we always predict Winner beats Loser, which biases validation
            # We will shuffle them in Python
        except Exception as e:
            st.error(f"Error loading Tennis data: {e}")
        finally:
            conn.close()

    # Ensure proper types
    if not games_df.empty:
        games_df['game_date'] = pd.to_datetime(games_df['game_date'])
        
    return games_df

@st.cache_data
def run_elo_simulation(games_df, league, k_factor, home_adv):
    """Run Elo simulation for the selected league."""
    if games_df.empty:
        return games_df
        
    # Tennis Specific: Randomize winner/loser positions to avoid bias
    # because database only has (Winner, Loser) columns, so "Home" is always Winner.
    if league == 'Tennis':
        # Create a mask for swapping
        np.random.seed(42) # Consistent seed
        swap_mask = np.random.random(len(games_df)) > 0.5
        
        # Make copy to avoid SettingWithCopy warning
        games_df = games_df.copy()
        
        # Apply swap
        # If swap=True: Home=Loser, Away=Winner, HomeWin=0
        # If swap=False: Home=Winner, Away=Loser, HomeWin=1 (Default)
        
        real_winners = games_df['home_team'].copy() # Currently holds winners
        real_losers = games_df['away_team'].copy() # Currently holds losers
        
        games_df.loc[swap_mask, 'home_team'] = real_losers[swap_mask]
        games_df.loc[swap_mask, 'away_team'] = real_winners[swap_mask]
        games_df.loc[swap_mask, 'home_win'] = 0
    
    # Initialize Elo system
    if league == 'MLB' and MLBEloRating:
        elo = MLBEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == 'NHL' and NHLEloRating:
        elo = NHLEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == 'NFL' and NFLEloRating:
        elo = NFLEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == 'NBA' and NBAEloRating:
        elo = NBAEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == 'EPL' and EPLEloRating:
        elo = EPLEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == 'Tennis' and TennisEloRating:
        elo = TennisEloRating(k_factor=k_factor) # No home advantage in tennis usually
    else:
        st.error(f"Elo system for {league} not available.")
        return games_df
        
    probs = []
    
    # Process games
    # We rely on games_df being sorted by date already
    for _, game in games_df.iterrows():
        # Predict
        prob = elo.predict(game['home_team'], game['away_team'])
        probs.append(prob)
        
        # Update
        if league == 'NBA':
            elo.update(game['home_team'], game['away_team'], game['home_win'])
        elif league == 'NHL':
            elo.update(game['home_team'], game['away_team'], game['home_win'])
        elif league == 'EPL':
             elo.update(game['home_team'], game['away_team'], game['result'])
        elif league == 'Tennis':
             # Update with actual winner/loser
             winner = game['home_team'] if game['home_win'] == 1 else game['away_team']
             loser = game['away_team'] if game['home_win'] == 1 else game['home_team']
             elo.update(winner, loser)
        elif league == 'MLB' or league == 'NFL':
             elo.update(game['home_team'], game['away_team'], 
                        game['home_score'], game['away_score'])
                        
    games_df['elo_prob'] = probs
    return games_df

def calculate_deciles(df):
    """Calculate lift/gain metrics by decile."""
    if df.empty or 'elo_prob' not in df.columns:
        return pd.DataFrame()
        
    df = df.copy()
    try:
        df['decile'] = pd.qcut(df['elo_prob'], q=10, labels=False, duplicates='drop') + 1
    except ValueError:
        df['decile'] = pd.cut(df['elo_prob'], bins=10, labels=False) + 1
    
    baseline = df['home_win'].mean()
    results = []
    
    for decile in sorted(df['decile'].unique()):
        subset = df[df['decile'] == decile]
        games = len(subset)
        wins = subset['home_win'].sum()
        win_rate = wins / games if games > 0 else 0
        avg_prob = subset['elo_prob'].mean()
        lift = win_rate / baseline if baseline > 0 else 0
        
        # ROI calculation (assuming -110 odds)
        roi = ((win_rate * 0.909) - (1 - win_rate)) * 100
        
        results.append({
            'Decile': decile,
            'Games': games,
            'Wins': wins,
            'Win Rate': win_rate,
            'Avg Prob': avg_prob,
            'Lift': lift,
            'ROI (-110)': roi,
            'Baseline': baseline,
            'Min Prob': subset['elo_prob'].min(),
            'Max Prob': subset['elo_prob'].max()
        })
        
    return pd.DataFrame(results)

def calculate_cumulative_gain(df):
    """Calculate cumulative gain curve data."""
    if df.empty:
        return pd.DataFrame()
        
    df_sorted = df.sort_values('elo_prob', ascending=False)
    df_sorted['cumulative_games'] = np.arange(1, len(df_sorted) + 1)
    df_sorted['cumulative_wins'] = df_sorted['home_win'].cumsum()
    
    df_sorted['pct_games'] = df_sorted['cumulative_games'] / len(df_sorted)
    df_sorted['pct_wins_captured'] = df_sorted['cumulative_wins'] / df_sorted['home_win'].sum()
    
    if len(df_sorted) > 1000:
        return df_sorted.iloc[::int(len(df_sorted)/1000)]
    return df_sorted

# --- Sidebar Controls ---

st.sidebar.title("Configuration")

# League Selection
league = st.sidebar.selectbox("Select League", ["MLB", "NHL", "NFL", "NBA", "EPL", "Tennis"])

# Load Data (Cached)
with st.spinner(f"Loading {league} data..."):
    raw_data = load_data(league)

if raw_data.empty:
    st.warning(f"No data found for {league}. Please ensure data is downloaded and DB loaded.")
    st.stop()

# Date Filtering
min_date = raw_data['game_date'].min().date()
max_date = raw_data['game_date'].max().date()
available_seasons = sorted(raw_data['season'].unique().tolist(), reverse=True)
available_seasons.insert(0, "All Time")

selected_season = st.sidebar.selectbox("Season", available_seasons)
cutoff_date = st.sidebar.date_input("Analysis Up To Date", value=max_date, min_value=min_date, max_value=max_date)

# Elo Parameters (Advanced)
with st.sidebar.expander("Elo Parameters"):
    default_k = 20
    default_home = 50 # MLB default
    
    if league == 'NHL': default_home = 100
    if league == 'NBA': default_home = 100
    if league == 'NFL': default_home = 65
    if league == 'EPL': default_home = 60
    if league == 'Tennis': 
        default_home = 0
        default_k = 32
    
    k_factor = st.number_input("K-Factor", value=default_k)
    home_adv = st.number_input("Home Advantage", value=default_home)

# --- Data Processing ---

if selected_season != "All Time":
    filtered_data = raw_data[raw_data['season'] == selected_season].copy()
else:
    filtered_data = raw_data.copy()

filtered_data = filtered_data[filtered_data['game_date'].dt.date <= cutoff_date].copy()

if filtered_data.empty:
    st.warning("No games found matching criteria.")
    st.stop()

with st.spinner("Running Elo Simulation..."):
    simulated_data = run_elo_simulation(filtered_data, league, k_factor, home_adv)

decile_stats = calculate_deciles(simulated_data)
gain_curve = calculate_cumulative_gain(simulated_data)

# --- Main Dashboard ---

st.title(f"{league} Betting Analytics Dashboard")
st.markdown(f"Analysis for **{selected_season}** up to **{cutoff_date}** ({len(simulated_data)} games)")

# KPI Row
col1, col2, col3, col4 = st.columns(4)
baseline_win_rate = simulated_data['home_win'].mean()
if not decile_stats.empty:
    top_decile = decile_stats.iloc[-1]
    
    col1.metric("Baseline Win Rate", f"{baseline_win_rate:.1%}")
    col2.metric("Top Decile Win Rate", f"{top_decile['Win Rate']:.1%}", 
                delta=f"{(top_decile['Win Rate'] - baseline_win_rate)*100:.1f} pts")
    col3.metric("Top Decile Lift", f"{top_decile['Lift']:.2f}x")
    col4.metric("Top Decile ROI (-110)", f"{top_decile['ROI (-110)']:.1f}%")

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Lift Chart", "Calibration", "ROI Analysis", "Cumulative Gain", "Details", "Season Timing"])

with tab1:
    st.header("Lift by Probability Decile")
    if not decile_stats.empty:
        fig = px.bar(decile_stats, x='Decile', y='Lift', 
                     color='Lift', color_continuous_scale='RdYlGn',
                     hover_data=['Win Rate', 'Games', 'Avg Prob'])
        fig.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="Baseline")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Values > 1.0 indicate the model successfully identifies games with higher-than-average win probability.")

with tab2:
    st.header("Model Calibration")
    if not decile_stats.empty:
        fig = px.scatter(decile_stats, x='Avg Prob', y='Win Rate', size='Games',
                         hover_data=['Decile', 'Lift'])
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1,
                      line=dict(color="Red", dash="dash"))
        fig.update_layout(xaxis_title="Predicted Probability", yaxis_title="Actual Win Rate")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Points closer to the red dashed line indicate a better calibrated model.")

with tab3:
    st.header("ROI Analysis (Assuming -110 Odds)")
    if not decile_stats.empty:
        fig = px.bar(decile_stats, x='Decile', y='ROI (-110)',
                     color='ROI (-110)', color_continuous_scale='RdYlGn')
        fig.add_hline(y=0, line_color="black")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Estimated Return on Investment if betting blindly on Home Team for all games in decile at standard -110 odds.")

with tab4:
    st.header("Cumulative Gain Curve")
    if not gain_curve.empty:
        fig = px.line(gain_curve, x='pct_games', y='pct_wins_captured')
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1,
                      line=dict(color="Red", dash="dash"), name="Random")
        fig.update_layout(xaxis_title="% of Games Bet (Sorted by Confidence)", 
                          yaxis_title="% of Total Wins Captured")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("The curve above the red diagonal indicates the model is better than random guessing.")

with tab5:
    st.header("Detailed Statistics")
    if not decile_stats.empty:
        display_df = decile_stats.copy()
        display_df['Win Rate'] = display_df['Win Rate'].map('{:.1%}'.format)
        display_df['Avg Prob'] = display_df['Avg Prob'].map('{:.1%}'.format)
        display_df['Lift'] = display_df['Lift'].map('{:.2f}x'.format)
        display_df['ROI (-110)'] = display_df['ROI (-110)'].map('{:.1f}%'.format)
        
        st.dataframe(display_df, use_container_width=True)
        
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "lift_analysis.csv", "text/csv")

with tab6:
    st.header("Predictive Power Over Season")
    st.markdown("Does the model get smarter as the season progresses? Analysis breaks down performance by percentage of season played.")
    
    if not simulated_data.empty:
        # Calculate season progress for visualization
        viz_df = simulated_data.copy()
        viz_df['season_rank'] = viz_df.groupby('season')['game_date'].rank(method='dense')
        season_max = viz_df.groupby('season')['season_rank'].transform('max')
        viz_df['Season Progress (%)'] = (viz_df['season_rank'] / season_max) * 100
        
        # Bin into 10% chunks
        viz_df['Progress Bin'] = (pd.cut(viz_df['Season Progress (%)'], bins=10, labels=False) + 1) * 10
        
        # Aggregate
        timing_stats = []
        for bin_val in sorted(viz_df['Progress Bin'].unique()):
            subset = viz_df[viz_df['Progress Bin'] == bin_val]
            if subset.empty: continue
            
            # Brier Score (lower is better)
            if 'home_win' in subset.columns:
                 brier = ((subset['elo_prob'] - subset['home_win']) ** 2).mean()
                 
                 # ROI on Favorites (>55%)
                 favs = subset[subset['elo_prob'] > 0.55]
                 if not favs.empty:
                     wins = favs['home_win'].sum()
                     roi = ((wins * 0.909) - (len(favs) - wins)) / len(favs) * 100
                 else:
                     roi = 0
                     
                 timing_stats.append({
                     'Progress (%)': bin_val,
                     'Brier Score': brier,
                     'ROI (Favorites)': roi,
                     'Games': len(subset)
                 })
                 
        timing_df = pd.DataFrame(timing_stats)
        
        if not timing_df.empty:
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.subheader("Model Error (Brier Score)")
                fig_brier = px.line(timing_df, x='Progress (%)', y='Brier Score', markers=True,
                                   title="Prediction Error over Time (Lower is Better)")
                st.plotly_chart(fig_brier, use_container_width=True)
                
            with col_b:
                st.subheader("Profitability (ROI)")
                fig_roi = px.bar(timing_df, x='Progress (%)', y='ROI (Favorites)',
                                title="ROI on Favorites (>55%) by Season Stage")
                fig_roi.add_hline(y=0, line_color="black")
                st.plotly_chart(fig_roi, use_container_width=True)
            
            st.dataframe(timing_df, use_container_width=True)
