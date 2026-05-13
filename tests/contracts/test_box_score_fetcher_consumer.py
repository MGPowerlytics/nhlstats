"""Consumer contract tests for the BoxScoreFetcher ABC boundary.

Validates that any consumer of BoxScoreFetcher outputs can trust the shape
of ``fetch_game_stats``, ``fetch_date_range``, and ``upsert_rows`` results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.box_score_fetcher_samples import (
    build_empty_fetch_date_range_payload,
    build_empty_fetch_game_stats_payload,
    build_empty_upsert_rows_payload,
    build_fetch_date_range_payload,
    build_fetch_game_stats_payload,
    build_single_box_score_row,
    build_upsert_rows_payload,
)

SCHEMA_PATH = Path(__file__).parent / "schemas" / "box_score_fetcher_contract_v1.json"


@pytest.fixture(scope="module")
def contract_schema() -> dict[str, Any]:
    """Load the BoxScoreFetcher multi-definition contract schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _build_definition_schema(
    contract: dict[str, Any], definition: str
) -> dict[str, Any]:
    """Build a temporary schema that targets one ``$defs`` entry."""
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
    """Validate *payload* against a single named definition in the contract."""
    Draft202012Validator(
        _build_definition_schema(contract, definition),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    ).validate(payload)


# ---------------------------------------------------------------------------
# Box score row definition conformance
# ---------------------------------------------------------------------------


class TestBoxScoreRowDefinition:
    """The ``box_score_row`` definition enforces per-row constraints."""

    def test_canonical_row_passes(self, contract_schema: dict[str, Any]) -> None:
        _validate_definition(build_single_box_score_row(), contract_schema, "box_score_row")

    def test_away_row_passes(self, contract_schema: dict[str, Any]) -> None:
        _validate_definition(
            build_single_box_score_row(team="Golden State Warriors", opponent="Los Angeles Lakers", home=False),
            contract_schema,
            "box_score_row",
        )

    def test_missing_team_is_rejected(self, contract_schema: dict[str, Any]) -> None:
        payload = build_single_box_score_row()
        del payload["team"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "box_score_row")

    def test_missing_opponent_is_rejected(self, contract_schema: dict[str, Any]) -> None:
        payload = build_single_box_score_row()
        del payload["opponent"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "box_score_row")

    def test_missing_home_is_rejected(self, contract_schema: dict[str, Any]) -> None:
        payload = build_single_box_score_row()
        del payload["home"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "box_score_row")

    def test_missing_points_is_rejected(self, contract_schema: dict[str, Any]) -> None:
        payload = build_single_box_score_row()
        del payload["points"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "box_score_row")

    def test_empty_team_string_is_rejected(self, contract_schema: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            _validate_definition(
                build_single_box_score_row(team=""),
                contract_schema,
                "box_score_row",
            )

    def test_empty_opponent_string_is_rejected(self, contract_schema: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            _validate_definition(
                build_single_box_score_row(opponent=""),
                contract_schema,
                "box_score_row",
            )

    def test_non_boolean_home_is_rejected(self, contract_schema: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            _validate_definition(
                build_single_box_score_row(home="yes"),
                contract_schema,
                "box_score_row",
            )

    def test_negative_points_is_rejected(self, contract_schema: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            _validate_definition(
                build_single_box_score_row(points=-5),
                contract_schema,
                "box_score_row",
            )

    def test_unknown_fields_are_allowed(self, contract_schema: dict[str, Any]) -> None:
        """box_score_row uses additionalProperties: true so extra sport-specific fields are OK."""
        _validate_definition(
            build_single_box_score_row(assists=15, rebounds=10),
            contract_schema,
            "box_score_row",
        )

    def test_string_points_is_rejected(self, contract_schema: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            _validate_definition(
                build_single_box_score_row(points="112"),
                contract_schema,
                "box_score_row",
            )


# ---------------------------------------------------------------------------
# fetch_game_stats result definition conformance
# ---------------------------------------------------------------------------


class TestFetchGameStatsDefinition:
    """The ``fetch_game_stats_result`` definition enforces output shape."""

    def test_canonical_payload_passes(
        self, contract_schema: dict[str, Any]
    ) -> None:
        _validate_definition(
            build_fetch_game_stats_payload(),
            contract_schema,
            "fetch_game_stats_result",
        )

    def test_empty_rows_passes(self, contract_schema: dict[str, Any]) -> None:
        _validate_definition(
            build_empty_fetch_game_stats_payload(),
            contract_schema,
            "fetch_game_stats_result",
        )

    def test_missing_game_id_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_game_stats_payload()
        del payload["game_id"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_missing_sport_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_game_stats_payload()
        del payload["sport"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_missing_rows_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_game_stats_payload()
        del payload["rows"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_missing_row_count_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_game_stats_payload()
        del payload["row_count"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_unknown_field_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_game_stats_payload()
        payload["unknown_field"] = "should_not_exist"
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_wrong_payload_kind_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_game_stats_payload(payload_kind="fetch_date_range_result")
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_wrong_schema_version_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_game_stats_payload(schema_version="v2")
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_rows_contain_valid_row_objects(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_game_stats_payload()
        for row in payload["rows"]:
            _validate_definition(row, contract_schema, "box_score_row")

    def test_negative_row_count_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_game_stats_payload(row_count=-1)
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")

    def test_empty_game_id_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_game_stats_payload(game_id="")
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_game_stats_result")


# ---------------------------------------------------------------------------
# fetch_date_range result definition conformance
# ---------------------------------------------------------------------------


class TestFetchDateRangeDefinition:
    """The ``fetch_date_range_result`` definition enforces output shape."""

    def test_canonical_payload_passes(
        self, contract_schema: dict[str, Any]
    ) -> None:
        _validate_definition(
            build_fetch_date_range_payload(),
            contract_schema,
            "fetch_date_range_result",
        )

    def test_empty_result_passes(
        self, contract_schema: dict[str, Any]
    ) -> None:
        _validate_definition(
            build_empty_fetch_date_range_payload(),
            contract_schema,
            "fetch_date_range_result",
        )

    def test_missing_start_date_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_date_range_payload()
        del payload["start_date"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_date_range_result")

    def test_missing_end_date_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_date_range_payload()
        del payload["end_date"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_date_range_result")

    def test_missing_total_games_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_date_range_payload()
        del payload["total_games"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_date_range_result")

    def test_invalid_date_format_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_date_range_payload(start_date="01-15-2025")
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_date_range_result")

    def test_unknown_field_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_date_range_payload()
        payload["unknown_field"] = "should_not_exist"
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_date_range_result")

    def test_wrong_payload_kind_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_date_range_payload(
            payload_kind="fetch_game_stats_result"
        )
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "fetch_date_range_result")

    def test_games_contain_valid_rows(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_fetch_date_range_payload()
        for game in payload["games"]:
            for row in game["rows"]:
                _validate_definition(row, contract_schema, "box_score_row")


# ---------------------------------------------------------------------------
# upsert_rows result definition conformance
# ---------------------------------------------------------------------------


class TestUpsertRowsDefinition:
    """The ``upsert_rows_result`` definition enforces output shape."""

    def test_canonical_payload_passes(
        self, contract_schema: dict[str, Any]
    ) -> None:
        _validate_definition(
            build_upsert_rows_payload(),
            contract_schema,
            "upsert_rows_result",
        )

    def test_empty_result_passes(
        self, contract_schema: dict[str, Any]
    ) -> None:
        _validate_definition(
            build_empty_upsert_rows_payload(),
            contract_schema,
            "upsert_rows_result",
        )

    def test_missing_rows_inserted_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_upsert_rows_payload()
        del payload["rows_inserted"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "upsert_rows_result")

    def test_missing_sport_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_upsert_rows_payload()
        del payload["sport"]
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "upsert_rows_result")

    def test_unknown_field_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_upsert_rows_payload()
        payload["unknown_field"] = "should_not_exist"
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "upsert_rows_result")

    def test_negative_rows_inserted_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_upsert_rows_payload(rows_inserted=-1)
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "upsert_rows_result")

    def test_wrong_payload_kind_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_upsert_rows_payload(payload_kind="fetch_game_stats_result")
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "upsert_rows_result")

    def test_wrong_schema_version_is_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        payload = build_upsert_rows_payload(schema_version="v2")
        with pytest.raises(ValidationError):
            _validate_definition(payload, contract_schema, "upsert_rows_result")
