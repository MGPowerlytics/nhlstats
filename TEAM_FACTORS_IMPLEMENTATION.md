# Team Factors Implementation Summary

## Overview
Implemented a daily data pipeline for fetching, storing, and using MLB team-level statistics to enhance probability calculations beyond pure Elo ratings.

## Components Created

### 1. Plugin: `plugins/team_factors.py`
Main module for fetching and managing team factors data.

**Functions:**
- `load_historical_team_factors()` - Loads pre-computed team stats from CSV
- `fetch_mlb_team_stats()` - Fetches current stats from MLB API (with fallback to historical)
- `store_team_factors(df)` - Stores team factors in PostgreSQL
- `fetch_team_factors(sport, date)` - Airflow task entry point
- `fetch_team_factors_for_game(sport, game_date, home_team, away_team)` - Fetches factors for specific game
- `create_team_factors_table()` - Creates database table

### 2. Database Table: `team_factors`
```sql
CREATE TABLE team_factors (
    factor_id SERIAL PRIMARY KEY,
    team_id VARCHAR NOT NULL,
    game_date DATE NOT NULL,
    season INTEGER,
    team_name VARCHAR,
    venue VARCHAR,
    runs_per_game DECIMAL(5,3),
    obp DECIMAL(5,3),
    slg DECIMAL(5,3),
    ops DECIMAL(5,3),
    wOBA DECIMAL(5,3),
    wRC_plus INTEGER,
    era DECIMAL(5,3),
    fip DECIMAL(5,3),
    whip DECIMAL(5,3),
    strikeouts_per_nine DECIMAL(5,2),
    walks_per_nine DECIMAL(5,2),
    defensive_runs_saved INTEGER,
    ultimate_zone_rating DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, game_date)
);
```

### 3. Historical Data: `data/mlb_team_factors.csv`
Pre-computed 2024 season statistics for all 30 MLB teams including:
- Offensive: OPS, OBP, SLG, wOBA, wRC+
- Pitching: ERA, FIP, WHIP, K/9, BB/9
- Defensive: DRS, UZR

### 4. DAG Integration: `dags/multi_sport_betting_workflow.py`
Added `fetch_team_factors` task that runs daily for MLB:
- Runs after `fetch_markets` task
- Stores factors in database for use in probability calculations
- Only active for MLB sport

## How Team Factors Adjust Probabilities

The `fetch_team_factors_for_game()` function calculates adjustments based on:

1. **OPS Differential** (60% weight): Compares each team's OPS to league average (~0.750)
2. **ERA Differential** (40% weight): Compares each team's ERA to league average (~4.50)

Formula:
```
home_adjustment = (home_ops_adj * 0.6 + home_era_adj * 0.4) / 10
away_adjustment = (away_ops_adj * 0.6 + away_era_adj * 0.4) / 10
```

Adjustments are capped at +/- 5% to prevent over-weighting team factors.

## Usage in Probability Calculation

To incorporate team factors into Elo probabilities:

```python
from plugins.team_factors import fetch_team_factors_for_game

# Get team adjustments
factors = fetch_team_factors_for_game(
    sport='mlb',
    game_date='2024-04-15',
    home_team='mlb_110',  # Baltimore Orioles
    away_team='mlb_147'   # New York Yankees
)

# Apply to base Elo probability
base_elo_prob = 0.60  # From Elo model
adjusted_prob = base_elo_prob + factors['home_adjustment'] - factors['away_adjustment']
adjusted_prob = min(max(adjusted_prob, 0.01), 0.99)  # Clip to valid range
```

## Pipeline Flow

```
Daily DAG Run (5 AM ET)
    │
    ▼
fetch_markets (gets Kalshi odds)
    │
    ▼
fetch_team_factors (MLB only) ──► Fetches from CSV or API
    │                              │
    │                              ▼
    │                         store_team_factors
    │                              │
    │                              ▼
    └─────────────────────────► PostgreSQL team_factors table
                                   │
                                   ▼
                              identify_good_bets
                                   │
                                   ▼
                              fetch_team_factors_for_game()
                                   │
                                   ▼
                              Apply adjustments to probabilities
```

## Testing

Run the pipeline manually:
```bash
export PYTHONPATH=/mnt/data2/nhlstats/plugins:/mnt/data2/nhlstats
export POSTGRES_HOST=localhost
python -c "
from team_factors import fetch_team_factors
fetch_team_factors('mlb', '2024-04-15')
"
```

Verify data in database:
```sql
SELECT team_name, ops, era FROM team_factors
ORDER BY ops DESC
LIMIT 10;
```

## Next Steps

1. **Integrate with Portfolio Optimizer**: Modify `plugins/portfolio_optimizer.py` to fetch and apply team factors when calculating probabilities.

2. **Expand Historical Data**: Add multi-year data (2021-2024) for better trend analysis.

3. **Add More Metrics**: Include park factors, bullpen strength, recent form (last 10 games).

4. **Backtest Impact**: Re-run the backtest with team factors integrated to measure ROI improvement.

5. **Extend to Other Sports**: Adapt the pipeline for NBA, NHL using their respective APIs.

## Files Modified/Created

| File | Action | Purpose |
|------|--------|---------|
| `plugins/team_factors.py` | Created | Main pipeline module |
| `data/mlb_team_factors.csv` | Created | Historical team stats |
| `dags/multi_sport_betting_workflow.py` | Modified | Added fetch_team_factors task |
| `plugins/db_manager.py` | Unchanged | Uses existing default_db |

## Key Design Decisions

1. **CSV-first approach**: Uses pre-computed historical data as primary source since MLB API has seasonal availability issues.

2. **Fallback chain**: CSV → API (current season) → API (prior seasons) ensures data availability.

3. **Simple adjustments**: Linear combination of OPS and ERA provides interpretable adjustments without overfitting.

4. **Capped impact**: +/- 5% maximum adjustment prevents team factors from overwhelming Elo base probability.

5. **Sport-specific**: Currently MLB-only, with architecture supporting expansion to other sports.
