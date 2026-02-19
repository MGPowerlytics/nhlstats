#!/bin/bash
# Monitor the new DAG run

DAG_RUN_ID="manual__2026-02-05T22:17:18.413229+00:00"
echo "🔍 Monitoring new DAG run: $DAG_RUN_ID"
echo "====================================="

# Wait a bit for it to start
sleep 10

# Check status
echo "1. Checking DAG run status..."
docker compose exec airflow-scheduler airflow dags state multi_sport_betting_workflow "$DAG_RUN_ID" 2>&1 | grep -v "RemovedInAirflow4Warning" || echo "Could not get state"

# Monitor key tasks
echo ""
echo "2. Monitoring key Elo update tasks..."
for task in nba_update_elo nhl_update_elo tennis_update_elo; do
    echo ""
    echo "   Checking $task..."

    # Wait for task to start
    for i in {1..10}; do
        STATUS=$(docker compose exec airflow-scheduler airflow tasks state multi_sport_betting_workflow "$task" "$DAG_RUN_ID" 2>&1 | grep -v "RemovedInAirflow4Warning" | tail -1 || echo "unknown")

        if [ "$STATUS" != "unknown" ] && [ "$STATUS" != "None" ]; then
            echo "   Status: $STATUS"
            break
        fi

        if [ $i -eq 10 ]; then
            echo "   Task not started yet"
        else
            sleep 5
        fi
    done

    # Check logs if task is running or completed
    if [ "$STATUS" = "running" ] || [ "$STATUS" = "success" ] || [ "$STATUS" = "failed" ]; then
        echo "   Checking logs for errors..."
        LOG_FILE="logs/dag_id=multi_sport_betting_workflow/run_id=$DAG_RUN_ID/task_id=$task/attempt=1.log"
        if [ -f "$LOG_FILE" ]; then
            # Check for errors
            ERRORS=$(tail -50 "$LOG_FILE" 2>/dev/null | grep -i "error\|exception\|traceback\|failed" || echo "No errors found")
            if [ "$ERRORS" != "No errors found" ]; then
                echo "   ❌ ERRORS FOUND:"
                echo "$ERRORS" | head -5
            else
                echo "   ✅ No errors found"

                # Check for success indicators
                if tail -20 "$LOG_FILE" 2>/dev/null | grep -q "unified_games\|Rating Changes\|✓.*updated"; then
                    echo "   ✅ Task appears successful"
                fi
            fi
        else
            echo "   Log file not found yet"
        fi
    fi
done

echo ""
echo "3. Checking for 'openpyxl' dependency in Tennis task..."
TENNIS_LOG="logs/dag_id=multi_sport_betting_workflow/run_id=$DAG_RUN_ID/task_id=tennis_update_elo/attempt=1.log"
if [ -f "$TENNIS_LOG" ]; then
    if tail -50 "$TENNIS_LOG" 2>/dev/null | grep -q "openpyxl"; then
        echo "   ❌ Tennis task still missing openpyxl!"
        echo "   We added it to requirements.txt but need to rebuild Docker image"
    else
        echo "   ✅ No openpyxl errors (or task hasn't run yet)"
    fi
else
    echo "   Tennis logs not available yet"
fi

echo ""
echo "====================================="
echo "To view full logs:"
echo "  tail -f logs/dag_id=multi_sport_betting_workflow/run_id=$DAG_RUN_ID/task_id=nba_update_elo/attempt=1.log"
