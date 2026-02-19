#!/usr/bin/env python3
"""
Analyze bets placed since February 6, 2025.
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plugins'))
from db_manager import default_db


def get_bets_since_date(start_date='2025-02-06'):
    """
    Get all bets placed since the specified date.

    Args:
        start_date: Start date in YYYY-MM-DD format

    Returns:
        DataFrame with all bets
    """
    query = f"""
    SELECT
        *,
        CASE
            WHEN status = 'won' THEN 1
            WHEN status = 'lost' THEN 0
            ELSE NULL
        END as win_binary
    FROM placed_bets
    WHERE placed_date >= '{start_date}'
    ORDER BY placed_date
    """

    return default_db.fetch_df(query)


def calculate_summary_stats(df):
    """
    Calculate summary statistics for the betting data.

    Args:
        df: DataFrame with betting data

    Returns:
        Dictionary with summary statistics
    """
    # Filter for settled bets
    settled_df = df[df['status'].isin(['won', 'lost'])]

    # Calculate overall metrics
    total_bets = len(settled_df)
    won_bets = len(settled_df[settled_df['status'] == 'won'])
    lost_bets = len(settled_df[settled_df['status'] == 'lost'])
    open_bets = len(df[df['status'] == 'open'])

    total_wagered = settled_df['cost_dollars'].sum()
    total_profit = settled_df['profit_dollars'].sum()

    roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
    win_rate = (won_bets / total_bets * 100) if total_bets > 0 else 0

    return {
        'total_bets': len(df),
        'settled_bets': total_bets,
        'won_bets': won_bets,
        'lost_bets': lost_bets,
        'open_bets': open_bets,
        'total_wagered': total_wagered,
        'total_profit': total_profit,
        'roi_pct': roi,
        'win_rate_pct': win_rate,
        'avg_bet_size': settled_df['cost_dollars'].mean() if total_bets > 0 else 0
    }


def analyze_by_sport(df):
    """
    Analyze performance by sport.

    Args:
        df: DataFrame with betting data

    Returns:
        DataFrame with sport-level performance
    """
    # Filter for settled bets
    settled_df = df[df['status'].isin(['won', 'lost'])]

    if len(settled_df) == 0:
        return pd.DataFrame()

    # Group by sport
    sport_stats = settled_df.groupby('sport').agg({
        'bet_id': 'count',
        'cost_dollars': 'sum',
        'profit_dollars': 'sum',
        'win_binary': 'mean'
    }).reset_index()

    sport_stats.columns = ['sport', 'bets', 'wagered', 'profit', 'win_rate']

    # Calculate ROI
    sport_stats['roi_pct'] = (sport_stats['profit'] / sport_stats['wagered'] * 100).round(2)
    sport_stats['win_rate_pct'] = (sport_stats['win_rate'] * 100).round(2)

    # Add status indicator
    sport_stats['status'] = sport_stats['profit'].apply(lambda x: '✅ Profitable' if x > 0 else '❌ Unprofitable')

    # Sort by profit
    sport_stats = sport_stats.sort_values('profit', ascending=False)

    return sport_stats[['sport', 'bets', 'roi_pct', 'win_rate_pct', 'profit', 'status']]


def analyze_by_segment(df):
    """
    Analyze performance by sport and confidence segment.

    Args:
        df: DataFrame with betting data

    Returns:
        DataFrame with segment-level performance
    """
    # Filter for settled bets
    settled_df = df[df['status'].isin(['won', 'lost'])]

    if len(settled_df) == 0:
        return pd.DataFrame()

    # Group by sport and confidence
    segment_stats = settled_df.groupby(['sport', 'confidence']).agg({
        'bet_id': 'count',
        'cost_dollars': 'sum',
        'profit_dollars': 'sum',
        'win_binary': 'mean'
    }).reset_index()

    segment_stats.columns = ['sport', 'confidence', 'bets', 'wagered', 'profit', 'win_rate']

    # Calculate ROI
    segment_stats['roi_pct'] = (segment_stats['profit'] / segment_stats['wagered'] * 100).round(2)
    segment_stats['win_rate_pct'] = (segment_stats['win_rate'] * 100).round(2)

    # Create segment column
    segment_stats['segment'] = segment_stats['sport'] + ' ' + segment_stats['confidence']

    return segment_stats


def get_worst_segments(segment_df, min_bets=5):
    """
    Identify worst performing segments.

    Args:
        segment_df: DataFrame with segment performance
        min_bets: Minimum number of bets to consider

    Returns:
        DataFrame with worst segments
    """
    # Filter for segments with enough bets
    filtered = segment_df[segment_df['bets'] >= min_bets].copy()

    if len(filtered) == 0:
        return pd.DataFrame()

    # Sort by ROI (ascending = worst first)
    worst_df = filtered.sort_values('roi_pct').head(10)

    return worst_df[['segment', 'bets', 'roi_pct', 'win_rate_pct', 'profit']]


def get_best_segments(segment_df, min_bets=5):
    """
    Identify best performing segments.

    Args:
        segment_df: DataFrame with segment performance
        min_bets: Minimum number of bets to consider

    Returns:
        DataFrame with best segments
    """
    # Filter for segments with enough bets and positive profit
    filtered = segment_df[(segment_df['bets'] >= min_bets) & (segment_df['profit'] > 0)].copy()

    if len(filtered) == 0:
        return pd.DataFrame()

    # Sort by ROI (descending = best first)
    best_df = filtered.sort_values('roi_pct', ascending=False).head(10)

    return best_df[['segment', 'bets', 'roi_pct', 'win_rate_pct', 'profit']]


def analyze_strategy_impact(df, excluded_segments):
    """
    Analyze impact of excluding specific segments.

    Args:
        df: DataFrame with all bets
        excluded_segments: List of (sport, confidence) tuples to exclude

    Returns:
        Dictionary with strategy performance metrics
    """
    # Filter for settled bets
    settled_df = df[df['status'].isin(['won', 'lost'])]

    # Filter out excluded segments
    filtered_df = settled_df.copy()
    for sport, confidence in excluded_segments:
        mask = (filtered_df['sport'] == sport) & (filtered_df['confidence'] == confidence)
        filtered_df = filtered_df[~mask]

    # Calculate metrics
    if len(filtered_df) > 0:
        total_wagered = filtered_df['cost_dollars'].sum()
        total_profit = filtered_df['profit_dollars'].sum()
        roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
        win_rate = (filtered_df['status'] == 'won').mean() * 100

        return {
            'bets': len(filtered_df),
            'wagered': total_wagered,
            'profit': total_profit,
            'roi_pct': roi,
            'win_rate_pct': win_rate,
            'excluded_count': len(excluded_segments)
        }

    return None


def generate_report(start_date='2025-02-06'):
    """
    Generate comprehensive betting analysis report.

    Args:
        start_date: Start date for analysis

    Returns:
        Dictionary with report data
    """
    print(f"Analyzing bets placed since {start_date}...")

    # Get all bets since start date
    all_bets = get_bets_since_date(start_date)

    if len(all_bets) == 0:
        print(f"No bets found since {start_date}")
        return None

    # Calculate summary statistics
    summary = calculate_summary_stats(all_bets)

    # Analyze by sport
    sport_stats = analyze_by_sport(all_bets)

    # Analyze by segment
    segment_stats = analyze_by_segment(all_bets)

    # Get worst and best segments
    worst_segments = get_worst_segments(segment_stats, min_bets=5)
    best_segments = get_best_segments(segment_stats, min_bets=5)

    # Define strategies to analyze (based on previous analysis)
    strategies = {
        'ALL_BETS': [],
        'EXCLUDE_WORST_3': [
            ('NHL', 'MEDIUM'),
            ('NCAAB', 'HIGH'),
            ('TENNIS', 'HIGH')
        ]
    }

    # Analyze each strategy
    strategy_results = {}
    for strategy_name, excluded in strategies.items():
        result = analyze_strategy_impact(all_bets, excluded)
        if result:
            strategy_results[strategy_name] = result

    # Compile report
    report = {
        'analysis_date': datetime.now().strftime('%Y-%m-%d'),
        'start_date': start_date,
        'summary': summary,
        'sport_stats': sport_stats,
        'segment_stats': segment_stats,
        'worst_segments': worst_segments,
        'best_segments': best_segments,
        'strategy_results': strategy_results,
        'total_bets': len(all_bets)
    }

    return report


def print_report(report):
    """
    Print formatted report to console.

    Args:
        report: Report dictionary
    """
    print("\n" + "="*80)
    print(f"ACTUAL BETTING ANALYSIS SUMMARY")
    print(f"Date: {report['analysis_date']}")
    print(f"Analysis Period: Since {report['start_date']}")
    print("="*80)

    # Overall summary
    summary = report['summary']
    print(f"\nEXECUTIVE SUMMARY")
    print(f"Total Bets: {summary['total_bets']} ({summary['settled_bets']} settled, {summary['open_bets']} open)")
    print(f"Won/Lost: {summary['won_bets']}/{summary['lost_bets']}")
    print(f"Total Wagered: ${summary['total_wagered']:.2f}")
    print(f"Total Profit: ${summary['total_profit']:.2f}")
    print(f"Overall ROI: {summary['roi_pct']:.2f}%")
    print(f"Win Rate: {summary['win_rate_pct']:.2f}%")
    print(f"Average Bet Size: ${summary['avg_bet_size']:.2f}")

    # Performance by sport
    if not report['sport_stats'].empty:
        print(f"\nPERFORMANCE BY SPORT")
        print("-" * 80)
        print(f"{'Sport':<10} {'Bets':<6} {'ROI':<8} {'Win Rate':<10} {'Profit':<12} {'Status':<15}")
        print("-" * 80)

        for _, row in report['sport_stats'].iterrows():
            print(f"{row['sport']:<10} {row['bets']:<6} {row['roi_pct']:<7.2f}% {row['win_rate_pct']:<9.2f}% ${row['profit']:<11.2f} {row['status']:<15}")

    # Worst segments
    if not report['worst_segments'].empty:
        print(f"\nTOP PROBLEMATIC SEGMENTS (min 5 bets)")
        print("-" * 80)
        print(f"{'Segment':<20} {'Bets':<6} {'ROI':<8} {'Win Rate':<10} {'Loss':<12}")
        print("-" * 80)

        for _, row in report['worst_segments'].head(5).iterrows():
            print(f"{row['segment']:<20} {row['bets']:<6} {row['roi_pct']:<7.2f}% {row['win_rate_pct']:<9.2f}% ${row['profit']:<11.2f}")

    # Best segments
    if not report['best_segments'].empty:
        print(f"\nTOP PROFITABLE SEGMENTS (min 5 bets)")
        print("-" * 80)
        print(f"{'Segment':<20} {'Bets':<6} {'ROI':<8} {'Win Rate':<10} {'Profit':<12}")
        print("-" * 80)

        for _, row in report['best_segments'].head(5).iterrows():
            print(f"{row['segment']:<20} {row['bets']:<6} {row['roi_pct']:<7.2f}% {row['win_rate_pct']:<9.2f}% ${row['profit']:<11.2f}")

    # Strategy comparison
    if report['strategy_results']:
        print(f"\nSTRATEGY COMPARISON")
        print("-" * 80)
        print(f"{'Strategy':<20} {'Bets':<8} {'Wagered':<12} {'Profit':<12} {'ROI':<8} {'Win Rate':<10}")
        print("-" * 80)

        for strategy_name, result in report['strategy_results'].items():
            print(f"{strategy_name:<20} {result['bets']:<8} "
                  f"${result['wagered']:<11.2f} ${result['profit']:<11.2f} "
                  f"{result['roi_pct']:<7.2f}% {result['win_rate_pct']:<9.2f}%")

    print("\n" + "="*80)
    print("Report complete.")


def main():
    """Main function to run analysis."""
    try:
        # Set environment variable for database connection
        os.environ['POSTGRES_HOST'] = 'localhost'
        os.environ['POSTGRES_USER'] = 'airflow'
        os.environ['POSTGRES_PASSWORD'] = 'airflow'
        os.environ['POSTGRES_DB'] = 'airflow'

        # Test database connection
        test_query = "SELECT COUNT(*) as bet_count FROM placed_bets"
        test_result = default_db.fetch_df(test_query)
        print(f"✓ Database connection successful. Total bets in database: {test_result.iloc[0][0]}")

        # Generate and print report
        report = generate_report(start_date='2025-02-06')

        if report:
            print_report(report)

            # Save report to file
            output_file = f"actual_betting_summary_{datetime.now().strftime('%Y%m%d')}.md"
            save_report_to_markdown(report, output_file)
            print(f"\n✓ Report saved to: {output_file}")

        return 0

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def save_report_to_markdown(report, filename):
    """
    Save report to markdown file.

    Args:
        report: Report dictionary
        filename: Output filename
    """
    with open(filename, 'w') as f:
        f.write(f"# Actual Betting Analysis Summary\n\n")
        f.write(f"**Date**: {report['analysis_date']}  \n")
        f.write(f"**Analysis Period**: Since {report['start_date']}  \n")
        f.write(f"**Data Source**: PostgreSQL `placed_bets` table ({report['summary']['total_bets']} actual bets)\n\n")

        f.write("---\n\n")

        f.write("## Executive Summary\n\n")
        summary = report['summary']
        f.write(f"### Current Performance\n")
        f.write(f"- **Total Bets**: {summary['total_bets']} ({summary['settled_bets']} settled, {summary['open_bets']} open)\n")
        f.write(f"- **Won/Lost**: {summary['won_bets']} won, {summary['lost_bets']} lost\n")
        f.write(f"- **Total Wagered**: ${summary['total_wagered']:.2f}\n")
        f.write(f"- **Total Profit**: ${summary['total_profit']:.2f}\n")
        f.write(f"- **Overall ROI**: {summary['roi_pct']:.2f}%\n")
        f.write(f"- **Win Rate**: {summary['win_rate_pct']:.2f}%\n")
        f.write(f"- **Average Bet Size**: ${summary['avg_bet_size']:.2f}\n\n")

        # Performance by sport
        if not report['sport_stats'].empty:
            f.write("## Performance by Sport\n\n")
            f.write("| Sport | Bets | ROI | Win Rate | Profit | Status |\n")
            f.write("|-------|------|-----|----------|--------|--------|\n")

            for _, row in report['sport_stats'].iterrows():
                status_emoji = "✅" if row['profit'] > 0 else "❌"
                f.write(f"| {row['sport']} | {row['bets']} | {row['roi_pct']:.2f}% | {row['win_rate_pct']:.2f}% | ${row['profit']:.2f} | {status_emoji} {'Profitable' if row['profit'] > 0 else 'Unprofitable'} |\n")

            f.write("\n")

        # Worst segments
        if not report['worst_segments'].empty:
            f.write("## Top Problematic Segments\n\n")
            f.write("| Rank | Segment | Bets | ROI | Win Rate | Loss |\n")
            f.write("|------|---------|------|-----|----------|------|\n")

            for i, (_, row) in enumerate(report['worst_segments'].head(5).iterrows(), 1):
                f.write(f"| {i} | {row['segment']} | {row['bets']} | {row['roi_pct']:.2f}% | {row['win_rate_pct']:.2f}% | ${row['profit']:.2f} |\n")

            f.write("\n")

        # Best segments
        if not report['best_segments'].empty:
            f.write("## Top Profitable Segments\n\n")
            f.write("| Rank | Segment | Bets | ROI | Win Rate | Profit |\n")
            f.write("|------|---------|------|-----|----------|--------|\n")

            for i, (_, row) in enumerate(report['best_segments'].head(5).iterrows(), 1):
                f.write(f"| {i} | {row['segment']} | {row['bets']} | {row['roi_pct']:.2f}% | {row['win_rate_pct']:.2f}% | ${row['profit']:.2f} |\n")

            f.write("\n")

        # Strategy comparison
        if report['strategy_results']:
            f.write("## Strategy Comparison\n\n")
            f.write("| Strategy | Bets | Wagered | Profit | ROI | Win Rate |\n")
            f.write("|----------|------|---------|--------|-----|----------|\n")

            for strategy_name, result in report['strategy_results'].items():
                f.write(f"| {strategy_name} | {result['bets']} | ${result['wagered']:.2f} | ${result['profit']:.2f} | {result['roi_pct']:.2f}% | {result['win_rate_pct']:.2f}% |\n")

            f.write("\n")

        f.write("---\n\n")
        f.write(f"*Analysis complete: {report['analysis_date']}*\n")
        f.write("*Based on actual PostgreSQL betting data*\n")


if __name__ == "__main__":
    sys.exit(main())
