# Multi-Sport Betting System

Production betting and stats workflows built around Airflow, PostgreSQL, and a
governed migration/bootstrap path.

## Getting Started

### Runtime contract

- Secrets are supported via environment variables and `/run/secrets` only.
- Supported betting credentials:
  - `KALSHI_API_KEY_ID`
  - `KALSHI_PRIVATE_KEY_PATH=/run/secrets/kalshi_private_key.pem`
  - `ODDS_API_KEY`
- The Airflow runtime is image-baked:
  - no `_PIP_ADDITIONAL_REQUIREMENTS`
  - no runtime `pip install`
  - no steady-state repo/code/config bind mounts
  - named Docker volumes provide persistence

### Build and bootstrap

```bash
docker compose build
docker compose up -d postgres redis
docker compose run --rm airflow-preflight
docker compose run --rm airflow-bootstrap-admin
docker compose up -d \
  airflow-apiserver \
  airflow-scheduler \
  airflow-dag-processor \
  airflow-worker \
  airflow-triggerer \
  dashboard
docker compose run --rm airflow-verify
```

Use the configured `_AIRFLOW_WWW_USER_*` environment variables to sign in to
the Airflow UI at `http://localhost:8080`.

## Validation

Supported validation commands:

```bash
pytest --collect-only -q
pytest -q
bash scripts/validate_dashboard_gate.sh
```

Dashboard browser tests are opt-in:

```bash
RUN_DASHBOARD_E2E=1 pytest -q
```

Use `bash scripts/validate_dashboard_gate.sh` for the required dashboard gate:
it installs dashboard and Playwright dependencies, provisions a local test
PostgreSQL database when needed, applies governed migrations, seeds deterministic
fixtures, runs provider checks in non-skipped live-PostgreSQL mode, healthchecks
Streamlit, and runs seeded Playwright tests with `RUN_DASHBOARD_E2E=1`.
The dashboard's stable data boundary is the governed `dashboard_*_v1`
PostgreSQL view layer, with canonical dashboard schemas in
`tests/contracts/schemas`; see
[`docs/DASHBOARD_POSTGRES_MIGRATION.md`](docs/DASHBOARD_POSTGRES_MIGRATION.md)
for recovery, empty-state, healthcheck, and contract-evolution guidance.

Schema validation commands:

```bash
bash scripts/apply_stats_schema_migrations.sh
bash scripts/verify_stats_schema_migrations.sh
```

## Key Documentation

- [Airflow Setup](docs/AIRFLOW_SETUP.md)
- [Operations Runbook](docs/OPERATIONS_RUNBOOK.md)
- [Deployment Protocol](docs/deployment_protocol.md)
- [System Overview](docs/SYSTEM_OVERVIEW.md)
- [Dashboard PostgreSQL Recovery](docs/DASHBOARD_POSTGRES_MIGRATION.md)
