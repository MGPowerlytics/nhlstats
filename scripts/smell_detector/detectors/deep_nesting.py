"""Detect deeply nested control flow.

Tracks nesting depth through If / For / While / With / Try / ExceptHandler.
Thresholds:
  4–5  → LOW
  5–6  → MEDIUM
  6–8  → HIGH
  8+   → CRITICAL
"""

from __future__ import annotations

import ast

from scripts.smell_detector.detectors.base import SmellDetector
from scripts.smell_detector.models import SmellInstance, SmellSeverity, SmellType

NESTING_THRESHOLD = 4

NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ExceptHandler,
)

# Python 3.11+
_EXTRA_NESTING: tuple[type, ...] = ()
if hasattr(ast, "TryStar"):
    _EXTRA_NESTING = (ast.TryStar,)  # type: ignore[attr-defined]


def _severity_for_depth(depth: int) -> SmellSeverity:
    if depth >= 8:
        return SmellSeverity.CRITICAL
    if depth >= 6:
        return SmellSeverity.HIGH
    if depth >= 5:
        return SmellSeverity.MEDIUM
    return SmellSeverity.LOW


class _NestingVisitor(ast.NodeVisitor):
    """Walks the AST tracking nesting depth inside functions."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.smells: list[SmellInstance] = []
        self._current_func: str = "<module>"
        self._depth: int = 0
        self._reported: set[tuple[str, int]] = set()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        old_func = self._current_func
        old_depth = self._depth
        self._current_func = node.name
        self._depth = 0
        self.generic_visit(node)
        self._current_func = old_func
        self._depth = old_depth

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def _visit_nesting_node(self, node: ast.AST) -> None:
        self._depth += 1
        if self._depth >= NESTING_THRESHOLD:
            key = (self._current_func, node.lineno)  # type: ignore[attr-defined]
            if key not in self._reported:
                self._reported.add(key)
                self.smells.append(
                    SmellInstance(
                        file=self.filepath,
                        line=node.lineno,  # type: ignore[attr-defined]
                        end_line=getattr(node, "end_lineno", node.lineno)
                        or node.lineno,  # type: ignore[attr-defined]
                        smell_type=SmellType.DEEP_NESTING,
                        severity=_severity_for_depth(self._depth),
                        message=(
                            f"Nesting depth {self._depth} in '{self._current_func}' "
                            f"(threshold: {NESTING_THRESHOLD})"
                        ),
                        suggested_refactoring=(
                            "Extract Method / Introduce Guard Clause / "
                            "Replace Nested Conditional with Early Return."
                        ),
                        symbol_name=self._current_func,
                    ),
                )
        self.generic_visit(node)
        self._depth -= 1

    # Register for all nesting node types.
    visit_If = _visit_nesting_node
    visit_For = _visit_nesting_node
    visit_AsyncFor = _visit_nesting_node
    visit_While = _visit_nesting_node
    visit_With = _visit_nesting_node
    visit_AsyncWith = _visit_nesting_node
    visit_Try = _visit_nesting_node
    visit_ExceptHandler = _visit_nesting_node


class DeepNestingDetector(SmellDetector):
    """Flags control-flow nesting exceeding 4 levels inside a function."""

    @property
    def name(self) -> str:
        return "Deep Nesting"

    def detect(
        self,
        tree: ast.Module,
        source: str,
        filepath: str,
    ) -> list[SmellInstance]:
        visitor = _NestingVisitor(filepath)
        visitor.visit(tree)
        return visitor.smells
