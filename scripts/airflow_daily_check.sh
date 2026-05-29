#!/usr/bin/env bash
# Daily Airflow failure check wrapper.
# Runs the Python check inside the airflow container (where psycopg2 lives),
# then sends a Discord DM from the host if any failures are found.
set -euo pipefail

PROJECT_DIR="/mnt/data2/nhlstats"
SEND_DM="$HOME/.claude/skills/discord-message/bin/send-dm"

cd "$PROJECT_DIR"

# Run the check inside the airflow container, capturing JSON output
OUTPUT=$(docker compose run --rm --no-deps airflow-scheduler \
  python3 /opt/airflow/scripts/airflow_daily_check.py 2>/dev/null || true)

if [ -z "$OUTPUT" ]; then
  echo "[airflow-daily-check] ERROR: No output from check script (container may have failed)."
  echo "Attempting to send error notification..."
  echo "⚠️ Airflow daily check failed — the check script produced no output (container error?)." | "$SEND_DM" 2>/dev/null || true
  exit 2
fi

STATUS=$(echo "$OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "error")

if [ "$STATUS" = "pass" ]; then
  echo "[airflow-daily-check] All clear — no failed DAG runs found."
  exit 0
fi

if [ "$STATUS" = "error" ]; then
  echo "[airflow-daily-check] ERROR: Could not parse check output."
  echo "$OUTPUT"
  exit 2
fi

# Format a friendly Discord message from the JSON report
DISCORD_MSG=$(python3 -c "
import sys, json
r = json.load(sys.stdin)
lines = [
    '⚠️ **Airflow Failure Report**',
    r['message'],
    ''
]
for f in r['failures']:
    start = f.get('start_date', 'N/A')
    logical = f.get('logical_date', 'N/A')
    lines.append(f'**{f[\"dag_id\"]}** — run \`{f[\"run_id\"]}\`')
    lines.append(f'  • Type: {f[\"run_type\"]}')
    lines.append(f'  • Started: {start}')
    lines.append(f'  • Logical date: {logical}')
    for t in f.get('failed_tasks', []):
        lines.append(f'  • Failed task: \`{t[\"task_id\"]}\` ({t[\"state\"]})')
    lines.append('')
print('\n'.join(lines))
" <<< "$OUTPUT")

echo "$DISCORD_MSG" | "$SEND_DM"
echo "[airflow-daily-check] Discord notification sent."
exit 1
