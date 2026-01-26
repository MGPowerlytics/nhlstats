#!/usr/bin/env python3
"""
CLV (Closing Line Value) Tracker

This module tracks closing line values to validate that our model beats the market.

CLV = Bet Line Probability - Closing Line Probability

- Positive CLV means we got better odds than the closing line (good!)
- Negative CLV means the market moved against us (bad)

Consistent positive CLV is the #1 indicator of long-term profitability.
"""

import sys
import os

sys.path.append(os.path.dirname(__file__))

from datetime import datetime, timedelta
from typing import Dict, Optional
from db_manager import default_db


class CLVTracker:
    """Track and analyze closing line values for bets."""

    def __init__(self, odds_api_key: Optional[str] = None):
        self.odds_api_key = odds_api_key

    def record_bet_line(self, bet_id: str, market_prob: float):
        """Record the line we bet at."""
        query = """
            UPDATE placed_bets
            SET bet_line_prob = :market_prob, updated_at = CURRENT_TIMESTAMP
            WHERE bet_id = :bet_id
        """
        default_db.execute(query, {"market_prob": market_prob, "bet_id": bet_id})

    def update_closing_line(self, bet_id: str, closing_prob: float):
        """Update the closing line for a bet."""
        # Get the bet line probability
        query = "SELECT bet_line_prob FROM placed_bets WHERE bet_id = :bet_id"
        result = default_db.execute(query, {"bet_id": bet_id})
        bet_line = result.fetchone()

        if bet_line and bet_line[0]:
            clv = bet_line[0] - closing_prob

            # Update with closing line and CLV
            update_query = """
                UPDATE placed_bets
                SET closing_line_prob = :closing_prob, clv = :clv, updated_at = CURRENT_TIMESTAMP
                WHERE bet_id = :bet_id
            """
            default_db.execute(
                update_query,
                {"closing_prob": closing_prob, "clv": clv, "bet_id": bet_id},
            )

            print(
                f"  CLV for {bet_id}: {clv:+.2%} ({bet_line[0]:.1%} bet → {closing_prob:.1%} close)"
            )

    def fetch_closing_lines_from_kalshi(self, days_back: int = 7):
        """Fetch recent Kalshi markets to get closing lines."""
        # TODO: Implement using Kalshi API to get market close prices
        pass

    def fetch_closing_lines_from_sbr(self, days_back: int = 7):
        """Fetch closing lines from SBR/OddsPortal (TODO: implement)."""
        # TODO: Implement SBR/OddsPortal scraping for closing lines
        # This should replace the Odds API method
        print("⚠️  SBR/OddsPortal integration not yet implemented")
        pass

    def analyze_clv(self, days_back: int = 30) -> Dict:
        """
        Analyze CLV performance over recent bets.

        Returns dict with:
        - avg_clv: Average CLV across all bets
        - positive_clv_pct: Percentage of bets with positive CLV
        - clv_by_sport: CLV broken down by sport
        """
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        # Overall CLV
        overall_query = """
            SELECT
                COUNT(*) as num_bets,
                AVG(clv) as avg_clv,
                SUM(CASE WHEN clv > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as positive_clv_pct
            FROM placed_bets
            WHERE placed_date >= :cutoff_date
            AND clv IS NOT NULL
        """
        overall = default_db.execute(
            overall_query, {"cutoff_date": cutoff_date}
        ).fetchone()

        # By sport
        by_sport_query = """
            SELECT
                sport,
                COUNT(*) as num_bets,
                AVG(clv) as avg_clv,
                SUM(CASE WHEN clv > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as positive_clv_pct
            FROM placed_bets
            WHERE placed_date >= :cutoff_date
            AND clv IS NOT NULL
            GROUP BY sport
            ORDER BY avg_clv DESC
        """
        by_sport = default_db.execute(
            by_sport_query, {"cutoff_date": cutoff_date}
        ).fetchall()

        if not overall or overall[0] == 0:
            return {"num_bets": 0, "message": "No CLV data available"}

        return {
            "num_bets": overall[0],
            "avg_clv": overall[1],
            "positive_clv_pct": overall[2],
            "by_sport": [
                {
                    "sport": row[0],
                    "num_bets": row[1],
                    "avg_clv": row[2],
                    "positive_clv_pct": row[3],
                }
                for row in by_sport
            ],
        }

    def print_clv_report(self, days_back: int = 30):
        """Print a formatted CLV report."""
        analysis = self.analyze_clv(days_back)

        if analysis.get("num_bets", 0) == 0:
            print("❌ No CLV data available")
            return

        print(f"\n{'=' * 60}")
        print(f"CLV ANALYSIS - Last {days_back} Days")
        print(f"{'=' * 60}\n")

        print("Overall Performance:")
        print(f"  Total Bets: {analysis['num_bets']}")
        print(f"  Average CLV: {analysis['avg_clv']:+.2%}")
        print(f"  Positive CLV %: {analysis['positive_clv_pct']:.1f}%")

        if analysis["avg_clv"] > 0:
            print("  ✅ POSITIVE CLV - Model is beating closing lines!")
        else:
            print("  ❌ NEGATIVE CLV - Model is NOT beating closing lines")

        print("\nBy Sport:")
        for sport_data in analysis["by_sport"]:
            indicator = "✅" if sport_data["avg_clv"] > 0 else "❌"
            print(
                f"  {indicator} {sport_data['sport'].upper():8} | "
                f"Bets: {sport_data['num_bets']:3} | "
                f"CLV: {sport_data['avg_clv']:+.2%} | "
                f"Positive: {sport_data['positive_clv_pct']:.0f}%"
            )

        print(f"\n{'=' * 60}\n")


def main():
    """Run CLV analysis."""
    tracker = CLVTracker()

    # Fetch closing lines for recent bets (using SBR/OddsPortal instead of Odds API)
    # tracker.fetch_closing_lines_from_sbr(days_back=7)

    # Print CLV report
    tracker.print_clv_report(days_back=30)


if __name__ == "__main__":
    main()
