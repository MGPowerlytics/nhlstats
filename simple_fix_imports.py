#!/usr/bin/env python3
"""
Simple script to fix imports in elo files.
Replace 'from .module' with try-except pattern.
"""

import os
import re
from pathlib import Path

def fix_file(filepath: Path):
    """Fix imports in a single file."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Find all relative imports
    pattern = r'^from \.([a-zA-Z_][a-zA-Z0-9_]*) import'

    def replace_import(match):
        module = match.group(1)
        return f'''try:
    # Try absolute import first (works when plugins is in sys.path)
    from {module} import
except ImportError:
    # Fall back to relative imports (works in development)
    from .{module} import'''

    new_content = re.sub(pattern, replace_import, content, flags=re.MULTILINE)

    # Fix the formatting - the import statement needs to be on the same line
    # Actually, let's do a simpler approach
    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r'^(from \.([a-zA-Z_][a-zA-Z0-9_]*) import .*)$', line)
        if match:
            module = match.group(2)
            import_stmt = match.group(1)
            # Get the full import statement (might be multi-line)
            full_import = line
            j = i + 1
            while j < len(lines) and lines[j].startswith('    ') and not lines[j].startswith('    #'):
                full_import += '\n' + lines[j]
                j += 1

            # Create replacement
            replacement = f'''try:
    # Try absolute import first (works when plugins is in sys.path)
    from {module} import{full_import[5 + len(module):]}
except ImportError:
    # Fall back to relative imports (works in development)
{full_import}'''

            new_lines.append(replacement)
            i = j  # Skip the lines we just processed
        else:
            new_lines.append(line)
            i += 1

    new_content = '\n'.join(new_lines)

    if content != new_content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"✅ Fixed imports in {filepath.name}")
        return True
    return False

def main():
    elo_dir = Path("/mnt/data2/nhlstats/plugins/elo")
    files_fixed = 0

    for py_file in elo_dir.glob("*.py"):
        if fix_file(py_file):
            files_fixed += 1

    print(f"\n📊 Fixed imports in {files_fixed} files")

if __name__ == "__main__":
    main()
