"""Provider RED tests for the Tennis CSV ingestion boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
from jsonschema import Draft202012Validator

from plugins.csv_processors import TennisCSVProcessor
from tests.contracts.fixtures.tennis_csv_samples import build_tennis_csv_row
from tests.contracts.fixtures.tennis_games_db_samples import (
    build_tennis_games_row,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "tennis_csv_ingestion_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _row_with_timestamp(**overrides: Any) -> pd.Series:
    base = build_tennis_csv_row(**overrides)
    base["Date"] = pd.Timestamp(base["Date"])
    return pd.Series(base)


def test_real_extractor_emits_tennis_games_row_matching_contract() -> None:
    """The real ``_extract_tennis_game_data`` must emit a games row that matches the v1 contract."""
    processor = TennisCSVProcessor(MagicMock())

    params = processor._extract_tennis_game_data(
        _row_with_timestamp(), tour="ATP", season="2026"
    )

    expected = build_tennis_games_row()
    assert params["game_id"] == expected["game_id"]
    assert params["tour"] == "ATP"
    assert params["winner"] == expected["winner"]
    assert params["loser"] == expected["loser"]


def test_csv_fixture_matches_consumer_contract() -> None:
    """The deterministic CSV fixture must satisfy the consumer-side contract."""
    Draft202012Validator(_load_schema()).validate(build_tennis_csv_row())


def test_real_processor_skips_rows_missing_required_columns() -> None:
    """``process_row`` must silently skip rows missing Date/Winner/Loser."""
    db = MagicMock()
    processor = TennisCSVProcessor(db)

    incomplete = pd.Series({"Date": pd.NaT, "Winner": "Foo", "Loser": "Bar"})
    processor.process_row(incomplete, tour="ATP", season="2026")

    db.execute.assert_not_called()
