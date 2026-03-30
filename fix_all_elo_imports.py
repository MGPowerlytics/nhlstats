#!/usr/bin/env python3
"""
Fix all import statements in elo module files with try-except pattern.
"""

import os
import re
from pathlib import Path
import ast
import astor

def fix_imports_in_file(filepath: Path):
    """Fix import statements in a single file using AST."""
    with open(filepath, 'r') as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        print(f"⚠️  Syntax error in {filepath.name}, skipping")
        return False

    # Check if file already has try-except for imports
    has_try_except_imports = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            # Check if this try block contains imports
            for item in node.body:
                if isinstance(item, ast.Import) or isinstance(item, ast.ImportFrom):
                    has_try_except_imports = True
                    break

    if has_try_except_imports:
        # Already fixed
        return False

    # Find all import statements
    imports_to_fix = []
    for i, node in enumerate(tree.body):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith('.'):
                # This is a relative import, needs fixing
                imports_to_fix.append((i, node))

    if not imports_to_fix:
        return False

    # Create new import statements with try-except
    new_imports = []

    # Group imports by module
    imports_by_module = {}
    for i, node in imports_to_fix:
        module = node.module.lstrip('.')
        if module not in imports_by_module:
            imports_by_module[module] = []
        imports_by_module[module].append((i, node))

    # Create try-except for each module
    for module, imports in imports_by_module.items():
        # Create the try block
        try_body = []
        for i, node in imports:
            # Create absolute import
            abs_import = ast.ImportFrom(
                module=module,
                names=node.names,
                level=0
            )
            try_body.append(abs_import)

        # Create the except block
        except_body = []
        for i, node in imports:
            # Keep the original relative import
            except_body.append(node)

        # Create try-except node
        try_except = ast.Try(
            body=try_body,
            handlers=[
                ast.ExceptHandler(
                    type=ast.Name(id='ImportError', ctx=ast.Load()),
                    name=None,
                    body=except_body
                )
            ],
            orelse=[],
            finalbody=[]
        )

        new_imports.append((min(i for i, _ in imports), try_except))

    # Replace old imports with new ones
    # Sort by position in reverse order so we can replace without affecting indices
    new_imports.sort(key=lambda x: x[0], reverse=True)

    for i, new_import in new_imports:
        # Remove all the old imports that are being replaced
        indices_to_remove = [idx for idx, _ in imports_by_module.values() for idx, _ in _ if idx == i]
        for idx in sorted(set(indices_to_remove), reverse=True):
            if idx < len(tree.body):
                tree.body.pop(idx)

        # Insert the new try-except import
        tree.body.insert(i, new_import)

    # Generate new code
    new_content = astor.to_source(tree)

    with open(filepath, 'w') as f:
        f.write(new_content)

    print(f"✅ Fixed imports in {filepath.name}")
    return True

def main():
    elo_dir = Path("/mnt/data2/nhlstats/plugins/elo")
    files_fixed = 0

    for py_file in elo_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            # Handle __init__.py specially
            continue
        if fix_imports_in_file(py_file):
            files_fixed += 1

    # Now fix __init__.py
    init_file = elo_dir / "__init__.py"
    if fix_imports_in_file(init_file):
        files_fixed += 1

    print(f"\n📊 Fixed imports in {files_fixed} files")

if __name__ == "__main__":
    main()
