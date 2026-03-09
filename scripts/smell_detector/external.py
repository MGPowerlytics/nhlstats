"""Run external analysis tools (ruff, radon) via subprocess.

Results are converted into SmellInstance objects for unified reporting.
Falls back gracefully if a tool is not installed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.smell_detector.models import (
    FileMetrics,
    SmellInstance,
    SmellSeverity,
    SmellType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_command(cmd: list[str], cwd: str | None = None) -> tuple[bool, str]:
    """Run a command, returning (success, stdout).  Never raises."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd,
        )
        return result.returncode == 0, result.stdout
    except FileNotFoundError:
        return False, ""
    except subprocess.TimeoutExpired:
        return False, ""


# ---------------------------------------------------------------------------
# Ruff
# ---------------------------------------------------------------------------


def run_ruff(target_dir: str) -> list[SmellInstance]:
    """Run ``ruff check --output-format=json`` and parse results.

    Returns SmellInstance objects for each violation.
    """
    cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--output-format=json",
        "--select=ALL",
        "--ignore=D,ANN,ERA,T20,FIX,TD,S",  # Skip docstring/annotation/print/todo/security rules
        target_dir,
    ]
    ok, output = _run_command(cmd)
    if not output.strip():
        return []

    try:
        violations = json.loads(output)
    except json.JSONDecodeError:
        return []

    smells: list[SmellInstance] = []
    for v in violations:
        # ruff JSON format: {"code": "E501", "message": "...", "filename": "...",
        #                     "location": {"row": N, "column": N}, ...}
        code = v.get("code", "")
        message = v.get("message", "")
        filename = v.get("filename", "")
        loc = v.get("location", {})
        end_loc = v.get("end_location", {})
        row = loc.get("row", 0)
        end_row = end_loc.get("row", row)

        # Classify severity by rule category.
        severity = SmellSeverity.LOW
        if code.startswith(("C9", "PLR")):  # complexity, refactor
            severity = SmellSeverity.MEDIUM
        elif code.startswith(("B", "SIM")):  # bugbear, simplicity
            severity = SmellSeverity.MEDIUM

        smells.append(
            SmellInstance(
                file=filename,
                line=row,
                end_line=end_row,
                smell_type=SmellType.LINT_VIOLATION,
                severity=severity,
                message=f"[{code}] {message}",
                suggested_refactoring=f"Fix ruff violation {code}.",
                symbol_name="",
            ),
        )

    return smells


# ---------------------------------------------------------------------------
# Radon — Cyclomatic Complexity
# ---------------------------------------------------------------------------


def run_radon_cc(target_dir: str) -> tuple[list[SmellInstance], dict[str, float]]:
    """Run ``radon cc --json`` and return smells + per-file avg complexity.

    Returns:
        (smells, file_complexity_map) where file_complexity_map maps
        filepath → average cyclomatic complexity.
    """
    cmd = [sys.executable, "-m", "radon", "cc", "--json", "-n", "C", target_dir]
    ok, output = _run_command(cmd)

    smells: list[SmellInstance] = []
    file_cc: dict[str, float] = {}

    if not output.strip():
        return smells, file_cc

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return smells, file_cc

    for filepath, blocks in data.items():
        if not isinstance(blocks, list):
            continue
        complexities = []
        for block in blocks:
            cc = block.get("complexity", 0)
            complexities.append(cc)
            name = block.get("name", "?")
            rank = block.get("rank", "?")
            lineno = block.get("lineno", 0)
            endline = block.get("endline", lineno)

            # Only flag C (11-15), D (16-20), E (21-30), F (30+)
            if rank in ("C", "D", "E", "F"):
                severity = {
                    "C": SmellSeverity.MEDIUM,
                    "D": SmellSeverity.HIGH,
                    "E": SmellSeverity.HIGH,
                    "F": SmellSeverity.CRITICAL,
                }.get(rank, SmellSeverity.MEDIUM)

                smells.append(
                    SmellInstance(
                        file=filepath,
                        line=lineno,
                        end_line=endline,
                        smell_type=SmellType.COMPLEX_FUNCTION,
                        severity=severity,
                        message=(
                            f"Function '{name}' has cyclomatic complexity {cc} "
                            f"(rank {rank})"
                        ),
                        suggested_refactoring=(
                            "Extract Method / Replace Conditional with "
                            "Polymorphism to reduce branching."
                        ),
                        symbol_name=name,
                    ),
                )
        if complexities:
            file_cc[filepath] = sum(complexities) / len(complexities)

    return smells, file_cc


# ---------------------------------------------------------------------------
# Radon — Maintainability Index
# ---------------------------------------------------------------------------


def run_radon_mi(target_dir: str) -> dict[str, float]:
    """Run ``radon mi --json`` and return per-file Maintainability Index.

    Returns:
        Map of filepath → MI score (0–100 scale).
    """
    cmd = [sys.executable, "-m", "radon", "mi", "--json", target_dir]
    ok, output = _run_command(cmd)

    if not output.strip():
        return {}

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return {}

    # radon mi JSON: {"file.py": {"mi": 65.2, "rank": "B"}, ...}
    result: dict[str, float] = {}
    for filepath, info in data.items():
        if isinstance(info, dict):
            result[filepath] = info.get("mi", 100.0)
        elif isinstance(info, (int, float)):
            # Some radon versions return just the score.
            result[filepath] = float(info)
    return result


# ---------------------------------------------------------------------------
# Combined external metrics
# ---------------------------------------------------------------------------


def collect_external_metrics(
    target_dir: str,
) -> tuple[list[SmellInstance], dict[str, FileMetrics]]:
    """Run all external tools and aggregate results.

    Returns:
        (all_smells, per_file_metrics)
    """
    all_smells: list[SmellInstance] = []
    per_file: dict[str, FileMetrics] = {}

    # Ruff lint smells.
    ruff_smells = run_ruff(target_dir)
    all_smells.extend(ruff_smells)

    # Radon cyclomatic complexity.
    cc_smells, file_cc = run_radon_cc(target_dir)
    all_smells.extend(cc_smells)

    # Radon maintainability index.
    file_mi = run_radon_mi(target_dir)

    # Build per-file metrics dicts.
    all_files = set(file_cc) | set(file_mi)
    for fp in all_files:
        metrics = per_file.get(fp, FileMetrics())
        if fp in file_cc:
            metrics.cyclomatic_complexity_avg = file_cc[fp]
        if fp in file_mi:
            metrics.maintainability_index = file_mi[fp]
        per_file[fp] = metrics

    return all_smells, per_file
