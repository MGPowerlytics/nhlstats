"""Provider contract tests for the BoxScoreFetcher ABC boundary.

Validates that a real BoxScoreFetcher implementation produces outputs that
satisfy the frozen contract.  Uses a minimal concrete subclass that returns
deterministic canned data — no real API calls.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from plugins.stats.base import BoxScoreFetcher

SCHEMA_PATH = Path(__file__).parent / "schemas" / "box_score_fetcher_contract_v1.json"

# ---------------------------------------------------------------------------
# Helper: build a definition-scoped schema from the composite contract
# ---------------------------------------------------------------------------


def _build_definition_schema(
    contract: dict[str, Any], definition: str
) -> dict[str, Any]:
    return {
        "$schema": contract["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": contract["$defs"],
    }


def _validate_definition(
    payload: dict[str, Any],
    contract: dict[str, Any],
    definition: str,
) -> None:
    Draft202012Validator(
        _build_definition_schema(contract, definition),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    ).validate(payload)


# ---------------------------------------------------------------------------
# Minimal concrete subclass — no real API calls
# ---------------------------------------------------------------------------


class TestBoxScoreFetcher(BoxScoreFetcher):
    """A minimal BoxScoreFetcher that returns deterministic canned data.

    This subclass exists solely for contract-testing the ABC boundary.
    It does NOT inherit from any sport-specific fetcher and makes no
    network or database calls.
    """

    SPORT = "TEST"
    RATE_LIMIT_SECONDS = 0.0
    EXT_TABLE = "test_team_game_stats_ext"

    def fetch_game_stats(self, game_id: str) -> list[dict[str, Any]]:
        if not game_id:
            return []
        return [
            {
                "team": "Home Team",
                "opponent": "Away Team",
                "home": True,
                "points": 105,
            },
            {
                "team": "Away Team",
                "opponent": "Home Team",
                "home": False,
                "points": 98,
            },
        ]

    def fetch_date_range(self, start: date, end: date) -> list[dict[str, Any]]:
        if start > end:
            return []
        return [
            {
                "team": "Home Team",
                "opponent": "Away Team",
                "home": True,
                "points": 105,
            },
            {
                "team": "Away Team",
                "opponent": "Home Team",
                "home": False,
                "points": 98,
            },
        ]

    def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        return len(rows)


# ---------------------------------------------------------------------------
# Assemble contract payloads from provider output
# ---------------------------------------------------------------------------


def _assemble_fetch_game_stats_payload(
    fetcher: TestBoxScoreFetcher, game_id: str
) -> dict[str, Any]:
    """Wrap real fetch_game_stats output into the contract shape."""
    rows = fetcher.fetch_game_stats(game_id)
    return {
        "game_id": game_id,
        "sport": fetcher.SPORT,
        "rows": rows,
        "row_count": len(rows),
        "schema_version": "v1",
        "payload_kind": "fetch_game_stats_result",
    }


def _assemble_fetch_date_range_payload(
    fetcher: TestBoxScoreFetcher, start: date, end: date
) -> dict[str, Any]:
    """Wrap real fetch_date_range output into the contract shape."""
    rows = fetcher.fetch_date_range(start, end)
    # Group rows by game — since our canned data has two rows (home/away) per game
    # we build a single game bucket.
    games: list[dict[str, Any]] = []
    if rows:
        games.append(
            {
                "game_id": f"TEST_{start.isoformat()}_GAME",
                "rows": rows,
            }
        )
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_games": len(games),
        "total_rows": len(rows),
        "games": games,
        "schema_version": "v1",
        "payload_kind": "fetch_date_range_result",
    }


def _assemble_upsert_rows_payload(
    fetcher: TestBoxScoreFetcher, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Wrap real upsert_rows output into the contract shape."""
    count = fetcher.upsert_rows(rows)
    return {
        "rows_inserted": count,
        "sport": fetcher.SPORT,
        "schema_version": "v1",
        "payload_kind": "upsert_rows_result",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def contract_schema() -> dict[str, Any]:
    """Load the composite BoxScoreFetcher contract schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def provider() -> TestBoxScoreFetcher:
    """Create a TestBoxScoreFetcher instance (no DB, no network)."""
    return TestBoxScoreFetcher(db=None)


# ---------------------------------------------------------------------------
# Provider contract: fetch_game_stats
# ---------------------------------------------------------------------------


class TestFetchGameStatsProviderContract:
    """Provider guarantees for ``fetch_game_stats`` outputs."""

    def test_fetch_game_stats_output_is_contract_valid(
        self,
        contract_schema: dict[str, Any],
        provider: TestBoxScoreFetcher,
    ) -> None:
        payload = _assemble_fetch_game_stats_payload(provider, "TEST_001")
        _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_fetch_game_stats_rows_are_box_score_rows(
        self,
        contract_schema: dict[str, Any],
        provider: TestBoxScoreFetcher,
    ) -> None:
        payload = _assemble_fetch_game_stats_payload(provider, "TEST_001")
        for row in payload["rows"]:
            _validate_definition(row, contract_schema, "box_score_row")

    def test_fetch_game_stats_returns_two_rows(
        self,
        provider: TestBoxScoreFetcher,
    ) -> None:
        payload = _assemble_fetch_game_stats_payload(provider, "TEST_001")
        assert payload["row_count"] == 2
        assert len(payload["rows"]) == 2

    def test_fetch_game_stats_row_has_required_fields(
        self,
        provider: TestBoxScoreFetcher,
    ) -> None:
        rows = provider.fetch_game_stats("TEST_001")
        for row in rows:
            assert "team" in row
            assert "opponent" in row
            assert "home" in row
            assert "points" in row

    def test_fetch_game_stats_home_and_away_present(
        self,
        provider: TestBoxScoreFetcher,
    ) -> None:
        rows = provider.fetch_game_stats("TEST_001")
        home_teams = [r for r in rows if r["home"]]
        away_teams = [r for r in rows if not r["home"]]
        assert len(home_teams) == 1
        assert len(away_teams) == 1

    def test_fetch_game_stats_empty_game_id_returns_empty(
        self,
        contract_schema: dict[str, Any],
        provider: TestBoxScoreFetcher,
    ) -> None:
        payload = _assemble_fetch_game_stats_payload(provider, "")
        assert payload["row_count"] == 0
        assert payload["rows"] == []
        # Empty game_id violates minLength: 1 — the contract should reject it.
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")


# ---------------------------------------------------------------------------
# Provider contract: fetch_date_range
# ---------------------------------------------------------------------------


class TestFetchDateRangeProviderContract:
    """Provider guarantees for ``fetch_date_range`` outputs."""

    def test_fetch_date_range_output_is_contract_valid(
        self,
        contract_schema: dict[str, Any],
        provider: TestBoxScoreFetcher,
    ) -> None:
        payload = _assemble_fetch_date_range_payload(
            provider, date(2025, 1, 15), date(2025, 1, 15)
        )
        _validate_definition(payload, contract_schema, "fetch_date_range_result")

    def test_fetch_date_range_rows_are_box_score_rows(
        self,
        contract_schema: dict[str, Any],
        provider: TestBoxScoreFetcher,
    ) -> None:
        payload = _assemble_fetch_date_range_payload(
            provider, date(2025, 1, 15), date(2025, 1, 15)
        )
        for game in payload["games"]:
            for row in game["rows"]:
                _validate_definition(row, contract_schema, "box_score_row")

    def test_fetch_date_range_empty_range_is_contract_valid(
        self,
        contract_schema: dict[str, Any],
        provider: TestBoxScoreFetcher,
    ) -> None:
        payload = _assemble_fetch_date_range_payload(
            provider, date(2025, 1, 16), date(2025, 1, 15)  # end before start
        )
        assert payload["total_games"] == 0
        assert payload["total_rows"] == 0
        assert payload["games"] == []
        _validate_definition(payload, contract_schema, "fetch_date_range_result")

    def test_fetch_date_range_uses_date_format(
        self,
        contract_schema: dict[str, Any],
        provider: TestBoxScoreFetcher,
    ) -> None:
        payload = _assemble_fetch_date_range_payload(
            provider, date(2025, 1, 15), date(2025, 1, 15)
        )
        assert payload["start_date"] == "2025-01-15"
        assert payload["end_date"] == "2025-01-15"
        _validate_definition(payload, contract_schema, "fetch_date_range_result")


# ---------------------------------------------------------------------------
# Provider contract: upsert_rows
# ---------------------------------------------------------------------------


class TestUpsertRowsProviderContract:
    """Provider guarantees for ``upsert_rows`` outputs."""

    def test_upsert_rows_output_is_contract_valid(
        self,
        contract_schema: dict[str, Any],
        provider: TestBoxScoreFetcher,
    ) -> None:
        rows = provider.fetch_game_stats("TEST_001")
        payload = _assemble_upsert_rows_payload(provider, rows)
        _validate_definition(payload, contract_schema, "upsert_rows_result")

    def test_upsert_rows_returns_insert_count(
        self,
        provider: TestBoxScoreFetcher,
    ) -> None:
        rows = provider.fetch_game_stats("TEST_001")
        count = provider.upsert_rows(rows)
        assert count == 2

    def test_upsert_rows_empty_input_is_contract_valid(
        self,
        contract_schema: dict[str, Any],
        provider: TestBoxScoreFetcher,
    ) -> None:
        payload = _assemble_upsert_rows_payload(provider, [])
        assert payload["rows_inserted"] == 0
        _validate_definition(payload, contract_schema, "upsert_rows_result")

    def test_upsert_rows_sport_constant(
        self,
        provider: TestBoxScoreFetcher,
    ) -> None:
        payload = _assemble_upsert_rows_payload(provider, [])
        assert payload["sport"] == "TEST"


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


class TestDriftDetection:
    """Schema-level drift detection for the BoxScoreFetcher boundary."""

    def test_schema_rejects_missing_game_id(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = {
            "sport": "TEST",
            "rows": [],
            "row_count": 0,
            "schema_version": "v1",
            "payload_kind": "fetch_game_stats_result",
        }
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_schema_rejects_extra_top_level_field(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = {
            "game_id": "TEST_001",
            "sport": "TEST",
            "rows": [],
            "row_count": 0,
            "schema_version": "v1",
            "payload_kind": "fetch_game_stats_result",
            "extra_field": "drift",
        }
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_schema_rejects_missing_rows_inserted(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = {
            "sport": "TEST",
            "schema_version": "v1",
            "payload_kind": "upsert_rows_result",
        }
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "upsert_rows_result")

    def test_schema_rejects_negative_rows_inserted(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = {
            "rows_inserted": -1,
            "sport": "TEST",
            "schema_version": "v1",
            "payload_kind": "upsert_rows_result",
        }
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "upsert_rows_result")

    def test_schema_rejects_wrong_payload_kind(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = {
            "game_id": "TEST_001",
            "sport": "TEST",
            "rows": [],
            "row_count": 0,
            "schema_version": "v1",
            "payload_kind": "upsert_rows_result",  # should be fetch_game_stats_result
        }
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")
