"""Airflow-callable helpers for MLB predictive modeling."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import pandas as pd

from plugins.mlb_modeling.features import stable_feature_hash
from plugins.mlb_modeling.models import (
    CalibratedMoneylineModel,
    DEFAULT_MONEYLINE_MODEL_PATH,
    load_moneyline_model_artifact,
    save_moneyline_model_artifact,
    validate_runtime_feature_inputs,
)


MODEL_ARTIFACT_UNAVAILABLE_REASON = "enabled_calibrated_moneyline_artifact_unavailable"
MODEL_FEATURES_UNAVAILABLE_REASON = "required_runtime_moneyline_features_unavailable"
MODEL_SCORING_FAILED_REASON = "moneyline_model_scoring_failed"
PUBLIC_MONEYLINE_MODEL_VERSION = "mlb_moneyline_public_abstain_v1"


def _coerce_run_date(run_date: str | date) -> date:
    """Return ``run_date`` as a date."""
    if isinstance(run_date, date):
        return run_date
    return datetime.strptime(run_date, "%Y-%m-%d").date()


def _load_upcoming_games(db: Any, run_date: date, horizon_days: int) -> pd.DataFrame:
    """Load upcoming MLB games for the model scoring horizon."""
    end_date = run_date + timedelta(days=max(0, int(horizon_days)))
    return db.fetch_df(
        """
        SELECT
            game_id::TEXT AS game_id,
            home_team,
            away_team
        FROM mlb_games
        WHERE game_date BETWEEN CAST(:run_date AS DATE) AND CAST(:end_date AS DATE)
          AND home_team IS NOT NULL
          AND away_team IS NOT NULL
          AND (status IS NULL OR status NOT IN ('Final', 'Game Over', 'Completed Early'))
        ORDER BY game_date, game_id
        """,
        {"run_date": run_date.isoformat(), "end_date": end_date.isoformat()},
    )


def _run_date_window(run_date: date) -> tuple[datetime, datetime]:
    """Return the inclusive/exclusive datetime window for a governed run date."""
    start = datetime.combine(run_date, time.min)
    return start, start + timedelta(days=1)


def _load_latest_matchup_features(db: Any, game_id: str, run_date: date) -> pd.DataFrame:
    """Load the latest same-day governed matchup-feature row for a game."""
    run_start, run_end = _run_date_window(run_date)
    features = db.fetch_df(
        """
        SELECT
            feature_hash,
            feature_vector,
            feature_availability,
            abstention_reasons,
            as_of_ts
        FROM mlb_matchup_features
        WHERE game_id = :game_id
          AND side = 'home'
          AND as_of_ts >= :run_start
          AND as_of_ts < :run_end
        ORDER BY as_of_ts DESC
        LIMIT 1
        """,
        {
            "game_id": game_id,
            "run_start": run_start.isoformat(sep=" "),
            "run_end": run_end.isoformat(sep=" "),
        },
    )
    if features is None or features.empty:
        return pd.DataFrame()
    filtered = features.copy()
    if "game_id" in filtered.columns:
        filtered = filtered.loc[filtered["game_id"].astype(str) == str(game_id)]
    if "side" in filtered.columns:
        filtered = filtered.loc[filtered["side"].astype(str) == "home"]
    if "as_of_ts" not in filtered.columns:
        return pd.DataFrame()
    as_of_ts = pd.to_datetime(filtered["as_of_ts"], errors="coerce")
    filtered = filtered.loc[
        as_of_ts.notna() & (as_of_ts >= run_start) & (as_of_ts < run_end)
    ].copy()
    if filtered.empty:
        return filtered
    filtered = filtered.assign(as_of_ts=as_of_ts.loc[filtered.index].to_numpy())
    return filtered.sort_values("as_of_ts", ascending=False).head(1)


def _load_latest_market_probabilities(db: Any, game_id: str) -> Dict[str, float]:
    """Return latest implied probabilities for home/away sides when available."""
    odds = db.fetch_df(
        """
        SELECT DISTINCT ON (outcome_name)
            outcome_name,
            price
        FROM game_odds
        WHERE game_id = :game_id
          AND outcome_name IN ('home', 'away')
          AND price IS NOT NULL
          AND price > 1.0
        ORDER BY outcome_name, last_update DESC
        """,
        {"game_id": game_id},
    )
    if odds is None or odds.empty:
        return {}
    market_probabilities: Dict[str, float] = {}
    for _, row in odds.iterrows():
        market_probabilities[str(row["outcome_name"])] = 1.0 / float(row["price"])
    return market_probabilities


def _normalize_feature_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        if isinstance(loaded, Mapping):
            return loaded
    raise ValueError("Expected a mapping-shaped feature payload")


def _normalize_abstention_reasons(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
            if isinstance(loaded, list):
                return [str(reason) for reason in loaded]
        except json.JSONDecodeError:
            return [value]
    if isinstance(value, list):
        return [str(reason) for reason in value]
    return [str(value)]


def _build_live_moneyline_payloads(
    *,
    game_id: str,
    run_date: date,
    model: CalibratedMoneylineModel,
    features: Mapping[str, float],
    feature_hash: str,
    market_probabilities: Mapping[str, float],
) -> list[Dict[str, Any]]:
    home_payload = model.prediction_payload(
        game_id=game_id,
        outcome_name="home",
        run_date=run_date,
        features=features,
        feature_hash=feature_hash,
        market_prob=market_probabilities.get("home"),
    )
    away_payload = dict(home_payload)
    away_payload["prediction_id"] = (
        f"{model.artifact.model_version}_{game_id}_away_{run_date.isoformat()}"
    )
    away_payload["outcome_name"] = "away"
    away_payload["model_prob"] = 1.0 - float(home_payload["model_prob"])
    away_market_prob = market_probabilities.get("away")
    away_payload["market_prob"] = away_market_prob
    away_payload["edge"] = (
        away_payload["model_prob"] - away_market_prob
        if away_market_prob is not None
        else None
    )
    away_payload["expected_value"] = (
        away_payload["edge"] / away_market_prob
        if away_payload["edge"] is not None and away_market_prob
        else None
    )
    away_payload["abstain"] = False
    away_payload["abstention_reason"] = None
    return [home_payload, away_payload]


def build_abstaining_moneyline_payloads(
    *,
    game_id: str,
    home_team: str,
    away_team: str,
    run_date: date,
    model_version: str = PUBLIC_MONEYLINE_MODEL_VERSION,
    abstention_reason: str = MODEL_ARTIFACT_UNAVAILABLE_REASON,
) -> List[Dict[str, Any]]:
    """Build explicit abstaining home/away moneyline prediction payloads.

    The public-source-first pipeline must not fabricate confidence before an
    enabled calibrated artifact and complete feature set exist. These rows feed
    model-health monitoring while keeping betting decisions unchanged.
    """
    base_hash = stable_feature_hash(
        {
            "game_id": str(game_id),
            "home_team": home_team,
            "away_team": away_team,
            "run_date": run_date.isoformat(),
            "model_version": model_version,
            "abstention_reason": abstention_reason,
        }
    )
    payloads: List[Dict[str, Any]] = []
    for outcome_name in ("home", "away"):
        payloads.append(
            {
                "schema_version": "v1",
                "sport": "MLB",
                "payload_kind": "model_prediction",
                "prediction_id": (
                    f"{model_version}_{game_id}_{outcome_name}_{run_date.isoformat()}"
                ),
                "model_version": model_version,
                "game_id": str(game_id),
                "market_name": "moneyline",
                "outcome_name": outcome_name,
                "run_date": run_date.isoformat(),
                "model_prob": 0.5,
                "market_prob": None,
                "edge": None,
                "expected_value": None,
                "calibration_method": None,
                "ece_at_train": None,
                "feature_hash": stable_feature_hash(
                    {"base_hash": base_hash, "outcome_name": outcome_name}
                ),
                "simulation_summary": None,
                "abstain": True,
                "abstention_reason": abstention_reason,
            }
        )
    return payloads


def _upsert_model_prediction(db: Any, payload: Mapping[str, Any]) -> None:
    """Persist a contract-shaped MLB model prediction."""
    db.execute(
        """
        INSERT INTO mlb_model_predictions
            (prediction_id, model_version, game_id, market_name, outcome_name,
             run_date, model_prob, market_prob, edge, expected_value,
             calibration_method, ece_at_train, feature_hash, simulation_summary,
             abstain, abstention_reason)
        VALUES
            (:prediction_id, :model_version, :game_id, :market_name, :outcome_name,
             CAST(:run_date AS DATE), :model_prob, :market_prob, :edge,
             :expected_value, :calibration_method, :ece_at_train, :feature_hash,
             CAST(:simulation_summary AS JSONB), :abstain, :abstention_reason)
        ON CONFLICT (prediction_id) DO UPDATE SET
            model_prob = EXCLUDED.model_prob,
            market_prob = EXCLUDED.market_prob,
            edge = EXCLUDED.edge,
            expected_value = EXCLUDED.expected_value,
            calibration_method = EXCLUDED.calibration_method,
            ece_at_train = EXCLUDED.ece_at_train,
            feature_hash = EXCLUDED.feature_hash,
            simulation_summary = EXCLUDED.simulation_summary,
            abstain = EXCLUDED.abstain,
            abstention_reason = EXCLUDED.abstention_reason,
            created_at = CURRENT_TIMESTAMP
        """,
        {
            **dict(payload),
            "simulation_summary": (
                json.dumps(payload["simulation_summary"], sort_keys=True)
                if payload["simulation_summary"] is not None
                else None
            ),
        },
    )


def score_mlb_moneyline_model(
    *,
    run_date: str | date,
    db: Optional[Any] = None,
    horizon_days: int = 2,
    model_path: Path = DEFAULT_MONEYLINE_MODEL_PATH,
) -> Dict[str, int]:
    """Score MLB moneyline model rows for Airflow.

    Writes governed prediction rows when an enabled artifact and complete feature
    vector are available, and explicit abstentions otherwise.
    """
    if db is None:
        from plugins.db_manager import default_db

        db = default_db

    parsed_run_date = _coerce_run_date(run_date)
    games = _load_upcoming_games(db, parsed_run_date, horizon_days=horizon_days)
    if games.empty:
        return {
            "games_scored": 0,
            "predictions_written": 0,
            "abstentions_written": 0,
        }

    try:
        artifact = load_moneyline_model_artifact(model_path)
        if not artifact.enabled:
            raise ValueError(f"Moneyline artifact {artifact.model_version} is disabled")
        model = CalibratedMoneylineModel(artifact)
        default_model_version = model.artifact.model_version
        artifact_error: Optional[Exception] = None
    except Exception as exc:  # noqa: BLE001 - fail closed to explicit abstentions
        model = None
        default_model_version = PUBLIC_MONEYLINE_MODEL_VERSION
        artifact_error = exc

    predictions_written = 0
    abstentions_written = 0
    for _, game in games.iterrows():
        game_id = str(game["game_id"])
        home_team = str(game["home_team"])
        away_team = str(game["away_team"])
        payloads: list[Dict[str, Any]]
        if model is None:
            if artifact_error is not None:
                print(f"⚠️ MLB moneyline artifact unavailable for {game_id}: {artifact_error}")
            payloads = build_abstaining_moneyline_payloads(
                game_id=game_id,
                home_team=home_team,
                away_team=away_team,
                run_date=parsed_run_date,
                model_version=default_model_version,
                abstention_reason=MODEL_ARTIFACT_UNAVAILABLE_REASON,
            )
        else:
            try:
                feature_rows = _load_latest_matchup_features(db, game_id, parsed_run_date)
                if feature_rows is None or feature_rows.empty:
                    raise ValueError("missing matchup feature row")
                feature_row = feature_rows.iloc[0]
                features = validate_runtime_feature_inputs(
                    feature_vector=_normalize_feature_mapping(feature_row["feature_vector"]),
                    feature_availability=_normalize_feature_mapping(
                        feature_row["feature_availability"]
                    ),
                    abstention_reasons=_normalize_abstention_reasons(
                        feature_row.get("abstention_reasons")
                    ),
                    expected_feature_names=model.artifact.feature_names,
                )
                market_probabilities = _load_latest_market_probabilities(db, game_id)
                payloads = _build_live_moneyline_payloads(
                    game_id=game_id,
                    run_date=parsed_run_date,
                    model=model,
                    features=features,
                    feature_hash=str(feature_row["feature_hash"]),
                    market_probabilities=market_probabilities,
                )
            except Exception as exc:  # noqa: BLE001 - explicit abstentions are required
                print(f"⚠️ MLB moneyline scoring abstained for {game_id}: {exc}")
                reason = (
                    MODEL_FEATURES_UNAVAILABLE_REASON
                    if isinstance(exc, ValueError)
                    else MODEL_SCORING_FAILED_REASON
                )
                payloads = build_abstaining_moneyline_payloads(
                    game_id=game_id,
                    home_team=home_team,
                    away_team=away_team,
                    run_date=parsed_run_date,
                    model_version=model.artifact.model_version,
                    abstention_reason=reason,
                )
        for payload in payloads:
            _upsert_model_prediction(db, payload)
            predictions_written += 1
            if payload["abstain"]:
                abstentions_written += 1

    return {
        "games_scored": int(len(games)),
        "predictions_written": predictions_written,
        "abstentions_written": abstentions_written,
    }


# ---------------------------------------------------------------------------
# Upstream data-ingestion callables
# ---------------------------------------------------------------------------


def fetch_mlb_player_stats(
    *,
    run_date: str | date,
    db: Optional[Any] = None,
) -> Dict[str, int]:
    """Fetch per-player batting, pitching, and pitch-level data for completed games.

    Queries completed ``mlb_games`` for *run_date*, then calls the MLB Stats
    API for each game's boxscore and live-feed data.  Batting, pitching, and
    pitch-feature rows are upserted into the V010 tables.

    Args:
        run_date: Execution date (ISO string or ``date``).
        db: Database manager.  Falls back to ``default_db`` when ``None``.

    Returns:
        Dict with keys ``games_fetched``, ``batting_rows``, ``pitching_rows``.
    """
    if db is None:
        from plugins.db_manager import default_db

        db = default_db

    parsed = _coerce_run_date(run_date)

    # Find completed games for this date.
    games = db.fetch_df(
        """
        SELECT game_id::TEXT AS game_id, game_date, home_team, away_team
        FROM mlb_games
        WHERE game_date = CAST(:run_date AS DATE)
          AND status IN ('Final', 'Game Over', 'Completed Early')
        """,
        {"run_date": parsed.isoformat()},
    )

    if games is None or games.empty:
        return {"games_fetched": 0, "batting_rows": 0, "pitching_rows": 0}

    from plugins.mlb_modeling.player_stats_fetcher import MLBPlayerStatsFetcher

    fetcher = MLBPlayerStatsFetcher(db=db)
    total_batting = 0
    total_pitching = 0

    for _, game in games.iterrows():
        game_id = str(game["game_id"])
        try:
            result = fetcher.fetch_game_stats(game_id)
            fetcher.upsert_all(result)
            total_batting += len(result.batting_rows)
            total_pitching += len(result.pitching_rows)
        except Exception as exc:  # noqa: BLE001 - best-effort per game
            print(f"⚠️  MLB player stats fetch failed for game {game_id}: {exc}")

    return {
        "games_fetched": int(len(games)),
        "batting_rows": total_batting,
        "pitching_rows": total_pitching,
    }


def compute_mlb_rolling_features(
    *,
    run_date: str | date,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """Compute rolling features for all active MLB players.

    Discovers player IDs from the batting and pitching stats tables and
    computes 7d, 14d, and 30d rolling-window features for each.

    Args:
        run_date: Reference date (ISO string or ``date``).  Only games strictly
            before this date are included in the rolling computation.
        db: Database manager.  Falls back to ``default_db`` when ``None``.

    Returns:
        Dict with ``rows_upserted`` and ``as_of_date``.
    """
    if db is None:
        from plugins.db_manager import default_db

        db = default_db

    from plugins.mlb_modeling.rolling_features import compute_all_rolling_features

    parsed = _coerce_run_date(run_date)
    rows_upserted = compute_all_rolling_features(db, parsed)
    return {
        "rows_upserted": rows_upserted,
        "as_of_date": parsed.isoformat(),
    }


def assemble_mlb_matchup_features(
    *,
    run_date: str | date,
    horizon_days: int = 2,
    db: Optional[Any] = None,
) -> Dict[str, int]:
    """Assemble matchup feature vectors for upcoming MLB games.

    Loads games that are not yet final within the scoring horizon and calls
    :func:`~plugins.mlb_modeling.matchup_assembler.assemble_matchup_features`
    for each, persisting the result to ``mlb_matchup_features``.

    Args:
        run_date: Execution date.
        horizon_days: How many days ahead to look for upcoming games.
        db: Database manager.  Falls back to ``default_db`` when ``None``.

    Returns:
        Dict with ``games_assembled``.
    """
    if db is None:
        from plugins.db_manager import default_db

        db = default_db

    from plugins.mlb_modeling.matchup_assembler import assemble_matchup_features as _assemble

    parsed = _coerce_run_date(run_date)
    games = _load_upcoming_games(db, parsed, horizon_days=horizon_days)

    if games.empty:
        return {"games_assembled": 0}

    count = 0
    for _, game in games.iterrows():
        try:
            result = _assemble(
                db,
                game_id=str(game["game_id"]),
                home_team=str(game["home_team"]),
                away_team=str(game["away_team"]),
                game_date=parsed,
            )
            if result is not None:
                count += 1
        except Exception as exc:  # noqa: BLE001 - best-effort per game
            print(f"⚠️  Matchup assembly failed for game {game['game_id']}: {exc}")

    return {"games_assembled": count}


def train_mlb_model_periodic(
    *,
    run_date: Optional[str | date] = None,
    db: Optional[Any] = None,
    model_path: Path = DEFAULT_MONEYLINE_MODEL_PATH,
) -> Dict[str, Any]:
    """Periodic MLB moneyline model training (intended for weekly schedule).

    Trains on completed games from the last 365 days, evaluates against the
    current production artifact (if it exists), and persists the new artifact
    when gate checks pass.

    Args:
        run_date: Optional execution date.  When ``None``, uses ``date.today()``.
        db: Database manager.  Falls back to ``default_db`` when ``None``.
        model_path: Path to persist the trained artifact.

    Returns:
        Dict with training summary (model version, row count, metrics, enabled).
    """
    if db is None:
        from plugins.db_manager import default_db

        db = default_db

    from plugins.mlb_modeling.training import train_and_evaluate_model

    if run_date is None:
        run_date = date.today()
    parsed = _coerce_run_date(run_date)

    # Train on the year leading up to (but not including) today.
    train_end = parsed - timedelta(days=1)
    train_start = train_end - timedelta(days=365)

    model_version = f"mlb_moneyline_v{parsed.strftime('%Y%m%d')}"

    artifact = train_and_evaluate_model(
        db,
        train_start=train_start,
        train_end=train_end,
        model_version=model_version,
        baseline_path=model_path,
    )

    save_moneyline_model_artifact(artifact, model_path=model_path)

    return {
        "model_version": model_version,
        "training_rows": artifact.metrics.sample_count,
        "accuracy": artifact.metrics.accuracy,
        "brier_score": artifact.metrics.brier_score,
        "log_loss": artifact.metrics.log_loss,
        "ece": artifact.metrics.expected_calibration_error,
        "enabled": artifact.enabled,
    }


def fetch_mlb_environment_features(
    *,
    run_date: str | date,
    horizon_days: int = 2,
    db: Optional[Any] = None,
) -> Dict[str, int]:
    """Fetch environment features (park factors, weather) for upcoming MLB games.

    Loads upcoming games and calls
    :func:`~plugins.mlb_modeling.environment_fetcher.fetch_environment_features`
    for each, persisting to ``mlb_environment_features``.

    Args:
        run_date: Execution date.
        horizon_days: How many days ahead to look for upcoming games.
        db: Database manager.  Falls back to ``default_db`` when ``None``.

    Returns:
        Dict with ``features_stored``.
    """
    if db is None:
        from plugins.db_manager import default_db

        db = default_db

    from plugins.mlb_modeling.environment_fetcher import (
        fetch_environment_features as _fetch_environment,
    )
    from plugins.mlb_modeling.travel_fetcher import TEAM_INFO

    parsed = _coerce_run_date(run_date)
    games = _load_upcoming_games(db, parsed, horizon_days=horizon_days)

    if games.empty:
        return {"features_stored": 0}

    count = 0
    for _, game in games.iterrows():
        game_id = str(game["game_id"])
        home_team = str(game["home_team"])
        try:
            venue = TEAM_INFO[home_team]["venue"]
            _fetch_environment(db, game_id, parsed, venue)
            count += 1
        except KeyError:
            print(f"⚠️  Unknown venue for team {home_team}; skipping environment")
        except Exception as exc:  # noqa: BLE001 - best-effort per game
            print(f"⚠️  Environment fetch failed for game {game_id}: {exc}")

    return {"features_stored": count}


def fetch_mlb_travel_features(
    *,
    run_date: str | date,
    horizon_days: int = 2,
    db: Optional[Any] = None,
) -> Dict[str, int]:
    """Compute travel fatigue features for upcoming MLB games.

    Loads upcoming games and calls
    :func:`~plugins.mlb_modeling.travel_fetcher.fetch_travel_features`
    for each, persisting to ``mlb_travel_features``.

    Args:
        run_date: Execution date.
        horizon_days: How many days ahead to look for upcoming games.
        db: Database manager.  Falls back to ``default_db`` when ``None``.

    Returns:
        Dict with ``features_stored`` (2 rows per game — home and away).
    """
    if db is None:
        from plugins.db_manager import default_db

        db = default_db

    from plugins.mlb_modeling.travel_fetcher import (
        fetch_travel_features as _fetch_travel,
    )

    parsed = _coerce_run_date(run_date)
    games = _load_upcoming_games(db, parsed, horizon_days=horizon_days)

    if games.empty:
        return {"features_stored": 0}

    count = 0
    for _, game in games.iterrows():
        game_id = str(game["game_id"])
        home_team = str(game["home_team"])
        away_team = str(game["away_team"])
        try:
            _fetch_travel(db, game_id, home_team, away_team, parsed)
            count += 2  # home + away rows
        except Exception as exc:  # noqa: BLE001 - best-effort per game
            print(f"⚠️  Travel feature fetch failed for game {game_id}: {exc}")

    return {"features_stored": count}
