#!/bin/bash
# Chains Stage 2 → Stage 3 of MLB sabermetrics backfill.
# Run inside the Airflow worker container.

set -euo pipefail

LOG="/opt/airflow/data/backfill_mlb_sabermetrics.log"
STAGE3_START_MARKER="/opt/airflow/data/.stage3_started"

echo "[chain2] Waiting for Stage 2 to complete..."
while ! grep -qE "Stage 2 complete" "$LOG" 2>/dev/null; do
    sleep 30
done

echo "[chain2] Stage 2 finished at $(date -Iseconds)"
echo "[chain2] Starting Stage 3 (matchup features)..."

python /opt/airflow/scripts/backfill_mlb_sabermetrics.py --matchup-only \
    --start-date 2021-03-01 \
    >> "$LOG" 2>&1

echo "[chain2] Stage 3 finished at $(date -Iseconds)"
touch "$STAGE3_START_MARKER"
echo "[chain2] Done. Log: $LOG"
