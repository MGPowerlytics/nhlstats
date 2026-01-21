import os
from pathlib import Path
import pytest
import pathspec

ROOT_DIR = Path(".")

def get_gitignore_spec():
    """Load .gitignore patterns."""
    gitignore = ROOT_DIR / ".gitignore"
    if gitignore.exists():
        with open(gitignore, "r") as f:
            return pathspec.PathSpec.from_lines("gitwildmatch", f)
    return pathspec.PathSpec.from_lines("gitwildmatch", [])

def test_no_empty_directories():
    """Ensure no empty directories exist in the project, respecting .gitignore."""
    spec = get_gitignore_spec()
    empty_dirs = []

    for root, dirs, files in os.walk(ROOT_DIR):
        # Skip .git directory explicitly
        if ".git" in root.split(os.sep):
            continue

        # Check if the current directory itself is ignored
        # pathspec expects relative paths from root
        rel_root = os.path.relpath(root, ROOT_DIR)
        if rel_root == ".":
            rel_root = ""

        # Filter subdirectories based on ignore patterns to avoid traversing ignored trees
        # This is optimization but also correctness
        # Must check d + "/" to match directory patterns in .gitignore like "data/"
        allowed_dirs = []
        for d in dirs:
            path = os.path.join(rel_root, d)
            # Check matches for "path" and "path/" to handle directory rules
            is_ignored = spec.match_file(path) or spec.match_file(path + "/")
            if not is_ignored and d != ".git":
                allowed_dirs.append(d)

        dirs[:] = allowed_dirs

        for d in dirs:
            dir_path = Path(root) / d
            rel_path = os.path.join(rel_root, d)

            # Double check (redundant but safe)
            if spec.match_file(rel_path) or spec.match_file(rel_path + "/"):
                continue

            try:
                if not any(dir_path.iterdir()):
                    empty_dirs.append(str(dir_path))
            except PermissionError:
                # If we can't access it, we assume it's a system dir (like postgres-data owned by root)
                # and skip it.
                continue

    assert not empty_dirs, f"Found empty directories (not ignored): {empty_dirs}"

def test_no_scripts_in_root():
    """Ensure no .py or .sh files exist in the root directory."""
    # Allowlist for essential configuration/entry points if strictly necessary
    # But user asked for "no python or shell scripts", so we aim for zero.

    forbidden_extensions = {".py", ".sh"}
    root_files = [f for f in os.listdir(ROOT_DIR) if os.path.isfile(f)]

    violators = []
    for f in root_files:
        ext = os.path.splitext(f)[1]
        if ext in forbidden_extensions:
            violators.append(f)

    assert not violators, f"Found scripts in root directory: {violators}"
