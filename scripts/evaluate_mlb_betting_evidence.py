#!/usr/bin/env python3
"""Run free-source MLB betting evidence with historical odds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.mlb_modeling.evidence import (  # noqa: E402
    LEGACY_REGULAR_SEASON_CONFIG,
    PRODUCTION_TUNED_CONFIG,
    audit_clv_snapshot_fidelity,
    build_betting_evidence_frame,
    build_value_recommendations,
    compute_betting_evidence_metrics,
    load_mlb_games_csv,
    run_elo_backtest,
    summarize_betting_evidence_by_edge_bucket,
)
from plugins.mlb_modeling.free_odds_sources import (  # noqa: E402
    build_princeton_mlb_odds_snapshots,
    build_sportsbookreview_mlb_odds_snapshots,
    load_free_historical_mlb_odds,
)


def _load_snapshots(path: str) -> pd.DataFrame:
    loaded = load_free_historical_mlb_odds(path)
    if isinstance(loaded, pd.DataFrame):
        payloads = build_princeton_mlb_odds_snapshots(loaded)
    else:
        payloads = build_sportsbookreview_mlb_odds_snapshots(loaded)
    return pd.DataFrame(payloads)


def _format_metrics(label: str, metrics: object) -> str:
    return (
        f"{label}: bets={metrics.bet_count}, flat_roi={metrics.flat_roi:+.3%}, "
        f"clv_hit_rate={metrics.clv_hit_rate:.3%}, "
        f"tier_a_bets={metrics.tier_a_bet_count}, tier_a_roi={metrics.tier_a_roi:+.3%}"
    )


def _format_bookmaker_table(rows: list[dict[str, object]]) -> str:
    rows = sorted(rows, key=lambda item: float(item["roi_delta"]), reverse=True)
    lines = [
        "| Bookmaker | Base bets | Base ROI | Base CLV | Prod bets | Prod ROI | Prod CLV | ROI delta | CLV delta | Prod Tier A ROI |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {bookmaker} | {base_bets} | {base_roi:+.3%} | {base_clv:.3%} | "
            "{prod_bets} | {prod_roi:+.3%} | {prod_clv:.3%} | {roi_delta:+.3%} | "
            "{clv_delta:+.3%} | {prod_tier_a_roi:+.3%} |".format(**row)
        )
    return "\n".join(lines)


def _format_edge_bucket_comparison(
    baseline: pd.DataFrame, production: pd.DataFrame
) -> str:
    merged = baseline.merge(
        production,
        on="edge_bucket",
        how="outer",
        suffixes=("_baseline", "_production"),
    ).fillna(0)
    merged["edge_bucket"] = pd.Categorical(
        merged["edge_bucket"],
        categories=["3-5%", "5-8%", "8-15%", "15%+"],
        ordered=True,
    )
    merged = merged.sort_values("edge_bucket")
    lines = [
        "| Edge bucket | Base bets | Base ROI | Base CLV | Prod bets | Prod ROI | Prod CLV | ROI delta | CLV delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in merged.to_dict("records"):
        lines.append(
            "| {edge_bucket} | {bet_count_baseline:.0f} | {flat_roi_baseline:+.3%} | "
            "{clv_hit_rate_baseline:.3%} | {bet_count_production:.0f} | "
            "{flat_roi_production:+.3%} | {clv_hit_rate_production:.3%} | "
            "{roi_delta:+.3%} | {clv_delta:+.3%} |".format(
                edge_bucket=row["edge_bucket"],
                bet_count_baseline=row["bet_count_baseline"],
                flat_roi_baseline=row["flat_roi_baseline"],
                clv_hit_rate_baseline=row["clv_hit_rate_baseline"],
                bet_count_production=row["bet_count_production"],
                flat_roi_production=row["flat_roi_production"],
                clv_hit_rate_production=row["clv_hit_rate_production"],
                roi_delta=row["flat_roi_production"] - row["flat_roi_baseline"],
                clv_delta=row["clv_hit_rate_production"]
                - row["clv_hit_rate_baseline"],
            )
        )
    return "\n".join(lines)


def _format_clv_audit_comparison(baseline: pd.DataFrame, production: pd.DataFrame) -> str:
    baseline_row = baseline.iloc[0].to_dict()
    production_row = production.iloc[0].to_dict()
    lines = [
        "| Model | Bets | Explicit open | Explicit close | Proxy close | Avg snapshots | CLV hit | Avg CLV delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| Baseline | {bet_count:.0f} | {explicit_open_rate:.3%} | {explicit_close_rate:.3%} | "
        "{proxy_close_rate:.3%} | {avg_snapshots_per_bet:.2f} | {clv_hit_rate:.3%} | "
        "{avg_clv_decimal_delta:+.4f} |".format(**baseline_row),
        "| Production | {bet_count:.0f} | {explicit_open_rate:.3%} | {explicit_close_rate:.3%} | "
        "{proxy_close_rate:.3%} | {avg_snapshots_per_bet:.2f} | {clv_hit_rate:.3%} | "
        "{avg_clv_decimal_delta:+.4f} |".format(**production_row),
    ]
    return "\n".join(lines)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate MLB betting ROI/CLV evidence using free historical odds."
    )
    parser.add_argument(
        "--games-csv",
        default=str(ROOT / "mlb_backtest_data" / "mlb_games.csv"),
        help="Historical MLB game-results CSV.",
    )
    parser.add_argument(
        "--odds-file",
        required=True,
        help="Free historical odds file (.csv/.xlsx Princeton-style or .json SportsBookReview-style).",
    )
    parser.add_argument(
        "--bookmaker",
        default="draftkings",
        help="Bookmaker key to evaluate for multi-book JSON sources, or 'all'. Ignored for consensus CSV/XLSX sources.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON in addition to the text summary.",
    )
    args = parser.parse_args()

    games = load_mlb_games_csv(args.games_csv)
    snapshots = _load_snapshots(args.odds_file)
    production_predictions = run_elo_backtest(games, PRODUCTION_TUNED_CONFIG)
    baseline_predictions = run_elo_backtest(games, LEGACY_REGULAR_SEASON_CONFIG)

    print("\nMLB BETTING EVIDENCE")
    print(f"Games source: {args.games_csv}")
    print(f"Odds source: {args.odds_file}")
    if "bookmaker_key" in snapshots.columns and args.bookmaker == "all":
        rows: list[dict[str, object]] = []
        for bookmaker in sorted(snapshots["bookmaker_key"].dropna().astype(str).unique()):
            bookmaker_snapshots = snapshots[snapshots["bookmaker_key"] == bookmaker]
            baseline_recs = build_value_recommendations(
                baseline_predictions, bookmaker_snapshots
            )
            production_recs = build_value_recommendations(
                production_predictions, bookmaker_snapshots
            )
            baseline_metrics = compute_betting_evidence_metrics(
                recommendations=baseline_recs,
                odds_snapshots=bookmaker_snapshots,
                games=games,
            )
            production_metrics = compute_betting_evidence_metrics(
                recommendations=production_recs,
                odds_snapshots=bookmaker_snapshots,
                games=games,
            )
            rows.append(
                {
                    "bookmaker": bookmaker,
                    "base_bets": baseline_metrics.bet_count,
                    "base_roi": baseline_metrics.flat_roi,
                    "base_clv": baseline_metrics.clv_hit_rate,
                    "prod_bets": production_metrics.bet_count,
                    "prod_roi": production_metrics.flat_roi,
                    "prod_clv": production_metrics.clv_hit_rate,
                    "roi_delta": production_metrics.flat_roi
                    - baseline_metrics.flat_roi,
                    "clv_delta": production_metrics.clv_hit_rate
                    - baseline_metrics.clv_hit_rate,
                    "prod_tier_a_roi": production_metrics.tier_a_roi,
                }
            )
        print("\nBookmaker comparison:")
        print(_format_bookmaker_table(rows))
        if args.json:
            print(json.dumps({"bookmakers": rows}, indent=2, sort_keys=True))
        return 0

    if "bookmaker_key" in snapshots.columns and args.bookmaker:
        filtered = snapshots[snapshots["bookmaker_key"] == args.bookmaker]
        if not filtered.empty:
            snapshots = filtered

    if args.bookmaker:
        print(f"Bookmaker: {args.bookmaker}")

    production_recs = build_value_recommendations(production_predictions, snapshots)
    baseline_recs = build_value_recommendations(baseline_predictions, snapshots)
    production_metrics = compute_betting_evidence_metrics(
        recommendations=production_recs,
        odds_snapshots=snapshots,
        games=games,
    )
    baseline_metrics = compute_betting_evidence_metrics(
        recommendations=baseline_recs,
        odds_snapshots=snapshots,
        games=games,
    )
    production_frame = build_betting_evidence_frame(
        recommendations=production_recs,
        odds_snapshots=snapshots,
        games=games,
    )
    baseline_frame = build_betting_evidence_frame(
        recommendations=baseline_recs,
        odds_snapshots=snapshots,
        games=games,
    )

    print(_format_metrics("Baseline", baseline_metrics))
    print(_format_metrics("Production", production_metrics))
    print(
        "Delta: "
        f"bet_count={production_metrics.bet_count - baseline_metrics.bet_count:+d}, "
        f"flat_roi={production_metrics.flat_roi - baseline_metrics.flat_roi:+.3%}, "
        f"clv_hit_rate={production_metrics.clv_hit_rate - baseline_metrics.clv_hit_rate:+.3%}, "
        f"tier_a_roi={production_metrics.tier_a_roi - baseline_metrics.tier_a_roi:+.3%}"
    )

    print("\nEdge-bucket comparison:")
    print(
        _format_edge_bucket_comparison(
            summarize_betting_evidence_by_edge_bucket(baseline_frame),
            summarize_betting_evidence_by_edge_bucket(production_frame),
        )
    )
    print("\nCLV snapshot audit:")
    print(
        _format_clv_audit_comparison(
            audit_clv_snapshot_fidelity(baseline_frame),
            audit_clv_snapshot_fidelity(production_frame),
        )
    )

    if args.json:
        payload = {
            "baseline": baseline_metrics.to_dict(),
            "production": production_metrics.to_dict(),
            "edge_buckets": {
                "baseline": summarize_betting_evidence_by_edge_bucket(
                    baseline_frame
                ).to_dict(orient="records"),
                "production": summarize_betting_evidence_by_edge_bucket(
                    production_frame
                ).to_dict(orient="records"),
            },
            "clv_audit": {
                "baseline": audit_clv_snapshot_fidelity(baseline_frame).to_dict(
                    orient="records"
                ),
                "production": audit_clv_snapshot_fidelity(production_frame).to_dict(
                    orient="records"
                ),
            },
            "delta": {
                "bet_count": production_metrics.bet_count - baseline_metrics.bet_count,
                "flat_roi": production_metrics.flat_roi - baseline_metrics.flat_roi,
                "clv_hit_rate": production_metrics.clv_hit_rate
                - baseline_metrics.clv_hit_rate,
                "tier_a_roi": production_metrics.tier_a_roi - baseline_metrics.tier_a_roi,
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
