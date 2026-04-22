# Operations Runbook

This document covers day-to-day operational procedures for the multi-sport
betting system, with emphasis on the **placed-bets reconciliation** pipeline
and the **historical stats backfill / daily stats ingestion** pipeline.

Supported runtime guardrails for all procedures in this runbook:

- secrets are provided through environment variables and `/run/secrets` only
- the Airflow runtime is image-baked; live-container `pip install` is unsupported
- persistent state uses named volumes rather than repo-root bind mounts
- production schema readiness is governed by checked-in migrations plus the
  `schema_migrations` ledger

---

## Table of Contents

1. [Bet Reconciliation Overview](#1-bet-reconciliation-overview)
2. [Running a Historical Backfill](#2-running-a-historical-backfill)
3. [Daily Automated Reconciliation (DAG)](#3-daily-automated-reconciliation-dag)
4. [Inspecting Audit Logs](#4-inspecting-audit-logs)
5. [Troubleshooting Reconciliation Failures](#5-troubleshooting-reconciliation-failures)
6. [Database Maintenance](#6-database-maintenance)
7. [Race-Condition Prevention: Reconciliation vs. Hourly Bet Sync](#7-race-condition-prevention-reconciliation-vs-hourly-bet-sync)
8. [Historical Stats Backfill (team_game_stats)](#8-historical-stats-backfill-team_game_stats)
9. [Stats DAG Pool Setup](#9-stats-dag-pool-setup)
10. [Troubleshooting: Stats Pipeline](#10-troubleshooting-stats-pipeline)
11. [Contact and Escalation](#11-contact-and-escalation)

---

## 1. Bet Reconciliation Overview

The reconciliation pipeline compares local `placed_bets` rows against
Kalshi's source-of-truth fills and auto-corrects discrepancies.

### Key components

| Component | Location | Purpose |
|-----------|----------|---------|
| `bet_audit.py` | `plugins/bet_audit.py` | Low-level INSERT/SELECT for `bet_reconciliation_audit` |
| `bet_reconciliation.py` | `plugins/bet_reconciliation.py` | Core reconciliation logic |
| `reconcile_bets_historical.py` | `scripts/reconcile_bets_historical.py` | CLI for ad-hoc / historical runs |
| `reconcile_placed_bets` task | `dags/multi_sport_betting_workflow.py` | Daily automated run |

### Fields reconciled

Only the following `placed_bets` columns are overwritten by Kalshi data:

- `contracts`
- `price_cents`
- `cost_dollars`
- `fees_dollars`
- `status`
- `settled_date`
- `payout_dollars`
- `profit_dollars`

All changes are **immutably logged** in `bet_reconciliation_audit` before
being applied.

---

## 2. Running a Historical Backfill

Use `scripts/reconcile_bets_historical.py` for one-off or catch-up runs.
The script is **idempotent** – safe to re-run without creating duplicate
audit rows.

### Basic usage (all bets)

```bash
cd /mnt/data2/nhlstats
python scripts/reconcile_bets_historical.py
```

This queries `MIN(placed_time_utc)` from `placed_bets` and reconciles
everything from that date forward.

### From a specific date

```bash
python scripts/reconcile_bets_historical.py --since 2024-01-01
```

### Dry run (no writes)

```bash
python scripts/reconcile_bets_historical.py --dry-run
```

Fetches Kalshi state and prints what *would* happen without touching the DB.

### Save summary to JSON

```bash
python scripts/reconcile_bets_historical.py --since 2024-06-01 \
    --output-json data/recon_summary_2024.json
```

### CLI reference

```
usage: reconcile_bets_historical.py [-h] [--since YYYY-MM-DD] [--dry-run]
                                    [--output-json FILE] [--verbose]

optional arguments:
  --since YYYY-MM-DD   Only reconcile bets placed on or after this date.
                       Default: earliest placed bet date from the database.
  --dry-run            Print what would be reconciled without making changes.
  --output-json FILE   Write the summary dict as JSON to this file path.
  -v, --verbose        Enable DEBUG logging.
```

---

## 3. Daily Automated Reconciliation (DAG)

The `reconcile_placed_bets` Airflow task runs automatically each day as part
of `multi_sport_betting_workflow`.

### Task position in the DAG

```
… → update_clv_data → reconcile_placed_bets → send_daily_summary
```

### Task configuration

| Setting | Value |
|---------|-------|
| `task_id` | `reconcile_placed_bets` |
| `retries` | 2 |
| Runs after | `update_clv_data` |
| Runs before | `send_daily_summary` |

### Triggering manually

```bash
docker exec $(docker ps -qf "name=airflow-apiserver") \
    airflow tasks test multi_sport_betting_workflow reconcile_placed_bets "$(date +%Y-%m-%d)"
```

---

## 4. Inspecting Audit Logs

### All audit rows for a specific bet

```sql
SELECT *
FROM   bet_reconciliation_audit
WHERE  bet_id = 'BET-001'
ORDER  BY reconciled_at DESC;
```

### All changes in the last 24 hours

```sql
SELECT *
FROM   bet_reconciliation_audit
WHERE  reconciled_at >= NOW() - INTERVAL '1 day'
ORDER  BY reconciled_at DESC;
```

### Summary of changes by field

```sql
SELECT field_changed, COUNT(*) AS changes
FROM   bet_reconciliation_audit
GROUP  BY field_changed
ORDER  BY changes DESC;
```

### Using the Python helper

```python
from plugins.bet_audit import get_audit_history
from plugins.db_manager import DBManager

db = DBManager()

# All changes for one bet
history = get_audit_history(db, bet_id="BET-001")

# Changes since a date
from datetime import date
history = get_audit_history(db, since=date(2024, 6, 1))
```

---

## 5. Troubleshooting Reconciliation Failures

### "Could not connect to database"

Verify PostgreSQL is running:

```bash
docker ps | grep postgres
# or
docker exec nhlstats-postgres-1 pg_isready -U airflow
```

### "Could not construct default KalshiBetting client"

Check that `KALSHI_API_KEY_ID` / `KALSHI_PRIVATE_KEY_PATH` environment
variables are set and that `KALSHI_PRIVATE_KEY_PATH` points at the runtime
secret mount under `/run/secrets`:

```bash
docker exec $(docker ps -qf "name=airflow-scheduler") \
    env | grep -i kalshi
```

### Reconciliation task stuck / timeout

Check that Kalshi pagination is not hitting an infinite loop:

```bash
docker logs nhlstats-airflow-worker-1 --tail 200 | grep reconcil
```

### Duplicate audit rows

The `insert_audit_row` helper only writes rows when `diff_bet` reports a
discrepancy.  Re-running reconcile on an already-corrected bet produces
**zero** diff entries, so no duplicate rows are written.

If you suspect stale duplicates, query:

```sql
SELECT bet_id, field_changed, reconciled_at, run_id
FROM   bet_reconciliation_audit
ORDER  BY bet_id, field_changed, reconciled_at;
```

---

## 6. Database Maintenance

### Schema initialisation

Production schema ownership belongs to the governed migration chain and the
`schema_migrations` ledger. Use the checked-in migration wrappers if schema
verification fails or a local runtime needs to be brought into compliance:

```bash
bash scripts/apply_stats_schema_migrations.sh
bash scripts/verify_stats_schema_migrations.sh
```

Verify the authoritative ledger directly:

```sql
SELECT version, name, checksum, applied_at
FROM schema_migrations
ORDER BY version;
```

`DatabaseSchemaManager` and `bet_tracker` helpers remain compatibility-only for
non-PostgreSQL and local paths; they no longer own production schema evolution.

### Archiving old audit rows

Audit rows are append-only by design.  Archive rows older than 90 days to
a cold-storage table:

```sql
-- Create archive table (one-time)
CREATE TABLE IF NOT EXISTS bet_reconciliation_audit_archive
    (LIKE bet_reconciliation_audit INCLUDING ALL);

-- Move rows older than 90 days
WITH moved AS (
    DELETE FROM bet_reconciliation_audit
    WHERE reconciled_at < NOW() - INTERVAL '90 days'
    RETURNING *
)
INSERT INTO bet_reconciliation_audit_archive SELECT * FROM moved;
```

### Index health

```sql
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_fetch
FROM   pg_stat_user_indexes
WHERE  tablename = 'bet_reconciliation_audit';
```

---

## 7. Race-Condition Prevention: Reconciliation vs. Hourly Bet Sync

### Background

Two DAGs write to the `placed_bets` table:

| DAG | Schedule | What it writes |
|-----|----------|----------------|
| `bet_sync_hourly` | `@hourly` (top of each hour) | Upserts fills from Kalshi API |
| `multi_sport_betting_workflow` | Daily at 10:00 AM UTC | Runs `reconcile_placed_bets` task |

Because the daily DAG starts at exactly 10:00 AM UTC — the same moment the
hourly sync fires — the `reconcile_placed_bets` task could run concurrently
with `bet_sync_hourly`, causing **simultaneous writes to the same rows**.

### Strategy: Reconciliation Lookback Window (Option A)

`reconcile_all()` accepts a `cutoff_minutes` parameter (default **15**).

When active, any `placed_bets` row whose `created_at` timestamp falls within
the last `cutoff_minutes` minutes is **excluded** from the reconciliation
pass via a SQL `WHERE` clause:

```sql
WHERE (created_at IS NULL OR created_at <= :cutoff_ts)
```

where `cutoff_ts = UTC_NOW() - 15 minutes`.

#### Why this works

- By the time `reconcile_placed_bets` executes (~10:05–10:15 AM, after
  upstream tasks), any fill synced during the 9:45–10:00 window is within
  the 15-minute exclusion zone.
- Those bets will be reconciled on the **next daily run** (10:00 AM the
  following day) once they are safely outside the cutoff window.
- The `bet_sync_hourly` run at 10:00 AM is the only potential overlapper;
  the next hourly sync (11:00 AM) is well outside the daily reconciliation
  window.

#### Trade-off

Very recently placed bets (< 15 min old) will not be reconciled on the same
day they are placed.  This is an acceptable delay — reconciliation is a
correctness check, not a real-time requirement.

#### Disabling the window

Pass `cutoff_minutes=0` to reconcile all bets regardless of age (useful for
historical backfills):

```python
from bet_reconciliation import reconcile_all
summary = reconcile_all(cutoff_minutes=0)
```

### Summary dict keys added

`reconcile_all` now returns two additional keys:

| Key | Type | Meaning |
|-----|------|---------|
| `excluded_by_cutoff` | `int` | Number of bets skipped due to the cutoff window |
| `cutoff_ts` | `str \| None` | ISO-8601 UTC timestamp used as the cutoff (``None`` when disabled) |

### Monitoring the cutoff

Check how many bets are typically excluded per run:

```sql
SELECT
    DATE(reconciled_at) AS run_date,
    COUNT(DISTINCT run_id) AS runs
FROM bet_reconciliation_audit
GROUP BY run_date
ORDER BY run_date DESC
LIMIT 14;
```

The Airflow task logs also print the cutoff timestamp at INFO level:

```
reconcile_all starting: cutoff_minutes=15, cutoff_ts=2026-01-27T09:45:03+00:00
reconcile_all: 2 bet(s) excluded by 15-minute cutoff window
```

---

## 8. Historical Stats Backfill (team_game_stats)

Use `scripts/backfill_team_game_stats.py` to populate `team_game_stats` and
all per-sport extension tables from 2021-01-01 to the current date.

### Basic usage (all sports, 2021 → yesterday)

```bash
cd /mnt/data2/nhlstats
python scripts/backfill_team_game_stats.py
```

### Single sport

```bash
python scripts/backfill_team_game_stats.py --sport nba
```

Available sport keys: `nba nhl mlb nfl epl ligue1 ncaab wncaab tennis all`

### Date range

```bash
python scripts/backfill_team_game_stats.py --sport nhl \
    --start 2023-10-01 --end 2024-06-30
```

### Dry run (no network calls, no DB writes)

```bash
python scripts/backfill_team_game_stats.py --sport nba --dry-run
```

### Resume an interrupted run

The script writes progress to `data/stats_backfill_progress.json`.
Pass `--resume` to skip dates already completed:

```bash
python scripts/backfill_team_game_stats.py --sport nba --resume
```

### CLI reference

```
usage: backfill_team_game_stats.py [-h]
    [--sport {nba,nhl,mlb,nfl,epl,ligue1,ncaab,wncaab,tennis,all}]
    [--start YYYY-MM-DD] [--end YYYY-MM-DD]
    [--dry-run] [--resume] [-v]

optional arguments:
  --sport    Sport to backfill (default: all)
  --start    Start date (default: 2021-01-01)
  --end      End date (default: yesterday UTC)
  --dry-run  Show what would happen; no writes
  --resume   Skip dates already in progress file
  -v         Verbose / DEBUG logging
```

### Rollback

The backfill uses `ON CONFLICT DO UPDATE` (upsert). To roll back a specific
sport/date range, delete the rows directly:

```sql
DELETE FROM team_game_stats
WHERE sport = 'NBA' AND game_date BETWEEN '2024-01-01' AND '2024-01-31';
```

Extension table rows cascade automatically via the FK. Re-run the
backfill to re-populate.

### Data sources (all free)

| Sport | Source | Rate limit |
|-------|--------|-----------|
| NBA | `nba_api` (BoxScoreTraditionalV2 + AdvancedV2) | ~3 req/s |
| NHL | NHL Web API (`api-web.nhle.com`) | ~0.3 req/s |
| MLB | MLB Stats API (`statsapi.mlb.com`) | ~2 req/s |
| NFL | `nfl_data_py` parquet bulk download | bulk |
| EPL/Ligue1 | football-data.co.uk CSV + optional FBRef | 1 req/4 s |
| NCAAB/WNCAAB | ESPN scoreboard/summary API | ~2 req/s |
| Tennis | Jeff Sackmann Tennis Abstract GitHub CSVs | bulk |

---

## 9. Stats DAG Pool Setup

The `historical_stats_daily` DAG depends on the canonical pool definitions in
`config/airflow_pools.json`. Pools are seeded by the supported bootstrap flow in
`docs/AIRFLOW_SETUP.md`.

### Supported bootstrap path

```bash
docker compose run --rm airflow-preflight
docker compose run --rm airflow-bootstrap-admin
```

### Pool reference table

| Pool name | Slots | Source | Effective rate |
|-----------|-------|--------|----------------|
| `stats_nba_pool` | 3 | NBA Stats API | ~1 req/s |
| `stats_nhl_pool` | 1 | NHL API | ~0.5 req/s |
| `stats_mlb_pool` | 2 | MLB Stats API | ~1 req/s |
| `stats_nfl_pool` | 2 | nfl_data_py parquet | bulk |
| `stats_fbref_pool` | 1 | FBRef / Sports-Reference | 1 req/4 s |
| `stats_cbb_pool` | 2 | Sports-Reference CBB | 1 req/4 s |
| `stats_tennis_pool` | 1 | Tennis Abstract GitHub CSV | bulk |

### Verify pools

Use `config/airflow_pools.json` as the source of truth and confirm the active
pool set in **Admin** → **Pools** after bootstrap.

If the running pool set diverges from `config/airflow_pools.json`, re-run:

```bash
docker compose run --rm airflow-bootstrap-admin
```

---

## 10. Troubleshooting: Stats Pipeline

### Missing games in unified_games

The `historical_stats_daily` DAG skips any `game_id` absent from
`unified_games`. If coverage appears low, check whether the main betting
workflow has populated the schedule table:

```sql
SELECT sport, COUNT(*) AS games, MIN(game_date), MAX(game_date)
FROM unified_games
GROUP BY sport
ORDER BY sport;
```

If games are missing, trigger the relevant `{sport}_download_games` task in
`multi_sport_betting_workflow` first, then re-run the stats task.

### API rate-limit errors (HTTP 429)

The backfill script uses exponential back-off (base 2 s, max 3 retries).
The DAG tasks carry `retries=2, retry_exponential_backoff=True` with a
`max_retry_delay` of 30 minutes.

If persistent 429s occur, reduce concurrency by lowering the pool slot count:

1. Update `config/airflow_pools.json`.
2. Rebuild the image if needed.
3. Re-run `docker compose run --rm airflow-bootstrap-admin`.

### Failed reconciliation audit entry

If the `reconcile_placed_bets` task fails after writing some audit rows but
before committing the `placed_bets` UPDATE, the transaction is rolled back.
The audit table may contain partial rows. Identify them:

```sql
SELECT * FROM bet_reconciliation_audit
WHERE run_id = '<failed-run-uuid>'
ORDER BY reconciled_at;
```

Delete orphaned rows if needed, then re-trigger the task. Re-running is safe
because `diff_bet` will re-detect the same discrepancies.

### Stats task fails with "optional dependency not installed"

The DAG tasks gracefully degrade for missing optional packages
(`nba_api`, `nfl_data_py`). They log a WARNING and exit success.
Add the missing package to the image build inputs and redeploy. Do not install
packages into a live container:

```bash
docker compose build
docker compose run --rm airflow-preflight
docker compose run --rm airflow-bootstrap-admin
docker compose up -d airflow-worker
```

### DAG schedule note

`historical_stats_daily` runs at `0 8 * * *` (08:00 UTC) to ensure overnight
games from all time zones are final before ingestion. `catchup=False` prevents
automatic backfill runs from the scheduler — use `scripts/backfill_team_game_stats.py`
for historical data.

---

## 11. Contact and Escalation

> **Note:** Replace the placeholders below with real contact information before
> going to production.

| Escalation level | Contact | When to use |
|-----------------|---------|-------------|
| L1 — On-call engineer | `<on-call-engineer@example.com>` | Stats DAG failures, reconciliation errors |
| L2 — Data engineering lead | `<data-lead@example.com>` | Persistent data quality issues, schema changes |
| L3 — Platform owner | `<owner@example.com>` | Kalshi API changes, budget/billing, outages > 4 h |

### Kalshi API issues

Kalshi status page: `https://status.kalshi.com`

### Airflow UI

`http://localhost:8080` (default local installation)

### Database access

```bash
docker compose exec postgres psql -U airflow -d airflow
```
