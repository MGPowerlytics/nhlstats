"""
MLB environment features fetcher.

Populates the ``mlb_environment_features`` V010 database table with park
factors, altitude, and weather data for each game.

Data sources
------------
1. Park factors — static lookup of 3-year rolling Baseball-Reference factors
   for all 30 MLB venues (runs, HR, doubles/triples, singles splits).
2. Altitude — static lookup (Wikipedia / public data).
3. Weather — best-effort fetch from OpenWeatherMap (free tier). Degrades
   gracefully when ``OPENWEATHERMAP_API_KEY`` is not set.

Usage::

    from plugins.mlb_modeling.environment_fetcher import (
        fetch_environment_features,
        upsert_environment_features,
    )

    payload = fetch_environment_features(db, game_id, game_date, venue)
    upsert_environment_features(db, payload)
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any, Optional

import requests

from plugins.db_manager import DBManager
from plugins.mlb_modeling.public_sources import (
    AvailabilityStatus,
    MLBEnvironmentFeatureBuilder,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Park factors — 3-year rolling Baseball-Reference averages (2023-2025)
# Each value is a multiplier where 1.00 = league average.
# ---------------------------------------------------------------------------

PARK_FACTOR_DB: dict[str, dict[str, float]] = {
    "Chase Field": {"runs": 1.03, "home_runs": 1.08, "doubles_triples": 0.99, "singles": 1.02},
    "Truist Park": {"runs": 1.00, "home_runs": 1.07, "doubles_triples": 0.97, "singles": 1.00},
    "Oriole Park at Camden Yards": {"runs": 1.01, "home_runs": 1.04, "doubles_triples": 1.01, "singles": 1.00},
    "Camden Yards": {"runs": 1.01, "home_runs": 1.04, "doubles_triples": 1.01, "singles": 1.00},
    "Fenway Park": {"runs": 1.07, "home_runs": 0.97, "doubles_triples": 1.18, "singles": 1.03},
    "Wrigley Field": {"runs": 1.04, "home_runs": 1.11, "doubles_triples": 0.99, "singles": 1.01},
    "Guaranteed Rate Field": {"runs": 0.98, "home_runs": 1.02, "doubles_triples": 0.96, "singles": 0.98},
    "Great American Ball Park": {"runs": 1.06, "home_runs": 1.14, "doubles_triples": 1.00, "singles": 1.03},
    "Progressive Field": {"runs": 0.97, "home_runs": 0.92, "doubles_triples": 1.00, "singles": 0.99},
    "Coors Field": {"runs": 1.20, "home_runs": 1.16, "doubles_triples": 1.17, "singles": 1.17},
    "Comerica Park": {"runs": 0.97, "home_runs": 0.94, "doubles_triples": 1.03, "singles": 0.97},
    "Minute Maid Park": {"runs": 1.02, "home_runs": 1.10, "doubles_triples": 0.97, "singles": 1.01},
    "Kauffman Stadium": {"runs": 0.92, "home_runs": 0.86, "doubles_triples": 0.93, "singles": 0.97},
    "Angel Stadium": {"runs": 1.00, "home_runs": 1.01, "doubles_triples": 1.01, "singles": 0.99},
    "Dodger Stadium": {"runs": 0.97, "home_runs": 0.91, "doubles_triples": 1.01, "singles": 0.98},
    "loanDepot park": {"runs": 0.91, "home_runs": 0.88, "doubles_triples": 0.92, "singles": 0.97},
    "American Family Field": {"runs": 0.99, "home_runs": 1.07, "doubles_triples": 0.91, "singles": 1.01},
    "Target Field": {"runs": 0.98, "home_runs": 0.97, "doubles_triples": 0.99, "singles": 0.99},
    "Citi Field": {"runs": 0.97, "home_runs": 0.93, "doubles_triples": 1.01, "singles": 0.97},
    "Yankee Stadium": {"runs": 1.03, "home_runs": 1.12, "doubles_triples": 0.97, "singles": 1.01},
    "Oakland Coliseum": {"runs": 0.93, "home_runs": 0.93, "doubles_triples": 0.94, "singles": 0.97},
    "Citizens Bank Park": {"runs": 1.02, "home_runs": 1.09, "doubles_triples": 0.99, "singles": 1.00},
    "PNC Park": {"runs": 0.96, "home_runs": 0.89, "doubles_triples": 1.01, "singles": 0.98},
    "Petco Park": {"runs": 0.96, "home_runs": 0.94, "doubles_triples": 0.96, "singles": 0.99},
    "Oracle Park": {"runs": 0.92, "home_runs": 0.86, "doubles_triples": 0.96, "singles": 0.96},
    "T-Mobile Park": {"runs": 0.94, "home_runs": 0.90, "doubles_triples": 0.97, "singles": 0.97},
    "Busch Stadium": {"runs": 0.97, "home_runs": 0.93, "doubles_triples": 1.03, "singles": 0.97},
    "Tropicana Field": {"runs": 0.95, "home_runs": 0.91, "doubles_triples": 0.96, "singles": 0.99},
    "Globe Life Field": {"runs": 1.05, "home_runs": 1.06, "doubles_triples": 1.01, "singles": 1.04},
    "Rogers Centre": {"runs": 1.02, "home_runs": 1.07, "doubles_triples": 0.98, "singles": 1.02},
    "Nationals Park": {"runs": 0.99, "home_runs": 0.97, "doubles_triples": 1.02, "singles": 1.00},
}

# ---------------------------------------------------------------------------
# Altitude lookup (feet above sea level, from Wikipedia / public data)
# ---------------------------------------------------------------------------

ALTITUDE_BY_VENUE: dict[str, float] = {
    "Chase Field": 1085.0,
    "Truist Park": 850.0,
    "Oriole Park at Camden Yards": 20.0,
    "Camden Yards": 20.0,
    "Fenway Park": 20.0,
    "Wrigley Field": 595.0,
    "Guaranteed Rate Field": 595.0,
    "Great American Ball Park": 490.0,
    "Progressive Field": 640.0,
    "Coors Field": 5200.0,
    "Comerica Park": 600.0,
    "Minute Maid Park": 30.0,
    "Kauffman Stadium": 750.0,
    "Angel Stadium": 50.0,
    "Dodger Stadium": 425.0,
    "loanDepot park": 5.0,
    "American Family Field": 635.0,
    "Target Field": 700.0,
    "Citi Field": 20.0,
    "Yankee Stadium": 30.0,
    "Oakland Coliseum": 30.0,
    "Citizens Bank Park": 30.0,
    "PNC Park": 720.0,
    "Petco Park": 25.0,
    "Oracle Park": 10.0,
    "T-Mobile Park": 10.0,
    "Busch Stadium": 465.0,
    "Tropicana Field": 10.0,
    "Globe Life Field": 550.0,
    "Rogers Centre": 260.0,
    "Nationals Park": 10.0,
}

# ---------------------------------------------------------------------------
# Venue coordinates for weather API lookups
# ---------------------------------------------------------------------------

VENUE_COORDINATES: dict[str, tuple[float, float]] = {
    "Chase Field": (33.445, -112.067),
    "Truist Park": (33.891, -84.468),
    "Oriole Park at Camden Yards": (39.284, -76.622),
    "Camden Yards": (39.284, -76.622),
    "Fenway Park": (42.347, -71.097),
    "Wrigley Field": (41.948, -87.655),
    "Guaranteed Rate Field": (41.830, -87.634),
    "Great American Ball Park": (39.090, -84.507),
    "Progressive Field": (41.496, -81.685),
    "Coors Field": (39.756, -104.994),
    "Comerica Park": (42.339, -83.049),
    "Minute Maid Park": (29.757, -95.355),
    "Kauffman Stadium": (39.051, -94.480),
    "Angel Stadium": (33.800, -117.883),
    "Dodger Stadium": (34.074, -118.240),
    "loanDepot park": (25.778, -80.220),
    "American Family Field": (43.028, -87.971),
    "Target Field": (44.982, -93.278),
    "Citi Field": (40.757, -73.846),
    "Yankee Stadium": (40.830, -73.926),
    "Oakland Coliseum": (37.751, -122.201),
    "Citizens Bank Park": (39.906, -75.167),
    "PNC Park": (40.447, -80.007),
    "Petco Park": (32.707, -117.157),
    "Oracle Park": (37.778, -122.389),
    "T-Mobile Park": (47.591, -122.333),
    "Busch Stadium": (38.623, -90.193),
    "Tropicana Field": (27.768, -82.653),
    "Globe Life Field": (32.747, -97.085),
    "Rogers Centre": (43.641, -79.389),
    "Nationals Park": (38.873, -77.007),
}

# ---------------------------------------------------------------------------
# Weather fetching (best-effort, graceful degradation)
# ---------------------------------------------------------------------------

_WEATHER_BASE_URL: str = "https://api.openweathermap.org/data/2.5/weather"


def _fetch_weather(
    venue: str,
    game_date: date,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch weather data for a venue on a given date (best-effort).

    Uses the OpenWeatherMap free tier's ``/weather`` endpoint via lat/lon
    lookup.  When no API key is available (or the call fails) all weather
    fields are returned as ``None`` and a warning is logged.

    Args:
        venue: Venue name (used for coordinate lookup).
        game_date: The date the weather is needed for (used for context,
            though the free-tier current-weather endpoint returns the latest
            observation near that date).
        api_key: OpenWeatherMap API key.  Falls back to the
            ``OPENWEATHERMAP_API_KEY`` environment variable when ``None``.

    Returns:
        A dict with keys ``temperature_f``, ``humidity_pct``,
        ``wind_speed_mph``, and ``wind_direction_degrees``.  All values are
        ``None`` when weather data is unavailable.
    """
    key = api_key or os.environ.get("OPENWEATHERMAP_API_KEY")
    if not key:
        logger.warning(
            "OPENWEATHERMAP_API_KEY not set; weather features will be None. "
            "Set this environment variable to enable live weather data."
        )
        return {
            "temperature_f": None,
            "humidity_pct": None,
            "wind_speed_mph": None,
            "wind_direction_degrees": None,
        }

    coords = VENUE_COORDINATES.get(venue)
    if coords is None:
        logger.warning("No coordinates for venue %r; weather will be None.", venue)
        return {
            "temperature_f": None,
            "humidity_pct": None,
            "wind_speed_mph": None,
            "wind_direction_degrees": None,
        }

    lat, lon = coords
    params: dict[str, str | float] = {
        "lat": lat,
        "lon": lon,
        "appid": key,
        "units": "imperial",
    }

    try:
        resp = requests.get(_WEATHER_BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except requests.RequestException as exc:
        logger.warning("Weather fetch failed for %s: %s", venue, exc)
        return {
            "temperature_f": None,
            "humidity_pct": None,
            "wind_speed_mph": None,
            "wind_direction_degrees": None,
        }

    main = data.get("main", {})
    wind = data.get("wind", {})

    temperature_c: float | None = main.get("temp")
    temperature_f: float | None = (
        round(temperature_c * 9.0 / 5.0 + 32.0, 1) if temperature_c is not None else None
    )

    humidity: int | None = main.get("humidity")
    wind_speed_mph: float | None = wind.get("speed")
    wind_deg: int | None = wind.get("deg")

    return {
        "temperature_f": temperature_f,
        "humidity_pct": float(humidity) if humidity is not None else None,
        "wind_speed_mph": float(wind_speed_mph) if wind_speed_mph is not None else None,
        "wind_direction_degrees": float(wind_deg) if wind_deg is not None else None,
    }


# ---------------------------------------------------------------------------
# Main fetch function
# ---------------------------------------------------------------------------


def fetch_environment_features(
    db: DBManager,
    game_id: str,
    game_date: date,
    venue: str,
    *,
    observed_at: datetime | None = None,
    weather_api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch environment features for a single game and upsert them.

    Looks up park factors and altitude for the venue, attempts a weather
    fetch (best-effort), then builds a payload via
    :class:`MLBEnvironmentFeatureBuilder` and upserts to
    ``mlb_environment_features``.

    Args:
        db: Database manager instance.
        game_id: Game identifier (e.g. ``"745431"``).
        game_date: Official game date.
        venue: Venue name (e.g. ``"Yankee Stadium"``).
        observed_at: Timestamp of when weather data was observed.
            ``None`` when no live weather was fetched.
        weather_api_key: Optional OpenWeatherMap API key. Falls back to
            ``OPENWEATHERMAP_API_KEY`` env var.

    Returns:
        The payload dict that was upserted (for testing/inspection).
    """
    # Resolve park factors (default to neutral 1.00 for unknown venues)
    pf = PARK_FACTOR_DB.get(venue, {"runs": 1.00, "home_runs": 1.00, "doubles_triples": 1.00, "singles": 1.00})

    # Resolve altitude
    altitude = ALTITUDE_BY_VENUE.get(venue)

    # Fetch weather
    weather = _fetch_weather(venue, game_date, api_key=weather_api_key)

    # Determine source and availability
    weather_available = weather.get("temperature_f") is not None
    if weather_available:
        source = "openweathermap"
        availability = AvailabilityStatus.AVAILABLE
    else:
        source = "park_factor_lookup"
        availability = AvailabilityStatus.DERIVED

    # Merge altitude into weather dict for the builder
    weather_with_altitude = dict(weather)
    weather_with_altitude["altitude_ft"] = altitude

    payload = MLBEnvironmentFeatureBuilder.build_payload(
        game_id=game_id,
        game_date=game_date.isoformat(),
        venue=venue,
        park_factors=pf,
        weather=weather_with_altitude,
        source=source,
        observed_at=observed_at,
        availability=availability,
    )

    upsert_environment_features(db, payload)
    return payload


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

_ENVIRONMENT_UPSERT_SQL = """
    INSERT INTO mlb_environment_features
        (game_id, game_date, venue,
         park_factor_runs, park_factor_hr, park_factor_doubles_triples,
         park_factor_singles,
         altitude_ft,
         temperature_f, humidity_pct, wind_speed_mph, wind_direction_degrees,
         hit_distance_adjustment_ft,
         source, observed_at, feature_version, updated_at)
    VALUES
        (:game_id, :game_date, :venue,
         :park_factor_runs, :park_factor_hr, :park_factor_doubles_triples,
         :park_factor_singles,
         :altitude_ft,
         :temperature_f, :humidity_pct, :wind_speed_mph, :wind_direction_degrees,
         :hit_distance_adjustment_ft,
         :source, :observed_at, :feature_version, NOW())
    ON CONFLICT (game_id) DO UPDATE SET
        game_date                  = EXCLUDED.game_date,
        venue                      = EXCLUDED.venue,
        park_factor_runs           = EXCLUDED.park_factor_runs,
        park_factor_hr             = EXCLUDED.park_factor_hr,
        park_factor_doubles_triples = EXCLUDED.park_factor_doubles_triples,
        park_factor_singles        = EXCLUDED.park_factor_singles,
        altitude_ft                = EXCLUDED.altitude_ft,
        temperature_f              = EXCLUDED.temperature_f,
        humidity_pct               = EXCLUDED.humidity_pct,
        wind_speed_mph             = EXCLUDED.wind_speed_mph,
        wind_direction_degrees     = EXCLUDED.wind_direction_degrees,
        hit_distance_adjustment_ft = EXCLUDED.hit_distance_adjustment_ft,
        source                     = EXCLUDED.source,
        observed_at                = EXCLUDED.observed_at,
        feature_version            = EXCLUDED.feature_version,
        updated_at                 = NOW()
"""


def upsert_environment_features(db: DBManager, payload: dict[str, Any]) -> int:
    """Upsert an environment feature payload into ``mlb_environment_features``.

    Args:
        db: Database manager instance.
        payload: Payload dict from :func:`fetch_environment_features` or
            :class:`MLBEnvironmentFeatureBuilder.build_payload`.

    Returns:
        Number of rows upserted (always 1).
    """
    pf = payload.get("park_factors", {})
    w = payload.get("weather", {})

    row = {
        "game_id": payload["game_id"],
        "game_date": payload["game_date"],
        "venue": payload["venue"],
        "park_factor_runs": pf.get("runs"),
        "park_factor_hr": pf.get("home_runs"),
        "park_factor_doubles_triples": pf.get("doubles_triples"),
        "park_factor_singles": pf.get("singles"),
        "altitude_ft": w.get("altitude_ft"),
        "temperature_f": w.get("temperature_f"),
        "humidity_pct": w.get("humidity_pct"),
        "wind_speed_mph": w.get("wind_speed_mph"),
        "wind_direction_degrees": w.get("wind_direction_degrees"),
        "hit_distance_adjustment_ft": payload.get("hit_distance_adjustment_ft"),
        "source": payload.get("source", "park_factor_lookup"),
        "observed_at": payload.get("observed_at"),
        "feature_version": payload.get("feature_version", "v1"),
    }

    db.execute(_ENVIRONMENT_UPSERT_SQL, row)
    return 1
