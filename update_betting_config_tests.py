#!/usr/bin/env python3
"""Update tests to use BettingConfig instead of keyword arguments."""

import re
from pathlib import Path


def update_test_file(file_path: Path):
    """Update test file to use BettingConfig."""
    content = file_path.read_text()

    # Pattern for process_bet_recommendations calls with keyword arguments
    pattern = r"process_bet_recommendations\([^)]*?(min_confidence|min_edge|dry_run|sport_filter|trade_date)\s*="

    if re.search(pattern, content):
        print(f"Updating {file_path}")

        # Simple replacement for common patterns
        replacements = [
            (
                r"process_bet_recommendations\(([^,]+),\s*min_confidence=([^),]+)",
                r"process_bet_recommendations(\1, config=BettingConfig(min_confidence=\2)",
            ),
            (
                r"process_bet_recommendations\(([^,]+),\s*min_edge=([^),]+)",
                r"process_bet_recommendations(\1, config=BettingConfig(min_edge=\2)",
            ),
            (
                r"process_bet_recommendations\(([^,]+),\s*dry_run=([^),]+)",
                r"process_bet_recommendations(\1, config=BettingConfig(dry_run=\2)",
            ),
            (
                r"process_bet_recommendations\(([^,]+),\s*sport_filter=([^),]+)",
                r"process_bet_recommendations(\1, config=BettingConfig(sport_filter=\2)",
            ),
        ]

        for old, new in replacements:
            content = re.sub(old, new, content)

        file_path.write_text(content)


def main():
    test_file = Path(__file__).parent / "tests" / "test_kalshi_betting.py"
    update_test_file(test_file)


if __name__ == "__main__":
    main()
