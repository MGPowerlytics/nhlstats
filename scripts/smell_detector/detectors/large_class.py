"""Detect classes that are too large.

Thresholds:
  Lines: 300–500 LOW, 500–800 MEDIUM, 800+ HIGH
  Methods: 20–30 LOW, 30–50 MEDIUM, 50+ HIGH
"""

from __future__ import annotations

import ast

from scripts.smell_detector.detectors.base import SmellDetector
from scripts.smell_detector.models import SmellInstance, SmellSeverity, SmellType

LINE_THRESHOLD_LOW = 300
LINE_THRESHOLD_MEDIUM = 500
LINE_THRESHOLD_HIGH = 800

METHOD_THRESHOLD_LOW = 20
METHOD_THRESHOLD_MEDIUM = 30
METHOD_THRESHOLD_HIGH = 50


def _class_line_count(node: ast.ClassDef) -> int:
    """Total lines spanned by the class definition."""
    end = node.end_lineno or node.lineno
    return max(0, end - node.lineno + 1)


def _method_count(node: ast.ClassDef) -> int:
    """Count direct methods (not nested classes/functions inside methods)."""
    return sum(
        1
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _line_severity(lines: int) -> SmellSeverity:
    if lines >= LINE_THRESHOLD_HIGH:
        return SmellSeverity.HIGH
    if lines >= LINE_THRESHOLD_MEDIUM:
        return SmellSeverity.MEDIUM
    return SmellSeverity.LOW


def _method_severity(count: int) -> SmellSeverity:
    if count >= METHOD_THRESHOLD_HIGH:
        return SmellSeverity.HIGH
    if count >= METHOD_THRESHOLD_MEDIUM:
        return SmellSeverity.MEDIUM
    return SmellSeverity.LOW


class LargeClassDetector(SmellDetector):
    """Flags classes exceeding line or method count thresholds."""

    @property
    def name(self) -> str:
        return "Large Class"

    def detect(
        self,
        tree: ast.Module,
        source: str,
        filepath: str,
    ) -> list[SmellInstance]:
        smells: list[SmellInstance] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            lines = _class_line_count(node)
            methods = _method_count(node)

            if lines >= LINE_THRESHOLD_LOW:
                smells.append(
                    SmellInstance(
                        file=filepath,
                        line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        smell_type=SmellType.LARGE_CLASS,
                        severity=_line_severity(lines),
                        message=(
                            f"Class '{node.name}' spans {lines} lines "
                            f"(threshold: {LINE_THRESHOLD_LOW})"
                        ),
                        suggested_refactoring=(
                            "Extract Class — split into smaller, cohesive classes "
                            "with single responsibilities."
                        ),
                        symbol_name=node.name,
                    ),
                )

            if methods >= METHOD_THRESHOLD_LOW:
                smells.append(
                    SmellInstance(
                        file=filepath,
                        line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        smell_type=SmellType.LARGE_CLASS,
                        severity=_method_severity(methods),
                        message=(
                            f"Class '{node.name}' has {methods} methods "
                            f"(threshold: {METHOD_THRESHOLD_LOW})"
                        ),
                        suggested_refactoring=(
                            "Split Class — group related methods into smaller "
                            "collaborating classes."
                        ),
                        symbol_name=node.name,
                    ),
                )

        return smells
