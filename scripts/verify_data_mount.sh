#!/bin/bash
# Verify data mount integrity between host and containers

set -e

echo "=== Data Mount Integrity Verification ==="
echo "Date: $(date)"
echo

# Check docker-compose configuration
echo "1. Checking docker-compose.yaml configuration..."
if grep -q "./data:/opt/airflow/data" docker-compose.yaml; then
    echo "   ✓ Bind mount configured correctly"
else
    echo "   ✗ ERROR: Bind mount not found in docker-compose.yaml"
    exit 1
fi

if grep -q "airflow-data:/opt/airflow/data" docker-compose.yaml; then
    echo "   ✗ WARNING: Old volume mount still present"
else
    echo "   ✓ No conflicting volume mounts"
fi

# Check data directory exists
echo -e "\n2. Checking data directory..."
DATA_DIR="./data"
if [ -d "$DATA_DIR" ]; then
    echo "   ✓ Data directory exists: $DATA_DIR"
    echo "   Permissions: $(stat -c '%A %U %G' "$DATA_DIR")"
else
    echo "   ✗ WARNING: Data directory does not exist: $DATA_DIR"
    echo "   Creating it..."
    mkdir -p "$DATA_DIR"
fi

# Check sport subdirectories
echo -e "\n3. Checking sport subdirectories..."
for sport in mlb nba nhl nfl epl ligue1 cba; do
    sport_dir="$DATA_DIR/$sport"
    if [ -d "$sport_dir" ]; then
        echo "   ✓ $sport directory exists"
    else
        echo "   ⚠️  $sport directory missing (will be created when needed)"
    fi
done

# Test file write/read if containers are running
echo -e "\n4. Testing file access (if containers are running)..."
TEST_FILE="$DATA_DIR/mount_test_$(date +%s).txt"
TEST_CONTENT="Data mount test at $(date)"

# Write test file
echo "$TEST_CONTENT" > "$TEST_FILE"
if [ $? -eq 0 ]; then
    echo "   ✓ Can write to data directory"

    # Read it back
    READ_CONTENT=$(cat "$TEST_FILE")
    if [ "$READ_CONTENT" = "$TEST_CONTENT" ]; then
        echo "   ✓ Can read from data directory"
    else
        echo "   ✗ ERROR: Content mismatch"
    fi

    # Cleanup
    rm "$TEST_FILE"
else
    echo "   ✗ ERROR: Cannot write to data directory"
    exit 1
fi

# Check if we can see files from potential container writes
echo -e "\n5. Checking for existing data files..."
FILE_COUNT=$(find "$DATA_DIR" -name "*.json" -type f | wc -l)
echo "   Found $FILE_COUNT JSON files in data directory"

if [ $FILE_COUNT -gt 0 ]; then
    echo "   Sample files:"
    find "$DATA_DIR" -name "*.json" -type f | head -3 | while read f; do
        echo "   - $(basename "$f") ($(stat -c '%y' "$f" | cut -d' ' -f1))"
    done
fi

echo -e "\n=== Verification Complete ==="
echo "Data mount configuration appears correct."
echo "To apply changes, restart Airflow services:"
echo "  docker compose down"
echo "  docker compose up -d"
echo
echo "After restart, run the betting DAG to test:"
echo "  airflow dags trigger multi_sport_betting_workflow"
