#!/usr/bin/env python3
"""
Expected Value (EV) Accuracy Report

This module analyzes the accuracy of our expected value predictions by comparing
predicted EV to actual returns from settled bets.

Key Metrics:
- Predicted EV vs Actual ROI by sport
- EV calibration (are 10% EV bets returning ~10%?)
- Cumulative performance tracking
- Sport-specific accuracy breakdowns
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

sys.path.append(os.path.dirname(__file__))

from plugins.db_manager import default_db

import pandas as pd


# Configuration Constants
DEFAULT_ANALYSIS_DAYS = 90
DAG_ANALYSIS_DAYS = 30
DEFAULT_MIN_BETS_PER_BUCKET = 5
DEFAULT_MIN_BETS_PER_WEEK = 3
MIN_BETS_SPORT_CONFIDENCE = 3
CALIBRATION_ERROR_THRESHOLD = 0.05
REPORT_WIDTH = 70

# EV Bucket Ranges: 0-5%, 5-10%, 10-15%, 15-20%, 20%+
EV_BUCKET_RANGES = [
    (0.0, 0.05),
    (0.05, 0.10),
    (0.10, 0.15),
    (0.15, 0.20),
    (0.20, 1.0),
]


@dataclass
class EVBucket:
    """Statistics for a bucket of EV predictions."""

    ev_range_min: float
    ev_range_max: float
    num_bets: int
    total_staked: float
    total_return: float
    actual_roi: float
    predicted_ev: float
    calibration_error: float  # predicted_ev - actual_roi


def _query_settled_bets_with_ev(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Query settled bets with EV data from database.

    Args:
        start_date: Start date for query (YYYY-MM-DD)
        end_date: End date for query (YYYY-MM-DD)

    Returns:
        DataFrame with settled bets and EV data
    """
    query = """
        SELECT
            sport,
            placed_date,
            ticker,
            cost_dollars,
            payout_dollars,
            profit_dollars,
            elo_prob,
            market_prob,
            edge,
            expected_value,
            kelly_fraction,
            confidence,
            status
        FROM placed_bets
        WHERE placed_date >= :start_date
          AND placed_date <= :end_date
          AND status IN ('won', 'lost', 'settled')
          AND cost_dollars > 0
          AND expected_value IS NOT NULL
        ORDER BY placed_date
    """

    return default_db.fetch_df(query, {"start_date": start_date, "end_date": end_date})


def _calculate_basic_statistics(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate basic statistics from settled bets DataFrame.

    Args:
        df: DataFrame with settled bets

    Returns:
        Dictionary with basic statistics
    """
    total_staked = df["cost_dollars"].sum()
    total_profit = df["profit_dollars"].sum()

    return {
        "total_bets": len(df),
        "total_staked": total_staked,
        "total_return": df["payout_dollars"].sum(),
        "total_profit": total_profit,
        "overall_roi": total_profit / total_staked if total_staked > 0 else 0,
        "avg_predicted_ev": df["expected_value"].mean(),
    }


def _analyze_by_sport(df: pd.DataFrame, min_bets: int) -> Dict[str, Dict]:
    """
    Analyze EV accuracy by sport.

    Args:
        df: DataFrame with settled bets
        min_bets: Minimum bets required per sport

    Returns:
        Dictionary with sport analysis results
    """
    sport_analysis = {}

    for sport, sport_df in df.groupby("sport"):
        if len(sport_df) < min_bets:
            continue

        total_staked = sport_df["cost_dollars"].sum()
        total_profit = sport_df["profit_dollars"].sum()

        sport_analysis[sport] = {
            "num_bets": len(sport_df),
            "total_staked": total_staked,
            "total_profit": total_profit,
            "actual_roi": total_profit / total_staked if total_staked > 0 else 0,
            "avg_predicted_ev": sport_df["expected_value"].mean(),
            "win_rate": (sport_df["status"] == "won").sum() / len(sport_df),
            "avg_elo_prob": sport_df["elo_prob"].mean(),
        }

        # Calculate calibration error (predicted - actual)
        sport_analysis[sport]["calibration_error"] = (
            sport_analysis[sport]["avg_predicted_ev"]
            - sport_analysis[sport]["actual_roi"]
        )

    return sport_analysis


def _analyze_ev_buckets(df: pd.DataFrame, min_bets: int) -> List[EVBucket]:
    """
    Analyze EV accuracy by EV buckets.

    Args:
        df: DataFrame with settled bets
        min_bets: Minimum bets required per bucket

    Returns:
        List of EVBucket objects
    """
    ev_buckets = []
    # Create 5 buckets using predefined ranges
    for ev_min, ev_max in EV_BUCKET_RANGES:
        bucket_df = df[
            (df["expected_value"] >= ev_min) & (df["expected_value"] < ev_max)
        ]

        if len(bucket_df) >= min_bets:
            staked = bucket_df["cost_dollars"].sum()
            profit = bucket_df["profit_dollars"].sum()
            actual_roi = profit / staked if staked > 0 else 0
            predicted_ev = bucket_df["expected_value"].mean()

            ev_buckets.append(
                EVBucket(
                    ev_range_min=ev_min,
                    ev_range_max=ev_max,
                    num_bets=len(bucket_df),
                    total_staked=staked,
                    total_return=bucket_df["payout_dollars"].sum(),
                    actual_roi=actual_roi,
                    predicted_ev=predicted_ev,
                    calibration_error=predicted_ev - actual_roi,
                )
            )

    return ev_buckets


def _calculate_calibration_metrics(ev_buckets: List[EVBucket]) -> Dict[str, Any]:
    """
    Calculate calibration metrics from EV buckets.

    Args:
        ev_buckets: List of EVBucket objects

    Returns:
        Dictionary with calibration metrics
    """
    if not ev_buckets:
        return {}

    return {
        "mean_abs_error": sum(abs(b.calibration_error) for b in ev_buckets)
        / len(ev_buckets),
        "is_overconfident": sum(b.calibration_error for b in ev_buckets) > 0,
        "best_calibrated_bucket": min(
            ev_buckets, key=lambda b: abs(b.calibration_error)
        ).ev_range_min,
    }


def _analyze_weekly_trend(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Analyze weekly performance trend.

    Args:
        df: DataFrame with settled bets

    Returns:
        List of weekly performance dictionaries
    """
    df["week"] = pd.to_datetime(df["placed_date"]).dt.to_period("W").astype(str)
    weekly_perf = []

    for week, week_df in df.groupby("week"):
        if len(week_df) >= DEFAULT_MIN_BETS_PER_WEEK:  # At least N bets per week
            total_staked = week_df["cost_dollars"].sum()
            total_profit = week_df["profit_dollars"].sum()

            weekly_perf.append(
                {
                    "week": week,
                    "num_bets": len(week_df),
                    "staked": total_staked,
                    "profit": total_profit,
                    "roi": total_profit / total_staked if total_staked > 0 else 0,
                    "avg_ev": week_df["expected_value"].mean(),
                }
            )

    return weekly_perf


def _analyze_by_confidence(df: pd.DataFrame, min_bets: int) -> Dict[str, Dict]:
    """
    Analyze EV accuracy by confidence level.

    Args:
        df: DataFrame with settled bets
        min_bets: Minimum bets required per confidence level

    Returns:
        Dictionary with confidence analysis results
    """
    confidence_analysis = {}

    # Handle None/NaN in confidence column
    df_clean = df.copy()
    df_clean["confidence"] = df_clean["confidence"].fillna("UNKNOWN").str.upper()

    for confidence, conf_df in df_clean.groupby("confidence"):
        if len(conf_df) < min_bets:
            continue

        total_staked = conf_df["cost_dollars"].sum()
        total_profit = conf_df["profit_dollars"].sum()

        confidence_analysis[confidence] = {
            "num_bets": len(conf_df),
            "total_staked": total_staked,
            "total_profit": total_profit,
            "actual_roi": total_profit / total_staked if total_staked > 0 else 0,
            "avg_predicted_ev": conf_df["expected_value"].mean(),
            "win_rate": (conf_df["status"] == "won").sum() / len(conf_df),
        }

        # Calculate calibration error (predicted - actual)
        confidence_analysis[confidence]["calibration_error"] = (
            confidence_analysis[confidence]["avg_predicted_ev"]
            - confidence_analysis[confidence]["actual_roi"]
        )

    return confidence_analysis


def _analyze_by_sport_confidence(
    df: pd.DataFrame, min_bets: int
) -> Dict[str, Dict[str, Dict]]:
    """
    Analyze EV accuracy by sport and confidence level.

    Args:
        df: DataFrame with settled bets
        min_bets: Minimum bets required per group

    Returns:
        Dictionary mapping sport -> confidence -> stats
    """
    analysis = {}

    # Handle None/NaN in confidence column
    df_clean = df.copy()
    df_clean["confidence"] = df_clean["confidence"].fillna("UNKNOWN").str.upper()

    for (sport, confidence), group_df in df_clean.groupby(["sport", "confidence"]):
        if len(group_df) < min_bets:
            continue

        if sport not in analysis:
            analysis[sport] = {}

        total_staked = group_df["cost_dollars"].sum()
        total_profit = group_df["profit_dollars"].sum()

        analysis[sport][confidence] = {
            "num_bets": len(group_df),
            "total_staked": total_staked,
            "total_profit": total_profit,
            "actual_roi": total_profit / total_staked if total_staked > 0 else 0,
            "avg_predicted_ev": group_df["expected_value"].mean(),
        }

    return analysis


def _build_analysis_results(
    df: pd.DataFrame, start_date: str, end_date: str, min_bets: int
) -> Dict:
    """
    Build the analysis results dictionary from the DataFrame.

    Args:
        df: DataFrame with settled bets
        start_date: Start date for analysis
        end_date: End date for analysis
        min_bets: Minimum bets required per bucket

    Returns:
        Dictionary with comprehensive EV accuracy analysis
    """
    # Calculate actual ROI for each bet
    df["actual_roi"] = df["profit_dollars"] / df["cost_dollars"]

    # Build results dictionary
    results = {
        "start_date": start_date,
        "end_date": end_date,
        **_calculate_basic_statistics(df),
    }

    # Analyze by sport
    results["by_sport"] = _analyze_by_sport(df, min_bets)

    # Analyze by confidence
    results["by_confidence"] = _analyze_by_confidence(df, min_bets)

    # Analyze by sport + confidence
    results["by_sport_confidence"] = _analyze_by_sport_confidence(
        df, MIN_BETS_SPORT_CONFIDENCE
    )

    # Analyze by EV buckets
    ev_buckets = _analyze_ev_buckets(df, min_bets)
    results["ev_buckets"] = [
        {
            "range": f"{b.ev_range_min:.0%}-{b.ev_range_max:.0%}",
            "num_bets": b.num_bets,
            "total_staked": b.total_staked,
            "actual_roi": b.actual_roi,
            "predicted_ev": b.predicted_ev,
            "calibration_error": b.calibration_error,
        }
        for b in ev_buckets
    ]

    # Calculate calibration metrics
    calibration_metrics = _calculate_calibration_metrics(ev_buckets)
    if calibration_metrics:
        results["calibration"] = calibration_metrics

    # Analyze weekly trend
    results["weekly_trend"] = _analyze_weekly_trend(df)

    return results


def analyze_ev_accuracy(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_bets: int = DEFAULT_MIN_BETS_PER_BUCKET,
) -> Dict:
    """
    Analyze EV prediction accuracy over settled bets.

    Args:
        start_date: Start date for analysis (YYYY-MM-DD)
        end_date: End date for analysis (YYYY-MM-DD)
        min_bets: Minimum bets required per bucket

    Returns:
        Dictionary with comprehensive EV accuracy analysis
    """
    # Default to last N days
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=DEFAULT_ANALYSIS_DAYS)).strftime(
            "%Y-%m-%d"
        )

    # Query settled bets with EV data
    df = _query_settled_bets_with_ev(start_date, end_date)

    if df.empty:
        return {
            "status": "no_data",
            "message": "No settled bets with EV data found in date range",
            "start_date": start_date,
            "end_date": end_date,
        }

    return _build_analysis_results(df, start_date, end_date, min_bets)


def compare_ev_vs_clv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict:
    """
    Compare EV predictions to CLV (Closing Line Value).

    This helps validate whether EV predictions correlate with beating the closing line.

    Args:
        start_date: Start date for analysis
        end_date: End date for analysis

    Returns:
        Dictionary with EV vs CLV comparison
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=DEFAULT_ANALYSIS_DAYS)).strftime(
            "%Y-%m-%d"
        )

    query = """
        SELECT
            sport,
            placed_date,
            expected_value,
            clv,
            profit_dollars,
            cost_dollars,
            status
        FROM placed_bets
        WHERE placed_date >= :start_date
          AND placed_date <= :end_date
          AND status IN ('won', 'lost', 'settled')
          AND expected_value IS NOT NULL
          AND clv IS NOT NULL
          AND cost_dollars > 0
    """

    df = default_db.fetch_df(query, {"start_date": start_date, "end_date": end_date})

    if df.empty:
        return {
            "status": "no_data",
            "message": "No bets with both EV and CLV data found",
        }

    # Correlation between EV and CLV
    correlation = df["expected_value"].corr(df["clv"])

    # Split by positive/negative CLV
    positive_clv = df[df["clv"] > 0]
    negative_clv = df[df["clv"] <= 0]

    results = {
        "start_date": start_date,
        "end_date": end_date,
        "total_bets": len(df),
        "ev_clv_correlation": correlation,
        "positive_clv_bets": {
            "count": len(positive_clv),
            "avg_ev": (
                positive_clv["expected_value"].mean() if len(positive_clv) > 0 else 0
            ),
            "avg_clv": positive_clv["clv"].mean() if len(positive_clv) > 0 else 0,
            "total_profit": positive_clv["profit_dollars"].sum(),
            "roi": (
                positive_clv["profit_dollars"].sum()
                / positive_clv["cost_dollars"].sum()
                if positive_clv["cost_dollars"].sum() > 0
                else 0
            ),
        },
        "negative_clv_bets": {
            "count": len(negative_clv),
            "avg_ev": (
                negative_clv["expected_value"].mean() if len(negative_clv) > 0 else 0
            ),
            "avg_clv": negative_clv["clv"].mean() if len(negative_clv) > 0 else 0,
            "total_profit": negative_clv["profit_dollars"].sum(),
            "roi": (
                negative_clv["profit_dollars"].sum()
                / negative_clv["cost_dollars"].sum()
                if negative_clv["cost_dollars"].sum() > 0
                else 0
            ),
        },
    }

    return results


def _print_header(results: Dict) -> None:
    """Print the report header and basic summary."""
    print(f"\n{'=' * REPORT_WIDTH}")
    print("EXPECTED VALUE ACCURACY REPORT")
    print(f"{'=' * REPORT_WIDTH}")
    print(f"Period: {results['start_date']} to {results['end_date']}")
    print(f"Total Bets: {results['total_bets']}")
    print(f"Total Staked: ${results['total_staked']:,.2f}")
    print(f"Total Profit: ${results['total_profit']:,.2f}")
    print(f"Overall ROI: {results['overall_roi']:.2%}")
    print(f"Avg Predicted EV: {results['avg_predicted_ev']:.2%}")


def _print_calibration(results: Dict) -> None:
    """Print calibration summary if available."""
    if "calibration" in results:
        cal = results["calibration"]
        print(f"\nCalibration:")
        print(f"  Mean Abs Error: {cal['mean_abs_error']:.2%}")
        status = "⚠️ OVERCONFIDENT" if cal["is_overconfident"] else "✅ Conservative"
        print(f"  Status: {status}")


def _print_sport_breakdown(results: Dict) -> None:
    """Print performance breakdown by sport."""
    if results.get("by_sport"):
        print(f"\n{'─' * REPORT_WIDTH}")
        print("BY SPORT:")
        print(f"{'─' * REPORT_WIDTH}")
        print(
            f"{'Sport':8} {'Bets':>6} {'Staked':>10} {'Profit':>10} "
            f"{'ROI':>8} {'Pred EV':>8} {'Cal Err':>8}"
        )
        print("─" * REPORT_WIDTH)

        for sport, data in sorted(results["by_sport"].items()):
            roi_color = "✅" if data["actual_roi"] > 0 else "❌"
            print(
                f"{sport:8} {data['num_bets']:>6} ${data['total_staked']:>9,.2f} "
                f"${data['total_profit']:>9,.2f} {data['actual_roi']:>7.1%} "
                f"{data['avg_predicted_ev']:>7.1%} {data['calibration_error']:>+7.1%} {roi_color}"
            )


def _print_confidence_breakdown(results: Dict) -> None:
    """Print performance breakdown by confidence level."""
    if results.get("by_confidence"):
        print(f"\n{'─' * REPORT_WIDTH}")
        print("BY CONFIDENCE:")
        print(f"{'─' * REPORT_WIDTH}")
        print(
            f"{'Conf':12} {'Bets':>6} {'Staked':>10} {'Profit':>10} "
            f"{'ROI':>8} {'Pred EV':>8} {'Cal Err':>8}"
        )
        print("─" * REPORT_WIDTH)

        # Order by common confidence labels
        order = ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
        sorted_conf = sorted(
            results["by_confidence"].items(),
            key=lambda x: order.index(x[0]) if x[0] in order else 99,
        )

        for conf, data in sorted_conf:
            roi_color = "✅" if data["actual_roi"] > 0 else "❌"
            print(
                f"{conf:12} {data['num_bets']:>6} ${data['total_staked']:>9,.2f} "
                f"${data['total_profit']:>9,.2f} {data['actual_roi']:>7.1%} "
                f"{data['avg_predicted_ev']:>7.1%} {data['calibration_error']:>+7.1%} {roi_color}"
            )


def _print_sport_confidence_breakdown(results: Dict) -> None:
    """Print performance breakdown by sport and confidence level."""
    if results.get("by_sport_confidence"):
        print(f"\n{'─' * REPORT_WIDTH}")
        print("BY SPORT + CONFIDENCE:")
        print(f"{'─' * REPORT_WIDTH}")
        print(
            f"{'Sport':8} {'Conf':10} {'Bets':>6} {'Staked':>10} {'Profit':>10} "
            f"{'ROI':>8}"
        )
        print("─" * REPORT_WIDTH)

        for sport in sorted(results["by_sport_confidence"].keys()):
            for conf, data in sorted(results["by_sport_confidence"][sport].items()):
                roi_color = "✅" if data["actual_roi"] > 0 else "❌"
                print(
                    f"{sport:8} {conf:10} {data['num_bets']:>6} ${data['total_staked']:>9,.2f} "
                    f"${data['total_profit']:>9,.2f} {data['actual_roi']:>7.1%} {roi_color}"
                )


def _print_ev_buckets(results: Dict) -> None:
    """Print performance breakdown by predicted EV bucket."""
    if results.get("ev_buckets"):
        print(f"\n{'─' * REPORT_WIDTH}")
        print("BY PREDICTED EV BUCKET:")
        print(f"{'─' * REPORT_WIDTH}")
        print(
            f"{'Range':12} {'Bets':>6} {'Staked':>10} {'Act ROI':>10} "
            f"{'Pred EV':>10} {'Cal Err':>10}"
        )
        print("─" * REPORT_WIDTH)

        for bucket in results["ev_buckets"]:
            cal_status = (
                "✅"
                if abs(bucket["calibration_error"]) < CALIBRATION_ERROR_THRESHOLD
                else "⚠️"
            )
            print(
                f"{bucket['range']:12} {bucket['num_bets']:>6} "
                f"${bucket['total_staked']:>9,.2f} {bucket['actual_roi']:>9.1%} "
                f"{bucket['predicted_ev']:>9.1%} {bucket['calibration_error']:>+9.1%} {cal_status}"
            )


def _print_weekly_trend(results: Dict) -> None:
    """Print weekly performance trend for the last 8 weeks."""
    if results.get("weekly_trend"):
        print(f"\n{'─' * REPORT_WIDTH}")
        print("WEEKLY TREND (Last 8 weeks):")
        print(f"{'─' * REPORT_WIDTH}")

        for week_data in results["weekly_trend"][-8:]:
            roi_bar = "█" * min(int(abs(week_data["roi"]) * 50), 20)
            direction = "+" if week_data["roi"] > 0 else "-"
            print(
                f"{week_data['week']}: {week_data['num_bets']:>3} bets, "
                f"${week_data['staked']:>6.0f} staked, "
                f"ROI: {week_data['roi']:>+6.1%} {direction}{roi_bar}"
            )


def print_ev_report(results: Dict) -> None:
    """Print formatted EV accuracy report."""
    if results.get("status") == "no_data":
        print(f"❌ {results.get('message')}")
        return

    _print_header(results)
    _print_calibration(results)
    _print_sport_breakdown(results)
    _print_confidence_breakdown(results)
    _print_sport_confidence_breakdown(results)
    _print_ev_buckets(results)
    _print_weekly_trend(results)

    print(f"\n{'=' * REPORT_WIDTH}\n")


def generate_ev_report_for_dag(**context) -> Dict:
    """
    Generate EV report for Airflow DAG integration.

    Returns the analysis results for downstream tasks.
    """
    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))

    # Analyze last N days
    start_date = (
        datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=DAG_ANALYSIS_DAYS)
    ).strftime("%Y-%m-%d")

    results = analyze_ev_accuracy(start_date=start_date, end_date=date_str)
    print_ev_report(results)

    # Also compare with CLV
    clv_comparison = compare_ev_vs_clv(start_date=start_date, end_date=date_str)
    if clv_comparison.get("status") != "no_data":
        print("\n📊 EV vs CLV Correlation:")
        print(f"  Correlation: {clv_comparison['ev_clv_correlation']:.3f}")
        print(
            f"  Positive CLV bets: {clv_comparison['positive_clv_bets']['count']} "
            f"(ROI: {clv_comparison['positive_clv_bets']['roi']:.1%})"
        )
        print(
            f"  Negative CLV bets: {clv_comparison['negative_clv_bets']['count']} "
            f"(ROI: {clv_comparison['negative_clv_bets']['roi']:.1%})"
        )

    return results


def main():
    """Run EV accuracy analysis."""
    print("Analyzing EV accuracy over last 90 days...")
    results = analyze_ev_accuracy()
    print_ev_report(results)

    # Also show CLV comparison
    print("\n📊 EV vs CLV Analysis:")
    clv_results = compare_ev_vs_clv()
    if clv_results.get("status") != "no_data":
        print(f"  Correlation: {clv_results['ev_clv_correlation']:.3f}")
        print(
            f"  +CLV: {clv_results['positive_clv_bets']['count']} bets, "
            f"ROI: {clv_results['positive_clv_bets']['roi']:.1%}"
        )
        print(
            f"  -CLV: {clv_results['negative_clv_bets']['count']} bets, "
            f"ROI: {clv_results['negative_clv_bets']['roi']:.1%}"
        )
    else:
        print(f"  {clv_results.get('message')}")


if __name__ == "__main__":
    main()
