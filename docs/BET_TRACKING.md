# Bet Recommendations Tracking System

## Overview

All bet recommendations are now automatically stored in the DuckDB database (`data/nhlstats.duckdb`) for historical analysis and performance tracking.

## Database Schema

### `bet_recommendations` Table

| Column | Type | Description |
|--------|------|-------------|
| `bet_id` | VARCHAR (PK) | Unique identifier: `{sport}_{date}_{index}_{home}_{away}` |
| `sport` | VARCHAR | Sport code (nba, nhl, mlb, nfl, epl, ncaab, tennis) |
| `recommendation_date` | DATE | Date the bet was recommended |
| `home_team` | VARCHAR | Home team name |
| `away_team` | VARCHAR | Away team name |
| `bet_on` | VARCHAR | Which side to bet on (home, away, Draw) |
| `elo_prob` | DOUBLE | Elo model predicted probability (0.0-1.0) |
| `market_prob` | DOUBLE | Market implied probability (0.0-1.0) |
| `edge` | DOUBLE | Betting edge (elo_prob - market_prob) |
| `confidence` | VARCHAR | Confidence level (HIGH, MEDIUM) |
| `yes_ask` | INTEGER | Kalshi yes price (cents) |
| `no_ask` | INTEGER | Kalshi no price (cents) |
| `ticker` | VARCHAR | Kalshi market ticker |
| `created_at` | TIMESTAMP | When the bet was loaded into DB |

## Workflow

The multi-sport betting DAG now includes an additional task for each sport:

```
download_games → load_db → update_elo → fetch_markets → identify_bets → load_bets_db
```

The `load_bets_db` task:
1. Reads bet recommendations from `data/{sport}/bets_{date}.json`
2. Inserts/updates records in the `bet_recommendations` table
3. Uses INSERT OR REPLACE to handle re-runs

## Usage

### Load Historical Bets

```python
from plugins.bet_loader import BetLoader

loader = BetLoader()

# Load bets for a specific date
count = loader.load_bets_for_date('nba', '2026-01-18')

# Load all historical bet files
from pathlib import Path

for sport in ['nba', 'nhl', 'mlb', 'nfl', 'epl', 'ncaab']:
    bet_files = Path(f'data/{sport}').glob('bets_*.json')
    for bet_file in bet_files:
        date_str = bet_file.stem.replace('bets_', '')
        loader.load_bets_for_date(sport, date_str)
```

### Analyze Bet Recommendations

```bash
# Run comprehensive analysis
python3 analyze_bets.py
```

### Query Database Directly

```python
import duckdb

conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)

# Get all high-edge bets
result = conn.execute("""
    SELECT sport, recommendation_date, home_team, away_team, edge, confidence
    FROM bet_recommendations
    WHERE edge > 0.15
    ORDER BY edge DESC
""").fetchall()

# Get sport performance summary
result = conn.execute("""
    SELECT 
        sport,
        COUNT(*) as total_bets,
        AVG(edge) as avg_edge,
        SUM(CASE WHEN confidence = 'HIGH' THEN 1 ELSE 0 END) as high_conf_bets
    FROM bet_recommendations
    GROUP BY sport
    ORDER BY avg_edge DESC
""").fetchall()

conn.close()
```

## Analysis Queries

### Best Opportunities by Edge

```sql
SELECT 
    recommendation_date,
    sport,
    away_team || ' @ ' || home_team as matchup,
    bet_on,
    edge,
    elo_prob,
    market_prob,
    confidence
FROM bet_recommendations
WHERE edge > 0.10
ORDER BY edge DESC
LIMIT 20;
```

### Performance by Sport

```sql
SELECT 
    sport,
    COUNT(*) as num_bets,
    AVG(edge) as avg_edge,
    AVG(elo_prob) as avg_elo_prob,
    MIN(edge) as min_edge,
    MAX(edge) as max_edge,
    SUM(CASE WHEN confidence = 'HIGH' THEN 1 ELSE 0 END) as high_conf_count
FROM bet_recommendations
GROUP BY sport
ORDER BY num_bets DESC;
```

### Daily Activity

```sql
SELECT 
    recommendation_date,
    COUNT(*) as total_bets,
    COUNT(DISTINCT sport) as sports_active,
    AVG(edge) as avg_edge,
    SUM(CASE WHEN edge > 0.20 THEN 1 ELSE 0 END) as high_edge_bets
FROM bet_recommendations
GROUP BY recommendation_date
ORDER BY recommendation_date DESC;
```

### Edge Distribution

```sql
SELECT 
    CASE 
        WHEN edge < 0.05 THEN '< 5%'
        WHEN edge < 0.10 THEN '5-10%'
        WHEN edge < 0.15 THEN '10-15%'
        WHEN edge < 0.20 THEN '15-20%'
        WHEN edge < 0.30 THEN '20-30%'
        ELSE '> 30%'
    END as edge_bucket,
    COUNT(*) as num_bets,
    AVG(elo_prob) as avg_elo_prob
FROM bet_recommendations
GROUP BY edge_bucket
ORDER BY MIN(edge);
```

## Future Enhancements

- [ ] Add actual game outcomes to track bet performance
- [ ] Calculate ROI based on bet outcomes
- [ ] Track market movement (open vs close prices)
- [ ] Add bet sizing recommendations (Kelly Criterion)
- [ ] Create dashboard for bet tracking
- [ ] Alert system for high-value opportunities

## Files

- `plugins/bet_loader.py` - Loads bet recommendations into database
- `analyze_bets.py` - Comprehensive bet analysis script
- `dags/multi_sport_betting_workflow.py` - Updated DAG with bet loading
- `data/nhlstats.duckdb` - Main database with `bet_recommendations` table
