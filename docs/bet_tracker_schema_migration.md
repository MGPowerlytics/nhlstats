# Bet Tracker Schema Migration

## Problem

After migrating from DuckDB to PostgreSQL, the `placed_bets` table was missing several columns that were added in recent code updates. This caused insertion failures with errors like:

```
psycopg2.errors.UndefinedColumn: column "placed_time_utc" of relation "placed_bets" does not exist
```

## Root Cause

The `placed_bets` table was created with an older schema version. The `CREATE TABLE IF NOT EXISTS` statement in `bet_tracker.py` doesn't modify existing tables, so new columns weren't added automatically.

## Solution

A schema migration was performed to add the missing columns:

1. **placed_time_utc** (TIMESTAMP) - When the bet was placed (with timezone)
2. **market_title** (VARCHAR) - Human-readable market title
3. **market_close_time_utc** (TIMESTAMP) - When the market closes
4. **opening_line_prob** (DOUBLE PRECISION) - Market opening probability
5. **bet_line_prob** (DOUBLE PRECISION) - Probability when bet was placed
6. **closing_line_prob** (DOUBLE PRECISION) - Market closing probability
7. **clv** (DOUBLE PRECISION) - Closing Line Value (bet vs close)
8. **updated_at** (TIMESTAMP) - Last record update time

## Migration Script

Run the migration script to update the schema:

```bash
python scripts/migrate_placed_bets_schema.py
```

Or manually:

```sql
ALTER TABLE placed_bets ADD COLUMN IF NOT EXISTS placed_time_utc TIMESTAMP;
ALTER TABLE placed_bets ADD COLUMN IF NOT EXISTS market_title VARCHAR;
ALTER TABLE placed_bets ADD COLUMN IF NOT EXISTS market_close_time_utc TIMESTAMP;
ALTER TABLE placed_bets ADD COLUMN IF NOT EXISTS opening_line_prob DOUBLE PRECISION;
ALTER TABLE placed_bets ADD COLUMN IF NOT EXISTS bet_line_prob DOUBLE PRECISION;
ALTER TABLE placed_bets ADD COLUMN IF NOT EXISTS closing_line_prob DOUBLE PRECISION;
ALTER TABLE placed_bets ADD COLUMN IF NOT EXISTS clv DOUBLE PRECISION;
ALTER TABLE placed_bets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
```

## Verification

Check the table schema:

```bash
docker exec nhlstats-dashboard-1 python -c "
import sys
sys.path.insert(0, '/opt/airflow/plugins')
from db_manager import default_db
result = default_db.fetch_df('''
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'placed_bets'
ORDER BY ordinal_position
''')
print(result.to_string())
"
```

Expected: 29 columns total.

## Testing

Test bet sync functionality:

```bash
docker exec nhlstats-dashboard-1 python -c "
import sys
sys.path.insert(0, '/opt/airflow/plugins')
from bet_tracker import sync_bets_to_database
sync_bets_to_database()
"
```

Should successfully sync bets from Kalshi without errors.

## Prevention

To prevent this issue in future:

1. **Use migrations**: Create explicit migration scripts for schema changes
2. **Version control**: Track schema version in a separate table
3. **CI/CD checks**: Verify schema matches code expectations
4. **Documentation**: Document all schema changes in CHANGELOG

## Schema Management Best Practices

### For new columns:

```python
# Bad: CREATE TABLE IF NOT EXISTS doesn't add new columns
db.execute("CREATE TABLE IF NOT EXISTS placed_bets (...)")

# Good: Use ALTER TABLE with IF NOT EXISTS
db.execute("""
    ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS new_column VARCHAR
""")
```

### For schema versioning:

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    table_name VARCHAR PRIMARY KEY,
    version INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Status: ✅ RESOLVED

Schema migration complete. All 65 bets synced successfully (39 new, 26 updated).
