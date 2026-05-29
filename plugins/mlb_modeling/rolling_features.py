"""
Rolling-window feature computation for MLB player stats.

Transforms raw per-game player stats from
:class:`~plugins.mlb_modeling.player_stats_fetcher` into derived rolling-window
features and upserts them into ``mlb_player_rolling_features``.

Usage::

    from plugins.mlb_modeling.rolling_features import (
        compute_rolling_features,
        compute_all_rolling_features,
        upsert_rolling_features,
    )

    rows = compute_rolling_features(db, "660271", as_of_date=date(2026, 5, 25))
    upsert_rolling_features(db, rows)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from math import exp
from typing import Any, Optional

from plugins.db_manager import DBManager
from plugins.mlb_modeling.features import recency_weighted_average
from plugins.utils import to_int, to_float

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE: str = "mlb_sabermetrics_rolling"
FEATURE_VERSION: str = "v1"

# wOBA linear weights (FanGraphs typical modern values)
_WOBA_WEIGHTS: dict[str, float] = {
    "bb": 0.690,
    "hbp": 0.722,
    "1b": 0.880,
    "2b": 1.249,
    "3b": 1.576,
    "hr": 2.031,
}

# Season constants from FanGraphs public data
_SEASON_CONSTANTS: dict[int, dict[str, float]] = {
    2021: {"lg_wOBA": 0.317, "fip_constant": 3.08},
    2022: {"lg_wOBA": 0.310, "fip_constant": 3.07},
    2023: {"lg_wOBA": 0.313, "fip_constant": 3.05},
    2024: {"lg_wOBA": 0.312, "fip_constant": 3.06},
    2025: {"lg_wOBA": 0.312, "fip_constant": 3.06},
    2026: {"lg_wOBA": 0.312, "fip_constant": 3.06},
}

_DEFAULT_SEASON: int = 2026

HALF_LIFE_LN2: float = 0.6931471805599453


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RollingWindowConfig:
    """Configuration for one rolling window."""

    window_days: int
    window_name: str
    half_life_days: float = 14.0


WINDOWS: list[RollingWindowConfig] = [
    RollingWindowConfig(7, "7d", half_life_days=7.0),
    RollingWindowConfig(14, "14d", half_life_days=10.0),
    RollingWindowConfig(30, "30d", half_life_days=14.0),
]

SPLITS: list[str] = ["ALL", "VS_RHP", "VS_LHP"]
ROLES: list[str] = ["batter", "pitcher", "starter"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_season_constants(year: int) -> dict[str, float]:
    """Return season constants dict, falling back to the most recent year."""
    return _SEASON_CONSTANTS.get(year, _SEASON_CONSTANTS[_DEFAULT_SEASON])





def _recency_weight(game_age_days: int, half_life_days: float) -> float:
    """Return the exponential-decay recency weight for one observation."""
    return exp(-HALF_LIFE_LN2 * max(0, game_age_days) / max(1.0, half_life_days))


def _parse_game_date(raw: Any) -> Optional[date]:
    """Normalise a raw game_date value to a :class:`~datetime.date`.

    Handles ``date`` objects, ISO-format strings, and ``datetime`` objects.
    Returns ``None`` when the value cannot be parsed.
    """
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except (ValueError, TypeError):
            return None
    if hasattr(raw, "date") and callable(raw.date):
        # datetime or Timestamp
        try:
            return raw.date()
        except Exception:
            return None
    return None


def _compute_woba_from_game(game: dict) -> Optional[float]:
    """Re-compute wOBA for one game from its counting stats.

    Uses the stored per-game ``woba`` when available, otherwise falls back to a
    computation from available counting stats.
    """
    woba = game.get("woba")
    if woba is not None:
        return float(woba)

    # Fallback: compute from counting stats (HBP and SF may be zero)
    ab = to_int(game.get("at_bats"))
    walks = to_int(game.get("walks"))
    hits = to_int(game.get("hits"))
    doubles = to_int(game.get("doubles"))
    triples = to_int(game.get("triples"))
    hr = to_int(game.get("home_runs"))

    pa = ab + walks
    if pa <= 0:
        return None

    singles = max(0, hits - doubles - triples - hr)
    numerator = (
        _WOBA_WEIGHTS["bb"] * walks
        + _WOBA_WEIGHTS["1b"] * singles
        + _WOBA_WEIGHTS["2b"] * doubles
        + _WOBA_WEIGHTS["3b"] * triples
        + _WOBA_WEIGHTS["hr"] * hr
    )
    return numerator / pa


def _compute_wrc_plus(woba: Optional[float], lg_woba: float = 0.312) -> Optional[float]:
    """Compute simplified wRC+ = (wOBA / lg_wOBA) * 100."""
    if woba is None or lg_woba <= 0:
        return None
    return round((woba / lg_woba) * 100, 1)


def _compute_fip_from_game(game: dict, fip_constant: float = 3.06) -> Optional[float]:
    """Re-compute FIP for one pitching game from its counting stats."""
    ip = to_float(game.get("innings_pitched"))
    if ip <= 0:
        return None
    hr = to_int(game.get("home_runs_allowed"))
    bb = to_int(game.get("walks"))
    k = to_int(game.get("strikeouts"))

    fip_val = (13 * hr + 3 * bb - 2 * k) / ip + fip_constant
    return round(fip_val, 2)


def _compute_siera_from_game(game: dict) -> Optional[float]:
    """Compute simplified SIERA for one pitching game."""
    pa = to_int(game.get("batters_faced"))
    if pa < 4:
        return None
    k = to_int(game.get("strikeouts"))
    bb = to_int(game.get("walks"))
    k_rate = k / pa
    bb_rate = bb / pa
    siera_val = (
        6.145
        - 16.986 * k_rate
        + 11.434 * k_rate * k_rate
        - 1.858 * bb_rate
        + 7.653 * bb_rate * bb_rate
        - 4.005 * k_rate * bb_rate
    )
    return round(max(0.0, siera_val), 2)


def _compute_k_bb_pct_from_game(game: dict) -> Optional[float]:
    """Compute K-BB% for one pitching game."""
    pa = to_int(game.get("batters_faced"))
    if pa <= 0:
        return None
    k = to_int(game.get("strikeouts"))
    bb = to_int(game.get("walks"))
    return round((k - bb) / pa * 100, 2)


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------

_BATTER_GAMES_SQL = """
    SELECT
        b.game_id,
        b.player_id,
        b.player_name,
        b.team,
        b.opponent,
        b.is_home,
        b.batting_order,
        b.bats,
        b.plate_appearances,
        b.at_bats,
        b.hits,
        b.doubles,
        b.triples,
        b.home_runs,
        b.walks,
        b.strikeouts,
        b.woba,
        b.wrc_plus,
        b.o_swing_pct,
        b.z_contact_pct,
        b.hard_hit_pct,
        b.avg_exit_velocity,
        b.avg_launch_angle,
        b.whiff_rate,
        b.csw_pct,
        g.game_date,
        starter.throws AS opposing_starter_throws
    FROM mlb_player_game_batting_stats b
    INNER JOIN mlb_games g
        ON b.game_id = g.game_id::text
    LEFT JOIN mlb_player_game_pitching_stats starter
        ON b.game_id = starter.game_id
        AND starter.team = b.opponent
        AND starter.is_starter = TRUE
    WHERE b.player_id = :player_id
      AND g.game_date < :as_of_date
    ORDER BY g.game_date DESC
"""

_PITCHER_GAMES_SQL = """
    SELECT
        p.game_id,
        p.pitcher_id,
        p.pitcher_name,
        p.team,
        p.opponent,
        p.is_home,
        p.is_starter,
        p.throws,
        p.innings_pitched,
        p.pitch_count,
        p.batters_faced,
        p.strikeouts,
        p.walks,
        p.home_runs_allowed,
        p.earned_runs,
        p.fip,
        p.xfip,
        p.siera,
        p.k_bb_pct,
        p.o_swing_pct,
        p.z_contact_pct,
        p.hard_hit_pct_allowed,
        p.avg_exit_velocity_allowed,
        p.whiff_rate,
        p.csw_pct,
        p.primary_pitch_type,
        p.primary_pitch_pct,
        p.avg_velocity,
        g.game_date
    FROM mlb_player_game_pitching_stats p
    INNER JOIN mlb_games g
        ON p.game_id = g.game_id::text
    WHERE p.pitcher_id = :pitcher_id
      AND g.game_date < :as_of_date
    ORDER BY g.game_date DESC
"""

_PITCHER_GAMES_AS_STARTER_SQL = """
    SELECT
        p.game_id,
        p.pitcher_id,
        p.pitcher_name,
        p.team,
        p.opponent,
        p.is_home,
        p.is_starter,
        p.throws,
        p.innings_pitched,
        p.pitch_count,
        p.batters_faced,
        p.strikeouts,
        p.walks,
        p.home_runs_allowed,
        p.earned_runs,
        p.fip,
        p.xfip,
        p.siera,
        p.k_bb_pct,
        p.o_swing_pct,
        p.z_contact_pct,
        p.hard_hit_pct_allowed,
        p.avg_exit_velocity_allowed,
        p.whiff_rate,
        p.csw_pct,
        p.primary_pitch_type,
        p.primary_pitch_pct,
        p.avg_velocity,
        g.game_date
    FROM mlb_player_game_pitching_stats p
    INNER JOIN mlb_games g
        ON p.game_id = g.game_id::text
    WHERE p.pitcher_id = :pitcher_id
      AND p.is_starter = TRUE
      AND g.game_date < :as_of_date
    ORDER BY g.game_date DESC
"""

_ALL_PLAYER_IDS_BATTING_SQL = """
    SELECT DISTINCT player_id
    FROM mlb_player_game_batting_stats
"""

_ALL_PLAYER_IDS_PITCHING_SQL = """
    SELECT DISTINCT pitcher_id
    FROM mlb_player_game_pitching_stats
"""

_UPSERT_SQL = """
    INSERT INTO mlb_player_rolling_features
        (as_of_date, player_id, player_name, team, role,
         window_name, handedness_split,
         plate_appearances, innings_pitched,
         woba, wrc_plus, fip, xfip, siera, k_bb_pct,
         o_swing_pct, z_contact_pct, hard_hit_pct,
         avg_exit_velocity, avg_launch_angle, whiff_rate, csw_pct,
         recency_weight, source, feature_version, updated_at)
    VALUES
        (:as_of_date, :player_id, :player_name, :team, :role,
         :window_name, :handedness_split,
         :plate_appearances, :innings_pitched,
         :woba, :wrc_plus, :fip, :xfip, :siera, :k_bb_pct,
         :o_swing_pct, :z_contact_pct, :hard_hit_pct,
         :avg_exit_velocity, :avg_launch_angle, :whiff_rate, :csw_pct,
         :recency_weight, :source, :feature_version, NOW())
    ON CONFLICT (as_of_date, player_id, role, window_name, handedness_split)
    DO UPDATE SET
        player_name      = EXCLUDED.player_name,
        team             = EXCLUDED.team,
        plate_appearances = EXCLUDED.plate_appearances,
        innings_pitched  = EXCLUDED.innings_pitched,
        woba             = EXCLUDED.woba,
        wrc_plus         = EXCLUDED.wrc_plus,
        fip              = EXCLUDED.fip,
        xfip             = EXCLUDED.xfip,
        siera            = EXCLUDED.siera,
        k_bb_pct         = EXCLUDED.k_bb_pct,
        o_swing_pct      = EXCLUDED.o_swing_pct,
        z_contact_pct    = EXCLUDED.z_contact_pct,
        hard_hit_pct     = EXCLUDED.hard_hit_pct,
        avg_exit_velocity = EXCLUDED.avg_exit_velocity,
        avg_launch_angle = EXCLUDED.avg_launch_angle,
        whiff_rate       = EXCLUDED.whiff_rate,
        csw_pct          = EXCLUDED.csw_pct,
        recency_weight   = EXCLUDED.recency_weight,
        source           = EXCLUDED.source,
        feature_version  = EXCLUDED.feature_version,
        updated_at       = NOW()
"""


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _fetch_batter_games(
    db: DBManager,
    player_id: str,
    as_of_date: date,
) -> list[dict[str, Any]]:
    """Return all batting games for *player_id* before *as_of_date*."""
    result = db.execute(
        _BATTER_GAMES_SQL,
        {"player_id": player_id, "as_of_date": as_of_date},
    )
    if result is None:
        return []
    rows = []
    for row in result:
        d = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
        rows.append(d)
    return rows


def _fetch_pitcher_games(
    db: DBManager,
    pitcher_id: str,
    as_of_date: date,
    *,
    is_starter: bool = False,
) -> list[dict[str, Any]]:
    """Return pitching games for *pitcher_id* before *as_of_date*."""
    sql = _PITCHER_GAMES_AS_STARTER_SQL if is_starter else _PITCHER_GAMES_SQL
    result = db.execute(
        sql,
        {"pitcher_id": pitcher_id, "as_of_date": as_of_date},
    )
    if result is None:
        return []
    rows = []
    for row in result:
        d = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
        rows.append(d)
    return rows


# ---------------------------------------------------------------------------
# Rolling computation helpers
# ---------------------------------------------------------------------------


def _filter_games_by_window(
    games: list[dict[str, Any]],
    as_of_date: date,
    window_days: int,
) -> list[dict[str, Any]]:
    """Filter games to those within *window_days* before *as_of_date*."""
    window_start = as_of_date - timedelta(days=window_days)
    filtered = []
    for g in games:
        gd = _parse_game_date(g.get("game_date"))
        if gd is None:
            continue
        if window_start <= gd < as_of_date:
            filtered.append(g)
    return filtered


def _compute_recency_weight(
    games: list[dict[str, Any]],
    as_of_date: date,
    half_life_days: float,
) -> float:
    """Return the sum of recency weights for the given games."""
    total_weight = 0.0
    for g in games:
        gd = _parse_game_date(g.get("game_date"))
        if gd is None:
            continue
        age = (as_of_date - gd).days
        total_weight += _recency_weight(age, half_life_days)
    return round(total_weight, 4)


def _compute_batter_rolling_features_for_window(
    games: list[dict[str, Any]],
    player_id: str,
    player_name: str,
    team: Optional[str],
    as_of_date: date,
    window: RollingWindowConfig,
    split: str,
) -> Optional[dict[str, Any]]:
    """Compute rolling features for a batter for one window and handedness split.

    Args:
        games: Pre-filtered list of batter games.
        player_id: The batter's MLB ID.
        player_name: The batter's full name.
        team: The batter's current team abbreviation.
        as_of_date: Reference date for the rolling computation.
        window: The rolling window configuration.
        split: Handedness split (``ALL``, ``VS_RHP``, or ``VS_LHP``).

    Returns:
        A row dict for ``mlb_player_rolling_features``, or ``None`` if no games
        qualify.
    """
    # Filter by handedness split
    if split == "VS_RHP":
        games = [g for g in games if g.get("opposing_starter_throws") == "R"]
    elif split == "VS_LHP":
        games = [g for g in games if g.get("opposing_starter_throws") == "L"]

    if not games:
        return None

    # --- Sum counting stats ---
    total_pa = sum(to_int(g.get("plate_appearances")) for g in games)
    total_ab = sum(to_int(g.get("at_bats")) for g in games)
    total_hits = sum(to_int(g.get("hits")) for g in games)
    total_doubles = sum(to_int(g.get("doubles")) for g in games)
    total_triples = sum(to_int(g.get("triples")) for g in games)
    total_hr = sum(to_int(g.get("home_runs")) for g in games)
    total_walks = sum(to_int(g.get("walks")) for g in games)

    # --- Recency-weighted rates ---
    woba_obs: list[tuple[float, int]] = []
    latest_season = _DEFAULT_SEASON

    for g in games:
        gd = _parse_game_date(g.get("game_date"))
        if gd is None:
            continue
        age = (as_of_date - gd).days
        latest_season = max(latest_season, gd.year)
        woba_val = _compute_woba_from_game(g)
        if woba_val is not None:
            woba_obs.append((woba_val, age))

    woba = recency_weighted_average(woba_obs, window.half_life_days)

    sc = _get_season_constants(latest_season)
    lg_woba = sc.get("lg_wOBA", 0.312)
    wrc_plus = _compute_wrc_plus(woba, lg_woba)

    recency_weight = _compute_recency_weight(games, as_of_date, window.half_life_days)

    # Plate-discipline / statcast fields are not available from boxscore data
    return {
        "as_of_date": as_of_date,
        "player_id": player_id,
        "player_name": player_name,
        "team": team,
        "role": "batter",
        "window_name": window.window_name,
        "handedness_split": split,
        "plate_appearances": total_pa,
        "innings_pitched": None,
        "woba": round(woba, 4) if woba is not None else None,
        "wrc_plus": wrc_plus,
        "fip": None,
        "xfip": None,
        "siera": None,
        "k_bb_pct": None,
        "o_swing_pct": None,
        "z_contact_pct": None,
        "hard_hit_pct": None,
        "avg_exit_velocity": None,
        "avg_launch_angle": None,
        "whiff_rate": None,
        "csw_pct": None,
        "recency_weight": recency_weight,
        "source": SOURCE,
        "feature_version": FEATURE_VERSION,
    }


def _compute_pitcher_rolling_features_for_window(
    games: list[dict[str, Any]],
    player_id: str,
    player_name: str,
    team: Optional[str],
    as_of_date: date,
    window: RollingWindowConfig,
    role: str,
) -> Optional[dict[str, Any]]:
    """Compute rolling features for a pitcher for one window.

    Args:
        games: Pre-filtered list of pitcher games.
        player_id: The pitcher's MLB ID.
        player_name: The pitcher's full name.
        team: The pitcher's current team abbreviation.
        as_of_date: Reference date for the rolling computation.
        window: The rolling window configuration.
        role: ``"pitcher"`` or ``"starter"``.

    Returns:
        A row dict for ``mlb_player_rolling_features``, or ``None`` if no games
        qualify.
    """
    if not games:
        return None

    # --- Sum counting stats ---
    total_ip = sum(to_float(g.get("innings_pitched")) for g in games)
    total_pa = sum(to_int(g.get("batters_faced")) for g in games)
    total_k = sum(to_int(g.get("strikeouts")) for g in games)
    total_bb = sum(to_int(g.get("walks")) for g in games)
    total_hr = sum(to_int(g.get("home_runs_allowed")) for g in games)
    total_pitch_count = sum(to_int(g.get("pitch_count")) for g in games)

    # --- Recency-weighted rates ---
    fip_obs: list[tuple[float, int]] = []
    siera_obs: list[tuple[float, int]] = []
    k_bb_obs: list[tuple[float, int]] = []

    latest_season = _DEFAULT_SEASON

    for g in games:
        gd = _parse_game_date(g.get("game_date"))
        if gd is None:
            continue
        latest_season = max(latest_season, gd.year)
        age = (as_of_date - gd).days

        fip_val = _compute_fip_from_game(g)
        if fip_val is not None:
            fip_obs.append((fip_val, age))

        siera_val = _compute_siera_from_game(g)
        if siera_val is not None:
            siera_obs.append((siera_val, age))

        k_bb_val = _compute_k_bb_pct_from_game(g)
        if k_bb_val is not None:
            k_bb_obs.append((k_bb_val, age))

    sc = _get_season_constants(latest_season)
    fip_constant = sc.get("fip_constant", 3.06)

    # Recompute FIP with recency weighting
    if fip_obs:
        # Weighted average FIP
        weighted_fip = recency_weighted_average(fip_obs, window.half_life_days)
    elif total_ip > 0 and total_pa > 0:
        # Fallback: compute from totals
        weighted_fip = (13 * total_hr + 3 * total_bb - 2 * total_k) / total_ip + fip_constant
        weighted_fip = round(weighted_fip, 2) if weighted_fip is not None else None
    else:
        weighted_fip = None

    fip = round(weighted_fip, 2) if weighted_fip is not None else None
    siera = recency_weighted_average(siera_obs, window.half_life_days)
    k_bb_pct = recency_weighted_average(k_bb_obs, window.half_life_days)

    recency_weight = _compute_recency_weight(games, as_of_date, window.half_life_days)

    return {
        "as_of_date": as_of_date,
        "player_id": player_id,
        "player_name": player_name,
        "team": team,
        "role": role,
        "window_name": window.window_name,
        "handedness_split": "ALL",
        "plate_appearances": total_pa,
        "innings_pitched": round(total_ip, 2),
        "woba": None,
        "wrc_plus": None,
        "fip": fip,
        "xfip": None,
        "siera": round(siera, 2) if siera is not None else None,
        "k_bb_pct": round(k_bb_pct, 2) if k_bb_pct is not None else None,
        "o_swing_pct": None,
        "z_contact_pct": None,
        "hard_hit_pct": None,
        "avg_exit_velocity": None,
        "avg_launch_angle": None,
        "whiff_rate": None,
        "csw_pct": None,
        "recency_weight": recency_weight,
        "source": SOURCE,
        "feature_version": FEATURE_VERSION,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_rolling_features(
    db: DBManager,
    player_id: str,
    as_of_date: date,
) -> list[dict[str, Any]]:
    """Compute rolling stats for one player on one date across all windows/splits.

    Automatically detects whether *player_id* corresponds to a batter, pitcher,
    or both (two-way player).  For batters, all three handedness splits are
    computed.  For pitchers, only the ``ALL`` split is computed.

    Args:
        db: Database manager instance.
        player_id: MLB player ID (e.g. ``"660271"``).
        as_of_date: Reference date; only games strictly before this date are
            included.

    Returns:
        List of row dicts ready for :func:`upsert_rolling_features`.
    """
    rows: list[dict[str, Any]] = []

    # ---- Batter ----
    batter_games = _fetch_batter_games(db, player_id, as_of_date)
    if batter_games:
        player_name = batter_games[0].get("player_name", "")
        team: Optional[str] = batter_games[0].get("team")

        for window in WINDOWS:
            window_games = _filter_games_by_window(batter_games, as_of_date, window.window_days)
            if not window_games:
                continue
            for split in SPLITS:
                row = _compute_batter_rolling_features_for_window(
                    window_games,
                    player_id,
                    player_name,
                    team,
                    as_of_date,
                    window,
                    split,
                )
                if row is not None:
                    rows.append(row)

    # ---- Pitcher ----
    pitcher_games = _fetch_pitcher_games(db, player_id, as_of_date, is_starter=False)
    if pitcher_games:
        player_name = pitcher_games[0].get("pitcher_name", "")
        team = pitcher_games[0].get("team")

        for window in WINDOWS:
            window_games = _filter_games_by_window(pitcher_games, as_of_date, window.window_days)
            if not window_games:
                continue
            row = _compute_pitcher_rolling_features_for_window(
                window_games,
                player_id,
                player_name,
                team,
                as_of_date,
                window,
                role="pitcher",
            )
            if row is not None:
                rows.append(row)

    # ---- Starter ----
    starter_games = _fetch_pitcher_games(db, player_id, as_of_date, is_starter=True)
    if starter_games:
        player_name = starter_games[0].get("pitcher_name", "")
        team = starter_games[0].get("team")

        for window in WINDOWS:
            window_games = _filter_games_by_window(starter_games, as_of_date, window.window_days)
            if not window_games:
                continue
            row = _compute_pitcher_rolling_features_for_window(
                window_games,
                player_id,
                player_name,
                team,
                as_of_date,
                window,
                role="starter",
            )
            if row is not None:
                rows.append(row)

    return rows


def compute_all_rolling_features(
    db: DBManager,
    as_of_date: date,
    player_ids: Optional[list[str]] = None,
) -> int:
    """Compute rolling features for all (or specified) active players.

    When ``player_ids`` is ``None``, discovers all distinct player IDs from
    both the batting and pitching stats tables.

    Args:
        db: Database manager instance.
        as_of_date: Reference date for the rolling computation.
        player_ids: Optional explicit list of player IDs to process.

    Returns:
        Total number of feature rows upserted.
    """
    if player_ids is None:
        seen: set[str] = set()
        ids: list[str] = []

        batting_result = db.execute(_ALL_PLAYER_IDS_BATTING_SQL)
        if batting_result:
            for row in batting_result:
                pid = str(row[0]) if not hasattr(row, "_mapping") else str(row._mapping[list(row._mapping.keys())[0]])
                if pid and pid not in seen:
                    seen.add(pid)
                    ids.append(pid)

        pitching_result = db.execute(_ALL_PLAYER_IDS_PITCHING_SQL)
        if pitching_result:
            for row in pitching_result:
                pid = str(row[0]) if not hasattr(row, "_mapping") else str(row._mapping[list(row._mapping.keys())[0]])
                if pid and pid not in seen:
                    seen.add(pid)
                    ids.append(pid)

        player_ids = ids

    all_rows: list[dict[str, Any]] = []
    for pid in player_ids:
        try:
            rows = compute_rolling_features(db, pid, as_of_date)
            all_rows.extend(rows)
        except Exception:
            logger.exception("Failed to compute rolling features for player %s", pid)

    if not all_rows:
        return 0

    return upsert_rolling_features(db, all_rows)


def upsert_rolling_features(
    db: DBManager,
    rows: list[dict[str, Any]],
) -> int:
    """Upsert rolling feature rows into ``mlb_player_rolling_features``.

    Args:
        db: Database manager instance.
        rows: Row dicts as returned by :func:`compute_rolling_features`.

    Returns:
        Number of rows upserted.
    """
    for row in rows:
        db.execute(_UPSERT_SQL, row)
    return len(rows)
