# DuckDB Multi-Session Access Guide

## The Issue
DuckDB uses file-level locking. By default, only ONE process can have a write connection open.

## Solution: Connection Management

### 1. **Writer (Airflow DAG)** - Use Short-Lived Connections
```python
def load_into_duckdb(date_str, **context):
    """Load NHL data - connection opens and closes within this function"""
    from nhl_db_loader import load_nhl_data_for_date
    
    # This function opens connection, loads data, and CLOSES connection
    games_count = load_nhl_data_for_date(date_str)
    print(f"Loaded {games_count} games - connection closed")
    # Connection is now closed - other processes can access!
```

### 2. **Readers (Analysis/Queries)** - Use read_only=True
```python
import duckdb

# Read-only connections can run in parallel!
conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)

# Run your queries...
games = conn.execute("SELECT * FROM games LIMIT 10").fetchall()

conn.close()
```

### 3. **Multiple Readers At Once** ✅
```bash
# Terminal 1
python query_nhl_stats.py

# Terminal 2 (at the same time!)
python analyze_betting_odds.py

# Terminal 3 (also at the same time!)
python train_ml_model.py
```

All readers can run simultaneously as long as no writer has the DB open!

## Current Problem
Your loader might be keeping the connection open. Let's verify it closes properly.

## Option 2: Access Modes (DuckDB 1.0+)

For advanced use cases, DuckDB supports multiple connection modes:

```python
# Default - exclusive write access
conn = duckdb.connect('db.duckdb')

# Read-only - multiple readers allowed  
conn = duckdb.connect('db.duckdb', read_only=True)

# Read-write with checkpoint_wal  
conn = duckdb.connect('db.duckdb', config={'checkpoint_wal_on_close': True})
```

## Best Practice for Your Use Case

**Airflow DAG Pattern:**
1. Download data (no DB connection)
2. Open connection →  load data → close connection (quick!)
3. Now anyone can query with read_only=True

**Query/Analysis Pattern:**
- Always use `read_only=True` for queries
- No locks, multiple sessions work fine
- Perfect for Jupyter notebooks, analysis scripts, ML training

## Testing Multi-Session Access

```bash
# Check if DB is locked
lsof data/nhlstats.duckdb  # Should show no processes

# Run query - should work!
docker compose exec airflow-scheduler python query_nhl_stats.py

# From another terminal simultaneously
docker compose exec airflow-worker python query_nhl_stats.py
```

Both should work if no writer is active!
