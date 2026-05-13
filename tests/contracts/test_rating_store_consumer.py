"""Consumer contract tests for the RatingStore boundary.

Consumers trust the RatingStore to return structured results for three
payload kinds:
  - save_rating_result: team, rating, sport, timestamp
  - load_rating_result: team, rating (number|null), sport, found
  - load_all_ratings_result: sport, ratings (dict), count
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.rating_store_samples import (
    build_load_all_ratings_payload,
    build_load_rating_payload_found,
    build_load_rating_payload_not_found,
    build_save_rating_payload,
)
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


class TestRatingStoreSaveRatingConsumerContract:
    """Consumer guarantees for RatingStore.set_rating() outputs."""

    def test_canonical_save_payload_passes_contract(self) -> None:
        payload = build_save_rating_payload()
        _validate_definition(payload, "save_rating_result")

    def test_save_rating_is_positive_number(self) -> None:
        payload = build_save_rating_payload()
        assert isinstance(payload["rating"], (int, float))
        assert payload["rating"] > 0

    def test_save_team_is_non_empty_string(self) -> None:
        payload = build_save_rating_payload()
        assert isinstance(payload["team"], str)
        assert len(payload["team"]) >= 1

    def test_save_sport_is_non_empty_string(self) -> None:
        payload = build_save_rating_payload()
        assert isinstance(payload["sport"], str)
        assert len(payload["sport"]) >= 1

    def test_save_timestamp_is_string(self) -> None:
        payload = build_save_rating_payload()
        assert isinstance(payload["timestamp"], str)

    def test_save_has_correct_schema_version(self) -> None:
        payload = build_save_rating_payload()
        assert payload["schema_version"] == "v1"

    def test_save_has_correct_payload_kind(self) -> None:
        payload = build_save_rating_payload()
        assert payload["payload_kind"] == "save_rating_result"

    def test_save_missing_team_is_rejected(self) -> None:
        payload = build_save_rating_payload()
        invalid = {k: v for k, v in payload.items() if k != "team"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "save_rating_result")

    def test_save_missing_rating_is_rejected(self) -> None:
        payload = build_save_rating_payload()
        invalid = {k: v for k, v in payload.items() if k != "rating"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "save_rating_result")

    def test_save_missing_sport_is_rejected(self) -> None:
        payload = build_save_rating_payload()
        invalid = {k: v for k, v in payload.items() if k != "sport"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "save_rating_result")

    def test_save_missing_timestamp_is_rejected(self) -> None:
        payload = build_save_rating_payload()
        invalid = {k: v for k, v in payload.items() if k != "timestamp"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "save_rating_result")

    def test_save_unknown_field_is_rejected(self) -> None:
        payload = build_save_rating_payload()
        invalid = {**payload, "extra_metadata": "stowaway"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "save_rating_result")

    def test_save_empty_team_is_rejected(self) -> None:
        payload = build_save_rating_payload()
        invalid = {**payload, "team": ""}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "save_rating_result")

    def test_save_empty_sport_is_rejected(self) -> None:
        payload = build_save_rating_payload()
        invalid = {**payload, "sport": ""}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "save_rating_result")

    def test_save_negative_rating_is_rejected(self) -> None:
        payload = build_save_rating_payload()
        invalid = {**payload, "rating": -100.0}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "save_rating_result")

    def test_save_zero_rating_is_rejected(self) -> None:
        payload = build_save_rating_payload()
        invalid = {**payload, "rating": 0}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "save_rating_result")


class TestRatingStoreLoadRatingConsumerContract:
    """Consumer guarantees for RatingStore.get_rating() outputs."""

    def test_canonical_load_found_payload_passes_contract(self) -> None:
        payload = build_load_rating_payload_found()
        _validate_definition(payload, "load_rating_result")

    def test_canonical_load_not_found_payload_passes_contract(self) -> None:
        payload = build_load_rating_payload_not_found()
        _validate_definition(payload, "load_rating_result")

    def test_load_found_rating_is_positive_number(self) -> None:
        payload = build_load_rating_payload_found()
        assert isinstance(payload["rating"], (int, float))
        assert payload["rating"] > 0

    def test_load_not_found_rating_is_none(self) -> None:
        payload = build_load_rating_payload_not_found()
        assert payload["rating"] is None

    def test_load_found_has_true_flag(self) -> None:
        payload = build_load_rating_payload_found()
        assert payload["found"] is True

    def test_load_not_found_has_false_flag(self) -> None:
        payload = build_load_rating_payload_not_found()
        assert payload["found"] is False

    def test_load_team_is_non_empty_string(self) -> None:
        payload = build_load_rating_payload_found()
        assert isinstance(payload["team"], str)
        assert len(payload["team"]) >= 1

    def test_load_sport_is_non_empty_string(self) -> None:
        payload = build_load_rating_payload_found()
        assert isinstance(payload["sport"], str)
        assert len(payload["sport"]) >= 1

    def test_load_has_correct_schema_version(self) -> None:
        payload = build_load_rating_payload_found()
        assert payload["schema_version"] == "v1"

    def test_load_has_correct_payload_kind(self) -> None:
        payload = build_load_rating_payload_found()
        assert payload["payload_kind"] == "load_rating_result"

    def test_load_missing_team_is_rejected(self) -> None:
        payload = build_load_rating_payload_found()
        invalid = {k: v for k, v in payload.items() if k != "team"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_rating_result")

    def test_load_missing_rating_is_rejected(self) -> None:
        payload = build_load_rating_payload_found()
        invalid = {k: v for k, v in payload.items() if k != "rating"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_rating_result")

    def test_load_missing_sport_is_rejected(self) -> None:
        payload = build_load_rating_payload_found()
        invalid = {k: v for k, v in payload.items() if k != "sport"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_rating_result")

    def test_load_missing_found_is_rejected(self) -> None:
        payload = build_load_rating_payload_found()
        invalid = {k: v for k, v in payload.items() if k != "found"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_rating_result")

    def test_load_unknown_field_is_rejected(self) -> None:
        payload = build_load_rating_payload_found()
        invalid = {**payload, "extra_metadata": "stowaway"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_rating_result")

    def test_load_rating_as_string_is_rejected(self) -> None:
        payload = build_load_rating_payload_found()
        invalid = {**payload, "rating": "high"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_rating_result")

    def test_load_empty_team_is_rejected(self) -> None:
        payload = build_load_rating_payload_found()
        invalid = {**payload, "team": ""}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_rating_result")


class TestRatingStoreLoadAllRatingsConsumerContract:
    """Consumer guarantees for RatingStore.get_all_ratings() outputs."""

    def test_canonical_load_all_payload_passes_contract(self) -> None:
        payload = build_load_all_ratings_payload()
        _validate_definition(payload, "load_all_ratings_result")

    def test_load_all_ratings_is_dict(self) -> None:
        payload = build_load_all_ratings_payload()
        assert isinstance(payload["ratings"], dict)

    def test_load_all_ratings_are_positive_numbers(self) -> None:
        payload = build_load_all_ratings_payload()
        for rating in payload["ratings"].values():
            assert isinstance(rating, (int, float))
            assert rating > 0

    def test_load_all_ratings_keys_start_with_uppercase(self) -> None:
        payload = build_load_all_ratings_payload()
        for team in payload["ratings"]:
            assert isinstance(team, str)
            assert team[0].isupper(), f"Team key '{team}' does not start with uppercase"

    def test_load_all_count_matches_dict_length(self) -> None:
        payload = build_load_all_ratings_payload()
        assert payload["count"] == len(payload["ratings"])

    def test_load_all_sport_is_non_empty_string(self) -> None:
        payload = build_load_all_ratings_payload()
        assert isinstance(payload["sport"], str)
        assert len(payload["sport"]) >= 1

    def test_load_all_has_correct_schema_version(self) -> None:
        payload = build_load_all_ratings_payload()
        assert payload["schema_version"] == "v1"

    def test_load_all_has_correct_payload_kind(self) -> None:
        payload = build_load_all_ratings_payload()
        assert payload["payload_kind"] == "load_all_ratings_result"

    def test_load_all_missing_sport_is_rejected(self) -> None:
        payload = build_load_all_ratings_payload()
        invalid = {k: v for k, v in payload.items() if k != "sport"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_all_ratings_result")

    def test_load_all_missing_ratings_is_rejected(self) -> None:
        payload = build_load_all_ratings_payload()
        invalid = {k: v for k, v in payload.items() if k != "ratings"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_all_ratings_result")

    def test_load_all_missing_count_is_rejected(self) -> None:
        payload = build_load_all_ratings_payload()
        invalid = {k: v for k, v in payload.items() if k != "count"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_all_ratings_result")

    def test_load_all_unknown_field_is_rejected(self) -> None:
        payload = build_load_all_ratings_payload()
        invalid = {**payload, "extra_metadata": "stowaway"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_all_ratings_result")

    def test_load_all_negative_count_is_rejected(self) -> None:
        payload = build_load_all_ratings_payload()
        invalid = {**payload, "count": -1}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_all_ratings_result")

    def test_load_all_non_integer_count_is_rejected(self) -> None:
        payload = build_load_all_ratings_payload()
        invalid = {**payload, "count": "four"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_all_ratings_result")

    def test_load_all_empty_ratings_is_valid(self) -> None:
        payload = build_load_all_ratings_payload()
        payload["ratings"] = {}
        payload["count"] = 0
        _validate_definition(payload, "load_all_ratings_result")

    def test_load_all_ratings_key_not_starting_with_uppercase_is_rejected(
        self,
    ) -> None:
        payload = build_load_all_ratings_payload()
        invalid = {**payload, "ratings": {"nyy": 1500.0}}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "load_all_ratings_result")
