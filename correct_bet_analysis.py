#!/usr/bin/env python3
"""
Correct analysis of bets placed since February 6, 2026.
"""

import sys
import os
import pandas as pd
from datetime import datetime

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plugins'))
from db_manager import DBManager

def get_bets_since_date(start_date='2026-02-06'):
    """Get all bets placed since the specified date."""
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

    return db.fetch_df(query)

def main():
    """Main function to run analysis."""
    try:
        # Create connection string for localhost
        connection_string = "postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
        global db
        db = DBManager(connection_string=connection_string)

        print("Analyzing bets placed since February 6, 2026...")

        # Get all bets since start date
        all_bets = get_bets_since_date('2026-02-06')

        if len(all_bets) == 0:
            print("No bets found since February 6, 2026")
            return 1

        print(f"Total bets found: {len(all_bets)}")

        # Filter for settled bets
        settled_bets = all_bets[all_bets['status'].isin(['won', 'lost'])]
        open_bets = all_bets[all_bets['status'] == 'open']

        print(f"\nSETTLED BETS: {len(settled_bets)}")
        print(f"OPEN BETS: {len(open_bets)}")

        if len(settled_bets) == 0:
            print("No settled bets to analyze")
            return 0

        # Calculate overall metrics
        total_wagered = settled_bets['cost_dollars'].sum()
        total_profit = settled_bets['profit_dollars'].sum()
        roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0

        won_bets = len(settled_bets[settled_bets['status'] == 'won'])
        lost_bets = len(settled_bets[settled_bets['status'] == 'lost'])
        win_rate = (won_bets / len(settled_bets) * 100) if len(settled_bets) > 0 else 0

        print(f"\nOVERALL PERFORMANCE:")
        print(f"Total Wagered: ${total_wagered:.2f}")
        print(f"Total Profit: ${total_profit:.2f}")
        print(f"ROI: {roi:.2f}%")
        print(f"Win Rate: {win_rate:.2f}% ({won_bets}/{len(settled_bets)})")

        # Analyze by sport
        print(f"\nPERFORMANCE BY SPORT:")
        sport_stats = settled_bets.groupby('sport').agg({
            'bet_id': 'count',
            'cost_dollars': 'sum',
            'profit_dollars': 'sum',
            'win_binary': 'mean'
        }).reset_index()

        sport_stats.columns = ['sport', 'bets', 'wagered', 'profit', 'win_rate']
        sport_stats['roi_pct'] = (sport_stats['profit'] / sport_stats['wagered'] * 100).round(2)
        sport_stats['win_rate_pct'] = (sport_stats['win_rate'] * 100).round(2)

        # Sort by profit
        sport_stats = sport_stats.sort_values('profit', ascending=False)

        for _, row in sport_stats.iterrows():
            status = "✅ Profitable" if row['profit'] > 0 else "❌ Unprofitable"
            print(f"{row['sport']}: {row['bets']} bets, ROI: {row['roi_pct']}%, "
                  f"Win Rate: {row['win_rate_pct']}%, Profit: ${row['profit']:.2f} {status}")

        # Analyze by segment (sport + confidence)
        print(f"\nPERFORMANCE BY SEGMENT (min 3 bets):")
        segment_stats = settled_bets.groupby(['sport', 'confidence']).agg({
            'bet_id': 'count',
            'cost_dollars': 'sum',
            'profit_dollars': 'sum',
            'win_binary': 'mean'
        }).reset_index()

        segment_stats.columns = ['sport', 'confidence', 'bets', 'wagered', 'profit', 'win_rate']
        segment_stats['roi_pct'] = (segment_stats['profit'] / segment_stats['wagered'] * 100).round(2)
        segment_stats['win_rate_pct'] = (segment_stats['win_rate'] * 100).round(2)
        segment_stats['segment'] = segment_stats['sport'] + ' ' + segment_stats['confidence']

        # Filter for segments with at least 3 bets (since sample is smaller)
        segment_stats = segment_stats[segment_stats['bets'] >= 3]

        if len(segment_stats) > 0:
            # Worst segments
            worst_segments = segment_stats.sort_values('roi_pct').head(5)
            print(f"\nTOP 5 WORST SEGMENTS:")
            for _, row in worst_segments.iterrows():
                print(f"{row['segment']}: {row['bets']} bets, ROI: {row['roi_pct']}%, "
                      f"Win Rate: {row['win_rate_pct']}%, Loss: ${row['profit']:.2f}")

            # Best segments
            best_segments = segment_stats[segment_stats['profit'] > 0].sort_values('roi_pct', ascending=False).head(5)
            print(f"\nTOP 5 BEST SEGMENTS:")
            for _, row in best_segments.iterrows():
                print(f"{row['segment']}: {row['bets']} bets, ROI: {row['roi_pct']}%, "
                      f"Win Rate: {row['win_rate_pct']}%, Profit: ${row['profit']:.2f}")

        # Generate markdown report
        generate_markdown_report(all_bets, settled_bets, sport_stats, segment_stats)

        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

def generate_markdown_report(all_bets, settled_bets, sport_stats, segment_stats):
    """Generate markdown report file."""
    # Calculate overall metrics
    total_wagered = settled_bets['cost_dollars'].sum()
    total_profit = settled_bets['profit_dollars'].sum()
    roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0

    won_bets = len(settled_bets[settled_bets['status'] == 'won'])
    lost_bets = len(settled_bets[settled_bets['status'] == 'lost'])
    win_rate = (won_bets / len(settled_bets) * 100) if len(settled_bets) > 0 else 0

    # Get worst and best segments
    worst_segments = segment_stats.sort_values('roi_pct').head(5)
    best_segments = segment_stats[segment_stats['profit'] > 0].sort_values('roi_pct', ascending=False).head(5)

    # Create markdown report
    report_date = datetime.now().strftime('%Y%m%d')
    filename = f"actual_betting_summary_since_20260206_{report_date}.md"

    with open(filename, 'w') as f:
        f.write(f"# Actual Betting Analysis Summary\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}  \n")
        f.write(f"**Analysis Period**: Since February 6, 2026  \n")
        f.write(f"**Data Source**: PostgreSQL `placed_bets` table ({len(all_bets)} actual bets)\n\n")

        f.write("---\n\n")

        f.write("## Executive Summary\n\n")
        f.write(f"### Current Performance\n")
        f.write(f"- **Total Bets**: {len(all_bets)} ({len(settled_bets)} settled, {len(all_bets) - len(settled_bets)} open)\n")
        f.write(f"- **Won/Lost**: {won_bets} won, {lost_bets} lost\n")
        f.write(f"- **Total Wagered**: ${total_wagered:.2f}\n")
        f.write(f"- **Total Profit**: ${total_profit:.2f}\n")
        f.write(f"- **Overall ROI**: {roi:.2f}%\n")
        f.write(f"- **Win Rate**: {win_rate:.2f}%\n\n")

        # Performance by sport
        f.write("## Performance by Sport\n\n")
        f.write("| Sport | Bets | ROI | Win Rate | Profit | Status |\n")
        f.write("|-------|------|-----|----------|--------|--------|\n")

        for _, row in sport_stats.iterrows():
            status_emoji = "✅" if row['profit'] > 0 else "❌"
            status_text = "Profitable" if row['profit'] > 0 else "Unprofitable"
            f.write(f"| {row['sport']} | {row['bets']} | {row['roi_pct']:.2f}% | {row['win_rate_pct']:.2f}% | ${row['profit']:.2f} | {status_emoji} {status_text} |\n")

        f.write("\n")

        # Worst segments
        if len(worst_segments) > 0:
            f.write("## Top Problematic Segments\n\n")
            f.write("| Rank | Segment | Bets | ROI | Win Rate | Loss |\n")
            f.write("|------|---------|------|-----|----------|------|\n")

            for i, (_, row) in enumerate(worst_segments.iterrows(), 1):
                f.write(f"| {i} | {row['segment']} | {row['bets']} | {row['roi_pct']:.2f}% | {row['win_rate_pct']:.2f}% | ${row['profit']:.2f} |\n")

            f.write("\n")

        # Best segments
        if len(best_segments) > 0:
            f.write("## Top Profitable Segments\n\n")
            f.write("| Rank | Segment | Bets | ROI | Win Rate | Profit |\n")
            f.write("|------|---------|------|-----|----------|--------|\n")

            for i, (_, row) in enumerate(best_segments.iterrows(), 1):
                f.write(f"| {i} | {row['segment']} | {row['bets']} | {row['roi_pct']:.2f}% | {row['win_rate_pct']:.2f}% | ${row['profit']:.2f} |\n")

            f.write("\n")

        f.write("---\n\n")
        f.write(f"*Analysis complete: {datetime.now().strftime('%Y-%m-%d')}*\n")
        f.write("*Based on actual PostgreSQL betting data*\n")

    print(f"\n✓ Report saved to: {filename}")

if __name__ == "__main__":
    sys.exit(main())
