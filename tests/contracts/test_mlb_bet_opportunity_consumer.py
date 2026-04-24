"""Wave-2 consumer-red contract tests for the MLB ``identify_good_bets`` /
``OddsComparator`` opportunity payload.

These tests freeze the canonical MLB opportunity dict shape consumed by
``identify_good_bets`` and downstream BetLoader. Production currently
propagates the configured sport casing verbatim (lowercase ``"mlb"``) and
omits explicit ``[0.03, 0.40]`` enforcement on the persisted opportunity, so
some of these tests are expected to surface drift the Wave-3 provider tests
will then drive to green.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from tests.contracts.fixtures.mlb_bet_opportunity_samples import (
    build_mlb_bet_opportunity,
    build_mlb_bet_opportunity_lowercase_sport,
    build_mlb_bet_opportunity_missing_field,
    build_mlb_bet_opportunity_out_of_range_edge,
)
from tests.contracts.helpers import validate_contract_payload

CONTRACT_PATH = Path(__file__).parent / "schemas" / "mlb_bet_opportunity_v1.json"


@pytest.fixture(scope="module")
def opportunity_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_canonical_mlb_opportunity_fixture_matches_contract(
    opportunity_contract: dict[str, Any],
) -> None:
    validate_contract_payload(build_mlb_bet_opportunity(), opportunity_contract)


def test_mlb_opportunity_contract_freezes_uppercase_sport(
    opportunity_contract: dict[str, Any],
) -> None:
    """The persisted opportunity must surface ``sport='MLB'`` (uppercase)."""
    assert opportunity_contract["properties"]["sport"]["const"] == "MLB"
    assert "sport" in opportunity_contract["required"]


def test_mlb_opportunity_contract_freezes_two_way_sides(
    opportunity_contract: dict[str, Any],
) -> None:
    """MLB has no draw outcome — only ``home`` and ``away`` are valid."""
    assert opportunity_contract["properties"]["side"]["enum"] == ["home", "away"]


def test_mlb_opportunity_contract_freezes_edge_band(
    opportunity_contract: dict[str, Any],
) -> None:
    """Persisted opportunities must satisfy MIN/MAX edge thresholds."""
    edge_schema = opportunity_contract["properties"]["edge"]
    assert edge_schema["minimum"] == 0.03
    assert edge_schema["maximum"] == 0.40


def test_mlb_opportunity_contract_freezes_confidence_enum(
    opportunity_contract: dict[str, Any],
) -> None:
    confidence_schema = opportunity_contract["properties"]["confidence"]
    assert confidence_schema["enum"] == ["HIGH", "MEDIUM", "LOW"]


@pytest.mark.parametrize(
    "missing_field",
    [
        "sport",
        "game_id",
        "home_team",
        "away_team",
        "side",
        "elo_prob",
        "market_prob",
        "edge",
        "confidence",
    ],
)
def test_mlb_opportunity_contract_rejects_missing_required_fields(
    opportunity_contract: dict[str, Any], missing_field: str
) -> None:
    payload = build_mlb_bet_opportunity_missing_field(missing_field)

    with pytest.raises(ValidationError):
        validate_contract_payload(payload, opportunity_contract)


def test_mlb_opportunity_contract_rejects_lowercase_sport(
    opportunity_contract: dict[str, Any],
) -> None:
    """Drift mode: production currently emits lowercase ``'mlb'`` — must fail."""
    with pytest.raises(ValidationError):
        validate_contract_payload(
            build_mlb_bet_opportunity_lowercase_sport(), opportunity_contract
        )


@pytest.mark.parametrize("bad_edge", [0.029, 0.401, -0.10, 1.0])
def test_mlb_opportunity_contract_rejects_out_of_range_edge(
    opportunity_contract: dict[str, Any], bad_edge: float
) -> None:
    with pytest.raises(ValidationError):
        validate_contract_payload(
            build_mlb_bet_opportunity_out_of_range_edge(bad_edge),
            opportunity_contract,
        )


def test_mlb_opportunity_contract_rejects_draw_side(
    opportunity_contract: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        validate_contract_payload(
            build_mlb_bet_opportunity(side="draw"), opportunity_contract
        )


def test_mlb_opportunity_contract_rejects_unknown_confidence(
    opportunity_contract: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        validate_contract_payload(
            build_mlb_bet_opportunity(confidence="medium"), opportunity_contract
        )


def test_mlb_opportunity_contract_rejects_unknown_top_level_field(
    opportunity_contract: dict[str, Any],
) -> None:
    """``additionalProperties: false`` blocks silently introduced columns."""
    payload = build_mlb_bet_opportunity()
    payload["mystery_field"] = 42

    with pytest.raises(ValidationError):
        validate_contract_payload(payload, opportunity_contract)


def test_mlb_opportunity_allows_optional_ticker_to_be_null(
    opportunity_contract: dict[str, Any],
) -> None:
    validate_contract_payload(
        build_mlb_bet_opportunity(ticker=None), opportunity_contract
    )
