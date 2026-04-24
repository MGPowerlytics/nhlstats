#!/usr/bin/env python3
"""
Analyze betting segments from PostgreSQL database.
Generates performance reports by sport and confidence level.
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))
from db_manager import default_db


def get_segment_performance(days_back=30):
    """
    Get performance by sport and confidence segment.

    Args:
        days_back: Number of days to analyze (default: 30)

    Returns:
        DataFrame with segment performance
    """
    query = f"""
    SELECT
        sport,
        confidence,
        COUNT(*) as total_bets,
        SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) as losses,
        SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_bets,
        SUM(cost_dollars) as total_wagered,
        SUM(profit_dollars) as total_profit,
        ROUND((SUM(profit_dollars) / NULLIF(SUM(cost_dollars), 0) * 100)::numeric, 2) as roi_pct,
        ROUND((AVG(CASE WHEN status IN ('won', 'lost') THEN
            CASE WHEN status = 'won' THEN 1.0 ELSE 0.0 END
            ELSE NULL END) * 100)::numeric, 2) as win_pct
    FROM placed_bets
    WHERE sport IS NOT NULL
      AND placed_date >= CURRENT_DATE - {days_back}
    GROUP BY sport, confidence
    ORDER BY sport,
        CASE confidence
            WHEN 'HIGH' THEN 1
            WHEN 'MEDIUM' THEN 2
            WHEN 'LOW' THEN 3
            ELSE 4
        END
    """

    return default_db.fetch_df(query)


def get_worst_segments(df, min_bets=5):
    """
    Identify worst performing segments.

    Args:
        df: Segment performance DataFrame
        min_bets: Minimum number of settled bets to consider

    Returns:
        DataFrame with worst segments
    """
    # Filter for segments with enough settled bets
    settled_mask = (df["total_bets"] - df["open_bets"]) >= min_bets
    settled_df = df[settled_mask].copy()

    # Sort by ROI (ascending = worst first)
    worst_df = settled_df.sort_values("roi_pct").head(10)

    return worst_df


def get_best_segments(df, min_bets=5):
    """
    Identify best performing segments.

    Args:
        df: Segment performance DataFrame
        min_bets: Minimum number of settled bets to consider

    Returns:
        DataFrame with best segments
    """
    # Filter for segments with enough settled bets and positive profit
    settled_mask = (df["total_bets"] - df["open_bets"]) >= min_bets
    profitable_mask = df["total_profit"] > 0

    best_df = df[settled_mask & profitable_mask].copy()
    best_df = best_df.sort_values("roi_pct", ascending=False).head(10)

    return best_df


def analyze_strategy_impact(excluded_segments):
    """
    Analyze impact of excluding specific segments.

    Args:
        excluded_segments: List of (sport, confidence) tuples to exclude

    Returns:
        Dictionary with strategy performance metrics
    """
    # Get all settled bets
    query = """
    SELECT
        sport,
        confidence,
        cost_dollars,
        profit_dollars,
        status
    FROM placed_bets
    WHERE status IN ('won', 'lost')
      AND sport IS NOT NULL
      AND confidence IS NOT NULL
    """

    all_bets = default_db.fetch_df(query)

    # Filter out excluded segments
    filtered_bets = all_bets.copy()
    for sport, confidence in excluded_segments:
        mask = (filtered_bets["sport"] == sport) & (
            filtered_bets["confidence"] == confidence
        )
        filtered_bets = filtered_bets[~mask]

    # Calculate metrics
    if len(filtered_bets) > 0:
        total_wagered = filtered_bets["cost_dollars"].sum()
        total_profit = filtered_bets["profit_dollars"].sum()
        roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
        win_rate = (filtered_bets["status"] == "won").mean() * 100

        return {
            "bets": len(filtered_bets),
            "wagered": total_wagered,
            "profit": total_profit,
            "roi_pct": roi,
            "win_rate_pct": win_rate,
            "excluded_count": len(excluded_segments),
        }

    return None


def generate_report(days_back=30):
    """
    Generate comprehensive segment analysis report.

    Args:
        days_back: Number of days to analyze

    Returns:
        Dictionary with report data
    """
    print(f"Analyzing betting segments for last {days_back} days...")

    # Get segment performance
    segment_df = get_segment_performance(days_back)

    # Get worst and best segments
    worst_segments = get_worst_segments(segment_df, min_bets=5)
    best_segments = get_best_segments(segment_df, min_bets=5)

    # Define strategies to analyze
    strategies = {
        "ALL_BETS": [],
        "EXCLUDE_WORST_3": [("NHL", "MEDIUM"), ("NCAAB", "HIGH"), ("TENNIS", "HIGH")],
        "PROFITABLE_ONLY": [
            ("NHL", "MEDIUM"),
            ("NCAAB", "HIGH"),
            ("TENNIS", "HIGH"),
            ("TENNIS", "LOW"),
            ("NCAAB", "LOW"),
            ("TENNIS", "MEDIUM"),
            ("NBA", "LOW"),
        ],
    }

    # Analyze each strategy
    strategy_results = {}
    for strategy_name, excluded in strategies.items():
        result = analyze_strategy_impact(excluded)
        if result:
            strategy_results[strategy_name] = result

    # Compile report
    report = {
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "days_analyzed": days_back,
        "segment_performance": segment_df,
        "worst_segments": worst_segments,
        "best_segments": best_segments,
        "strategy_results": strategy_results,
        "total_bets": segment_df["total_bets"].sum() if not segment_df.empty else 0,
        "total_profit": segment_df["total_profit"].sum() if not segment_df.empty else 0,
    }

    return report


def print_report(report):
    """
    Print formatted report to console.

    Args:
        report: Report dictionary from generate_report()
    """
    print("\n" + "=" * 80)
    print(f"BETTING SEGMENT ANALYSIS REPORT")
    print(f"Date: {report['analysis_date']}")
    print(f"Analysis Period: Last {report['days_analyzed']} days")
    print("=" * 80)

    # Overall summary
    print(f"\nOVERALL SUMMARY")
    print(f"Total Bets: {report['total_bets']:,}")
    print(f"Total Profit: ${report['total_profit']:,.2f}")

    # Worst segments
    if not report["worst_segments"].empty:
        print(f"\nTOP 5 WORST PERFORMING SEGMENTS (min 5 settled bets)")
        print("-" * 80)
        for _, row in report["worst_segments"].head(5).iterrows():
            print(
                f"{row['sport']} {row['confidence']}: {row['total_bets']} bets, "
                f"ROI: {row['roi_pct']}%, Profit: ${row['total_profit']:,.2f}"
            )

    # Best segments
    if not report["best_segments"].empty:
        print(f"\nTOP 5 BEST PERFORMING SEGMENTS (min 5 settled bets)")
        print("-" * 80)
        for _, row in report["best_segments"].head(5).iterrows():
            print(
                f"{row['sport']} {row['confidence']}: {row['total_bets']} bets, "
                f"ROI: {row['roi_pct']}%, Profit: ${row['total_profit']:,.2f}"
            )

    # Strategy comparison
    if report["strategy_results"]:
        print(f"\nSTRATEGY COMPARISON")
        print("-" * 80)
        print(
            f"{'Strategy':<20} {'Bets':<8} {'Wagered':<12} {'Profit':<12} {'ROI':<8} {'Win Rate':<10}"
        )
        print("-" * 80)

        for strategy_name, result in report["strategy_results"].items():
            print(
                f"{strategy_name:<20} {result['bets']:<8} "
                f"${result['wagered']:<11.2f} ${result['profit']:<11.2f} "
                f"{result['roi_pct']:<7.2f}% {result['win_rate_pct']:<9.2f}%"
            )

    print("\n" + "=" * 80)
    print("Report complete.")


def main():
    """Main function to run analysis."""
    try:
        # Test database connection
        test_query = "SELECT COUNT(*) as bet_count FROM placed_bets"
        test_result = default_db.fetch_df(test_query)
        print(
            f"✓ Database connection successful. Bets in database: {test_result.iloc[0][0]}"
        )

        # Generate and print report
        report = generate_report(days_back=30)
        print_report(report)

        # Save detailed data to CSV
        output_dir = "/mnt/data2/nhlstats/reports"
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(output_dir, f"segment_analysis_{timestamp}.csv")
        report["segment_performance"].to_csv(csv_path, index=False)
        print(f"\n✓ Detailed data saved to: {csv_path}")

        return 0

    except Exception as e:
        print(f"✗ Error: {e}")
        return 1


if __name__ == "__main__":
    # Set POSTGRES_HOST environment variable if not set
    if "POSTGRES_HOST" not in os.environ:
        os.environ["POSTGRES_HOST"] = "localhost"

    sys.exit(main())
