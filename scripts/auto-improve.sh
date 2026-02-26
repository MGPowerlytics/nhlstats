#!/usr/bin/env bash
# auto-improve.sh — Run Henchman to make one codebase improvement, then commit & redeploy.
set -euo pipefail

# Ensure conda is on PATH (required for cron where PATH is minimal)
export PATH="/home/matthew/anaconda3/bin:/home/matthew/anaconda3/condabin:$PATH"

# Export API keys not available in cron environment
export DEEPSEEK_API_KEY="sk-999d210dbd284fe8be163d625166ea64"

# Activate the base conda environment (henchman lives here)
set +u
eval "$(conda shell.bash hook)"
conda activate base
set -u

WORKDIR="/mnt/data2/nhlstats"
LOGFILE="$WORKDIR/.agent_tasks/auto-improve/last-run.log"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cd "$WORKDIR"

# Ensure log directory exists
mkdir -p "$(dirname "$LOGFILE")"

echo "[$TIMESTAMP] Starting auto-improve run..." | tee "$LOGFILE"

PROMPT='You are running in an automated improvement cycle on the Multi-Sport Betting System codebase
located at /mnt/data2/nhlstats.

## Primary Goal: Increase Profitability

Every improvement you make should ultimately serve the goal of increasing the profitability
of this sports betting system. Think about what changes would lead to better predictions,
smarter bet selection, improved risk management, or reduced losses.

## Your Task

1. Pick ONE small, valuable improvement to make to the codebase. Prioritize changes that
   increase profitability, ordered by expected impact:

   **TOP PRIORITY:**
    - ANY FAILED AIRFLOW TASKS. FIX THESE FIRST.
    - ENSURE YOU MARK FIXED TASKS AS SUCCESS IN AIRFLOW SO WE DONT FIX THE SAME ISSUE AGAIN.

   **HIGH PRIORITY:**
    - Fix any bugs that could lead to incorrect predictions or lost bets.
    - Random audits of airflow tasks to identify and fix any issues.
    - Random database audits.
    - New ways of looking at our data to increase profitability.
    - Refactor any code that is particularly complex or error-prone.
    - Updating/removing stale code/documentation that could cause confusion or mistakes.

   **MEDIUM PRIORITY:**
    - Add new unit tests for critical code paths that currently lack coverage.
    - Improve code readability and maintainability in areas that are frequently changed.




## Important Constraints

- Only make ONE improvement per run.
- Keep changes minimal and focused.
- Ensure all unit tests pass before finishing.
- Do NOT modify this prompt or the auto-improve script itself.
- Do NOT create random CSV or JSON files — use the database for data storage.
- Follow Google docstring style, use type hints, run black on new code.
- Update CHANGELOG.md with your change.'

# Run Henchman in headless mode with auto-approve
echo "Running Henchman..." | tee -a "$LOGFILE"
henchman chat --yes -p "$PROMPT" 2>&1 | tee -a "$LOGFILE"

HENCHMAN_EXIT=${PIPESTATUS[0]}

if [ "$HENCHMAN_EXIT" -ne 0 ]; then
  echo "[$TIMESTAMP] Henchman exited with code $HENCHMAN_EXIT" | tee -a "$LOGFILE"
  exit "$HENCHMAN_EXIT"
fi

# Stage all changes and commit
echo "Committing changes..." | tee -a "$LOGFILE"
git add -A

SUMMARY=""
if [ -f "$WORKDIR/.agent_tasks/auto-improve/last-improvement.md" ]; then
  SUMMARY=$(head -5 "$WORKDIR/.agent_tasks/auto-improve/last-improvement.md" | tail -4)
fi

COMMIT_MSG="chore(auto-improve): automated profitability improvement

${SUMMARY}

Automated by scripts/auto-improve.sh at $TIMESTAMP"

git commit -m "$COMMIT_MSG" | tee -a "$LOGFILE"

# Redeploy Docker containers to pick up code changes
echo "[$TIMESTAMP] Redeploying Docker containers..." | tee -a "$LOGFILE"
cd "$WORKDIR"
docker compose down 2>&1 | tee -a "$LOGFILE"
docker compose up -d 2>&1 | tee -a "$LOGFILE"

# Wait for services to come up
echo "Waiting for services to stabilize..." | tee -a "$LOGFILE"
sleep 15

# Verify containers are healthy
docker compose ps 2>&1 | tee -a "$LOGFILE"

echo "[$TIMESTAMP] Auto-improve complete. Containers redeployed." | tee -a "$LOGFILE"
