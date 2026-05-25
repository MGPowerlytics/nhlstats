"""
MLB travel fatigue features fetcher.

Populates the ``mlb_travel_features`` V010 database table with schedule-derived
travel metrics (time zones crossed, travel direction, circadian advantage, rest
days) for each team in each game.

Data sources
------------
1. Team info — static lookup table (all 30 MLB teams) with IANA timezone,
   venue name, and lat/lon coordinates.
2. ``mlb_games`` — prior-game query per team to compute travel distance in
   time zones and rest days between appearances.

Usage::

    from plugins.mlb_modeling.travel_fetcher import (
        fetch_travel_features,
        upsert_travel_features,
        compute_time_zones_crossed,
        compute_travel_direction,
    )

    payloads = fetch_travel_features(db, game_id, home_team, away_team, game_date)
    upsert_travel_features(db, payloads)
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

from zoneinfo import ZoneInfo

from plugins.db_manager import DBManager
from plugins.mlb_modeling.public_sources import (
    AvailabilityStatus,
    MLBTravelFatigueBuilder,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Team information
# ---------------------------------------------------------------------------

TEAM_INFO: dict[str, dict[str, Any]] = {
    "Arizona Diamondbacks": {
        "timezone": "America/Phoenix",
        "venue": "Chase Field",
        "coordinates": (33.445, -112.067),
    },
    "Atlanta Braves": {
        "timezone": "America/New_York",
        "venue": "Truist Park",
        "coordinates": (33.891, -84.468),
    },
    "Baltimore Orioles": {
        "timezone": "America/New_York",
        "venue": "Oriole Park at Camden Yards",
        "coordinates": (39.284, -76.622),
    },
    "Boston Red Sox": {
        "timezone": "America/New_York",
        "venue": "Fenway Park",
        "coordinates": (42.347, -71.097),
    },
    "Chicago Cubs": {
        "timezone": "America/Chicago",
        "venue": "Wrigley Field",
        "coordinates": (41.948, -87.655),
    },
    "Chicago White Sox": {
        "timezone": "America/Chicago",
        "venue": "Guaranteed Rate Field",
        "coordinates": (41.830, -87.634),
    },
    "Cincinnati Reds": {
        "timezone": "America/New_York",
        "venue": "Great American Ball Park",
        "coordinates": (39.090, -84.507),
    },
    "Cleveland Guardians": {
        "timezone": "America/New_York",
        "venue": "Progressive Field",
        "coordinates": (41.496, -81.685),
    },
    "Colorado Rockies": {
        "timezone": "America/Denver",
        "venue": "Coors Field",
        "coordinates": (39.756, -104.994),
    },
    "Detroit Tigers": {
        "timezone": "America/New_York",
        "venue": "Comerica Park",
        "coordinates": (42.339, -83.049),
    },
    "Houston Astros": {
        "timezone": "America/Chicago",
        "venue": "Minute Maid Park",
        "coordinates": (29.757, -95.355),
    },
    "Kansas City Royals": {
        "timezone": "America/Chicago",
        "venue": "Kauffman Stadium",
        "coordinates": (39.051, -94.480),
    },
    "Los Angeles Angels": {
        "timezone": "America/Los_Angeles",
        "venue": "Angel Stadium",
        "coordinates": (33.800, -117.883),
    },
    "Los Angeles Dodgers": {
        "timezone": "America/Los_Angeles",
        "venue": "Dodger Stadium",
        "coordinates": (34.074, -118.240),
    },
    "Miami Marlins": {
        "timezone": "America/New_York",
        "venue": "loanDepot park",
        "coordinates": (25.778, -80.220),
    },
    "Milwaukee Brewers": {
        "timezone": "America/Chicago",
        "venue": "American Family Field",
        "coordinates": (43.028, -87.971),
    },
    "Minnesota Twins": {
        "timezone": "America/Chicago",
        "venue": "Target Field",
        "coordinates": (44.982, -93.278),
    },
    "New York Mets": {
        "timezone": "America/New_York",
        "venue": "Citi Field",
        "coordinates": (40.757, -73.846),
    },
    "New York Yankees": {
        "timezone": "America/New_York",
        "venue": "Yankee Stadium",
        "coordinates": (40.830, -73.926),
    },
    "Oakland Athletics": {
        "timezone": "America/Los_Angeles",
        "venue": "Oakland Coliseum",
        "coordinates": (37.751, -122.201),
    },
    "Philadelphia Phillies": {
        "timezone": "America/New_York",
        "venue": "Citizens Bank Park",
        "coordinates": (39.906, -75.167),
    },
    "Pittsburgh Pirates": {
        "timezone": "America/New_York",
        "venue": "PNC Park",
        "coordinates": (40.447, -80.007),
    },
    "San Diego Padres": {
        "timezone": "America/Los_Angeles",
        "venue": "Petco Park",
        "coordinates": (32.707, -117.157),
    },
    "San Francisco Giants": {
        "timezone": "America/Los_Angeles",
        "venue": "Oracle Park",
        "coordinates": (37.778, -122.389),
    },
    "Seattle Mariners": {
        "timezone": "America/Los_Angeles",
        "venue": "T-Mobile Park",
        "coordinates": (47.591, -122.333),
    },
    "St. Louis Cardinals": {
        "timezone": "America/Chicago",
        "venue": "Busch Stadium",
        "coordinates": (38.623, -90.193),
    },
    "Tampa Bay Rays": {
        "timezone": "America/New_York",
        "venue": "Tropicana Field",
        "coordinates": (27.768, -82.653),
    },
    "Texas Rangers": {
        "timezone": "America/Chicago",
        "venue": "Globe Life Field",
        "coordinates": (32.747, -97.085),
    },
    "Toronto Blue Jays": {
        "timezone": "America/Toronto",
        "venue": "Rogers Centre",
        "coordinates": (43.641, -79.389),
    },
    "Washington Nationals": {
        "timezone": "America/New_York",
        "venue": "Nationals Park",
        "coordinates": (38.873, -77.007),
    },
}

# ---------------------------------------------------------------------------
# Derived lookups
# ---------------------------------------------------------------------------

# Map venue name -> IANA timezone string
VENUE_TIMEZONE: dict[str, str] = {
    info["venue"]: info["timezone"] for info in TEAM_INFO.values()
}

# Map venue name -> team name (for reverse lookup)
_VENUE_TO_TEAM: dict[str, str] = {
    info["venue"]: team for team, info in TEAM_INFO.items()
}


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------


def _venue_utc_offset(venue: str, for_date: date) -> float:
    """Return the UTC offset in hours for a venue on a given date.

    Uses ``zoneinfo`` to resolve DST-aware offsets.

    Args:
        venue: Venue name.
        for_date: The date to compute the offset for.

    Returns:
        UTC offset in hours (e.g. ``-5.0`` for EST, ``-4.0`` for EDT).

    Raises:
        KeyError: If the venue is not in :data:`VENUE_TIMEZONE`.
    """
    tz_name = VENUE_TIMEZONE[venue]
    tz = ZoneInfo(tz_name)
    dt = datetime.combine(for_date, datetime.min.time(), tzinfo=tz)
    offset_seconds = dt.utcoffset().total_seconds() if dt.utcoffset() is not None else 0
    return offset_seconds / 3600.0


# ---------------------------------------------------------------------------
# Travel computation helpers
# ---------------------------------------------------------------------------


def compute_time_zones_crossed(
    prev_venue: str | None,
    curr_venue: str,
    game_date: date,
) -> int:
    """Compute the integer count of time zones crossed between venues.

    Args:
        prev_venue: Previous game's venue (``None`` if first game of season).
        curr_venue: Current game venue.
        game_date: Game date (used for DST-aware offset resolution).

    Returns:
        Number of time zones crossed (rounded to nearest integer), or ``0``
        if *prev_venue* is ``None``.
    """
    if prev_venue is None:
        return 0
    try:
        prev_offset = _venue_utc_offset(prev_venue, game_date)
        curr_offset = _venue_utc_offset(curr_venue, game_date)
        return int(round(abs(curr_offset - prev_offset)))
    except KeyError:
        logger.warning("Unknown venue in timezone lookup: %s or %s", prev_venue, curr_venue)
        return 0


def compute_travel_direction(
    prev_venue: str | None,
    curr_venue: str,
    game_date: date,
) -> str:
    """Compute the direction of travel from previous to current venue.

    Direction is expressed from the **traveling team's** perspective:
    - ``"east"`` — traveled eastward (to a more positive UTC offset).
    - ``"west"`` — traveled westward (to a more negative UTC offset).
    - ``"none"`` — same timezone or no previous game.

    Args:
        prev_venue: Previous game's venue.
        curr_venue: Current game venue.
        game_date: Game date for DST-aware offset resolution.

    Returns:
        ``"east"``, ``"west"``, or ``"none"``.
    """
    if prev_venue is None:
        return "none"
    try:
        prev_offset = _venue_utc_offset(prev_venue, game_date)
        curr_offset = _venue_utc_offset(curr_venue, game_date)
    except KeyError:
        return "none"

    diff = curr_offset - prev_offset
    if diff > 0.5:
        return "east"
    if diff < -0.5:
        return "west"
    return "none"


# ---------------------------------------------------------------------------
# Previous-game query
# ---------------------------------------------------------------------------

_PREVIOUS_GAME_SQL = """
    SELECT game_id, game_date, home_team, away_team
    FROM mlb_games
    WHERE (:team IN (home_team, away_team))
      AND game_date < :game_date
      AND status IN ('Final', 'Game Over', 'Completed Early')
    ORDER BY game_date DESC
    LIMIT 1
"""


def _query_previous_game(
    db: DBManager,
    team: str,
    game_date: date,
) -> dict[str, Any] | None:
    """Query ``mlb_games`` for a team's most recent completed game.

    Args:
        db: Database manager instance.
        team: Team name (e.g. ``"New York Yankees"``).
        game_date: Current game date (finds games strictly before this date).

    Returns:
        Dict with keys ``game_id``, ``game_date``, ``home_team``, ``away_team``
        or ``None`` if no previous game exists.
    """
    result = db.fetch_df(
        _PREVIOUS_GAME_SQL,
        {"team": team, "game_date": game_date.isoformat()},
    )
    if result.empty:
        return None

    row = result.iloc[0]
    return {
        "game_id": str(row.get("game_id", "")),
        "game_date": row.get("game_date"),
        "home_team": str(row.get("home_team", "")),
        "away_team": str(row.get("away_team", "")),
    }


# ---------------------------------------------------------------------------
# Travel feature computation for one team
# ---------------------------------------------------------------------------


def _compute_team_travel(
    db: DBManager,
    game_id: str,
    team: str,
    is_home: bool,
    game_date: date,
    curr_venue: str,
    *,
    local_start_time: str | None = None,
) -> dict[str, Any]:
    """Compute travel fatigue features for a single team.

    Args:
        db: Database manager instance.
        game_id: Current game ID.
        team: Team name.
        is_home: Whether this team is the home team.
        game_date: Current game date.
        curr_venue: Current game venue.
        local_start_time: Optional local game start time (HH:MM:SS format).

    Returns:
        Payload dict suitable for :class:`MLBTravelFatigueBuilder.build_payload`.
    """
    prev = _query_previous_game(db, team, game_date)

    if prev is not None:
        prev_game_id = prev["game_id"]
        prev_game_date = prev["game_date"]

        # Determine previous venue from whether the team was home or away
        if prev["home_team"] == team:
            prev_venue = TEAM_INFO[team]["venue"]
        else:
            prev_venue = TEAM_INFO[prev["home_team"]]["venue"]

        # Days rest = days between previous game and current game, minus 1
        if isinstance(prev_game_date, date):
            delta = (game_date - prev_game_date).days - 1
            days_rest = max(0, min(7, delta))
        else:
            days_rest = 2

        time_zones = compute_time_zones_crossed(prev_venue, curr_venue, game_date)
        direction = compute_travel_direction(prev_venue, curr_venue, game_date)

        # Circadian advantage: positive when traveling west (body thinks it's earlier)
        if prev_venue is not None and prev_venue != curr_venue:
            try:
                prev_offset = _venue_utc_offset(prev_venue, game_date)
                curr_offset = _venue_utc_offset(curr_venue, game_date)
                circadian_hours = prev_offset - curr_offset
            except KeyError:
                circadian_hours = 0.0
        else:
            circadian_hours = 0.0

        prev_game_date_str: str | None = (
            prev_game_date.isoformat() if isinstance(prev_game_date, date) else None
        )
    else:
        prev_game_id = None
        prev_venue = None
        prev_game_date_str = None
        days_rest = 2
        time_zones = 0
        direction = "none"
        circadian_hours = 0.0

    return MLBTravelFatigueBuilder.build_payload(
        game_id=game_id,
        team=team,
        is_home=is_home,
        time_zones_crossed=time_zones,
        travel_direction=direction,
        circadian_advantage_hours=circadian_hours,
        days_rest=days_rest,
        previous_game_id=prev_game_id,
        previous_game_date=prev_game_date_str,
        previous_venue=prev_venue,
        local_start_time=local_start_time,
    )


# ---------------------------------------------------------------------------
# Main fetch function
# ---------------------------------------------------------------------------


def fetch_travel_features(
    db: DBManager,
    game_id: str,
    home_team: str,
    away_team: str,
    game_date: date,
    *,
    local_start_time: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch and upsert travel features for both teams in a game.

    Queries ``mlb_games`` for each team's previous completed game, computes
    rest days, time zones crossed, travel direction, and circadian advantage,
    then builds payloads via :class:`MLBTravelFatigueBuilder` and upserts
    both rows.

    Args:
        db: Database manager instance.
        game_id: Game identifier.
        home_team: Home team name.
        away_team: Away team name.
        game_date: Official game date.
        local_start_time: Optional local game start time (HH:MM:SS).

    Returns:
        List of two payload dicts (home team first, then away team) that
        were upserted.
    """
    curr_venue = TEAM_INFO[home_team]["venue"]

    home_payload = _compute_team_travel(
        db, game_id, home_team, is_home=True, game_date=game_date,
        curr_venue=curr_venue, local_start_time=local_start_time,
    )
    away_payload = _compute_team_travel(
        db, game_id, away_team, is_home=False, game_date=game_date,
        curr_venue=curr_venue, local_start_time=local_start_time,
    )

    payloads = [home_payload, away_payload]
    upsert_travel_features(db, payloads)
    return payloads


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

_TRAVEL_UPSERT_SQL = """
    INSERT INTO mlb_travel_features
        (game_id, team, is_home,
         previous_game_id, previous_game_date, previous_venue,
         time_zones_crossed, travel_direction,
         west_to_east_penalty, circadian_advantage_hours,
         local_start_time, days_rest,
         source, feature_version, updated_at)
    VALUES
        (:game_id, :team, :is_home,
         :previous_game_id, :previous_game_date, :previous_venue,
         :time_zones_crossed, :travel_direction,
         :west_to_east_penalty, :circadian_advantage_hours,
         :local_start_time, :days_rest,
         :source, :feature_version, NOW())
    ON CONFLICT (game_id, team) DO UPDATE SET
        is_home                    = EXCLUDED.is_home,
        previous_game_id           = EXCLUDED.previous_game_id,
        previous_game_date         = EXCLUDED.previous_game_date,
        previous_venue             = EXCLUDED.previous_venue,
        time_zones_crossed         = EXCLUDED.time_zones_crossed,
        travel_direction           = EXCLUDED.travel_direction,
        west_to_east_penalty       = EXCLUDED.west_to_east_penalty,
        circadian_advantage_hours  = EXCLUDED.circadian_advantage_hours,
        local_start_time           = EXCLUDED.local_start_time,
        days_rest                  = EXCLUDED.days_rest,
        source                     = EXCLUDED.source,
        feature_version            = EXCLUDED.feature_version,
        updated_at                 = NOW()
"""


def upsert_travel_features(db: DBManager, payloads: list[dict[str, Any]]) -> int:
    """Upsert travel feature payloads into ``mlb_travel_features``.

    Args:
        db: Database manager instance.
        payloads: List of payload dicts (typically two — one per team) from
            :func:`fetch_travel_features` or
            :class:`MLBTravelFatigueBuilder.build_payload`.

    Returns:
        Number of rows upserted.
    """
    for p in payloads:
        row = {
            "game_id": p["game_id"],
            "team": p["team"],
            "is_home": p["is_home"],
            "previous_game_id": p.get("previous_game_id"),
            "previous_game_date": p.get("previous_game_date"),
            "previous_venue": p.get("previous_venue"),
            "time_zones_crossed": p.get("time_zones_crossed", 0),
            "travel_direction": p.get("travel_direction", "none"),
            "west_to_east_penalty": p.get("west_to_east_penalty", 0.0),
            "circadian_advantage_hours": p.get("circadian_advantage_hours", 0.0),
            "local_start_time": p.get("local_start_time"),
            "days_rest": p.get("days_rest", 2),
            "source": p.get("source", "schedule_derived"),
            "feature_version": p.get("feature_version", "v1"),
        }
        db.execute(_TRAVEL_UPSERT_SQL, row)
    return len(payloads)
