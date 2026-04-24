"""Abstract base class for all code smell detectors."""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod

from scripts.smell_detector.models import SmellInstance


class SmellDetector(ABC):
    """Base class for AST-based code smell detectors.

    Each detector walks an AST and returns a list of SmellInstance objects
    describing the smells found.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this detector."""

    @abstractmethod
    def detect(
        self,
        tree: ast.Module,
        source: str,
        filepath: str,
    ) -> list[SmellInstance]:
        """Analyse *tree* and return any smells found.

        Args:
            tree: The parsed AST of the file.
            source: The raw source text (for line-based analysis).
            filepath: Relative path to the file being scanned.

        Returns:
            A list of SmellInstance objects.
        """
