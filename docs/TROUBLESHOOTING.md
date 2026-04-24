# Dashboard Troubleshooting Guide

## Common Error: "Connection refused" when loading MLB data

### Symptoms
```
Error loading MLB data: (psycopg2.OperationalError) connection to server at "localhost" (::1),
port 5432 failed: Connection refused
```

### Root Cause
The dashboard cannot connect to PostgreSQL. This happens when:
1. PostgreSQL isn't running
2. Environment variables aren't set when Streamlit starts
3. Streamlit cached a failed connection attempt

### Solutions

#### Solution 1: Use the startup script (Recommended)
```bash
./run_dashboard.sh
```
This script sets all required environment variables automatically.

#### Solution 2: Clear Streamlit cache
If the dashboard was started when PostgreSQL was down, Streamlit may have cached the error:
```bash
# Clear Streamlit cache
rm -rf ~/.streamlit/cache/

# Restart dashboard with environment variables
./run_dashboard.sh
```

#### Solution 3: Verify PostgreSQL is running
```bash
# Check status
docker ps | grep postgres

# Start if needed
cd /mnt/data2/nhlstats
docker compose up -d postgres

# Wait for it to be healthy (10-15 seconds)
docker ps | grep postgres
# Should show: (healthy)
```

#### Solution 4: Set environment variables manually
```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=airflow
export POSTGRES_USER=airflow
export POSTGRES_PASSWORD=airflow

# Then start dashboard
streamlit run dashboard_app.py
```

#### Solution 5: Test connection before starting dashboard
```bash
# Test connection
python -c "
import sys; sys.path.insert(0, 'plugins')
from db_manager import default_db
print('Testing connection...')
result = default_db.fetch_df('SELECT 1 as test')
print(f'✓ Connection works! Result: {result.iloc[0][0]}')
"

# If this works, start dashboard
./run_dashboard.sh
```

## Other Common Issues

### Issue: "No module named 'db_manager'"
**Solution:** Make sure you're in the nhlstats directory
```bash
cd /mnt/data2/nhlstats
./run_dashboard.sh
```

### Issue: "ImportError: No module named 'psycopg2'"
**Solution:** Install dashboard requirements
```bash
pip install -r requirements_dashboard.txt
```

### Issue: "No data available"
**Solution:** Check if data exists in database
```bash
python -c "
import sys; sys.path.insert(0, 'plugins')
from db_manager import default_db
games = default_db.fetch_df('SELECT COUNT(*) FROM unified_games')
print(f'Games in database: {games.iloc[0][0]}')
"
```

### Issue: Dashboard loads but shows no teams
**Solution:** The data is there but filtered out. Check:
- Date range filter in sidebar
- Sport selection
- Data status on the page

## Restart Everything (Nuclear Option)

If nothing works, restart everything:
```bash
# Stop dashboard (Ctrl+C if running)

# Restart PostgreSQL
cd /mnt/data2/nhlstats
docker compose down
docker compose up -d postgres

# Wait for healthy status
sleep 15
docker ps | grep postgres  # Should show (healthy)

# Clear caches
rm -rf ~/.streamlit/cache/

# Start dashboard
./run_dashboard.sh
```

## Get Help

If you're still having issues:
1. Check PostgreSQL logs: `docker logs nhlstats-postgres-1`
2. Check connection string: See DASHBOARD_STARTUP_GUIDE.md
3. Verify data exists: Run queries in TROUBLESHOOTING.md
