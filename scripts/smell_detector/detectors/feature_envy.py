"""Detect Feature Envy.

Feature Envy occurs when a method in class A accesses attributes or
methods of object B more than its own (self).  This suggests the method
belongs on B rather than A.

Heuristic:
  For each method in a class, count attribute accesses:
    - ``self.x`` → self_count
    - ``obj.x`` where obj ≠ self → other_counts[obj]
  If any single other_counts[obj] > self_count and other_counts[obj] >= 3,
  flag it.
"""

from __future__ import annotations

import ast

from scripts.smell_detector.detectors.base import SmellDetector
from scripts.smell_detector.models import SmellInstance, SmellSeverity, SmellType

MIN_OTHER_ACCESSES = 3


class _AttributeCounter(ast.NodeVisitor):
    """Counts ``obj.attr`` accesses grouped by ``obj`` name."""

    def __init__(self) -> None:
        self.self_count: int = 0
        self.other_counts: dict[str, int] = {}

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if isinstance(node.value, ast.Name):
            name = node.value.id
            if name == "self":
                self.self_count += 1
            else:
                self.other_counts[name] = self.other_counts.get(name, 0) + 1
        self.generic_visit(node)


class FeatureEnvyDetector(SmellDetector):
    """Flags methods that access another object's attributes more than their own."""

    @property
    def name(self) -> str:
        return "Feature Envy"

    def detect(
        self,
        tree: ast.Module,
        source: str,
        filepath: str,
    ) -> list[SmellInstance]:
        smells: list[SmellInstance] = []

        for class_node in ast.walk(tree):
            if not isinstance(class_node, ast.ClassDef):
                continue

            for method_node in class_node.body:
                if not isinstance(method_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                counter = _AttributeCounter()
                counter.visit(method_node)

                for obj_name, count in counter.other_counts.items():
                    if count > counter.self_count and count >= MIN_OTHER_ACCESSES:
                        severity = (
                            SmellSeverity.HIGH
                            if count >= 10
                            else SmellSeverity.MEDIUM
                            if count >= 5
                            else SmellSeverity.LOW
                        )
                        smells.append(
                            SmellInstance(
                                file=filepath,
                                line=method_node.lineno,
                                end_line=method_node.end_lineno or method_node.lineno,
                                smell_type=SmellType.FEATURE_ENVY,
                                severity=severity,
                                message=(
                                    f"Method '{class_node.name}.{method_node.name}' "
                                    f"accesses '{obj_name}' {count} times but "
                                    f"'self' only {counter.self_count} times"
                                ),
                                suggested_refactoring=(
                                    f"Move Method — consider moving "
                                    f"'{method_node.name}' to the class that "
                                    f"owns '{obj_name}'."
                                ),
                                symbol_name=f"{class_node.name}.{method_node.name}",
                            ),
                        )

        return smells
