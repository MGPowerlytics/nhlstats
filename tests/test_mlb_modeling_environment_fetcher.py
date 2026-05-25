"""Tests for MLB environment features fetcher."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.contracts.helpers import validate_contract_payload

from plugins.mlb_modeling.environment_fetcher import (
    ALTITUDE_BY_VENUE,
    PARK_FACTOR_DB,
    VENUE_COORDINATES,
    _fetch_weather,
    fetch_environment_features,
    upsert_environment_features,
)
from plugins.mlb_modeling.public_sources import AvailabilityStatus


SCHEMAS_ROOT = Path(__file__).resolve().parent / "contracts" / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


class _FakeDb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, sql: str, params: dict) -> None:
        self.calls.append((sql, params))


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------


def test_park_factor_db_covers_all_30_mlb_venues() -> None:
    """All 30 primary MLB venues have park factor entries."""
    # 30 unique venues (some venues have aliases like Camden Yards / Oriole Park)
    expected_venues = {
        "Chase Field",
        "Truist Park",
        "Fenway Park",
        "Wrigley Field",
        "Guaranteed Rate Field",
        "Great American Ball Park",
        "Progressive Field",
        "Coors Field",
        "Comerica Park",
        "Minute Maid Park",
        "Kauffman Stadium",
        "Angel Stadium",
        "Dodger Stadium",
        "loanDepot park",
        "American Family Field",
        "Target Field",
        "Citi Field",
        "Yankee Stadium",
        "Oakland Coliseum",
        "Citizens Bank Park",
        "PNC Park",
        "Petco Park",
        "Oracle Park",
        "T-Mobile Park",
        "Busch Stadium",
        "Tropicana Field",
        "Globe Life Field",
        "Rogers Centre",
        "Nationals Park",
        "Oriole Park at Camden Yards",
        "Camden Yards",
    }
    assert expected_venues.issubset(PARK_FACTOR_DB.keys())


def test_all_park_factors_have_four_splits() -> None:
    """Each park factor entry has all four required split keys."""
    for venue, factors in PARK_FACTOR_DB.items():
        assert "runs" in factors, f"{venue} missing runs"
        assert "home_runs" in factors, f"{venue} missing home_runs"
        assert "doubles_triples" in factors, f"{venue} missing doubles_triples"
        assert "singles" in factors, f"{venue} missing singles"


def test_all_park_factors_are_reasonable() -> None:
    """Park factor values are within plausible bounds."""
    for venue, factors in PARK_FACTOR_DB.items():
        for key, value in factors.items():
            assert 0.70 <= value <= 1.40, (
                f"{venue} {key}={value} outside [0.70, 1.40]"
            )


def test_altitude_covers_all_park_factor_venues() -> None:
    """Every venue with park factors has an altitude entry."""
    for venue in PARK_FACTOR_DB:
        assert venue in ALTITUDE_BY_VENUE, (
            f"{venue} missing from ALTITUDE_BY_VENUE"
        )


def test_coordinates_covers_all_park_factor_venues() -> None:
    """Every venue with park factors has coordinate entries."""
    for venue in PARK_FACTOR_DB:
        assert venue in VENUE_COORDINATES, (
            f"{venue} missing from VENUE_COORDINATES"
        )


# ---------------------------------------------------------------------------
# Weather: graceful degradation
# ---------------------------------------------------------------------------


def test_fetch_weather_returns_none_when_no_api_key() -> None:
    """Without API key, weather fields should all be None."""
    result = _fetch_weather("Yankee Stadium", date(2026, 5, 10), api_key=None)
    assert result["temperature_f"] is None
    assert result["humidity_pct"] is None
    assert result["wind_speed_mph"] is None
    assert result["wind_direction_degrees"] is None


def test_fetch_weather_returns_none_for_unknown_venue() -> None:
    """Unknown venue returns None weather values."""
    result = _fetch_weather("Unknown Park", date(2026, 5, 10), api_key="fake_key")
    assert result["temperature_f"] is None
    assert result["humidity_pct"] is None


@patch("plugins.mlb_modeling.environment_fetcher.requests.get")
def test_fetch_weather_degrades_on_api_failure(mock_get) -> None:
    """API failure should log warning and return None."""
    from requests.exceptions import ConnectionError

    mock_get.side_effect = ConnectionError("connection failed")

    result = _fetch_weather("Yankee Stadium", date(2026, 5, 10), api_key="fake_key")
    assert result["temperature_f"] is None


@patch("plugins.mlb_modeling.environment_fetcher.requests.get")
def test_fetch_weather_parses_response(mock_get) -> None:
    """Successful API response is parsed into expected fields."""
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "main": {"temp": 21.1, "humidity": 55},
        "wind": {"speed": 7.5, "deg": 225},
    }

    result = _fetch_weather("Yankee Stadium", date(2026, 5, 10), api_key="fake_key")
    # 21.1 C -> 70.0 F
    assert result["temperature_f"] == pytest.approx(70.0, abs=0.1)
    assert result["humidity_pct"] == 55.0
    assert result["wind_speed_mph"] == 7.5
    assert result["wind_direction_degrees"] == 225.0


# ---------------------------------------------------------------------------
# Contract / schema validation
# ---------------------------------------------------------------------------


def test_fetch_environment_features_emits_valid_contract() -> None:
    """Payload from fetch_environment_features matches the JSON schema."""
    db = _FakeDb()

    payload = fetch_environment_features(
        db,
        game_id="745431",
        game_date=date(2026, 5, 10),
        venue="Yankee Stadium",
    )

    schema = _load_schema("mlb_environment_features_v1.json")
    validate_contract_payload(payload, schema)

    # Verify park factors are present
    assert payload["park_factors"]["runs"] == 1.03
    assert payload["park_factors"]["home_runs"] == 1.12

    # Verify weather is None (no API key)
    assert payload["weather"]["temperature_f"] is None

    # Availability should be DERIVED since no weather
    assert payload["availability"] == AvailabilityStatus.DERIVED.value


def test_fetch_environment_features_with_weather() -> None:
    """When weather_api_key is set and API works, weather data is populated."""
    db = _FakeDb()

    with patch(
        "plugins.mlb_modeling.environment_fetcher._fetch_weather",
        return_value={
            "temperature_f": 70.0,
            "humidity_pct": 55.0,
            "wind_speed_mph": 7.5,
            "wind_direction_degrees": 225.0,
        },
    ):
        payload = fetch_environment_features(
            db,
            game_id="745431",
            game_date=date(2026, 5, 10),
            venue="Yankee Stadium",
            weather_api_key="test_key",
        )

    assert payload["weather"]["temperature_f"] == 70.0
    assert payload["weather"]["humidity_pct"] == 55.0
    assert payload["availability"] == AvailabilityStatus.AVAILABLE.value
    assert payload["source"] == "openweathermap"


def test_fetch_environment_features_unknown_venue() -> None:
    """Unknown venue should default to neutral park factors (1.00)."""
    db = _FakeDb()

    payload = fetch_environment_features(
        db,
        game_id="999999",
        game_date=date(2026, 6, 1),
        venue="Unknown Ballpark",
    )

    assert payload["park_factors"]["runs"] == 1.00
    assert payload["park_factors"]["home_runs"] == 1.00
    assert payload["park_factors"]["doubles_triples"] == 1.00
    assert payload["park_factors"]["singles"] == 1.00
    assert payload["weather"]["altitude_ft"] is None


def test_fetch_environment_features_coors_field_altitude() -> None:
    """Coors Field should have a high altitude entry."""
    db = _FakeDb()

    payload = fetch_environment_features(
        db,
        game_id="745000",
        game_date=date(2026, 7, 1),
        venue="Coors Field",
    )

    assert payload["weather"]["altitude_ft"] == 5200.0


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


def test_upsert_environment_features_executes_sql() -> None:
    """Upsert should call db.execute with INSERT ... ON CONFLICT."""
    db = _FakeDb()

    payload = fetch_environment_features(
        db,
        game_id="745431",
        game_date=date(2026, 5, 10),
        venue="Yankee Stadium",
    )

    assert db.calls  # fetch already upserts
    sql, params = db.calls[0]
    assert "INSERT INTO mlb_environment_features" in sql
    assert "ON CONFLICT" in sql
    assert params["game_id"] == "745431"
    assert params["park_factor_runs"] == 1.03
    assert params["park_factor_hr"] == 1.12


def test_upsert_returns_one() -> None:
    """upsert_environment_features returns 1 (single row)."""
    db = _FakeDb()
    result = upsert_environment_features(
        db,
        {
            "game_id": "test",
            "game_date": "2026-05-10",
            "venue": "Test",
            "park_factors": {"runs": 1.0, "home_runs": 1.0, "doubles_triples": 1.0, "singles": 1.0},
            "weather": {"temperature_f": None, "humidity_pct": None, "wind_speed_mph": None, "wind_direction_degrees": None, "altitude_ft": None},
            "hit_distance_adjustment_ft": None,
            "source": "test",
            "feature_version": "v1",
        },
    )
    assert result == 1
