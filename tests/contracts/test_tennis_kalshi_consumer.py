"""Consumer contract tests for the Tennis Kalshi raw market + persisted game_odds row."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from plugins.kalshi_markets import (
    _kalshi_tennis_event_key,
    _kalshi_tennis_full_name,
    _kalshi_tennis_game_date,
    _kalshi_tennis_tour,
)
from tests.contracts.fixtures.tennis_kalshi_event_samples import (
    build_tennis_kalshi_paired_event,
)
from tests.contracts.fixtures.tennis_kalshi_samples import (
    build_tennis_kalshi_game_odds_row,
    build_tennis_kalshi_raw_market,
    build_tennis_kalshi_wta_raw_market,
)


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def _validator(schema: dict[str, Any], def_name: str) -> Draft202012Validator:
    resource = Resource.from_contents(schema)
    registry = Registry().with_resource(uri=schema["$id"], resource=resource)
    return Draft202012Validator(
        {"$ref": f"{schema['$id']}#/$defs/{def_name}"}, registry=registry
    )


# ---------------------------------------------------------------------------
# raw_market $def
# ---------------------------------------------------------------------------


def test_canonical_atp_raw_market_satisfies_contract() -> None:
    schema = _load("tennis_kalshi_market_v1.json")
    _validator(schema, "raw_market").validate(build_tennis_kalshi_raw_market("COB"))
    _validator(schema, "raw_market").validate(build_tennis_kalshi_raw_market("BLO"))


def test_canonical_wta_raw_market_satisfies_contract() -> None:
    schema = _load("tennis_kalshi_market_v1.json")
    _validator(schema, "raw_market").validate(build_tennis_kalshi_wta_raw_market())


@pytest.mark.parametrize(
    "missing_field", ["ticker", "event_ticker", "yes_sub_title", "yes_ask", "title"]
)
def test_raw_market_rejects_missing_required_field(missing_field: str) -> None:
    schema = _load("tennis_kalshi_market_v1.json")
    market = build_tennis_kalshi_raw_market("COB")
    market.pop(missing_field)
    with pytest.raises(ValidationError):
        _validator(schema, "raw_market").validate(market)


# ---------------------------------------------------------------------------
# game_odds_row $def
# ---------------------------------------------------------------------------


def test_persisted_game_odds_row_home_satisfies_contract() -> None:
    schema = _load("tennis_kalshi_market_v1.json")
    _validator(schema, "game_odds_row").validate(
        build_tennis_kalshi_game_odds_row("home")
    )


def test_persisted_game_odds_row_away_satisfies_contract() -> None:
    schema = _load("tennis_kalshi_market_v1.json")
    _validator(schema, "game_odds_row").validate(
        build_tennis_kalshi_game_odds_row("away")
    )


# ---------------------------------------------------------------------------
# Helper invariants exercised by the producer
# ---------------------------------------------------------------------------


def test_full_name_helper_extracts_yes_sub_title() -> None:
    market = build_tennis_kalshi_raw_market("COB")
    assert _kalshi_tennis_full_name(market) == "Flavio Cobolli"


def test_event_key_helper_extracts_event_ticker() -> None:
    market = build_tennis_kalshi_raw_market("COB")
    assert _kalshi_tennis_event_key(market) == "KXATPMATCH-26APR07COBBLO"


def test_tour_helper_classifies_atp_and_wta() -> None:
    assert _kalshi_tennis_tour("KXATPMATCH-26APR07COBBLO") == "ATP"
    assert _kalshi_tennis_tour("KXWTAMATCH-26APR07SWIGAU") == "WTA"


def test_game_date_helper_returns_iso_date() -> None:
    market = build_tennis_kalshi_raw_market("COB")
    assert _kalshi_tennis_game_date(market, "KXATPMATCH-26APR07COBBLO") == "2026-04-07"


# ---------------------------------------------------------------------------
# paired_event aggregation
# ---------------------------------------------------------------------------


def test_canonical_paired_event_satisfies_contract() -> None:
    Draft202012Validator(_load("tennis_kalshi_event_v1.json")).validate(
        build_tennis_kalshi_paired_event()
    )
