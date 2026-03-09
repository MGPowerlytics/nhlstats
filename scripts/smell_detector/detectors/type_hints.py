"""Detect missing type annotations on function signatures.

Checks:
  - Missing return type annotation
  - Missing parameter type annotations (excluding ``self`` / ``cls``)

Severity:
  - Fully untyped function → MEDIUM
  - Partially untyped (>50 % params missing) → LOW
  - Missing return only → LOW
"""

from __future__ import annotations

import ast

from scripts.smell_detector.detectors.base import SmellDetector
from scripts.smell_detector.models import SmellInstance, SmellSeverity, SmellType

SELF_CLS: frozenset[str] = frozenset({"self", "cls"})


def _check_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    filepath: str,
    is_method: bool,
) -> list[SmellInstance]:
    smells: list[SmellInstance] = []
    args = node.args

    # Gather all parameter names and their annotations.
    all_params: list[tuple[str, ast.expr | None]] = []
    for arg in args.args + args.posonlyargs + args.kwonlyargs:
        all_params.append((arg.arg, arg.annotation))
    if args.vararg:
        all_params.append((args.vararg.arg, args.vararg.annotation))
    if args.kwarg:
        all_params.append((args.kwarg.arg, args.kwarg.annotation))

    # Filter out self/cls for methods.
    check_params = [
        (name, ann) for name, ann in all_params if not (is_method and name in SELF_CLS)
    ]

    missing_params = [(name, ann) for name, ann in check_params if ann is None]
    missing_return = node.returns is None

    total = len(check_params)
    missing_count = len(missing_params)

    if missing_count == 0 and not missing_return:
        return smells  # Fully annotated.

    # Determine severity.
    if total > 0 and missing_count == total and missing_return:
        severity = SmellSeverity.MEDIUM
        detail = "fully untyped"
    elif total > 0 and missing_count / total > 0.5:
        severity = SmellSeverity.LOW
        detail = f"{missing_count}/{total} params untyped"
    elif missing_return and missing_count == 0:
        severity = SmellSeverity.LOW
        detail = "missing return type"
    else:
        severity = SmellSeverity.LOW
        parts: list[str] = []
        if missing_count:
            parts.append(f"{missing_count}/{total} params untyped")
        if missing_return:
            parts.append("missing return type")
        detail = ", ".join(parts)

    smells.append(
        SmellInstance(
            file=filepath,
            line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            smell_type=SmellType.MISSING_TYPE_HINT,
            severity=severity,
            message=(f"Function '{node.name}' has incomplete type hints: {detail}"),
            suggested_refactoring="Add Type Annotations for all parameters and return type.",
            symbol_name=node.name,
        ),
    )
    return smells


class MissingTypeHintDetector(SmellDetector):
    """Flags functions and methods that lack type annotations."""

    @property
    def name(self) -> str:
        return "Missing Type Hint"

    def detect(
        self,
        tree: ast.Module,
        source: str,
        filepath: str,
    ) -> list[SmellInstance]:
        smells: list[SmellInstance] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        smells.extend(_check_function(child, filepath, is_method=True))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip if this is a method (handled above via ClassDef).
                if not isinstance(getattr(node, "_parent", None), ast.ClassDef):
                    smells.extend(_check_function(node, filepath, is_method=False))

        # Deduplicate: walk may visit methods both from ClassDef and top-level.
        seen: set[tuple[str, int]] = set()
        unique: list[SmellInstance] = []
        for smell in smells:
            key = (smell.symbol_name, smell.line)
            if key not in seen:
                seen.add(key)
                unique.append(smell)
        return unique
