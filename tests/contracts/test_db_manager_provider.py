"""Provider RED tests for the DBManager boundary.

These tests exercise the real :class:`DBManager` producer using an in-memory
SQLite database via SQLAlchemy. Since the production environment uses
PostgreSQL, SQLite serves as a stand-in that exercises the same code paths
for output shape (columns/rows, scalar values, rowcount/success) without
requiring a live PostgreSQL instance.

The contract payloads are assembled from real DBManager method outputs and
validated against the frozen schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest
from jsonschema.exceptions import ValidationError
from sqlalchemy import create_engine, text

from plugins.db_manager import DBManager
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "db_manager_contract_v1.json").read_text(encoding="utf-8")
    )


def _validate_definition(payload: dict[str, Any], definition: str) -> None:
    """Validate a payload against a single $defs entry in the contract schema."""
    schema = _load_schema()
    v_schema: dict[str, Any] = {
        "$schema": schema["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": schema["$defs"],
    }
    validate_contract_payload(payload, v_schema)


def _assemble_fetch_df_payload(df: pd.DataFrame) -> dict[str, Any]:
    """Convert a real DBManager fetch_df output to the contract shape."""
    return {
        "columns": list(df.columns),
        "rows": [list(row) for row in df.itertuples(index=False)],
    }


def _assemble_fetch_scalar_payload(value: Any) -> dict[str, Any]:
    """Wrap a real DBManager fetch_scalar output into the contract shape."""
    return {"value": value}


def _assemble_execution_payload(
    result: Any,
) -> dict[str, Any]:
    """Wrap a real DBManager.execute() output into the contract shape."""
    return {
        "rowcount": result.rowcount,
        "success": True,
    }


@pytest.fixture(scope="module")
def sqlite_db_manager() -> DBManager:
    """Create a DBManager backed by an in-memory SQLite database.

    We bypass DBManager.__init__ to inject the SQLite engine directly,
    since DBManager.__init__ always builds a PostgreSQL connection string
    and uses a global engine registry keyed by connection string.
    """
    engine = create_engine("sqlite://", echo=False)
    db = DBManager.__new__(DBManager)
    db.engine = engine
    db.connection_string = "sqlite://"

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE test_games ("
                "  game_id INTEGER PRIMARY KEY,"
                "  home_team TEXT NOT NULL,"
                "  away_team TEXT NOT NULL,"
                "  home_score INTEGER,"
                "  away_score INTEGER"
                ")"
            )
        )
        conn.execute(
            text(
                "INSERT INTO test_games (game_id, home_team, away_team, home_score, away_score) "
                "VALUES (:game_id, :home_team, :away_team, :home_score, :away_score)"
            ),
            [
                {"game_id": 1, "home_team": "Yankees", "away_team": "Red Sox", "home_score": 5, "away_score": 3},
                {"game_id": 2, "home_team": "Dodgers", "away_team": "Giants", "home_score": 2, "away_score": 1},
            ],
        )

    return db


class TestDbManagerFetchDfProviderContract:
    """Provider-side guarantees for DBManager.fetch_df() outputs."""

    def test_fetch_df_produces_contract_valid_payload(
        self, sqlite_db_manager: DBManager
    ) -> None:
        df = sqlite_db_manager.fetch_df("SELECT * FROM test_games ORDER BY game_id")
        payload = _assemble_fetch_df_payload(df)
        _validate_definition(payload, "fetch_df_result")

    def test_fetch_df_columns_match_schema(
        self, sqlite_db_manager: DBManager
    ) -> None:
        df = sqlite_db_manager.fetch_df("SELECT * FROM test_games ORDER BY game_id")
        payload = _assemble_fetch_df_payload(df)
        assert payload["columns"] == ["game_id", "home_team", "away_team", "home_score", "away_score"]

    def test_fetch_df_rows_contain_expected_data(
        self, sqlite_db_manager: DBManager
    ) -> None:
        df = sqlite_db_manager.fetch_df("SELECT * FROM test_games ORDER BY game_id")
        payload = _assemble_fetch_df_payload(df)
        assert len(payload["rows"]) == 2
        assert payload["rows"][0][1] == "Yankees"
        assert payload["rows"][1][2] == "Giants"

    def test_fetch_df_empty_result_is_contract_valid(
        self, sqlite_db_manager: DBManager
    ) -> None:
        df = sqlite_db_manager.fetch_df(
            "SELECT * FROM test_games WHERE game_id = 999"
        )
        payload = _assemble_fetch_df_payload(df)
        assert len(payload["rows"]) == 0
        assert len(payload["columns"]) == 5
        _validate_definition(payload, "fetch_df_result")

    def test_fetch_df_row_count_matches_inserted_data(
        self, sqlite_db_manager: DBManager
    ) -> None:
        df = sqlite_db_manager.fetch_df("SELECT * FROM test_games")
        assert len(df) == 2


class TestDbManagerFetchScalarProviderContract:
    """Provider-side guarantees for DBManager.fetch_scalar() outputs."""

    def test_fetch_scalar_produces_contract_valid_payload(
        self, sqlite_db_manager: DBManager
    ) -> None:
        value = sqlite_db_manager.fetch_scalar(
            "SELECT COUNT(*) FROM test_games"
        )
        payload = _assemble_fetch_scalar_payload(value)
        _validate_definition(payload, "fetch_scalar_result")

    def test_fetch_scalar_returns_expected_count(
        self, sqlite_db_manager: DBManager
    ) -> None:
        value = sqlite_db_manager.fetch_scalar(
            "SELECT COUNT(*) FROM test_games"
        )
        assert value == 2

    def test_fetch_scalar_returns_none_for_empty_result(
        self, sqlite_db_manager: DBManager
    ) -> None:
        value = sqlite_db_manager.fetch_scalar(
            "SELECT MAX(game_id) FROM test_games WHERE game_id = 999"
        )
        assert value is None

    def test_fetch_scalar_none_is_contract_valid(
        self, sqlite_db_manager: DBManager
    ) -> None:
        value = sqlite_db_manager.fetch_scalar(
            "SELECT MAX(game_id) FROM test_games WHERE game_id = 999"
        )
        payload = _assemble_fetch_scalar_payload(value)
        _validate_definition(payload, "fetch_scalar_result")

    def test_fetch_scalar_returns_string_value(
        self, sqlite_db_manager: DBManager
    ) -> None:
        value = sqlite_db_manager.fetch_scalar(
            "SELECT home_team FROM test_games WHERE game_id = 1"
        )
        assert isinstance(value, str)
        payload = _assemble_fetch_scalar_payload(value)
        _validate_definition(payload, "fetch_scalar_result")

    def test_fetch_scalar_returns_numeric_value(
        self, sqlite_db_manager: DBManager
    ) -> None:
        value = sqlite_db_manager.fetch_scalar(
            "SELECT home_score FROM test_games WHERE game_id = 1"
        )
        assert isinstance(value, int)
        payload = _assemble_fetch_scalar_payload(value)
        _validate_definition(payload, "fetch_scalar_result")


class TestDbManagerExecutionProviderContract:
    """Provider-side guarantees for DBManager.execute() outputs."""

    def test_execute_insert_produces_contract_valid_payload(
        self, sqlite_db_manager: DBManager
    ) -> None:
        result = sqlite_db_manager.execute(
            "INSERT INTO test_games (game_id, home_team, away_team, home_score, away_score) "
            "VALUES (:game_id, :home_team, :away_team, :home_score, :away_score)",
            {"game_id": 3, "home_team": "Cubs", "away_team": "Cardinals", "home_score": 4, "away_score": 2},
        )
        payload = _assemble_execution_payload(result)
        _validate_definition(payload, "execution_result")

    def test_execute_insert_returns_rowcount(
        self, sqlite_db_manager: DBManager
    ) -> None:
        result = sqlite_db_manager.execute(
            "INSERT INTO test_games (game_id, home_team, away_team, home_score, away_score) "
            "VALUES (:game_id, :home_team, :away_team, :home_score, :away_score)",
            {"game_id": 4, "home_team": "Mariners", "away_team": "Angels", "home_score": 3, "away_score": 5},
        )
        payload = _assemble_execution_payload(result)
        assert payload["rowcount"] == 1
        assert payload["success"] is True

    def test_execute_update_returns_affected_rowcount(
        self, sqlite_db_manager: DBManager
    ) -> None:
        result = sqlite_db_manager.execute(
            "UPDATE test_games SET home_score = 6 WHERE game_id = 1"
        )
        payload = _assemble_execution_payload(result)
        assert payload["rowcount"] >= 1
        assert payload["success"] is True

    def test_execute_delete_returns_rowcount(
        self, sqlite_db_manager: DBManager
    ) -> None:
        # Insert a row we can safely delete
        sqlite_db_manager.execute(
            "INSERT INTO test_games (game_id, home_team, away_team, home_score, away_score) "
            "VALUES (:game_id, :home_team, :away_team, :home_score, :away_score)",
            {"game_id": 99, "home_team": "Test", "away_team": "Team", "home_score": 0, "away_score": 0},
        )
        result = sqlite_db_manager.execute(
            "DELETE FROM test_games WHERE game_id = 99"
        )
        payload = _assemble_execution_payload(result)
        assert payload["rowcount"] == 1
        assert payload["success"] is True

    def test_execute_select_returns_contract_valid_payload(
        self, sqlite_db_manager: DBManager
    ) -> None:
        result = sqlite_db_manager.execute(
            "SELECT * FROM test_games WHERE game_id = 1"
        )
        payload = _assemble_execution_payload(result)
        _validate_definition(payload, "execution_result")

    def test_execute_ddl_returns_contract_valid_payload(
        self, sqlite_db_manager: DBManager
    ) -> None:
        db = sqlite_db_manager
        db.execute("CREATE TABLE IF NOT EXISTS _contract_test_ddl (x INTEGER)")
        # DDL statements may return rowcount of -1
        result = db.execute("DROP TABLE IF EXISTS _contract_test_ddl")
        payload = _assemble_execution_payload(result)
        _validate_definition(payload, "execution_result")

    def test_producer_assembled_payload_rejects_drift(self) -> None:
        """A deliberately broken payload must be rejected by the schema."""
        invalid: Dict[str, Any] = {"rowcount": "not-an-int", "success": "not-a-bool"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "execution_result")
