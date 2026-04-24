#!/usr/bin/env python3
"""
Extract MLB Data for Backtesting

This script extracts historical MLB game data with:
- Elo probabilities
- Market probabilities (Kalshi)
- BetMGM probabilities
- Game results
- Odds

To use this script, ensure you have database access and run:
    python extract_mlb_data.py --start_date 2021-01-01 --end_date 2024-12-31

The extracted data will be saved as CSV for backtesting.
"""

import sys
import pandas as pd
from datetime import datetime
from pathlib import Path
import argparse

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugins"))
from db_manager import default_db

def extract_mlb_data(start_date: str, end_date: str, output_file: str = None) -> pd.DataFrame:
    """
    Extract MLB game data for backtesting.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        output_file: Optional output CSV file path

    Returns:
        DataFrame with extracted data
    """
    print(f"🔍 Extracting MLB data from {start_date} to {end_date}...")

    query = """
    SELECT
        g.game_id,
        g.game_date,
        g.home_team_name as home_team,
        g.away_team_name as away_team,
        g.home_score,
        g.away_score,
        g.status,
        r.elo_prob,
        r.market_prob,
        b.price as betmgm_price,
        b.price / 100.0 as betmgm_prob,
        r.edge,
        r.confidence,
        r.market_prob * 100.0 as kalshi_yes_ask,
        (1.0 - r.market_prob) * 100.0 as kalshi_no_ask,
        r.recommendation_date
    FROM unified_games g
    JOIN bet_recommendations r
        ON g.sport = r.sport
        AND g.home_team_name = r.home_team
        AND g.away_team_name = r.away_team
        AND TO_CHAR(g.game_date, 'YYYYMMDD') = CAST(r.recommendation_date AS TEXT)
    LEFT JOIN game_odds o ON g.game_id = o.game_id
        AND o.bookmaker = 'Kalshi'
        AND o.market_name = 'moneyline'
    LEFT JOIN game_odds b ON g.game_id = b.game_id
        AND b.bookmaker = 'BetMGM'
        AND b.market_name = 'moneyline'
    WHERE g.sport = 'MLB'
        AND g.game_date >= :start_date
        AND g.game_date <= :end_date
        AND g.status IN ('Final', 'Completed')
    ORDER BY g.game_date
    """

    params = {
        "start_date": start_date,
        "end_date": end_date
    }

    print("📥 Querying database...")
    df = default_db.fetch_df(query, params)

    print(f"✓ Extracted {len(df)} games")

    # Verify data existence in underlying tables
    print("\n🔍 Checking data availability...")
    # Check unified_games
    game_count = default_db.fetch_scalar("SELECT COUNT(*) FROM unified_games WHERE sport = 'MLB' AND game_date BETWEEN :start_date AND :end_date", params)
    print(f"   MLB games in unified_games: {game_count}")

    # Check bet_recommendations
    rec_count = default_db.fetch_scalar("SELECT COUNT(*) FROM bet_recommendations WHERE sport = 'MLB' AND recommendation_date BETWEEN :start_date AND :end_date", params)
    print(f"   MLB recommendations: {rec_count}")

    # Check game_odds for BetMGM
    odds_count = default_db.fetch_scalar("SELECT COUNT(*) FROM game_odds WHERE bookmaker = 'BetMGM' AND market_name = 'moneyline' AND game_id IN (SELECT game_id FROM unified_games WHERE sport = 'MLB')", params)
    print(f"   BetMGM moneyline odds: {odds_count}")

    # Debug database content
    game_count_df = default_db.fetch_df("SELECT COUNT(*) as count FROM unified_games WHERE sport = 'MLB'")
    game_count = game_count_df.iloc[0]['count'] if not game_count_df.empty else 0

    rec_count_df = default_db.fetch_df("SELECT COUNT(*) as count FROM bet_recommendations WHERE sport = 'MLB'")
    rec_count = rec_count_df.iloc[0]['count'] if not rec_count_df.empty else 0

    betmgm_count_df = default_db.fetch_df("SELECT COUNT(*) as count FROM game_odds WHERE bookmaker = 'BetMGM' AND market_name = 'moneyline'")
    betmgm_count = betmgm_count_df.iloc[0]['count'] if not betmgm_count_df.empty else 0

    # Detailed diagnostics temporarily disabled

    print(f"\n   With Elo: {df['elo_prob'].notna().sum() if not df.empty else 0}")
    print(f"   With Market: {df['market_prob'].notna().sum() if not df.empty else 0}")
    print(f"   With BetMGM: {df['betmgm_prob'].notna().sum() if not df.empty else 0}")

    # Save to CSV if output_file provided
    if output_file:
        df.to_csv(output_file, index=False)
        print(f"💾 Data saved to {output_file}")

    return df


def main():
    parser = argparse.ArgumentParser(description="Extract MLB data for backtesting")
    parser.add_argument("--start_date", default="2021-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end_date", default="2024-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", default="mlb_backtest_data.csv", help="Output CSV file")

    args = parser.parse_args()

    try:
        df = extract_mlb_data(args.start_date, args.end_date, args.output)
        return 0
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
