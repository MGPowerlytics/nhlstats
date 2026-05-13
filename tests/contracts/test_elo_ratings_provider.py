"""Provider contract tests for the elo_ratings database table.

Ensures that the elo_ratings table maintains its column contract and
SCD Type 2 properties.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from plugins.db_manager import DBManager
from plugins.elo.elo_update_helpers import save_ratings_to_db
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "elo_ratings_row_v1.json").read_text(encoding="utf-8")
    )


def _validate_row(row: dict[str, Any]) -> None:
    """Validate a single database row against the contract schema."""
    schema = _load_schema()
    validate_contract_payload(row, schema)


@pytest.fixture
def contract_db() -> DBManager:
    """Create a DBManager for contract testing (SQLite)."""
    engine = create_engine("sqlite://", echo=False)
    db = DBManager.__new__(DBManager)
    db.engine = engine
    db.connection_string = "sqlite://"

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE elo_ratings ("
                "  rating_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  sport TEXT NOT NULL,"
                "  entity_id TEXT NOT NULL,"
                "  entity_name TEXT NOT NULL,"
                "  rating DECIMAL(10,2) NOT NULL,"
                "  valid_from DATE NOT NULL,"
                "  valid_to DATE,"
                "  games_played INTEGER,"
                "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
    return db


class TestEloRatingsProviderContract:
    """Tests that the database output matches the elo_ratings contract."""

    def test_save_ratings_produces_contract_valid_rows(
        self, contract_db: DBManager, monkeypatch
    ) -> None:
        # Mock default_db to use our contract_db
        monkeypatch.setattr("plugins.db_manager.default_db", contract_db)

        ratings = {"ALCARAZ": 2100.5, "ZVEREV": 2050.2}
        save_ratings_to_db("TENNIS", ratings, reference_date=date(2026, 4, 26))

        df = contract_db.fetch_df("SELECT * FROM elo_ratings")
        assert len(df) == 2

        for _, row in df.iterrows():
            row_dict = row.to_dict()
            # Convert date objects to strings for JSON validation
            row_dict["valid_from"] = str(row_dict["valid_from"])
            if row_dict["valid_to"]:
                row_dict["valid_to"] = str(row_dict["valid_to"])
            row_dict["created_at"] = "2026-04-26T12:00:00Z" # Mock for validation

            _validate_row(row_dict)

    def test_scd_update_preserves_contract(
        self, contract_db: DBManager, monkeypatch
    ) -> None:
        monkeypatch.setattr("plugins.db_manager.default_db", contract_db)

        # Initial rating
        save_ratings_to_db("MLB", {"NYY": 1500.0}, reference_date=date(2026, 4, 1))

        # Update rating
        save_ratings_to_db("MLB", {"NYY": 1510.0}, reference_date=date(2026, 4, 2))

        df = contract_db.fetch_df("SELECT * FROM elo_ratings ORDER BY valid_from")
        assert len(df) == 2

        for _, row in df.iterrows():
            row_dict = row.to_dict()
            row_dict["valid_from"] = str(row_dict["valid_from"])
            if row_dict["valid_to"]:
                row_dict["valid_to"] = str(row_dict["valid_to"])
            row_dict["created_at"] = "2026-04-26T12:00:00Z"
            _validate_row(row_dict)

        # Verify SCD logic
        rows = df.to_dict('records')
        assert str(rows[0]['valid_to']) == '2026-04-02'

        # Handle pandas converting NULL to NaN
        valid_to_1 = rows[1]['valid_to']
        assert valid_to_1 is None or pd.isna(valid_to_1)

        assert str(rows[1]['valid_from']) == '2026-04-02'
