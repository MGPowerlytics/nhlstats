#!/bin/bash
# Check Elo results after DAG run completes

echo "📊 Checking Elo results after DAG run..."
echo "========================================"

# Wait for DAG to complete
echo "1. Waiting for DAG to complete..."
MAX_WAIT=300
WAIT_INTERVAL=30
elapsed=0
completed=false

while [ $elapsed -lt $MAX_WAIT ]; do
    STATUS=$(docker compose exec airflow-scheduler airflow dags state multi_sport_betting_workflow "manual__2026-02-05T22:03:03.450872+00:00" 2>&1 | grep -v "RemovedInAirflow4Warning" | tail -1)

    if [ "$STATUS" = "success" ]; then
        echo "✅ DAG completed successfully!"
        completed=true
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "❌ DAG failed!"
        break
    else
        echo "   Status after $elapsed seconds: $STATUS"
    fi

    sleep $WAIT_INTERVAL
    elapsed=$((elapsed + WAIT_INTERVAL))
done

if [ "$completed" = false ]; then
    echo "⚠️  DAG still running after $MAX_WAIT seconds"
    echo "   Current status: $STATUS"
fi

echo ""
echo "2. Checking updated Elo rating files..."
for sport in nhl nba mlb nfl; do
    FILE="data/${sport}_current_elo_ratings.csv"
    if [ -f "$FILE" ]; then
        # Check file size and content
        LINE_COUNT=$(wc -l < "$FILE")
        TEAM_COUNT=$((LINE_COUNT - 1))  # Subtract header

        echo "   $sport: $TEAM_COUNT teams in $FILE"

        # Check rating range
        if [ $TEAM_COUNT -gt 0 ]; then
            python3 -c "
import pandas as pd
try:
    df = pd.read_csv('$FILE')
    if len(df) > 0:
        min_rating = df['rating'].min()
        max_rating = df['rating'].max()
        rating_range = max_rating - min_rating
        avg_rating = df['rating'].mean()
        print(f'      Rating range: {min_rating:.1f} - {max_rating:.1f} ({rating_range:.1f})')
        print(f'      Average: {avg_rating:.1f}')

        # Check if range is reasonable
        expected_ranges = {'nhl': 200, 'nba': 300, 'mlb': 250, 'nfl': 200}
        if '$sport' in expected_ranges:
            expected = expected_ranges['$sport']
            if rating_range > expected * 0.5:
                print(f'      ✅ Good range for {sport.upper()}')
            else:
                print(f'      ⚠️  Narrow range for {sport.upper()} (expected ~{expected})')
except Exception as e:
    print(f'      Error reading file: {e}')
" 2>/dev/null || echo "      Could not analyze file"
    else
        echo "   ⚠️  $FILE not found"
    fi
    echo ""
done

echo "3. Checking for evidence of unified_games usage..."
echo "   Looking in logs for 'unified_games' references..."

# Check worker logs
UNIFIED_COUNT=$(docker compose logs airflow-worker --tail=500 2>&1 | grep -c "unified_games" || echo "0")
if [ "$UNIFIED_COUNT" -gt 0 ]; then
    echo "   ✅ Found $UNIFIED_COUNT references to 'unified_games' in logs"
    echo "   Sample:"
    docker compose logs airflow-worker --tail=500 2>&1 | grep -i "unified_games" | head -3
else
    echo "   ⚠️  No 'unified_games' references found in recent logs"
fi

echo ""
echo "4. Summary of deployment:"
echo "   - DAG status: $STATUS"
echo "   - NHL Elo file: $(ls -la data/nhl_current_elo_ratings.csv 2>/dev/null | awk '{print $5}' || echo 'not found') bytes"
echo "   - NBA Elo file: $(ls -la data/nba_current_elo_ratings.csv 2>/dev/null | awk '{print $5}' || echo 'not found') bytes"
echo "   - 'unified_games' references: $UNIFIED_COUNT"

echo ""
echo "========================================"
echo "To verify the fix worked:"
echo "1. Check that rating ranges are wide (NHL: ~250, NBA: ~300)"
echo "2. Check that 'unified_games' appears in task logs"
echo "3. Check Airflow UI for task logs showing 'Rating Changes'"
echo ""
echo "If issues persist, check:"
echo "  docker compose logs airflow-worker | grep -A20 'nhl_update_elo\|nba_update_elo'"
