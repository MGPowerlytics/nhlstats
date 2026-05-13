# Dashboard Redesign Spec

**Date:** 2026-05-01
**Status:** Approved

## Problem

The current dashboard (`dashboard/dashboard_app.py`) is a 2,475-line monolithic Streamlit app with embedded SQL, no data freshness indicators, minimal caching, and zero tests. It reads from 3 of 16 available database tables. Users cannot answer "why was this bet placed?", cannot see live Elo rankings, cannot view odds market data, and cannot assess model calibration quality efficiently.

## Goals

1. **Portfolio health at a glance** — value, P&L, open positions, win rate, drill-down to individual bets
2. **Bet traceability** — every number that went into a placement decision visible on one page
3. **System health awareness** — live odds, current Elo ratings, model calibration, data quality
4. **Near real-time** — auto-refreshing with configurable intervals per page
5. **Locked contracts** — consumer-driven JSON Schema contracts between dashboard data layer and database

## Architecture

```
dashboard/
├── app.py                    # Entry point: sidebar nav, auto-refresh loop (~80 lines)
├── data_layer.py             # ALL SQL queries, @st.cache_data, returns DataFrames (~300 lines)
├── pages/
│   ├── portfolio.py          # Portfolio health & P&L (~250 lines)
│   ├── live_markets.py       # Today's games, odds, recommendations (~250 lines)
│   ├── rankings.py           # Elo ratings, team comparison (~300 lines)
│   ├── calibration.py        # Model accuracy charts (~250 lines)
│   ├── data_quality.py       # Health checks & validation (~200 lines)
│   └── bet_detail.py         # Drill-down: full bet audit trail (~200 lines)
├── contracts/
│   └── *.json                # 10 JSON Schema files, one per data function
└── __init__.py
```

**Key rule:** SQL lives ONLY in `data_layer.py`. Page files import functions and render UI. No SQL strings outside `data_layer.py`.

## Pages

### 1. Portfolio (Home)
- KPI cards: portfolio value, daily P&L, open bets count, win rate, total exposure
- Portfolio value line chart (daily/weekly/monthly toggle)
- P&L by sport bar chart
- Recent activity table (placed, settled) — every row clickable → Bet Detail
- ROI by sport
- Auto-refresh: 30s

### 2. Live Markets
- Today's games by sport, with Elo win probabilities and best available odds
- Edge indicators (green/yellow/red based on threshold)
- Active bet recommendations the system wants to place
- "Starting soon" section
- Odds source status (Kalshi, BetMGM, DraftKings — last fetch timestamp)
- Auto-refresh: 30s

### 3. Rankings
- Current Elo ratings table, sortable by sport/rating
- Rating change sparklines (last 7/30 days)
- Team comparison tool: pick two teams → head-to-head prediction with rating overlay chart
- Sport selector in sidebar
- Auto-refresh: 300s (5 min)

### 4. Calibration
- Calibration curves per sport (predicted probability vs actual win rate)
- Edge-vs-actual-ROI scatter plot
- Confidence level breakdown (HIGH/MEDIUM/LOW accuracy)
- Recent vs historical performance comparison
- Weekly EV trend
- Auto-refresh: 3600s (1 hr)

### 5. Data Quality
- Health score per sport (bar chart)
- Missing game data alerts
- Stale Elo ratings warnings
- Odds feed status indicators
- Recent DAG run statuses
- Expandable per-sport detail reports
- Auto-refresh: 300s

### 6. Bet Detail (drill-down, not a nav item)
Accessible by clicking any bet row anywhere in the dashboard.

Shows:
- Header: sport, market, placed timestamp, settlement result
- Decision panel: Elo probability, market implied probability, edge %, confidence level, Kelly fraction, stake
- Elo rating snapshot at bet time (both teams, rating diff, home advantage)
- Odds comparison table (Kalshi, BetMGM, DraftKings — price, implied prob, edge, timestamp)
- Elo rating history chart (30 days before bet, annotated with bet placement time)
- Recent form for both teams (last 5 games)

Data sources: `placed_bets` + `game_odds` + `elo_ratings` + `unified_games`

## Data Layer (`data_layer.py`)

All functions are decorated with `@st.cache_data` with TTLs. Each has a corresponding JSON Schema contract.

| Function | TTL | Source Tables | Contract |
|---|---|---|---|
| `get_portfolio_summary()` | 30s | placed_bets, portfolio_value_snapshots | portfolio_summary_v1.json |
| `get_placed_bets(limit, status, sport)` | 30s | placed_bets | placed_bet_row_v1.json |
| `get_bet_detail(bet_id)` | manual | placed_bets, game_odds, elo_ratings, unified_games | bet_detail_v1.json |
| `get_current_elo_ratings(sport)` | 300s | elo_ratings | elo_ratings_v1.json |
| `get_today_games(sport)` | 30s | unified_games, elo_ratings, game_odds | today_game_v1.json |
| `get_bet_recommendations(sport)` | 30s | bet_recommendations | bet_recommendation_v1.json |
| `get_calibration_data(sport)` | 3600s | placed_bets | calibration_data_v1.json |
| `get_elo_history(team, days)` | 300s | elo_ratings | elo_history_v1.json |
| `get_data_quality_report()` | 300s | unified_games, elo_ratings, game_odds | data_quality_v1.json |
| `get_portfolio_snapshots(hours)` | 300s | portfolio_value_snapshots | portfolio_snapshots_v1.json |

## Contracts

JSON Schema (draft 2020-12) files in `dashboard/contracts/`. Consumer-driven: the dashboard defines the shape it needs, tests validate producers deliver it.

Contract tests in `tests/contracts/test_dashboard_data_contracts.py`:
- Validate each data function's output against its schema
- Validate required fields are non-null in real data
- Validate enum values, numeric ranges, timestamp formats
- Run against test database with known data

## Auto-Refresh

- Each page defines `REFRESH_SECONDS` constant
- `app.py` runs `st.rerun()` loop with `time.sleep(REFRESH_SECONDS)`
- On each cycle, busts expired cache entries
- Refresh indicator in sidebar: green dot + "Last updated: Xs ago" + countdown to next refresh
- Manual "Refresh Now" button available
- Stale data warning banner when data exceeds expected freshness

## Migration

**Deleted:** `dashboard/dashboard_app.py` (entire 2,475-line file)

**Adapted into data_layer.py:**
- Data Quality SQL queries
- CLV analysis queries (become calibration data)
- EV analysis queries (become calibration data)
- Portfolio snapshot loading

**Imported as-is (unchanged):**
- `plugins/data_validation.py` — used by data quality page
- `plugins/clv_tracker.py` — used by calibration page
- All existing Elo plugin code (no changes to Elo system)

**Docker change:** One line in `docker-compose.yaml` — command points to `dashboard/app.py`

## Testing Strategy

### Contract Tests (new)
`tests/contracts/test_dashboard_data_contracts.py` — validates every data_layer function against its schema. Uses test database with fixture data. Extends existing contract test patterns from `tests/contracts/test_dashboard_bet_opportunity_consumer.py`.

### Dashboard Unit Tests (new)
`tests/test_dashboard_data_layer.py` — tests for data_layer functions with SQLite test database, verifying query correctness, cache behavior, edge cases (empty results, null handling).

### Existing Tests (unchanged)
All existing tests continue to pass. No changes to plugins, DAGs, or database schema.

## Implementation Order

1. Create `dashboard/contracts/` — all 10 JSON schemas
2. Create `tests/contracts/test_dashboard_data_contracts.py` — tests fail (no data layer yet)
3. Create `dashboard/data_layer.py` — implement all 10 functions, tests pass
4. Create `dashboard/pages/bet_detail.py` — drill-down (no dependencies on other pages)
5. Create `dashboard/app.py` — sidebar nav, auto-refresh loop
6. Create `dashboard/pages/portfolio.py`
7. Create `dashboard/pages/live_markets.py`
8. Create `dashboard/pages/rankings.py`
9. Create `dashboard/pages/calibration.py`
10. Create `dashboard/pages/data_quality.py`
11. Update `docker-compose.yaml` — point to new entry point
12. Delete `dashboard/dashboard_app.py`
13. Run full test suite, verify dashboard renders
