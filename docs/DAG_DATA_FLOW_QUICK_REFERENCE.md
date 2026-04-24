# DAG Data Flow Quick Reference

## Critical Data Paths

### 1. **Bet Recommendations Path** (MOST IMPORTANT)
```
External APIs → JSON Files → Database → Portfolio Betting → Kalshi API
    ↓              ↓           ↓              ↓               ↓
 Download      Load to     Identify      Optimize &      Place Bets
  Games         DB          Bets          Place
```

**Key Table**: `bet_recommendations` (primary source for portfolio betting)

### 2. **Portfolio Value Path**
```
Kalshi API → Hourly Snapshot → Database → Dashboard
    ↓              ↓              ↓           ↓
 Balance      Record in      Store in    Display
              portfolio_     portfolio_   charts
              snapshots      snapshots
```

**Key Table**: `portfolio_snapshots` (hourly values for dashboard)

### 3. **Placed Bets Tracking Path**
```
Kalshi API → Hourly Sync → Database → Dashboard/Reports
    ↓              ↓           ↓           ↓
  Fills        Upsert      Store in    Track P/L
  Data         placed_     placed_
               bets        bets
```

**Key Table**: `placed_bets` (track bet status and outcomes)

---

## Task Data Sources & Destinations

### **Core Processing Tasks**

| Task | Data Source | Data Destination | Critical For |
|------|-------------|------------------|--------------|
| `{sport}_download_games` | External APIs | JSON files | Game schedule |
| `{sport}_load_db` | JSON files | `unified_games` table | All downstream tasks |
| `{sport}_update_elo` | Game tables | CSV files + XCom | Bet identification |
| `{sport}_fetch_markets` | Kalshi API | `game_odds` table | Market comparison |
| `{sport}_identify_bets` | Elo + Markets | JSON files | Bet opportunities |
| `{sport}_load_bets_db` | JSON files | `bet_recommendations` table | **PORTFOLIO BETTING** |

### **Portfolio Tasks**

| Task | Data Source | Data Destination | Critical For |
|------|-------------|------------------|--------------|
| `portfolio_optimized_betting` | `bet_recommendations` table | Kalshi API + JSON | **ACTUAL BETTING** |
| `update_clv_data` | `placed_bets` + `game_odds` | CLV tables | Performance analysis |
| `send_daily_summary` | Kalshi + Portfolio files | SMS | User notifications |

### **Hourly Tasks**

| Task | Data Source | Data Destination | Critical For |
|------|-------------|------------------|--------------|
| `sync_bets_from_kalshi` | Kalshi API | `placed_bets` table | Bet tracking |
| `snapshot_portfolio_value` | Kalshi API | `portfolio_snapshots` table | Dashboard charts |

---

## Validation Tasks (NEW - 2026-01-29)

### **Per Sport Validation Chain**
```
download_games → validate_games → load_db → [update_elo, fetch_markets]
                    ↓                    ↓                    ↓
               Games exist?      Loaded to DB?     [Elo calculated?, Markets fetched?]
```

### **Validation Task Purposes**
1. **`{sport}_validate_games`**: Check games downloaded (files + database)
2. **`{sport}_validate_elo`**: Check Elo ratings calculated (files + XCom)
3. **`{sport}_validate_markets`**: Check markets fetched (files + database)
4. **`{sport}_validate_bets`**: Check bets identified (files + database)

**Failure Action**: All raise `ValueError` with clear message

---

## Database Tables by Data Flow

### **Primary Data Tables**
- `unified_games`: Central game schedule (source for Elo)
- `game_odds`: Market prices (source for bet identification)
- `bet_recommendations`: **CRITICAL**: Bet opportunities (source for portfolio)
- `placed_bets`: Tracked bets (destination from Kalshi)
- `portfolio_snapshots`: Hourly values (destination from Kalshi)

### **Model Output Tables**
- `elo_ratings`: Historical Elo ratings
- CLV tables: Closing line value tracking

### **Supporting Tables**
- Sport-specific game tables (e.g., `nba_games`, `nhl_games`)
- Index tables for performance

---

## File System Storage

### **JSON Files (Temporary/Backup)**
```
data/{sport}/games_{date}.json     # Raw game data
data/{sport}/markets_{date}.json   # Raw market data
data/{sport}/bets_{date}.json      # Bet recommendations
data/portfolio/betting_*.json      # Portfolio results
```

### **CSV Files (Model Output)**
```
data/{sport}_current_elo_ratings.csv      # Current Elo ratings
data/{sport}_current_glicko2_ratings.csv  # Current Glicko-2 ratings
```

### **File vs Database Strategy**
- **Primary**: Database (consistent, transactional)
- **Secondary**: JSON files (backup, debugging)
- **Model Output**: CSV files (easy analysis)

---

## Error Recovery Guide

### **Common Failure Points**

#### 1. **No Games Downloaded**
- **Check**: `{sport}_validate_games` failed
- **Fix**: Check API keys, network, external API status
- **Recovery**: Rerun `{sport}_download_games`

#### 2. **No Markets Fetched**
- **Check**: `{sport}_validate_markets` failed
- **Fix**: Check Kalshi API, market availability
- **Recovery**: Rerun `{sport}_fetch_markets`

#### 3. **No Bets Identified**
- **Check**: `{sport}_validate_bets` failed
- **Fix**: Check Elo ratings, market data alignment
- **Recovery**: Check `{sport}_update_elo` and `{sport}_fetch_markets`

#### 4. **Portfolio Betting Failed**
- **Check**: `portfolio_optimized_betting` failed
- **Fix**: Check `bet_recommendations` table has data
- **Recovery**: Ensure all `{sport}_load_bets_db` completed

### **Data Consistency Checks**
```sql
-- Check games loaded
SELECT COUNT(*) FROM unified_games WHERE game_date = '2026-01-29';

-- Check markets fetched
SELECT COUNT(*) FROM game_odds WHERE game_date = '2026-01-29';

-- Check bet recommendations
SELECT COUNT(*) FROM bet_recommendations WHERE recommendation_date = '2026-01-29';

-- Check portfolio betting ran
SELECT COUNT(*) FROM placed_bets WHERE placed_date = '2026-01-29';
```

---

## Performance Tips

### **Parallel Processing Opportunities**
1. **Sports**: 9 sports process in parallel
2. **Elo vs Markets**: Independent, run concurrently
3. **Validation**: Minimal overhead, runs quickly

### **Bottlenecks to Monitor**
1. **External APIs**: Rate limits, network latency
2. **Database**: Connection pool, query performance
3. **Kalshi API**: Bet placement rate limits

### **Optimization Strategies**
1. **Caching**: Reuse Elo ratings when possible
2. **Batching**: Group similar operations
3. **Connection Pooling**: Reuse database connections

---

## Monitoring Checklist

### **Daily Checks**
- [ ] All 9 sports completed `load_bets_db`
- [ ] `bet_recommendations` table has data for today
- [ ] `portfolio_optimized_betting` completed successfully
- [ ] `placed_bets` has new entries for today
- [ ] `portfolio_snapshots` has hourly entries

### **Data Quality Checks**
- [ ] No NULL critical fields in `bet_recommendations`
- [ ] `edge` values reasonable (typically 0.05-0.20)
- [ ] `confidence` values reasonable (typically "HIGH"/"MEDIUM")
- [ ] `ticker` fields populated (required for betting)

### **System Health Checks**
- [ ] Database connections healthy
- [ ] External APIs reachable
- [ ] File system has free space
- [ ] Airflow scheduler running

---

## Contact & Support

### **Integration Issues**
- **Primary**: Check `DAG_TASK_DATA_FLOW.md` for detailed documentation
- **Secondary**: Review task logs in Airflow UI
- **Tertiary**: Check database for data consistency

### **Emergency Recovery**
1. **Stop**: Pause DAG in Airflow UI
2. **Diagnose**: Check latest failed task logs
3. **Fix**: Address root cause (API, data, configuration)
4. **Restart**: Clear failed tasks and resume

### **Documentation**
- `DAG_TASK_DATA_FLOW.md`: Complete task documentation
- `database_schema.md`: Database structure and relationships
- This file: Quick reference guide

---

*Last Updated: 2026-01-29*
*Integration Engineering Team*
