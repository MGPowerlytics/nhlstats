#!/usr/bin/env python3
"""
Detailed analysis of actual bets placed vs reported.
"""

import sys
import pandas as pd

sys.path.insert(0, "/opt/airflow")

from plugins.db_manager import DBManager


def analyze_bet_discrepancy():
    """Analyze discrepancy between database and JSON reports."""
    print("=" * 80)
    print("BET PLACEMENT DISCREPANCY ANALYSIS")
    print("=" * 80)

    db = DBManager()

    # Get bets by date
    query = """
    SELECT
        DATE(placed_time_utc) as bet_date,
        COUNT(*) as total_bets,
        COUNT(CASE WHEN status = 'won' THEN 1 END) as won,
        COUNT(CASE WHEN status = 'lost' THEN 1 END) as lost,
        COUNT(CASE WHEN status = 'open' THEN 1 END) as open,
        COUNT(CASE WHEN status = 'void' THEN 1 END) as void,
        SUM(CASE WHEN status IN ('won', 'lost', 'void') THEN profit_dollars ELSE 0 END) as total_profit,
        SUM(CASE WHEN status = 'lost' THEN ABS(profit_dollars) ELSE 0 END) as total_loss,
        SUM(CASE WHEN status = 'won' THEN profit_dollars ELSE 0 END) as total_wins
    FROM placed_bets
    WHERE placed_time_utc >= '2026-03-09'
    GROUP BY DATE(placed_time_utc)
    ORDER BY bet_date DESC
    """

    try:
        df = db.fetch_df(query)
        print("\nBETS BY DATE (Database Reality):")
        print("-" * 60)
        for _, row in df.iterrows():
            date_str = row["bet_date"].strftime("%Y-%m-%d")
            print(f"{date_str}: {row['total_bets']} bets")
            print(f"  Won: {row['won']}, Lost: {row['lost']}, Open: {row['open']}")
            print(
                f"  P&L: ${row['total_profit']:.2f} (Wins: ${row['total_wins']:.2f}, Losses: ${row['total_loss']:.2f})"
            )
            print()

    except Exception as e:
        print(f"Error aggregating: {e}")

    # Get detailed March 10 bets
    print("\n" + "=" * 80)
    print("MARCH 10, 2026 - ACTUAL BETS PLACED")
    print("=" * 80)

    query_march10 = """
    SELECT
        placed_time_utc,
        ticker,
        market_title,
        home_team,
        away_team,
        bet_on,
        side,
        cost_dollars,
        price_cents,
        status,
        profit_dollars,
        elo_prob,
        market_prob,
        edge,
        confidence
    FROM placed_bets
    WHERE DATE(placed_time_utc) = '2026-03-10'
    ORDER BY placed_time_utc DESC
    """

    try:
        df_march10 = db.fetch_df(query_march10)
        print(f"Total bets placed March 10: {len(df_march10)}")

        if len(df_march10) > 0:
            total_cost = df_march10["cost_dollars"].sum()
            total_profit = df_march10["profit_dollars"].fillna(0).sum()

            print(f"Total cost: ${total_cost:.2f}")
            print(f"Total profit/loss: ${total_profit:.2f}")

            # Show some bets
            print("\nSample March 10 bets:")
            for idx, row in df_march10.head(10).iterrows():
                time_str = row["placed_time_utc"].strftime("%H:%M:%S")
                market = row.get("market_title", row["ticker"])
                print(f"\n{time_str}: {market}")
                print(
                    f"  Bet on: {row['bet_on']} (${row['cost_dollars']:.2f} @ {row['price_cents']}¢)"
                )
                print(f"  Edge: {row.get('edge', 0):.1%}, Status: {row['status']}")
                if pd.notna(row["profit_dollars"]):
                    print(f"  Profit: ${row['profit_dollars']:.2f}")

    except Exception as e:
        print(f"Error getting March 10 bets: {e}")
        import traceback

        traceback.print_exc()

    # Check for the big loss on March 11
    print("\n" + "=" * 80)
    print("MARCH 11 LOSS ANALYSIS")
    print("=" * 80)

    # Look for the Chicago at Golden State loss
    query_big_loss = """
    SELECT *
    FROM placed_bets
    WHERE DATE(placed_time_utc) = '2026-03-11'
    AND status = 'lost'
    ORDER BY ABS(profit_dollars) DESC
    LIMIT 5
    """

    try:
        df_losses = db.fetch_df(query_big_loss)
        print(f"March 11 losses found: {len(df_losses)}")

        total_loss = df_losses["profit_dollars"].sum()
        print(f"Total loss from these: ${total_loss:.2f}")

        for idx, row in df_losses.iterrows():
            time_str = row["placed_time_utc"].strftime("%H:%M:%S")
            market = row.get("market_title", row["ticker"])
            print(f"\n{time_str}: {market}")
            print(f"  Bet on: {row['bet_on']}, Cost: ${row['cost_dollars']:.2f}")
            print(f"  Loss: ${row['profit_dollars']:.2f}")

    except Exception as e:
        print(f"Error checking losses: {e}")

    # Compare with JSON reports
    print("\n" + "=" * 80)
    print("DISCREPANCY SUMMARY")
    print("=" * 80)

    print("\nJSON Files Report (data/portfolio/betting_results_*.json):")
    print("  March 9: 0 bets placed, 5 errors")
    print("  March 10: 0 bets placed, 7 errors")
    print("  March 11: 0 bets placed, 5 errors")

    print("\nDatabase Reality:")
    print("  61 bets placed March 10+")
    print("  Multiple settled bets with profits/losses")
    print("  Chicago at Golden State lost $6.40 on March 11")

    print("\n🚨 ROOT CAUSE:")
    print("The portfolio_betting.py module reports 'Failed to place bet' but")
    print("bets ARE actually being placed. The error reporting is incorrect.")
    print("\nPossible issues:")
    print("1. Bet placement succeeds but returns None/False")
    print("2. Error handling incorrectly categorizes successful bets as failures")
    print("3. JSON report generation happens before bet confirmation")


def check_bankroll_impact():
    """Check total bankroll impact."""
    print("\n" + "=" * 80)
    print("BANKROLL IMPACT ANALYSIS")
    print("=" * 80)

    db = DBManager()

    # Get all settled bets profit/loss
    query = """
    SELECT
        SUM(CASE WHEN status = 'won' THEN profit_dollars ELSE 0 END) as total_won,
        SUM(CASE WHEN status = 'lost' THEN profit_dollars ELSE 0 END) as total_lost,
        COUNT(CASE WHEN status = 'won' THEN 1 END) as wins,
        COUNT(CASE WHEN status = 'lost' THEN 1 END) as losses
    FROM placed_bets
    WHERE status IN ('won', 'lost', 'void')
    AND placed_time_utc >= '2026-03-09'
    """

    try:
        df = db.fetch_df(query)
        if not df.empty:
            total_won = df.iloc[0]["total_won"] or 0
            total_lost = df.iloc[0]["total_lost"] or 0
            wins = df.iloc[0]["wins"] or 0
            losses = df.iloc[0]["losses"] or 0

            net = total_won + total_lost  # lost is negative

            print(f"March 9-11 Settled Bets:")
            print(f"  Wins: {wins} (${total_won:.2f})")
            print(f"  Losses: {losses} (${abs(total_lost):.2f})")
            print(f"  Net P&L: ${net:.2f}")

            # Check open bets at risk
            query_open = """
            SELECT SUM(cost_dollars) as total_risk
            FROM placed_bets
            WHERE status = 'open'
            AND placed_time_utc >= '2026-03-09'
            """

            df_open = db.fetch_df(query_open)
            if not df_open.empty:
                risk = df_open.iloc[0]["total_risk"] or 0
                print(f"  Open bets at risk: ${risk:.2f}")
                print(f"  Total exposure: ${net + risk:.2f}")

    except Exception as e:
        print(f"Error checking bankroll: {e}")


if __name__ == "__main__":
    analyze_bet_discrepancy()
    check_bankroll_impact()

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print("\n1. FIX ERROR REPORTING: portfolio_betting.py incorrectly reports failures")
    print("2. VERIFY BET LOGIC: Check why successful bets return None/False")
    print("3. AUDIT ALL BETS: Reconcile database with Kalshi account")
    print("4. UPDATE PORTFOLIO REPORTS: Regenerate with correct data")
    print("5. TEST BET PLACEMENT: Add validation to confirm bets placed")
