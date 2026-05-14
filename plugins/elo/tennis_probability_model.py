"""Lightweight tennis probability model with calibrated Elo fallback.

The production betting boundary can safely prefer this model when a valid
artifact exists, while retaining the existing ``TennisEloRating`` calibrated
probability if the artifact is absent, disabled, or cannot build features.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from plugins.elo.tennis_elo_rating import TennisEloRating
from plugins.elo.tennis_features import TennisFeatureBuilder, TennisMatchupFeatures

try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover - dependency is present in repo requirements
    XGBClassifier = None


MODEL_VERSION = "tennis_probability_model_v2"
DEFAULT_MODEL_PATH = Path("data/models/tennis_probability_model_v1.joblib")
DEFAULT_METRICS_PATH = Path("data/models/tennis_probability_model_v1_metrics.json")
MIN_HOLDOUT_ROWS = 20
ENSEMBLE_ELO_WEIGHT = 0.30
ENSEMBLE_FEATURE_WEIGHT = 0.70

FEATURE_COLUMNS = [
    "calibrated_elo_prob_a",
    "weighted_match_count_diff",
    "win_rate_diff",
    "common_opponent_count",
    "common_opponent_win_rate_diff",
    "direct_win_rate_a",
    "intransitivity_complexity",
    "serveadv_diff",
    "complete_diff",
    "fatigue_diff",
    "retired_diff",
    "age_30_diff",
    "rank_diff",
    "data_certainty",
]


@dataclass(frozen=True)
class TennisModelMetrics:
    """Chronological holdout metrics for baseline Elo and ensemble models."""

    model_version: str
    data_source: str
    rows: int
    holdout_rows: int
    enabled: bool
    baseline_log_loss: float
    ensemble_log_loss: float
    log_loss_delta: float
    baseline_brier: float
    ensemble_brier: float
    brier_delta: float
    baseline_accuracy: float
    ensemble_accuracy: float
    accuracy_delta: float
    baseline_actionable_count: int
    ensemble_actionable_count: int
    actionable_count_delta: int
    betmgm_holdout_rows: int
    ensemble_market_log_loss: float | None
    betmgm_log_loss: float | None
    ensemble_vs_betmgm_log_loss_delta: float | None
    ensemble_market_brier: float | None
    betmgm_brier: float | None
    ensemble_vs_betmgm_brier_delta: float | None
    ensemble_market_accuracy: float | None
    betmgm_accuracy: float | None
    ensemble_vs_betmgm_accuracy_delta: float | None
    beats_betmgm: bool

    def to_payload(self) -> dict[str, Any]:
        """Return JSON-serializable metrics."""
        return asdict(self)


@dataclass(frozen=True)
class TennisProbabilityResult:
    """Prediction payload returned by the probability service."""

    prob_a: float
    source: str
    calibrated_elo_prob_a: float
    feature_model_prob_a: float | None
    model_version: str | None
    data_certainty: float | None

    def to_payload(self) -> dict[str, Any]:
        """Return JSON-serializable prediction details."""
        return asdict(self)


@dataclass(frozen=True)
class TennisTrainingRunResult:
    """Persisted production-training summary for Airflow and tests."""

    model_version: str
    data_source: str
    rows: int
    holdout_rows: int
    feature_frame_rows: int
    enabled: bool
    metrics_published: bool
    model_path: str
    metrics_path: str

    def to_payload(self) -> dict[str, Any]:
        """Return JSON-serializable training summary."""
        return asdict(self)


class TennisStackedEnsembleModel:
    """Stack tree-based tennis classifiers with a Kernel Ridge meta learner."""

    def __init__(self) -> None:
        """Initialize the preprocessing, base models, and meta learner."""
        self.imputer = SimpleImputer(strategy="median")
        self.scaler = StandardScaler()
        self.meta_model = KernelRidge(alpha=0.8, kernel="rbf", gamma=0.75)
        self.base_models: list[Any] = []
        self._fitted = False

    def fit(
        self, features: pd.DataFrame, target: pd.Series
    ) -> "TennisStackedEnsembleModel":
        """Fit the stacked ensemble on chronological tennis features."""
        feature_frame = pd.DataFrame(features, columns=FEATURE_COLUMNS)
        X = self.imputer.fit_transform(feature_frame)
        X = self.scaler.fit_transform(X)
        y = target.to_numpy(dtype=float)

        base_models = _build_base_models()
        stacked = np.zeros((len(feature_frame), len(base_models)), dtype=float)
        validation_mask = np.zeros(len(feature_frame), dtype=bool)
        splitter = TimeSeriesSplit(n_splits=min(4, max(2, len(feature_frame) // 30)))

        for train_idx, valid_idx in splitter.split(X):
            if len(train_idx) < MIN_HOLDOUT_ROWS:
                continue
            validation_mask[valid_idx] = True
            for column_idx, model in enumerate(_build_base_models()):
                model.fit(X[train_idx], y[train_idx])
                stacked[valid_idx, column_idx] = model.predict_proba(X[valid_idx])[:, 1]

        if not validation_mask.any():
            validation_mask[:] = True
            for column_idx, model in enumerate(base_models):
                model.fit(X, y)
                stacked[:, column_idx] = model.predict_proba(X)[:, 1]

        meta_X = np.column_stack(
            [
                stacked[validation_mask],
                feature_frame.loc[validation_mask, "calibrated_elo_prob_a"].to_numpy(
                    dtype=float
                ),
            ]
        )
        self.meta_model.fit(meta_X, y[validation_mask])

        self.base_models = []
        for model in base_models:
            model.fit(X, y)
            self.base_models.append(model)
        self._fitted = True
        return self

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        """Return binary probabilities for the fitted stacked ensemble."""
        if not self._fitted:
            raise ValueError(
                "TennisStackedEnsembleModel must be fit before predict_proba"
            )

        feature_frame = pd.DataFrame(features, columns=FEATURE_COLUMNS)
        X = self.imputer.transform(feature_frame)
        X = self.scaler.transform(X)
        stacked = np.column_stack(
            [model.predict_proba(X)[:, 1] for model in self.base_models]
        )
        meta_X = np.column_stack(
            [stacked, feature_frame["calibrated_elo_prob_a"].to_numpy(dtype=float)]
        )
        prob = np.clip(self.meta_model.predict(meta_X), 0.01, 0.99)
        return np.column_stack([1.0 - prob, prob])


def train_and_evaluate(
    history: pd.DataFrame,
    *,
    data_source: str,
    holdout_fraction: float = 0.20,
    max_matches: int | None = None,
) -> tuple[TennisStackedEnsembleModel, TennisModelMetrics, pd.DataFrame]:
    """Train and evaluate a tennis feature model on chronological data.

    Args:
        history: Historical tennis match rows.
        data_source: Human-readable source label included in metrics.
        holdout_fraction: Fraction of newest rows reserved for holdout.
        max_matches: Optional newest-match cap for keeping feature builds
            bounded on large local CSV exports.

    Returns:
        Fitted sklearn pipeline, metrics, and full feature frame.

    Raises:
        ValueError: If there are not enough feature rows to evaluate.
    """
    frame = build_training_frame(history, max_matches=max_matches)
    if len(frame) < MIN_HOLDOUT_ROWS * 2:
        raise ValueError(
            f"Need at least {MIN_HOLDOUT_ROWS * 2} tennis feature rows; got {len(frame)}"
        )

    split_idx = max(1, int(len(frame) * (1.0 - holdout_fraction)))
    split_idx = min(split_idx, len(frame) - MIN_HOLDOUT_ROWS)
    train = frame.iloc[:split_idx].copy()
    holdout = frame.iloc[split_idx:].copy()

    pipeline = _build_pipeline()
    pipeline.fit(train[FEATURE_COLUMNS], train["target"])

    feature_prob = pipeline.predict_proba(holdout[FEATURE_COLUMNS])[:, 1]
    baseline_prob = holdout["calibrated_elo_prob_a"].to_numpy(dtype=float)
    ensemble_prob = _blend_probabilities(baseline_prob, feature_prob)
    betmgm_prob = pd.to_numeric(holdout.get("betmgm_prob_a"), errors="coerce").to_numpy(
        dtype=float
    )
    y = holdout["target"].to_numpy(dtype=float)

    metrics = _build_metrics(
        data_source=data_source,
        total_rows=len(frame),
        holdout_rows=len(holdout),
        y=y,
        baseline_prob=baseline_prob,
        ensemble_prob=ensemble_prob,
        market_prob=betmgm_prob,
    )
    return pipeline, metrics, frame


def build_training_frame(
    history: pd.DataFrame, *, max_matches: int | None = None
) -> pd.DataFrame:
    """Build leakage-safe tennis training rows from historical matches."""
    normalized = _normalize_history(history)
    if normalized.empty:
        return pd.DataFrame()
    if max_matches is not None and max_matches > 0:
        normalized = normalized.tail(max_matches).reset_index(drop=True)

    builder = TennisFeatureBuilder()
    elo = TennisEloRating()
    prior_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []

    for _, match in normalized.iterrows():
        if prior_rows:
            prior_frame = pd.DataFrame(prior_rows)
            feature_rows.append(
                _build_oriented_row(
                    builder=builder,
                    elo=elo,
                    history=prior_frame,
                    player_a=str(match["winner"]),
                    player_b=str(match["loser"]),
                    target=1.0,
                    match=match,
                )
            )
            feature_rows.append(
                _build_oriented_row(
                    builder=builder,
                    elo=elo,
                    history=prior_frame,
                    player_a=str(match["loser"]),
                    player_b=str(match["winner"]),
                    target=0.0,
                    match=match,
                )
            )

        elo.update(str(match["winner"]), str(match["loser"]), tour=str(match["tour"]))
        prior_rows.append(match.to_dict())

    frame = pd.DataFrame(feature_rows)
    if frame.empty:
        return frame
    return frame.sort_values(["date", "player_a", "player_b"]).reset_index(drop=True)


def predict_with_artifact(
    *,
    player_a: str,
    player_b: str,
    tour: str,
    surface: str,
    as_of_date: str | pd.Timestamp,
    history: pd.DataFrame,
    calibrated_elo_prob_a: float,
    model_path: Path = DEFAULT_MODEL_PATH,
) -> TennisProbabilityResult:
    """Predict with a persisted feature model, falling back to calibrated Elo."""
    fallback = TennisProbabilityResult(
        prob_a=_clip_prob(calibrated_elo_prob_a),
        source="calibrated_elo_fallback",
        calibrated_elo_prob_a=_clip_prob(calibrated_elo_prob_a),
        feature_model_prob_a=None,
        model_version=None,
        data_certainty=None,
    )
    try:
        artifact = load_artifact(model_path)
        if not artifact.get("enabled", False):
            return fallback
        if history.empty:
            return fallback

        builder = TennisFeatureBuilder()
        features = builder.build_matchup_features(
            history=history,
            player_a=player_a,
            player_b=player_b,
            as_of_date=as_of_date,
            surface=surface,
            tour=tour,
        )
        row = _feature_dict_from_payload(
            features=features,
            calibrated_elo_prob_a=_clip_prob(calibrated_elo_prob_a),
            betmgm_prob_a=None,
            target=None,
            date=pd.Timestamp(as_of_date),
        )
        model: TennisStackedEnsembleModel = artifact["model"]
        feature_prob = float(
            model.predict_proba(pd.DataFrame([row])[FEATURE_COLUMNS])[0, 1]
        )
        prob = float(
            _blend_probabilities(
                np.array([calibrated_elo_prob_a], dtype=float),
                np.array([feature_prob], dtype=float),
            )[0]
        )
        return TennisProbabilityResult(
            prob_a=_clip_prob(prob),
            source="ensemble",
            calibrated_elo_prob_a=_clip_prob(calibrated_elo_prob_a),
            feature_model_prob_a=_clip_prob(feature_prob),
            model_version=str(artifact.get("model_version") or MODEL_VERSION),
            data_certainty=float(features.data_certainty),
        )
    except Exception:
        return fallback


def load_history_from_db() -> pd.DataFrame:
    """Load rich tennis match history from PostgreSQL for runtime predictions."""
    from plugins.db_manager import default_db

    return default_db.fetch_df(
        """
        WITH latest_market_odds AS (
            SELECT DISTINCT ON (go.game_id, go.outcome_name)
                go.game_id,
                ug.game_date,
                ug.home_team_name,
                ug.away_team_name,
                go.outcome_name,
                go.price
            FROM game_odds go
            JOIN unified_games ug ON ug.game_id = go.game_id
            WHERE LOWER(go.bookmaker) IN ('kalshi', 'betmgm')
              AND COALESCE(go.is_pregame, TRUE) = TRUE
              AND go.price IS NOT NULL
              AND go.price > 1.0
              AND UPPER(ug.sport) = 'TENNIS'
            ORDER BY go.game_id, go.outcome_name, go.last_update DESC NULLS LAST, go.odds_id ASC
        ),
        market_probs AS (
            SELECT
                lmo.game_date,
                lmo.home_team_name AS player_a,
                lmo.away_team_name AS player_b,
                MAX(
                    CASE
                        WHEN lmo.outcome_name IN ('home', lmo.home_team_name)
                        THEN 1.0 / lmo.price
                    END
                ) AS player_a_raw_prob,
                MAX(
                    CASE
                        WHEN lmo.outcome_name IN ('away', lmo.away_team_name)
                        THEN 1.0 / lmo.price
                    END
                ) AS player_b_raw_prob
            FROM latest_market_odds lmo
            GROUP BY lmo.game_date, lmo.home_team_name, lmo.away_team_name
        )
        SELECT
            tg.game_id,
            tg.game_date AS date,
            tg.tour,
            tg.surface,
            tg.winner,
            tg.loser,
            tg.score,
            CASE
                WHEN ws.first_serve_pct IS NULL
                  OR ws.first_serve_won_pct IS NULL
                  OR ws.second_serve_won_pct IS NULL
                THEN NULL
                ELSE (
                    ws.first_serve_pct * ws.first_serve_won_pct
                    + (1.0 - ws.first_serve_pct) * ws.second_serve_won_pct
                )
            END AS winner_serve_win_pct,
            CASE
                WHEN ls.first_serve_pct IS NULL
                  OR ls.first_serve_won_pct IS NULL
                  OR ls.second_serve_won_pct IS NULL
                THEN NULL
                ELSE (
                    ls.first_serve_pct * ls.first_serve_won_pct
                    + (1.0 - ls.first_serve_pct) * ls.second_serve_won_pct
                )
            END AS loser_serve_win_pct,
            CASE
                WHEN ls.first_serve_pct IS NULL
                  OR ls.first_serve_won_pct IS NULL
                  OR ls.second_serve_won_pct IS NULL
                THEN NULL
                ELSE 1.0 - (
                    ls.first_serve_pct * ls.first_serve_won_pct
                    + (1.0 - ls.first_serve_pct) * ls.second_serve_won_pct
                )
            END AS winner_return_win_pct,
            CASE
                WHEN ws.first_serve_pct IS NULL
                  OR ws.first_serve_won_pct IS NULL
                  OR ws.second_serve_won_pct IS NULL
                THEN NULL
                ELSE 1.0 - (
                    ws.first_serve_pct * ws.first_serve_won_pct
                    + (1.0 - ws.first_serve_pct) * ws.second_serve_won_pct
                )
            END AS loser_return_win_pct,
            CASE
                WHEN mp.player_a_raw_prob IS NULL
                  OR mp.player_b_raw_prob IS NULL
                  OR (mp.player_a_raw_prob + mp.player_b_raw_prob) <= 0
                THEN NULL
                WHEN tg.winner = mp.player_a AND tg.loser = mp.player_b
                THEN mp.player_a_raw_prob / (mp.player_a_raw_prob + mp.player_b_raw_prob)
                WHEN tg.winner = mp.player_b AND tg.loser = mp.player_a
                THEN mp.player_b_raw_prob / (mp.player_a_raw_prob + mp.player_b_raw_prob)
                ELSE NULL
            END AS winner_market_prob,
            CASE
                WHEN mp.player_a_raw_prob IS NULL
                  OR mp.player_b_raw_prob IS NULL
                  OR (mp.player_a_raw_prob + mp.player_b_raw_prob) <= 0
                THEN NULL
                WHEN tg.loser = mp.player_a AND tg.winner = mp.player_b
                THEN mp.player_a_raw_prob / (mp.player_a_raw_prob + mp.player_b_raw_prob)
                WHEN tg.loser = mp.player_b AND tg.winner = mp.player_a
                THEN mp.player_b_raw_prob / (mp.player_a_raw_prob + mp.player_b_raw_prob)
                ELSE NULL
            END AS loser_market_prob
        FROM tennis_games tg
        LEFT JOIN tennis_player_match_stats ws
            ON ws.game_id = tg.game_id
           AND ws.player_name = tg.winner
        LEFT JOIN tennis_player_match_stats ls
            ON ls.game_id = tg.game_id
           AND ls.player_name = tg.loser
        LEFT JOIN market_probs mp
            ON mp.game_date = tg.game_date
            AND ((tg.winner = mp.player_a AND tg.loser = mp.player_b)
                 OR (tg.winner = mp.player_b AND tg.loser = mp.player_a))
        WHERE tg.game_date IS NOT NULL
          AND tg.winner IS NOT NULL
          AND tg.loser IS NOT NULL
        ORDER BY tg.game_date ASC
        """
    )


def load_history_from_csv_dir(csv_dir: Path = Path("data/tennis")) -> pd.DataFrame:
    """Load tennis history from local CSVs without downloading external data."""
    frames: list[pd.DataFrame] = []
    if not csv_dir.exists():
        return pd.DataFrame()
    for path in sorted(csv_dir.glob("*_*.csv")):
        parts = path.stem.split("_")
        if len(parts) < 2:
            continue
        tour = parts[0].upper()
        try:
            frame = pd.read_csv(path, encoding="latin1")
        except UnicodeDecodeError:
            frame = pd.read_csv(path)
        if frame.empty:
            continue
        frame["tour"] = tour
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_benchmark_history(match_count: int = 220) -> pd.DataFrame:
    """Build deterministic tennis benchmark data for offline validation.

    This fixture is used only when live PostgreSQL/local CSV history is
    unavailable. It gives the evaluation command stable numbers while clearly
    labeling the metrics as ``benchmark_fixture`` rather than production data.
    """
    players = {
        "Alpha A.": {"skill": 1.25, "serve": 0.66, "rank": 5, "age": 27.0},
        "Bravo B.": {"skill": 0.85, "serve": 0.62, "rank": 18, "age": 29.0},
        "Clay C.": {"skill": 0.35, "serve": 0.58, "rank": 42, "age": 31.0},
        "Delta D.": {"skill": -0.05, "serve": 0.55, "rank": 70, "age": 24.0},
        "Echo E.": {"skill": -0.45, "serve": 0.53, "rank": 95, "age": 33.0},
        "Foxtrot F.": {"skill": -0.85, "serve": 0.50, "rank": 130, "age": 22.0},
    }
    surfaces = ["Hard", "Grass", "Clay"]
    names = list(players)
    rows: list[dict[str, Any]] = []
    start = pd.Timestamp("2025-01-01")
    for idx in range(match_count):
        player_a = names[idx % len(names)]
        player_b = names[(idx * 2 + 3) % len(names)]
        if player_a == player_b:
            player_b = names[(idx + 1) % len(names)]
        surface = surfaces[idx % len(surfaces)]
        skill_a = float(players[player_a]["skill"])
        skill_b = float(players[player_b]["skill"])
        surface_bonus_a = (
            0.18 if surface == "Grass" and player_a in {"Alpha A.", "Bravo B."} else 0.0
        )
        surface_bonus_b = (
            0.18 if surface == "Grass" and player_b in {"Alpha A.", "Bravo B."} else 0.0
        )
        score_signal = skill_a - skill_b + surface_bonus_a - surface_bonus_b
        true_prob_a = float(1.0 / (1.0 + np.exp(-1.35 * score_signal)))
        market_prob_a = float(
            np.clip(
                0.5 + 0.80 * (true_prob_a - 0.5) + 0.025 * np.sin(idx / 9.0), 0.05, 0.95
            )
        )
        upset_cycle = (idx % 17) == 0
        a_wins = score_signal >= 0
        if upset_cycle:
            a_wins = not a_wins
        winner, loser = (player_a, player_b) if a_wins else (player_b, player_a)
        winner_market_prob = market_prob_a if a_wins else 1.0 - market_prob_a
        loser_market_prob = 1.0 - winner_market_prob
        w = players[winner]
        l = players[loser]
        w_svpt = 78 + (idx % 11)
        l_svpt = 76 + (idx % 9)
        rows.append(
            {
                "date": start + pd.Timedelta(days=idx),
                "tour": "ATP",
                "surface": surface,
                "winner": winner,
                "loser": loser,
                "score": "6-4 6-4",
                "winner_rank": float(w["rank"]),
                "loser_rank": float(l["rank"]),
                "winner_age": float(w["age"]),
                "loser_age": float(l["age"]),
                "w_svpt": w_svpt,
                "w_1stWon": int(float(w["serve"]) * w_svpt * 0.75),
                "w_2ndWon": int(float(w["serve"]) * w_svpt * 0.25),
                "l_svpt": l_svpt,
                "l_1stWon": int(float(l["serve"]) * l_svpt * 0.70),
                "l_2ndWon": int(float(l["serve"]) * l_svpt * 0.20),
                "winner_market_prob": winner_market_prob,
                "loser_market_prob": loser_market_prob,
            }
        )
    return pd.DataFrame(rows)


def save_artifact(
    model: TennisStackedEnsembleModel,
    metrics: TennisModelMetrics,
    *,
    model_path: Path = DEFAULT_MODEL_PATH,
) -> None:
    """Persist model and metrics metadata."""
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model_version": MODEL_VERSION,
            "enabled": metrics.enabled,
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "metrics": metrics.to_payload(),
        },
        model_path,
    )


def persist_training_outputs(
    model: TennisStackedEnsembleModel,
    metrics: TennisModelMetrics,
    *,
    model_path: Path = DEFAULT_MODEL_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    publish_metrics: bool = False,
) -> bool:
    """Persist artifact + metrics JSON and optionally publish DB evidence."""
    save_artifact(model, metrics, model_path=model_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(metrics.to_payload(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return save_metrics_to_db(metrics) if publish_metrics else False


def load_artifact(model_path: Path = DEFAULT_MODEL_PATH) -> dict[str, Any]:
    """Load a persisted tennis probability model artifact."""
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    artifact = joblib.load(model_path)
    if artifact.get("feature_columns") != FEATURE_COLUMNS:
        raise ValueError("Tennis model artifact feature columns do not match runtime")
    return artifact


def train_production_model(
    *,
    history: pd.DataFrame | None = None,
    model_path: Path = DEFAULT_MODEL_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    max_matches: int | None = 1200,
    publish_metrics: bool = False,
) -> TennisTrainingRunResult:
    """Train and persist the production tennis probability artifact from PostgreSQL.

    Args:
        history: Optional preloaded history used for tests or offline callers.
            When omitted, the function loads history from PostgreSQL.
        model_path: Destination for the persisted model artifact.
        metrics_path: Destination for the JSON metrics payload.
        max_matches: Optional newest-match cap passed to ``train_and_evaluate``.
        publish_metrics: When ``True``, publish governed evaluation rows via the
            existing metrics gate. Production retraining defaults to ``False`` so
            artifact refresh is decoupled from BetMGM evidence rollout.

    Returns:
        Summary of the persisted training run.

    Raises:
        ValueError: If PostgreSQL history is unavailable for production training.
    """
    history_frame = load_history_from_db() if history is None else history.copy()
    if history_frame.empty:
        raise ValueError(
            "No PostgreSQL tennis history available for production training"
        )

    model, metrics, frame = train_and_evaluate(
        history_frame,
        data_source="postgres_tennis_games",
        max_matches=max_matches,
    )
    metrics_published = persist_training_outputs(
        model,
        metrics,
        model_path=model_path,
        metrics_path=metrics_path,
        publish_metrics=publish_metrics,
    )
    return TennisTrainingRunResult(
        model_version=metrics.model_version,
        data_source=metrics.data_source,
        rows=metrics.rows,
        holdout_rows=metrics.holdout_rows,
        feature_frame_rows=len(frame),
        enabled=metrics.enabled,
        metrics_published=metrics_published,
        model_path=str(model_path),
        metrics_path=str(metrics_path),
    )


def _build_oriented_row(
    *,
    builder: TennisFeatureBuilder,
    elo: TennisEloRating,
    history: pd.DataFrame,
    player_a: str,
    player_b: str,
    target: float,
    match: pd.Series,
) -> dict[str, Any]:
    """Build one oriented feature row for a historical match."""
    tour = str(match["tour"]).upper()
    surface = str(match["surface"])
    date = pd.Timestamp(match["date"])
    features = builder.build_matchup_features(
        history=history,
        player_a=player_a,
        player_b=player_b,
        as_of_date=date,
        surface=surface,
        tour=tour,
    )
    elo_payload = elo.predict_with_payload(player_a, player_b, tour=tour)
    market_prob_a = _market_probability_for_orientation(
        match=match,
        player_a=player_a,
        player_b=player_b,
    )
    return _feature_dict_from_payload(
        features=features,
        calibrated_elo_prob_a=float(elo_payload["calibrated_prob_a"]),
        betmgm_prob_a=market_prob_a,
        target=target,
        date=date,
    )


def _feature_dict_from_payload(
    *,
    features: TennisMatchupFeatures,
    calibrated_elo_prob_a: float,
    betmgm_prob_a: float | None,
    target: float | None,
    date: pd.Timestamp,
) -> dict[str, Any]:
    """Convert a TennisMatchupFeatures payload into model columns."""
    row = {
        "date": date,
        "tour": features.tour,
        "player_a": features.player_a,
        "player_b": features.player_b,
        "target": target,
        "calibrated_elo_prob_a": _clip_prob(calibrated_elo_prob_a),
        "betmgm_prob_a": (
            None
            if betmgm_prob_a is None or pd.isna(betmgm_prob_a)
            else _clip_prob(betmgm_prob_a)
        ),
        "weighted_match_count_diff": (
            features.weighted_match_count_a - features.weighted_match_count_b
        ),
        "win_rate_diff": features.win_rate_a - features.win_rate_b,
        "common_opponent_count": features.common_opponent_count,
        "common_opponent_win_rate_diff": features.common_opponent_win_rate_diff,
        "direct_win_rate_a": features.direct_win_rate_a,
        "intransitivity_complexity": features.intransitivity_complexity,
        "serveadv_diff": features.serveadv_a - features.serveadv_b,
        "complete_diff": features.complete_a - features.complete_b,
        "fatigue_diff": features.fatigue_diff,
        "retired_diff": features.retired_a - features.retired_b,
        "age_30_diff": features.age_30_a - features.age_30_b,
        "rank_diff": features.rank_diff,
        "data_certainty": features.data_certainty,
    }
    return row


def _normalize_history(history: pd.DataFrame) -> pd.DataFrame:
    """Normalize accepted tennis history column variants."""
    if history.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, row in history.iterrows():
        date_value = _first(row, "date", "Date", "game_date")
        winner = _first(row, "winner", "Winner", "winner_name")
        loser = _first(row, "loser", "Loser", "loser_name")
        if pd.isna(date_value) or pd.isna(winner) or pd.isna(loser):
            continue
        rows.append(
            {
                **row.to_dict(),
                "date": pd.Timestamp(date_value),
                "tour": str(_first(row, "tour", "Tour", default="ATP")).upper(),
                "surface": str(_first(row, "surface", "Surface", default="Hard")),
                "winner": str(winner).strip(),
                "loser": str(loser).strip(),
            }
        )
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _first(row: pd.Series, *names: str, default: Any = None) -> Any:
    """Return first non-null row value by column name."""
    for name in names:
        if name in row.index and not pd.isna(row[name]):
            return row[name]
    return default


def _build_pipeline() -> TennisStackedEnsembleModel:
    """Return the stacked tennis feature model."""
    return TennisStackedEnsembleModel()


def _build_metrics(
    *,
    data_source: str,
    total_rows: int,
    holdout_rows: int,
    y: np.ndarray,
    baseline_prob: np.ndarray,
    ensemble_prob: np.ndarray,
    market_prob: np.ndarray,
) -> TennisModelMetrics:
    """Build holdout metrics and enablement gate."""
    baseline_log_loss = _log_loss(y, baseline_prob)
    ensemble_log_loss = _log_loss(y, ensemble_prob)
    baseline_brier = _brier(y, baseline_prob)
    ensemble_brier = _brier(y, ensemble_prob)
    baseline_accuracy = _accuracy(y, baseline_prob)
    ensemble_accuracy = _accuracy(y, ensemble_prob)
    baseline_actionable = _actionable_count(baseline_prob)
    ensemble_actionable = _actionable_count(ensemble_prob)
    market_mask = np.isfinite(market_prob.astype(float))
    betmgm_holdout_rows = int(np.sum(market_mask))
    ensemble_market_log_loss: float | None = None
    betmgm_log_loss: float | None = None
    ensemble_vs_betmgm_log_loss_delta: float | None = None
    ensemble_market_brier: float | None = None
    betmgm_brier: float | None = None
    ensemble_vs_betmgm_brier_delta: float | None = None
    ensemble_market_accuracy: float | None = None
    betmgm_accuracy: float | None = None
    ensemble_vs_betmgm_accuracy_delta: float | None = None
    beats_betmgm = False

    if betmgm_holdout_rows > 0:
        market_subset = _clip_prob_array(market_prob[market_mask])
        ensemble_subset = ensemble_prob[market_mask]
        y_subset = y[market_mask]
        ensemble_market_log_loss = _log_loss(y_subset, ensemble_subset)
        betmgm_log_loss = _log_loss(y_subset, market_subset)
        ensemble_vs_betmgm_log_loss_delta = ensemble_market_log_loss - betmgm_log_loss
        ensemble_market_brier = _brier(y_subset, ensemble_subset)
        betmgm_brier = _brier(y_subset, market_subset)
        ensemble_vs_betmgm_brier_delta = ensemble_market_brier - betmgm_brier
        ensemble_market_accuracy = _accuracy(y_subset, ensemble_subset)
        betmgm_accuracy = _accuracy(y_subset, market_subset)
        ensemble_vs_betmgm_accuracy_delta = ensemble_market_accuracy - betmgm_accuracy
        beats_betmgm = (
            ensemble_vs_betmgm_log_loss_delta < 0
            and ensemble_vs_betmgm_brier_delta < 0
            and ensemble_vs_betmgm_accuracy_delta >= 0
        )

    enabled = ensemble_log_loss < baseline_log_loss and ensemble_brier < baseline_brier
    return TennisModelMetrics(
        model_version=MODEL_VERSION,
        data_source=data_source,
        rows=total_rows,
        holdout_rows=holdout_rows,
        enabled=enabled,
        baseline_log_loss=baseline_log_loss,
        ensemble_log_loss=ensemble_log_loss,
        log_loss_delta=ensemble_log_loss - baseline_log_loss,
        baseline_brier=baseline_brier,
        ensemble_brier=ensemble_brier,
        brier_delta=ensemble_brier - baseline_brier,
        baseline_accuracy=baseline_accuracy,
        ensemble_accuracy=ensemble_accuracy,
        accuracy_delta=ensemble_accuracy - baseline_accuracy,
        baseline_actionable_count=baseline_actionable,
        ensemble_actionable_count=ensemble_actionable,
        actionable_count_delta=ensemble_actionable - baseline_actionable,
        betmgm_holdout_rows=betmgm_holdout_rows,
        ensemble_market_log_loss=ensemble_market_log_loss,
        betmgm_log_loss=betmgm_log_loss,
        ensemble_vs_betmgm_log_loss_delta=ensemble_vs_betmgm_log_loss_delta,
        ensemble_market_brier=ensemble_market_brier,
        betmgm_brier=betmgm_brier,
        ensemble_vs_betmgm_brier_delta=ensemble_vs_betmgm_brier_delta,
        ensemble_market_accuracy=ensemble_market_accuracy,
        betmgm_accuracy=betmgm_accuracy,
        ensemble_vs_betmgm_accuracy_delta=ensemble_vs_betmgm_accuracy_delta,
        beats_betmgm=beats_betmgm,
    )


def _blend_probabilities(
    calibrated_elo_prob: np.ndarray,
    feature_model_prob: np.ndarray,
) -> np.ndarray:
    """Blend calibrated Elo and feature model probabilities."""
    blended = (
        ENSEMBLE_ELO_WEIGHT * calibrated_elo_prob
        + ENSEMBLE_FEATURE_WEIGHT * feature_model_prob
    )
    return np.clip(blended, 0.01, 0.99)


def _log_loss(y: np.ndarray, p: np.ndarray) -> float:
    """Binary log loss."""
    bounded = np.clip(p.astype(float), 1e-9, 1.0 - 1e-9)
    return float(-np.mean(y * np.log(bounded) + (1.0 - y) * np.log(1.0 - bounded)))


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    """Brier score."""
    return float(np.mean((p.astype(float) - y.astype(float)) ** 2))


def _accuracy(y: np.ndarray, p: np.ndarray) -> float:
    """Binary accuracy at 0.5 probability."""
    return float(np.mean((p >= 0.5) == (y == 1.0)))


def _actionable_count(prob: np.ndarray) -> int:
    """Count opportunities against a neutral market proxy for comparability."""
    market_prob = 0.50
    edge = prob - market_prob
    return int(np.sum((edge >= 0.03) & (edge <= 0.40)))


def _clip_prob(value: float) -> float:
    """Clamp probability to a numerically safe unit interval."""
    return float(np.clip(float(value), 0.01, 0.99))


def _clip_prob_array(values: np.ndarray) -> np.ndarray:
    """Clamp a probability array to a numerically safe unit interval."""
    return np.clip(values.astype(float), 0.01, 0.99)


def _market_probability_for_orientation(
    *, match: pd.Series, player_a: str, player_b: str
) -> float | None:
    """Return BetMGM implied probability for the oriented player-A row."""
    winner = str(match["winner"])
    loser = str(match["loser"])
    winner_prob = _safe_optional_float(match.get("winner_market_prob"))
    loser_prob = _safe_optional_float(match.get("loser_market_prob"))
    if winner_prob is None or loser_prob is None:
        return None
    if player_a == winner and player_b == loser:
        return winner_prob
    if player_a == loser and player_b == winner:
        return loser_prob
    return None


def _safe_optional_float(value: Any) -> float | None:
    """Return a finite float or ``None``."""
    if value is None or pd.isna(value):
        return None
    value_float = float(value)
    if not np.isfinite(value_float):
        return None
    return value_float


def _build_base_models() -> list[Any]:
    """Return the base-model set used by the tennis stack."""
    models: list[Any] = [
        LogisticRegression(max_iter=1000, solver="lbfgs", random_state=42),
        RandomForestClassifier(
            n_estimators=300,
            min_samples_leaf=4,
            max_depth=6,
            random_state=42,
        ),
        HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=4,
            max_iter=250,
            min_samples_leaf=10,
            random_state=42,
        ),
    ]
    if XGBClassifier is not None:
        models.append(
            XGBClassifier(
                n_estimators=120,
                max_depth=3,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.8,
                reg_lambda=1.0,
                eval_metric="logloss",
                random_state=42,
                n_jobs=1,
            )
        )
    return models


def should_publish_metrics_to_db(metrics: TennisModelMetrics) -> bool:
    """Return whether a tennis evaluation is safe to surface on the dashboard."""
    return (
        metrics.data_source == "postgres_tennis_games"
        and metrics.holdout_rows > 0
    )


def save_metrics_to_db(metrics: TennisModelMetrics) -> bool:
    """Persist the latest tennis model-evaluation snapshot to PostgreSQL.

    Returns:
        True when the snapshot was published, False when it was intentionally
        skipped because the evaluation was not production-grade evidence.
    """
    if not should_publish_metrics_to_db(metrics):
        return False

    from plugins.db_manager import default_db

    run_date = datetime.now(timezone.utc).date().isoformat()
    default_db.execute(
        """
        INSERT INTO tennis_model_evaluations (
            run_date,
            model_version,
            data_source,
            rows,
            holdout_rows,
            betmgm_holdout_rows,
            enabled,
            beats_betmgm,
            baseline_log_loss,
            ensemble_log_loss,
            ensemble_market_log_loss,
            betmgm_log_loss,
            baseline_brier,
            ensemble_brier,
            ensemble_market_brier,
            betmgm_brier,
            baseline_accuracy,
            ensemble_accuracy,
            ensemble_market_accuracy,
            betmgm_accuracy,
            baseline_actionable_count,
            ensemble_actionable_count,
            log_loss_delta,
            brier_delta,
            accuracy_delta,
            ensemble_vs_betmgm_log_loss_delta,
            ensemble_vs_betmgm_brier_delta,
            ensemble_vs_betmgm_accuracy_delta
        ) VALUES (
            :run_date,
            :model_version,
            :data_source,
            :rows,
            :holdout_rows,
            :betmgm_holdout_rows,
            :enabled,
            :beats_betmgm,
            :baseline_log_loss,
            :ensemble_log_loss,
            :ensemble_market_log_loss,
            :betmgm_log_loss,
            :baseline_brier,
            :ensemble_brier,
            :ensemble_market_brier,
            :betmgm_brier,
            :baseline_accuracy,
            :ensemble_accuracy,
            :ensemble_market_accuracy,
            :betmgm_accuracy,
            :baseline_actionable_count,
            :ensemble_actionable_count,
            :log_loss_delta,
            :brier_delta,
            :accuracy_delta,
            :ensemble_vs_betmgm_log_loss_delta,
            :ensemble_vs_betmgm_brier_delta,
            :ensemble_vs_betmgm_accuracy_delta
        )
        ON CONFLICT (run_date, model_version, data_source) DO UPDATE SET
            rows = EXCLUDED.rows,
            holdout_rows = EXCLUDED.holdout_rows,
            betmgm_holdout_rows = EXCLUDED.betmgm_holdout_rows,
            enabled = EXCLUDED.enabled,
            beats_betmgm = EXCLUDED.beats_betmgm,
            baseline_log_loss = EXCLUDED.baseline_log_loss,
            ensemble_log_loss = EXCLUDED.ensemble_log_loss,
            ensemble_market_log_loss = EXCLUDED.ensemble_market_log_loss,
            betmgm_log_loss = EXCLUDED.betmgm_log_loss,
            baseline_brier = EXCLUDED.baseline_brier,
            ensemble_brier = EXCLUDED.ensemble_brier,
            ensemble_market_brier = EXCLUDED.ensemble_market_brier,
            betmgm_brier = EXCLUDED.betmgm_brier,
            baseline_accuracy = EXCLUDED.baseline_accuracy,
            ensemble_accuracy = EXCLUDED.ensemble_accuracy,
            ensemble_market_accuracy = EXCLUDED.ensemble_market_accuracy,
            betmgm_accuracy = EXCLUDED.betmgm_accuracy,
            baseline_actionable_count = EXCLUDED.baseline_actionable_count,
            ensemble_actionable_count = EXCLUDED.ensemble_actionable_count,
            log_loss_delta = EXCLUDED.log_loss_delta,
            brier_delta = EXCLUDED.brier_delta,
            accuracy_delta = EXCLUDED.accuracy_delta,
            ensemble_vs_betmgm_log_loss_delta = EXCLUDED.ensemble_vs_betmgm_log_loss_delta,
            ensemble_vs_betmgm_brier_delta = EXCLUDED.ensemble_vs_betmgm_brier_delta,
            ensemble_vs_betmgm_accuracy_delta = EXCLUDED.ensemble_vs_betmgm_accuracy_delta,
            created_at = CURRENT_TIMESTAMP
        """,
        {"run_date": run_date, **metrics.to_payload()},
    )
    return True
