"""Detector base class and registry."""

from __future__ import annotations

from scripts.smell_detector.detectors.base import SmellDetector
from scripts.smell_detector.detectors.deep_nesting import DeepNestingDetector
from scripts.smell_detector.detectors.duplicates import DuplicateCodeDetector
from scripts.smell_detector.detectors.feature_envy import FeatureEnvyDetector
from scripts.smell_detector.detectors.large_class import LargeClassDetector
from scripts.smell_detector.detectors.long_method import LongMethodDetector
from scripts.smell_detector.detectors.magic_numbers import MagicNumberDetector
from scripts.smell_detector.detectors.primitive_obsession import (
    PrimitiveObsessionDetector,
)
from scripts.smell_detector.detectors.type_hints import MissingTypeHintDetector

ALL_DETECTORS: list[type[SmellDetector]] = [
    LongMethodDetector,
    LargeClassDetector,
    DeepNestingDetector,
    MagicNumberDetector,
    MissingTypeHintDetector,
    DuplicateCodeDetector,
    PrimitiveObsessionDetector,
    FeatureEnvyDetector,
]

__all__ = [
    "ALL_DETECTORS",
    "DeepNestingDetector",
    "DuplicateCodeDetector",
    "FeatureEnvyDetector",
    "LargeClassDetector",
    "LongMethodDetector",
    "MagicNumberDetector",
    "MissingTypeHintDetector",
    "PrimitiveObsessionDetector",
    "SmellDetector",
]
