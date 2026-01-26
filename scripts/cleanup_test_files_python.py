#!/usr/bin/env python3
"""
Clean up unused variables and imports in test files.
This is safer than using sed as it preserves file structure.
"""

import re


def clean_file(filepath, patterns):
    """Remove lines matching patterns from a file."""
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()

        original_len = len(lines)
        cleaned_lines = []

        for line in lines:
            should_keep = True
            for pattern in patterns:
                if re.search(pattern, line):
                    should_keep = False
                    break
            if should_keep:
                cleaned_lines.append(line)

        if len(cleaned_lines) < original_len:
            with open(filepath, "w") as f:
                f.writelines(cleaned_lines)
            print(
                f"Cleaned {filepath}: removed {original_len - len(cleaned_lines)} lines"
            )
            return True
        else:
            print(f"No changes needed for {filepath}")
            return False

    except Exception as e:
        print(f"Error cleaning {filepath}: {e}")
        return False


# Define cleanup patterns for each file
cleanup_tasks = [
    {"file": "tests/test_analyze_positions.py", "patterns": [r"mock_mkdirs*="]},
    {
        "file": "tests/test_bet_metrics_pipeline.py",
        "patterns": [r"setup_recommendationss*=", r"mock_db_manager_to_test_engines*="],
    },
    {"file": "tests/test_coverage_boost4.py", "patterns": [r"mock_nfl_datas*="]},
    {
        "file": "tests/test_dag_task_functions.py",
        "patterns": [r"kalshi_sandbox_clients*="],
    },
    {"file": "tests/test_kalshi_markets.py", "patterns": [r"mock_configs*="]},
]


# Also clean up unused imports in test_elo_actual.py
def clean_imports():
    """Clean up unused imports in test_elo_actual.py"""
    try:
        with open("tests/test_elo_actual.py", "r") as f:
            content = f.read()

        # Comment out specific unused imports
        imports_to_comment = [
            "import nhl_elo_rating",
            "import tennis_elo_rating",
            "import epl_elo_rating",
            "import ligue1_elo_rating",
            "import glicko2_rating",
        ]

        for imp in imports_to_comment:
            content = content.replace(imp, f"# {imp}")

        with open("tests/test_elo_actual.py", "w") as f:
            f.write(content)

        print("Cleaned imports in tests/test_elo_actual.py")
        return True

    except Exception as e:
        print(f"Error cleaning imports: {e}")
        return False


# Execute cleanups
print("Starting test file cleanup...")
changes_made = False

for task in cleanup_tasks:
    if clean_file(task["file"], task["patterns"]):
        changes_made = True

if clean_imports():
    changes_made = True

if changes_made:
    print("\nCleanup completed successfully!")
else:
    print("\nNo changes needed.")

print("\nRun 'pytest tests/ -k \"not playwright\" -v' to verify tests still pass.")
