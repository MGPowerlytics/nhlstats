from __future__ import annotations

from copy import deepcopy
from typing import Any

_BASE_RECOMMENDATION_PAYLOAD: dict[str, Any] = {
    "bet_id": "EPL-2025-08-16-KXHEPL-LIVBOU-20250816-home",
    "sport": "EPL",
    "recommendation_date": "2025-08-16",
    "home_team": "Liverpool",
    "away_team": "Bournemouth",
    "bet_on": "home",
    "side": "home",
    "ticker": "KXHEPL-LIVBOU-20250816",
    "elo_prob": 0.58,
    "market_prob": 0.47,
    "edge": 0.11,
    "expected_value": 0.2340425532,
    "kelly_fraction": 0.1037735849,
    "confidence": "MEDIUM",
    "home_rating": 1612.4,
    "away_rating": 1498.2,
    "yes_ask": 47,
    "no_ask": 53,
}

_BASE_RECOMMENDATION_ROW: dict[str, Any] = {
    key: value for key, value in _BASE_RECOMMENDATION_PAYLOAD.items() if key != "side"
}

_BASE_RECOMMENDATION_CONTRACT_EXPECTATIONS: dict[str, Any] = {
    "bet_id": "EPL-2025-08-16-KXHEPL-LIVBOU-20250816-home",
    "sport": "EPL",
    "recommendation_date": "2025-08-16",
    "allowed_bet_on": {"home", "away", "draw"},
}


def build_epl_recommendation_payload(**overrides: Any) -> dict[str, Any]:
    """Build a canonical EPL recommendation payload fixture."""
    payload = deepcopy(_BASE_RECOMMENDATION_PAYLOAD)
    payload.update(overrides)
    return payload


def build_epl_recommendation_row(**overrides: Any) -> dict[str, Any]:
    """Build a canonical bet_recommendations row fixture."""
    row = deepcopy(_BASE_RECOMMENDATION_ROW)
    row.update(overrides)
    return row


def build_legacy_recommendation_payload(**overrides: Any) -> dict[str, Any]:
    """Build a legacy recommendation payload that should violate the v1 contract."""
    payload = build_epl_recommendation_payload(
        sport="epl",
        bet_on="Liverpool",
    )
    payload.pop("recommendation_date")
    payload["date_str"] = "2025-08-16"
    payload.pop("bet_id")
    payload.update(overrides)
    return payload


def build_epl_recommendation_contract_expectations() -> dict[str, Any]:
    """Build shared canonical recommendation invariant expectations."""
    return deepcopy(_BASE_RECOMMENDATION_CONTRACT_EXPECTATIONS)
