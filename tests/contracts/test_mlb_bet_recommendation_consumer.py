"""Wave-2 consumer-red contract tests for MLB ``bet_recommendations`` rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from tests.contracts.fixtures.mlb_bet_recommendation_samples import (
    build_legacy_mlb_recommendation_payload,
    build_mlb_recommendation_contract_expectations,
    build_mlb_recommendation_payload,
    build_mlb_recommendation_row,
)
from tests.contracts.helpers import validate_contract_definition

CONTRACT_PATH = Path(__file__).parent / "schemas" / "mlb_bet_recommendation_row_v1.json"


@pytest.fixture(scope="module")
def recommendation_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def recommendation_expectations() -> dict[str, Any]:
    return build_mlb_recommendation_contract_expectations()


# ---------------------------------------------------------------------------
# Schema-shape invariants
# ---------------------------------------------------------------------------


def test_mlb_recommendation_contract_freezes_uppercase_sport(
    recommendation_contract: dict[str, Any],
) -> None:
    base = recommendation_contract["$defs"]["base_recommendation"]
    assert base["properties"]["sport"]["const"] == "MLB"


def test_mlb_recommendation_contract_requires_ticker(
    recommendation_contract: dict[str, Any],
) -> None:
    """Ticker is required for placed_bets linkage per repo memory."""
    base = recommendation_contract["$defs"]["base_recommendation"]
    assert "ticker" in base["required"]


def test_mlb_recommendation_contract_freezes_bet_id_pattern(
    recommendation_contract: dict[str, Any],
) -> None:
    pattern = recommendation_contract["$defs"]["bet_identifier"]["pattern"]
    assert pattern == r"^MLB_[0-9]{4}-[0-9]{2}-[0-9]{2}_.+_(home|away)$"


def test_mlb_recommendation_contract_freezes_edge_band(
    recommendation_contract: dict[str, Any],
) -> None:
    edge_schema = recommendation_contract["$defs"]["base_recommendation"][
        "properties"
    ]["edge"]
    assert edge_schema["minimum"] == 0.05
    assert edge_schema["maximum"] == 0.15


def test_mlb_recommendation_contract_freezes_confidence_enum(
    recommendation_contract: dict[str, Any],
) -> None:
    confidence_schema = recommendation_contract["$defs"]["base_recommendation"][
        "properties"
    ]["confidence"]
    assert confidence_schema["enum"] == ["HIGH", "MEDIUM", "LOW"]


def test_mlb_recommendation_saved_payload_requires_two_way_side(
    recommendation_contract: dict[str, Any],
) -> None:
    saved = recommendation_contract["$defs"]["saved_payload"]
    side_schema = saved["allOf"][1]["properties"]["side"]
    assert side_schema["enum"] == ["home", "away"]


# ---------------------------------------------------------------------------
# Positive fixture validation
# ---------------------------------------------------------------------------


def test_canonical_saved_payload_fixture_matches_contract(
    recommendation_contract: dict[str, Any],
) -> None:
    validate_contract_definition(
        build_mlb_recommendation_payload(), recommendation_contract, "saved_payload"
    )


def test_canonical_persisted_row_fixture_matches_contract(
    recommendation_contract: dict[str, Any],
) -> None:
    validate_contract_definition(
        build_mlb_recommendation_row(), recommendation_contract, "persisted_row"
    )


def test_canonical_persisted_row_uses_uppercase_mlb_sport(
    recommendation_expectations: dict[str, Any],
) -> None:
    row = build_mlb_recommendation_row()
    assert row["sport"] == recommendation_expectations["sport"]


# ---------------------------------------------------------------------------
# Negative cases
# ---------------------------------------------------------------------------


def test_legacy_payload_with_lowercase_sport_and_date_str_is_rejected(
    recommendation_contract: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        validate_contract_definition(
            build_legacy_mlb_recommendation_payload(),
            recommendation_contract,
            "saved_payload",
        )


@pytest.mark.parametrize(
    "missing_field",
    [
        "bet_id",
        "sport",
        "recommendation_date",
        "home_team",
        "away_team",
        "bet_on",
        "elo_prob",
        "market_prob",
        "edge",
        "confidence",
        "ticker",
    ],
)
def test_persisted_row_contract_rejects_missing_required_columns(
    recommendation_contract: dict[str, Any], missing_field: str
) -> None:
    row = build_mlb_recommendation_row()
    row.pop(missing_field)

    with pytest.raises(ValidationError):
        validate_contract_definition(
            row, recommendation_contract, "persisted_row"
        )


def test_persisted_row_contract_rejects_lowercase_sport(
    recommendation_contract: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        validate_contract_definition(
            build_mlb_recommendation_row(sport="mlb"),
            recommendation_contract,
            "persisted_row",
        )


@pytest.mark.parametrize("bad_edge", [0.0, 0.029, 0.41, 0.5])
def test_persisted_row_contract_rejects_out_of_range_edge(
    recommendation_contract: dict[str, Any], bad_edge: float
) -> None:
    with pytest.raises(ValidationError):
        validate_contract_definition(
            build_mlb_recommendation_row(edge=bad_edge),
            recommendation_contract,
            "persisted_row",
        )


@pytest.mark.parametrize(
    "bad_bet_id",
    [
        "EPL-2025-04-15-KXMLBGAME-25APR15NYYBOS-NYY-home",
        "MLB_2025-04-15_KXMLBGAME-25APR15NYYBOS-NYY_draw",
        "mlb_2025-04-15_KXMLBGAME-25APR15NYYBOS-NYY_home",
        "MLB-2025-04-15-KXMLBGAME-25APR15NYYBOS-NYY-home",
    ],
)
def test_persisted_row_contract_rejects_malformed_bet_id(
    recommendation_contract: dict[str, Any], bad_bet_id: str
) -> None:
    with pytest.raises(ValidationError):
        validate_contract_definition(
            build_mlb_recommendation_row(bet_id=bad_bet_id),
            recommendation_contract,
            "persisted_row",
        )


def test_persisted_row_contract_rejects_null_ticker(
    recommendation_contract: dict[str, Any],
) -> None:
    """Ticker must be present (and a string) for placed_bets linkage."""
    with pytest.raises(ValidationError):
        validate_contract_definition(
            build_mlb_recommendation_row(ticker=None),
            recommendation_contract,
            "persisted_row",
        )


def test_persisted_row_contract_rejects_non_kalshi_ticker(
    recommendation_contract: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        validate_contract_definition(
            build_mlb_recommendation_row(ticker="DRAFTKINGS-NYY-BOS"),
            recommendation_contract,
            "persisted_row",
        )


def test_persisted_row_contract_rejects_unknown_confidence(
    recommendation_contract: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        validate_contract_definition(
            build_mlb_recommendation_row(confidence="medium"),
            recommendation_contract,
            "persisted_row",
        )
