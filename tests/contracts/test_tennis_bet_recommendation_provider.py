"""Provider RED tests for the Tennis branch of BetLoader / BetRecommendation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from plugins.bet_loader import (
    BetContext,
    BetData,
    BetRecommendation,
    _generate_tennis_bet_id,
    _normalize_bet_sport,
    _synthesize_tennis_ticker,
)
from tests.contracts.fixtures.tennis_bet_recommendation_samples import (
    build_tennis_saved_bet_payload,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parent
    / "schemas"
    / "tennis_bet_recommendation_row_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator(def_name: str) -> Draft202012Validator:
    schema = _load_schema()
    resource = Resource.from_contents(schema)
    registry = Registry().with_resource(uri=schema["$id"], resource=resource)
    return Draft202012Validator(
        {"$ref": f"{schema['$id']}#/$defs/{def_name}"}, registry=registry
    )


@pytest.fixture
def tennis_context() -> BetContext:
    return BetContext(sport="tennis", date_str="2026-04-07", index=0)


def test_normalize_bet_sport_tennis_returns_uppercase() -> None:
    assert _normalize_bet_sport("tennis") == "TENNIS"


def test_generate_tennis_bet_id_uses_ticker_when_present() -> None:
    bet_id = _generate_tennis_bet_id(
        date_str="2026-04-07",
        ticker="KXATPMATCH-26APR07COBBLO-COB",
        home_team="Alexander Blockx",
        away_team="Flavio Cobolli",
        side="away",
    )
    assert bet_id == "TENNIS_2026-04-07_KXATPMATCH-26APR07COBBLO-COB_away"


def test_generate_tennis_bet_id_falls_back_to_synthetic_ticker() -> None:
    bet_id = _generate_tennis_bet_id(
        date_str="2026-04-07",
        ticker=None,
        home_team="Alexander Blockx",
        away_team="Flavio Cobolli",
        side="away",
    )
    assert bet_id.startswith("TENNIS_2026-04-07_KXATPMATCH-SYNTH-")
    assert bet_id.endswith("_away")


def test_synthetic_tennis_ticker_format_matches_contract() -> None:
    ticker = _synthesize_tennis_ticker(
        date_str="2026-04-07",
        home_team="Alexander Blockx",
        away_team="Flavio Cobolli",
        side="away",
    )
    assert ticker.startswith("KXATPMATCH-SYNTH-2026-04-07-")


def test_bet_recommendation_from_dict_emits_contract_valid_persisted_row(
    tennis_context: BetContext,
) -> None:
    payload = build_tennis_saved_bet_payload()
    rec = BetRecommendation.from_dict(payload, tennis_context)
    params = rec.to_sql_params()

    assert params["sport"] == "TENNIS"
    assert params["bet_id"].startswith("TENNIS_2026-04-07_")
    _validator("persisted_row").validate(params)


def test_bet_recommendation_from_dict_synthesizes_ticker_when_missing(
    tennis_context: BetContext,
) -> None:
    payload = build_tennis_saved_bet_payload()
    payload["ticker"] = None
    payload["bet_id"] = None
    rec = BetRecommendation.from_dict(payload, tennis_context)
    params = rec.to_sql_params()

    assert params["ticker"].startswith("KXATPMATCH-SYNTH-2026-04-07-")
    _validator("persisted_row").validate(params)


def test_bet_data_to_recommendation_normalizes_sport(
    tennis_context: BetContext,
) -> None:
    bet = BetData.from_dict(build_tennis_saved_bet_payload())
    rec = bet.to_recommendation(tennis_context)
    assert rec.sport == "TENNIS"
