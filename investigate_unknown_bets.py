#!/usr/bin/env python3
"""
Investigate UNKNOWN sport bets in the database.
"""

import sys
import os
import pandas as pd
from datetime import datetime

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plugins'))
from db_manager import DBManager

def main():
    """Investigate UNKNOWN bets."""
    try:
        # Create connection string for localhost
        connection_string = "postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
        db = DBManager(connection_string=connection_string)

        print("Investigating UNKNOWN sport bets...")

        # Get all UNKNOWN bets
        query = """
        SELECT
            bet_id,
            placed_date,
            ticker,
            home_team,
            away_team,
            bet_on,
            side,
            contracts,
            price_cents,
            cost_dollars,
            fees_dollars,
            elo_prob,
            market_prob,
            edge,
            confidence,
            status,
            settled_date,
            payout_dollars,
            profit_dollars,
            market_title,
            market_close_time_utc
        FROM placed_bets
        WHERE sport = 'UNKNOWN'
        ORDER BY placed_date DESC
        """

        unknown_bets = db.fetch_df(query)

        print(f"\nTotal UNKNOWN bets: {len(unknown_bets)}")

        if len(unknown_bets) == 0:
            print("No UNKNOWN bets found")
            return 0

        # Show date range
        print(f"Date range: {unknown_bets['placed_date'].min()} to {unknown_bets['placed_date'].max()}")

        # Show unique tickers
        unique_tickers = unknown_bets['ticker'].unique()
        print(f"\nUnique tickers ({len(unique_tickers)}):")
        for ticker in unique_tickers[:20]:  # Show first 20
            print(f"  {ticker}")

        if len(unique_tickers) > 20:
            print(f"  ... and {len(unique_tickers) - 20} more")

        # Show unique market titles
        unique_titles = unknown_bets['market_title'].dropna().unique()
        print(f"\nUnique market titles ({len(unique_titles)}):")
        for title in unique_titles[:20]:  # Show first 20
            print(f"  {title}")

        if len(unique_titles) > 20:
            print(f"  ... and {len(unique_titles) - 20} more")

        # Show performance by confidence
        print(f"\nPerformance by confidence:")
        conf_stats = unknown_bets.groupby('confidence').agg({
            'bet_id': 'count',
            'cost_dollars': 'sum',
            'profit_dollars': 'sum'
        }).reset_index()

        conf_stats.columns = ['confidence', 'bets', 'wagered', 'profit']
        conf_stats['roi_pct'] = (conf_stats['profit'] / conf_stats['wagered'] * 100).round(2)

        for _, row in conf_stats.iterrows():
            print(f"  {row['confidence']}: {row['bets']} bets, ROI: {row['roi_pct']}%, Profit: ${row['profit']:.2f}")

        # Show sample of bets
        print(f"\nSample of UNKNOWN bets (first 10):")
        sample = unknown_bets.head(10)
        for _, row in sample.iterrows():
            print(f"\n  Bet ID: {row['bet_id']}")
            print(f"  Date: {row['placed_date']}")
            print(f"  Ticker: {row['ticker']}")
            print(f"  Market: {row['market_title']}")
            print(f"  Teams: {row['home_team']} vs {row['away_team']} (bet on: {row['bet_on']})")
            print(f"  Confidence: {row['confidence']}, Status: {row['status']}")
            print(f"  Profit: ${row['profit_dollars']:.2f}")

        # Try to identify sport from ticker patterns
        print(f"\nAnalyzing ticker patterns...")

        # Check for common ticker prefixes
        ticker_prefixes = {}
        for ticker in unknown_bets['ticker']:
            if ticker and isinstance(ticker, str):
                # Extract prefix (e.g., KXNBAGAME from KXNBAGAME-26FEB08NYKBOS-BOS)
                parts = ticker.split('-')
                if len(parts) > 0:
                    prefix = parts[0]
                    ticker_prefixes[prefix] = ticker_prefixes.get(prefix, 0) + 1

        print(f"Ticker prefixes found:")
        for prefix, count in sorted(ticker_prefixes.items(), key=lambda x: x[1], reverse=True):
            print(f"  {prefix}: {count} bets")

            # Try to identify sport from prefix
            if 'NBA' in prefix:
                print(f"    -> Likely NBA")
            elif 'NCAAM' in prefix or 'NCAAB' in prefix:
                print(f"    -> Likely NCAAB")
            elif 'NHL' in prefix:
                print(f"    -> Likely NHL")
            elif 'TENNIS' in prefix or 'ATP' in prefix or 'WTA' in prefix:
                print(f"    -> Likely TENNIS")
            elif 'MLB' in prefix:
                print(f"    -> Likely MLB")
            elif 'NFL' in prefix:
                print(f"    -> Likely NFL")
            elif 'EPL' in prefix:
                print(f"    -> Likely EPL")
            elif 'CBA' in prefix:
                print(f"    -> Likely CBA")
            elif 'WNCAAB' in prefix or 'NCAAWB' in prefix:
                print(f"    -> Likely WNCAAB")

        # Check if we can update these bets with correct sport
        print(f"\nChecking for sport identification opportunities...")

        # Look for bets that might be misclassified
        for prefix in ticker_prefixes:
            if 'NBA' in prefix and prefix != 'KXNBAGAME':
                print(f"Found {ticker_prefixes[prefix]} bets with prefix '{prefix}' - might be NBA")
            elif ('NCAAM' in prefix or 'NCAAB' in prefix) and 'KXNCAAM' not in prefix:
                print(f"Found {ticker_prefixes[prefix]} bets with prefix '{prefix}' - might be NCAAB")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
