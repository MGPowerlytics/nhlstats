"""Detect duplicate and near-duplicate functions.

Strategy:
  1. Normalise each function's AST: strip names, docstrings, string literals.
  2. Serialise the normalised tree to a canonical string and hash it.
  3. Identical hashes → exact duplicate.
  4. Near-duplicate: compare node-type sequences using a simple similarity
     ratio (shared bigrams).  Threshold ≥ 0.85 with ≥ 10 nodes.

This detector is a *cross-file* detector so it receives all trees at once
via the ``detect_repo`` class method.  The per-file ``detect`` returns an
empty list — the scanner should call ``detect_repo`` separately.
"""

from __future__ import annotations

import ast
import hashlib
from collections import defaultdict

from scripts.smell_detector.detectors.base import SmellDetector
from scripts.smell_detector.models import SmellInstance, SmellSeverity, SmellType

NEAR_DUPLICATE_THRESHOLD = 0.92
MIN_NODES_FOR_COMPARISON = 20


# ---------------------------------------------------------------------------
# AST normalisation helpers
# ---------------------------------------------------------------------------


def _normalise_tree(node: ast.AST) -> ast.AST:
    """Return a deep-copied tree with names and literals blanked out."""
    import copy

    tree = copy.deepcopy(node)
    for child in ast.walk(tree):
        # Blank out all Name ids.
        if isinstance(child, ast.Name):
            child.id = "_"
        # Blank out function/class names.
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            child.name = "_"
        # Blank out string constants (but keep numeric ones for structure).
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            child.value = ""
        # Blank out argument names.
        if isinstance(child, ast.arg):
            child.arg = "_"
        # Strip line numbers to avoid hash differences from location.
        for attr in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
            if hasattr(child, attr):
                setattr(child, attr, 0)
    return tree


def _ast_hash(node: ast.AST) -> str:
    """Hash the normalised AST dump."""
    normalised = _normalise_tree(node)
    dump = ast.dump(normalised, annotate_fields=False)
    return hashlib.sha256(dump.encode()).hexdigest()[:16]


def _node_type_sequence(node: ast.AST) -> list[str]:
    """Flat list of node type names in walk order."""
    return [type(n).__name__ for n in ast.walk(node)]


def _bigram_similarity(seq_a: list[str], seq_b: list[str]) -> float:
    """Jaccard similarity of bigram sets."""
    if len(seq_a) < 2 or len(seq_b) < 2:
        return 0.0
    bigrams_a = {(seq_a[i], seq_a[i + 1]) for i in range(len(seq_a) - 1)}
    bigrams_b = {(seq_b[i], seq_b[i + 1]) for i in range(len(seq_b) - 1)}
    intersection = bigrams_a & bigrams_b
    union = bigrams_a | bigrams_b
    return len(intersection) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class DuplicateCodeDetector(SmellDetector):
    """Detects duplicate and near-duplicate functions across files."""

    @property
    def name(self) -> str:
        return "Duplicate Code"

    def detect(
        self,
        tree: ast.Module,
        source: str,
        filepath: str,
    ) -> list[SmellInstance]:
        # Per-file detection returns nothing — use detect_repo for cross-file.
        return []

    @staticmethod
    def detect_repo(
        file_trees: dict[str, ast.Module],
    ) -> list[SmellInstance]:
        """Cross-file duplicate detection.

        Args:
            file_trees: Mapping of filepath → parsed AST for each file.

        Returns:
            SmellInstance list for all duplicates found.
        """
        # Collect all functions: (filepath, node.name, node.lineno, ast_hash, type_seq)
        FuncInfo = tuple[str, str, int, int, str, list[str]]  # noqa: N806
        functions: list[FuncInfo] = []
        hash_groups: dict[str, list[FuncInfo]] = defaultdict(list)

        for filepath, tree in file_trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                type_seq = _node_type_sequence(node)
                if len(type_seq) < MIN_NODES_FOR_COMPARISON:
                    continue  # Too small to be meaningful.
                h = _ast_hash(node)
                info = (
                    filepath,
                    node.name,
                    node.lineno,
                    node.end_lineno or node.lineno,
                    h,
                    type_seq,
                )
                functions.append(info)
                hash_groups[h].append(info)

        smells: list[SmellInstance] = []

        # --- Exact duplicates (same hash) ---
        reported_pairs: set[tuple[str, str]] = set()
        for h, group in hash_groups.items():
            if len(group) < 2:
                continue
            for i, func_a in enumerate(group):
                for func_b in group[i + 1 :]:
                    pair_key = tuple(
                        sorted(
                            [
                                f"{func_a[0]}:{func_a[1]}:{func_a[2]}",
                                f"{func_b[0]}:{func_b[1]}:{func_b[2]}",
                            ]
                        )
                    )
                    if pair_key in reported_pairs:
                        continue
                    reported_pairs.add(pair_key)  # type: ignore[arg-type]
                    smells.append(
                        SmellInstance(
                            file=func_a[0],
                            line=func_a[2],
                            end_line=func_a[3],
                            smell_type=SmellType.DUPLICATE_CODE,
                            severity=SmellSeverity.HIGH,
                            message=(
                                f"Function '{func_a[1]}' is an exact duplicate of "
                                f"'{func_b[1]}' at {func_b[0]}:{func_b[2]}"
                            ),
                            suggested_refactoring=(
                                "Once and Only Once — extract the shared logic "
                                "into a single function and call it from both sites."
                            ),
                            symbol_name=func_a[1],
                        ),
                    )

        # --- Near duplicates (high similarity, different hash) ---
        for i, func_a in enumerate(functions):
            for func_b in functions[i + 1 :]:
                if func_a[4] == func_b[4]:
                    continue  # Already reported as exact.
                # Only compare functions of similar size (within 2x).
                len_a, len_b = len(func_a[5]), len(func_b[5])
                if max(len_a, len_b) > 2 * min(len_a, len_b):
                    continue
                sim = _bigram_similarity(func_a[5], func_b[5])
                if sim >= NEAR_DUPLICATE_THRESHOLD:
                    pair_key = tuple(
                        sorted(
                            [
                                f"{func_a[0]}:{func_a[1]}:{func_a[2]}",
                                f"{func_b[0]}:{func_b[1]}:{func_b[2]}",
                            ]
                        )
                    )
                    if pair_key in reported_pairs:
                        continue
                    reported_pairs.add(pair_key)  # type: ignore[arg-type]
                    smells.append(
                        SmellInstance(
                            file=func_a[0],
                            line=func_a[2],
                            end_line=func_a[3],
                            smell_type=SmellType.DUPLICATE_CODE,
                            severity=SmellSeverity.MEDIUM,
                            message=(
                                f"Function '{func_a[1]}' is {sim:.0%} similar to "
                                f"'{func_b[1]}' at {func_b[0]}:{func_b[2]}"
                            ),
                            suggested_refactoring=(
                                "Extract Shared Function — identify the common "
                                "logic and parameterise the differences."
                            ),
                            symbol_name=func_a[1],
                        ),
                    )

        return smells
