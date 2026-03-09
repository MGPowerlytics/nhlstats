#!/usr/bin/env python3
"""Update KalshiBetting tests to use config objects."""

import re
from pathlib import Path


def update_test_file(file_path: Path):
    """Update a test file to use KalshiConfig and BettingConfig."""
    content = file_path.read_text()

    # Pattern for KalshiBetting constructor calls
    kalshi_pattern = r"KalshiBetting\(([^)]+)\)"

    def replace_kalshi(match):
        args_str = match.group(1)

        # Check if it's already using config=
        if "config=" in args_str:
            return match.group(0)

        # Parse keyword arguments
        kwargs = {}
        if "=" in args_str:
            # Keyword arguments
            pairs = re.findall(r"(\w+)\s*=\s*[^,]+", args_str)
            for pair in args_str.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    kwargs[key.strip()] = value.strip()
        else:
            # Positional arguments
            parts = [p.strip() for p in args_str.split(",") if p.strip()]
            if len(parts) >= 1:
                kwargs["api_key_id"] = parts[0]
            if len(parts) >= 2:
                kwargs["private_key_path"] = parts[1]
            if len(parts) >= 3:
                kwargs["max_bet_size"] = parts[2]
            if len(parts) >= 4:
                kwargs["production"] = parts[3]

        # Build config object
        config_args = []
        for key in [
            "api_key_id",
            "private_key_path",
            "max_bet_size",
            "production",
            "odds_api_key",
            "dedupe_dir",
        ]:
            if key in kwargs:
                config_args.append(f"{key}={kwargs[key]}")

        config_str = f"KalshiConfig({', '.join(config_args)})"
        return f"KalshiBetting(config={config_str})"

    # Apply replacement
    new_content = re.sub(kalshi_pattern, replace_kalshi, content)

    if new_content != content:
        file_path.write_text(new_content)
        print(f"Updated {file_path}")
    else:
        print(f"No changes needed for {file_path}")


def main():
    test_dir = Path(__file__).parent / "tests"

    # Update all test files that use KalshiBetting
    for test_file in test_dir.glob("*.py"):
        if test_file.name.startswith("test_kalshi"):
            update_test_file(test_file)

    # Also update other test files that might use KalshiBetting
    for test_file in test_dir.glob("test_*.py"):
        content = test_file.read_text()
        if "KalshiBetting(" in content:
            update_test_file(test_file)


if __name__ == "__main__":
    main()
