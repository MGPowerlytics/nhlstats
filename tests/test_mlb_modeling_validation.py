"""Tests for MLB validation and safety gates."""

from __future__ import annotations

from plugins.mlb_modeling.validation import (
    MLBValidationGateConfig,
    MLBValidationSnapshot,
    evaluate_validation_gates,
    validation_result_payload,
)


def test_validation_gates_pass_at_requested_benchmarks() -> None:
    result = evaluate_validation_gates(
        MLBValidationSnapshot(
            ece=0.031,
            clv_hit_rate=0.58,
            flat_roi=0.021,
            tier_a_roi=0.061,
            feature_staleness_hours=2.0,
            abstention_rate=0.10,
        )
    )

    assert result.passes is True
    assert result.staking_enabled is True
    assert result.failed_gates == []


def test_validation_gates_fail_and_recommend_actions() -> None:
    result = evaluate_validation_gates(
        MLBValidationSnapshot(
            ece=0.05,
            clv_hit_rate=0.40,
            flat_roi=-0.01,
            tier_a_roi=0.02,
            feature_staleness_hours=12.0,
            abstention_rate=0.75,
        ),
        config=MLBValidationGateConfig(max_feature_staleness_hours=6.0),
    )

    assert result.passes is False
    assert set(result.failed_gates) == {
        "ece",
        "clv_hit_rate",
        "flat_roi",
        "tier_a_roi",
        "feature_staleness",
        "abstention_rate",
    }
    assert "Disable new artifact" in result.recommendations[0]


def test_validation_result_payload_is_serializable() -> None:
    result = evaluate_validation_gates(
        MLBValidationSnapshot(
            ece=0.02,
            clv_hit_rate=0.60,
            flat_roi=0.03,
            tier_a_roi=0.07,
            feature_staleness_hours=1.0,
            abstention_rate=0.05,
        )
    )

    payload = validation_result_payload(result)

    assert payload["passes"] is True
    assert payload["staking_enabled"] is True
    assert payload["failed_gates"] == []
