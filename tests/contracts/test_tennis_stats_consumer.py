"""Consumer/provider contract tests for the tennis_player_match_stats boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.tennis_stats_samples import (
    build_tennis_loser_stats_row,
    build_tennis_winner_stats_row,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parent
    / "schemas"
    / "tennis_player_match_stats_row_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_canonical_winner_row_satisfies_contract() -> None:
    Draft202012Validator(_load_schema()).validate(build_tennis_winner_stats_row())


def test_canonical_loser_row_satisfies_contract() -> None:
    Draft202012Validator(_load_schema()).validate(build_tennis_loser_stats_row())


@pytest.mark.parametrize(
    "missing_field",
    ["game_id", "player_name", "won"],
)
def test_stats_contract_rejects_missing_required_field(missing_field: str) -> None:
    row = build_tennis_winner_stats_row()
    row.pop(missing_field)
    with pytest.raises(ValidationError):
        Draft202012Validator(_load_schema()).validate(row)


def test_stats_contract_rejects_invalid_game_id_pattern() -> None:
    row = build_tennis_winner_stats_row(game_id="invalid_game_id_123")
    with pytest.raises(ValidationError):
        Draft202012Validator(_load_schema()).validate(row)
