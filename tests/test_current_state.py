#!/usr/bin/env python3
"""
Check current system state for CI/CD pipeline.
"""

import sys
from pathlib import Path

print("Checking current system state...")
print("="*60)

# Check if we're in project root
project_root = Path(__file__).parent
print(f"Project root: {project_root}")

# Check for key files
key_files = [
    "requirements.txt",
    "docker-compose.yaml",
    "dags/multi_sport_betting_workflow.py",
    "plugins/elo/__init__.py",
    "plugins/db_manager.py"
]

for file_path in key_files:
    path = project_root / file_path
    if path.exists():
        print(f"✓ {file_path}")
    else:
        print(f"✗ {file_path} (missing)")

print("\nChecking test status...")
print("="*60)

# Try to run a simple test
try:
    import pytest
    print("✓ pytest available")

    # Check if we can import core modules
    sys.path.insert(0, str(project_root))

    modules_to_check = [
        "plugins.elo",
        "plugins.db_manager",
        "dags.multi_sport_betting_workflow"
    ]

    for module in modules_to_check:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError as e:
            print(f"✗ {module}: {e}")

except ImportError:
    print("✗ pytest not available")

print("\n" + "="*60)
print("State check complete")
