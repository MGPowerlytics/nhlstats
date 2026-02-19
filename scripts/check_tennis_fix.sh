#!/bin/bash
# Check if Tennis fix worked

DAG_RUN_ID="manual__2026-02-05T23:15:29.374070+00:00"
echo "🎾 Checking Tennis task after openpyxl install..."
echo "================================================"

# Wait for Tennis task to run
echo "1. Waiting for Tennis task to start..."
sleep 30

# Check Tennis task status
echo "2. Checking Tennis task status..."
STATUS=$(docker compose exec airflow-scheduler airflow tasks state multi_sport_betting_workflow tennis_update_elo "$DAG_RUN_ID" 2>&1 | grep -v "RemovedInAirflow4Warning" | tail -1 || echo "unknown")
echo "   Status: $STATUS"

# Check logs
echo ""
echo "3. Checking Tennis task logs..."
LOG_FILE="logs/dag_id=multi_sport_betting_workflow/run_id=$DAG_RUN_ID/task_id=tennis_update_elo/attempt=1.log"

if [ -f "$LOG_FILE" ]; then
    echo "   Log file exists, checking for errors..."

    # Check for openpyxl errors
    if tail -100 "$LOG_FILE" 2>/dev/null | grep -q "openpyxl"; then
        echo "   ❌ STILL HAS openpyxl ERRORS!"
        echo "   Sample:"
        tail -100 "$LOG_FILE" 2>/dev/null | grep -i "openpyxl" | head -3
    else
        echo "   ✅ No openpyxl errors found"
    fi

    # Check for other errors
    ERRORS=$(tail -100 "$LOG_FILE" 2>/dev/null | grep -i "error\|exception\|traceback\|failed" | grep -v "openpyxl" || echo "No other errors")
    if [ "$ERRORS" != "No other errors" ]; then
        echo "   ⚠️  Other errors found:"
        echo "$ERRORS" | head -3
    else
        echo "   ✅ No other errors found"
    fi

    # Check for success
    if tail -20 "$LOG_FILE" 2>/dev/null | grep -q "✓ TENNIS Elo ratings updated"; then
        echo "   ✅ Task completed successfully"
        # Get player count
        PLAYERS=$(tail -20 "$LOG_FILE" 2>/dev/null | grep -o "Elo ratings updated: [0-9]* players" | grep -o "[0-9]*" || echo "unknown")
        echo "   Players updated: $PLAYERS"
    fi

    # Show last 10 lines
    echo ""
    echo "4. Last 10 lines of log:"
    tail -10 "$LOG_FILE" 2>/dev/null

else
    echo "   Log file not found yet"
    echo "   Checking if task has run..."
    docker compose logs airflow-worker --tail=50 2>&1 | grep -i "tennis_update_elo" | tail -5
fi

echo ""
echo "================================================"
echo "To view full logs:"
echo "  tail -f $LOG_FILE"
