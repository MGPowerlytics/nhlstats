#!/usr/bin/env python3
"""
Analyze betting losses from yesterday and current exposure.
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
import glob
import re


def load_bets_for_date(sport, bet_date):
    """Load bet recommendations for a specific date."""
    file_path = f"data/{sport}/bets_{bet_date}.json"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return []


def load_game_result(game_id):
    """Load game result from boxscore file."""
    # Extract date from game_id format: NBA_20260310_HOUSTON_TOR
    # Date part: 20260310
    match = re.search(r"(\d{8})", game_id)
    if not match:
        return None

    date_str = match.group(1)
    year = date_str[:4]
    month = date_str[4:6]
    day = date_str[6:8]

    # Convert to file naming format: 2025021012 (needs game number)
    # This is complex - let's search for files with the date
    games_dir = "data/games"
    date_dir = f"{year}-{month}-{day}"
    date_path = os.path.join(games_dir, date_dir)

    if not os.path.exists(date_path):
        return None

    # Look for boxscore files
    boxscore_files = glob.glob(os.path.join(date_path, "*_boxscore.json"))

    # Simple approach: parse first boxscore to understand format
    if boxscore_files:
        with open(boxscore_files[0], "r") as f:
            sample = json.load(f)
            return sample

    return None


def analyze_nba_bets_yesterday():
    """Analyze NBA bets from yesterday (March 10, 2026)."""
    yesterday = date(2026, 3, 10)
    bets = load_bets_for_date("nba", yesterday.strftime("%Y-%m-%d"))

    print("=" * 80)
    print(f"NBA BET ANALYSIS FOR {yesterday}")
    print("=" * 80)

    if not bets:
        print("No bets found for yesterday")
        return

    print(f"Found {len(bets)} bet recommendations")
    print("\n" + "-" * 80)

    # Categorize bets by confidence
    high_bets = [b for b in bets if b.get("confidence") == "HIGH"]
    medium_bets = [b for b in bets if b.get("confidence") == "MEDIUM"]
    low_bets = [b for b in bets if b.get("confidence") == "LOW"]

    print(f"Confidence breakdown:")
    print(f"  HIGH: {len(high_bets)} bets")
    print(f"  MEDIUM: {len(medium_bets)} bets")
    print(f"  LOW: {len(low_bets)} bets")

    # Analyze edges
    edges = [b.get("edge", 0) for b in bets]
    avg_edge = np.mean(edges) if edges else 0

    print(f"\nEdge analysis:")
    print(f"  Average edge: {avg_edge:.2%}")
    print(f"  Min edge: {min(edges):.2%}" if edges else "  No edges")
    print(f"  Max edge: {max(edges):.2%}" if edges else "  No edges")

    # Show highest edge bets
    print(f"\nTOP 5 HIGHEST EDGE BETS:")
    print("-" * 40)

    sorted_bets = sorted(bets, key=lambda x: x.get("edge", 0), reverse=True)[:5]
    for i, bet in enumerate(sorted_bets, 1):
        game_id = bet.get("game_id", "Unknown")
        home = bet.get("home_team", "Unknown")
        away = bet.get("away_team", "Unknown")
        bet_on = bet.get("bet_on", "Unknown")
        edge = bet.get("edge", 0)
        elo_prob = bet.get("elo_prob", 0)
        market_prob = bet.get("market_prob", 0)
        confidence = bet.get("confidence", "UNKNOWN")

        print(f"{i}. {home} vs {away} - Bet on: {bet_on}")
        print(f"   Edge: {edge:.2%} (Elo: {elo_prob:.1%} vs Market: {market_prob:.1%})")
        print(f"   Confidence: {confidence}")
        print()

    # Check which games were actually played yesterday
    print(f"\nGAMES PLAYED ON {yesterday}:")
    print("-" * 40)

    # Hardcoded known results for March 10, 2026 NBA games
    # Based on typical NBA schedule and the bets we saw
    known_results = {
        "NBA_20260310_HOUSTON_TOR": {
            "home": "Houston",
            "away": "TOR",
            "home_won": None,
            "notes": "Unknown result",
        },
        "NBA_20260310_LAL_MIN": {
            "home": "LAL",
            "away": "MIN",
            "home_won": None,
            "notes": "Unknown result",
        },
        "NBA_20260310_SAC_INDIANA": {
            "home": "SAC",
            "away": "Indiana",
            "home_won": None,
            "notes": "Unknown result",
        },
        "NBA_20260310_MIA_WAS": {
            "home": "MIA",
            "away": "WAS",
            "home_won": None,
            "notes": "Unknown result",
        },
        "NBA_20260310_BKN_DET": {
            "home": "BKN",
            "away": "DET",
            "home_won": None,
            "notes": "Unknown result",
        },
        "NBA_20260310_PHI_MEM": {
            "home": "PHI",
            "away": "MEM",
            "home_won": None,
            "notes": "Unknown result",
        },
        "NBA_20260310_ATL_DAL": {
            "home": "ATL",
            "away": "DAL",
            "home_won": None,
            "notes": "Unknown result",
        },
        "NBA_20260310_MIL_PHX": {
            "home": "MIL",
            "away": "PHX",
            "home_won": None,
            "notes": "Unknown result",
        },
        "NBA_20260310_SAS_BOS": {
            "home": "SAS",
            "away": "BOS",
            "home_won": None,
            "notes": "Unknown result",
        },
        "NBA_20260310_GSW_CHI": {
            "home": "GSW",
            "away": "CHI",
            "home_won": None,
            "notes": "Unknown result",
        },
    }

    # Try to get actual results from boxscore files
    games_dir = "data/games/2026-03-10"
    if os.path.exists(games_dir):
        boxscore_files = glob.glob(os.path.join(games_dir, "*_boxscore.json"))
        print(f"Found {len(boxscore_files)} boxscore files for {yesterday}")

        # Parse a few to understand format
        for boxscore_file in boxscore_files[:3]:
            try:
                with open(boxscore_file, "r") as f:
                    data = json.load(f)

                # Extract game info - structure varies
                print(f"\nSample boxscore: {os.path.basename(boxscore_file)}")
                if "game" in data:
                    game_info = data["game"]
                    if "homeTeam" in game_info and "awayTeam" in game_info:
                        home_team = game_info["homeTeam"].get("teamName", "Unknown")
                        away_team = game_info["awayTeam"].get("teamName", "Unknown")
                        home_score = game_info.get("homeScore", "Unknown")
                        away_score = game_info.get("awayScore", "Unknown")
                        print(
                            f"  {home_team} vs {away_team}: {home_score}-{away_score}"
                        )
            except Exception as e:
                print(f"  Error parsing {boxscore_file}: {e}")
    else:
        print(f"No game directory found for {yesterday}")

    return bets


def analyze_portfolio_losses():
    """Analyze portfolio losses from betting reports."""
    print("\n" + "=" * 80)
    print("PORTFOLIO LOSS ANALYSIS")
    print("=" * 80)

    # Read recent betting reports
    report_files = sorted(glob.glob("data/portfolio/betting_report_*.txt"))

    if not report_files:
        print("No betting reports found")
        return

    # Get last 5 reports
    recent_reports = report_files[-5:]

    portfolio_values = []

    for report_file in recent_reports:
        date_str = (
            os.path.basename(report_file)
            .replace("betting_report_", "")
            .replace(".txt", "")
        )

        with open(report_file, "r") as f:
            content = f.read()

        # Extract bankroll
        bankroll_match = re.search(r"Bankroll:\s*\$([\d.]+)", content)
        bankroll = float(bankroll_match.group(1)) if bankroll_match else 0

        # Extract total bet amount
        bet_amount_match = re.search(r"Total Bet Amount:\s*\$([\d.]+)", content)
        bet_amount = float(bet_amount_match.group(1)) if bet_amount_match else 0

        portfolio_values.append(
            {"date": date_str, "bankroll": bankroll, "bet_amount": bet_amount}
        )

    # Create DataFrame
    df = pd.DataFrame(portfolio_values)

    print("\nRecent Portfolio Performance:")
    print("-" * 40)

    for i, row in df.iterrows():
        print(
            f"{row['date']}: Bankroll: ${row['bankroll']:.2f}, Bet Amount: ${row['bet_amount']:.2f}"
        )

    # Calculate daily changes
    if len(df) >= 2:
        df["daily_change"] = df["bankroll"].diff()
        df["pct_change"] = df["bankroll"].pct_change() * 100

        print(f"\nDaily Changes:")
        print("-" * 40)

        for i in range(1, len(df)):
            date1 = df.iloc[i - 1]["date"]
            date2 = df.iloc[i]["date"]
            change = df.iloc[i]["daily_change"]
            pct_change = df.iloc[i]["pct_change"]

            if change < 0:
                print(
                    f"{date1} → {date2}: LOST ${abs(change):.2f} ({abs(pct_change):.1f}%)"
                )
            else:
                print(f"{date1} → {date2}: Gained ${change:.2f} ({pct_change:.1f}%)")

    # Check betting results
    print(f"\nBETTING EXECUTION RESULTS:")
    print("-" * 40)

    result_files = sorted(glob.glob("data/portfolio/betting_results_*.json"))

    if result_files:
        # Get last 3 results
        for result_file in result_files[-3:]:
            date_str = (
                os.path.basename(result_file)
                .replace("betting_results_", "")
                .replace(".json", "")
            )

            with open(result_file, "r") as f:
                result = json.load(f)

            placed = len(result.get("placed_bets", []))
            errors = len(result.get("errors", []))
            skipped = len(result.get("skipped_bets", []))

            print(
                f"{date_str}: {placed} bets placed, {errors} errors, {skipped} skipped"
            )

            if errors > 0:
                print(f"  ⚠️  {errors} bets failed to place!")

    return df


def analyze_current_exposure():
    """Analyze current exposure from pending bets."""
    print("\n" + "=" * 80)
    print("CURRENT EXPOSURE ANALYSIS")
    print("=" * 80)

    # Check for bets placed on March 8th that are still pending
    march8_file = "data/portfolio/betting_results_2026-03-08.json"

    if os.path.exists(march8_file):
        with open(march8_file, "r") as f:
            result = json.load(f)

        placed_bets = result.get("placed_bets", [])

        if placed_bets:
            print(f"\nPENDING BETS FROM MARCH 8TH:")
            print("-" * 40)

            total_at_risk = 0
            for bet in placed_bets:
                ticker = bet.get("ticker", "Unknown")
                amount = bet.get("amount", 0)
                price = bet.get("price", 0)  # This is market probability (34 = 34%)
                side = bet.get("side", "yes")
                sport = bet.get("sport", "unknown")

                # Extract game info from ticker
                # Format: KXNBAGAME-26MAR12PHXIND-IND
                if "26MAR12" in ticker:
                    game_date = "March 12"
                elif "26MAR11" in ticker:
                    game_date = "March 11"
                elif "26MAR10" in ticker:
                    game_date = "March 10"
                else:
                    game_date = "Unknown"

                teams = ticker.split("-")[1].replace("26MAR", "")
                bet_on = ticker.split("-")[-1]

                print(f"{teams} - Bet on {bet_on} (${amount:.2f})")
                print(
                    f"  Market probability: {price}%, Game date: {game_date}, Sport: {sport}"
                )
                print()

                total_at_risk += amount

            print(f"Total at risk from March 8th bets: ${total_at_risk:.2f}")

    # Check today's recommendations
    today = date(2026, 3, 11)
    today_bets = load_bets_for_date("nba", today.strftime("%Y-%m-%d"))

    if today_bets:
        print(f"\nTODAY'S BET RECOMMENDATIONS ({today}):")
        print("-" * 40)

        total_recommended_stake = 0
        high_confidence_bets = []

        for bet in today_bets[:5]:  # Show top 5
            home = bet.get("home_team", "Unknown")
            away = bet.get("away_team", "Unknown")
            bet_on = bet.get("bet_on", "Unknown")
            edge = bet.get("edge", 0)
            confidence = bet.get("confidence", "UNKNOWN")
            market_odds = bet.get("market_odds", 0)

            print(f"{home} vs {away} - Bet on {bet_on}")
            print(
                f"  Edge: {edge:.2%}, Confidence: {confidence}, Odds: {market_odds:.2f}"
            )
            print()

            if confidence == "HIGH":
                high_confidence_bets.append(bet)

        print(f"Total recommendations today: {len(today_bets)}")
        print(f"High confidence bets: {len(high_confidence_bets)}")


def main():
    """Main analysis function."""
    print("🚨 COMPREHENSIVE BETTING LOSS ANALYSIS")
    print("=" * 80)

    # 1. Analyze yesterday's NBA bets
    nba_bets = analyze_nba_bets_yesterday()

    # 2. Analyze portfolio losses
    portfolio_df = analyze_portfolio_losses()

    # 3. Analyze current exposure
    analyze_current_exposure()

    # 4. Summary and recommendations
    print("\n" + "=" * 80)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 80)

    # Key findings from portfolio analysis
    if len(portfolio_df) >= 2:
        latest = portfolio_df.iloc[-1]
        previous = portfolio_df.iloc[-2]

        loss = previous["bankroll"] - latest["bankroll"]
        loss_pct = (
            (loss / previous["bankroll"]) * 100 if previous["bankroll"] > 0 else 0
        )

        print(f"\n⚠️ CRITICAL LOSS DETECTED:")
        print(f"  From {previous['date']} to {latest['date']}:")
        print(f"  Lost ${loss:.2f} ({loss_pct:.1f}% of bankroll)")
        print(
            f"  Bankroll dropped from ${previous['bankroll']:.2f} to ${latest['bankroll']:.2f}"
        )

    print(f"\n🔍 ROOT CAUSE ANALYSIS:")
    print("  1. Betting system shows 'Failed to place bet' errors on March 9-11")
    print("  2. Yet bankroll dropped dramatically - suggests manual bets or stale data")
    print("  3. Portfolio data may not reflect actual placed bets")

    print(f"\n🎯 IMMEDIATE ACTIONS REQUIRED:")
    print("  1. CHECK KALSHI ACCOUNT: Verify actual bets placed and current balance")
    print("  2. FIX BET PLACEMENT: Investigate 'Failed to place bet' errors")
    print("  3. VALIDATE ELO MODEL: Check if recent predictions are accurate")
    print("  4. PAUSE BETTING: Stop automated betting until issues resolved")

    print(f"\n📊 TECHNICAL ISSUES IDENTIFIED:")
    print("  • Database connection failing (could not translate host name 'postgres')")
    print("  • Bet placement API errors")
    print("  • Portfolio data inconsistency")

    print(f"\n✅ NEXT STEPS:")
    print("  1. Run manual Kalshi balance check")
    print("  2. Test bet placement with small amount")
    print("  3. Validate Elo predictions against actual results")
    print("  4. Implement proper error handling and logging")


if __name__ == "__main__":
    main()
