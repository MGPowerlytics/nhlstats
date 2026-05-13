#!/usr/bin/env python3
"""Run concrete MLB model-improvement evidence checks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.mlb_modeling.evidence import (  # noqa: E402
    format_metrics_table,
    load_mlb_games_csv,
    run_standard_elo_improvement_backtest,
)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate MLB probability-model improvement evidence."
    )
    parser.add_argument(
        "--games-csv",
        default=str(ROOT / "mlb_backtest_data" / "mlb_games.csv"),
        help="Historical MLB game-results CSV.",
    )
    args = parser.parse_args()

    games = load_mlb_games_csv(args.games_csv)
    evidence = run_standard_elo_improvement_backtest(games)
    metrics = evidence["metrics"]
    delta = evidence["delta"]

    print("\nMLB MODEL IMPROVEMENT EVIDENCE")
    print(f"Source: {args.games_csv}")
    print(format_metrics_table(metrics))
    print("\nCandidate vs regular-season legacy baseline:")
    print(f"- Accuracy delta: {delta.accuracy_delta:+.3%}")
    print(f"- Log-loss delta: {delta.log_loss_delta:+.4f}")
    print(f"- Brier delta: {delta.brier_score_delta:+.4f}")
    print(f"- ECE delta: {delta.ece_delta:+.3%}")
    print(f"- Probability gate passed: {delta.passes_probability_gate}")
    print(
        "\nROI/CLV evidence is not computed here because this source contains "
        "game results only; market odds, bet timestamps, and closing prices are "
        "required for that proof."
    )
    return 0 if delta.passes_probability_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
