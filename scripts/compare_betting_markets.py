"""
Cross-Market Analysis: Compare Kalshi, BetMGM, and our Elo predictions.
Find arbitrage and value betting opportunities.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import sys


def load_kalshi_bets(sport: str, date_str: str) -> List[Dict]:
    """Load Kalshi bet recommendations."""
    bets_file = Path(f"data/{sport}/bets_{date_str}.json")
    if not bets_file.exists():
        return []

    with open(bets_file) as f:
        return json.load(f)


def load_betmgm_opportunities(date_str: str) -> List[Dict]:
    """Load BetMGM opportunities."""
    opp_file = Path(f"data/betmgm_opportunities_{date_str}.json")
    if not opp_file.exists():
        return []

    with open(opp_file) as f:
        return json.load(f)


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal."""
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


def find_arbitrage(kalshi_bets: List[Dict], betmgm_opps: List[Dict]) -> List[Dict]:
    """Find arbitrage opportunities between Kalshi and BetMGM."""
    arbitrage_opps = []

    # Create lookup by team matchup
    kalshi_by_matchup = {}
    for bet in kalshi_bets:
        home = bet.get("home_team", bet.get("player", ""))
        away = bet.get("away_team", bet.get("opponent", ""))
        key = f"{home}_{away}"
        kalshi_by_matchup[key] = bet

    # Check each BetMGM game
    for betmgm in betmgm_opps:
        home = betmgm["home_team"]
        away = betmgm["away_team"]
        key = f"{home}_{away}"

        if key not in kalshi_by_matchup:
            continue

        kalshi_bet = kalshi_by_matchup[key]

        # Calculate if arbitrage exists
        # Kalshi: yes_ask / no_ask (cents)
        kalshi_yes_ask = kalshi_bet.get("yes_ask", 100)
        kalshi_no_ask = kalshi_bet.get("no_ask", 100)

        # BetMGM: american odds
        betmgm_home_odds = betmgm["home_odds"]
        betmgm_away_odds = betmgm["away_odds"]

        # Convert to decimal for arbitrage calc
        kalshi_yes_decimal = 100 / kalshi_yes_ask
        kalshi_no_decimal = 100 / kalshi_no_ask
        betmgm_home_decimal = american_to_decimal(betmgm_home_odds)
        betmgm_away_decimal = american_to_decimal(betmgm_away_odds)

        # Check all 4 combinations for arbitrage
        combos = [
            ("Kalshi YES + BetMGM Away", kalshi_yes_decimal, betmgm_away_decimal),
            ("Kalshi NO + BetMGM Home", kalshi_no_decimal, betmgm_home_decimal),
        ]

        for combo_name, odds1, odds2 in combos:
            implied_total = (1 / odds1) + (1 / odds2)
            if implied_total < 1.0:
                profit_pct = (1 / implied_total - 1) * 100
                arbitrage_opps.append(
                    {
                        "sport": betmgm["sport"],
                        "matchup": f"{away} @ {home}",
                        "combination": combo_name,
                        "profit_pct": profit_pct,
                        "odds1": odds1,
                        "odds2": odds2,
                    }
                )

    return arbitrage_opps


def compare_markets(date_str: str = None):
    """Compare all markets for a date."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"{'=' * 80}")
    print(f"📊 CROSS-MARKET ANALYSIS - {date_str}")
    print(f"{'=' * 80}\n")

    # Load data
    sports = ["nba", "ncaab", "wncaab", "tennis"]
    all_kalshi_bets = []
    for sport in sports:
        bets = load_kalshi_bets(sport, date_str)
        for bet in bets:
            bet["sport"] = sport
        all_kalshi_bets.extend(bets)

    betmgm_opps = load_betmgm_opportunities(date_str)

    print(f"✓ Loaded {len(all_kalshi_bets)} Kalshi bets")
    print(f"✓ Loaded {len(betmgm_opps)} BetMGM opportunities\n")

    # Kalshi summary
    print(f"{'=' * 80}")
    print("🎯 KALSHI BETS (Edge over Market)")
    print(f"{'=' * 80}\n")

    kalshi_by_sport = {}
    for bet in all_kalshi_bets:
        sport = bet["sport"]
        if sport not in kalshi_by_sport:
            kalshi_by_sport[sport] = []
        kalshi_by_sport[sport].append(bet)

    for sport in sorted(kalshi_by_sport.keys()):
        bets = kalshi_by_sport[sport]
        high_edge = [b for b in bets if b["edge"] >= 0.10]
        med_edge = [b for b in bets if 0.05 <= b["edge"] < 0.10]

        print(f"{sport.upper()}: {len(bets)} bets")
        print(f"  High edge (≥10%): {len(high_edge)}")
        print(f"  Med edge (5-10%): {len(med_edge)}")

        # Top 3
        top_bets = sorted(bets, key=lambda x: x["edge"], reverse=True)[:3]
        for bet in top_bets:
            home = bet.get("home_team", bet.get("player", ""))
            away = bet.get("away_team", bet.get("opponent", ""))
            print(f"    {bet['edge'] * 100:.0f}% - {bet['bet_on']}: {away} @ {home}")
        print()

    # BetMGM vs Elo summary
    print(f"{'=' * 80}")
    print("📈 BETMGM vs ELO PREDICTIONS")
    print(f"{'=' * 80}\n")

    betmgm_by_sport = {}
    for opp in betmgm_opps:
        sport = opp["sport"]
        if sport not in betmgm_by_sport:
            betmgm_by_sport[sport] = []
        betmgm_by_sport[sport].append(opp)

    for sport in sorted(betmgm_by_sport.keys()):
        opps = betmgm_by_sport[sport]
        pos_edge = [o for o in opps if o["edge"] > 0]
        neg_edge = [o for o in opps if o["edge"] < 0]

        print(f"{sport.upper()}: {len(opps)} games")
        print(f"  Elo > Market: {len(pos_edge)}")
        print(f"  Elo < Market: {len(neg_edge)}")

        # Show best Elo edges
        if pos_edge:
            top_opps = sorted(pos_edge, key=lambda x: x["edge"], reverse=True)[:3]
            print("  Top Elo edges:")
            for opp in top_opps:
                print(
                    f"    {opp['edge'] * 100:.0f}% - {opp['best_bet'].upper()}: "
                    f"{opp['away_team']} @ {opp['home_team']} "
                    f"(Elo {opp['elo_prob'] * 100:.0f}% vs Mkt {opp['betmgm_prob'] * 100:.0f}%)"
                )
        print()

    # Arbitrage opportunities
    print(f"{'=' * 80}")
    print("💰 ARBITRAGE OPPORTUNITIES (Kalshi vs BetMGM)")
    print(f"{'=' * 80}\n")

    arb_opps = find_arbitrage(all_kalshi_bets, betmgm_opps)

    if arb_opps:
        arb_opps.sort(key=lambda x: x["profit_pct"], reverse=True)
        for arb in arb_opps:
            print(f"🔥 {arb['profit_pct']:.2f}% profit - {arb['sport'].upper()}")
            print(f"   {arb['matchup']}")
            print(f"   Strategy: {arb['combination']}")
            print(f"   Odds: {arb['odds1']:.2f} x {arb['odds2']:.2f}")
            print()
    else:
        print("No arbitrage opportunities found.")
        print("Note: Real arbitrage is rare. Markets are typically efficient.\n")

    # Recommendation summary
    print(f"{'=' * 80}")
    print("✅ RECOMMENDATIONS")
    print(f"{'=' * 80}\n")

    total_kalshi = len(all_kalshi_bets)
    high_edge_kalshi = [b for b in all_kalshi_bets if b["edge"] >= 0.10]

    print(f"1. Focus on HIGH EDGE Kalshi bets: {len(high_edge_kalshi)} bets")
    print("   These show significant edge over prediction market\n")

    if arb_opps:
        print(f"2. Execute arbitrage opportunities: {len(arb_opps)} found")
        print("   Risk-free profit by betting both sides\n")

    pos_elo_edge = [o for o in betmgm_opps if o["edge"] > 0.05]
    if pos_elo_edge:
        print(f"3. Consider BetMGM bets where Elo >> Market: {len(pos_elo_edge)}")
        print("   Our model sees value BetMGM doesn't\n")

    # Value comparison
    print(f"{'=' * 80}")
    print("📌 KEY INSIGHTS")
    print(f"{'=' * 80}\n")

    print(f"• Kalshi markets: {total_kalshi} total betting opportunities")
    print(f"• BetMGM markets: {len(betmgm_opps)} games covered")
    print("• Overlap: Check for same games in both markets")
    print("• Strategy: Use Elo for edge identification, bet where we have advantage\n")


if __name__ == "__main__":
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    compare_markets(date_str)
