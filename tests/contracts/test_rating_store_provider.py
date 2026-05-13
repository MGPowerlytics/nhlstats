"""Provider RED tests for the RatingStore boundary.

These tests exercise the real :class:`RatingStore` producer directly using its
in-memory dictionary store — no database needed. The contract payloads are
assembled from real RatingStore method outputs and validated against the
frozen schema.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pytest
from jsonschema.exceptions import ValidationError

from plugins.elo.elo_dataclasses import EloConfig
from plugins.elo.rating_store import RatingStore
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "rating_store_contract_v1.json").read_text(encoding="utf-8")
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


def _assemble_save_rating_payload(
    store: RatingStore, team: str, sport: str
) -> dict[str, Any]:
    """Construct a save_rating_result payload from a real RatingStore operation.

    Saves a rating, then captures the output shape that a consumer would
    receive after the operation completes.
    """
    rating = store.get_rating(team)
    return {
        "team": team,
        "rating": rating,
        "sport": sport,
        "timestamp": datetime.now().isoformat(),
        "schema_version": "v1",
        "payload_kind": "save_rating_result",
    }


def _assemble_load_rating_payload(
    store: RatingStore, team: str, sport: str
) -> dict[str, Any]:
    """Construct a load_rating_result payload from a real RatingStore lookup."""
    found = store.has_rating(team)
    rating = store.get_rating(team) if found else None
    return {
        "team": team,
        "rating": rating,
        "sport": sport,
        "found": found,
        "schema_version": "v1",
        "payload_kind": "load_rating_result",
    }


def _assemble_load_all_ratings_payload(
    store: RatingStore, sport: str
) -> dict[str, Any]:
    """Construct a load_all_ratings_result payload from a real RatingStore."""
    ratings = store.get_all_ratings()
    return {
        "sport": sport,
        "ratings": dict(ratings),
        "count": len(ratings),
        "schema_version": "v1",
        "payload_kind": "load_all_ratings_result",
    }


@pytest.fixture
def rating_store() -> RatingStore:
    """Create a fresh RatingStore for each test."""
    config = EloConfig(initial_rating=1500.0)
    return RatingStore(config=config)


@pytest.fixture
def populated_store(rating_store: RatingStore) -> RatingStore:
    """Return a RatingStore pre-populated with sample team ratings."""
    rating_store.set_rating("NYY", 1520.0)
    rating_store.set_rating("BOS", 1485.0)
    rating_store.set_rating("LAD", 1510.0)
    rating_store.set_rating("SFG", 1475.0)
    return rating_store


class TestRatingStoreSaveRatingProviderContract:
    """Provider-side guarantees for RatingStore.set_rating() outputs."""

    def test_save_rating_produces_contract_valid_payload(
        self, rating_store: RatingStore
    ) -> None:
        rating_store.set_rating("NYY", 1520.0)
        payload = _assemble_save_rating_payload(rating_store, "NYY", "MLB")
        _validate_definition(payload, "save_rating_result")

    def test_save_rating_returns_stored_value(self, rating_store: RatingStore) -> None:
        rating_store.set_rating("LAL", 1580.0)
        payload = _assemble_save_rating_payload(rating_store, "LAL", "NBA")
        assert payload["rating"] == 1580.0
        assert payload["team"] == "LAL"
        assert payload["sport"] == "NBA"

    def test_save_rating_overwrites_previous_value(
        self, rating_store: RatingStore
    ) -> None:
        rating_store.set_rating("KC", 1450.0)
        rating_store.set_rating("KC", 1600.0)
        payload = _assemble_save_rating_payload(rating_store, "KC", "NFL")
        assert payload["rating"] == 1600.0

    def test_save_rating_updates_existing_rating_via_update(
        self, rating_store: RatingStore
    ) -> None:
        rating_store.set_rating("MIL", 1500.0)
        rating_store.update_rating("MIL", 25.0)
        payload = _assemble_save_rating_payload(rating_store, "MIL", "MLB")
        assert payload["rating"] == 1525.0

    def test_save_rating_with_minimal_rating(self, rating_store: RatingStore) -> None:
        rating_store.set_rating("MIN", 0.01)
        payload = _assemble_save_rating_payload(rating_store, "MIN", "NHL")
        _validate_definition(payload, "save_rating_result")
        assert payload["rating"] == 0.01

    def test_save_rating_rejects_negative_rating(
        self, rating_store: RatingStore
    ) -> None:
        with pytest.raises(ValueError, match="Rating cannot be negative"):
            rating_store.set_rating("BAD", -100.0)

    def test_save_rating_rejects_empty_team_name(
        self, rating_store: RatingStore
    ) -> None:
        with pytest.raises(ValueError, match="Team name cannot be empty"):
            rating_store.set_rating("", 1500.0)

    def test_save_rating_rejects_non_numeric_rating(
        self, rating_store: RatingStore
    ) -> None:
        with pytest.raises(TypeError, match="Rating must be numeric"):
            rating_store.set_rating("NYY", "high")  # type: ignore[arg-type]

    def test_producer_assembled_save_payload_rejects_drift(self) -> None:
        """A deliberately broken payload must be rejected by the schema."""
        invalid: Dict[str, Any] = {
            "team": "",
            "rating": 0,
            "sport": "",
            "timestamp": "bad",
            "schema_version": "v2",
            "payload_kind": "wrong_kind",
        }
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "save_rating_result")


class TestRatingStoreLoadRatingProviderContract:
    """Provider-side guarantees for RatingStore.get_rating() outputs."""

    def test_load_rating_produces_contract_valid_payload_found(
        self, populated_store: RatingStore
    ) -> None:
        payload = _assemble_load_rating_payload(populated_store, "NYY", "MLB")
        _validate_definition(payload, "load_rating_result")

    def test_load_rating_returns_correct_value(
        self, populated_store: RatingStore
    ) -> None:
        payload = _assemble_load_rating_payload(populated_store, "LAD", "MLB")
        assert payload["rating"] == 1510.0
        assert payload["found"] is True
        assert payload["team"] == "LAD"

    def test_load_rating_not_found_returns_none(
        self, rating_store: RatingStore
    ) -> None:
        payload = _assemble_load_rating_payload(rating_store, "UNKN", "MLB")
        assert payload["rating"] is None
        assert payload["found"] is False

    def test_load_rating_not_found_is_contract_valid(
        self, rating_store: RatingStore
    ) -> None:
        payload = _assemble_load_rating_payload(rating_store, "UNKN", "MLB")
        _validate_definition(payload, "load_rating_result")

    def test_load_rating_returns_none_for_new_team(
        self, rating_store: RatingStore
    ) -> None:
        """A team that hasn't been explicitly set returns None (found=False)."""
        payload = _assemble_load_rating_payload(rating_store, "NEW", "NFL")
        assert payload["rating"] is None
        assert payload["found"] is False

    def test_load_rating_after_clear_returns_default(
        self, populated_store: RatingStore
    ) -> None:
        populated_store.clear_ratings()
        payload = _assemble_load_rating_payload(populated_store, "NYY", "MLB")
        assert payload["found"] is False

    def test_producer_assembled_load_payload_rejects_drift(self) -> None:
        """A deliberately broken payload must be rejected by the schema."""
        invalid: Dict[str, Any] = {
            "team": "",
            "rating": "not-a-number",
            "sport": "",
            "found": "not-a-bool",
            "schema_version": "v2",
            "payload_kind": "wrong_kind",
        }
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_rating_result")


class TestRatingStoreLoadAllRatingsProviderContract:
    """Provider-side guarantees for RatingStore.get_all_ratings() outputs."""

    def test_load_all_ratings_produces_contract_valid_payload(
        self, populated_store: RatingStore
    ) -> None:
        payload = _assemble_load_all_ratings_payload(populated_store, "MLB")
        _validate_definition(payload, "load_all_ratings_result")

    def test_load_all_ratings_count_matches_inserted(
        self, populated_store: RatingStore
    ) -> None:
        payload = _assemble_load_all_ratings_payload(populated_store, "MLB")
        assert payload["count"] == 4
        assert len(payload["ratings"]) == 4

    def test_load_all_ratings_contains_expected_teams(
        self, populated_store: RatingStore
    ) -> None:
        payload = _assemble_load_all_ratings_payload(populated_store, "MLB")
        assert "NYY" in payload["ratings"]
        assert "BOS" in payload["ratings"]
        assert "LAD" in payload["ratings"]
        assert "SFG" in payload["ratings"]

    def test_load_all_ratings_values_are_correct(
        self, populated_store: RatingStore
    ) -> None:
        payload = _assemble_load_all_ratings_payload(populated_store, "MLB")
        assert payload["ratings"]["NYY"] == 1520.0
        assert payload["ratings"]["BOS"] == 1485.0
        assert payload["ratings"]["LAD"] == 1510.0
        assert payload["ratings"]["SFG"] == 1475.0

    def test_load_all_ratings_empty_store(self, rating_store: RatingStore) -> None:
        payload = _assemble_load_all_ratings_payload(rating_store, "NBA")
        assert payload["count"] == 0
        assert payload["ratings"] == {}

    def test_load_all_ratings_empty_store_is_contract_valid(
        self, rating_store: RatingStore
    ) -> None:
        payload = _assemble_load_all_ratings_payload(rating_store, "NBA")
        _validate_definition(payload, "load_all_ratings_result")

    def test_load_all_ratings_after_clear(self, populated_store: RatingStore) -> None:
        populated_store.clear_ratings()
        payload = _assemble_load_all_ratings_payload(populated_store, "MLB")
        assert payload["count"] == 0
        assert payload["ratings"] == {}
        _validate_definition(payload, "load_all_ratings_result")

    def test_load_all_ratings_with_single_team(self, rating_store: RatingStore) -> None:
        rating_store.set_rating("GSW", 1550.0)
        payload = _assemble_load_all_ratings_payload(rating_store, "NBA")
        assert payload["count"] == 1
        assert payload["ratings"]["GSW"] == 1550.0
        _validate_definition(payload, "load_all_ratings_result")

    def test_load_all_ratings_returns_copy_not_reference(
        self, populated_store: RatingStore
    ) -> None:
        payload = _assemble_load_all_ratings_payload(populated_store, "MLB")
        # Modifying the returned dict should not affect internal state
        payload["ratings"]["NYY"] = 9999.0
        assert populated_store.get_rating("NYY") == 1520.0

    def test_producer_assembled_load_all_payload_rejects_drift(self) -> None:
        """A deliberately broken payload must be rejected by the schema."""
        invalid: Dict[str, Any] = {
            "sport": "",
            "ratings": "not-a-dict",
            "count": -1,
            "schema_version": "v2",
            "payload_kind": "wrong_kind",
        }
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_all_ratings_result")
