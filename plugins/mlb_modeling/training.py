"""MLB model training pipeline with strict temporal leakage prevention.

Builds training rows for completed games by reconstructing the feature vector
as it would have appeared BEFORE the game was played (only data available up to
``game_date - 1``).  The reconstructed features mirror the runtime output of
:func:`~plugins.mlb_modeling.matchup_assembler.assemble_matchup_features`.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from plugins.mlb_modeling.features import (
    BullpenFatigueSummary,
    RelieverAppearance,
    calculate_bullpen_fatigue,
    get_recent_bullpen_appearances,
)
from plugins.mlb_modeling.models import (
    DEFAULT_MONEYLINE_MODEL_PATH,
    MoneylineModelArtifact,
    MoneylineTrainingRow,
    load_moneyline_model_artifact,
    train_logistic_moneyline_model,
)
from plugins.mlb_modeling.matchup_assembler import (
    _compute_matchup_dynamics,
    _query_all,
    _query_one,
    _to_dict,
    _zero_if_none,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL Queries — strict temporal cutoff (< game_date, never <=)
# ---------------------------------------------------------------------------

_COMPLETED_GAMES_SQL = """
    SELECT game_id::TEXT AS game_id, home_team, away_team, game_date,
           home_score, away_score
    FROM mlb_games
    WHERE game_date BETWEEN :start_date AND :end_date
      AND status IN ('Final', 'Game Over', 'Completed Early')
      AND home_score IS NOT NULL
      AND away_score IS NOT NULL
      AND home_team IS NOT NULL
      AND away_team IS NOT NULL
    ORDER BY game_date
"""

_ACTUAL_STARTER_SQL = """
    SELECT pitcher_id, pitcher_name, throws, avg_velocity,
           primary_pitch_type, primary_pitch_pct
    FROM mlb_player_game_pitching_stats
    WHERE game_id = :game_id
      AND team = :team
      AND is_starter = TRUE
    LIMIT 1
"""

_PRE_GAME_STARTER_ROLLING_SQL = """
    SELECT *
    FROM mlb_player_rolling_features
    WHERE player_id = :player_id
      AND role = 'starter'
      AND window_name = '14d'
      AND handedness_split = 'ALL'
      AND as_of_date < :game_date
    ORDER BY as_of_date DESC
    LIMIT 1
"""

_PRE_GAME_TEAM_ROLLING_SQL = """
    SELECT DISTINCT ON (player_id) *
    FROM mlb_player_rolling_features
    WHERE team = :team
      AND role = :role
      AND window_name = :window_name
      AND handedness_split = :split
      AND as_of_date < :game_date
    ORDER BY player_id, as_of_date DESC
"""

_TEAM_PRIOR_GAME_COUNT_SQL = """
    SELECT COUNT(*) AS game_count
    FROM mlb_games
    WHERE (home_team = :team OR away_team = :team)
      AND game_date < :game_date
      AND status IN ('Final', 'Game Over', 'Completed Early')
"""

_PRE_GAME_BULLPEN_SQL = """
    SELECT pitcher_id, game_date, pitch_count, avg_velocity
    FROM mlb_player_game_pitching_stats
    WHERE team = :team
      AND is_starter = FALSE
      AND game_date >= :start_date
      AND game_date < :game_date
    ORDER BY game_date DESC
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_actual_starter(
    db: Any, game_id: str, team: str
) -> dict[str, Any] | None:
    """Return the actual starting pitcher for a completed game."""
    result = db.execute(_ACTUAL_STARTER_SQL, {"game_id": game_id, "team": team})
    if not result:
        return None
    try:
        return _to_dict(next(iter(result)))
    except (StopIteration, TypeError):
        return None


def _get_team_prior_game_count(db: Any, team: str, game_date: date) -> int:
    """Count completed games for a team strictly before *game_date*."""
    result = db.execute(
        _TEAM_PRIOR_GAME_COUNT_SQL,
        {"team": team, "game_date": game_date},
    )
    if not result:
        return 0
    try:
        row = _to_dict(next(iter(result)))
        return int(row.get("game_count", 0) or 0)
    except (StopIteration, TypeError):
        return 0


def _get_pre_game_starter_rolling(
    db: Any, player_id: str, game_date: date
) -> dict[str, Any] | None:
    """Pre-game rolling features for a starter (``as_of_date < game_date``)."""
    return _query_one(
        db,
        _PRE_GAME_STARTER_ROLLING_SQL,
        {"player_id": player_id, "game_date": game_date},
    )


def _weighted_avg(
    rows: list[dict[str, Any]],
    value_col: str,
    weight_col: str = "plate_appearances",
) -> float | None:
    """PA-weighted average of *value_col* across *rows*."""
    numerator = 0.0
    denominator = 0
    for r in rows:
        val = r.get(value_col)
        w = int(r.get(weight_col, 0) or 0)
        if val is not None and w > 0:
            numerator += float(val) * w
            denominator += w
    return numerator / denominator if denominator > 0 else None


def _get_pre_game_team_batting_features(
    db: Any,
    team: str,
    game_date: date,
    split: str = "ALL",
) -> dict[str, Any]:
    """30d pre-game team batting features (``as_of_date < game_date``)."""
    rows = _query_all(
        db,
        _PRE_GAME_TEAM_ROLLING_SQL,
        {
            "team": team,
            "role": "batter",
            "window_name": "30d",
            "split": split,
            "game_date": game_date,
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


def _get_pre_game_team_plate_discipline(
    db: Any,
    team: str,
    game_date: date,
) -> dict[str, Any]:
    """30d pre-game team plate-discipline features."""
    rows = _query_all(
        db,
        _PRE_GAME_TEAM_ROLLING_SQL,
        {
            "team": team,
            "role": "batter",
            "window_name": "30d",
            "split": "ALL",
            "game_date": game_date,
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


def _get_pre_game_bullpen_appearances(
    db: Any,
    team: str,
    game_date: date,
    days_back: int = 5,
) -> list[RelieverAppearance]:
    """Query reliever appearances strictly before *game_date*."""
    start_date = game_date - timedelta(days=days_back)
    result = db.execute(
        _PRE_GAME_BULLPEN_SQL,
        {
            "team": team,
            "start_date": start_date.isoformat(),
            "game_date": game_date,
        },
    )
    appearances: list[RelieverAppearance] = []
    if result:
        for row_obj in result:
            row = dict(row_obj._mapping) if hasattr(row_obj, "_mapping") else dict(row_obj)
            raw_date = row.get("game_date")
            parsed_date: date | None = None
            if isinstance(raw_date, date):
                parsed_date = raw_date
            elif raw_date is not None:
                try:
                    parsed_date = date.fromisoformat(str(raw_date))
                except (ValueError, TypeError):
                    pass
            if parsed_date is None:
                continue
            appearances.append(
                RelieverAppearance(
                    pitcher_id=str(row.get("pitcher_id", "")),
                    appearance_date=parsed_date,
                    pitch_count=int(row.get("pitch_count", 0) or 0),
                    avg_velocity=(
                        float(row["avg_velocity"])
                        if row.get("avg_velocity") is not None
                        else None
                    ),
                )
            )
    return appearances


def _get_pre_game_recency(
    db: Any,
    home_team: str,
    away_team: str,
    game_date: date,
) -> dict[str, Any]:
    """Compute recency features using pre-game rolling data."""

    def _team_recency(team: str) -> tuple[float, int, int]:
        rows = _query_all(
            db,
            _PRE_GAME_TEAM_ROLLING_SQL,
            {
                "team": team,
                "role": "batter",
                "window_name": "30d",
                "split": "ALL",
                "game_date": game_date,
            },
        )
        total_rw = sum(float(r.get("recency_weight", 0) or 0) for r in rows)
        total_pa = sum(int(r.get("plate_appearances", 0) or 0) for r in rows)
        return total_rw, total_pa, len(rows)

    home_rw, home_pa, home_n = _team_recency(home_team)
    away_rw, away_pa, away_n = _team_recency(away_team)

    combined_pa = max(1, home_pa + away_pa)
    total_batters = home_n + away_n
    per_batter_rw = (home_rw + away_rw) / max(1, total_batters)
    recency_weight = round(min(1.0, per_batter_rw / 15.0), 4)

    return {
        "window_days": 30,
        "plate_appearance_window": combined_pa,
        "recency_weight": recency_weight,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _reconstruct_pre_game_features(
    db: Any,
    game: dict[str, Any],
    game_date: date,
) -> dict[str, float] | None:
    """Historical mirror of :func:`assemble_matchup_features`.

    Reads from the same tables but **only** rows where ``game_date < target_date``
    to prevent any look-ahead bias.  Returns ``None`` when a starting pitcher
    cannot be determined for either team.

    The returned flat dict uses dotted-namespace keys that match the runtime
    ``_flatten_feature_mapping`` output (e.g. ``sabermetrics.home_woba``,
    ``plate_discipline.home_o_swing_pct``).
    """
    game_id = str(game["game_id"])
    home_team = str(game["home_team"])
    away_team = str(game["away_team"])

    # ---- 1. Sabermetrics ---------------------------------------------------

    # Query actual starters for this completed game, then enrich with
    # pre-game rolling features.
    home_starter_row = _get_actual_starter(db, game_id, home_team)
    away_starter_row = _get_actual_starter(db, game_id, away_team)

    if home_starter_row is None or away_starter_row is None:
        return None

    home_pitcher_id = str(home_starter_row.get("pitcher_id", ""))
    away_pitcher_id = str(away_starter_row.get("pitcher_id", ""))

    home_rf = _get_pre_game_starter_rolling(db, home_pitcher_id, game_date)
    away_rf = _get_pre_game_starter_rolling(db, away_pitcher_id, game_date)

    home_starter = dict(home_starter_row)
    away_starter = dict(away_starter_row)
    if home_rf:
        home_starter.update(home_rf)
    if away_rf:
        away_starter.update(away_rf)

    home_batting = _get_pre_game_team_batting_features(db, home_team, game_date)
    away_batting = _get_pre_game_team_batting_features(db, away_team, game_date)

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
        "home_starter_k_bb_pct": _zero_if_none(
            (home_starter or {}).get("k_bb_pct")
        ),
        "away_starter_k_bb_pct": _zero_if_none(
            (away_starter or {}).get("k_bb_pct")
        ),
    }

    # ---- 2. Plate Discipline -----------------------------------------------

    home_pd = _get_pre_game_team_plate_discipline(db, home_team, game_date)
    away_pd = _get_pre_game_team_plate_discipline(db, away_team, game_date)

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

    home_apps = _get_pre_game_bullpen_appearances(db, home_team, game_date)
    away_apps = _get_pre_game_bullpen_appearances(db, away_team, game_date)
    home_bullpen = calculate_bullpen_fatigue(home_apps, game_date)
    away_bullpen = calculate_bullpen_fatigue(away_apps, game_date)

    # ---- 5. Recency --------------------------------------------------------

    recency = _get_pre_game_recency(db, home_team, away_team, game_date)

    # ---- 6. Flatten to match runtime _flatten_feature_mapping ---------------

    features: dict[str, float] = {}
    for prefix, subdict in (
        ("sabermetrics", sabermetrics),
        ("plate_discipline", plate_discipline),
        ("matchup_dynamics", matchup_dynamics),
        ("recency", recency),
    ):
        for sub_key, value in subdict.items():
            features[f"{prefix}.{sub_key}"] = (
                float(value) if value is not None else 0.0
            )

    for key, value in home_bullpen.to_payload("home").items():
        features[f"bullpen_fatigue.{key}"] = (
            float(value) if value is not None else 0.0
        )
    for key, value in away_bullpen.to_payload("away").items():
        features[f"bullpen_fatigue.{key}"] = (
            float(value) if value is not None else 0.0
        )

    return features


def build_training_rows(
    db: Any,
    *,
    start_date: date,
    end_date: date,
    min_games: int = 15,
) -> list[MoneylineTrainingRow]:
    """Build leakage-safe training rows.

    For each completed game in the date range, reconstructs the feature vector
    as it would have appeared **before** the game, using only data available up
    to ``game_date`` (strict ``<`` in SQL WHERE clauses).

    Games are skipped when:
    - A starting pitcher cannot be identified for either team.
    - Either team has fewer than *min_games* prior completed games in the
      database.

    Returns a list sorted by ``game_date`` in ascending order.
    """
    # Query completed games
    games_result = db.execute(
        _COMPLETED_GAMES_SQL,
        {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )
    if not games_result:
        return []

    games: list[dict[str, Any]] = []
    for row_obj in games_result:
        row = _to_dict(row_obj)
        raw_date = row.get("game_date")
        if isinstance(raw_date, date):
            parsed_date = raw_date
        elif raw_date is not None:
            try:
                parsed_date = date.fromisoformat(str(raw_date))
            except (ValueError, TypeError):
                continue
        else:
            continue
        games.append({**row, "game_date": parsed_date})

    # Reconstruct pre-game features for each game
    rows: list[MoneylineTrainingRow] = []
    for game in games:
        game_date = game["game_date"]
        home_team = str(game["home_team"])
        away_team = str(game["away_team"])
        home_score = int(game.get("home_score", 0) or 0)
        away_score = int(game.get("away_score", 0) or 0)
        label_home_win = 1 if home_score > away_score else 0

        # Enforce min_games threshold: both teams must have enough prior games.
        home_games = _get_team_prior_game_count(db, home_team, game_date)
        away_games = _get_team_prior_game_count(db, away_team, game_date)
        if home_games < min_games or away_games < min_games:
            continue

        features = _reconstruct_pre_game_features(db, game, game_date)
        if features is None:
            continue

        rows.append(
            MoneylineTrainingRow(
                game_date=game_date,
                features=features,
                label_home_win=label_home_win,
            )
        )

    return sorted(rows, key=lambda r: r.game_date)


def train_and_evaluate_model(
    db: Any,
    *,
    train_start: date,
    train_end: date,
    model_version: str,
    baseline_path: Path = DEFAULT_MONEYLINE_MODEL_PATH,
) -> MoneylineModelArtifact:
    """Build training data, train, evaluate against baseline, return artifact.

    Training data spans completed games from *train_start* to *train_end*
    inclusive.  Before training, the baseline artifact at *baseline_path* is
    loaded (when available) so that the newly trained model goes through the
    standard gate comparison (log-loss, Brier score, ECE).

    Raises ``ValueError`` when no training rows are produced for the date
    range (e.g. no completed games or insufficient history).
    """
    rows = build_training_rows(
        db,
        start_date=train_start,
        end_date=train_end,
    )

    if not rows:
        raise ValueError(
            f"No training rows found for {train_start} to {train_end}"
        )

    # Load baseline metrics for gate comparison (best-effort).
    try:
        baseline = load_moneyline_model_artifact(baseline_path)
        baseline_metrics = baseline.metrics
    except (FileNotFoundError, ValueError):
        baseline_metrics = None

    artifact = train_logistic_moneyline_model(
        rows,
        model_version=model_version,
        baseline_metrics=baseline_metrics,
    )

    logger.info(
        "Trained %s on %d rows: "
        "accuracy=%.4f, brier=%.4f, log_loss=%.4f, ece=%.4f, enabled=%s",
        model_version,
        len(rows),
        artifact.metrics.accuracy,
        artifact.metrics.brier_score,
        artifact.metrics.log_loss,
        artifact.metrics.expected_calibration_error,
        artifact.enabled,
    )

    return artifact
