"""Render a RepoReport as a Markdown document optimised for LLM consumption."""

from __future__ import annotations

from scripts.smell_detector.models import (
    FileReport,
    RepoReport,
    SmellInstance,
    SmellSeverity,
)

# Severity badge for visual scanning.
SEVERITY_BADGE: dict[SmellSeverity, str] = {
    SmellSeverity.CRITICAL: "🔴 CRITICAL",
    SmellSeverity.HIGH: "🟠 HIGH",
    SmellSeverity.MEDIUM: "🟡 MEDIUM",
    SmellSeverity.LOW: "🟢 LOW",
}

GRADE_EMOJI: dict[str, str] = {
    "A": "✅",
    "B": "👍",
    "C": "⚠️",
    "D": "🔶",
    "F": "❌",
}


def _grade_badge(grade: str) -> str:
    return f"{GRADE_EMOJI.get(grade, '❓')} {grade}"


def _smell_table(smells: list[SmellInstance]) -> str:
    """Render a list of smells as a Markdown table."""
    if not smells:
        return "_No smells detected._\n"

    lines = [
        "| Line | Severity | Type | Message | Suggested Refactoring |",
        "|-----:|:---------|:-----|:--------|:----------------------|",
    ]
    for s in sorted(smells, key=lambda x: (-_severity_rank(x.severity), x.line)):
        sev = SEVERITY_BADGE.get(s.severity, s.severity.value)
        lines.append(
            f"| {s.line} | {sev} | {s.smell_type.value} | "
            f"{s.message} | {s.suggested_refactoring} |"
        )
    return "\n".join(lines) + "\n"


def _severity_rank(severity: SmellSeverity) -> int:
    return {
        SmellSeverity.CRITICAL: 4,
        SmellSeverity.HIGH: 3,
        SmellSeverity.MEDIUM: 2,
        SmellSeverity.LOW: 1,
    }.get(severity, 0)


def _top_smelliest_files(report: RepoReport, n: int = 10) -> list[FileReport]:
    """Return the *n* files with the lowest scores."""
    return sorted(report.files, key=lambda f: f.score)[:n]


def _prioritised_refactoring_queue(
    report: RepoReport, n: int = 15
) -> list[SmellInstance]:
    """Return the top *n* highest-impact smells to fix first."""
    all_smells: list[SmellInstance] = []
    for fr in report.files:
        all_smells.extend(fr.smells)
    # Sort by severity (desc) then by file+line.
    return sorted(
        all_smells,
        key=lambda s: (-_severity_rank(s.severity), s.file, s.line),
    )[:n]


# ---------------------------------------------------------------------------
# Main formatting function
# ---------------------------------------------------------------------------


def format_markdown(report: RepoReport) -> str:
    """Render a full Markdown report from *report*."""
    sections: list[str] = []

    # --- Title ---
    sections.append(
        f"# Code Smell Report — {_grade_badge(report.overall_grade)} "
        f"(Score: {report.overall_score}/100)\n"
    )
    sections.append(f"_Scanned: {report.target_dir}_  \n")
    sections.append(f"_Generated: {report.timestamp}_\n")

    # --- Executive Summary ---
    s = report.summary
    sections.append("## Executive Summary\n")
    sections.append(f"| Metric | Value |")
    sections.append(f"|:-------|------:|")
    sections.append(f"| **Overall Grade** | {_grade_badge(report.overall_grade)} |")
    sections.append(f"| **Overall Score** | {report.overall_score}/100 |")
    sections.append(f"| **Files Scanned** | {s.total_files} |")
    sections.append(f"| **Total Lines (non-blank)** | {s.total_lines:,} |")
    sections.append(f"| **Total Smells** | {s.total_smells} |")
    sections.append(f"| **Avg Maintainability Index** | {s.avg_maintainability} |")
    sections.append(f"| **Avg Cyclomatic Complexity** | {s.avg_complexity} |")
    sections.append("")

    # Smells by severity.
    if s.smells_by_severity:
        sections.append("### Smells by Severity\n")
        sections.append("| Severity | Count |")
        sections.append("|:---------|------:|")
        for sev, count in s.smells_by_severity.items():
            sections.append(f"| {sev} | {count} |")
        sections.append("")

    # Smells by type.
    if s.smells_by_type:
        sections.append("### Smells by Category\n")
        sections.append("| Category | Count |")
        sections.append("|:---------|------:|")
        for typ, count in s.smells_by_type.items():
            sections.append(f"| {typ} | {count} |")
        sections.append("")

    # --- Prioritised Refactoring Queue ---
    queue = _prioritised_refactoring_queue(report)
    if queue:
        sections.append("## 🎯 Prioritised Refactoring Queue\n")
        sections.append("These are the highest-impact smells to address first:\n")
        for i, smell in enumerate(queue, 1):
            sev = SEVERITY_BADGE.get(smell.severity, smell.severity.value)
            sections.append(
                f"{i}. **{smell.file}:{smell.line}** — {sev} — "
                f"{smell.smell_type.value}  \n"
                f"   {smell.message}  \n"
                f"   → _{smell.suggested_refactoring}_\n"
            )
        sections.append("")

    # --- Top Smelliest Files ---
    worst = _top_smelliest_files(report)
    if worst:
        sections.append("## 📊 Files Ranked by Quality\n")
        sections.append("| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |")
        sections.append("|-----:|:-----|:------|------:|-------:|----:|---:|-------:|")
        for i, fr in enumerate(worst, 1):
            sections.append(
                f"| {i} | {fr.path} | {_grade_badge(fr.grade)} | "
                f"{fr.score} | {len(fr.smells)} | "
                f"{fr.metrics.lines_of_code} | "
                f"{fr.metrics.maintainability_index:.0f} | "
                f"{fr.metrics.cyclomatic_complexity_avg:.1f} |"
            )
        sections.append("")

    # --- Per-File Details ---
    # Only include the worst files to keep report concise for LLM consumption.
    MAX_DETAIL_FILES = 20
    MAX_SMELLS_PER_FILE = 15
    files_with_smells = [
        fr for fr in report.files if fr.smells or fr.grade in ("D", "F")
    ]
    files_with_smells.sort(key=lambda f: f.score)
    files_with_smells = files_with_smells[:MAX_DETAIL_FILES]

    if files_with_smells:
        sections.append("## 📁 Per-File Details\n")
        if len(report.files) > MAX_DETAIL_FILES:
            sections.append(
                f"_Showing {MAX_DETAIL_FILES} worst files. "
                f"{len(report.files) - MAX_DETAIL_FILES} additional files omitted._\n"
            )
        for fr in files_with_smells:
            sections.append(
                f"### {fr.path} — {_grade_badge(fr.grade)} ({fr.score}/100)\n"
            )
            sections.append(
                f"LOC: {fr.metrics.lines_of_code} | "
                f"Classes: {fr.metrics.num_classes} | "
                f"Functions: {fr.metrics.num_functions} | "
                f"MI: {fr.metrics.maintainability_index:.0f} | "
                f"Avg CC: {fr.metrics.cyclomatic_complexity_avg:.1f}\n"
            )
            display_smells = sorted(
                fr.smells,
                key=lambda x: (-_severity_rank(x.severity), x.line),
            )[:MAX_SMELLS_PER_FILE]
            sections.append(_smell_table(display_smells))
            if len(fr.smells) > MAX_SMELLS_PER_FILE:
                sections.append(
                    f"_... and {len(fr.smells) - MAX_SMELLS_PER_FILE} more smells._\n"
                )

    # --- Clean Files ---
    clean_files = [
        fr for fr in report.files if not fr.smells and fr.grade not in ("D", "F")
    ]
    if clean_files:
        sections.append(
            f"## ✨ Clean Files ({len(clean_files)} files with no smells)\n"
        )
        sections.append("<details><summary>Click to expand</summary>\n")
        for fr in clean_files:
            sections.append(f"- {fr.path} — {_grade_badge(fr.grade)}")
        sections.append("\n</details>\n")

    # --- Footer ---
    sections.append("---\n")
    sections.append(
        "_Report generated by XP Code Smell Detector. "
        "Smells are static heuristics — use judgement when prioritising fixes._\n"
    )

    return "\n".join(sections)


def format_json(report: RepoReport) -> str:
    """Render the report as JSON."""
    import json
    from dataclasses import asdict

    # Convert enums to their values for JSON serialisation.
    def _serialise(obj: object) -> object:
        if hasattr(obj, "value"):
            return obj.value
        raise TypeError(f"Cannot serialise {type(obj)}")

    return json.dumps(asdict(report), default=_serialise, indent=2)
