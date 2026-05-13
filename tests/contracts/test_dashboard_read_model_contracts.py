"""Canonical dashboard read-model contract tests.

The dashboard ``dashboard_*_v1`` PostgreSQL read models are governed by JSON
Schemas in ``tests/contracts/schemas``.  Legacy files under
``dashboard/contracts`` are not the canonical dashboard read-model contracts.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError


SCHEMAS_DIR = Path(__file__).parent / "schemas"

DASHBOARD_SCHEMA_NAMES = (
    "dashboard_portfolio_v1",
    "dashboard_live_markets_v1",
    "dashboard_rankings_v1",
    "dashboard_calibration_v1",
    "dashboard_data_quality_v1",
    "dashboard_bet_detail_v1",
    "dashboard_tennis_predictions_v1",
    "dashboard_tennis_model_health_v1",
    "dashboard_mlb_model_health_v1",
    "dashboard_empty_state_v1",
)


def _load_schema(name: str) -> dict[str, Any]:
    """Load a canonical dashboard read-model schema by contract name."""
    return json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def _validate(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate a payload against a Draft 2020-12 JSON Schema."""
    Draft202012Validator(schema).validate(payload)


def _object_schema_nodes(schema: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield every object schema node so strictness can be enforced recursively."""
    if schema.get("type") == "object":
        yield schema

    for value in schema.get("properties", {}).values():
        if isinstance(value, dict):
            yield from _object_schema_nodes(value)

    for value in schema.get("$defs", {}).values():
        if isinstance(value, dict):
            yield from _object_schema_nodes(value)


@pytest.fixture(scope="module")
def dashboard_schemas() -> dict[str, dict[str, Any]]:
    """Load all canonical dashboard read-model schemas."""
    return {name: _load_schema(name) for name in DASHBOARD_SCHEMA_NAMES}


@pytest.fixture
def valid_dashboard_payloads() -> dict[str, dict[str, Any]]:
    """Return valid examples for each dashboard read-model contract."""
    return {
        "dashboard_portfolio_v1": {
            "snapshot_hour_utc": "2026-05-03T14:00:00Z",
            "balance_dollars": 1250.25,
            "portfolio_value_dollars": 1475.75,
            "cumulative_deposits_dollars": 1000.0,
            "realized_profit_dollars": 75.5,
            "open_risk_dollars": 150.0,
            "settled_bet_count": 12,
            "open_bet_count": 3,
            "roi": 0.0755,
            "created_at_utc": "2026-05-03T14:01:00Z",
        },
        "dashboard_live_markets_v1": {
            "market_external_id": "odds-api-nhl-001",
            "game_date": "2026-05-03",
            "commence_time": "2026-05-03T23:00:00Z",
            "home_team_name": "New York Rangers",
            "away_team_name": "Boston Bruins",
            "bookmaker": "Kalshi",
            "market_name": "Moneyline",
            "outcome_name": "New York Rangers",
            "price": 0.57,
            "last_update": "2026-05-03T13:55:00Z",
            "recommendation_bet_id": "NHL-2026-05-03-NYR-BOS-home",
            "edge": 0.08,
            "expected_value": 0.14,
            "confidence": "MEDIUM",
            "ticker": "KXNHL-26MAY03NYRBOS-NYR",
        },
        "dashboard_rankings_v1": {
            "sport": "NHL",
            "entity_type": "team",
            "entity_id": "NYR",
            "entity_name": "New York Rangers",
            "rating": 1582.4,
            "rank": 1,
            "games_played": 82,
            "valid_from": "2026-04-20T00:00:00Z",
            "valid_to": None,
            "created_at": "2026-04-20T00:05:00Z",
        },
        "dashboard_calibration_v1": {
            "bucket_start": 0.5,
            "bucket_end": 0.6,
            "prediction_count": 24,
            "avg_elo_prob": 0.55,
            "avg_market_prob": 0.52,
            "observed_win_rate": 0.58,
            "avg_edge": 0.03,
            "avg_expected_value": 0.07,
            "settled_count": 20,
            "unsettled_count": 4,
        },
        "dashboard_data_quality_v1": {
            "check_name": "dashboard_rankings_v1_exists",
            "relation_name": "dashboard_rankings_v1",
            "relation_type": "view",
            "status": "pass",
            "row_count": 32,
            "freshness_timestamp": "2026-05-03T13:50:00Z",
            "max_allowed_lag_minutes": 120,
            "actual_lag_minutes": 10,
            "message": "Dashboard rankings view is fresh.",
            "checked_at_utc": "2026-05-03T14:00:00Z",
        },
        "dashboard_bet_detail_v1": {
            "bet_id": "NHL-2026-05-03-NYR-BOS-home",
            "recommendation_date": "2026-05-03",
            "placed_time_utc": "2026-05-03T14:15:00Z",
            "home_team": "New York Rangers",
            "away_team": "Boston Bruins",
            "bet_on": "New York Rangers",
            "ticker": "KXNHL-26MAY03NYRBOS-NYR",
            "elo_prob": 0.62,
            "market_prob": 0.54,
            "edge": 0.08,
            "expected_value": 0.14,
            "kelly_fraction": 0.11,
            "confidence": "HIGH",
            "yes_ask": 54,
            "no_ask": 46,
            "status": "open",
            "cost_dollars": 10.0,
            "payout_dollars": 18.5,
            "profit_dollars": 8.5,
            "created_at": "2026-05-03T14:00:00Z",
        },
        "dashboard_tennis_predictions_v1": {
            "bet_id": "TENNIS_2026-05-04_KXATPMATCH-26MAY04ALPBRA-ALP_home",
            "sport": "TENNIS",
            "recommendation_date": "2026-05-04",
            "commence_time": "2026-05-04T16:00:00Z",
            "home_team": "Alpha A.",
            "away_team": "Bravo B.",
            "bet_on": "Alpha A.",
            "ticker": "KXATPMATCH-26MAY04ALPBRA-ALP",
            "model_prob": 0.64,
            "market_prob": 0.56,
            "edge": 0.08,
            "expected_value": 0.1429,
            "kelly_fraction": 0.18,
            "confidence": "HIGH",
            "yes_ask": 56,
            "no_ask": 44,
            "created_at": "2026-05-03T14:00:00Z",
        },
        "dashboard_tennis_model_health_v1": {
            "run_date": "2026-05-11",
            "model_version": "tennis_probability_model_v2",
            "data_source": "postgres_tennis_games",
            "rows": 960,
            "holdout_rows": 192,
            "betmgm_holdout_rows": 144,
            "enabled": True,
            "beats_betmgm": True,
            "baseline_log_loss": 0.6221,
            "ensemble_log_loss": 0.5982,
            "ensemble_market_log_loss": 0.6034,
            "betmgm_log_loss": 0.6178,
            "baseline_brier": 0.2174,
            "ensemble_brier": 0.2091,
            "ensemble_market_brier": 0.2108,
            "betmgm_brier": 0.2156,
            "baseline_accuracy": 0.6771,
            "ensemble_accuracy": 0.6979,
            "ensemble_market_accuracy": 0.6944,
            "betmgm_accuracy": 0.6875,
            "baseline_actionable_count": 81,
            "ensemble_actionable_count": 104,
            "log_loss_delta": -0.0239,
            "brier_delta": -0.0083,
            "accuracy_delta": 0.0208,
            "ensemble_vs_betmgm_log_loss_delta": -0.0144,
            "ensemble_vs_betmgm_brier_delta": -0.0048,
            "ensemble_vs_betmgm_accuracy_delta": 0.0069,
            "created_at": "2026-05-11T19:45:00Z",
        },
        "dashboard_mlb_model_health_v1": {
            "run_date": "2026-05-10",
            "model_version": "mlb_moneyline_public_v1",
            "prediction_count": 14,
            "abstention_count": 2,
            "abstention_rate": 0.1429,
            "avg_model_prob": 0.552,
            "avg_market_prob": 0.537,
            "avg_edge": 0.031,
            "avg_expected_value": 0.058,
            "ece_at_train": 0.031,
            "latest_prediction_at": "2026-05-10T14:00:00Z",
        },
        "dashboard_empty_state_v1": {
            "kind": "no_live_markets",
            "title": "No live markets",
            "message": "No upcoming markets are currently available.",
            "action": None,
            "severity": "info",
        },
    }


class TestCanonicalDashboardSchemaInventory:
    """Inventory tests for canonical dashboard schema assets."""

    @pytest.mark.parametrize("name", DASHBOARD_SCHEMA_NAMES)
    def test_canonical_schema_file_exists(self, name: str) -> None:
        """Every dashboard page has a named dashboard_*_v1 schema."""
        assert (SCHEMAS_DIR / f"{name}.schema.json").exists()

    def test_tests_contracts_schemas_is_canonical_location(
        self, dashboard_schemas: dict[str, dict[str, Any]]
    ) -> None:
        """Dashboard read-model contracts are canonical in tests/contracts/schemas."""
        assert set(dashboard_schemas) == set(DASHBOARD_SCHEMA_NAMES)

    @pytest.mark.parametrize("name", DASHBOARD_SCHEMA_NAMES)
    def test_schema_is_strict_for_all_object_nodes(
        self, name: str, dashboard_schemas: dict[str, dict[str, Any]]
    ) -> None:
        """All dashboard object schemas reject undeclared properties."""
        schema = dashboard_schemas[name]
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False
        for object_node in _object_schema_nodes(schema):
            assert object_node["additionalProperties"] is False


class TestDashboardReadModelContracts:
    """Consumer contract tests for canonical dashboard read-model rows."""

    @pytest.mark.parametrize("name", DASHBOARD_SCHEMA_NAMES)
    def test_valid_payload_passes(
        self,
        name: str,
        dashboard_schemas: dict[str, dict[str, Any]],
        valid_dashboard_payloads: dict[str, dict[str, Any]],
    ) -> None:
        """A representative schema-compliant read-model row is accepted."""
        _validate(valid_dashboard_payloads[name], dashboard_schemas[name])

    @pytest.mark.parametrize("name", DASHBOARD_SCHEMA_NAMES)
    def test_missing_required_fields_fail(
        self,
        name: str,
        dashboard_schemas: dict[str, dict[str, Any]],
        valid_dashboard_payloads: dict[str, dict[str, Any]],
    ) -> None:
        """Consumers reject read-model rows missing any required field."""
        schema = dashboard_schemas[name]
        for field in schema["required"]:
            payload = deepcopy(valid_dashboard_payloads[name])
            del payload[field]
            with pytest.raises(ValidationError):
                _validate(payload, schema)

    @pytest.mark.parametrize("name", DASHBOARD_SCHEMA_NAMES)
    def test_extra_fields_fail(
        self,
        name: str,
        dashboard_schemas: dict[str, dict[str, Any]],
        valid_dashboard_payloads: dict[str, dict[str, Any]],
    ) -> None:
        """Consumers reject read-model rows with undeclared fields."""
        payload = {**valid_dashboard_payloads[name], "unexpected_column": "drift"}
        with pytest.raises(ValidationError):
            _validate(payload, dashboard_schemas[name])

    @pytest.mark.parametrize(
        ("name", "field"),
        (
            ("dashboard_live_markets_v1", "edge"),
            ("dashboard_bet_detail_v1", "elo_prob"),
            ("dashboard_bet_detail_v1", "market_prob"),
            ("dashboard_calibration_v1", "bucket_start"),
            ("dashboard_calibration_v1", "avg_elo_prob"),
        ),
    )
    def test_invalid_probability_ranges_fail(
        self,
        name: str,
        field: str,
        dashboard_schemas: dict[str, dict[str, Any]],
        valid_dashboard_payloads: dict[str, dict[str, Any]],
    ) -> None:
        """Probability and edge fields reject values outside governed ranges."""
        payload = {**valid_dashboard_payloads[name], field: 1.5}
        with pytest.raises(ValidationError):
            _validate(payload, dashboard_schemas[name])

    @pytest.mark.parametrize(
        ("name", "field", "bad_value"),
        (
            ("dashboard_data_quality_v1", "status", "PASS"),
            ("dashboard_bet_detail_v1", "status", "OPEN"),
            ("dashboard_live_markets_v1", "confidence", "medium"),
        ),
    )
    def test_wrong_status_or_enum_casing_fails(
        self,
        name: str,
        field: str,
        bad_value: str,
        dashboard_schemas: dict[str, dict[str, Any]],
        valid_dashboard_payloads: dict[str, dict[str, Any]],
    ) -> None:
        """Status and confidence enums are case-sensitive."""
        payload = {**valid_dashboard_payloads[name], field: bad_value}
        with pytest.raises(ValidationError):
            _validate(payload, dashboard_schemas[name])


class TestDashboardEmptyAndErrorStateContract:
    """Contract tests for empty-state and typed dashboard error payloads."""

    @pytest.mark.parametrize(
        "kind",
        (
            "no_portfolio_snapshots",
            "no_live_markets",
            "no_rankings",
            "no_calibration_predictions",
            "no_settled_calibration_outcomes",
            "no_bet_details",
            "bet_not_found",
            "dashboard_contract_mismatch",
            "dashboard_read_model_missing",
            "dashboard_query_failed",
            "dashboard_unavailable",
        ),
    )
    def test_valid_empty_and_error_kinds_pass(
        self,
        kind: str,
        dashboard_schemas: dict[str, dict[str, Any]],
        valid_dashboard_payloads: dict[str, dict[str, Any]],
    ) -> None:
        """All governed empty-state and typed error kinds are accepted."""
        severity = "error" if kind.startswith("dashboard_") else "info"
        payload = {
            **valid_dashboard_payloads["dashboard_empty_state_v1"],
            "kind": kind,
            "severity": severity,
        }
        _validate(payload, dashboard_schemas["dashboard_empty_state_v1"])

    @pytest.mark.parametrize(
        "kind", ("no_data", "query_failed", "DASHBOARD_UNAVAILABLE")
    )
    def test_invalid_empty_or_error_kinds_fail(
        self,
        kind: str,
        dashboard_schemas: dict[str, dict[str, Any]],
        valid_dashboard_payloads: dict[str, dict[str, Any]],
    ) -> None:
        """Ungoverned empty-state and error kinds are rejected."""
        payload = {**valid_dashboard_payloads["dashboard_empty_state_v1"], "kind": kind}
        with pytest.raises(ValidationError):
            _validate(payload, dashboard_schemas["dashboard_empty_state_v1"])
