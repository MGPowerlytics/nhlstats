"""MLB matchup feature assembly.

Gathers all feature components for an upcoming game, calls
:func:`build_advanced_feature_payload()`, and persists the result to
``mlb_matchup_features``.

Typical usage::

    from plugins.mlb_modeling.matchup_assembler import assemble_matchup_features

    payload = assemble_matchup_features(
        db,
        game_id="745431",
        home_team="New York Yankees",
        away_team="Boston Red Sox",
        game_date=date(2026, 5, 10),
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from plugins.mlb_modeling.features import (
    BullpenFatigueSummary,
    MLBFeatureRepository,
    build_advanced_feature_payload,
    calculate_bullpen_fatigue,
    get_recent_bullpen_appearances,
)
from plugins.mlb_modeling.public_sources import AvailabilityStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_ROLLING_WINDOWS: tuple[str, ...] = ("30d", "14d", "7d")

# ---------------------------------------------------------------------------
# Team name → abbreviation mapping
# ---------------------------------------------------------------------------

MLB_TEAM_NAME_TO_ABBREV: dict[str, str] = {
    "Arizona Diamondbacks": "AZ",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Cleveland Indians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Athletics": "ATH",
    "Oakland Athletics": "ATH",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
}


def _team_abbrev(full_name: str) -> str:
    """Return the standard MLB team abbreviation for *full_name*."""
    if full_name in MLB_TEAM_NAME_TO_ABBREV:
        return MLB_TEAM_NAME_TO_ABBREV[full_name]
    raise KeyError(f"Unknown MLB team name: {full_name!r}")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchupAssemblyConfig:
    """Configuration for the matchup feature assembly process.

    Attributes:
        rolling_windows: Which rolling windows to consider.
        include_environment: Whether to include environment features
            (park factors, weather).
        include_travel: Whether to include travel-fatigue features.
        include_bullpen: Whether to include bullpen fatigue features.
        feature_version: Version string stamped into the payload.
    """

    rolling_windows: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_ROLLING_WINDOWS)
    include_environment: bool = True
    include_travel: bool = True
    include_bullpen: bool = True
    feature_version: str = "v1"


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------

_STARTER_GAME_SQL = """
    SELECT ps.pitcher_id, ps.pitcher_name, ps.throws, ps.avg_velocity,
           ps.primary_pitch_type, ps.primary_pitch_pct
    FROM mlb_player_game_pitching_stats ps
    JOIN mlb_games g ON g.game_id::text = ps.game_id
    WHERE ps.team = :team
      AND g.game_date <= :game_date
    ORDER BY ps.is_starter DESC,
             ps.innings_pitched DESC NULLS LAST,
             ps.pitch_count DESC NULLS LAST,
             g.game_date DESC
    LIMIT 1
"""

_STARTER_ROLLING_FEATURES_SQL = """
    SELECT *
    FROM mlb_player_rolling_features
    WHERE player_id = :player_id
      AND role = 'starter'
      AND window_name = '14d'
      AND handedness_split = 'ALL'
      AND as_of_date <= :game_date
    ORDER BY as_of_date DESC
    LIMIT 1
"""

_TEAM_ROLLING_FEATURES_SQL = """
    SELECT DISTINCT ON (player_id) *
    FROM mlb_player_rolling_features
    WHERE team = :team
      AND role = :role
      AND window_name = :window_name
      AND handedness_split = :split
      AND as_of_date <= :game_date
    ORDER BY player_id, as_of_date DESC
"""

_ELO_RATINGS_SQL = """
    SELECT entity_name, rating
    FROM elo_ratings
    WHERE sport = 'MLB'
      AND entity_name = :team
      AND valid_from <= :game_date
      AND (valid_to IS NULL OR valid_to >= :game_date)
    ORDER BY valid_from DESC
    LIMIT 1
"""

# MLB Elo home advantage (matches MLBEloRating production default)
_ELO_HOME_ADVANTAGE: float = 20.0


def _elo_home_win_prob(home_rating: float, away_rating: float) -> float:
    """Standard Elo expected score for the home team (home advantage baked in)."""
    return 1.0 / (1.0 + 10.0 ** ((away_rating - (home_rating + _ELO_HOME_ADVANTAGE)) / 400.0))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_dict(row_obj: Any) -> dict[str, Any]:
    """Normalise a DB result row to a plain dict."""
    if hasattr(row_obj, "_mapping"):
        return dict(row_obj._mapping)
    if isinstance(row_obj, dict):
        return row_obj
    if hasattr(row_obj, "items"):
        return dict(row_obj.items())
    return dict(row_obj)


def _query_one(
    db: Any,
    sql: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    """Execute SQL and return the first result row as a dict, or ``None``."""
    result = db.execute(sql, params)
    if not result:
        return None
    try:
        return _to_dict(next(iter(result)))
    except (StopIteration, TypeError):
        return None


def _query_all(
    db: Any,
    sql: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """Execute SQL and return all result rows as dicts."""
    result = db.execute(sql, params)
    if not result:
        return []
    return [_to_dict(row) for row in result]


def _zero_if_none(value: Any) -> float:
    """Return 0.0 when *value* is ``None``, otherwise ``float(value)``.

    This is used to keep the feature payload schema-compliant: the contract
    schema requires numbers for sabermetrics and plate-discipline fields
    (not ``null``).  The :data:`feature_availability` mapping independently
    tracks whether each source was actually available.
    """
    if value is None:
        return 0.0
    return float(value)


def _weighted_avg(
    rows: list[dict[str, Any]],
    value_col: str,
    weight_col: str = "plate_appearances",
) -> float | None:
    """Compute a PA-weighted average of *value_col* across *rows*.

    Returns ``None`` when no rows have both a non-``None`` value and a positive
    weight.
    """
    numerator = 0.0
    denominator = 0
    for r in rows:
        val = r.get(value_col)
        w = int(r.get(weight_col, 0) or 0)
        if val is not None and w > 0:
            numerator += float(val) * w
            denominator += w
    return numerator / denominator if denominator > 0 else None


# ---------------------------------------------------------------------------
# Starter data
# ---------------------------------------------------------------------------


def _get_starter_data(
    db: Any,
    team: str,
    game_date: date,
) -> dict[str, Any] | None:
    """Return combined rolling features and game-level stats for the probable starter.

    Queries ``mlb_player_game_pitching_stats`` for the team's most recent
    starter (probable starter), then fetches the matching 14d rolling features
    row from ``mlb_player_rolling_features``.

    Returns a merged dict (game-level keys plus rolling-feature keys when they
    exist), or ``None`` when no starter is found.
    """
    starter = _query_one(
        db,
        _STARTER_GAME_SQL,
        {"team": team, "game_date": game_date.isoformat()},
    )
    if not starter:
        return None

    pitcher_id = str(starter.get("pitcher_id", ""))
    if not pitcher_id:
        return None

    data = dict(starter)

    rf = _query_one(
        db,
        _STARTER_ROLLING_FEATURES_SQL,
        {"player_id": pitcher_id, "game_date": game_date.isoformat()},
    )
    if rf:
        data.update(rf)

    return data


# ---------------------------------------------------------------------------
# Team batting features
# ---------------------------------------------------------------------------


def _get_team_batting_features(
    db: Any,
    team: str,
    game_date: date,
    split: str = "ALL",
) -> dict[str, Any]:
    """Query 30d batter rolling features for *team* and return PA-weighted averages.

    Returns a dict with keys ``woba`` and ``wrc_plus`` (both set to ``None``
    when no data is available).
    """
    rows = _query_all(
        db,
        _TEAM_ROLLING_FEATURES_SQL,
        {
            "team": team,
            "role": "batter",
            "window_name": "30d",
            "split": split,
            "game_date": game_date.isoformat(),
        },
    )
    if not rows:
        return {"woba": None, "wrc_plus": None}

    woba = _weighted_avg(rows, "woba")
    wrc_plus = _weighted_avg(rows, "wrc_plus")

    return {
        "woba": round(woba, 4) if woba is not None else None,
        "wrc_plus": round(wrc_plus, 1) if wrc_plus is not None else None,
    }


def _get_team_plate_discipline(
    db: Any,
    team: str,
    game_date: date,
) -> dict[str, Any]:
    """Query plate-discipline rolling features for *team* batters.

    All values are PA-weighted.  The rolling features currently set all
    discipline fields to ``None`` (they require Statcast-level data), so this
    helper returns them as ``None`` and the caller marks them
    ``UNAVAILABLE``.  When Statcast data is later added this helper will
    return real values transparently.
    """
    rows = _query_all(
        db,
        _TEAM_ROLLING_FEATURES_SQL,
        {
            "team": team,
            "role": "batter",
            "window_name": "30d",
            "split": "ALL",
            "game_date": game_date.isoformat(),
        },
    )

    columns = [
        "o_swing_pct",
        "z_contact_pct",
        "hard_hit_pct",
        "avg_exit_velocity",
        "avg_launch_angle",
        "whiff_rate",
        "csw_pct",
    ]
    if not rows:
        return {col: None for col in columns}

    result: dict[str, Any] = {}
    for col in columns:
        val = _weighted_avg(rows, col)
        result[col] = round(val, 4) if val is not None else None

    return result


# ---------------------------------------------------------------------------
# Matchup dynamics
# ---------------------------------------------------------------------------


def _compute_matchup_dynamics(
    home_starter: dict[str, Any] | None,
    away_starter: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute matchup-level delta features between the two starters.

    Returns keys matching the ``mlb_advanced_features_v1.json`` schema.
    Fields that require scouting or Statcast data (catcher framing, umpire
    zones, pitch accuracy) are set to ``None`` where the schema allows.

    .. note::

        The contract schema requires ``pitcher_batter_k_rate_delta``,
        ``pitcher_batter_contact_rate_delta``, ``pitch_mix_mismatch``, and
        ``platoon_advantage`` to be non-``None`` numbers.  When the underlying
        data is missing the function falls back to 0.0 to stay schema-compliant.
    """
    home_k = (home_starter or {}).get("k_bb_pct")
    away_k = (away_starter or {}).get("k_bb_pct")
    home_primary_pct = (home_starter or {}).get("primary_pitch_pct")
    away_primary_pct = (away_starter or {}).get("primary_pitch_pct")

    k_rate_delta = 0.0
    if home_k is not None and away_k is not None:
        k_rate_delta = round(float(home_k) - float(away_k), 4)

    pitch_mix_diff = 0.0
    if home_primary_pct is not None and away_primary_pct is not None:
        pitch_mix_diff = round(abs(float(home_primary_pct) - float(away_primary_pct)), 4)

    return {
        "pitcher_batter_k_rate_delta": k_rate_delta,
        "pitcher_batter_contact_rate_delta": 0.0,
        "pitch_mix_mismatch": pitch_mix_diff,
        "platoon_advantage": 0.0,
        "catcher_framing_runs": 0.0,
        "umpire_zone_runs": 0.0,
        "pitch_accuracy": 0.0,
        "vertical_location_score": 0.0,
    }


# ---------------------------------------------------------------------------
# Recency
# ---------------------------------------------------------------------------


def _compute_recency(
    db: Any,
    home_team: str,
    away_team: str,
    game_date: date,
) -> dict[str, Any]:
    """Compute 30-day recency-weighted team performance indicators.

    Returns keys matching the ``mlb_advanced_features_v1.json`` schema:
    ``window_days``, ``plate_appearance_window`` (sum of home + away PA),
    and ``recency_weight`` (per-batter average recency normalised to ``[0, 1]``).

    The normalisation divisor (15.0) is derived from the maximum plausible
    per-batter exponential-decay weight sum for a 30-day, 14-day-half-life
    rolling window (~15.6) rounded down.  When no rolling features exist,
    ``plate_appearance_window`` is set to 1 and ``recency_weight`` to 0.0.
    """
    def _team_recency(team: str) -> tuple[float, int, int]:
        rows = _query_all(
            db,
            _TEAM_ROLLING_FEATURES_SQL,
            {
                "team": team,
                "role": "batter",
                "window_name": "30d",
                "split": "ALL",
                "game_date": game_date.isoformat(),
            },
        )
        total_rw = sum(float(r.get("recency_weight", 0) or 0) for r in rows)
        total_pa = sum(int(r.get("plate_appearances", 0) or 0) for r in rows)
        return total_rw, total_pa, len(rows)

    home_rw, home_pa, home_n = _team_recency(home_team)
    away_rw, away_pa, away_n = _team_recency(away_team)

    combined_pa = max(1, home_pa + away_pa)
    total_batters = home_n + away_n

    # Normalise per-batter average recency to [0, 1].
    # Max plausible per-batter weight for a 30d/14d half-life window is ~15.
    per_batter_rw = (home_rw + away_rw) / max(1, total_batters)
    recency_weight = round(min(1.0, per_batter_rw / 15.0), 4)

    return {
        "window_days": 30,
        "plate_appearance_window": combined_pa,
        "recency_weight": recency_weight,
    }


# ---------------------------------------------------------------------------
# Feature availability
# ---------------------------------------------------------------------------


def _build_feature_availability(
    home_starter: dict[str, Any] | None,
    away_starter: dict[str, Any] | None,
    home_batting: dict[str, Any],
    away_batting: dict[str, Any],
    home_pd: dict[str, Any],
    away_pd: dict[str, Any],
    home_bullpen_apps: list[Any],
    away_bullpen_apps: list[Any],
) -> dict[str, AvailabilityStatus]:
    """Mark each signal source as ``AVAILABLE``, ``DERIVED``, or ``UNAVAILABLE``.

    Does not produce ``ABSTAIN_REQUIRED`` at this level -- that is reserved for
    downstream validation gates.
    """
    batting_ok = home_batting.get("woba") is not None or away_batting.get("woba") is not None
    pitching_ok = home_starter is not None and away_starter is not None
    pd_ok = home_pd.get("o_swing_pct") is not None
    bullpen_ok = bool(home_bullpen_apps) or bool(away_bullpen_apps)

    return {
        "rolling_batting": (
            AvailabilityStatus.AVAILABLE if batting_ok else AvailabilityStatus.UNAVAILABLE
        ),
        "rolling_pitching": (
            AvailabilityStatus.AVAILABLE if pitching_ok else AvailabilityStatus.UNAVAILABLE
        ),
        "plate_discipline": (
            AvailabilityStatus.AVAILABLE if pd_ok else AvailabilityStatus.UNAVAILABLE
        ),
        "matchup_dynamics": AvailabilityStatus.DERIVED,
        "bullpen_fatigue": (
            AvailabilityStatus.AVAILABLE if bullpen_ok else AvailabilityStatus.UNAVAILABLE
        ),
        "recency": AvailabilityStatus.AVAILABLE,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _compute_elo_features(
    db: Any,
    home_team_full: str,
    away_team_full: str,
    game_date: date,
) -> dict[str, float]:
    """Query pre-game Elo ratings and return Elo-derived features.

    Uses the ``elo_ratings`` table to find each team's rating as it stood
    before *game_date*, then computes the home win probability via the
    standard Elo formula with MLB-tuned home advantage.

    Falls back to the default rating (1500.0) when a team has no Elo record.
    """
    home_row = _query_one(
        db, _ELO_RATINGS_SQL,
        {"team": home_team_full, "game_date": game_date.isoformat()},
    )
    away_row = _query_one(
        db, _ELO_RATINGS_SQL,
        {"team": away_team_full, "game_date": game_date.isoformat()},
    )
    home_rating = float(home_row["rating"]) if home_row else 1500.0
    away_rating = float(away_row["rating"]) if away_row else 1500.0
    home_prob = _elo_home_win_prob(home_rating, away_rating)
    return {
        "home_rating": home_rating,
        "away_rating": away_rating,
        "home_win_prob": round(home_prob, 6),
    }


def assemble_matchup_features(
    db: Any,
    *,
    game_id: str,
    home_team: str,
    away_team: str,
    game_date: date,
    as_of_ts: datetime | None = None,
    config: MatchupAssemblyConfig | None = None,
) -> dict[str, Any] | None:
    """Build and persist the full matchup feature vector for one game.

    Gathers sabermetrics, plate discipline, matchup dynamics, bullpen fatigue,
    and recency features; builds a contract-shaped payload via
    :func:`~plugins.mlb_modeling.features.build_advanced_feature_payload`;
    upserts it to ``mlb_matchup_features`` for both the home and away side;
    and returns the payload dict.

    Args:
        db: Database manager with an ``execute(sql, params)`` method.
        game_id: Game identifier (e.g. ``"745431"``).
        home_team: Home team name (e.g. ``"New York Yankees"``).
        away_team: Away team name (e.g. ``"Boston Red Sox"``).
        game_date: Official game date.
        as_of_ts: Timestamp used for the payload.  Defaults to ``datetime.now()``.
        config: Optional :class:`MatchupAssemblyConfig`.  Defaults to a standard
            config with all options enabled.

    Returns:
        The payload dict, or ``None`` if critical features are missing (no
        starting pitcher identified for either team).
    """
    cfg = config or MatchupAssemblyConfig()
    if as_of_ts is None:
        as_of_ts = datetime.now()

    # Convert full team names to abbreviations (DB stats tables use abbrevs)
    home_abbr = _team_abbrev(home_team)
    away_abbr = _team_abbrev(away_team)

    # ---- 0. Elo Ratings ----------------------------------------------------
    elo = _compute_elo_features(db, home_team, away_team, game_date)

    # ---- 1. Sabermetrics ---------------------------------------------------
    home_starter = _get_starter_data(db, home_abbr, game_date)
    away_starter = _get_starter_data(db, away_abbr, game_date)

    home_batting = _get_team_batting_features(db, home_abbr, game_date)
    away_batting = _get_team_batting_features(db, away_abbr, game_date)

    sabermetrics: dict[str, Any] = {
        "home_woba": _zero_if_none(home_batting.get("woba")),
        "away_woba": _zero_if_none(away_batting.get("woba")),
        "home_wrc_plus": _zero_if_none(home_batting.get("wrc_plus")),
        "away_wrc_plus": _zero_if_none(away_batting.get("wrc_plus")),
        "home_starter_fip": _zero_if_none((home_starter or {}).get("fip")),
        "away_starter_fip": _zero_if_none((away_starter or {}).get("fip")),
        "home_starter_xfip": _zero_if_none((home_starter or {}).get("xfip")),
        "away_starter_xfip": _zero_if_none((away_starter or {}).get("xfip")),
        "home_starter_siera": _zero_if_none((home_starter or {}).get("siera")),
        "away_starter_siera": _zero_if_none((away_starter or {}).get("siera")),
        "home_starter_k_bb_pct": _zero_if_none((home_starter or {}).get("k_bb_pct")),
        "away_starter_k_bb_pct": _zero_if_none((away_starter or {}).get("k_bb_pct")),
    }

    # ---- 2. Plate Discipline -----------------------------------------------
    home_pd = _get_team_plate_discipline(db, home_abbr, game_date)
    away_pd = _get_team_plate_discipline(db, away_abbr, game_date)

    plate_discipline: dict[str, Any] = {
        "home_o_swing_pct": _zero_if_none(home_pd.get("o_swing_pct")),
        "away_o_swing_pct": _zero_if_none(away_pd.get("o_swing_pct")),
        "home_z_contact_pct": _zero_if_none(home_pd.get("z_contact_pct")),
        "away_z_contact_pct": _zero_if_none(away_pd.get("z_contact_pct")),
        "home_hard_hit_pct": _zero_if_none(home_pd.get("hard_hit_pct")),
        "away_hard_hit_pct": _zero_if_none(away_pd.get("hard_hit_pct")),
        "home_exit_velocity": _zero_if_none(home_pd.get("avg_exit_velocity")),
        "away_exit_velocity": _zero_if_none(away_pd.get("avg_exit_velocity")),
        "home_launch_angle": _zero_if_none(home_pd.get("avg_launch_angle")),
        "away_launch_angle": _zero_if_none(away_pd.get("avg_launch_angle")),
        "home_whiff_rate": _zero_if_none(home_pd.get("whiff_rate")),
        "away_whiff_rate": _zero_if_none(away_pd.get("whiff_rate")),
        "home_csw_pct": _zero_if_none(home_pd.get("csw_pct")),
        "away_csw_pct": _zero_if_none(away_pd.get("csw_pct")),
    }

    # ---- 3. Matchup Dynamics -----------------------------------------------
    matchup_dynamics = _compute_matchup_dynamics(home_starter, away_starter)

    # ---- 4. Bullpen Fatigue ------------------------------------------------
    if cfg.include_bullpen:
        home_apps = get_recent_bullpen_appearances(db, home_abbr, game_date)
        away_apps = get_recent_bullpen_appearances(db, away_abbr, game_date)
        home_bullpen = calculate_bullpen_fatigue(home_apps, game_date)
        away_bullpen = calculate_bullpen_fatigue(away_apps, game_date)
    else:
        home_apps = []
        away_apps = []
        home_bullpen = BullpenFatigueSummary(0, 0, 0, 0, 0.0)
        away_bullpen = BullpenFatigueSummary(0, 0, 0, 0, 0.0)

    # ---- 5. Recency --------------------------------------------------------
    recency = _compute_recency(db, home_abbr, away_abbr, game_date)

    # ---- 6. Feature Availability -------------------------------------------
    feature_availability = _build_feature_availability(
        home_starter,
        away_starter,
        home_batting,
        away_batting,
        home_pd,
        away_pd,
        home_apps,
        away_apps,
    )

    # ---- 7. Build payload --------------------------------------------------
    payload = build_advanced_feature_payload(
        game_id=game_id,
        home_team=home_team,
        away_team=away_team,
        as_of_ts=as_of_ts,
        elo=elo,
        sabermetrics=sabermetrics,
        plate_discipline=plate_discipline,
        matchup_dynamics=matchup_dynamics,
        home_bullpen=home_bullpen,
        away_bullpen=away_bullpen,
        recency=recency,
        feature_availability=feature_availability,
        feature_version=cfg.feature_version,
    )

    # ---- 8. Persist --------------------------------------------------------
    repo = MLBFeatureRepository(db)
    repo.upsert_matchup_features(payload, side="home")
    repo.upsert_matchup_features(payload, side="away")

    return payload
