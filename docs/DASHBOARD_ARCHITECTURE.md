# 📐 Dashboard Architecture & Implementation Guide

Technical deep dive into the Streamlit dashboard design, data flow, and extensibility.

---

## System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT APP LAYER                      │
│  (UI, Controls, Caching, Session Management)               │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Data Layer  │  │Analytics     │  │Visualization │
│              │  │ Layer        │  │ Layer        │
│ ✓ DuckDB     │  │              │  │              │
│ ✓ JSON       │  │ ✓ Elo Rating │  │ ✓ Plotly     │
│ ✓ CSV        │  │ ✓ Metrics    │  │ ✓ Charts     │
│              │  │ ✓ Deciles    │  │ ✓ Tables     │
└──────────────┘  └──────────────┘  └──────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
    ┌────────┐        ┌────────┐        ┌────────┐
    │  NHL   │        │  MLB   │        │  NFL   │
    │ (DDB)  │        │ (DDB)  │        │ (DDB)  │
    └────────┘        └────────┘        └────────┘
        │                                    │
        └────────┬─────────────────────────┬─┘
                 │                         │
                 ▼                         ▼
            ┌──────────┐            ┌──────────┐
            │   NBA    │            │Database+ │
            │  (JSON)  │            │JSON Data │
            └──────────┘            └──────────┘
```

---

## Component Breakdown

### 1. **Data Loading Module**

#### DuckDB-Based Sports (NHL, MLB, NFL)

```python
load_games_for_analysis(league, season, up_to_date)
  ├─ Build SQL query based on league
  ├─ Filter by season (using season_start_month)
  ├─ Filter by date range
  └─ Return DataFrame: [game_id, game_date, teams, scores]
```

**Key Design Decisions:**
- Temporary database copy to avoid locking
- Sport-specific table names and column mappings
- Configurable season start month per sport
- Date filtering at query level (efficient)

**Season Logic:**
```python
# NFL season starts Sept 1, 2023 → runs Sept 2023 - Aug 2024
start = datetime(2023, 9, 1)
end = datetime(2024, 8, 31)
```

#### JSON-Based Sports (NBA)

```python
_load_nba_games(season, up_to_date)
  ├─ Iterate through date directories
  ├─ Filter by season and date range
  ├─ Load scoreboard JSON (game metadata)
  ├─ Load boxscore JSON (team stats)
  └─ Return DataFrame: [game_id, game_date, teams, scores]
```

**Key Design Decisions:**
- Directory-based iteration (more efficient than query)
- Handles missing files gracefully
- Cross-references scoreboard and boxscore data
- Season filtering in Python (simpler than DB query)

### 2. **Analytics Module**

#### Elo Prediction Calculation

```python
calculate_elo_predictions(league, games_df)
  ├─ Instantiate Elo class (sport-specific)
  ├─ Sort games chronologically
  ├─ For each game:
  │  ├─ Check for season boundary (NHL only)
  │  ├─ Apply season reversion if needed (NHL)
  │  ├─ Predict: prob = elo.predict(home, away)
  │  ├─ Update: elo.update(home, away, result)
  │  └─ Store prediction
  └─ Return DataFrame with elo_prob column
```

**Key Design Decisions:**
- Predictions before updates (proper backtesting)
- NHL-specific season reversion (0.35 factor)
- Sport-specific update methods (scores vs binary)
- Chronological processing (required for Elo)

**Elo Update Methods by Sport:**
| Sport | Method | Args |
|-------|--------|------|
| NHL   | `elo.update(h, a, binary)` | 0 or 1 |
| MLB   | `elo.update(h, a, h_score, a_score)` | scores |
| NFL   | `elo.update(h, a, h_score, a_score)` | scores |
| NBA   | `elo.update(h, a, binary)` | 0 or 1 |

#### Decile Metrics Calculation

```python
calculate_decile_metrics(df)
  ├─ Create 10 equal-size deciles via pd.qcut
  ├─ For each decile:
  │  ├─ n_games = count of games
  │  ├─ n_wins = sum of home_win (1 if H>A)
  │  ├─ win_rate = n_wins / n_games
  │  └─ lift = win_rate / baseline
  ├─ Calculate cumulative stats (from decile 10 down):
  │  ├─ cumulative_games = running sum
  │  ├─ cumulative_wins = running sum
  │  ├─ cumulative_win_rate = cum_wins / cum_games
  │  ├─ gain_pct = (cum_wins / total_wins) * 100
  │  └─ coverage_pct = (cum_games / total_games) * 100
  └─ Return metrics DataFrame
```

**Key Metrics:**

1. **Baseline Win Rate**
   ```python
   baseline = df['home_win'].mean()  # ~50% for most sports
   ```

2. **Lift**
   ```python
   lift = win_rate / baseline
   # Measures relative improvement over random
   ```

3. **ROI (at -110 odds)**
   ```python
   roi_pct = (win_rate * 100 - 50) * 0.91
   # 0.91 factor = vig adjustment
   # +1% means $1 profit per $100 wagered
   ```

4. **Cumulative Gain**
   ```python
   # Calculated from high confidence (dec 10) to low (dec 1)
   # Shows concentration of predictive power
   gain_pct = (cumulative_wins / total_wins) * 100
   ```

### 3. **Visualization Module**

#### Chart Types

| Chart | Purpose | Data | Interpretation |
|-------|---------|------|-----------------|
| **Lift** | Model quality | Deciles | >1.0 good, <1.0 bad |
| **Win Rate** | Performance | Deciles | Above/below baseline |
| **ROI** | Profitability | Deciles | Betting returns |
| **Calibration** | Accuracy | All games | Predicted vs actual |
| **Cum Gain** | Discrimination | Deciles | Curve vs baseline |

#### Lift Chart Implementation

```python
def plot_lift_chart(decile_df):
    fig = go.Figure()

    # Main bars (one per decile)
    fig.add_trace(go.Bar(
        x=decile_df['decile'],           # 1-10
        y=decile_df['lift'],             # 0.8 - 1.3
        name='Lift',
        marker_color='steelblue'
    ))

    # Reference line at y=1.0
    fig.add_hline(y=1.0, line_dash="dash")

    return fig
```

**Design Decisions:**
- Decile 1-10 on X-axis (intuitive ordering)
- Lift on Y-axis with 1.0 baseline
- Hover shows exact lift values
- Reference line for quick assessment

#### Calibration Plot Implementation

```python
def plot_calibration(games_df, n_bins=10):
    # Bin predictions into n_bins groups
    df['prob_bin'] = pd.cut(df['elo_prob'], bins=n_bins)

    # Calculate mean probability and actual win rate per bin
    calibration = df.groupby('prob_bin').agg({
        'elo_prob': 'mean',      # Avg predicted prob
        'home_win': 'mean'       # Actual win rate
    })

    # Plot predicted vs actual
    # Perfect calibration = points on y=x line
```

**Interpretation:**
- Point at (0.60, 0.62): Underconfident
- Point at (0.60, 0.58): Overconfident
- Points on diagonal: Well-calibrated

#### ROI Chart Implementation

```python
def plot_roi_by_decile(decile_df):
    # ROI already calculated in decile_df['roi_pct']

    # Color: green if ROI > 0, red if < 0
    colors = ['green' if x > 0 else 'red' for x in roi_pct]

    fig.add_trace(go.Bar(
        x=decile_df['decile'],
        y=decile_df['roi_pct'],
        marker_color=colors
    ))
```

---

## Data Flow Example: NHL Analysis

### Step 1: User Selects Parameters
```python
league = "NHL"
season = 2023
up_to_date = 2024-04-01
```

### Step 2: Load Games
```
SQL Query:
SELECT * FROM games
WHERE (MONTH(game_date) >= 10 AND YEAR(game_date) = 2023)
   OR (MONTH(game_date) < 10 AND YEAR(game_date) = 2024)
  AND game_date <= 2024-04-01
  AND game_state IN ('OFF', 'FINAL')
  AND home_score IS NOT NULL
ORDER BY game_date

Result: 1,230 games from Oct 2023 - Apr 2024
```

### Step 3: Calculate Elo Predictions
```
For each game (chronologically):
1. game_date: 2023-10-10, TOR vs MON
   - TOR rating: 1500, MON rating: 1500
   - predict(1500, 1500) = 0.50
   - Result: TOR won 3-1
   - update(TOR, MON, home_win=1)
   - TOR rating: 1505, MON rating: 1495

2. game_date: 2023-10-11, BOS vs NYR
   - BOS rating: 1520, NYR rating: 1480
   - predict(1520, 1480) = 0.61
   - Result: NYR won 2-1
   - update(BOS, NYR, home_win=0)
   - BOS rating: 1510, NYR rating: 1490

... (repeat for 1,228 more games)
```

### Step 4: Create Deciles
```
Sort 1,230 games by elo_prob:
Decile 1 (lowest):    123 games, prob 0.45-0.48
Decile 2:             123 games, prob 0.48-0.50
...
Decile 9:             123 games, prob 0.52-0.54
Decile 10 (highest):  123 games, prob 0.54-0.58

Calculate metrics for each decile
```

### Step 5: Visualize
```
Charts show:
- Decile 10 has lift 1.15x (15% better than baseline)
- Calibration plot shows model is well-calibrated
- Cumulative gain shows strong discrimination
- Top 2 deciles contain 25% of wins from 20% of games
```

---

## Caching Strategy

### What's Cached?

```python
@st.cache_data  # Caches are invalidated on code change
def get_available_seasons(league):
    # Database query results
    # Cache key: league name
    # Invalidates: When function code changes

@st.cache_data
def load_games_for_analysis(league, season, up_to_date):
    # Game dataframes from database
    # Cache key: (league, season, up_to_date)
    # Invalidates: When parameters change or function code changes
```

### Cache Invalidation

**Automatic:**
- Parameter changes invalidate cache
- Function code changes invalidate cache
- Streamlit version changes invalidate cache

**Manual:**
- User clicks "Refresh Analysis" button
- Calls `st.cache_data.clear()`
- Then `st.rerun()` to re-execute

### Performance Impact

| Scenario | Time | Why |
|----------|------|-----|
| First load, new league | 10s | Queries DB + Elo calc |
| Switch parameter | <1s | Cache hit |
| Manual refresh | 10s | Cache cleared |
| Same page refresh | <1s | Cache hit |

---

## Extensibility Points

### Adding a New League

1. **Create Elo Class** (in `plugins/`)
   ```python
   class NewSportEloRating:
       def __init__(self, k_factor=20, home_advantage=50):
           self.ratings = {}
           self.k_factor = k_factor
           self.home_advantage = home_advantage

       def predict(self, home_team, away_team):
           # Return probability (0-1)
           pass

       def update(self, home_team, away_team, result):
           # Update ratings based on result
           pass
   ```

2. **Register in Config**
   ```python
   SPORT_CONFIG['NEW_LEAGUE'] = {
       'elo_class': NewSportEloRating,
       'k_factor': 20,
       'home_advantage': 50,
       'season_start_month': 9,
       'table': 'new_league_games',
       'date_col': 'game_date',
       'home_team_col': 'home_team',
       'away_team_col': 'away_team',
       'home_score_col': 'home_score',
       'away_score_col': 'away_score',
   }
   ```

3. **Add Loading Logic** (if needed)
   ```python
   def _load_new_league_games(season, up_to_date):
       # Implement based on data source
       # Return DataFrame with standard columns
       pass
   ```

### Adding a New Metric

1. **Calculate in `calculate_decile_metrics()`**
   ```python
   results_df['new_metric'] = results_df.apply(
       lambda row: calculate_custom_metric(row),
       axis=1
   )
   ```

2. **Create Visualization**
   ```python
   def plot_new_metric(decile_df):
       fig = go.Figure()
       fig.add_trace(go.Bar(
           x=decile_df['decile'],
           y=decile_df['new_metric']
       ))
       return fig
   ```

3. **Add Tab in Main App**
   ```python
   with tab_new:
       st.plotly_chart(plot_new_metric(decile_metrics))
   ```

### Adding a New Visualization

1. **Create function returning `go.Figure`**
   ```python
   def plot_new_viz(data_df):
       fig = go.Figure()
       # ... add traces
       fig.update_layout(title="...", template="plotly_white")
       return fig
   ```

2. **Add to tab in main UI**
   ```python
   with st.expander("New Visualization"):
       st.plotly_chart(plot_new_viz(decile_metrics))
   ```

---

## Configuration Details

### SPORT_CONFIG Structure

```python
SPORT_CONFIG = {
    'LEAGUE_NAME': {
        'elo_class': EloRatingClass,           # Elo class
        'k_factor': 20,                        # Rating change speed
        'home_advantage': 50,                  # Home Elo bonus
        'season_start_month': 9,               # Season start month
        'table': 'table_name',                 # DuckDB table
        'date_col': 'game_date',               # Date column
        'home_team_col': 'home_team',          # Home team column
        'away_team_col': 'away_team',          # Away team column
        'home_score_col': 'home_score',        # Home score column
        'away_score_col': 'away_score',        # Away score column
    }
}
```

### Elo Parameters Explained

| Parameter | Value | Meaning |
|-----------|-------|---------|
| **K-Factor** | 10-20 | Higher = faster rating changes |
| **Home Advantage** | 50-100 | Elo points for home team |
| | NHL: 50 | Smallest home advantage |
| | MLB: 50 | Moderate home advantage |
| | NFL: 65 | Larger home advantage |
| | NBA: 100 | Largest home advantage |

---

## Error Handling

### User-Facing Errors

```python
# Database not found
try:
    load_games_for_analysis(...)
except Exception as e:
    st.error(f"Database error: {e}")

# No data in range
if games_df.empty:
    st.error(f"No games found for selected parameters")

# Insufficient data for analysis
if len(decile_df) < 10:
    st.error("Not enough games for decile analysis")
```

### Data Validation

```python
# Check for null values
df = df.dropna(subset=['home_score', 'away_score'])

# Validate decile creation
if len(df) < 10:
    return pd.DataFrame()  # Can't create 10 deciles

# Check for duplicates
df = df.drop_duplicates(subset=['game_id'])
```

---

## Testing Strategy

### Unit Tests (proposed)

```python
def test_load_games_nhl():
    df = load_games_for_analysis('NHL', 2023, datetime(2024, 4, 1))
    assert not df.empty
    assert all(col in df.columns for col in ['game_date', 'home_team'])

def test_calculate_elo_predictions():
    df = load_games_for_analysis('NHL', 2023, ...)
    df_pred = calculate_elo_predictions('NHL', df)
    assert 'elo_prob' in df_pred.columns
    assert all(0 <= p <= 1 for p in df_pred['elo_prob'])

def test_calculate_decile_metrics():
    df = load_games_for_analysis('NHL', 2023, ...)
    df_pred = calculate_elo_predictions('NHL', df)
    metrics = calculate_decile_metrics(df_pred)
    assert len(metrics) <= 10
    assert all(metrics['decile'].between(1, 10))
```

### Integration Tests

```python
# Full pipeline test
def test_nhl_analysis_pipeline():
    league = 'NHL'
    season = 2023
    up_to_date = datetime(2024, 4, 1)

    df = load_games_for_analysis(league, season, up_to_date)
    assert len(df) > 100

    df_pred = calculate_elo_predictions(league, df)
    assert 'elo_prob' in df_pred.columns

    metrics = calculate_decile_metrics(df_pred)
    assert len(metrics) == 10 or len(metrics) < 10  # May have fewer due to duplicates

    # Verify metrics are reasonable
    assert all(metrics['lift'] > 0)
    assert all(metrics['win_rate'].between(0, 1))
```

---

## Performance Optimization

### Query Optimization

```sql
-- Good: Filters applied at database level
SELECT * FROM games
WHERE game_date >= '2023-10-01'
  AND game_date <= '2024-04-01'

-- Bad: Fetch all then filter in Python
SELECT * FROM games
# Then filter in pandas
```

### Memory Efficiency

```python
# Good: Keep only needed columns
df = conn.execute(query).fetchdf()  # Efficient

# Bad: Load unnecessary data
df = conn.execute("SELECT *").fetchdf()
```

### Caching Effectiveness

```python
# Good: Reuse cached data
@st.cache_data
def load_games_for_analysis(league, season, up_to_date):
    # This gets cached effectively

# Caching ineffective: Too specific cache keys
@st.cache_data
def plot_specific_chart(df, title, color):
    # Cache invalidates on every parameter change
```

---

## Deployment Considerations

### Environment Variables
```bash
export STREAMLIT_PORT=8501
export STREAMLIT_LOGGER_LEVEL=info
```

### Requirements
- Python 3.8+
- 4GB RAM (recommended)
- DuckDB database access
- (Optional) NBA JSON files

### Docker Deployment
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements_dashboard.txt .
RUN pip install -r requirements_dashboard.txt
COPY . .
CMD ["streamlit", "run", "dashboard_app.py"]
```

---

## Troubleshooting Guide

### Issue: Cache corruption
**Symptom:** Stale data showing after database update
**Solution:**
```python
st.cache_data.clear()
st.rerun()
```

### Issue: Memory leak on long sessions
**Symptom:** Increasing RAM usage over time
**Solution:** Add session timeout or memory monitoring

### Issue: Slow Elo calculation
**Symptom:** 30+ second load times
**Solution:**
- Pre-calculate Elo ratings offline
- Cache results in database
- Load pre-computed ratings instead

---

## Future Improvements

1. **Database Abstraction**
   - Support multiple database backends
   - Abstract SQL queries

2. **Async Loading**
   - Load data in background
   - Progressive UI updates

3. **Machine Learning**
   - Compare Elo vs other models
   - A/B testing framework

4. **Real-time Updates**
   - Live game scoring
   - Streaming data integration

5. **Mobile Optimization**
   - Responsive layout
   - Mobile-friendly charts

---

**Document Version:** 1.0
**Last Updated:** January 2024
