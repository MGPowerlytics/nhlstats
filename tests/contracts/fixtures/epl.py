from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_GAME_PAYLOAD: dict[str, Any] = {
    "competition": "EPL",
    "schema_version": "v1",
    "payload_kind": "game",
    "season": "2025-2026",
    "match_date": "2025-08-16",
    "home_team": "Liverpool",
    "away_team": "Bournemouth",
    "game_id": "EPL-2025-08-16-LIV-BOU",
    "source": "contract_scaffold",
}

_BASE_MARKET_PAYLOAD: dict[str, Any] = {
    "competition": "EPL",
    "schema_version": "v1",
    "payload_kind": "market",
    "sport": "EPL",
    "market_id": "kxh-epl-liv-bou-2025-08-16",
    "ticker": "KXHEPL-LIVBOU-20250816",
    "home_team": "Liverpool",
    "away_team": "Bournemouth",
    "market_type": "match_winner",
}

_BASE_GOVERNED_ROW: dict[str, Any] = {
    "competition": "EPL",
    "schema_version": "v1",
    "row_kind": "epl_game",
    "game_id": "EPL-2025-08-16-LIV-BOU",
    "season": "2025-2026",
    "home_team": "Liverpool",
    "away_team": "Bournemouth",
    "match_date": "2025-08-16",
}


def build_epl_game_payload() -> dict[str, Any]:
    """Build a deterministic EPL game payload sample."""
    return deepcopy(_BASE_GAME_PAYLOAD)


def build_epl_market_payload() -> dict[str, Any]:
    """Build a deterministic EPL market payload sample."""
    return deepcopy(_BASE_MARKET_PAYLOAD)


def build_epl_governed_row() -> dict[str, Any]:
    """Build a deterministic EPL governed-row sample."""
    return deepcopy(_BASE_GOVERNED_ROW)
