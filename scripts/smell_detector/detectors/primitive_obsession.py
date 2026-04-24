"""Detect Primitive Obsession.

Primitive Obsession occurs when:
  1. A function has > 3 parameters all typed as primitives
     (str, int, float, bool, bytes, None).
  2. The same group of ≥ 3 primitive parameters appears in ≥ 2 functions
     (suggests they should be an object).
"""

from __future__ import annotations

import ast
from collections import Counter

from scripts.smell_detector.detectors.base import SmellDetector
from scripts.smell_detector.models import SmellInstance, SmellSeverity, SmellType

PRIMITIVE_THRESHOLD = 3

PRIMITIVE_NAMES: frozenset[str] = frozenset(
    {"str", "int", "float", "bool", "bytes", "None", "none"}
)

SELF_CLS: frozenset[str] = frozenset({"self", "cls"})


def _annotation_is_primitive(ann: ast.expr | None) -> bool:
    """Return True if the annotation resolves to a primitive type name."""
    if ann is None:
        return False  # No annotation → not counted as primitive.
    if isinstance(ann, ast.Name):
        return ann.id in PRIMITIVE_NAMES
    if isinstance(ann, ast.Constant):
        return str(ann.value) in PRIMITIVE_NAMES
    # ``str | None`` etc  (BinOp in older Python)
    if isinstance(ann, ast.BinOp):
        return _annotation_is_primitive(ann.left) and _annotation_is_primitive(
            ann.right
        )
    # ``Optional[str]``, ``Union[str, int]`` — Subscript
    if isinstance(ann, ast.Subscript):
        if isinstance(ann.value, ast.Name) and ann.value.id in {
            "Optional",
            "Union",
        }:
            if isinstance(ann.slice, ast.Tuple):
                return all(_annotation_is_primitive(elt) for elt in ann.slice.elts)
            return _annotation_is_primitive(ann.slice)
    return False


def _param_type_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    is_method: bool,
) -> list[tuple[str, str]]:
    """Extract (param_name, type_name) pairs for primitive-typed params."""
    results: list[tuple[str, str]] = []
    for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
        if is_method and arg.arg in SELF_CLS:
            continue
        if arg.annotation and _annotation_is_primitive(arg.annotation):
            type_name = ast.dump(arg.annotation)
            results.append((arg.arg, type_name))
    return results


class PrimitiveObsessionDetector(SmellDetector):
    """Flags functions whose signatures are dominated by primitive types."""

    @property
    def name(self) -> str:
        return "Primitive Obsession"

    def detect(
        self,
        tree: ast.Module,
        source: str,
        filepath: str,
    ) -> list[SmellInstance]:
        smells: list[SmellInstance] = []
        # Also collect parameter groups for cross-function analysis.
        param_groups: list[
            tuple[str, int, frozenset[str]]
        ] = []  # (func_name, line, {type_sigs})

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Determine if this is a method.
            is_method = False
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef):
                    if node in parent.body:
                        is_method = True
                        break

            prim_params = _param_type_signature(node, is_method)
            if len(prim_params) >= PRIMITIVE_THRESHOLD:
                param_names = ", ".join(f"{n}: {t}" for n, t in prim_params)
                severity = (
                    SmellSeverity.HIGH
                    if len(prim_params) >= 6
                    else SmellSeverity.MEDIUM
                    if len(prim_params) >= 4
                    else SmellSeverity.LOW
                )
                smells.append(
                    SmellInstance(
                        file=filepath,
                        line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        smell_type=SmellType.PRIMITIVE_OBSESSION,
                        severity=severity,
                        message=(
                            f"Function '{node.name}' has {len(prim_params)} "
                            f"primitive-typed parameters: {param_names}"
                        ),
                        suggested_refactoring=(
                            "Introduce Parameter Object — group related primitives "
                            "into a dataclass or NamedTuple."
                        ),
                        symbol_name=node.name,
                    ),
                )

            # Track parameter groups for repeated-group detection.
            if len(prim_params) >= PRIMITIVE_THRESHOLD:
                group = frozenset(t for _, t in prim_params)
                param_groups.append((node.name, node.lineno, group))

        # Repeated parameter groups.
        group_counter: Counter[frozenset[str]] = Counter(g for _, _, g in param_groups)
        reported_groups: set[frozenset[str]] = set()
        for func_name, line, group in param_groups:
            if group_counter[group] >= 2 and group not in reported_groups:
                reported_groups.add(group)
                funcs_with_group = [
                    f"'{n}' (line {ln})" for n, ln, g in param_groups if g == group
                ]
                smells.append(
                    SmellInstance(
                        file=filepath,
                        line=line,
                        end_line=line,
                        smell_type=SmellType.PRIMITIVE_OBSESSION,
                        severity=SmellSeverity.HIGH,
                        message=(
                            f"Repeated primitive parameter group appears in: "
                            f"{', '.join(funcs_with_group)}"
                        ),
                        suggested_refactoring=(
                            "Replace Data Value with Object — create a shared "
                            "data structure for this recurring parameter group."
                        ),
                        symbol_name=func_name,
                    ),
                )

        return smells
