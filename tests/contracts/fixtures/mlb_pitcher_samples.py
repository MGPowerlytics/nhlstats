"""Deterministic MLB pitcher-Elo fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from plugins.elo.mlb_pitcher_elo import PitcherEloLadder


HOME_PITCHER_ID = "543037"  # Gerrit Cole
AWAY_PITCHER_ID = "519242"  # Chris Sale


def build_trained_pitcher_ladder() -> PitcherEloLadder:
    """Return a deterministically-seeded :class:`PitcherEloLadder`."""
    ladder = PitcherEloLadder()
    ladder.update(HOME_PITCHER_ID, AWAY_PITCHER_ID, True)
    ladder.update(HOME_PITCHER_ID, AWAY_PITCHER_ID, True)
    ladder.update(AWAY_PITCHER_ID, HOME_PITCHER_ID, False)
    return ladder


def _build_rating_payload() -> Dict[str, Any]:
    ladder = build_trained_pitcher_ladder()
    return {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "pitcher_rating",
        "pitcher_id": HOME_PITCHER_ID,
        "rating": float(ladder.get_rating(HOME_PITCHER_ID)),
        "k_factor": float(ladder.k_factor),
        "pitcher_weight": float(ladder.pitcher_weight),
    }


def _build_matchup_payload() -> Dict[str, Any]:
    ladder = build_trained_pitcher_ladder()
    return {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "pitcher_matchup",
        "home_pitcher_id": HOME_PITCHER_ID,
        "away_pitcher_id": AWAY_PITCHER_ID,
        "home_rating": float(ladder.get_rating(HOME_PITCHER_ID)),
        "away_rating": float(ladder.get_rating(AWAY_PITCHER_ID)),
        "adjustment_elo": float(
            ladder.matchup_adjustment(HOME_PITCHER_ID, AWAY_PITCHER_ID)
        ),
        "pitcher_weight": float(ladder.pitcher_weight),
    }


_BASE_PITCHER_RATING_PAYLOAD: Dict[str, Any] = _build_rating_payload()
_BASE_PITCHER_MATCHUP_PAYLOAD: Dict[str, Any] = _build_matchup_payload()


def build_pitcher_rating_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical pitcher rating payload."""
    return deepcopy(_BASE_PITCHER_RATING_PAYLOAD)


def build_pitcher_matchup_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical pitcher matchup payload."""
    return deepcopy(_BASE_PITCHER_MATCHUP_PAYLOAD)
