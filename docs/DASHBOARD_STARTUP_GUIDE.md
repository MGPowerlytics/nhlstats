# Dashboard Startup Guide

## Quick Start (Recommended)

The easiest way to run the dashboard is using the provided script:

```bash
./run_dashboard.sh
```

This script automatically sets the required environment variables.

## Manual Start

If you prefer to run Streamlit directly:

### Option 1: Set environment variables in your shell
```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=airflow
export POSTGRES_USER=airflow
export POSTGRES_PASSWORD=airflow

streamlit run dashboard_app.py
```

### Option 2: One-liner
```bash
POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=airflow POSTGRES_USER=airflow POSTGRES_PASSWORD=airflow streamlit run dashboard_app.py
```

### Option 3: Add to your shell profile
Add these lines to your `~/.bashrc` or `~/.zshrc`:
```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=airflow
export POSTGRES_USER=airflow
export POSTGRES_PASSWORD=airflow
```

Then reload: `source ~/.bashrc` and run: `streamlit run dashboard_app.py`

## Troubleshooting

### Error: "Connection refused" or "server at localhost"

**Check 1: Is PostgreSQL running?**
```bash
docker ps | grep postgres
```
You should see: `nhlstats-postgres-1` with status "Up"

**Check 2: Start PostgreSQL if needed**
```bash
cd /mnt/data2/nhlstats
docker compose up -d postgres
```

**Check 3: Test connection directly**
```bash
docker exec nhlstats-postgres-1 psql -U airflow -d airflow -c "SELECT 1;"
```

**Check 4: Verify environment variables**
```bash
echo $POSTGRES_HOST  # Should be: localhost
echo $POSTGRES_PORT  # Should be: 5432
```

If empty, you need to set them (see options above).

### Error: "psycopg2" or "sqlalchemy" not installed

```bash
pip install -r requirements_dashboard.txt
```

## Database Default Values

If environment variables are not set, these defaults are used:
- Host: `localhost`
- Port: `5432`
- Database: `airflow`
- User: `airflow`
- Password: `airflow`

These match the docker-compose configuration, so the dashboard should work without explicit environment variables if PostgreSQL is running on the default port.

## Verifying Database Connection

Test the connection without starting the dashboard:
```bash
python -c "
import sys
sys.path.insert(0, 'plugins')
from db_manager import default_db
result = default_db.fetch_df('SELECT COUNT(*) FROM unified_games')
print(f'Games in database: {result.iloc[0][0]}')
"
```

Expected output: `Games in database: 85610` (or similar number)
