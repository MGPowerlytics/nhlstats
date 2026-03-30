#!/usr/bin/env python3
"""
Fix import statements in elo module files.
Change 'from plugins.elo.' to 'from .' for relative imports.
"""

import os
import re
from pathlib import Path

def fix_imports_in_file(filepath: Path):
    """Fix import statements in a single file."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Replace 'from plugins.elo.' with 'from .'
    # But be careful not to replace imports from other plugins modules
    # like 'from plugins.base_games import ...'
    fixed_content = re.sub(
        r'from plugins\.elo\.([a-zA-Z_][a-zA-Z0-9_]*) import',
        r'from .\1 import',
        content
    )

    if content != fixed_content:
        with open(filepath, 'w') as f:
            f.write(fixed_content)
        print(f"✅ Fixed imports in {filepath.name}")
        return True
    return False

def main():
    elo_dir = Path("/mnt/data2/nhlstats/plugins/elo")
    files_fixed = 0

    for py_file in elo_dir.glob("*.py"):
        if py_file.name == "__init__.py" or py_file.name == "factory.py":
            continue  # Already fixed
        if fix_imports_in_file(py_file):
            files_fixed += 1

    print(f"\n📊 Fixed imports in {files_fixed} files")

if __name__ == "__main__":
    main()
