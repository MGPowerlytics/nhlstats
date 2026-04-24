"""CLI entry point: python -m scripts.smell_detector <target_dir>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.smell_detector.formatter import format_json, format_markdown
from scripts.smell_detector.scanner import scan_repository


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smell_detector",
        description=(
            "XP Code Smell Detector — scans Python files for common code smells "
            "and outputs a graded Markdown report."
        ),
    )
    parser.add_argument(
        "target_dirs",
        nargs="+",
        help="One or more directories to scan for Python files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help=(
            "Output file path. If omitted, writes to stdout. "
            "Example: .agent_tasks/auto-improve/smell-report.md"
        ),
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format (default: md).",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        action="append",
        default=None,
        help=(
            "Glob pattern to exclude. Can be specified multiple times. "
            "Defaults: tests/*, *_test.py, test_*.py, conftest.py"
        ),
    )
    parser.add_argument(
        "--skip-external",
        action="store_true",
        help="Skip ruff and radon (AST-only, faster).",
    )
    parser.add_argument(
        "--skip-ruff",
        action="store_true",
        help="Skip ruff but still run radon.",
    )
    parser.add_argument(
        "--min-grade",
        choices=["A", "B", "C", "D", "F"],
        default=None,
        help="Only include files with this grade or worse.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the smell detector and write the report."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    for d in args.target_dirs:
        if not Path(d).is_dir():
            print(f"Error: '{d}' is not a directory.", file=sys.stderr)
            return 1

    # Scan and grade.
    report = scan_repository(
        target_dirs=args.target_dirs,
        excludes=args.exclude,  # None → use defaults
        skip_external=args.skip_external,
        skip_ruff=args.skip_ruff,
    )

    # Filter by grade if requested.
    if args.min_grade:
        grade_order = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4}
        threshold = grade_order.get(args.min_grade, 0)
        report.files = [
            fr for fr in report.files if grade_order.get(fr.grade, 4) <= threshold
        ]

    # Format output.
    if args.format == "json":
        output = format_json(report)
    else:
        output = format_markdown(report)

    # Write output.
    if args.output:
        outpath = Path(args.output)
        outpath.parent.mkdir(parents=True, exist_ok=True)
        outpath.write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
