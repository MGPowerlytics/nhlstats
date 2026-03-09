"""Detect functions and methods that are too long.

Thresholds (body lines, excluding docstring):
  - 30–50  → LOW
  - 50–80  → MEDIUM
  - 80–120 → HIGH
  - 120+   → CRITICAL
"""

from __future__ import annotations

import ast

from scripts.smell_detector.detectors.base import SmellDetector
from scripts.smell_detector.models import SmellInstance, SmellSeverity, SmellType

THRESHOLD_LOW = 30
THRESHOLD_MEDIUM = 50
THRESHOLD_HIGH = 80
THRESHOLD_CRITICAL = 120


def _body_line_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the number of lines in the function body, excluding the docstring."""
    if not node.body:
        return 0
    first = node.body[0]
    # Skip the docstring node if present.
    has_docstring = (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )
    start = (
        first.end_lineno if has_docstring and first.end_lineno else node.body[0].lineno
    )
    last = node.body[-1]
    end = last.end_lineno or last.lineno
    # If body has only the docstring, length is 0.
    if has_docstring and len(node.body) == 1:
        return 0
    if has_docstring:
        start = node.body[1].lineno
    return max(0, end - start + 1)


def _severity_for_length(length: int) -> SmellSeverity:
    if length >= THRESHOLD_CRITICAL:
        return SmellSeverity.CRITICAL
    if length >= THRESHOLD_HIGH:
        return SmellSeverity.HIGH
    if length >= THRESHOLD_MEDIUM:
        return SmellSeverity.MEDIUM
    return SmellSeverity.LOW


class LongMethodDetector(SmellDetector):
    """Flags functions/methods whose body exceeds 30 lines."""

    @property
    def name(self) -> str:
        return "Long Method"

    def detect(
        self,
        tree: ast.Module,
        source: str,
        filepath: str,
    ) -> list[SmellInstance]:
        smells: list[SmellInstance] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            length = _body_line_count(node)
            if length < THRESHOLD_LOW:
                continue
            severity = _severity_for_length(length)
            smells.append(
                SmellInstance(
                    file=filepath,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    smell_type=SmellType.LONG_METHOD,
                    severity=severity,
                    message=f"Function '{node.name}' has {length} lines (threshold: {THRESHOLD_LOW})",
                    suggested_refactoring=(
                        "Extract Method — break this function into smaller, "
                        "intention-revealing helper functions."
                    ),
                    symbol_name=node.name,
                ),
            )
        return smells
