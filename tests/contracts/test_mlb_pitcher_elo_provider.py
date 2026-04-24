"""Provider RED tests for the MLB pitcher Elo boundary.

The producer (:class:`PitcherEloLadder`) returns raw floats from
``get_rating()`` and ``matchup_adjustment()``. The locked contract requires
two structured payload kinds: ``pitcher_rating`` and ``pitcher_matchup``.
This file calls real producer methods, wraps results into the canonical
shapes, and validates against the frozen schema. Drift that cannot be
addressed by harness-side wrapping is marked ``xfail(strict=True)`` with
the Wave 4-6 fix task id.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from plugins.elo.mlb_pitcher_elo import PitcherEloLadder
from tests.contracts.fixtures.mlb_pitcher_samples import (
    AWAY_PITCHER_ID,
    HOME_PITCHER_ID,
    build_trained_pitcher_ladder,
)
from tests.contracts.helpers import validate_contract_definition


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "mlb_pitcher_elo_v1.json").read_text(encoding="utf-8")
    )


def _assemble_rating_payload(
    ladder: PitcherEloLadder, pitcher_id: str
) -> dict[str, Any]:
    return {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "pitcher_rating",
        "pitcher_id": pitcher_id,
        "rating": float(ladder.get_rating(pitcher_id)),
        "k_factor": float(ladder.k_factor),
        "pitcher_weight": float(ladder.pitcher_weight),
    }


def _assemble_matchup_payload(ladder: PitcherEloLadder) -> dict[str, Any]:
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


class TestMLBPitcherEloProviderContract:
    """Provider-side guarantees against real ``PitcherEloLadder`` outputs."""

    def test_real_pitcher_rating_payload_matches_contract(self) -> None:
        ladder = build_trained_pitcher_ladder()

        payload = _assemble_rating_payload(ladder, HOME_PITCHER_ID)

        validate_contract_definition(payload, _load_schema(), "pitcher_rating")

    def test_real_pitcher_matchup_payload_matches_contract(self) -> None:
        ladder = build_trained_pitcher_ladder()

        payload = _assemble_matchup_payload(ladder)

        validate_contract_definition(payload, _load_schema(), "pitcher_matchup")

    def test_matchup_adjustment_is_zero_when_pitcher_unknown(self) -> None:
        ladder = build_trained_pitcher_ladder()

        assert ladder.matchup_adjustment(None, AWAY_PITCHER_ID) == 0.0
        assert ladder.matchup_adjustment(HOME_PITCHER_ID, None) == 0.0

    def test_real_update_changes_rating_in_expected_direction(self) -> None:
        ladder = PitcherEloLadder()
        before = float(ladder.get_rating(HOME_PITCHER_ID))

        ladder.update(HOME_PITCHER_ID, AWAY_PITCHER_ID, True)

        assert float(ladder.get_rating(HOME_PITCHER_ID)) > before

    def test_invalid_rating_payload_is_rejected_by_schema(self) -> None:
        ladder = build_trained_pitcher_ladder()
        payload = _assemble_rating_payload(ladder, HOME_PITCHER_ID)
        payload["pitcher_weight"] = 1.5  # outside [0, 1]

        with pytest.raises(ValidationError):
            validate_contract_definition(payload, _load_schema(), "pitcher_rating")

    def test_invalid_matchup_payload_is_rejected_by_schema(self) -> None:
        ladder = build_trained_pitcher_ladder()
        payload = _assemble_matchup_payload(ladder)
        del payload["adjustment_elo"]

        with pytest.raises(ValidationError):
            validate_contract_definition(payload, _load_schema(), "pitcher_matchup")

    def test_producer_emits_native_pitcher_rating_payload(self) -> None:
        ladder = build_trained_pitcher_ladder()

        payload = ladder.rating_payload(HOME_PITCHER_ID)
        validate_contract_definition(payload, _load_schema(), "pitcher_rating")

    def test_producer_emits_native_pitcher_matchup_payload(self) -> None:
        ladder = build_trained_pitcher_ladder()

        payload = ladder.matchup_payload(HOME_PITCHER_ID, AWAY_PITCHER_ID)
        validate_contract_definition(payload, _load_schema(), "pitcher_matchup")
