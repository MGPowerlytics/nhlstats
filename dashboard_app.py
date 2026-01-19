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

try:
    from ncaab_elo_rating import NCAABEloRating
except ImportError:
    NCAABEloRating = None

try:
    from ligue1_elo_rating import Ligue1EloRating
except ImportError:
    Ligue1EloRating = None

try:
    from wncaab_elo_rating import WNCAABEloRating
except ImportError:
    WNCAABEloRating = None

# Import Glicko-2 classes
try:
    from glicko2_rating import (NBAGlicko2Rating, NHLGlicko2Rating, 
                                 MLBGlicko2Rating, NFLGlicko2Rating)
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

    elif league == 'NCAAB':
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
                is_neutral,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM ncaab_games
            WHERE home_score IS NOT NULL 
              AND away_score IS NOT NULL
            ORDER BY game_date
        """
        try:
            games_df = conn.execute(query).fetchdf()
        except Exception as e:
            st.error(f"Error loading NCAAB data: {e}")
        finally:
            conn.close()
    
    elif league == 'WNCAAB':
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
                neutral_site,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM wncaab_games
            WHERE home_score IS NOT NULL 
              AND away_score IS NOT NULL
            ORDER BY game_date
        """
        try:
            games_df = conn.execute(query).fetchdf()
        except Exception as e:
            st.error(f"Error loading WNCAAB data: {e}")
        finally:
            conn.close()
    
    elif league == 'Ligue1':
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
            FROM ligue1_games
            WHERE result IS NOT NULL
            ORDER BY game_date
        """
        try:
            games_df = conn.execute(query).fetchdf()
        except Exception as e:
            st.error(f"Error loading Ligue1 data: {e}")
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
    elif league == 'NCAAB' and NCAABEloRating:
        elo = NCAABEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == 'WNCAAB' and WNCAABEloRating:
        elo = WNCAABEloRating(k_factor=k_factor, home_advantage=home_adv)
    elif league == 'Ligue1' and Ligue1EloRating:
        elo = Ligue1EloRating(k_factor=k_factor, home_advantage=home_adv)
    else:
        st.error(f"Elo system for {league} not available.")
        return games_df
        
    probs = []
    
    # Process games
    # We rely on games_df being sorted by date already
    for _, game in games_df.iterrows():
        # Predict
        if league == 'NCAAB':
            prob = elo.predict(game['home_team'], game['away_team'], is_neutral=game['is_neutral'])
        elif league == 'WNCAAB':
            prob = elo.predict(game['home_team'], game['away_team'], is_neutral=game['neutral_site'])
        else:
            prob = elo.predict(game['home_team'], game['away_team'])
        probs.append(prob)
        
        # Update
        if league == 'NBA':
            elo.update(game['home_team'], game['away_team'], game['home_win'])
        elif league == 'NHL':
            elo.update(game['home_team'], game['away_team'], game['home_win'])
        elif league == 'NCAAB':
            elo.update(game['home_team'], game['away_team'], game['home_win'], is_neutral=game['is_neutral'])
        elif league == 'WNCAAB':
            elo.update(game['home_team'], game['away_team'], game['home_win'], is_neutral=game['neutral_site'])
        elif league == 'EPL':
             elo.update(game['home_team'], game['away_team'], game['result'])
        elif league == 'Ligue1':
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

@st.cache_data
def run_glicko2_simulation(games_df, league, tau=0.5, home_adv=100):
    """Run Glicko-2 simulation for the selected league."""
    if games_df.empty:
        return games_df
    
    # Initialize Glicko-2 system
    if league == 'MLB' and MLBGlicko2Rating:
        glicko = MLBGlicko2Rating()
    elif league == 'NHL' and NHLGlicko2Rating:
        glicko = NHLGlicko2Rating()
    elif league == 'NFL' and NFLGlicko2Rating:
        glicko = NFLGlicko2Rating()
    elif league == 'NBA' and NBAGlicko2Rating:
        glicko = NBAGlicko2Rating()
    else:
        st.warning(f"Glicko-2 system for {league} not yet implemented.")
        return games_df
    
    # Override parameters
    glicko.home_advantage = home_adv
    glicko.TAU = tau
    
    probs = []
    
    # Process games
    for _, game in games_df.iterrows():
        # Predict
        prob = glicko.predict(game['home_team'], game['away_team'])
        probs.append(prob)
        
        # Update
        glicko.update(game['home_team'], game['away_team'], game['home_win'])
    
    games_df['glicko2_prob'] = probs
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

# Add page navigation
page = st.sidebar.radio(
    "📍 Navigation",
    ["Elo Ratings & Analysis", "Betting Performance"],
    index=0
)

if page == "Betting Performance":
    betting_performance_page_v2()
    st.stop()

st.sidebar.title("Configuration")

# League Selection
league = st.sidebar.selectbox("Select League", ["MLB", "NHL", "NFL", "NBA", "EPL", "Tennis", "NCAAB", "WNCAAB", "Ligue1"])

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

# Set defaults based on league
default_k = 20
default_home = 50 # MLB default

if league == 'NHL': default_home = 100
if league == 'NBA': default_home = 100
if league == 'NFL': default_home = 65
if league == 'EPL': default_home = 60
if league == 'Ligue1': default_home = 60
if league == 'Tennis': 
    default_home = 0
    default_k = 32
if league == 'NCAAB': default_home = 100
if league == 'WNCAAB': default_home = 100  # Added for Women's NCAA Basketball

# Elo Parameters (Advanced)
with st.sidebar.expander("Elo Parameters"):
    k_factor = st.number_input("K-Factor", value=default_k)
    home_adv = st.number_input("Home Advantage", value=default_home)

# Glicko-2 Parameters (Advanced)
with st.sidebar.expander("Glicko-2 Parameters"):
    enable_glicko2 = st.checkbox("Enable Glicko-2 Comparison", value=True)
    glicko2_tau = st.slider("System Volatility (τ)", 0.3, 1.2, 0.5, 0.1,
                            help="Lower = more stable ratings, Higher = faster adaptation")
    glicko2_home_adv = st.number_input("Home Advantage (Glicko-2)", value=default_home)

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

# Run Glicko-2 if enabled
if enable_glicko2 and league in ['NBA', 'NHL', 'MLB', 'NFL']:
    with st.spinner("Running Glicko-2 Simulation..."):
        simulated_data_glicko2 = run_glicko2_simulation(filtered_data, league, glicko2_tau, glicko2_home_adv)
        # Merge predictions
        if 'glicko2_prob' in simulated_data_glicko2.columns:
            simulated_data['glicko2_prob'] = simulated_data_glicko2['glicko2_prob']
else:
    simulated_data['glicko2_prob'] = None

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
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Lift Chart", "Calibration", "ROI Analysis", "Cumulative Gain", "Elo vs Glicko-2", "Details", "Season Timing"])

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
    st.header("Elo vs Glicko-2 Comparison")
    
    if enable_glicko2 and 'glicko2_prob' in simulated_data.columns and simulated_data['glicko2_prob'].notna().any():
        # Calculate metrics for both
        comp_df = simulated_data[simulated_data['glicko2_prob'].notna()].copy()
        
        # Accuracy
        elo_accuracy = ((comp_df['elo_prob'] > 0.5) == comp_df['home_win']).mean()
        glicko2_accuracy = ((comp_df['glicko2_prob'] > 0.5) == comp_df['home_win']).mean()
        
        # Brier Score (lower is better)
        elo_brier = ((comp_df['elo_prob'] - comp_df['home_win']) ** 2).mean()
        glicko2_brier = ((comp_df['glicko2_prob'] - comp_df['home_win']) ** 2).mean()
        
        # Log Loss (lower is better)
        from sklearn.metrics import log_loss
        elo_logloss = log_loss(comp_df['home_win'], comp_df['elo_prob'])
        glicko2_logloss = log_loss(comp_df['home_win'], comp_df['glicko2_prob'])
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Elo Accuracy", f"{elo_accuracy:.1%}")
            st.metric("Elo Brier Score", f"{elo_brier:.4f}")
            st.metric("Elo Log Loss", f"{elo_logloss:.4f}")
        
        with col2:
            st.metric("Glicko-2 Accuracy", f"{glicko2_accuracy:.1%}", 
                     delta=f"{(glicko2_accuracy - elo_accuracy)*100:.1f} pts")
            st.metric("Glicko-2 Brier Score", f"{glicko2_brier:.4f}",
                     delta=f"{elo_brier - glicko2_brier:.4f}",
                     delta_color="inverse")
            st.metric("Glicko-2 Log Loss", f"{glicko2_logloss:.4f}",
                     delta=f"{elo_logloss - glicko2_logloss:.4f}",
                     delta_color="inverse")
        
        with col3:
            st.subheader("Winner")
            if glicko2_accuracy > elo_accuracy:
                st.success("✅ Glicko-2 wins on Accuracy!")
            elif elo_accuracy > glicko2_accuracy:
                st.info("✅ Elo wins on Accuracy!")
            else:
                st.warning("🤝 Tie on Accuracy")
            
            if glicko2_brier < elo_brier:
                st.success("✅ Glicko-2 wins on Brier Score!")
            elif elo_brier < glicko2_brier:
                st.info("✅ Elo wins on Brier Score!")
            else:
                st.warning("🤝 Tie on Brier Score")
        
        # Scatter plot comparison
        st.subheader("Probability Comparison")
        fig = px.scatter(comp_df, x='elo_prob', y='glicko2_prob', 
                         color='home_win', 
                         labels={'elo_prob': 'Elo Probability', 
                                'glicko2_prob': 'Glicko-2 Probability'},
                         title="Elo vs Glicko-2 Predictions")
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1,
                     line=dict(color="Red", dash="dash"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Points near the diagonal mean both systems agree. Points off the diagonal show disagreement.")
        
        # Probability difference distribution
        st.subheader("Prediction Differences")
        comp_df['prob_diff'] = comp_df['glicko2_prob'] - comp_df['elo_prob']
        fig = px.histogram(comp_df, x='prob_diff', nbins=50,
                          title="Distribution of Glicko-2 vs Elo Probability Differences")
        fig.add_vline(x=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Positive values mean Glicko-2 was more confident in home win. Negative means less confident.")
        
        # Games where they disagree significantly
        st.subheader("Significant Disagreements (>10% difference)")
        disagreements = comp_df[abs(comp_df['prob_diff']) > 0.10].copy()
        if not disagreements.empty:
            disagreements = disagreements.sort_values('prob_diff', ascending=False)
            st.dataframe(disagreements[['game_date', 'home_team', 'away_team', 
                                       'elo_prob', 'glicko2_prob', 'prob_diff', 'home_win']].head(20),
                        use_container_width=True)
        else:
            st.info("No significant disagreements found.")
    else:
        st.info("Enable Glicko-2 in the sidebar to see comparison. Currently only supported for NBA, NHL, MLB, NFL.")

with tab6:
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

with tab7:
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


# --- Betting Performance Functions ---

def load_betting_results():
    """Load betting results from JSON files."""
    import json
    betting_data = []
    data_dir = Path('data')
    
    for sport_dir in ['nba', 'ncaab', 'nhl', 'mlb', 'nfl', 'epl', 'tennis']:
        sport_path = data_dir / sport_dir
        if not sport_path.exists():
            continue
            
        # Find all betting_results JSON files
        for results_file in sport_path.glob('betting_results_*.json'):
            try:
                with open(results_file, 'r') as f:
                    data = json.load(f)
                
                # Extract date from filename
                date_str = results_file.stem.replace('betting_results_', '').replace('_FINAL', '')
                
                # Parse placed bets
                for bet in data.get('placed', []):
                    rec = bet.get('rec', {})
                    order = bet.get('result', {}).get('order', {})
                    
                    betting_data.append({
                        'sport': sport_dir.upper(),
                        'date': date_str,
                        'home_team': rec.get('home_team', rec.get('player2', 'N/A')),
                        'away_team': rec.get('away_team', rec.get('player1', 'N/A')),
                        'bet_on': rec.get('bet_on', 'N/A'),
                        'elo_prob': rec.get('elo_prob', 0),
                        'market_prob': rec.get('market_prob', 0),
                        'edge': rec.get('edge', 0),
                        'confidence': rec.get('confidence', 'N/A'),
                        'bet_size': bet.get('bet_size', 0),
                        'side': bet.get('side', 'N/A'),
                        'price': order.get('yes_price', 0) / 100 if order.get('yes_price') else 0,
                        'contracts': order.get('fill_count', 0),
                        'cost': float(str(order.get('taker_fill_cost_dollars', '0')).replace('$', '')),
                        'fees': float(str(order.get('taker_fees_dollars', '0')).replace('$', '')),
                        'ticker': rec.get('ticker', 'N/A'),
                        'status': 'placed'
                    })
                
                # Parse skipped bets
                for skip in data.get('skipped', []):
                    rec = skip.get('rec', {})
                    betting_data.append({
                        'sport': sport_dir.upper(),
                        'date': date_str,
                        'home_team': rec.get('home_team', rec.get('player2', 'N/A')),
                        'away_team': rec.get('away_team', rec.get('player1', 'N/A')),
                        'bet_on': rec.get('bet_on', 'N/A'),
                        'elo_prob': rec.get('elo_prob', 0),
                        'market_prob': rec.get('market_prob', 0),
                        'edge': rec.get('edge', 0),
                        'confidence': rec.get('confidence', 'N/A'),
                        'bet_size': 0,
                        'side': 'N/A',
                        'price': 0,
                        'contracts': 0,
                        'cost': 0,
                        'fees': 0,
                        'ticker': rec.get('ticker', 'N/A'),
                        'status': f"skipped: {skip.get('reason', 'unknown')}"
                    })
                    
            except Exception as e:
                continue
    
    return pd.DataFrame(betting_data)


def betting_performance_page_v2():
    """Display betting performance metrics."""
    st.title("🎰 Betting Performance Tracker")
    
    # Load betting data
    betting_df = load_betting_results()
    
    if betting_df.empty:
        st.warning("No betting data available yet.")
        return
    
    # Convert numeric columns
    numeric_cols = ['elo_prob', 'market_prob', 'edge', 'bet_size', 'price', 'contracts']
    for col in numeric_cols:
        betting_df[col] = pd.to_numeric(betting_df[col], errors='coerce')
    
    betting_df['cost'] = pd.to_numeric(betting_df['cost'], errors='coerce')
    betting_df['fees'] = pd.to_numeric(betting_df['fees'], errors='coerce')
    
    # Filter controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sports = ['All'] + sorted(betting_df['sport'].unique().tolist())
        selected_sport = st.selectbox('Sport', sports)
    
    with col2:
        dates = ['All'] + sorted(betting_df['date'].unique().tolist(), reverse=True)
        selected_date = st.selectbox('Date', dates)
    
    with col3:
        statuses = ['All'] + sorted(betting_df['status'].unique().tolist())
        selected_status = st.selectbox('Status', statuses)
    
    # Apply filters
    filtered_df = betting_df.copy()
    if selected_sport != 'All':
        filtered_df = filtered_df[filtered_df['sport'] == selected_sport]
    if selected_date != 'All':
        filtered_df = filtered_df[filtered_df['date'] == selected_date]
    if selected_status != 'All':
        filtered_df = filtered_df[filtered_df['status'] == selected_status]
    
    # Summary metrics
    placed_df = filtered_df[filtered_df['status'] == 'placed']
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Bets Placed", len(placed_df))
    
    with col2:
        total_invested = placed_df['cost'].sum()
        st.metric("Total Invested", f"${total_invested:.2f}")
    
    with col3:
        total_fees = placed_df['fees'].sum()
        st.metric("Total Fees", f"${total_fees:.2f}")
    
    with col4:
        avg_edge = placed_df['edge'].mean() * 100 if not placed_df.empty else 0
        st.metric("Avg Edge", f"{avg_edge:.1f}%")
    
    with col5:
        avg_elo = placed_df['elo_prob'].mean() * 100 if not placed_df.empty else 0
        st.metric("Avg Elo Prob", f"{avg_elo:.1f}%")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 By Sport", "📅 By Date", "📋 All Bets"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Bets by sport
            sport_summary = filtered_df.groupby('sport').agg({
                'bet_size': 'count',
                'cost': 'sum',
                'edge': 'mean',
                'elo_prob': 'mean'
            }).reset_index()
            sport_summary.columns = ['Sport', 'Count', 'Total Cost', 'Avg Edge', 'Avg Elo Prob']
            
            fig = px.bar(sport_summary, x='Sport', y='Count', 
                        title='Bets by Sport',
                        color='Avg Edge',
                        color_continuous_scale='RdYlGn')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Confidence distribution
            conf_dist = placed_df['confidence'].value_counts()
            fig = px.pie(values=conf_dist.values, names=conf_dist.index,
                        title='Confidence Distribution')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Sport-specific analysis
        for sport in filtered_df['sport'].unique():
            sport_data = filtered_df[filtered_df['sport'] == sport]
            placed_sport = sport_data[sport_data['status'] == 'placed']
            
            st.subheader(f"📊 {sport}")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Placed", len(placed_sport))
            
            with col2:
                skipped = len(sport_data[sport_data['status'] != 'placed'])
                st.metric("Skipped", skipped)
            
            with col3:
                invested = placed_sport['cost'].sum()
                st.metric("Invested", f"${invested:.2f}")
            
            with col4:
                avg_edge = placed_sport['edge'].mean() * 100 if not placed_sport.empty else 0
                st.metric("Avg Edge", f"{avg_edge:.1f}%")
            
            # Show recent bets
            if not placed_sport.empty:
                display_df = placed_sport[['date', 'away_team', 'home_team', 'bet_on', 
                                          'elo_prob', 'market_prob', 'edge', 'cost']].tail(5).copy()
                display_df['elo_prob'] = (display_df['elo_prob'] * 100).round(1)
                display_df['market_prob'] = (display_df['market_prob'] * 100).round(1)
                display_df['edge'] = (display_df['edge'] * 100).round(1)
                st.dataframe(display_df, use_container_width=True)
    
    with tab3:
        # Daily summary
        daily = placed_df.groupby('date').agg({
            'cost': 'sum',
            'fees': 'sum',
            'bet_size': 'count',
            'edge': 'mean'
        }).reset_index()
        daily.columns = ['Date', 'Total Cost', 'Total Fees', 'Num Bets', 'Avg Edge']
        daily['Avg Edge'] = (daily['Avg Edge'] * 100).round(1)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=daily['Date'], y=daily['Total Cost'], name='Cost'))
        fig.add_trace(go.Bar(x=daily['Date'], y=daily['Total Fees'], name='Fees'))
        fig.update_layout(title='Daily Betting Activity', barmode='stack')
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(daily, use_container_width=True)
    
    with tab4:
        # Full bet list
        display_df = filtered_df.sort_values('date', ascending=False).copy()
        for col in ['elo_prob', 'market_prob', 'edge']:
            if col in display_df.columns:
                display_df[col] = (display_df[col] * 100).round(1)
        
        st.dataframe(display_df, 
                    use_container_width=True,
                    height=600)



# --- Main Application Entry ---

# Add page selector at the top (before sidebar)
page = st.sidebar.radio(
    "�� Navigation",
    ["Elo Ratings & Analysis", "Betting Performance"],
    index=0
)

if page == "Betting Performance":
    betting_performance_page_v2()
    st.stop()

# Otherwise continue with existing dashboard code below...


# --- Updated Betting Performance with Database Integration ---

def load_betting_results_from_db():
    """Load betting results from database."""
    import json
    
    conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
    
    try:
        # Check if table exists
        tables = conn.execute("SHOW TABLES").fetchall()
        if not any('placed_bets' in str(t) for t in tables):
            return pd.DataFrame()
        
        bets_df = conn.execute("""
            SELECT *
            FROM placed_bets
            ORDER BY placed_date DESC, created_at DESC
        """).fetchdf()
        
        conn.close()
        return bets_df
    except:
        conn.close()
        return pd.DataFrame()


def betting_performance_page_v2():
    """Enhanced betting performance page with outcomes tracking."""
    st.title("🎰 Betting Performance Tracker")
    
    # Sync button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Sync from Kalshi"):
            with st.spinner("Syncing bets from Kalshi API..."):
                import subprocess
                result = subprocess.run(['python3', 'plugins/bet_tracker.py'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    st.success("✅ Synced successfully!")
                    st.rerun()
                else:
                    st.error(f"Error: {result.stderr}")
    
    # Load betting data from database
    betting_df = load_betting_results_from_db()
    
    if betting_df.empty:
        st.warning("No betting data available. Click 'Sync from Kalshi' to load your bets.")
        return
    
    # Summary metrics
    total_bets = len(betting_df)
    total_invested = betting_df['cost_dollars'].sum()
    wins = len(betting_df[betting_df['status'] == 'won'])
    losses = len(betting_df[betting_df['status'] == 'lost'])
    open_bets = len(betting_df[betting_df['status'] == 'open'])
    
    settled_df = betting_df[betting_df['status'].isin(['won', 'lost'])]
    total_profit = settled_df['profit_dollars'].sum() if not settled_df.empty else 0
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    roi = (total_profit / total_invested * 100) if total_invested > 0 else 0
    
    # Top metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Bets", total_bets)
    
    with col2:
        st.metric("Win Rate", f"{win_rate:.1f}%")
    
    with col3:
        st.metric("Total Invested", f"${total_invested:.2f}")
    
    with col4:
        profit_color = "normal" if total_profit >= 0 else "inverse"
        st.metric("Total Profit", f"${total_profit:.2f}", 
                 delta=f"{roi:.1f}% ROI", 
                 delta_color=profit_color)
    
    with col5:
        st.metric("Open Bets", open_bets)
    
    # Filters
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sports = ['All'] + sorted(betting_df['sport'].unique().tolist())
        selected_sport = st.selectbox('Sport', sports, key='sport_filter_v2')
    
    with col2:
        dates = ['All'] + sorted(betting_df['placed_date'].unique().tolist(), reverse=True)
        selected_date = st.selectbox('Date', dates, key='date_filter_v2')
    
    with col3:
        statuses = ['All'] + sorted(betting_df['status'].unique().tolist())
        selected_status = st.selectbox('Status', statuses, key='status_filter_v2')
    
    # Apply filters
    filtered_df = betting_df.copy()
    if selected_sport != 'All':
        filtered_df = filtered_df[filtered_df['sport'] == selected_sport]
    if selected_date != 'All':
        filtered_df = filtered_df[filtered_df['placed_date'] == selected_date]
    if selected_status != 'All':
        filtered_df = filtered_df[filtered_df['status'] == selected_status]
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📅 Daily Performance", "🏆 By Sport", "📋 All Bets"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Win/Loss pie chart
            wl_data = pd.DataFrame({
                'Status': ['Won', 'Lost', 'Open'],
                'Count': [wins, losses, open_bets]
            })
            fig = px.pie(wl_data, values='Count', names='Status',
                        title='Bet Outcomes',
                        color='Status',
                        color_discrete_map={'Won': 'green', 'Lost': 'red', 'Open': 'gray'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Profit by sport
            sport_profit = filtered_df[filtered_df['status'].isin(['won', 'lost'])].groupby('sport').agg({
                'profit_dollars': 'sum'
            }).reset_index()
            
            fig = px.bar(sport_profit, x='sport', y='profit_dollars',
                        title='Profit/Loss by Sport',
                        color='profit_dollars',
                        color_continuous_scale='RdYlGn',
                        color_continuous_midpoint=0)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Daily performance
        daily = filtered_df.groupby('placed_date').agg({
            'bet_id': 'count',
            'cost_dollars': 'sum',
            'profit_dollars': lambda x: x[filtered_df.loc[x.index, 'status'].isin(['won', 'lost'])].sum()
        }).reset_index()
        daily.columns = ['Date', 'Bets', 'Invested', 'Profit']
        daily['ROI %'] = (daily['Profit'] / daily['Invested'] * 100).round(1)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=daily['Date'], y=daily['Invested'], name='Invested', marker_color='lightblue'))
        fig.add_trace(go.Bar(x=daily['Date'], y=daily['Profit'], name='Profit', marker_color='green'))
        fig.update_layout(title='Daily Performance', barmode='group')
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(daily, use_container_width=True)
    
    with tab3:
        # By sport analysis
        for sport in filtered_df['sport'].unique():
            sport_data = filtered_df[filtered_df['sport'] == sport]
            settled = sport_data[sport_data['status'].isin(['won', 'lost'])]
            
            st.subheader(f"📊 {sport}")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                sport_wins = len(sport_data[sport_data['status'] == 'won'])
                sport_losses = len(sport_data[sport_data['status'] == 'lost'])
                st.metric("Record", f"{sport_wins}W - {sport_losses}L")
            
            with col2:
                sport_wr = (sport_wins / (sport_wins + sport_losses) * 100) if (sport_wins + sport_losses) > 0 else 0
                st.metric("Win Rate", f"{sport_wr:.1f}%")
            
            with col3:
                sport_invested = sport_data['cost_dollars'].sum()
                st.metric("Invested", f"${sport_invested:.2f}")
            
            with col4:
                sport_profit = settled['profit_dollars'].sum() if not settled.empty else 0
                st.metric("Profit", f"${sport_profit:.2f}")
            
            # Recent bets
            if not sport_data.empty:
                display_cols = ['placed_date', 'ticker', 'side', 'contracts', 'price_cents', 'cost_dollars', 'status', 'profit_dollars']
                available_cols = [c for c in display_cols if c in sport_data.columns]
                st.dataframe(sport_data[available_cols].head(10), use_container_width=True)
    
    with tab4:
        # Full bet list with formatting
        display_df = filtered_df.copy()
        if 'profit_dollars' in display_df.columns:
            display_df['profit_dollars'] = display_df['profit_dollars'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "pending")
        if 'cost_dollars' in display_df.columns:
            display_df['cost_dollars'] = display_df['cost_dollars'].apply(lambda x: f"${x:.2f}")
        
        st.dataframe(display_df, use_container_width=True, height=600)

