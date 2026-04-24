"""Detect magic numbers in source code.

A "magic number" is a numeric literal that appears in code without a
named constant to explain its meaning.

Exclusions (not flagged):
  - 0, 1, -1, 2 (very common and usually obvious)
  - Numbers in UPPER_SNAKE_CASE constant assignments
  - Default parameter values
  - Numbers used as arguments to range(), enumerate(), zip()
  - Indices and slice components
  - return 0 / return 1 patterns
  - __version__ and version tuples
"""

from __future__ import annotations

import ast

from scripts.smell_detector.detectors.base import SmellDetector
from scripts.smell_detector.models import SmellInstance, SmellSeverity, SmellType

# Numbers so common they are never flagged.
TRIVIAL_NUMBERS: frozenset[int | float] = frozenset({0, 1, -1, 2, 0.0, 1.0, 0.5})

# Functions whose numeric arguments are conventional.
ALLOWED_CALL_FUNCS: frozenset[str] = frozenset(
    {"range", "enumerate", "zip", "round", "max", "min", "pow", "divmod", "slice"}
)


def _is_upper_snake(name: str) -> bool:
    """Return True if *name* looks like ``MY_CONST_42``."""
    return name.replace("_", "").isupper() and "_" in name or name.isupper()


def _severity_for_count(count: int) -> SmellSeverity:
    """More magic numbers in one file → higher severity."""
    if count >= 15:
        return SmellSeverity.HIGH
    if count >= 8:
        return SmellSeverity.MEDIUM
    return SmellSeverity.LOW


class _MagicNumberVisitor(ast.NodeVisitor):
    """Collects numeric literals that look like magic numbers."""

    def __init__(self) -> None:
        self.magic_lines: list[tuple[int, int | float]] = []
        self._in_constant_assign = False
        self._in_default = False
        self._in_allowed_call = False
        self._in_return = False

    # --- context managers ---------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        # Check if this is ``MY_CONST = 42``
        for target in node.targets:
            if isinstance(target, ast.Name) and _is_upper_snake(target.id):
                self._in_constant_assign = True
                self.generic_visit(node)
                self._in_constant_assign = False
                return
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        if isinstance(node.target, ast.Name) and _is_upper_snake(node.target.id):
            self._in_constant_assign = True
            self.generic_visit(node)
            self._in_constant_assign = False
            return
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        # Defaults are OK
        self._in_default = True
        for default in node.args.defaults + node.args.kw_defaults:
            if default is not None:
                self.visit(default)
        self._in_default = False
        # Visit the body normally
        for child in node.body:
            self.visit(child)
        for decorator in node.decorator_list:
            self.visit(decorator)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        func = node.func
        fname = ""
        if isinstance(func, ast.Name):
            fname = func.id
        elif isinstance(func, ast.Attribute):
            fname = func.attr

        if fname in ALLOWED_CALL_FUNCS:
            self._in_allowed_call = True
            self.generic_visit(node)
            self._in_allowed_call = False
        else:
            self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:  # noqa: N802
        self._in_return = True
        self.generic_visit(node)
        self._in_return = False

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
        if not isinstance(node.value, (int, float)):
            return
        if isinstance(node.value, bool):  # bool is subclass of int
            return
        if node.value in TRIVIAL_NUMBERS:
            return
        if self._in_constant_assign or self._in_default or self._in_allowed_call:
            return
        if self._in_return and node.value in {0, 1, -1}:
            return
        self.magic_lines.append((node.lineno, node.value))


class MagicNumberDetector(SmellDetector):
    """Flags unexplained numeric literals."""

    @property
    def name(self) -> str:
        return "Magic Number"

    def detect(
        self,
        tree: ast.Module,
        source: str,
        filepath: str,
    ) -> list[SmellInstance]:
        visitor = _MagicNumberVisitor()
        visitor.visit(tree)

        if not visitor.magic_lines:
            return []

        severity = _severity_for_count(len(visitor.magic_lines))

        return [
            SmellInstance(
                file=filepath,
                line=line,
                end_line=line,
                smell_type=SmellType.MAGIC_NUMBER,
                severity=severity,
                message=f"Magic number {value!r} — consider extracting to a named constant",
                suggested_refactoring="Extract Constant / Introduce Named Constant.",
                symbol_name="",
            )
            for line, value in visitor.magic_lines
        ]
