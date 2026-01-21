import os
import re
from pathlib import Path
import pytest

DOCS_DIR = Path("docs")
README_PATH = Path("README.md")

def test_readme_exists():
    """Ensure README.md exists and is not empty."""
    assert README_PATH.exists()
    assert README_PATH.stat().st_size > 0

def test_essential_docs_exist():
    """Ensure critical documentation files exist."""
    essential_files = [
        "BETTING_STRATEGY.md",
        "SYSTEM_OVERVIEW.md",
        "DASHBOARD_GUIDE.md",
    ]
    for filename in essential_files:
        assert (DOCS_DIR / filename).exists(), f"Missing essential doc: {filename}"

def test_readme_links_are_valid():
    """
    Parse all relative links in README.md and ensure they point to existing files.
    Ignores external links (http/https).
    """
    if not README_PATH.exists():
        pytest.skip("README.md not found")

    content = README_PATH.read_text()
    # Regex for markdown links [text](target)
    links = re.findall(r'\[.*?\]\((.*?)\)', content)

    for link in links:
        # Skip external links and anchors
        if link.startswith("http") or link.startswith("#"):
            continue

        # Clean link (remove query params or anchors)
        clean_link = link.split('#')[0].split('?')[0]
        if not clean_link:
            continue

        target_path = Path(clean_link)
        assert target_path.exists(), f"Broken link in README.md: {link}"

def test_docs_folder_structure():
    """Ensure docs folder follows structure."""
    assert DOCS_DIR.exists()
    assert (DOCS_DIR / "BETTING_STRATEGY.md").exists()
