from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from plugins.bet_loader import BetContext, BetRecommendation
from plugins.odds_comparator import BettingOutcome, BettingThresholds, GameContext
from tests.contracts.fixtures.epl_bet_recommendations import (
    build_epl_recommendation_payload,
    build_epl_recommendation_row,
    build_legacy_recommendation_payload,
)

CONTRACT_PATH = Path(__file__).parent / "schemas" / "epl_bet_recommendation_row_v1.json"


class _RatingStub:
    def get_rating(self, team: str) -> float:
        ratings = {
            "Liverpool": 1612.4,
            "Bournemouth": 1498.2,
        }
        return ratings[team]


@pytest.fixture(scope="module")
def recommendation_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _validate_contract_payload(
    contract: dict[str, Any], definition: str, payload: dict[str, Any]
) -> None:
    schema = {
        "$schema": contract["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": contract["$defs"],
    }
    Draft202012Validator(schema).validate(payload)


def test_canonical_saved_payload_fixture_matches_contract(
    recommendation_contract: dict[str, Any],
) -> None:
    _validate_contract_payload(
        recommendation_contract,
        "saved_payload",
        build_epl_recommendation_payload(),
    )


def test_canonical_persisted_row_fixture_matches_contract(
    recommendation_contract: dict[str, Any],
) -> None:
    _validate_contract_payload(
        recommendation_contract,
        "persisted_row",
        build_epl_recommendation_row(),
    )


def test_legacy_date_str_payload_is_rejected(
    recommendation_contract: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        _validate_contract_payload(
            recommendation_contract,
            "saved_payload",
            build_legacy_recommendation_payload(),
        )


def test_odds_comparator_saved_payload_matches_contract(
    recommendation_contract: dict[str, Any],
) -> None:
    context = GameContext(
        sport="epl",
        game_id="EPL-2025-08-16-LIV-BOU",
        home_team_name="Liverpool",
        away_team_name="Bournemouth",
        source="kalshi",
        canon_home="Liverpool",
        canon_away="Bournemouth",
        elo_home="Liverpool",
        elo_away="Bournemouth",
        odds_by_bm={"Kalshi": {"home": 2.13}},
        tickers_by_bm={"Kalshi": {"home": "KXHEPL-LIVBOU-20250816"}},
        elo_system=_RatingStub(),
    )

    payload = BettingOutcome(
        side="home",
        team_name="Liverpool",
        elo_prob=0.58,
        market_prob=0.47,
        market_odds=2.13,
        edge=0.11,
    ).to_opportunity(context, BettingThresholds())

    _validate_contract_payload(recommendation_contract, "saved_payload", payload)


def test_bet_loader_persisted_row_uses_stable_identifier(
    recommendation_contract: dict[str, Any],
) -> None:
    payload = build_epl_recommendation_payload(
        ticker=None,
        side="draw",
        bet_on="draw",
        bet_id="EPL-2025-08-16-LIV-BOU-draw",
    )

    first = BetRecommendation.from_dict(
        payload,
        BetContext(sport="EPL", date_str="2025-08-16", index=0),
    )
    second = BetRecommendation.from_dict(
        payload,
        BetContext(sport="EPL", date_str="2025-08-16", index=7),
    )

    assert first.bet_id == second.bet_id
    _validate_contract_payload(
        recommendation_contract,
        "persisted_row",
        first.to_sql_params(),
    )


def test_bet_loader_persisted_row_uses_uppercase_sport_and_recommendation_date(
    recommendation_contract: dict[str, Any],
) -> None:
    payload = build_epl_recommendation_payload()

    recommendation = BetRecommendation.from_dict(
        payload,
        BetContext(sport="epl", date_str="1999-01-01", index=0),
    )

    assert recommendation.sport == "EPL"
    assert recommendation.recommendation_date == payload["recommendation_date"]
    _validate_contract_payload(
        recommendation_contract,
        "persisted_row",
        recommendation.to_sql_params(),
    )
