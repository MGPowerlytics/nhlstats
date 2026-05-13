"""Consumer contract tests for the TheOddsAPI boundary.

Validates that consumers of TheOddsAPI outputs correctly validate against
the frozen JSON Schema contract. Tests fixture conformance, field constraints,
and rejection of invalid payloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.the_odds_api_samples import (
    build_bookmaker_payload,
    build_market_result_payload,
    build_odds_response_payload,
    build_outcome_payload,
)

SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / "the_odds_api_contract_v1.json"
)


@pytest.fixture(scope="module")
def contract_schema() -> dict[str, Any]:
    """Load the TheOddsAPI contract schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _build_odds_schema(contract: dict[str, Any]) -> dict[str, Any]:
    """Build a temporary schema targeting the odds_response_result definition."""
    return {
        "$schema": contract["$schema"],
        "$ref": "#/$defs/odds_response_result",
        "$defs": contract["$defs"],
    }


def _build_market_schema(contract: dict[str, Any]) -> dict[str, Any]:
    """Build a temporary schema targeting the market_result definition."""
    return {
        "$schema": contract["$schema"],
        "$ref": "#/$defs/market_result",
        "$defs": contract["$defs"],
    }


def _build_bookmaker_schema(contract: dict[str, Any]) -> dict[str, Any]:
    """Build a temporary schema targeting the bookmaker_entry definition."""
    return {
        "$schema": contract["$schema"],
        "$ref": "#/$defs/bookmaker_entry",
        "$defs": contract["$defs"],
    }


def _build_outcome_schema(contract: dict[str, Any]) -> dict[str, Any]:
    """Build a temporary schema targeting the outcome definition."""
    return {
        "$schema": contract["$schema"],
        "$ref": "#/$defs/outcome",
        "$defs": contract["$defs"],
    }


def _validate(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


# ---------------------------------------------------------------------------
# Fixture → schema conformance
# ---------------------------------------------------------------------------


class TestOddsResponseFixtureConformance:
    """Canonical odds response fixture must match the frozen schema."""

    def test_canonical_odds_response_matches_schema(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_odds_schema(contract_schema)
        _validate(schema, build_odds_response_payload())

    def test_canonical_market_result_matches_schema(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_market_schema(contract_schema)
        _validate(schema, build_market_result_payload())

    def test_canonical_bookmaker_matches_schema(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_bookmaker_schema(contract_schema)
        _validate(schema, build_bookmaker_payload())

    def test_canonical_outcome_matches_schema(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_outcome_schema(contract_schema)
        _validate(schema, build_outcome_payload())

    def test_odds_response_rejects_extra_field(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        payload["unknown_field"] = "should_not_exist"
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_odds_response_rejects_missing_required_field(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        del payload["game_id"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)


# ---------------------------------------------------------------------------
# Field constraint validation
# ---------------------------------------------------------------------------


class TestFieldConstraints:
    """Field-level constraints (price > 0, non-empty keys, etc.) are enforced."""

    def test_price_must_be_positive(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_outcome_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_outcome_payload(price=0))

    def test_price_cannot_be_negative(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_outcome_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_outcome_payload(price=-1.5))

    def test_bookmaker_key_must_be_non_empty(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_bookmaker_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_bookmaker_payload(key=""))

    def test_bookmaker_title_must_be_non_empty(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_bookmaker_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_bookmaker_payload(title=""))

    def test_sport_must_be_non_empty(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_odds_response_payload(sport=""))

    def test_game_id_must_be_non_empty(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_odds_response_payload(game_id=""))

    def test_home_team_must_be_non_empty(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_odds_response_payload(home_team=""))

    def test_away_team_must_be_non_empty(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_odds_response_payload(away_team=""))

    def test_market_key_must_be_non_empty(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_market_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_market_result_payload(market_key=""))

    def test_outcome_name_must_be_non_empty(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_outcome_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_outcome_payload(name=""))

    def test_total_bookmakers_must_be_non_negative(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_odds_schema(contract_schema)
        with pytest.raises(ValidationError):
            _validate(schema, build_odds_response_payload(total_bookmakers=-1))


# ---------------------------------------------------------------------------
# Missing / unknown field rejection
# ---------------------------------------------------------------------------


class TestFieldRejection:
    """Schema correctly rejects missing required fields and unknown fields."""

    def test_missing_sport(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        del payload["sport"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_game_id(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        del payload["game_id"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_home_team(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        del payload["home_team"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_away_team(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        del payload["away_team"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_bookmakers(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        del payload["bookmakers"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_total_bookmakers(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        del payload["total_bookmakers"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_schema_version(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        del payload["schema_version"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_payload_kind(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        del payload["payload_kind"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_market_key(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_market_schema(contract_schema)
        payload = build_market_result_payload()
        del payload["market_key"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_outcomes(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_market_schema(contract_schema)
        payload = build_market_result_payload()
        del payload["outcomes"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_is_best(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_market_schema(contract_schema)
        payload = build_market_result_payload()
        del payload["is_best"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_outcome_name(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_outcome_schema(contract_schema)
        payload = build_outcome_payload()
        del payload["name"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_outcome_price(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_outcome_schema(contract_schema)
        payload = build_outcome_payload()
        del payload["price"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_bookmaker_key(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_bookmaker_schema(contract_schema)
        payload = build_bookmaker_payload()
        del payload["key"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_bookmaker_title(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_bookmaker_schema(contract_schema)
        payload = build_bookmaker_payload()
        del payload["title"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_missing_bookmaker_markets(self, contract_schema: dict[str, Any]) -> None:
        schema = _build_bookmaker_schema(contract_schema)
        payload = build_bookmaker_payload()
        del payload["markets"]
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_unknown_field_in_odds_response(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_odds_schema(contract_schema)
        payload = build_odds_response_payload()
        payload["bogus_field"] = "should_be_rejected"
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_unknown_field_in_market_result(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_market_schema(contract_schema)
        payload = build_market_result_payload()
        payload["bogus_field"] = "should_be_rejected"
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_unknown_field_in_bookmaker(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_bookmaker_schema(contract_schema)
        payload = build_bookmaker_payload()
        payload["bogus_field"] = "should_be_rejected"
        with pytest.raises(ValidationError):
            _validate(schema, payload)

    def test_unknown_field_in_outcome(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_outcome_schema(contract_schema)
        payload = build_outcome_payload()
        payload["bogus_field"] = "should_be_rejected"
        with pytest.raises(ValidationError):
            _validate(schema, payload)
