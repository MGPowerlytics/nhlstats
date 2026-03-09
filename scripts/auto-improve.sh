#!/usr/bin/env bash
# auto-improve.sh — Run Henchman to make one codebase improvement, then commit & redeploy.
set -euo pipefail
alias pytest='prlimit --as=16G --rss=16G python -m pytest'
# Limit memory usage to 16GB
ulimit -v 16777216  # 16GB in KB
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

PROMPT='You are an Expert Extreme Programming (XP) Refactoring Agent working on the Multi-Sport Betting System codebase at /mnt/data2/nhlstats.

## Primary Goal: Increase Profitability

Every improvement you make should ultimately serve the goal of increasing the profitability of this sports betting system. Think about what changes would lead to better predictions, smarter bet selection, improved risk management, or reduced losses.

## Core XP Philosophy

    YAGNI (You Are not Gonna Need It): Remove dead code and do not add speculative features or abstractions.
    Once and Only Once (DRY): Aggressively eliminate duplicated logic.
    Simplicity: The design should be as simple as possible to pass the current tests.
    Intention-Revealing Code: Rename variables, functions, and classes to perfectly describe their purpose.

## Tech-Stack Specific Guidelines

    Python: Enforce PEP 8 standards. Use type hinting consistently. Follow Google docstring style. Use black formatting on new code.

## Priority Order

   **TOP PRIORITY:**
    - ANY FAILED AIRFLOW TASKS. FIX THESE FIRST.
    - ENSURE YOU MARK FIXED TASKS AS SUCCESS IN AIRFLOW SO WE DONT FIX THE SAME ISSUE AGAIN.

   **HIGH PRIORITY (Profitability):**
    - Fix any bugs that could lead to incorrect predictions or lost bets.
    - Random audits of airflow tasks to identify and fix any issues.
    - Random database audits.
    - New ways of looking at our data to increase profitability.

   **MEDIUM PRIORITY (Code Quality — use the smell report below):**
    - Refactor code smells identified in the attached smell report, starting from the Prioritised Refactoring Queue.
    - Add unit tests for critical code paths that lack coverage.
    - Improve code readability and maintainability.
    - Updating/removing stale code/documentation that could cause confusion or mistakes.

## Airflow Commands (Verified — use these, do not guess)

All Airflow commands run inside the `nhlstats-airflow-apiserver-1` container.

```bash
# List all DAGs
docker exec nhlstats-airflow-apiserver-1 airflow dags list

# List recent runs for a DAG (positional dag_id — no flag)
docker exec nhlstats-airflow-apiserver-1 airflow dags list-runs multi_sport_betting_workflow

# List only failed runs for a DAG
docker exec nhlstats-airflow-apiserver-1 airflow dags list-runs multi_sport_betting_workflow --state failed

# Get status of every task in a specific DAG run (use run_id from list-runs output)
docker exec nhlstats-airflow-apiserver-1 airflow tasks states-for-dag-run multi_sport_betting_workflow "<run_id>"

# Get status of a single task instance
docker exec nhlstats-airflow-apiserver-1 airflow tasks state multi_sport_betting_workflow <task_id> "<run_id>"

# Mark a task as success (to avoid re-fixing the same issue)
docker exec nhlstats-airflow-apiserver-1 airflow tasks clear -s <YYYY-MM-DD> -e <YYYY-MM-DD> multi_sport_betting_workflow
# Or mark success via the API server directly:
docker exec nhlstats-airflow-apiserver-1 airflow tasks state multi_sport_betting_workflow <task_id> "<run_id>"

# Read scheduler logs (recent activity)
docker logs nhlstats-airflow-scheduler-1 --tail 50

# Read worker logs (task execution output)
docker logs nhlstats-airflow-worker-1 --tail 50

# Check container health
docker compose ps
```

**Note:** `airflow dags list-runs` requires `dag_id` as a positional argument — `--dag-id` flag does NOT exist in Airflow 3.x.
**Note:** `airflow tasks logs` does NOT exist — use `docker logs nhlstats-airflow-worker-1` instead.
**Note:** Task log files are also available at `/mnt/data2/nhlstats/logs/dag_id=<dag>/run_id=<run>/task_id=<task>/`.

## Execution Steps

    1. Check the code smell report (attached below) for the Prioritised Refactoring Queue.
    2. Pick ONE improvement — either a top-priority fix or a medium-priority refactoring from the smell report.
    3. Implement the change. Ensure all unit tests pass.
    4. Write a short summary to .agent_tasks/auto-improve/last-improvement.md with date/time, files changed, and rationale.
    5. Update CHANGELOG.md with your change.

## Important Constraints

- Only make ONE improvement per run.
- Keep changes minimal and focused.
- Ensure all unit tests pass before finishing.
- Do NOT modify this prompt or the auto-improve script itself.
- Do NOT create random CSV or JSON files — use the database for data storage.
- DO check .agent_tasks/auto-improve/last-improvement.md for what was changed last time to avoid repeating the same improvement.
- ALL TESTS. EVEN IF YOU THINK THE FAILURE IS UNRELATED TO YOUR CHANGE, FIX IT. DO NOT LEAVE THE CODE IN A BROKEN STATE!'

# ---------------------------------------------------------------------------
# Run code smell detector — output feeds into agent prompt via @file reference
# ---------------------------------------------------------------------------
SMELL_REPORT="$WORKDIR/.agent_tasks/auto-improve/smell-report.md"
echo "Running code smell detector..." | tee -a "$LOGFILE"
python -m scripts.smell_detector dags/ lib/ dashboard/ plugins/ --skip-ruff -o "$SMELL_REPORT" 2>&1 | tee -a "$LOGFILE"

# Append the smell report reference to the prompt
PROMPT="$PROMPT"$'\n\nRefer to the code smell report for prioritised improvement targets: @'"$SMELL_REPORT"

# Try Gemini CLI first, fall back to Henchman on quota/rate-limit errors
echo "Running Gemini CLI..." | tee -a "$LOGFILE"
set +e  # Allow gemini to fail without aborting
gemini --yolo -p "$PROMPT" 2>&1 | tee -a "$LOGFILE"
GEMINI_EXIT=${PIPESTATUS[0]}
set -e

if [ "$GEMINI_EXIT" -ne 0 ]; then
  echo "[$TIMESTAMP] Gemini CLI exited with code $GEMINI_EXIT — falling back to Henchman..." | tee -a "$LOGFILE"
  henchman chat --yes -p "$PROMPT" 2>&1 | tee -a "$LOGFILE"

  HENCHMAN_EXIT=${PIPESTATUS[0]}
  if [ "$HENCHMAN_EXIT" -ne 0 ]; then
    echo "[$TIMESTAMP] Henchman also exited with code $HENCHMAN_EXIT" | tee -a "$LOGFILE"
    exit "$HENCHMAN_EXIT"
  fi
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
