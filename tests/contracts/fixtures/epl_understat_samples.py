from __future__ import annotations

from copy import deepcopy
from typing import Any

_BASE_UNDERSTAT_API_MATCH: dict[str, Any] = {
    "id": "99999",
    "isResult": True,
    "h": {
        "id": "89",
        "title": "Manchester City",
        "short_title": "MCI",
    },
    "a": {
        "id": "82",
        "title": "Tottenham",
        "short_title": "TOT",
    },
    "goals": {
        "h": "2",
        "a": "1",
    },
    "xG": {
        "h": "2.71828",
        "a": "0.84319",
    },
    "datetime": "2025-08-16 16:30:00",
    "forecast": {
        "w": "0.7021",
        "d": "0.1811",
        "l": "0.1168",
    },
}

_BASE_UNDERSTAT_CONTRACT_PAYLOAD: dict[str, Any] = {
    "source": "UNDERSTAT",
    "sport": "EPL",
    "season": 2025,
    "match_id": "99999",
    "game_date": "2025-08-16",
    "home_team": "Manchester City",
    "away_team": "Tottenham Hotspur",
    "home_xg": 2.71828,
    "away_xg": 0.84319,
    "forecast_home_win": 0.7021,
    "forecast_draw": 0.1811,
    "forecast_away_win": 0.1168,
}


def build_epl_understat_api_match(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic raw Understat league-match payload."""
    payload = deepcopy(_BASE_UNDERSTAT_API_MATCH)
    payload.update(overrides)
    return payload


def build_epl_understat_contract_payload(**overrides: Any) -> dict[str, Any]:
    """Build the canonical normalized Understat contract payload."""
    payload = deepcopy(_BASE_UNDERSTAT_CONTRACT_PAYLOAD)
    payload.update(overrides)
    return payload
