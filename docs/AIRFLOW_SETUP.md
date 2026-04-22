# Airflow Setup Guide

This runbook documents the supported Airflow bootstrap flow after the remediation
cutover. It is limited to the implemented runtime, schema, and validation
contracts.

## 1. Runtime inputs

### Supported secret inputs

- `KALSHI_API_KEY_ID` via environment variable
- `KALSHI_PRIVATE_KEY_PATH=/run/secrets/kalshi_private_key.pem`
- `ODDS_API_KEY` via environment variable
- Airflow bootstrap admin credentials via:
  - `_AIRFLOW_WWW_USER_USERNAME`
  - `_AIRFLOW_WWW_USER_PASSWORD`
  - `_AIRFLOW_WWW_USER_FIRSTNAME`
  - `_AIRFLOW_WWW_USER_LASTNAME`
  - `_AIRFLOW_WWW_USER_EMAIL`

### Unsupported patterns

Do not use:

- repo-root `kalshkey`
- repo-root `odds_api_key`
- repo-root PEM files or PEM mount guidance
- `/tmp` secret-copy workflows
- manual secret creation inside running containers

## 2. Runtime topology

The supported Airflow runtime is image-baked and named-volume-backed:

- no `_PIP_ADDITIONAL_REQUIREMENTS`
- no runtime `pip install`
- no steady-state repo/code/config bind mounts
- no repo-root `./data` mount
- migrations are baked into the image at `/opt/airflow/migrations`
- persistent state lives in named Docker volumes

## 3. Canonical bootstrap sources

- Pool definitions: `config/airflow_pools.json`
- Governed migrations: `/opt/airflow/migrations/stats_schema`
- Bootstrap entrypoint: `scripts/airflow_bootstrap.py`

`airflow-bootstrap-admin` imports the checked-in pool config and applies the
governed schema migration chain idempotently. Manual `docker compose exec`
pool/bootstrap steps are not part of the supported setup flow.

## 4. Supported bootstrap flow

Start backing services first:

```bash
docker compose up -d postgres redis
```

Run the first two one-shot bootstrap stages:

```bash
docker compose run --rm airflow-preflight
docker compose run --rm airflow-bootstrap-admin
```

After those succeed, start the steady-state services:

```bash
docker compose up -d \
  airflow-apiserver \
  airflow-scheduler \
  airflow-dag-processor \
  airflow-worker \
  airflow-triggerer \
  dashboard
```

Then run the final verification stage:

```bash
docker compose run --rm airflow-verify
```

`airflow-verify` is part of the supported bootstrap flow, but it requires the
API server and scheduler to be healthy first.

## 5. Schema validation

Production schema evolution is owned by the governed migration chain plus the
`schema_migrations` ledger. Use the supported wrappers when operating the schema
outside the one-shot bootstrap flow:

```bash
bash scripts/apply_stats_schema_migrations.sh
bash scripts/verify_stats_schema_migrations.sh
```

Ledger-based verification is authoritative:

```sql
SELECT version, name, checksum, applied_at
FROM schema_migrations
ORDER BY version;
```

`DatabaseSchemaManager` and `bet_tracker` helpers remain compatibility paths for
non-PostgreSQL and local-only scenarios; they do not own production schema
evolution.

## 6. Pool validation

`config/airflow_pools.json` is the canonical pool source. To confirm the running
environment matches the checked-in contract:

```bash
docker compose run --rm airflow-bootstrap-admin
```

The bootstrap stage is idempotent and re-imports the canonical pool
definitions. After it completes, use **Admin** → **Pools** in the Airflow UI to
confirm the active pool set matches `config/airflow_pools.json`.

## 7. UI access

Open `http://localhost:8080` and sign in with the configured bootstrap admin
environment variables. Do not rely on hard-coded default credentials in
operator workflows.

## 8. Supported validation commands

Use the implemented local and CI validation commands:

```bash
pytest --collect-only -q
pytest -q
```

Dashboard/Playwright browser tests are opt-in only:

```bash
RUN_DASHBOARD_E2E=1 pytest -q
```

## 9. Troubleshooting

| Symptom | Likely cause | Supported response |
|---|---|---|
| `airflow-preflight` fails secret validation | `KALSHI_PRIVATE_KEY_PATH` does not resolve to `/run/secrets/kalshi_private_key.pem` or the file is missing | Fix the runtime secret injection and re-run `docker compose run --rm airflow-preflight` |
| `airflow-bootstrap-admin` fails schema verification | Migration chain or ledger state is incomplete | Run `bash scripts/apply_stats_schema_migrations.sh`, then `bash scripts/verify_stats_schema_migrations.sh` |
| Required pools are missing or wrong | Runtime diverged from `config/airflow_pools.json` | Re-run `docker compose run --rm airflow-bootstrap-admin` |
| Airflow UI login fails | Bootstrap admin env vars do not match the intended user | Update `_AIRFLOW_WWW_USER_*` env vars and re-run `docker compose run --rm airflow-bootstrap-admin` |
| Optional dependency missing in a worker image | Image does not contain the required package | Rebuild the image and redeploy; live-container `pip install` is unsupported |
