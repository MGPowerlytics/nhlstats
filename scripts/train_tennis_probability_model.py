#!/usr/bin/env python3
"""Train/evaluate the tennis probability model.

By default the command prefers PostgreSQL, then local CSVs under ``data/tennis``.
Use ``--data-source benchmark`` to run the deterministic offline benchmark when
runtime data is unavailable.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins.elo.tennis_probability_model import (
    DEFAULT_METRICS_PATH,
    DEFAULT_MODEL_PATH,
    build_benchmark_history,
    load_history_from_csv_dir,
    load_history_from_db,
    persist_training_outputs,
    train_and_evaluate,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-source",
        choices=["auto", "db", "csv", "benchmark"],
        default="auto",
        help="Training data source.",
    )
    parser.add_argument(
        "--csv-dir", default="data/tennis", help="Local tennis CSV dir."
    )
    parser.add_argument(
        "--model-path",
        default=str(DEFAULT_MODEL_PATH),
        help="Output model artifact path.",
    )
    parser.add_argument(
        "--metrics-path",
        default=str(DEFAULT_METRICS_PATH),
        help="Output metrics JSON path.",
    )
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Compute metrics without writing model/metrics artifacts.",
    )
    parser.add_argument(
        "--max-history-rows",
        type=int,
        default=1200,
        help=(
            "Use only the newest N historical matches for training/evaluation. "
            "Set to 0 to use every available row."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run training/evaluation and print the metric comparison."""
    args = parse_args(argv)
    history, source_label = _load_history(args.data_source, Path(args.csv_dir))
    max_matches = args.max_history_rows if args.max_history_rows > 0 else None
    model, metrics, frame = train_and_evaluate(
        history, data_source=source_label, max_matches=max_matches
    )

    if not args.evaluate_only:
        model_path = Path(args.model_path)
        metrics_path = Path(args.metrics_path)
        persist_training_outputs(
            model,
            metrics,
            model_path=model_path,
            metrics_path=metrics_path,
            publish_metrics=True,
        )

    print(f"data_source: {metrics.data_source}")
    print(f"training_rows: {metrics.rows}")
    print(f"holdout_rows: {metrics.holdout_rows}")
    print(f"enabled: {metrics.enabled}")
    print("")
    print("metric                 calibrated_elo     ensemble          delta")
    print(
        f"log_loss               {metrics.baseline_log_loss:>14.4f}     "
        f"{metrics.ensemble_log_loss:>8.4f}     {metrics.log_loss_delta:>+10.4f}"
    )
    print(
        f"brier_score            {metrics.baseline_brier:>14.4f}     "
        f"{metrics.ensemble_brier:>8.4f}     {metrics.brier_delta:>+10.4f}"
    )
    print(
        f"accuracy               {metrics.baseline_accuracy:>14.3%}     "
        f"{metrics.ensemble_accuracy:>8.3%}     {metrics.accuracy_delta:>+10.3%}"
    )
    print(
        f"actionable_ev_count    {metrics.baseline_actionable_count:>14d}     "
        f"{metrics.ensemble_actionable_count:>8d}     "
        f"{metrics.actionable_count_delta:>+10d}"
    )
    if metrics.betmgm_holdout_rows:
        print("")
        print(
            "BetMGM comparison on shared holdout rows "
            f"({metrics.betmgm_holdout_rows} rows)"
        )
        print("metric                 betmgm baseline     ensemble          delta")
        print(
            f"log_loss               {metrics.betmgm_log_loss:>14.4f}     "
            f"{metrics.ensemble_market_log_loss:>8.4f}     "
            f"{metrics.ensemble_vs_betmgm_log_loss_delta:>+10.4f}"
        )
        print(
            f"brier_score            {metrics.betmgm_brier:>14.4f}     "
            f"{metrics.ensemble_market_brier:>8.4f}     "
            f"{metrics.ensemble_vs_betmgm_brier_delta:>+10.4f}"
        )
        print(
            f"accuracy               {metrics.betmgm_accuracy:>14.3%}     "
            f"{metrics.ensemble_market_accuracy:>8.3%}     "
            f"{metrics.ensemble_vs_betmgm_accuracy_delta:>+10.3%}"
        )
        print(f"beats_betmgm: {metrics.beats_betmgm}")
    print(f"feature_frame_rows: {len(frame)}")


def _load_history(data_source: str, csv_dir: Path) -> tuple[pd.DataFrame, str]:
    """Load history according to source preference."""
    if data_source == "benchmark":
        return build_benchmark_history(), "benchmark_fixture"

    if data_source in {"auto", "db"}:
        try:
            history = load_history_from_db()
            if not history.empty:
                return history, "postgres_tennis_games"
        except Exception:
            if data_source == "db":
                raise

    if data_source in {"auto", "csv"}:
        history = load_history_from_csv_dir(csv_dir)
        if not history.empty:
            return history, "local_tennis_csv"
        if data_source == "csv":
            raise ValueError(f"No tennis CSV history found in {csv_dir}")

    return build_benchmark_history(), "benchmark_fixture"


if __name__ == "__main__":
    main()
