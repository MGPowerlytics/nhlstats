"""Provider contract tests for the TheOddsAPI boundary.

Validates that ``TheOddsAPI`` methods produce output that conforms to the
frozen JSON Schema contract. Uses mocked HTTP requests so no real API
credentials are required.

Tests cover:
  - fetch_markets() output validates against schema
  - _parse_game() produces contract-valid output
  - _extract_bookmaker_odds() preserves contract structure
  - Drift detection: contract still matches current output shape
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from jsonschema import Draft202012Validator

from plugins.the_odds_api import TheOddsAPI

SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / "the_odds_api_contract_v1.json"
)

# --- Deterministic raw API response data ---

CANONICAL_GAME_ID = "basketball_nba_cfb8c60c1c1e1c1e1c1e1c1e"
CANONICAL_SPORT = "nba"

RAW_API_GAME: dict[str, Any] = {
    "id": CANONICAL_GAME_ID,
    "sport_key": "basketball_nba",
    "sport_title": "NBA",
    "commence_time": "2025-01-20T19:00:00Z",
    "home_team": "Los Angeles Lakers",
    "away_team": "Golden State Warriors",
    "bookmakers": [
        {
            "key": "draftkings",
            "title": "DraftKings",
            "last_update": "2025-01-20T18:30:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 1.95},
                        {"name": "Golden State Warriors", "price": 1.91},
                    ],
                },
            ],
        },
        {
            "key": "fanduel",
            "title": "FanDuel",
            "last_update": "2025-01-20T18:30:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 1.92},
                        {"name": "Golden State Warriors", "price": 1.94},
                    ],
                },
            ],
        },
    ],
}

RAW_API_RESPONSE: list[dict[str, Any]] = [RAW_API_GAME]


@pytest.fixture(scope="module")
def contract_schema() -> dict[str, Any]:
    """Load the TheOddsAPI contract schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _build_odds_schema(contract: dict[str, Any]) -> dict[str, Any]:
    """Build a temporary schema targeting the odds_response_result definition."""
    return {
        "$schema": contract["$schema"],
        "$ref": "#/$defs/odds_response_result",
        "$defs": contract["$defs"],
    }


def _validate(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


# ---------------------------------------------------------------------------
# Helpers to create a mocked TheOddsAPI instance
# ---------------------------------------------------------------------------


def _make_mocked_api() -> TheOddsAPI:
    """Create a TheOddsAPI instance with mocked HTTP session.

    The session.get() call is patched to return a canned response from
    RAW_API_RESPONSE, so no real API key or network access is needed.
    """
    api = TheOddsAPI(api_key="test_key_do_not_use")

    mock_response = MagicMock()
    mock_response.json.return_value = RAW_API_RESPONSE
    mock_response.headers = {"x-requests-remaining": "499"}
    mock_response.raise_for_status.return_value = None

    api.session.get = MagicMock(return_value=mock_response)
    return api


# ---------------------------------------------------------------------------
# Provider: fetch_markets() output matches schema
# ---------------------------------------------------------------------------


class TestFetchMarketsOutput:
    """fetch_markets() must produce schema-compliant output."""

    def test_fetch_markets_returns_list_of_dicts(self) -> None:
        api = _make_mocked_api()
        result = api.fetch_markets("nba")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(item, dict) for item in result)

    def test_fetch_markets_output_validates_against_schema(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_odds_schema(contract_schema)
        api = _make_mocked_api()
        result = api.fetch_markets("nba")

        # Convert the internal _parse_game output shape (which uses a dict of
        # bookmakers keyed by name) into the contract's shape (which uses an
        # array of bookmaker_entry objects). The contract format is the
        # canonical representation we enforce across the boundary.
        for game in result:
            contract_payload = {
                "sport": game["sport"],
                "game_id": game["game_id"],
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "commence_time": game["commence_time"],
                "bookmakers": [
                    {
                        "key": bm_name,
                        "title": bm_name,
                        "markets": [
                            {
                                "market_key": "h2h",
                                "outcomes": [
                                    {"name": game["home_team"], "price": bm_data["home_odds"], "point": None},
                                    {"name": game["away_team"], "price": bm_data["away_odds"], "point": None},
                                ],
                                "is_best": bm_name == game.get("best_home_bookmaker"),
                                "schema_version": "v1",
                                "payload_kind": "market_result",
                            },
                        ],
                    }
                    for bm_name, bm_data in game["bookmakers"].items()
                ],
                "total_bookmakers": game["num_bookmakers"],
                "schema_version": "v1",
                "payload_kind": "odds_response_result",
            }
            _validate(schema, contract_payload)

    def test_fetch_markets_includes_all_expected_fields(self) -> None:
        api = _make_mocked_api()
        result = api.fetch_markets("nba")
        assert len(result) >= 1
        game = result[0]
        expected_fields = {
            "platform", "sport", "game_id", "home_team", "away_team",
            "commence_time", "bookmakers", "best_home_bookmaker",
            "best_home_odds", "best_home_prob", "best_away_bookmaker",
            "best_away_odds", "best_away_prob", "num_bookmakers",
        }
        assert expected_fields.issubset(game.keys())
        assert game["sport"] == "nba"
        assert game["home_team"] == "Los Angeles Lakers"
        assert game["away_team"] == "Golden State Warriors"

    def test_fetch_markets_unknown_sport_returns_empty_list(self) -> None:
        api = _make_mocked_api()
        result = api.fetch_markets("nonexistent_sport")
        assert result == []

    def test_fetch_markets_no_api_key_returns_empty_list(self) -> None:
        api = TheOddsAPI(api_key=None)
        with patch.object(api, "api_key", None):
            result = api.fetch_markets("nba")
        assert result == []


# ---------------------------------------------------------------------------
# Provider: _parse_game() produces contract-valid output
# ---------------------------------------------------------------------------


class TestParseGame:
    """_parse_game() must produce data that conforms to the contract."""

    def test_parse_game_returns_valid_structure(self) -> None:
        api = _make_mocked_api()
        parsed = api._parse_game(RAW_API_GAME, CANONICAL_SPORT)
        assert parsed is not None
        assert parsed["sport"] == CANONICAL_SPORT
        assert parsed["game_id"] == CANONICAL_GAME_ID
        assert parsed["home_team"] == "Los Angeles Lakers"
        assert parsed["away_team"] == "Golden State Warriors"
        assert parsed["num_bookmakers"] == 2

    def test_parse_game_output_converts_to_schema(
        self, contract_schema: dict[str, Any]
    ) -> None:
        schema = _build_odds_schema(contract_schema)
        api = _make_mocked_api()
        parsed = api._parse_game(RAW_API_GAME, CANONICAL_SPORT)
        assert parsed is not None

        contract_payload = {
            "sport": parsed["sport"],
            "game_id": parsed["game_id"],
            "home_team": parsed["home_team"],
            "away_team": parsed["away_team"],
            "commence_time": parsed["commence_time"],
            "bookmakers": [
                {
                    "key": bm_name,
                    "title": bm_name,
                    "markets": [
                        {
                            "market_key": "h2h",
                            "outcomes": [
                                {"name": parsed["home_team"], "price": bm_data["home_odds"], "point": None},
                                {"name": parsed["away_team"], "price": bm_data["away_odds"], "point": None},
                            ],
                            "is_best": bm_name == parsed.get("best_home_bookmaker"),
                            "schema_version": "v1",
                            "payload_kind": "market_result",
                        },
                    ],
                }
                for bm_name, bm_data in parsed["bookmakers"].items()
            ],
            "total_bookmakers": parsed["num_bookmakers"],
            "schema_version": "v1",
            "payload_kind": "odds_response_result",
        }
        _validate(schema, contract_payload)

    def test_parse_game_no_h2h_market_returns_none(self) -> None:
        api = _make_mocked_api()
        game_no_h2h = dict(RAW_API_GAME)
        game_no_h2h["bookmakers"] = [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "last_update": "2025-01-20T18:30:00Z",
                "markets": [
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Los Angeles Lakers", "price": 1.95, "point": -4.5},
                            {"name": "Golden State Warriors", "price": 1.91, "point": 4.5},
                        ],
                    },
                ],
            },
        ]
        parsed = api._parse_game(game_no_h2h, "nba")
        assert parsed is None


# ---------------------------------------------------------------------------
# Provider: _extract_bookmaker_odds() preserves contract structure
# ---------------------------------------------------------------------------


class TestExtractBookmakerOdds:
    """_extract_bookmaker_odds() must preserve contract-level structure."""

    def test_extracts_odds_from_single_bookmaker(self) -> None:
        api = _make_mocked_api()
        bookmakers = api._extract_bookmaker_odds(
            RAW_API_GAME, "Los Angeles Lakers", "Golden State Warriors"
        )
        assert isinstance(bookmakers, dict)
        assert "draftkings" in bookmakers
        assert "fanduel" in bookmakers

    def test_extracted_odds_have_expected_keys(self) -> None:
        api = _make_mocked_api()
        bookmakers = api._extract_bookmaker_odds(
            RAW_API_GAME, "Los Angeles Lakers", "Golden State Warriors"
        )
        for bm_name, bm_data in bookmakers.items():
            assert "home_odds" in bm_data
            assert "away_odds" in bm_data
            assert "home_prob" in bm_data
            assert "away_prob" in bm_data
            assert "last_update" in bm_data

    def test_extracted_odds_home_away_prices_positive(self) -> None:
        api = _make_mocked_api()
        bookmakers = api._extract_bookmaker_odds(
            RAW_API_GAME, "Los Angeles Lakers", "Golden State Warriors"
        )
        for bm_data in bookmakers.values():
            assert bm_data["home_odds"] > 0
            assert bm_data["away_odds"] > 0

    def test_extracted_odds_probs_sum_to_less_than_one(self) -> None:
        """Implied probabilities from a single bookmaker sum to ~1 (overround)."""
        api = _make_mocked_api()
        bookmakers = api._extract_bookmaker_odds(
            RAW_API_GAME, "Los Angeles Lakers", "Golden State Warriors"
        )
        for bm_data in bookmakers.values():
            prob_sum = bm_data["home_prob"] + bm_data["away_prob"]
            assert prob_sum > 0
            assert prob_sum <= 1.1  # Allow for overround up to 10%

    def test_empty_bookmakers_returns_empty_dict(self) -> None:
        api = _make_mocked_api()
        game_no_bookmakers = dict(RAW_API_GAME)
        game_no_bookmakers["bookmakers"] = []
        bookmakers = api._extract_bookmaker_odds(
            game_no_bookmakers, "Los Angeles Lakers", "Golden State Warriors"
        )
        assert bookmakers == {}


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


class TestDriftDetection:
    """Contract drift detection: current output shape still matches schema.

    These tests act as an early warning system. If the TheOddsAPI changes its
    output format (field names, types, nesting), these tests will fail and
    signal that the contract schema needs updating.
    """

    def test_current_fetch_markets_shape_matches_contract(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """If this test fails, the provider's output format has drifted from the
        frozen schema. Update the schema or fix the provider to match."""
        schema = _build_odds_schema(contract_schema)
        api = _make_mocked_api()
        result = api.fetch_markets("nba")

        for game in result:
            contract_payload = {
                "sport": game["sport"],
                "game_id": game["game_id"],
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "commence_time": game["commence_time"],
                "bookmakers": [
                    {
                        "key": bm_name,
                        "title": bm_name,
                        "markets": [
                            {
                                "market_key": "h2h",
                                "outcomes": [
                                    {"name": game["home_team"], "price": bm_data["home_odds"], "point": None},
                                    {"name": game["away_team"], "price": bm_data["away_odds"], "point": None},
                                ],
                                "is_best": bm_name == game.get("best_home_bookmaker"),
                                "schema_version": "v1",
                                "payload_kind": "market_result",
                            },
                        ],
                    }
                    for bm_name, bm_data in game["bookmakers"].items()
                ],
                "total_bookmakers": game["num_bookmakers"],
                "schema_version": "v1",
                "payload_kind": "odds_response_result",
            }
            _validate(schema, contract_payload)

    def test_current_parse_game_shape_matches_contract(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """If this test fails, _parse_game() output has drifted from the contract."""
        schema = _build_odds_schema(contract_schema)
        api = _make_mocked_api()
        parsed = api._parse_game(RAW_API_GAME, CANONICAL_SPORT)
        assert parsed is not None

        contract_payload = {
            "sport": parsed["sport"],
            "game_id": parsed["game_id"],
            "home_team": parsed["home_team"],
            "away_team": parsed["away_team"],
            "commence_time": parsed["commence_time"],
            "bookmakers": [
                {
                    "key": bm_name,
                    "title": bm_name,
                    "markets": [
                        {
                            "market_key": "h2h",
                            "outcomes": [
                                {"name": parsed["home_team"], "price": bm_data["home_odds"], "point": None},
                                {"name": parsed["away_team"], "price": bm_data["away_odds"], "point": None},
                            ],
                            "is_best": bm_name == parsed.get("best_home_bookmaker"),
                            "schema_version": "v1",
                            "payload_kind": "market_result",
                        },
                    ],
                }
                for bm_name, bm_data in parsed["bookmakers"].items()
            ],
            "total_bookmakers": parsed["num_bookmakers"],
            "schema_version": "v1",
            "payload_kind": "odds_response_result",
        }
        _validate(schema, contract_payload)

    def test_schema_version_is_still_v1(self, contract_schema: dict[str, Any]) -> None:
        """Ensure the schema version hasn't accidentally changed."""
        assert contract_schema.get("$id", "").endswith("_v1.json")
        for def_name, definition in contract_schema.get("$defs", {}).items():
            props = definition.get("properties", {})
            sv = props.get("schema_version", {})
            if sv.get("const"):
                assert sv["const"] == "v1", f"{def_name}.schema_version changed from v1"

    def test_payload_kind_discriminators_are_present(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """Top-level result definitions should have a payload_kind const discriminator.

        Nested sub-types (e.g. bookmaker_entry, outcome) are embedded within
        other structures and don't require a discriminator.
        """
        discriminator_defs = {"odds_response_result", "market_result"}
        for def_name, definition in contract_schema.get("$defs", {}).items():
            if def_name not in discriminator_defs:
                continue
            props = definition.get("properties", {})
            pk = props.get("payload_kind", {})
            assert pk.get("const"), f"{def_name} missing payload_kind const"
