"""Data models for the code smell detector.

Pure dataclasses — no external dependencies.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class SmellType(enum.Enum):
    """Categories of code smells aligned with XP refactoring patterns."""

    LONG_METHOD = "Long Method"
    LARGE_CLASS = "Large Class"
    DEEP_NESTING = "Deep Nesting"
    MAGIC_NUMBER = "Magic Number"
    MISSING_TYPE_HINT = "Missing Type Hint"
    DUPLICATE_CODE = "Duplicate Code"
    PRIMITIVE_OBSESSION = "Primitive Obsession"
    FEATURE_ENVY = "Feature Envy"
    COMPLEX_FUNCTION = "Complex Function"
    LOW_MAINTAINABILITY = "Low Maintainability"
    LINT_VIOLATION = "Lint Violation"


class SmellSeverity(enum.Enum):
    """Severity levels for detected smells."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Maps severity to score deduction when grading files.
SEVERITY_PENALTY: dict[SmellSeverity, int] = {
    SmellSeverity.LOW: 2,
    SmellSeverity.MEDIUM: 5,
    SmellSeverity.HIGH: 10,
    SmellSeverity.CRITICAL: 20,
}


@dataclass(frozen=True)
class SmellInstance:
    """A single detected code smell."""

    file: str
    line: int
    end_line: int
    smell_type: SmellType
    severity: SmellSeverity
    message: str
    suggested_refactoring: str
    symbol_name: str = ""


@dataclass
class FileMetrics:
    """Raw metrics for a single file (populated by external tools)."""

    lines_of_code: int = 0
    cyclomatic_complexity_avg: float = 0.0
    cyclomatic_complexity_max: int = 0
    maintainability_index: float = 100.0
    num_classes: int = 0
    num_functions: int = 0


@dataclass
class FileReport:
    """Smell report for a single file."""

    path: str
    smells: list[SmellInstance] = field(default_factory=list)
    metrics: FileMetrics = field(default_factory=FileMetrics)
    grade: str = "A"
    score: float = 100.0


@dataclass
class RepoSummary:
    """Aggregate statistics for the entire repository."""

    total_files: int = 0
    total_lines: int = 0
    total_smells: int = 0
    smells_by_type: dict[str, int] = field(default_factory=dict)
    smells_by_severity: dict[str, int] = field(default_factory=dict)
    avg_maintainability: float = 100.0
    avg_complexity: float = 0.0


@dataclass
class RepoReport:
    """Complete smell report for a repository."""

    target_dir: str
    files: list[FileReport] = field(default_factory=list)
    summary: RepoSummary = field(default_factory=RepoSummary)
    overall_grade: str = "A"
    overall_score: float = 100.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
