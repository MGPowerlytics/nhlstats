"""
MLB player-level stats fetcher.

Populates three V010 database tables from the MLB Stats API:

- ``mlb_player_game_batting_stats``  — per-player batting stats
- ``mlb_player_game_pitching_stats`` — per-pitcher pitching stats
- ``mlb_pitch_level_features``       — pitch-level aggregated features

Data sources
------------
1. MLB Stats API — boxscore endpoint::

    GET https://statsapi.mlb.com/api/v1/game/{gamePk}/boxscore

   Returns per-player data under ``teams.{home,away}.players`` and the
   ``batters`` / ``pitchers`` ID lists.

2. MLB Stats API — live feed endpoint::

    GET https://statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live

   Used for pitch-level extraction from ``liveData.plays.allPlays[].playEvents[]``
   and to determine the starting pitcher.

Rate limit: ``RATE_LIMIT = 0.5`` (2 req/s).

Usage::

    from plugins.mlb_modeling.player_stats_fetcher import (
        MLBPlayerStatsFetcher,
        compute_advanced_batting_metrics,
        compute_advanced_pitching_metrics,
    )

    fetcher = MLBPlayerStatsFetcher()
    result = fetcher.fetch_game_stats("745431")
    fetcher.upsert_all(result)
"""

from __future__ import annotations

import logging
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Optional

import requests
from sqlalchemy import text

from plugins.db_manager import DBManager
from plugins.stats.advanced_stats import compute_baseball_fip, compute_baseball_woba

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RATE_LIMIT: float = 0.5  # seconds between API calls

_LIVE_FEED_URL: str = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
_BOXSCORE_URL: str = "https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"

# wOBA linear weights (FanGraphs typical modern values)
_WOBA_WEIGHTS: dict[str, float] = {
    "bb": 0.690,
    "hbp": 0.722,
    "1b": 0.880,
    "2b": 1.249,
    "3b": 1.576,
    "hr": 2.031,
}

# Result codes from details.call.code in playEvents
_CALLED_STRIKE_CODES: frozenset[str] = frozenset({"C", "c"})
_SWINGING_STRIKE_CODES: frozenset[str] = frozenset({"S", "s"})

# Season constants from FanGraphs public data (lg_wOBA, scale, FIP constant,
# lg_ERA, lg_HR_per_FB).
_SEASON_CONSTANTS: dict[int, dict[str, float]] = {
    2021: {
        "lg_wOBA": 0.317,
        "lg_wOBA_scale": 1.19,
        "fip_constant": 3.08,
        "lg_era": 4.25,
        "lg_hr_per_fb": 0.145,
    },
    2022: {
        "lg_wOBA": 0.310,
        "lg_wOBA_scale": 1.18,
        "fip_constant": 3.07,
        "lg_era": 3.95,
        "lg_hr_per_fb": 0.136,
    },
    2023: {
        "lg_wOBA": 0.313,
        "lg_wOBA_scale": 1.18,
        "fip_constant": 3.05,
        "lg_era": 4.33,
        "lg_hr_per_fb": 0.135,
    },
    2024: {
        "lg_wOBA": 0.312,
        "lg_wOBA_scale": 1.18,
        "fip_constant": 3.06,
        "lg_era": 4.15,
        "lg_hr_per_fb": 0.138,
    },
    2025: {
        "lg_wOBA": 0.312,
        "lg_wOBA_scale": 1.18,
        "fip_constant": 3.06,
        "lg_era": 4.15,
        "lg_hr_per_fb": 0.137,
    },
    2026: {
        "lg_wOBA": 0.312,
        "lg_wOBA_scale": 1.18,
        "fip_constant": 3.06,
        "lg_era": 4.15,
        "lg_hr_per_fb": 0.137,
    },
}

_DEFAULT_SEASON: int = 2026


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------


def _retry_request(
    url: str,
    *,
    max_retries: int = 3,
    backoff: float = 1.0,
    timeout: int = 30,
) -> requests.Response:
    """GET *url* with retries on transient errors (429, 5xx).

    Uses exponential backoff: wait = backoff * 2^attempt seconds.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()
                return resp
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
        except requests.exceptions.Timeout as exc:
            last_exc = exc
        except requests.exceptions.HTTPError as exc:
            if resp.status_code >= 500 or resp.status_code == 429:
                last_exc = exc
            else:
                raise

        if attempt < max_retries:
            wait = backoff * (2 ** attempt)
            logger.warning(
                "Request to %s failed (attempt %d/%d): %s. Retrying in %.1fs.",
                url[:80],
                attempt + 1,
                max_retries + 1,
                last_exc,
                wait,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"Request to {url[:80]} failed after {max_retries + 1} attempts"
    ) from last_exc


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlayerStatsFetchResult:
    """Container for fetched player-level stats for one game.

    Attributes:
        batting_rows: List of dicts for ``mlb_player_game_batting_stats``.
        pitching_rows: List of dicts for ``mlb_player_game_pitching_stats``.
        pitch_features: List of dicts for ``mlb_pitch_level_features``.
    """

    batting_rows: list[dict[str, Any]]
    pitching_rows: list[dict[str, Any]]
    pitch_features: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_int(val: Any, default: int = 0) -> int:
    """Safely coerce *val* to int, returning *default* on failure."""
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _to_float(val: Any, default: float = 0.0) -> float:
    """Safely coerce *val* to float, returning *default* on failure."""
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _parse_innings_pitched(ip_str: Any) -> float:
    """Convert '6.1' --> 6.333, '9.0' --> 9.0.

    The MLB API represents partial innings as decimal tenths where each
    tenth equals one out (i.e. 6.1 = 6 and 1 out = 6 1/3 innings).
    """
    s = str(ip_str or "0.0").strip()
    if "." in s:
        whole_str, frac_str = s.split(".", 1)
        return _to_int(whole_str) + _to_int(frac_str) / 3.0
    return _to_float(s)


def _safe_divide(num: float, denom: float) -> Optional[float]:
    """Return *num* / *denom* or None if *denom* is 0."""
    if denom == 0:
        return None
    return num / denom


def _get_season_constants(year: int) -> dict[str, float]:
    """Return season constants dict, falling back to the most recent year."""
    return _SEASON_CONSTANTS.get(year, _SEASON_CONSTANTS[_DEFAULT_SEASON])


# ---------------------------------------------------------------------------
# Advanced batting metrics
# ---------------------------------------------------------------------------


def compute_advanced_batting_metrics(
    raw_stats: dict[str, Any],
    season: int,
) -> dict[str, Any]:
    """Compute advanced batting metrics from raw boxscore stats.

    Uses ``compute_baseball_woba()`` from ``plugins.stats.advanced_stats`` for
    wOBA.  Simplified wRC+ is derived from wOBA / lg_wOBA * 100 (no park
    factor).  Statcast / plate-discipline fields are always returned as
    ``None`` since the boxscore endpoint does not provide that data.

    Args:
        raw_stats: Dict with keys like ``atBats``, ``hits``, ``doubles``,
            ``homeRuns``, ``baseOnBalls``, ``strikeOuts``, etc.
        season: Season year used to look up ``_SEASON_CONSTANTS``.

    Returns:
        Dict containing ``woba``, ``wrc_plus``, ``o_swing_pct``,
        ``z_contact_pct``, ``hard_hit_pct``, ``avg_exit_velocity``,
        ``avg_launch_angle``, ``whiff_rate``, ``csw_pct``.
    """
    sc = _get_season_constants(season)
    lg_wOBA = sc.get("lg_wOBA", 0.315)

    hits = _to_int(raw_stats.get("hits"))
    doubles = _to_int(raw_stats.get("doubles"))
    triples = _to_int(raw_stats.get("triples"))
    home_runs = _to_int(raw_stats.get("homeRuns"))
    walks = _to_int(raw_stats.get("baseOnBalls"))
    hbp = _to_int(raw_stats.get("hitByPitch"))
    sac_flies = _to_int(raw_stats.get("sacFlies"))
    at_bats = _to_int(raw_stats.get("atBats"))

    singles = max(0, hits - doubles - triples - home_runs)

    pa_denom = at_bats + walks + sac_flies + hbp
    if pa_denom == 0:
        return {
            "woba": None,
            "wrc_plus": None,
            "o_swing_pct": None,
            "z_contact_pct": None,
            "hard_hit_pct": None,
            "avg_exit_velocity": None,
            "avg_launch_angle": None,
            "whiff_rate": None,
            "csw_pct": None,
        }

    woba = compute_baseball_woba(
        _WOBA_WEIGHTS,
        {
            "ab": at_bats,
            "bb": walks,
            "sf": sac_flies,
            "hbp": hbp,
            "1b": singles,
            "2b": doubles,
            "3b": triples,
            "hr": home_runs,
        },
    )

    # Simplified wRC+ = (wOBA / lg_wOBA) * 100
    # pa_denom > 0 guaranteed by early return above
    wrc_plus: Optional[float] = None
    if lg_wOBA > 0:
        wrc_plus = round((woba / lg_wOBA) * 100, 1)

    return {
        "woba": round(woba, 4) if woba is not None else None,
        "wrc_plus": wrc_plus,
        "o_swing_pct": None,
        "z_contact_pct": None,
        "hard_hit_pct": None,
        "avg_exit_velocity": None,
        "avg_launch_angle": None,
        "whiff_rate": None,
        "csw_pct": None,
    }


# ---------------------------------------------------------------------------
# Advanced pitching metrics
# ---------------------------------------------------------------------------


def compute_advanced_pitching_metrics(
    raw_stats: dict[str, Any],
    season: int,
) -> dict[str, Any]:
    """Compute advanced pitching metrics from raw boxscore stats.

    Uses ``compute_baseball_fip()`` from ``plugins.stats.advanced_stats`` for
    FIP.  xFIP is always ``None`` because fly-ball data is not available from
    the boxscore.  SIERA uses the simplified FanGraphs formula that only
    requires K/PA and BB/PA.  Statcast fields are returned as ``None``.

    Args:
        raw_stats: Dict with keys like ``inningsPitched``, ``strikeOuts``,
            ``baseOnBalls``, ``homeRuns``, ``earnedRuns``, etc.
        season: Season year used to look up ``_SEASON_CONSTANTS``.

    Returns:
        Dict containing ``fip``, ``xfip``, ``siera``, ``k_bb_pct``,
        ``o_swing_pct``, ``z_contact_pct``, ``hard_hit_pct_allowed``,
        ``avg_exit_velocity_allowed``, ``whiff_rate``, ``csw_pct``,
        ``primary_pitch_type``, ``primary_pitch_pct``, ``avg_velocity``.
    """
    sc = _get_season_constants(season)
    fip_constant = sc.get("fip_constant", 3.10)

    ip = _parse_innings_pitched(raw_stats.get("inningsPitched", "0.0"))
    strikeouts = _to_int(raw_stats.get("strikeOuts"))
    walks = _to_int(raw_stats.get("baseOnBalls"))
    home_runs = _to_int(raw_stats.get("homeRuns"))
    batters_faced = _to_int(raw_stats.get("battersFaced"))
    hbp = _to_int(raw_stats.get("hitByPitch"))

    # FIP
    fip = compute_baseball_fip(
        hr=home_runs,
        bb=walks,
        hbp=hbp,
        k=strikeouts,
        ip=ip,
        fip_constant=fip_constant,
    )

    # xFIP -- requires fly-ball data not available from the boxscore
    xfip: Optional[float] = None

    # SIERA (simplified FanGraphs formula)
    siera: Optional[float] = None
    pa = batters_faced
    if pa >= 4:
        k_rate = strikeouts / pa
        bb_rate = walks / pa
        siera_val = (
            6.145
            - 16.986 * k_rate
            + 11.434 * k_rate * k_rate
            - 1.858 * bb_rate
            + 7.653 * bb_rate * bb_rate
            - 4.005 * k_rate * bb_rate
        )
        siera = round(max(0.0, siera_val), 2)

    # K-BB%
    k_bb_pct: Optional[float] = None
    if pa > 0:
        k_bb_pct = round((strikeouts - walks) / pa * 100, 2)

    return {
        "fip": round(fip, 2) if fip is not None else None,
        "xfip": xfip,
        "siera": siera,
        "k_bb_pct": k_bb_pct,
        "o_swing_pct": None,
        "z_contact_pct": None,
        "hard_hit_pct_allowed": None,
        "avg_exit_velocity_allowed": None,
        "whiff_rate": None,
        "csw_pct": None,
        "primary_pitch_type": None,
        "primary_pitch_pct": None,
        "avg_velocity": None,
    }


# ---------------------------------------------------------------------------
# Pitch-level extraction helpers
# ---------------------------------------------------------------------------


def _extract_pitch_events(
    live_feed: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract individual pitch events from live-feed play-by-play.

    Iterates ``liveData.plays.allPlays[].playEvents[]`` and returns a flat
    list of dicts, one per pitch event with ``isPitch == true``.

    Args:
        live_feed: Parsed JSON from the live-feed endpoint.

    Returns:
        List of pitch-event dicts with keys ``batter_id``, ``pitcher_id``,
        ``pitch_type``, ``batter_side``, ``pitcher_throw_side``, ``velocity``,
        ``vert_location``, ``is_whiff``, ``is_called_strike``, ``is_csw``.
    """
    events: list[dict[str, Any]] = []
    plays = live_feed.get("liveData", {}).get("plays", {}).get("allPlays", [])

    for play in plays:
        matchup = play.get("matchup", {})
        batter_id = str(matchup.get("batter", {}).get("id", ""))
        pitcher_id = str(matchup.get("pitcher", {}).get("id", ""))
        batter_side = matchup.get("batSide", {}).get("code", "")
        pitcher_side = matchup.get("pitchHand", {}).get("code", "")

        for play_event in play.get("playEvents", []):
            if not play_event.get("isPitch"):
                continue

            details = play_event.get("details", {})
            pitch_data = play_event.get("pitchData", {})

            # Pitch type from details.type.code (e.g. "FF", "SL")
            type_info = details.get("type", {})
            pitch_type: str = type_info.get("code", "")

            # Result classification from details.call.code
            call_info = details.get("call", {})
            call_code: str = call_info.get("code", "")

            is_whiff = call_code in _SWINGING_STRIKE_CODES
            is_called_strike = call_code in _CALLED_STRIKE_CODES

            velocity = _to_float(pitch_data.get("startSpeed"), default=0.0)
            if velocity == 0.0:
                velocity = None

            coordinates = pitch_data.get("coordinates", {})
            vert_location = _to_float(coordinates.get("z"), default=0.0)
            if vert_location == 0.0:
                vert_location = None

            events.append(
                {
                    "batter_id": batter_id,
                    "pitcher_id": pitcher_id,
                    "pitch_type": pitch_type if pitch_type else "UNK",
                    "batter_side": batter_side,
                    "pitcher_throw_side": pitcher_side,
                    "velocity": velocity,
                    "vert_location": vert_location,
                    "is_whiff": is_whiff,
                    "is_called_strike": is_called_strike,
                    "is_csw": is_whiff or is_called_strike,
                }
            )

    return events


def _aggregate_pitch_features(
    events: list[dict[str, Any]],
    game_id: str,
) -> list[dict[str, Any]]:
    """Aggregate pitch events into per-combination pitch-level features.

    Groups by ``(pitcher_id, batter_id, pitch_type)`` and computes rates
    and averages.

    Args:
        events: Flat list of pitch-event dicts from :func:`_extract_pitch_events`.
        game_id: Game identifier for the primary key.

    Returns:
        List of pitch-feature dicts for ``mlb_pitch_level_features``.
    """
    groups: dict[
        tuple[str, str, str],
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "pitch_count": 0,
            "whiffs": 0,
            "csw": 0,
            "velocities": [],
            "vert_locations": [],
            "batter_side": "",
            "pitcher_throw_side": "",
        }
    )

    for event in events:
        key = (event["pitcher_id"], event["batter_id"], event["pitch_type"])
        g = groups[key]
        g["pitch_count"] += 1
        if event["is_whiff"]:
            g["whiffs"] += 1
        if event["is_csw"]:
            g["csw"] += 1
        if event["velocity"] is not None:
            g["velocities"].append(event["velocity"])
        if event["vert_location"] is not None:
            g["vert_locations"].append(event["vert_location"])
        if not g["batter_side"]:
            g["batter_side"] = event["batter_side"]
        if not g["pitcher_throw_side"]:
            g["pitcher_throw_side"] = event["pitcher_throw_side"]

    features: list[dict[str, Any]] = []
    for (pitcher_id, batter_id, pitch_type), g in groups.items():
        pitch_count = g["pitch_count"]
        whiff_rate = _safe_divide(float(g["whiffs"]), float(pitch_count))
        csw_pct = _safe_divide(float(g["csw"]), float(pitch_count))

        avg_vel: Optional[float] = None
        if g["velocities"]:
            avg_vel = statistics.mean(g["velocities"])

        avg_vert: Optional[float] = None
        if g["vert_locations"]:
            avg_vert = statistics.mean(g["vert_locations"])

        vert_accuracy: Optional[float] = None
        if len(g["vert_locations"]) >= 2:
            vert_accuracy = statistics.stdev(g["vert_locations"])

        features.append(
            {
                "game_id": game_id,
                "pitcher_id": pitcher_id,
                "batter_id": batter_id,
                "pitch_type": pitch_type,
                "batter_side": g["batter_side"] or None,
                "pitcher_throw_side": g["pitcher_throw_side"] or None,
                "pitch_count": pitch_count,
                "whiff_rate": round(whiff_rate, 4) if whiff_rate is not None else None,
                "csw_pct": round(csw_pct, 4) if csw_pct is not None else None,
                "z_contact_pct": None,
                "avg_vertical_location": (
                    round(avg_vert, 4) if avg_vert is not None else None
                ),
                "vertical_location_accuracy": (
                    round(vert_accuracy, 4) if vert_accuracy is not None else None
                ),
                "avg_velocity": round(avg_vel, 1) if avg_vel is not None else None,
                "source": "mlb_statsapi_livefeed",
                "feature_version": "v1",
            }
        )

    return features


# ---------------------------------------------------------------------------
# Main fetch function
# ---------------------------------------------------------------------------


def fetch_player_stats(
    game_id: str,
    game_date: date,
    rate_limiter: Callable[[], None],
    *,
    live_feed: dict[str, Any] | None = None,
) -> PlayerStatsFetchResult:
    """Fetch per-player batting and pitching stats for one MLB game.

    Calls the boxscore endpoint for counting stats and the live-feed endpoint
    for pitch-level event data.

    Args:
        game_id: MLB game PK (e.g. ``"745431"``).
        game_date: Official game date (used for season year).
        rate_limiter: Zero-argument callable that blocks to respect the API
            rate limit.  Call between each API request.
        live_feed: Pre-fetched live feed JSON. When provided, the live-feed
            API call is skipped (caller already fetched it).

    Returns:
        A :class:`PlayerStatsFetchResult` containing batting, pitching, and
        pitch-feature rows.
    """
    season = game_date.year

    # ---- Live feed ----
    if live_feed is None:
        rate_limiter()
        live_resp = _retry_request(_LIVE_FEED_URL.format(game_pk=game_id))
        live_feed = live_resp.json()

    # ---- Boxscore ----
    rate_limiter()
    box_resp = _retry_request(_BOXSCORE_URL.format(game_pk=game_id))
    boxscore: dict[str, Any] = box_resp.json()

    # ---- Team abbreviations from live feed ----
    game_data = live_feed.get("gameData", {})
    gd_teams = game_data.get("teams", {})
    home_abbr: str = gd_teams.get("home", {}).get("abbreviation", "HOME")
    away_abbr: str = gd_teams.get("away", {}).get("abbreviation", "AWAY")

    # ---- Determine starting pitcher(s) from live-feed ----
    starters: set[str] = set()
    all_plays = live_feed.get("liveData", {}).get("plays", {}).get("allPlays", [])
    if all_plays:
        first_play = all_plays[0]
        starter_id = str(first_play.get("matchup", {}).get("pitcher", {}).get("id", ""))
        if starter_id:
            starters.add(starter_id)

    # ---- Process boxscore ----
    bs_teams = boxscore.get("teams", {})
    batting_rows: list[dict[str, Any]] = []
    pitching_rows: list[dict[str, Any]] = []

    for side, team_abbr, opp_abbr in [
        ("home", home_abbr, away_abbr),
        ("away", away_abbr, home_abbr),
    ]:
        team_bs = bs_teams.get(side, {})
        players: dict[str, Any] = team_bs.get("players", {})
        batter_ids: list[int] = team_bs.get("batters", [])
        pitcher_ids: list[int] = team_bs.get("pitchers", [])

        # --- Batting ---
        for pid_int in batter_ids:
            player_key = f"ID{pid_int}"
            player_data = players.get(player_key, {})
            if not player_data:
                continue

            person = player_data.get("person", {})
            pid = str(person.get("id", pid_int))
            name: str = person.get("fullName", "")

            batting_stats = player_data.get("stats", {}).get("batting", {})
            if not batting_stats:
                continue

            advanced = compute_advanced_batting_metrics(batting_stats, season)

            batting_rows.append(
                {
                    "game_id": game_id,
                    "player_id": pid,
                    "player_name": name,
                    "team": team_abbr,
                    "opponent": opp_abbr,
                    "is_home": side == "home",
                    "batting_order": _to_int(player_data.get("battingOrder"), default=0)
                    or None,
                    "bats": (player_data.get("batSide", {}).get("code") or None),
                    "plate_appearances": _to_int(batting_stats.get("plateAppearances")),
                    "at_bats": _to_int(batting_stats.get("atBats")),
                    "hits": _to_int(batting_stats.get("hits")),
                    "doubles": _to_int(batting_stats.get("doubles")),
                    "triples": _to_int(batting_stats.get("triples")),
                    "home_runs": _to_int(batting_stats.get("homeRuns")),
                    "walks": _to_int(batting_stats.get("baseOnBalls")),
                    "strikeouts": _to_int(batting_stats.get("strikeOuts")),
                    **advanced,
                    "source": "mlb_statsapi_boxscore",
                    "feature_version": "v1",
                }
            )

        # --- Pitching ---
        for pid_int in pitcher_ids:
            player_key = f"ID{pid_int}"
            player_data = players.get(player_key, {})
            if not player_data:
                continue

            person = player_data.get("person", {})
            pid = str(person.get("id", pid_int))
            name: str = person.get("fullName", "")

            pitching_stats = player_data.get("stats", {}).get("pitching", {})
            if not pitching_stats:
                continue

            advanced = compute_advanced_pitching_metrics(pitching_stats, season)

            pitching_rows.append(
                {
                    "game_id": game_id,
                    "pitcher_id": pid,
                    "pitcher_name": name,
                    "team": team_abbr,
                    "opponent": opp_abbr,
                    "is_home": side == "home",
                    "is_starter": pid in starters,
                    "throws": (player_data.get("throws", {}).get("code") or None),
                    "innings_pitched": _parse_innings_pitched(
                        pitching_stats.get("inningsPitched", "0.0")
                    ),
                    "pitch_count": _to_int(pitching_stats.get("pitchesThrown")),
                    "batters_faced": _to_int(pitching_stats.get("battersFaced")),
                    "strikeouts": _to_int(pitching_stats.get("strikeOuts")),
                    "walks": _to_int(pitching_stats.get("baseOnBalls")),
                    "home_runs_allowed": _to_int(pitching_stats.get("homeRuns")),
                    "earned_runs": _to_int(pitching_stats.get("earnedRuns")),
                    **advanced,
                    # Fatigue / rolling fields computed downstream
                    "days_rest": None,
                    "pitches_last_3_days": None,
                    "pitches_last_5_days": None,
                    "fatigue_velocity_penalty": None,
                    "source": "mlb_statsapi_boxscore",
                    "feature_version": "v1",
                }
            )

    # ---- Pitch features ----
    pitch_events = _extract_pitch_events(live_feed)
    pitch_features = _aggregate_pitch_features(pitch_events, game_id)

    return PlayerStatsFetchResult(
        batting_rows=batting_rows,
        pitching_rows=pitching_rows,
        pitch_features=pitch_features,
    )


# ---------------------------------------------------------------------------
# Upsert functions
# ---------------------------------------------------------------------------

_BATTING_UPSERT_SQL = """
    INSERT INTO mlb_player_game_batting_stats
        (game_id, player_id, player_name, team, opponent, is_home,
         batting_order, bats,
         plate_appearances, at_bats, hits, doubles, triples, home_runs,
         walks, strikeouts,
         woba, wrc_plus,
         o_swing_pct, z_contact_pct, hard_hit_pct, avg_exit_velocity,
         avg_launch_angle, whiff_rate, csw_pct,
         source, feature_version, updated_at)
    VALUES
        (:game_id, :player_id, :player_name, :team, :opponent, :is_home,
         :batting_order, :bats,
         :plate_appearances, :at_bats, :hits, :doubles, :triples, :home_runs,
         :walks, :strikeouts,
         :woba, :wrc_plus,
         :o_swing_pct, :z_contact_pct, :hard_hit_pct, :avg_exit_velocity,
         :avg_launch_angle, :whiff_rate, :csw_pct,
         :source, :feature_version, NOW())
    ON CONFLICT (game_id, player_id) DO UPDATE SET
        player_name          = EXCLUDED.player_name,
        team                 = EXCLUDED.team,
        opponent             = EXCLUDED.opponent,
        is_home              = EXCLUDED.is_home,
        batting_order        = EXCLUDED.batting_order,
        bats                 = EXCLUDED.bats,
        plate_appearances    = EXCLUDED.plate_appearances,
        at_bats              = EXCLUDED.at_bats,
        hits                 = EXCLUDED.hits,
        doubles              = EXCLUDED.doubles,
        triples              = EXCLUDED.triples,
        home_runs            = EXCLUDED.home_runs,
        walks                = EXCLUDED.walks,
        strikeouts           = EXCLUDED.strikeouts,
        woba                 = EXCLUDED.woba,
        wrc_plus             = EXCLUDED.wrc_plus,
        o_swing_pct          = EXCLUDED.o_swing_pct,
        z_contact_pct        = EXCLUDED.z_contact_pct,
        hard_hit_pct         = EXCLUDED.hard_hit_pct,
        avg_exit_velocity    = EXCLUDED.avg_exit_velocity,
        avg_launch_angle     = EXCLUDED.avg_launch_angle,
        whiff_rate           = EXCLUDED.whiff_rate,
        csw_pct              = EXCLUDED.csw_pct,
        source               = EXCLUDED.source,
        feature_version      = EXCLUDED.feature_version,
        updated_at           = NOW()
"""


def upsert_batting_stats(
    db: DBManager,
    rows: list[dict[str, Any]],
) -> int:
    """Upsert batting stat rows into ``mlb_player_game_batting_stats``.

    Args:
        db: Database manager instance.
        rows: Batting row dicts from a :class:`PlayerStatsFetchResult`.

    Returns:
        Number of rows upserted.
    """
    for row in rows:
        db.execute(_BATTING_UPSERT_SQL, row)
    return len(rows)


_PITCHING_UPSERT_SQL = """
    INSERT INTO mlb_player_game_pitching_stats
        (game_id, pitcher_id, pitcher_name, team, opponent, is_home,
         is_starter, throws,
         innings_pitched, pitch_count, batters_faced, strikeouts, walks,
         home_runs_allowed, earned_runs,
         fip, xfip, siera, k_bb_pct,
         o_swing_pct, z_contact_pct, hard_hit_pct_allowed,
         avg_exit_velocity_allowed, whiff_rate, csw_pct,
         primary_pitch_type, primary_pitch_pct, avg_velocity,
         days_rest, pitches_last_3_days, pitches_last_5_days,
         fatigue_velocity_penalty,
         source, feature_version, updated_at)
    VALUES
        (:game_id, :pitcher_id, :pitcher_name, :team, :opponent, :is_home,
         :is_starter, :throws,
         :innings_pitched, :pitch_count, :batters_faced, :strikeouts, :walks,
         :home_runs_allowed, :earned_runs,
         :fip, :xfip, :siera, :k_bb_pct,
         :o_swing_pct, :z_contact_pct, :hard_hit_pct_allowed,
         :avg_exit_velocity_allowed, :whiff_rate, :csw_pct,
         :primary_pitch_type, :primary_pitch_pct, :avg_velocity,
         :days_rest, :pitches_last_3_days, :pitches_last_5_days,
         :fatigue_velocity_penalty,
         :source, :feature_version, NOW())
    ON CONFLICT (game_id, pitcher_id) DO UPDATE SET
        pitcher_name                = EXCLUDED.pitcher_name,
        team                        = EXCLUDED.team,
        opponent                    = EXCLUDED.opponent,
        is_home                     = EXCLUDED.is_home,
        is_starter                  = EXCLUDED.is_starter,
        throws                      = EXCLUDED.throws,
        innings_pitched             = EXCLUDED.innings_pitched,
        pitch_count                 = EXCLUDED.pitch_count,
        batters_faced               = EXCLUDED.batters_faced,
        strikeouts                  = EXCLUDED.strikeouts,
        walks                       = EXCLUDED.walks,
        home_runs_allowed           = EXCLUDED.home_runs_allowed,
        earned_runs                 = EXCLUDED.earned_runs,
        fip                         = EXCLUDED.fip,
        xfip                        = EXCLUDED.xfip,
        siera                       = EXCLUDED.siera,
        k_bb_pct                    = EXCLUDED.k_bb_pct,
        o_swing_pct                 = EXCLUDED.o_swing_pct,
        z_contact_pct               = EXCLUDED.z_contact_pct,
        hard_hit_pct_allowed        = EXCLUDED.hard_hit_pct_allowed,
        avg_exit_velocity_allowed   = EXCLUDED.avg_exit_velocity_allowed,
        whiff_rate                  = EXCLUDED.whiff_rate,
        csw_pct                     = EXCLUDED.csw_pct,
        primary_pitch_type          = EXCLUDED.primary_pitch_type,
        primary_pitch_pct           = EXCLUDED.primary_pitch_pct,
        avg_velocity                = EXCLUDED.avg_velocity,
        days_rest                   = EXCLUDED.days_rest,
        pitches_last_3_days         = EXCLUDED.pitches_last_3_days,
        pitches_last_5_days         = EXCLUDED.pitches_last_5_days,
        fatigue_velocity_penalty    = EXCLUDED.fatigue_velocity_penalty,
        source                      = EXCLUDED.source,
        feature_version             = EXCLUDED.feature_version,
        updated_at                  = NOW()
"""


def upsert_pitching_stats(
    db: DBManager,
    rows: list[dict[str, Any]],
) -> int:
    """Upsert pitching stat rows into ``mlb_player_game_pitching_stats``.

    Args:
        db: Database manager instance.
        rows: Pitching row dicts from a :class:`PlayerStatsFetchResult`.

    Returns:
        Number of rows upserted.
    """
    for row in rows:
        db.execute(_PITCHING_UPSERT_SQL, row)
    return len(rows)


_PITCH_FEATURES_UPSERT_SQL = """
    INSERT INTO mlb_pitch_level_features
        (game_id, pitcher_id, batter_id, pitch_type,
         batter_side, pitcher_throw_side,
         pitch_count, whiff_rate, csw_pct, z_contact_pct,
         avg_vertical_location, vertical_location_accuracy, avg_velocity,
         source, feature_version, updated_at)
    VALUES
        (:game_id, :pitcher_id, :batter_id, :pitch_type,
         :batter_side, :pitcher_throw_side,
         :pitch_count, :whiff_rate, :csw_pct, :z_contact_pct,
         :avg_vertical_location, :vertical_location_accuracy, :avg_velocity,
         :source, :feature_version, NOW())
    ON CONFLICT (game_id, pitcher_id, batter_id, pitch_type) DO UPDATE SET
        batter_side               = EXCLUDED.batter_side,
        pitcher_throw_side        = EXCLUDED.pitcher_throw_side,
        pitch_count               = EXCLUDED.pitch_count,
        whiff_rate                = EXCLUDED.whiff_rate,
        csw_pct                   = EXCLUDED.csw_pct,
        z_contact_pct             = EXCLUDED.z_contact_pct,
        avg_vertical_location     = EXCLUDED.avg_vertical_location,
        vertical_location_accuracy = EXCLUDED.vertical_location_accuracy,
        avg_velocity              = EXCLUDED.avg_velocity,
        source                    = EXCLUDED.source,
        feature_version           = EXCLUDED.feature_version,
        updated_at                = NOW()
"""


def upsert_pitch_features(
    db: DBManager,
    rows: list[dict[str, Any]],
) -> int:
    """Upsert pitch-feature rows into ``mlb_pitch_level_features``.

    Args:
        db: Database manager instance.
        rows: Pitch-feature dicts from a :class:`PlayerStatsFetchResult`.

    Returns:
        Number of rows upserted.
    """
    for row in rows:
        db.execute(_PITCH_FEATURES_UPSERT_SQL, row)
    return len(rows)


# ---------------------------------------------------------------------------
# Convenience class
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple monotonic rate limiter.

    Example::

        limiter = _RateLimiter(0.5)
        limiter.wait()  # blocks if called within 0.5s of last call
    """

    def __init__(self, min_interval: float = RATE_LIMIT) -> None:
        self._min_interval = min_interval
        self._last_ts: float = 0.0

    def wait(self) -> None:
        """Block if the minimum interval since the last call has not elapsed."""
        elapsed = time.monotonic() - self._last_ts
        remaining = self._min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_ts = time.monotonic()


class MLBPlayerStatsFetcher:
    """Convenience wrapper around :func:`fetch_player_stats` and upserts.

    Manages its own rate limiter and DB connection.
    """

    RATE_LIMIT: float = RATE_LIMIT

    def __init__(self, db: DBManager | None = None) -> None:
        """Initialise the fetcher.

        Args:
            db: Optional shared :class:`~plugins.db_manager.DBManager`.
                Creates a new instance if not provided.
        """
        self.db: DBManager = db or DBManager()
        self._limiter = _RateLimiter(RATE_LIMIT)

    def fetch_game_stats(
        self,
        game_id: str,
        game_date: date | None = None,
    ) -> PlayerStatsFetchResult:
        """Fetch player stats for a single game.

        When *game_date* is ``None`` the live feed's ``officialDate`` is
        used.  The live feed is fetched once and reused for both the date
        and the pitch-level data.

        Args:
            game_id: MLB game PK.
            game_date: Official game date.  If ``None``, fetched from API.

        Returns:
            :class:`PlayerStatsFetchResult`.
        """
        pre_fetched_live: dict[str, Any] | None = None

        if game_date is None:
            self._limiter.wait()
            meta_resp = _retry_request(
                _LIVE_FEED_URL.format(game_pk=game_id)
            )
            meta: dict[str, Any] = meta_resp.json()
            pre_fetched_live = meta
            official_date = (
                meta.get("gameData", {}).get("datetime", {}).get("officialDate", "")
            )
            game_date = (
                date.fromisoformat(official_date) if official_date else date.today()
            )

        return fetch_player_stats(
            game_id, game_date, self._limiter.wait, live_feed=pre_fetched_live,
        )

    def upsert_all(self, result: PlayerStatsFetchResult) -> int:
        """Persist all three tables from a fetch result in a single transaction.

        Args:
            result: The fetch result to persist.

        Returns:
            Total rows upserted across all three tables.
        """
        total = 0
        with self.db.engine.begin() as conn:
            for row in result.batting_rows:
                conn.execute(text(_BATTING_UPSERT_SQL), row)
                total += 1
            for row in result.pitching_rows:
                conn.execute(text(_PITCHING_UPSERT_SQL), row)
                total += 1
            for row in result.pitch_features:
                conn.execute(text(_PITCH_FEATURES_UPSERT_SQL), row)
                total += 1
        return total
