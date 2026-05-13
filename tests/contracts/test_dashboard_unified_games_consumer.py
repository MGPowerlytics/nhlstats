"""Dashboard consumer-side contract tests for unified_games rows.

The dashboard consumes unified_games rows via load_data() for Elo analysis.
These tests verify the dashboard correctly enforces the contract schemas for
each sport's game rows, validating field types, required fields, and constraints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from tests.contracts.helpers import validate_contract_payload

# Sport-specific schemas consumed by dashboard
SCHEMAS_DIR = Path(__file__).parent / "schemas"


# ------------------------------------------------------------------
# Schema loaders
# ------------------------------------------------------------------


@pytest.fixture(scope="module")
def epl_unified_schema() -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / "epl_unified_game_row_v1.json").read_text())


@pytest.fixture(scope="module")
def mlb_unified_schema() -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / "mlb_unified_game_row_v1.json").read_text())


@pytest.fixture(scope="module")
def tennis_unified_schema() -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / "tennis_unified_game_row_v1.json").read_text())


# ------------------------------------------------------------------
# Valid payload factories (unified_games row fields only — no raw variants)
# ------------------------------------------------------------------


@pytest.fixture
def valid_epl_row() -> dict[str, Any]:
    """Canonical EPL unified_games row (home/away_team_name only — no raw variants)."""
    return {
        "game_id": "EPL_20251018_LIVERPOOL_ARSENAL",
        "sport": "EPL",
        "game_date": "2025-10-18",
        "season": 2025,
        "status": "Final",
        "home_team_name": "Liverpool",
        "away_team_name": "Arsenal",
        "home_score": 2,
        "away_score": 2,
    }


@pytest.fixture
def valid_mlb_row() -> dict[str, Any]:
    return {
        "game_id": "745431",
        "sport": "MLB",
        "game_date": "2025-04-15",
        "season": 2025,
        "status": "Final",
        "home_team_id": "147",
        "home_team_name": "New York Yankees",
        "away_team_id": "118",
        "away_team_name": "Boston Red Sox",
        "home_score": 5,
        "away_score": 3,
    }


@pytest.fixture
def valid_tennis_row() -> dict[str, Any]:
    return {
        "game_id": "TENNIS_ATP_2026-04-07_AlexanderBlockx_FlavioCobolli",
        "sport": "TENNIS",
        "game_date": "2026-04-07",
        "home_team_name": "Alexander Blockx",
        "away_team_name": "Flavio Cobolli",
    }


# ------------------------------------------------------------------
# EPL unified_games consumer tests
# ------------------------------------------------------------------


class TestEPLUnifiedGamesConsumer:
    """Consumer contract tests: dashboard reading EPL unified_games rows."""

    def test_valid_epl_row_passes_contract(
        self, valid_epl_row: dict[str, Any], epl_unified_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(valid_epl_row, epl_unified_schema)

    def test_epl_row_requires_game_id(
        self, valid_epl_row: dict[str, Any], epl_unified_schema: dict[str, Any]
    ) -> None:
        row = {k: v for k, v in valid_epl_row.items() if k != "game_id"}
        with pytest.raises(ValidationError):
            validate_contract_payload(row, epl_unified_schema)

    def test_epl_row_requires_sport(
        self, valid_epl_row: dict[str, Any], epl_unified_schema: dict[str, Any]
    ) -> None:
        row = {k: v for k, v in valid_epl_row.items() if k != "sport"}
        with pytest.raises(ValidationError):
            validate_contract_payload(row, epl_unified_schema)

    def test_epl_row_freezes_sport_const(
        self, epl_unified_schema: dict[str, Any]
    ) -> None:
        assert epl_unified_schema["properties"]["sport"]["const"] == "EPL"
        assert "sport" in epl_unified_schema["required"]

    def test_epl_row_game_id_pattern(
        self, valid_epl_row: dict[str, Any], epl_unified_schema: dict[str, Any]
    ) -> None:
        # Valid pattern
        validate_contract_payload(valid_epl_row, epl_unified_schema)
        # Invalid pattern — wrong prefix
        bad = {**valid_epl_row, "game_id": "NBA_20251018_Lakers_Celtics"}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, epl_unified_schema)

    def test_epl_row_game_date_valid_isostring(
        self, valid_epl_row: dict[str, Any], epl_unified_schema: dict[str, Any]
    ) -> None:
        """ISO date strings are accepted by the schema (format checking requires format_checker)."""
        validate_contract_payload(valid_epl_row, epl_unified_schema)
        # Valid alternative ISO format
        validate_contract_payload({**valid_epl_row, "game_date": "2025-10-18"}, epl_unified_schema)

    def test_epl_row_rejects_unknown_fields(
        self, valid_epl_row: dict[str, Any], epl_unified_schema: dict[str, Any]
    ) -> None:
        assert epl_unified_schema["additionalProperties"] is False
        bad = {**valid_epl_row, "mystery_column": "surprise"}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, epl_unified_schema)

    def test_epl_row_status_is_final_const(
        self, epl_unified_schema: dict[str, Any]
    ) -> None:
        assert epl_unified_schema["properties"]["status"]["const"] == "Final"

    def test_epl_row_team_names_must_be_recognized_club(
        self, valid_epl_row: dict[str, Any], epl_unified_schema: dict[str, Any]
    ) -> None:
        # Valid club name
        validate_contract_payload(valid_epl_row, epl_unified_schema)
        # Unknown club name
        bad = {**valid_epl_row, "home_team_name": "Unknown FC"}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, epl_unified_schema)


# ------------------------------------------------------------------
# MLB unified_games consumer tests
# ------------------------------------------------------------------


class TestMLBUnifiedGamesConsumer:
    """Consumer contract tests: dashboard reading MLB unified_games rows."""

    def test_valid_mlb_row_passes_contract(
        self, valid_mlb_row: dict[str, Any], mlb_unified_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(valid_mlb_row, mlb_unified_schema)

    def test_mlb_row_requires_required_fields(
        self, valid_mlb_row: dict[str, Any], mlb_unified_schema: dict[str, Any]
    ) -> None:
        for field in mlb_unified_schema["required"]:
            bad = {k: v for k, v in valid_mlb_row.items() if k != field}
            with pytest.raises(ValidationError):
                validate_contract_payload(bad, mlb_unified_schema)

    def test_mlb_row_freezes_sport_const(
        self, mlb_unified_schema: dict[str, Any]
    ) -> None:
        assert mlb_unified_schema["properties"]["sport"]["const"] == "MLB"

    def test_mlb_row_game_id_pattern(
        self, valid_mlb_row: dict[str, Any], mlb_unified_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(valid_mlb_row, mlb_unified_schema)
        bad = {**valid_mlb_row, "game_id": "not-a-number"}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, mlb_unified_schema)

    def test_mlb_row_rejects_unknown_fields(
        self, valid_mlb_row: dict[str, Any], mlb_unified_schema: dict[str, Any]
    ) -> None:
        bad = {**valid_mlb_row, "unknown_col": "nope"}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, mlb_unified_schema)

    def test_mlb_row_scores_nullable(
        self, valid_mlb_row: dict[str, Any], mlb_unified_schema: dict[str, Any]
    ) -> None:
        row = {**valid_mlb_row, "home_score": None, "away_score": None}
        validate_contract_payload(row, mlb_unified_schema)

    def test_mlb_row_team_ids_nullable(
        self, valid_mlb_row: dict[str, Any], mlb_unified_schema: dict[str, Any]
    ) -> None:
        row = {**valid_mlb_row, "home_team_id": None, "away_team_id": None}
        validate_contract_payload(row, mlb_unified_schema)


# ------------------------------------------------------------------
# Tennis unified_games consumer tests
# ------------------------------------------------------------------


class TestTennisUnifiedGamesConsumer:
    """Consumer contract tests: dashboard reading Tennis unified_games rows."""

    def test_valid_tennis_row_passes_contract(
        self, valid_tennis_row: dict[str, Any], tennis_unified_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(valid_tennis_row, tennis_unified_schema)

    def test_tennis_row_requires_minimal_fields(
        self, valid_tennis_row: dict[str, Any], tennis_unified_schema: dict[str, Any]
    ) -> None:
        required = ["game_id", "sport", "game_date", "home_team_name", "away_team_name"]
        for field in required:
            bad = {k: v for k, v in valid_tennis_row.items() if k != field}
            with pytest.raises(ValidationError):
                validate_contract_payload(bad, tennis_unified_schema)

    def test_tennis_row_game_id_matches_unified_pattern(
        self, valid_tennis_row: dict[str, Any], tennis_unified_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(valid_tennis_row, tennis_unified_schema)
        # Bad pattern — missing TENNIS_ prefix
        bad = {**valid_tennis_row, "game_id": "ATP_2026-04-07_Blockx_Cobolli"}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, tennis_unified_schema)

    def test_tennis_row_freezes_sport_const(
        self, tennis_unified_schema: dict[str, Any]
    ) -> None:
        assert tennis_unified_schema["properties"]["sport"]["const"] == "TENNIS"

    def test_tennis_row_rejects_unknown_fields(
        self, valid_tennis_row: dict[str, Any], tennis_unified_schema: dict[str, Any]
    ) -> None:
        bad = {**valid_tennis_row, "not_a_field": True}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, tennis_unified_schema)

    def test_tennis_row_allows_optional_season(
        self, valid_tennis_row: dict[str, Any], tennis_unified_schema: dict[str, Any]
    ) -> None:
        row = {**valid_tennis_row, "season": 2026}
        validate_contract_payload(row, tennis_unified_schema)

    def test_tennis_row_allows_null_scores(
        self, valid_tennis_row: dict[str, Any], tennis_unified_schema: dict[str, Any]
    ) -> None:
        row = {**valid_tennis_row, "home_score": None, "away_score": None}
        validate_contract_payload(row, tennis_unified_schema)
