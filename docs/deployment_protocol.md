# Deployment Protocol & Validation Checklist

This protocol reflects the remediated deployment surface only. It documents the
supported validation, bootstrap, and runtime topology contracts.

## 1. Pre-deployment validation

Run the required validation commands from the repo root:

```bash
pytest --collect-only -q
pytest -q
bash scripts/verify_stats_schema_migrations.sh
```

Dashboard browser coverage is opt-in:

```bash
RUN_DASHBOARD_E2E=1 pytest -q
```

Before deployment, confirm the runtime contract is still true:

- secrets are injected via environment variables and `/run/secrets` only
- `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`, and `ODDS_API_KEY` are the
  supported betting credentials
- no repo-root secret files or `/tmp` secret copies are required
- the image contains `/opt/airflow/migrations/stats_schema`
- persistence uses named volumes only

## 2. Supported deployment sequence

Build the image-baked runtime:

```bash
docker compose build
```

Start backing services:

```bash
docker compose up -d postgres redis
```

Run the supported one-shot bootstrap stages:

```bash
docker compose run --rm airflow-preflight
docker compose run --rm airflow-bootstrap-admin
```

Start the steady-state services:

```bash
docker compose up -d \
  airflow-apiserver \
  airflow-scheduler \
  airflow-dag-processor \
  airflow-worker \
  airflow-triggerer \
  dashboard
```

Verify the runtime:

```bash
docker compose run --rm airflow-verify
```

## 3. Runtime topology guardrails

The deployment is supported only when these guardrails remain intact:

- no `_PIP_ADDITIONAL_REQUIREMENTS`
- no runtime package installation in live containers
- no steady-state repo/code/config bind mounts
- no repo-root `./data` mount
- migrations are image-baked under `/opt/airflow/migrations`
- pool definitions come from `config/airflow_pools.json`
- schema readiness is enforced by `plugins.schema_migrations apply/verify`
  against `/opt/airflow/migrations/stats_schema`

## 4. Post-deployment verification

Confirm service health:

```bash
docker compose ps
docker compose exec airflow-scheduler airflow dags list
docker compose run --rm airflow-bootstrap-admin
```

Confirm the governed schema ledger:

```bash
bash scripts/verify_stats_schema_migrations.sh
```

Open the Airflow UI at `http://localhost:8080` and sign in with the configured
`_AIRFLOW_WWW_USER_*` bootstrap admin environment variables. Confirm **Admin** →
**Pools** matches `config/airflow_pools.json`.

## 5. Rollback

Rollback uses the same image-baked/bootstrap flow:

1. Restore the prior image or checkout the prior revision.
2. Rebuild the image: `docker compose build`
3. Start backing services: `docker compose up -d postgres redis`
4. Re-run:
   - `docker compose run --rm airflow-preflight`
   - `docker compose run --rm airflow-bootstrap-admin`
5. Start steady-state services again.
6. Run `docker compose run --rm airflow-verify`

Named volumes preserve database and Airflow state across the rollback unless you
explicitly remove them.

## 6. Unsupported deployment patterns

Do not use these as operator guidance:

- `airflow-init` as the bootstrap instruction
- manual `docker compose exec` bootstrap or pool-seeding flows
- live-container `pip install`
- repo-mounted secret/bootstrap workflows
- repo-root `kalshkey`, `odds_api_key`, or PEM guidance
- `/tmp` secret-copy patterns
