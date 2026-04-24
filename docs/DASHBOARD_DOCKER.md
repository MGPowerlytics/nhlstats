# Running the Dashboard in Docker

The dashboard runs as a Docker container managed by docker-compose.

## Quick Start

```bash
# Start all services (including dashboard)
docker compose up -d

# Or start just dashboard (will auto-start postgres)
docker compose up -d dashboard
```

The dashboard will be available at: http://localhost:8501

## Configuration

The dashboard container is configured in `docker-compose.yaml` with these environment variables:

```yaml
environment:
  - POSTGRES_HOST=postgres      # Docker service name (NOT localhost!)
  - POSTGRES_PORT=5432
  - POSTGRES_DB=airflow
  - POSTGRES_USER=airflow
  - POSTGRES_PASSWORD=airflow
```

**Important:** Inside Docker containers, use the service name `postgres` as the hostname, not `localhost`.

## Checking Status

```bash
# View all running containers
docker compose ps

# Check dashboard logs
docker logs nhlstats-dashboard-1

# Follow dashboard logs in real-time
docker logs -f nhlstats-dashboard-1

# Check if dashboard can connect to database
docker exec nhlstats-dashboard-1 python -c "
import sys
sys.path.insert(0, '/opt/airflow/plugins')
from db_manager import default_db
result = default_db.fetch_df('SELECT COUNT(*) FROM unified_games')
print(f'Games: {result.iloc[0][0]}')
"
```

## Restarting Dashboard

```bash
# Restart dashboard only
docker compose restart dashboard

# Recreate dashboard container (after config changes)
docker compose up -d dashboard

# Stop and remove dashboard
docker compose down dashboard
```

## Troubleshooting

### Dashboard shows "Connection refused"

**Cause:** Environment variables not set or PostgreSQL not running.

**Solution:**
```bash
# 1. Check postgres is running
docker compose ps postgres

# 2. Recreate dashboard with correct env vars
docker compose up -d dashboard

# 3. Check logs
docker logs nhlstats-dashboard-1
```

### Dashboard not updating after code changes

**Cause:** Streamlit doesn't auto-reload in Docker.

**Solution:**
```bash
# Restart the container
docker compose restart dashboard
```

### Can't access dashboard at localhost:8501

**Check:**
```bash
# 1. Container is running
docker compose ps dashboard

# 2. Port is mapped correctly
docker ps | grep dashboard
# Should show: 0.0.0.0:8501->8501/tcp

# 3. Try from inside container
docker exec nhlstats-dashboard-1 curl -s http://localhost:8501 | head
```

## Development Mode

To run the dashboard locally (outside Docker) for development:

```bash
# Set environment variables for local PostgreSQL
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=airflow
export POSTGRES_USER=airflow
export POSTGRES_PASSWORD=airflow

# Run dashboard locally
streamlit run dashboard_app.py
```

Or use the helper script:
```bash
./run_dashboard.sh
```

## Viewing Logs

```bash
# Last 50 lines
docker logs nhlstats-dashboard-1 --tail 50

# Follow logs (Ctrl+C to stop)
docker logs -f nhlstats-dashboard-1

# Search logs for errors
docker logs nhlstats-dashboard-1 | grep -i error
```

## Database Connection Inside Docker

The key difference from local development:
- **Local:** `POSTGRES_HOST=localhost`
- **Docker:** `POSTGRES_HOST=postgres` (service name)

Docker's internal network allows containers to communicate using service names from docker-compose.yaml.

## Updating Dashboard

After making changes to `dashboard_app.py`:

```bash
# Restart to pick up changes
docker compose restart dashboard

# Or rebuild if dependencies changed
docker compose build dashboard
docker compose up -d dashboard
```

## Complete Restart

If you need to restart everything:

```bash
# Stop all services
docker compose down

# Start all services
docker compose up -d

# Check status
docker compose ps
```

## Status: ✓ CONFIGURED

Dashboard is properly configured to run in Docker with PostgreSQL on the internal Docker network.
