"""Tests for public-source MLB modeling adapters."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tests.contracts.helpers import validate_contract_payload

from plugins.mlb_modeling.public_sources import (
    AvailabilityStatus,
    MLBEnvironmentFeatureBuilder,
    MLBMarketSignalBuilder,
    MLBTravelFatigueBuilder,
    UnavailablePublicSignalAdapter,
)


SCHEMAS_ROOT = Path(__file__).resolve().parent / "contracts" / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


def test_temperature_hit_distance_adjustment_uses_requested_transform() -> None:
    """Every 10°F above baseline adds 4.5 feet."""
    assert MLBEnvironmentFeatureBuilder.temperature_hit_distance_adjustment(70) == 4.5
    assert MLBEnvironmentFeatureBuilder.temperature_hit_distance_adjustment(50) == -4.5
    assert (
        MLBEnvironmentFeatureBuilder.temperature_hit_distance_adjustment(None) is None
    )


def test_environment_builder_emits_contract_payload() -> None:
    payload = MLBEnvironmentFeatureBuilder.build_payload(
        game_id="745431",
        game_date="2026-05-10",
        venue="Yankee Stadium",
        park_factors={
            "runs": 1.03,
            "home_runs": 1.12,
            "doubles_triples": 0.97,
            "singles": 1.01,
        },
        weather={
            "temperature_f": 70.0,
            "humidity_pct": 55.0,
            "wind_speed_mph": 7.0,
            "wind_direction_degrees": 225.0,
            "altitude_ft": 54.0,
        },
        source="public_weather",
        observed_at=datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc),
    )

    validate_contract_payload(payload, _load_schema("mlb_environment_features_v1.json"))
    assert payload["hit_distance_adjustment_ft"] == 4.5


def test_unavailable_adapter_marks_proprietary_signal_without_defaulting() -> None:
    adapter = UnavailablePublicSignalAdapter(
        signal_name="ticket_money_percentages",
        reason="No public/free source is configured.",
        abstain_required=True,
    )

    snapshot = adapter.fetch()

    assert snapshot.status == AvailabilityStatus.ABSTAIN_REQUIRED
    assert snapshot.abstain_required is True
    assert snapshot.payload == {"ticket_money_percentages": None}


def test_travel_builder_applies_west_to_east_penalty_and_contract() -> None:
    payload = MLBTravelFatigueBuilder.build_payload(
        game_id="745431",
        team="Los Angeles Dodgers",
        is_home=False,
        time_zones_crossed=3,
        travel_direction="east",
        circadian_advantage_hours=-3.0,
        days_rest=0,
        local_start_time="13:05:00",
    )

    validate_contract_payload(payload, _load_schema("mlb_travel_fatigue_v1.json"))
    assert payload["west_to_east_penalty"] == -0.045
    assert MLBTravelFatigueBuilder.circadian_advantage_win_expectation(3.0) == 0.606


def test_market_signal_builder_computes_pro_edge_and_reverse_line_movement() -> None:
    payload = MLBMarketSignalBuilder.build_payload(
        game_id="745431",
        ticker="KXMLBGAME-26MAY10NYYBOS-NYY",
        outcome_name="home",
        snapshot_at=datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc),
        market_prob=0.54,
        source="public_market",
        ticket_pct=0.35,
        money_pct=0.61,
        line_move=0.02,
        public_side="away",
    )

    validate_contract_payload(payload, _load_schema("mlb_market_signals_v1.json"))
    assert payload["pro_edge"] == 0.26
    assert payload["reverse_line_movement"] is True
    assert payload["availability"] == "available"


def test_market_signal_builder_allows_unavailable_ticket_money_contract() -> None:
    payload = MLBMarketSignalBuilder.build_payload(
        game_id="745431",
        ticker="KXMLBGAME-26MAY10NYYBOS-NYY",
        outcome_name="home",
        snapshot_at=datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc),
        market_prob=0.54,
        source="kalshi_public_market",
        ticket_pct=None,
        money_pct=None,
        line_move=0.01,
        public_side=None,
    )

    validate_contract_payload(payload, _load_schema("mlb_market_signals_v1.json"))
    assert payload["pro_edge"] is None
    assert payload["availability"] == "unavailable"
