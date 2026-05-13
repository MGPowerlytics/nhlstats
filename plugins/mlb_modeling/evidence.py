"""Evidence utilities for MLB model-improvement backtests."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Mapping, Sequence

import numpy as np
import pandas as pd

from plugins.elo.mlb_elo_rating import MLBEloRating, is_regular_season_date
from plugins.constants import (
    HIGH_CONFIDENCE_MIN_EDGE,
    MAX_EDGE_THRESHOLD,
    MEDIUM_CONFIDENCE_MIN_EDGE,
)


VEGAS_MONEYLINE_ACCURACY_BENCHMARK = 0.569
MIN_EDGE_THRESHOLD = 0.03
EDGE_EPSILON = 1e-12


@dataclass(frozen=True)
class EloBacktestConfig:
    """Configuration for a chronological MLB Elo backtest."""

    model_name: str
    k_factor: float
    home_advantage: float
    use_mov: bool
    skip_spring_training: bool = True
    season_carryover: float = 0.0


@dataclass(frozen=True)
class ModelEvidenceMetrics:
    """Out-of-sample probability metrics for one MLB model."""

    model_name: str
    games: int
    accuracy: float
    accuracy_vs_vegas_benchmark: float
    log_loss: float
    brier_score: float
    expected_calibration_error: float
    favorite_win_rate: float
    top_decile_accuracy: float
    top_decile_lift: float
    avg_confidence: float

    def to_dict(self) -> Dict[str, float | int | str]:
        """Return a JSON/table-friendly representation."""
        return asdict(self)


@dataclass(frozen=True)
class ModelImprovementDelta:
    """Candidate-vs-baseline deltas for model promotion evidence."""

    baseline_model: str
    candidate_model: str
    accuracy_delta: float
    log_loss_delta: float
    brier_score_delta: float
    ece_delta: float
    passes_probability_gate: bool

    def to_dict(self) -> Dict[str, float | bool | str]:
        """Return a JSON/table-friendly representation."""
        return asdict(self)


@dataclass(frozen=True)
class BettingEvidenceMetrics:
    """Flat-stake betting evidence from real odds snapshots."""

    bet_count: int
    flat_roi: float
    clv_hit_rate: float
    tier_a_bet_count: int
    tier_a_roi: float

    def to_dict(self) -> Dict[str, float | int]:
        """Return a JSON/table-friendly representation."""
        return asdict(self)


EDGE_BUCKET_LABELS = ["3-5%", "5-8%", "8-15%", "15%+"]


LEGACY_REGULAR_SEASON_CONFIG = EloBacktestConfig(
    model_name="legacy_k10_ha75_regular_season",
    k_factor=10.0,
    home_advantage=75.0,
    use_mov=False,
    skip_spring_training=True,
)
PRODUCTION_TUNED_CONFIG = EloBacktestConfig(
    model_name="production_k4_ha20_no_mov_regular_season",
    k_factor=4.0,
    home_advantage=20.0,
    use_mov=False,
    skip_spring_training=True,
)
LEGACY_ALL_GAMES_CONFIG = EloBacktestConfig(
    model_name="legacy_k10_ha75_all_games",
    k_factor=10.0,
    home_advantage=75.0,
    use_mov=False,
    skip_spring_training=False,
)


def load_mlb_games_csv(path: str) -> pd.DataFrame:
    """Load MLB game-result rows from a checked-in CSV export."""
    df = pd.read_csv(path)
    return prepare_mlb_games(df)


def prepare_mlb_games(games: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate MLB game rows for chronological backtesting."""
    required = {
        "game_id",
        "game_date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
    }
    missing = required.difference(games.columns)
    if missing:
        raise ValueError(f"missing required MLB game columns: {sorted(missing)}")

    prepared = games.copy()
    prepared["game_date"] = pd.to_datetime(prepared["game_date"]).dt.date
    prepared["home_score"] = pd.to_numeric(prepared["home_score"], errors="coerce")
    prepared["away_score"] = pd.to_numeric(prepared["away_score"], errors="coerce")
    prepared = prepared.dropna(
        subset=[
            "game_id",
            "game_date",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
        ]
    )
    prepared = prepared[prepared["home_score"] != prepared["away_score"]]
    prepared = prepared.sort_values(["game_date", "game_id"]).reset_index(drop=True)
    return prepared


def run_elo_backtest(
    games: pd.DataFrame,
    config: EloBacktestConfig,
) -> pd.DataFrame:
    """Run a leakage-safe chronological Elo backtest.

    Each row is predicted before the model observes that game's result.
    """
    prepared = prepare_mlb_games(games)
    elo = MLBEloRating(
        k_factor=config.k_factor,
        home_advantage=config.home_advantage,
        use_mov=config.use_mov,
    )
    records: List[Dict[str, object]] = []
    previous_year: int | None = None

    for row in prepared.itertuples(index=False):
        game_date = _coerce_date(row.game_date)
        if config.skip_spring_training and not is_regular_season_date(game_date):
            continue

        if previous_year is not None and game_date.year != previous_year:
            elo.apply_season_carryover(config.season_carryover)
        previous_year = game_date.year

        home_team = str(row.home_team)
        away_team = str(row.away_team)
        home_score = int(row.home_score)
        away_score = int(row.away_score)
        home_prob = float(elo.predict(home_team, away_team))
        home_won = home_score > away_score

        records.append(
            {
                "model_name": config.model_name,
                "game_id": str(row.game_id),
                "game_date": game_date,
                "home_team": home_team,
                "away_team": away_team,
                "home_prob": home_prob,
                "home_won": int(home_won),
                "favorite_prob": max(home_prob, 1.0 - home_prob),
                "favorite_won": int((home_prob >= 0.5) == home_won),
            }
        )
        elo.update(
            home_team,
            away_team,
            home_won=home_won,
            home_score=home_score,
            away_score=away_score,
        )

    return pd.DataFrame(records)


def evaluate_prediction_records(
    prediction_records: pd.DataFrame,
    n_bins: int = 10,
) -> ModelEvidenceMetrics:
    """Calculate accuracy, loss, calibration, and lift metrics."""
    if prediction_records.empty:
        raise ValueError("prediction_records must be non-empty")

    model_names = prediction_records["model_name"].dropna().unique()
    if len(model_names) != 1:
        raise ValueError("prediction_records must contain exactly one model_name")

    probs = np.clip(
        prediction_records["home_prob"].to_numpy(dtype=float), 1e-12, 1 - 1e-12
    )
    outcomes = prediction_records["home_won"].to_numpy(dtype=int)
    favorite_probs = prediction_records["favorite_prob"].to_numpy(dtype=float)
    favorite_won = prediction_records["favorite_won"].to_numpy(dtype=int)
    accuracy = float(np.mean(favorite_won))
    log_loss = float(
        -np.mean(outcomes * np.log(probs) + (1 - outcomes) * np.log(1 - probs))
    )
    brier = float(np.mean((probs - outcomes) ** 2))
    ece = expected_calibration_error(outcomes, probs, n_bins=n_bins)
    top_decile_accuracy = _top_quantile_accuracy(
        favorite_probs, favorite_won, quantile=0.90
    )
    top_decile_lift = top_decile_accuracy / accuracy if accuracy > 0 else 0.0

    return ModelEvidenceMetrics(
        model_name=str(model_names[0]),
        games=int(len(prediction_records)),
        accuracy=accuracy,
        accuracy_vs_vegas_benchmark=accuracy - VEGAS_MONEYLINE_ACCURACY_BENCHMARK,
        log_loss=log_loss,
        brier_score=brier,
        expected_calibration_error=ece,
        favorite_win_rate=accuracy,
        top_decile_accuracy=top_decile_accuracy,
        top_decile_lift=top_decile_lift,
        avg_confidence=float(np.mean(favorite_probs)),
    )


def expected_calibration_error(
    outcomes: Sequence[int],
    probabilities: Sequence[float],
    n_bins: int = 10,
) -> float:
    """Return expected calibration error for binary home-win probabilities."""
    labels = np.asarray(outcomes, dtype=int)
    probs = np.asarray(probabilities, dtype=float)
    if labels.size == 0 or labels.size != probs.size:
        raise ValueError(
            "outcomes and probabilities must be non-empty and equal length"
        )

    bin_count = max(1, int(n_bins))
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    ece = 0.0
    for idx in range(bin_count):
        left, right = edges[idx], edges[idx + 1]
        if idx == bin_count - 1:
            mask = (probs >= left) & (probs <= right)
        else:
            mask = (probs >= left) & (probs < right)
        if not np.any(mask):
            continue
        confidence = float(np.mean(probs[mask]))
        observed = float(np.mean(labels[mask]))
        ece += float(np.mean(mask)) * abs(confidence - observed)
    return float(ece)


def compare_model_metrics(
    baseline: ModelEvidenceMetrics,
    candidate: ModelEvidenceMetrics,
) -> ModelImprovementDelta:
    """Compare a candidate model against a baseline model."""
    log_loss_delta = candidate.log_loss - baseline.log_loss
    brier_delta = candidate.brier_score - baseline.brier_score
    ece_delta = (
        candidate.expected_calibration_error - baseline.expected_calibration_error
    )
    return ModelImprovementDelta(
        baseline_model=baseline.model_name,
        candidate_model=candidate.model_name,
        accuracy_delta=candidate.accuracy - baseline.accuracy,
        log_loss_delta=log_loss_delta,
        brier_score_delta=brier_delta,
        ece_delta=ece_delta,
        passes_probability_gate=log_loss_delta < 0
        and brier_delta <= 0
        and ece_delta <= 0,
    )


def compute_betting_evidence_metrics(
    *,
    recommendations: pd.DataFrame,
    odds_snapshots: pd.DataFrame,
    games: pd.DataFrame,
) -> BettingEvidenceMetrics:
    """Compute flat ROI and CLV hit rate from real odds snapshots.

    Opening snapshot price is used as the entry proxy when no bet timestamp is
    available; closing snapshot price is the latest price before commence time.
    The function refuses empty odds input so result-only backtests cannot invent
    ROI or CLV.
    """
    if odds_snapshots.empty:
        raise ValueError("odds_snapshots must be non-empty for ROI/CLV evidence")
    if recommendations.empty:
        raise ValueError("recommendations must be non-empty")
    if games.empty:
        raise ValueError("games must be non-empty")

    evidence_frame = build_betting_evidence_frame(
        recommendations=recommendations,
        odds_snapshots=odds_snapshots,
        games=games,
    )
    pnl = evidence_frame["pnl"].to_list()
    clv_hits = evidence_frame["clv_hit"].to_list()
    tier_a_pnl = evidence_frame.loc[
        evidence_frame["confidence"].astype(str).str.upper().isin({"HIGH", "TIER A", "A"}),
        "pnl",
    ].to_list()

    return BettingEvidenceMetrics(
        bet_count=len(pnl),
        flat_roi=float(np.mean(pnl)),
        clv_hit_rate=float(np.mean(clv_hits)),
        tier_a_bet_count=len(tier_a_pnl),
        tier_a_roi=float(np.mean(tier_a_pnl)) if tier_a_pnl else 0.0,
    )


def build_value_recommendations(
    prediction_records: pd.DataFrame,
    odds_snapshots: pd.DataFrame,
    *,
    min_edge: float = MIN_EDGE_THRESHOLD,
    max_edge: float = MAX_EDGE_THRESHOLD,
    medium_confidence_min_edge: float = MEDIUM_CONFIDENCE_MIN_EDGE,
    high_confidence_min_edge: float = HIGH_CONFIDENCE_MIN_EDGE,
) -> pd.DataFrame:
    """Build flat-stake value recommendations from predictions and pregame odds."""
    if prediction_records.empty:
        raise ValueError("prediction_records must be non-empty")
    if odds_snapshots.empty:
        raise ValueError("odds_snapshots must be non-empty")

    openings = _prepare_opening_snapshots(odds_snapshots)
    by_game = openings.set_index(["game_id", "outcome_role"])
    recommendations: list[dict[str, object]] = []

    for row in prediction_records.to_dict("records"):
        game_id = str(row["game_id"])
        home_market = _market_probability(by_game, game_id, "home")
        away_market = _market_probability(by_game, game_id, "away")
        if home_market is None or away_market is None:
            continue

        home_prob = float(row["home_prob"])
        away_prob = 1.0 - home_prob
        candidates = [
            ("home", str(row["home_team"]), home_prob, home_market),
            ("away", str(row["away_team"]), away_prob, away_market),
        ]
        eligible = []
        for outcome_role, outcome_name, model_prob, market_prob in candidates:
            edge = model_prob - market_prob
            if edge + EDGE_EPSILON < min_edge or edge - EDGE_EPSILON > max_edge:
                continue
            eligible.append((edge, outcome_role, outcome_name, model_prob, market_prob))
        if not eligible:
            continue

        edge, outcome_role, outcome_name, model_prob, market_prob = max(
            eligible, key=lambda item: item[0]
        )
        recommendations.append(
            {
                "game_id": game_id,
                "game_date": row["game_date"],
                "bet_on": outcome_name,
                "outcome_name": outcome_name,
                "outcome_role": outcome_role,
                "model_prob": model_prob,
                "market_prob": market_prob,
                "edge": edge,
                "confidence": _edge_confidence(
                    edge,
                    medium_confidence_min_edge=medium_confidence_min_edge,
                    high_confidence_min_edge=high_confidence_min_edge,
                ),
            }
        )

    return pd.DataFrame(recommendations)


def build_betting_evidence_frame(
    *,
    recommendations: pd.DataFrame,
    odds_snapshots: pd.DataFrame,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """Return one matched evidence row per recommendation."""
    if odds_snapshots.empty:
        raise ValueError("odds_snapshots must be non-empty for ROI/CLV evidence")
    if recommendations.empty:
        raise ValueError("recommendations must be non-empty")
    if games.empty:
        raise ValueError("games must be non-empty")

    snapshots = _prepare_pregame_snapshots(odds_snapshots)
    game_lookup = games.set_index("game_id").to_dict("index")
    evidence_rows: list[dict[str, object]] = []

    for rec in recommendations.to_dict("records"):
        game_id = rec.get("game_id")
        if game_id not in game_lookup:
            continue
        game = game_lookup[game_id]
        role = _recommendation_outcome_role(rec, game)
        if role is None:
            continue

        side_snapshots = snapshots[
            (snapshots["game_id"] == game_id) & (snapshots["outcome_role"] == role)
        ].sort_values("source_snapshot_at")
        if side_snapshots.empty:
            continue

        entry = _select_entry_snapshot(side_snapshots)
        close = _select_close_snapshot(side_snapshots)
        entry_price = float(entry["decimal_price"])
        close_price = float(close["decimal_price"])
        won = _bet_won(role, game)
        bet_pnl = entry_price - 1.0 if won else -1.0
        evidence_rows.append(
            {
                "game_id": str(game_id),
                "game_date": rec.get("game_date"),
                "bookmaker_key": str(
                    entry.get("bookmaker_key") or close.get("bookmaker_key") or ""
                ),
                "bet_on": rec.get("bet_on") or rec.get("outcome_name"),
                "outcome_role": role,
                "confidence": str(rec.get("confidence") or ""),
                "edge": float(rec.get("edge")) if rec.get("edge") is not None else np.nan,
                "model_prob": float(rec.get("model_prob"))
                if rec.get("model_prob") is not None
                else np.nan,
                "market_prob": float(rec.get("market_prob"))
                if rec.get("market_prob") is not None
                else np.nan,
                "entry_price": entry_price,
                "close_price": close_price,
                "entry_implied_probability": _snapshot_implied_probability(entry),
                "close_implied_probability": _snapshot_implied_probability(close),
                "entry_snapshot_type": str(entry.get("snapshot_type") or ""),
                "close_snapshot_type": str(close.get("snapshot_type") or ""),
                "snapshot_count": int(len(side_snapshots)),
                "explicit_open_available": bool(
                    "snapshot_type" in side_snapshots.columns
                    and side_snapshots["snapshot_type"].astype(str).eq("open").any()
                ),
                "explicit_close_available": bool(
                    "snapshot_type" in side_snapshots.columns
                    and side_snapshots["snapshot_type"].astype(str).eq("close").any()
                ),
                "won": bool(won),
                "pnl": float(bet_pnl),
                "clv_hit": bool(entry_price > close_price),
                "clv_decimal_delta": float(entry_price - close_price),
            }
        )

    if not evidence_rows:
        raise ValueError("no recommendations could be matched to odds snapshots")
    return pd.DataFrame(evidence_rows)


def summarize_betting_evidence_by_edge_bucket(
    evidence_frame: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate ROI and CLV by modeled edge bucket."""
    if evidence_frame.empty:
        raise ValueError("evidence_frame must be non-empty")

    frame = evidence_frame.copy()
    frame["edge_bucket"] = pd.Categorical(
        frame["edge"].apply(_edge_bucket_label),
        categories=EDGE_BUCKET_LABELS,
        ordered=True,
    )
    rows: list[dict[str, object]] = []
    for bucket_label in EDGE_BUCKET_LABELS:
        bucket = frame[frame["edge_bucket"] == bucket_label]
        if bucket.empty:
            continue
        rows.append(
            {
                "edge_bucket": bucket_label,
                "bet_count": int(len(bucket)),
                "avg_edge": float(bucket["edge"].mean()),
                "flat_roi": float(bucket["pnl"].mean()),
                "clv_hit_rate": float(bucket["clv_hit"].mean()),
                "win_rate": float(bucket["won"].mean()),
            }
        )
    return pd.DataFrame(rows)


def audit_clv_snapshot_fidelity(evidence_frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize how often CLV uses explicit open/close snapshots."""
    if evidence_frame.empty:
        raise ValueError("evidence_frame must be non-empty")

    group_keys = (
        sorted(
            value
            for value in evidence_frame["bookmaker_key"].dropna().astype(str).unique()
            if value
        )
        if "bookmaker_key" in evidence_frame.columns
        else []
    )
    if not group_keys:
        grouped_items = [("__all__", evidence_frame)]
    else:
        grouped_items = [
            (bookmaker, evidence_frame[evidence_frame["bookmaker_key"] == bookmaker])
            for bookmaker in group_keys
        ]

    rows: list[dict[str, object]] = []
    for bookmaker_key, group in grouped_items:
        rows.append(
            {
                "bookmaker_key": bookmaker_key,
                "bet_count": int(len(group)),
                "explicit_open_rate": float(
                    group["entry_snapshot_type"].astype(str).eq("open").mean()
                ),
                "explicit_close_rate": float(
                    group["close_snapshot_type"].astype(str).eq("close").mean()
                ),
                "proxy_close_rate": float(
                    (~group["close_snapshot_type"].astype(str).eq("close")).mean()
                ),
                "avg_snapshots_per_bet": float(group["snapshot_count"].mean()),
                "clv_hit_rate": float(group["clv_hit"].mean()),
                "avg_clv_decimal_delta": float(group["clv_decimal_delta"].mean()),
            }
        )
    return pd.DataFrame(rows)


def run_standard_elo_improvement_backtest(games: pd.DataFrame) -> Dict[str, object]:
    """Run the standard MLB baseline-vs-production evidence comparison."""
    configs = [
        LEGACY_REGULAR_SEASON_CONFIG,
        PRODUCTION_TUNED_CONFIG,
        LEGACY_ALL_GAMES_CONFIG,
    ]
    metrics = [
        evaluate_prediction_records(run_elo_backtest(games, config))
        for config in configs
    ]
    by_name = {metric.model_name: metric for metric in metrics}
    delta = compare_model_metrics(
        by_name[LEGACY_REGULAR_SEASON_CONFIG.model_name],
        by_name[PRODUCTION_TUNED_CONFIG.model_name],
    )
    return {
        "metrics": metrics,
        "delta": delta,
    }


def format_metrics_table(metrics: Iterable[ModelEvidenceMetrics]) -> str:
    """Format evidence metrics as a compact Markdown table."""
    rows = [
        "| Model | Games | Accuracy | vs 56.9% | Log loss | Brier | ECE | Top-decile lift |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for metric in metrics:
        rows.append(
            "| {model} | {games} | {acc:.3%} | {bench:+.3%} | {log:.4f} | "
            "{brier:.4f} | {ece:.3%} | {lift:.3f} |".format(
                model=metric.model_name,
                games=metric.games,
                acc=metric.accuracy,
                bench=metric.accuracy_vs_vegas_benchmark,
                log=metric.log_loss,
                brier=metric.brier_score,
                ece=metric.expected_calibration_error,
                lift=metric.top_decile_lift,
            )
        )
    return "\n".join(rows)


def _top_quantile_accuracy(
    confidence: np.ndarray,
    favorite_won: np.ndarray,
    quantile: float,
) -> float:
    threshold = float(np.quantile(confidence, quantile))
    mask = confidence >= threshold
    if not np.any(mask):
        return 0.0
    return float(np.mean(favorite_won[mask]))


def _recommendation_outcome_role(
    recommendation: Mapping[str, object],
    game: Mapping[str, object],
) -> str | None:
    bet_on = str(
        recommendation.get("bet_on") or recommendation.get("outcome_name") or ""
    )
    if bet_on.lower() in {"home", "away"}:
        return bet_on.lower()
    if bet_on == str(game.get("home_team")):
        return "home"
    if bet_on == str(game.get("away_team")):
        return "away"
    return None


def _bet_won(role: str, game: Mapping[str, object]) -> bool:
    home_score = float(game["home_score"])
    away_score = float(game["away_score"])
    return home_score > away_score if role == "home" else away_score > home_score


def _prepare_pregame_snapshots(odds_snapshots: pd.DataFrame) -> pd.DataFrame:
    snapshots = odds_snapshots.copy()
    snapshots["source_snapshot_at"] = pd.to_datetime(
        snapshots["source_snapshot_at"], utc=True
    )
    snapshots["commence_time"] = pd.to_datetime(snapshots["commence_time"], utc=True)
    snapshots = snapshots[snapshots["source_snapshot_at"] < snapshots["commence_time"]]
    if snapshots.empty:
        raise ValueError("odds_snapshots must include pregame prices")
    return snapshots


def _prepare_opening_snapshots(odds_snapshots: pd.DataFrame) -> pd.DataFrame:
    snapshots = _prepare_pregame_snapshots(odds_snapshots)
    preferred = snapshots
    if "snapshot_type" in snapshots.columns and (snapshots["snapshot_type"] == "open").any():
        preferred = snapshots[snapshots["snapshot_type"] == "open"]

    openings = (
        preferred.sort_values("source_snapshot_at")
        .groupby(["game_id", "outcome_role"], as_index=False)
        .first()
    )
    return openings


def _select_entry_snapshot(side_snapshots: pd.DataFrame) -> pd.Series:
    if (
        "snapshot_type" in side_snapshots.columns
        and side_snapshots["snapshot_type"].astype(str).eq("open").any()
    ):
        return side_snapshots[side_snapshots["snapshot_type"].astype(str) == "open"].iloc[
            0
        ]
    return side_snapshots.iloc[0]


def _select_close_snapshot(side_snapshots: pd.DataFrame) -> pd.Series:
    if (
        "snapshot_type" in side_snapshots.columns
        and side_snapshots["snapshot_type"].astype(str).eq("close").any()
    ):
        return side_snapshots[side_snapshots["snapshot_type"].astype(str) == "close"].iloc[
            -1
        ]
    return side_snapshots.iloc[-1]


def _market_probability(
    openings: pd.DataFrame,
    game_id: str,
    outcome_role: str,
) -> float | None:
    try:
        row = openings.loc[(game_id, outcome_role)]
    except KeyError:
        return None
    return float(row["implied_probability"])


def _snapshot_implied_probability(snapshot: pd.Series) -> float:
    implied = snapshot.get("implied_probability")
    if implied is not None and not pd.isna(implied):
        return float(implied)
    return round(1.0 / float(snapshot["decimal_price"]), 8)


def _edge_confidence(
    edge: float,
    *,
    medium_confidence_min_edge: float,
    high_confidence_min_edge: float,
) -> str:
    if edge + EDGE_EPSILON >= high_confidence_min_edge:
        return "HIGH"
    if edge + EDGE_EPSILON >= medium_confidence_min_edge:
        return "MEDIUM"
    return "LOW"


def _edge_bucket_label(edge: float) -> str:
    if edge < 0.05:
        return "3-5%"
    if edge < 0.08:
        return "5-8%"
    if edge < 0.15:
        return "8-15%"
    return "15%+"


def _coerce_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
