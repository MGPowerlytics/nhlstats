# Dashboard Integration Testing

This directory contains integration tests for the Streamlit dashboard using Playwright.

## Overview

Integration tests verify the dashboard's end-to-end functionality by:
1. Calculating expected values from the database
2. Launching the real dashboard in a browser
3. Verifying the displayed values match expectations

## Test Files

### `test_dashboard_integration.py`
**Playwright E2E Test** - Launches dashboard and verifies Financial Performance page

**What it tests:**
- Dashboard loads successfully
- Portfolio Value metric is displayed
- Value shown matches database calculation (cash + open positions)

**Prerequisites:**
```bash
# Install Playwright
pip install playwright pytest-playwright

# Install browser drivers
playwright install chromium
```

**Running the test:**
```bash
# From host (requires postgres port forwarding)
python tests/test_dashboard_integration.py

# OR run in Docker
docker exec -it nhlstats-airflow-worker-1 \
  python /opt/airflow/tests/test_dashboard_integration.py
```

**Requirements:**
- Dashboard must be running on `http://localhost:8501`
- Database must be accessible
- Playwright chromium browser installed

### `test_portfolio_value_final.py`
**Database Verification Test** - Confirms portfolio value calculation

**What it tests:**
- Cash balance retrieved from `portfolio_value_snapshots`
- Open positions value summed from `placed_bets`
- Portfolio value = cash + open positions
- Value matches user's reported Kalshi balance

**Running the test:**
```bash
# In Docker
docker exec -it nhlstats-airflow-dag-processor-1 \
  python /opt/airflow/tests/test_portfolio_value_final.py
```

**Expected output:**
```
Portfolio Value Calculation:
   Cash Balance:        $     73.35
   + Open Positions:    $      7.34  (4 open bets)
   ========================================
   Portfolio Value:     $     80.69

✅ Verification:
   User's Kalshi Balance:  $     80.69
   Dashboard Shows:        $     80.69
   Difference:             $      0.00

🎯 PERFECT MATCH!
```

### `test_cash_vs_portfolio_value.py`
**Diagnostic Test** - Explains cash balance vs portfolio value distinction

**What it tests:**
- Understanding of `balance_dollars` (cash only)
- Understanding of `portfolio_value_dollars` (should be total)
- Calculation of expected portfolio value
- Identification of data issues

**Use case:** Run this when portfolio value doesn't match expectations

## Key Concepts

### Portfolio Value vs Cash Balance

**Cash Balance** (`balance_dollars`):
- Uninvested cash in Kalshi account
- Example: $73.35

**Portfolio Value** (what user sees in Kalshi):
- Cash + market value of open positions
- Example: $73.35 + $7.34 = $80.69

**Dashboard Must Show:** Portfolio Value (the total)

### Why This Matters

Users compare dashboard to their Kalshi account balance. Kalshi shows **portfolio value** (total), not just cash. Our dashboard must match!

## Troubleshooting

### Test fails with "could not translate host name 'postgres'"
**Solution:** Run test from inside Docker container where postgres hostname is resolved

### Test fails with "Dashboard not running"
**Solution:** Start dashboard:
```bash
docker compose up dashboard -d
```
Verify: `curl http://localhost:8501`

### Dashboard shows different value than test expects
**Causes:**
1. **Race condition:** Bet settled between test calculation and dashboard render
2. **Stale snapshot:** Run `airflow dags trigger portfolio_hourly_snapshot`
3. **Database not synced:** Run bet sync DAG

### Playwright browser not installed
**Solution:**
```bash
playwright install chromium
```

## CI/CD Integration

These tests can be run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Dashboard Integration Tests
  run: |
    docker compose up -d
    sleep 10  # Wait for services
    docker exec nhlstats-airflow-worker-1 \
      python /opt/airflow/tests/test_portfolio_value_final.py
```

## Test Development

When adding new dashboard features:

1. **Add database test** - Verify calculation logic
2. **Add integration test** - Verify UI displays correctly
3. **Document expected behavior** - In test docstrings
4. **Add to CI/CD** - Automate testing

## References

- [Playwright Python Docs](https://playwright.dev/python/)
- [Streamlit Testing Guide](https://docs.streamlit.io/library/advanced-features/testing)
- Project CHANGELOG: See entries for dashboard fixes with TDD process
