"""Tests for MLB advanced feature engineering helpers."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from plugins.mlb_modeling.features import (
    MLBFeatureRepository,
    RelieverAppearance,
    build_advanced_feature_payload,
    calculate_bullpen_fatigue,
    recency_weighted_average,
    stable_feature_hash,
)
from plugins.mlb_modeling.public_sources import AvailabilityStatus
from tests.contracts.helpers import validate_contract_payload
from tests.contracts.fixtures.mlb_predictive_modeling_samples import (
    build_mlb_advanced_features_payload,
)


SCHEMAS_ROOT = Path(__file__).resolve().parent / "contracts" / "schemas"


class _FakeDb:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, sql: str, params: dict) -> None:
        self.calls.append((sql, params))


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


def test_bullpen_fatigue_applies_15_and_20_pitch_thresholds() -> None:
    summary = calculate_bullpen_fatigue(
        [
            RelieverAppearance("p1", date(2026, 5, 9), 16),
            RelieverAppearance("p2", date(2026, 5, 8), 21),
            RelieverAppearance("p3", date(2026, 5, 5), 12),
        ],
        as_of_date=date(2026, 5, 10),
    )

    assert summary.pitches_last_3_days == 37
    assert summary.pitches_last_5_days == 49
    assert summary.relievers_over_15_pitches == 2
    assert summary.relievers_over_20_pitches == 1
    assert summary.velocity_penalty == pytest.approx(-0.2)


def test_bullpen_fatigue_includes_velocity_drop_penalty() -> None:
    summary = calculate_bullpen_fatigue(
        [
            RelieverAppearance(
                "p1",
                date(2026, 5, 9),
                22,
                avg_velocity=93.0,
                baseline_velocity=95.0,
            )
        ],
        as_of_date=date(2026, 5, 10),
    )

    assert summary.velocity_penalty == pytest.approx(-0.25)


def test_recency_weighted_average_emphasizes_recent_observations() -> None:
    weighted = recency_weighted_average([(1.0, 0), (0.0, 30)], half_life_days=10)

    assert weighted is not None
    assert weighted > 0.85


def test_stable_feature_hash_is_order_independent() -> None:
    assert stable_feature_hash({"b": 2, "a": 1}) == stable_feature_hash(
        {"a": 1, "b": 2}
    )


def test_build_advanced_feature_payload_matches_contract() -> None:
    sample = build_mlb_advanced_features_payload()
    payload = build_advanced_feature_payload(
        game_id=sample["game_id"],
        home_team=sample["home_team"],
        away_team=sample["away_team"],
        as_of_ts=datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc),
        sabermetrics=sample["sabermetrics"],
        plate_discipline=sample["plate_discipline"],
        matchup_dynamics=sample["matchup_dynamics"],
        home_bullpen=calculate_bullpen_fatigue(
            [RelieverAppearance("h1", date(2026, 5, 9), 16)],
            as_of_date=date(2026, 5, 10),
        ),
        away_bullpen=calculate_bullpen_fatigue(
            [RelieverAppearance("a1", date(2026, 5, 8), 21)],
            as_of_date=date(2026, 5, 10),
        ),
        recency=sample["recency"],
        feature_availability={
            "woba": AvailabilityStatus.AVAILABLE,
            "catcher_framing": AvailabilityStatus.UNAVAILABLE,
        },
    )

    validate_contract_payload(payload, _load_schema("mlb_advanced_features_v1.json"))
    assert payload["feature_hash"] != "pending"


def test_feature_repository_upserts_matchup_payload() -> None:
    db = _FakeDb()
    payload = build_mlb_advanced_features_payload()
    repo = MLBFeatureRepository(db)

    repo.upsert_matchup_features(payload, side="home")

    assert db.calls
    sql, params = db.calls[0]
    assert "INSERT INTO mlb_matchup_features" in sql
    assert params["game_id"] == payload["game_id"]
    assert params["side"] == "home"
    assert params["feature_hash"] == payload["feature_hash"]
