import os
from pathlib import Path
import pytest

ROOT_DIR = Path(".")

def test_no_empty_directories():
    """Ensure no empty directories exist in the project."""
    empty_dirs = []
    for root, dirs, files in os.walk(ROOT_DIR):
        # Skip .git and other hidden/system dirs
        if "/." in root or root.startswith("."):
            continue

        for d in dirs:
            dir_path = Path(root) / d
            # Skip hidden directories
            if d.startswith("."):
                continue

            # check if empty
            if not any(dir_path.iterdir()):
                empty_dirs.append(str(dir_path))

    assert not empty_dirs, f"Found empty directories: {empty_dirs}"

def test_no_scripts_in_root():
    """Ensure no .py or .sh files exist in the root directory."""
    # Allowlist for essential configuration/entry points if strictly necessary
    # But user asked for "no python or shell scripts", so we aim for zero.
    # We might need to exception `setup.py` if it existed, but here we enforce the rule.

    forbidden_extensions = {".py", ".sh"}
    root_files = [f for f in os.listdir(ROOT_DIR) if os.path.isfile(f)]

    violators = []
    for f in root_files:
        ext = os.path.splitext(f)[1]
        if ext in forbidden_extensions:
            violators.append(f)

    assert not violators, f"Found scripts in root directory: {violators}"
