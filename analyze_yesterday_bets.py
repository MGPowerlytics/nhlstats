#!/usr/bin/env python3
"""
Analyze yesterday's bets to understand losses and current exposure.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import logging
from plugins.db_manager import DBManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_yesterday_bets():
    """Analyze bets placed yesterday and their outcomes."""
    db = DBManager()

    # Get yesterday's date (2026-03-10)
    yesterday = date(2026, 3, 10)
    today = date(2026, 3, 11)

    print(f"Analyzing bets placed on {yesterday} and their current status...")
    print("=" * 80)

    # Query placed bets from yesterday
    query = """
    SELECT
        bet_id,
        game_id,
        market_id,
        bookmaker,
        outcome,
        stake,
        odds,
        potential_payout,
        status,
        result,
        placed_time_utc,
        market_title,
        market_close_time_utc
    FROM placed_bets
    WHERE DATE(placed_time_utc) = :yesterday
    OR DATE(placed_time_utc) = :today
    ORDER BY placed_time_utc DESC
    """

    try:
        df = db.fetch_df(query, {"yesterday": yesterday, "today": today})

        if df.empty:
            print("⚠️ No bets found for yesterday or today!")
            print("\nChecking if placed_bets table exists...")

            # Check if table exists
            if db.table_exists("placed_bets"):
                print("✓ placed_bets table exists")
                # Check total count
                count_query = "SELECT COUNT(*) as total_bets FROM placed_bets"
                count_df = db.fetch_df(count_query)
                print(f"Total bets in database: {count_df.iloc[0]['total_bets']}")

                # Check date range
                date_query = """
                SELECT MIN(placed_time_utc) as earliest, MAX(placed_time_utc) as latest
                FROM placed_bets
                """
                date_df = db.fetch_df(date_query)
                print(
                    f"Date range: {date_df.iloc[0]['earliest']} to {date_df.iloc[0]['latest']}"
                )
            else:
                print("✗ placed_bets table does not exist")
            return

        print(f"Found {len(df)} bets placed yesterday/today")
        print("\n" + "=" * 80)

        # Calculate summary statistics
        total_stake = df["stake"].sum()
        total_potential_payout = df["potential_payout"].sum()

        # Separate by status
        pending_bets = df[df["status"] == "pending"]
        win_bets = df[df["status"] == "win"]
        loss_bets = df[df["status"] == "loss"]

        # Calculate actual results
        total_result = df["result"].sum() if "result" in df.columns else 0
        total_wins = win_bets["result"].sum() if not win_bets.empty else 0
        total_losses = abs(loss_bets["stake"].sum()) if not loss_bets.empty else 0

        print("\n📊 BETTING SUMMARY")
        print("-" * 40)
        print(f"Total bets placed: {len(df)}")
        print(f"Total stake: ${total_stake:.2f}")
        print(f"Total potential payout: ${total_potential_payout:.2f}")
        print(f"Total realized P&L: ${total_result:.2f}")
        print(f"\nStatus breakdown:")
        print(
            f"  Pending: {len(pending_bets)} bets (${pending_bets['stake'].sum():.2f} at risk)"
        )
        print(f"  Wins: {len(win_bets)} bets (${total_wins:.2f} profit)")
        print(f"  Losses: {len(loss_bets)} bets (${total_losses:.2f} loss)")

        if len(pending_bets) > 0:
            print(f"\n🚨 CURRENT EXPOSURE (Pending bets):")
            print("-" * 40)
            for _, bet in pending_bets.iterrows():
                sport = (
                    bet["market_title"].split()[0]
                    if isinstance(bet["market_title"], str)
                    else "Unknown"
                )
                print(f"  {bet['market_title'][:50]}...")
                print(f"    Stake: ${bet['stake']:.2f}, Odds: {bet['odds']:.2f}")
                print(f"    Potential: ${bet['potential_payout']:.2f}")
                if pd.notna(bet["market_close_time_utc"]):
                    close_time = bet["market_close_time_utc"]
                    print(f"    Closes: {close_time}")
                print()

        # Analyze by bookmaker
        print("\n📈 BY BOOKMAKER:")
        print("-" * 40)
        for bookmaker in df["bookmaker"].unique():
            bookmaker_bets = df[df["bookmaker"] == bookmaker]
            bookmaker_stake = bookmaker_bets["stake"].sum()
            bookmaker_result = (
                bookmaker_bets["result"].sum()
                if "result" in bookmaker_bets.columns
                else 0
            )
            print(
                f"  {bookmaker}: {len(bookmaker_bets)} bets, Stake: ${bookmaker_stake:.2f}, P&L: ${bookmaker_result:.2f}"
            )

        # Check for today's pending bets (potential losses)
        today_pending = df[
            (df["status"] == "pending") & (df["placed_time_utc"].dt.date == today)
        ]
        if len(today_pending) > 0:
            print(f"\n⚠️ TODAY'S PENDING BETS (Potential future losses):")
            print("-" * 40)
            for _, bet in today_pending.iterrows():
                print(f"  {bet['market_title'][:60]}...")
                print(f"    Stake: ${bet['stake']:.2f}, At risk: ${bet['stake']:.2f}")

        # Check game outcomes for yesterday's bets
        print("\n🎯 GAME OUTCOME ANALYSIS:")
        print("-" * 40)

        # Query game results for these bets
        if "game_id" in df.columns and not df["game_id"].isna().all():
            game_ids = df["game_id"].dropna().unique()
            if len(game_ids) > 0:
                game_query = f"""
                SELECT game_id, sport, home_team_name, away_team_name, home_score, away_score, status
                FROM unified_games
                WHERE game_id IN ({",".join([f"'{gid}'" for gid in game_ids])})
                """
                games_df = db.fetch_df(game_query)

                if not games_df.empty:
                    # Merge with bets
                    merged = pd.merge(df, games_df, on="game_id", how="left")

                    # Analyze by sport
                    for sport in merged["sport"].dropna().unique():
                        sport_bets = merged[merged["sport"] == sport]
                        sport_stake = sport_bets["stake"].sum()
                        sport_result = (
                            sport_bets["result"].sum()
                            if "result" in sport_bets.columns
                            else 0
                        )
                        print(
                            f"  {sport}: {len(sport_bets)} bets, Stake: ${sport_stake:.2f}, P&L: ${sport_result:.2f}"
                        )

                        # Show game details
                        for _, bet in sport_bets.iterrows():
                            if pd.notna(bet["home_team_name"]):
                                outcome = (
                                    "Home win"
                                    if bet["home_score"] > bet["away_score"]
                                    else "Away win"
                                    if bet["away_score"] > bet["home_score"]
                                    else "Unknown"
                                )
                                print(
                                    f"    {bet['home_team_name']} vs {bet['away_team_name']}: {bet['home_score']}-{bet['away_score']} ({outcome})"
                                )

        # Check if we're primed to lose more today
        print("\n🔮 RISK ASSESSMENT:")
        print("-" * 40)

        # Check portfolio snapshot for recent losses
        portfolio_query = """
        SELECT snapshot_time, total_value, cash_balance, invested_amount, unrealized_pnl, realized_pnl
        FROM portfolio_snapshots
        ORDER BY snapshot_time DESC
        LIMIT 10
        """

        try:
            portfolio_df = db.fetch_df(portfolio_query)
            if not portfolio_df.empty:
                print("Recent portfolio performance:")
                for _, row in portfolio_df.iterrows():
                    print(
                        f"  {row['snapshot_time']}: Value: ${row['total_value']:.2f}, "
                        f"Cash: ${row['cash_balance']:.2f}, Invested: ${row['invested_amount']:.2f}, "
                        f"Realized P&L: ${row['realized_pnl']:.2f}"
                    )

                # Calculate daily change
                if len(portfolio_df) >= 2:
                    latest = portfolio_df.iloc[0]
                    previous = portfolio_df.iloc[1]
                    daily_change = latest["total_value"] - previous["total_value"]
                    print(f"\n📉 Yesterday's portfolio change: ${daily_change:.2f}")

                    if daily_change < 0:
                        print(f"⚠️ LOST ${abs(daily_change):.2f} yesterday")

        except Exception as e:
            logger.warning(f"Could not fetch portfolio data: {e}")

        # Check bet recommendations for today
        print("\n📋 TODAY'S BET RECOMMENDATIONS:")
        print("-" * 40)

        rec_query = """
        SELECT sport, COUNT(*) as num_recommendations, SUM(recommended_stake) as total_stake
        FROM bet_recommendations
        WHERE DATE(generated_at) = :today
        AND status = 'active'
        GROUP BY sport
        """

        try:
            rec_df = db.fetch_df(rec_query, {"today": today})
            if not rec_df.empty:
                for _, row in rec_df.iterrows():
                    print(
                        f"  {row['sport']}: {row['num_recommendations']} recommendations, "
                        f"Total stake: ${row['total_stake']:.2f}"
                    )
            else:
                print("  No active recommendations for today")
        except Exception as e:
            logger.warning(f"Could not fetch recommendations: {e}")

        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")

        # Return detailed DataFrame for further analysis
        return df

    except Exception as e:
        logger.error(f"Error analyzing bets: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    analyze_yesterday_bets()
