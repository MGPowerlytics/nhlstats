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
```

Dashboard browser tests are opt-in:

```bash
RUN_DASHBOARD_E2E=1 pytest -q
```

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
