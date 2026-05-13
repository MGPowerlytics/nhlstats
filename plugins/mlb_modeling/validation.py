"""Validation and safety gates for MLB model activation and staking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class MLBValidationGateConfig:
    """Thresholds for MLB model activation and staking gates."""

    max_ece: float = 0.031
    min_clv_hit_rate: float = 0.58
    min_flat_roi: float = 0.021
    min_tier_a_roi: float = 0.061
    max_feature_staleness_hours: float = 6.0
    max_abstention_rate: float = 0.50


@dataclass(frozen=True)
class MLBValidationSnapshot:
    """Latest MLB model and betting health metrics."""

    ece: float
    clv_hit_rate: float
    flat_roi: float
    tier_a_roi: float
    feature_staleness_hours: float
    abstention_rate: float


@dataclass(frozen=True)
class MLBValidationGateResult:
    """Outcome of applying MLB validation gates."""

    passes: bool
    failed_gates: List[str]
    recommendations: List[str]

    @property
    def staking_enabled(self) -> bool:
        """Return True when all gates pass."""
        return self.passes


def evaluate_validation_gates(
    snapshot: MLBValidationSnapshot,
    config: MLBValidationGateConfig | None = None,
) -> MLBValidationGateResult:
    """Evaluate all MLB safety gates and return failures/recommendations."""
    cfg = config or MLBValidationGateConfig()
    failed: list[str] = []
    recommendations: list[str] = []

    if snapshot.ece > cfg.max_ece:
        failed.append("ece")
        recommendations.append("Disable new artifact; recalibrate probabilities.")
    if snapshot.clv_hit_rate < cfg.min_clv_hit_rate:
        failed.append("clv_hit_rate")
        recommendations.append("Reduce stake tier; edge is not beating close.")
    if snapshot.flat_roi < cfg.min_flat_roi:
        failed.append("flat_roi")
        recommendations.append("Re-check edge threshold and market-probability inputs.")
    if snapshot.tier_a_roi < cfg.min_tier_a_roi:
        failed.append("tier_a_roi")
        recommendations.append("Disable Tier A sizing until confidence tier recovers.")
    if snapshot.feature_staleness_hours > cfg.max_feature_staleness_hours:
        failed.append("feature_staleness")
        recommendations.append(
            "Abstain from MLB bets until feature freshness recovers."
        )
    if snapshot.abstention_rate > cfg.max_abstention_rate:
        failed.append("abstention_rate")
        recommendations.append("Investigate unavailable public-source signals.")

    return MLBValidationGateResult(
        passes=not failed,
        failed_gates=failed,
        recommendations=recommendations,
    )


def validation_result_payload(result: MLBValidationGateResult) -> Dict[str, object]:
    """Return a compact serializable validation result."""
    return {
        "passes": result.passes,
        "staking_enabled": result.staking_enabled,
        "failed_gates": list(result.failed_gates),
        "recommendations": list(result.recommendations),
    }
