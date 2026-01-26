#!/usr/bin/env python3
"""
Verify Phase 1.4 Completion Status
"""

import sys
from pathlib import Path

print("Phase 1.4 Completion Verification")
print("=" * 50)

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Check for Phase 1.4 deliverables
deliverables = {
    "Documentation": [
        ("docs/deployment_protocol.md", "Deployment protocol document"),
        ("PHASE_1_4_COMPLETION_SUMMARY.md", "Completion summary"),
    ],
    "Scripts": [
        ("scripts/validate_deployment.py", "Deployment validation script"),
    ],
    "Test Infrastructure": [
        ("tests/smoke/", "Smoke test directory"),
        ("tests/integration/", "Integration test directory"),
    ],
}

all_passed = True

for category, files in deliverables.items():
    print(f"\n{category}:")
    print("-" * 30)

    for file_path, description in files:
        path = project_root / file_path
        if path.exists():
            print(f"  ✓ {description}")
        else:
            print(f"  ✗ {description} - MISSING")
            all_passed = False

# Check core functionality
print("\nCore Functionality Check:")
print("-" * 30)

try:
    # Check database manager
    import plugins.db_manager

    _ = plugins.db_manager
    print("  ✓ Database manager import")

    # Check Elo system
    from plugins.elo import BaseEloRating, NBAEloRating

    _ = BaseEloRating
    _ = NBAEloRating
    print("  ✓ Elo system import")

    # Check DAG
    from dags.multi_sport_betting_workflow import SPORTS_CONFIG

    _ = SPORTS_CONFIG
    print(f"  ✓ DAG configuration ({len(SPORTS_CONFIG)} sports)")

except ImportError as e:
    print(f"  ✗ Import error: {e}")
    all_passed = False

print("\n" + "=" * 50)
if all_passed:
    print("✅ Phase 1.4 verification PASSED")
    sys.exit(0)
else:
    print("❌ Phase 1.4 verification FAILED")
    print("\nMissing deliverables need to be created.")
    sys.exit(1)
