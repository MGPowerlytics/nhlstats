"""Consumer contract tests for the tennis_games row + tennis unified row boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.tennis_games_db_samples import (
    build_tennis_games_row,
    build_tennis_games_row_wta,
)
from tests.contracts.fixtures.tennis_unified_samples import (
    build_tennis_unified_row_from_csv,
    build_tennis_unified_row_from_kalshi,
)


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def test_canonical_tennis_games_row_satisfies_contract() -> None:
    Draft202012Validator(_load("tennis_tennis_games_row_v1.json")).validate(
        build_tennis_games_row()
    )


def test_wta_tennis_games_row_satisfies_contract() -> None:
    Draft202012Validator(_load("tennis_tennis_games_row_v1.json")).validate(
        build_tennis_games_row_wta()
    )


def test_unified_row_from_kalshi_satisfies_contract() -> None:
    Draft202012Validator(_load("tennis_unified_game_row_v1.json")).validate(
        build_tennis_unified_row_from_kalshi()
    )


def test_unified_row_from_csv_satisfies_contract() -> None:
    Draft202012Validator(_load("tennis_unified_game_row_v1.json")).validate(
        build_tennis_unified_row_from_csv()
    )


def test_unified_row_rejects_non_tennis_sport() -> None:
    row = build_tennis_unified_row_from_kalshi(sport="MLB")
    with pytest.raises(ValidationError):
        Draft202012Validator(_load("tennis_unified_game_row_v1.json")).validate(row)


def test_tennis_games_row_rejects_invalid_tour() -> None:
    row = build_tennis_games_row(tour="DAVIS")
    with pytest.raises(ValidationError):
        Draft202012Validator(_load("tennis_tennis_games_row_v1.json")).validate(row)
