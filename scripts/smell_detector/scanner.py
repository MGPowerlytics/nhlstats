"""File discovery and orchestration of all detectors."""

from __future__ import annotations

import ast
import fnmatch
from pathlib import Path

from scripts.smell_detector.detectors import ALL_DETECTORS
from scripts.smell_detector.detectors.duplicates import DuplicateCodeDetector
from scripts.smell_detector.external import collect_external_metrics
from scripts.smell_detector.grading import grade_repo
from scripts.smell_detector.models import (
    FileMetrics,
    FileReport,
    RepoReport,
    SmellInstance,
    SmellType,
)

DEFAULT_EXCLUDES: list[str] = [
    "tests/*",
    "*_test.py",
    "test_*.py",
    "conftest.py",
    "setup.py",
    "*/migrations/*",
    "*/.venv/*",
    "*/node_modules/*",
    "*/__pycache__/*",
    "*.egg-info/*",
]


def _should_exclude(path: str, excludes: list[str]) -> bool:
    """Return True if *path* matches any exclusion pattern."""
    return any(fnmatch.fnmatch(path, pat) for pat in excludes)


def _discover_python_files(
    target_dir: Path,
    excludes: list[str],
) -> list[Path]:
    """Recursively find .py files under *target_dir*, honoring *excludes*."""
    files: list[Path] = []
    for p in sorted(target_dir.rglob("*.py")):
        rel = str(p.relative_to(target_dir))
        if not _should_exclude(rel, excludes):
            files.append(p)
    return files


def _count_lines(source: str) -> int:
    """Count non-blank, non-comment lines."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def _count_classes_and_functions(tree: ast.Module) -> tuple[int, int]:
    """Count top-level classes and functions."""
    classes = 0
    functions = 0
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            classes += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions += 1
    return classes, functions


def scan_repository(
    target_dirs: str | list[str],
    excludes: list[str] | None = None,
    skip_external: bool = False,
    skip_ruff: bool = False,
) -> RepoReport:
    """Scan all Python files in one or more directories and produce a graded report.

    Args:
        target_dirs: Root directory (or list of directories) to scan.
        excludes: Glob patterns for files to skip.
        skip_external: If True, skip ruff/radon (faster, AST-only).
        skip_ruff: If True, skip ruff but still run radon.

    Returns:
        A fully graded RepoReport.
    """
    if excludes is None:
        excludes = DEFAULT_EXCLUDES

    # Normalise to list.
    if isinstance(target_dirs, str):
        target_dirs = [target_dirs]

    # Discover files across all target directories.
    # Use common parent as the base for relative paths.
    resolved_dirs = [Path(d).resolve() for d in target_dirs]
    if len(resolved_dirs) == 1:
        base_dir = resolved_dirs[0]
    else:
        # Find common parent of all target directories.
        parts = [d.parts for d in resolved_dirs]
        common = []
        for level in zip(*parts):
            if len(set(level)) == 1:
                common.append(level[0])
            else:
                break
        base_dir = Path(*common) if common else Path("/")

    py_files: list[tuple[Path, Path]] = []  # (absolute, base_dir_for_rel)
    for target in resolved_dirs:
        for f in _discover_python_files(target, excludes):
            py_files.append((f, base_dir))

    # Parse all files.
    file_trees: dict[str, ast.Module] = {}
    file_sources: dict[str, str] = {}
    parse_errors: dict[str, str] = {}

    for pyfile, base in py_files:
        rel = str(pyfile.relative_to(base))
        try:
            source = pyfile.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=rel)
            file_trees[rel] = tree
            file_sources[rel] = source
        except SyntaxError as exc:
            parse_errors[rel] = str(exc)

    # Instantiate all per-file detectors.
    detectors = [cls() for cls in ALL_DETECTORS]

    # Run per-file detectors.
    file_smells: dict[str, list[SmellInstance]] = {rel: [] for rel in file_trees}
    for rel, tree in file_trees.items():
        source = file_sources[rel]
        for detector in detectors:
            file_smells[rel].extend(detector.detect(tree, source, rel))

    # Run cross-file duplicate detector.
    dup_smells = DuplicateCodeDetector.detect_repo(file_trees)
    for smell in dup_smells:
        if smell.file in file_smells:
            file_smells[smell.file].append(smell)

    # Run external tools (ruff + radon).
    external_smells: list[SmellInstance] = []
    external_metrics: dict[str, FileMetrics] = {}
    if not skip_external:
        for target in resolved_dirs:
            dir_smells, dir_metrics = collect_external_metrics(str(target))
            external_smells.extend(dir_smells)
            external_metrics.update(dir_metrics)

    # Bucket external smells into the correct file.
    for smell in external_smells:
        # External tools use absolute paths — relativise if possible.
        rel = smell.file
        try:
            rel = str(Path(smell.file).relative_to(base_dir))
        except ValueError:
            pass
        if rel in file_smells:
            # Skip ruff violations if requested.
            if skip_ruff and smell.smell_type == SmellType.LINT_VIOLATION:
                continue
            file_smells[rel].append(smell)

    # Build file reports.
    file_reports: list[FileReport] = []
    for rel in sorted(file_trees):
        source = file_sources[rel]
        tree = file_trees[rel]
        classes, functions = _count_classes_and_functions(tree)

        # Get or create metrics.
        abs_path = str(base_dir / rel)
        metrics = external_metrics.get(abs_path, FileMetrics())
        # Also try relative path key.
        if abs_path not in external_metrics and rel in external_metrics:
            metrics = external_metrics[rel]

        metrics.lines_of_code = _count_lines(source)
        metrics.num_classes = classes
        metrics.num_functions = functions

        file_reports.append(
            FileReport(
                path=rel,
                smells=file_smells.get(rel, []),
                metrics=metrics,
            ),
        )

    # Assemble and grade the repo report.
    report = RepoReport(
        target_dir=str(base_dir),
        files=file_reports,
    )
    grade_repo(report)
    return report
