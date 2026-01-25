#!/bin/bash

# Simple functional test script that works with current environment
# This is a fallback if the main script has issues

set -e

echo "=== Simple Functional Tests ==="
echo "Timestamp: $(date)"
echo ""

# Test 1: Check Python environment
echo "1. Testing Python environment..."
python --version
echo "✓ Python available"

# Test 2: Check project structure
echo ""
echo "2. Testing project structure..."
if [ -d "dags" ] && [ -d "plugins" ] && [ -d "dashboard" ]; then
    echo "✓ Project structure valid"
else
    echo "✗ Missing directories"
    exit 1
fi

# Test 3: Check DAG files exist
echo ""
echo "3. Testing DAG files..."
DAG_FILES="$(ls dags/*.py 2>/dev/null | wc -l)"
if [ "$DAG_FILES" -ge 3 ]; then
    echo "✓ Found $DAG_FILES DAG files"
else
    echo "✗ Insufficient DAG files"
    exit 1
fi

# Test 4: Check plugins
echo ""
echo "4. Testing plugins..."
if [ -f "plugins/db_manager.py" ] && [ -f "plugins/elo/__init__.py" ]; then
    echo "✓ Core plugins exist"
else
    echo "✗ Missing core plugins"
    exit 1
fi

# Test 5: Simple Python import test
echo ""
echo "5. Testing basic imports..."
python -c "
import sys
sys.path.insert(0, 'plugins')
try:
    from db_manager import DBManager
    print('✓ DBManager imports')
except ImportError as e:
    print(f'✗ DBManager import failed: {e}')
    sys.exit(1)

try:
    from plugins.elo import NBAEloRating
    print('✓ NBAEloRating imports')
except ImportError as e:
    print(f'✗ NBAEloRating import failed: {e}')
    sys.exit(1)
"

echo ""
echo "=== All basic tests passed ==="
echo "System is minimally functional"
exit 0
