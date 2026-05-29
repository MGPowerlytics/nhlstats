#!/bin/bash
# Chains Stage 1 → Stage 2 of MLB sabermetrics backfill.
# Run inside the Airflow worker container.
#
# Waits for Stage 1 to finish (by polling the log), then immediately
# starts Stage 2 (rolling features).

set -euo pipefail

LOG="/opt/airflow/data/backfill_mlb_sabermetrics.log"
STAGE2_START_MARKER="/opt/airflow/data/.stage2_started"

echo "[chain] Waiting for Stage 1 to complete..."
while ! grep -qE "Stage 1 complete|Backfill complete" "$LOG" 2>/dev/null; do
    sleep 30
done

echo "[chain] Stage 1 finished at $(date -Iseconds)"
echo "[chain] Starting Stage 2 (rolling features)..."

python /opt/airflow/scripts/backfill_mlb_sabermetrics.py --rolling-only \
    --start-date 2021-03-01 \
    >> "$LOG" 2>&1

echo "[chain] Stage 2 finished at $(date -Iseconds)"
touch "$STAGE2_START_MARKER"
echo "[chain] Done. Log: $LOG"
