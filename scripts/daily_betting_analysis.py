#!/usr/bin/env python3
"""
Daily betting analysis - Quick command to check all opportunities.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_analysis():
    """Run complete betting analysis."""
    today = datetime.now().strftime("%Y-%m-%d")

    print("=" * 80)
    print(f"🎯 DAILY BETTING ANALYSIS - {today}")
    print("=" * 80)
    print()

    # Check if we have today's Kalshi bets
    sports = ["nba", "ncaab", "wncaab", "tennis"]
    bet_files = []
    for sport in sports:
        bet_file = Path(f"data/{sport}/bets_{today}.json")
        if bet_file.exists():
            bet_files.append(sport)

    if not bet_files:
        print("⚠️  No Kalshi bets found for today!")
        print("Run the Airflow DAG first: docker exec <scheduler> airflow dags trigger multi_sport_betting_workflow")
        return

    print(f"✓ Found Kalshi bets for: {', '.join(bet_files)}\n")

    # Fetch BetMGM odds
    print("📥 Fetching BetMGM odds...")
    print()
    result = subprocess.run(
        ["python", "plugins/betmgm_integration.py"],
        capture_output=False
    )

    if result.returncode != 0:
        print("\n⚠️  Error fetching BetMGM odds")
        return

    # Run comparison
    print("\n" + "=" * 80)
    print()
    result = subprocess.run(
        ["python", "compare_betting_markets.py", today],
        capture_output=False
    )

    if result.returncode != 0:
        print("\n⚠️  Error running market comparison")
        return

    # Show summary files
    print("\n" + "=" * 80)
    print("📁 Output Files")
    print("=" * 80)
    print()

    for sport in bet_files:
        bet_file = Path(f"data/{sport}/bets_{today}.json")
        print(f"  Kalshi {sport.upper()}: {bet_file}")

    betmgm_file = Path(f"data/betmgm_opportunities_{today}.json")
    if betmgm_file.exists():
        print(f"  BetMGM: {betmgm_file}")

    print()
    print("=" * 80)
    print("✅ Analysis complete!")
    print("=" * 80)


if __name__ == "__main__":
    run_analysis()
