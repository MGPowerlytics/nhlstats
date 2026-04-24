"""Grading rubric for code smell reports.

Converts raw smell counts + severity + external metrics into A–F grades.
"""

from __future__ import annotations

from scripts.smell_detector.models import (
    SEVERITY_PENALTY,
    FileMetrics,
    FileReport,
    RepoReport,
    RepoSummary,
    SmellSeverity,
)

# Grade boundaries (score → letter).
GRADE_BOUNDARIES: list[tuple[float, str]] = [
    (90.0, "A"),
    (80.0, "B"),
    (70.0, "C"),
    (60.0, "D"),
    (0.0, "F"),
]

# Weight of Maintainability Index vs smell-based score.
MI_WEIGHT = 0.30
SMELL_WEIGHT = 0.70


def _letter_grade(score: float) -> str:
    """Map a 0–100 score to a letter grade."""
    for threshold, letter in GRADE_BOUNDARIES:
        if score >= threshold:
            return letter
    return "F"


def grade_file(report: FileReport) -> None:
    """Compute and set grade + score on a FileReport (mutates in place)."""
    # Smell-based score: start at 100, deduct per smell.
    smell_score = 100.0
    for smell in report.smells:
        penalty = SEVERITY_PENALTY.get(smell.severity, 2)
        smell_score -= penalty
    smell_score = max(0.0, smell_score)

    # Maintainability Index component (already 0–100 from radon).
    mi = report.metrics.maintainability_index
    mi_score = max(0.0, min(100.0, mi))

    # Composite score.
    report.score = round(SMELL_WEIGHT * smell_score + MI_WEIGHT * mi_score, 1)
    report.grade = _letter_grade(report.score)


def grade_repo(report: RepoReport) -> None:
    """Compute overall grade and summary statistics (mutates in place)."""
    # Grade each file.
    for fr in report.files:
        grade_file(fr)

    # Aggregate summary.
    summary = RepoSummary()
    summary.total_files = len(report.files)
    summary.total_lines = sum(fr.metrics.lines_of_code for fr in report.files)
    summary.total_smells = sum(len(fr.smells) for fr in report.files)

    # Smells by type.
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for fr in report.files:
        for smell in fr.smells:
            by_type[smell.smell_type.value] = by_type.get(smell.smell_type.value, 0) + 1
            by_severity[smell.severity.value] = (
                by_severity.get(smell.severity.value, 0) + 1
            )
    summary.smells_by_type = dict(sorted(by_type.items(), key=lambda x: -x[1]))
    summary.smells_by_severity = dict(sorted(by_severity.items(), key=lambda x: -x[1]))

    # Averages.
    if report.files:
        mi_values = [fr.metrics.maintainability_index for fr in report.files]
        cc_values = [
            fr.metrics.cyclomatic_complexity_avg
            for fr in report.files
            if fr.metrics.cyclomatic_complexity_avg > 0
        ]
        summary.avg_maintainability = round(sum(mi_values) / len(mi_values), 1)
        summary.avg_complexity = (
            round(sum(cc_values) / len(cc_values), 1) if cc_values else 0.0
        )

    report.summary = summary

    # Overall score: weighted average by LOC (files with more code matter more).
    total_loc = summary.total_lines or 1
    weighted_score = sum(fr.score * fr.metrics.lines_of_code for fr in report.files)
    report.overall_score = round(weighted_score / total_loc, 1) if total_loc else 100.0
    report.overall_grade = _letter_grade(report.overall_score)
