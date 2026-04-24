"""Standalone XP Code Smell Detector.

Scans Python files in a repository for common code smells using the
Extreme Programming Continuous Refactoring framework. Produces a graded
Markdown report suitable for consumption by an AI refactoring agent.

No dependencies on the henchman library — uses only stdlib + subprocess
calls to ruff and radon.
"""

from scripts.smell_detector.models import (
    FileReport,
    RepoReport,
    SmellInstance,
    SmellSeverity,
    SmellType,
)
from scripts.smell_detector.scanner import scan_repository

__all__ = [
    "FileReport",
    "RepoReport",
    "SmellInstance",
    "SmellSeverity",
    "SmellType",
    "scan_repository",
]
