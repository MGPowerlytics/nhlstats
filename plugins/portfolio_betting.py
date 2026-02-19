"""Integration module connecting portfolio optimizer to Kalshi betting execution.

This module:
1. Uses PortfolioOptimizer to calculate optimal bet sizes
2. Places bets via KalshiBetting
3. Tracks results and updates bankroll
"""

from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import json

from portfolio_optimizer import PortfolioOptimizer, PortfolioAllocation
from kalshi_betting import KalshiBetting


class PortfolioBettingManager:
    """Manages portfolio-optimized betting with Kalshi."""

    def __init__(
        self,
        kalshi_client: KalshiBetting,
        initial_bankroll: Optional[float] = None,
        max_daily_risk_pct: float = 0.10,
        kelly_fraction: float = 0.25,
        min_bet_size: float = 2.0,
        max_bet_size: float = 50.0,
        max_single_bet_pct: float = 0.05,
        min_edge: float = 0.05,
        min_confidence: float = 0.68,
        excluded_segments: Optional[List[Tuple[str, str]]] = None,
        dry_run: bool = False,
    ):
        """Initialize portfolio betting manager.

        Args:
            kalshi_client: Initialized KalshiBetting client
            initial_bankroll: Initial bankroll (if None, fetches from Kalshi)
            max_daily_risk_pct: Max percentage of bankroll to risk daily
            kelly_fraction: Fraction of Kelly to use
            min_bet_size: Minimum bet in dollars
            max_bet_size: Maximum bet in dollars
            max_single_bet_pct: Max percentage per bet
            min_edge: Minimum edge required
            min_confidence: Minimum Elo probability required
            excluded_segments: List of (sport, confidence) tuples to skip.
                              Example: [("NHL", "MEDIUM"), ("TENNIS", "LOW")]
            dry_run: If True, don't actually place bets
        """
        self.kalshi_client = kalshi_client
        self.dry_run = dry_run

        # Get current bankroll
        if initial_bankroll is None:
            balance, _ = kalshi_client.get_balance()
            self.bankroll = balance
        else:
            self.bankroll = initial_bankroll

        # Initialize optimizer
        self.optimizer = PortfolioOptimizer(
            bankroll=self.bankroll,
            max_daily_risk_pct=max_daily_risk_pct,
            kelly_fraction=kelly_fraction,
            min_bet_size=min_bet_size,
            max_bet_size=max_bet_size,
            max_single_bet_pct=max_single_bet_pct,
            min_edge=min_edge,
            min_confidence=min_confidence,
            excluded_segments=excluded_segments,
        )

    def process_daily_bets(
        self,
        date_str: str,
        sports: List[str] = ["nhl", "nba", "mlb", "nfl", "ncaab", "tennis"],
        output_dir: Optional[Path] = None,
    ) -> Dict:
        """Process and place all bets for a given date.

        Args:
            date_str: Date in YYYY-MM-DD format
            sports: List of sports to consider
            output_dir: Directory to save reports (default: data/portfolio)

        Returns:
            Dictionary with results
        """
        if output_dir is None:
            output_dir = Path("data/portfolio")
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'=' * 80}")
        print(f"PORTFOLIO BETTING - {date_str}")
        print(f"{'=' * 80}")
        print(f"Bankroll: ${self.bankroll:,.2f}")
        print(f"Dry Run: {self.dry_run}\n")

        # Optimize portfolio
        allocations, summary = self.optimizer.optimize_daily_bets(date_str, sports)

        # Generate and save report
        report = self.optimizer.generate_bet_report(allocations, summary)
        report_file = output_dir / f"betting_report_{date_str}.txt"
        report_file.write_text(report)
        print(f"📄 Report saved to: {report_file}\n")

        # Place bets
        results = self._place_optimized_bets(allocations, date_str)

        # Print comprehensive betting table
        self._print_comprehensive_table(allocations, results)

        # Save results
        results_file = output_dir / f"betting_results_{date_str}.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {results_file}")

        # Update bankroll
        if not self.dry_run and results["placed_bets"]:
            balance, _ = self.kalshi_client.get_balance()
            self.bankroll = balance
            print(f"💰 Updated bankroll: ${self.bankroll:,.2f}")

        return results

    def _place_optimized_bets(
        self, allocations: List[PortfolioAllocation], date_str: str
    ) -> Dict:
        """Place bets based on portfolio allocations.

        Args:
            allocations: List of portfolio allocations
            date_str: Date string for logging

        Returns:
            Dictionary with placement results
        """
        results = {
            "date": date_str,
            "dry_run": self.dry_run,
            "planned_bets": len(allocations),
            "placed_bets": [],
            "skipped_bets": [],
            "errors": [],
        }

        if not allocations:
            print("No bets to place.")
            return results

        print(f"\n{'─' * 80}")
        print("PLACING BETS")
        print(f"{'─' * 80}\n")

        for i, alloc in enumerate(allocations, 1):
            opp = alloc.opportunity

            print(f"{i}. {opp.ticker} - ${alloc.bet_size:.2f}")
            print(f"   {opp.team} vs {opp.opponent} ({opp.sport.upper()})")

            # Check if market is still active
            market_details = self.kalshi_client.get_market_details(opp.ticker)
            if not market_details:
                print("   ❌ Cannot fetch market details")
                results["errors"].append(
                    {"ticker": opp.ticker, "error": "Cannot fetch market details"}
                )
                continue

            status = market_details.get("status")
            if status != "active":
                print(f"   ⚠️  Market not active (status: {status})")
                results["skipped_bets"].append(
                    {"ticker": opp.ticker, "reason": f"Market status: {status}"}
                )
                continue

            # Check if market has closed
            close_time = market_details.get("close_time")
            if close_time:
                try:
                    from datetime import datetime, timezone

                    close_dt = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) >= close_dt:
                        print("   ⚠️  Market closed")
                        results["skipped_bets"].append(
                            {"ticker": opp.ticker, "reason": "Market closed"}
                        )
                        continue
                except Exception:
                    pass

            # Determine side (yes/no)
            # Since tickers are specific to the outcome (e.g. "...-BOS"), we always buy YES
            side = "yes"
            price = opp.yes_ask

            # Calculate bet_line_prob (implied probability at time of bet placement)
            # For Kalshi markets: probability = (100 - price) / 100 for the side we're betting on
            # If we're betting YES at 30¢, implied prob of YES winning = 70%
            bet_line_prob = (100 - price) / 100 if side == "yes" else price / 100

            # Place bet
            if self.dry_run:
                print(
                    f"   🔍 DRY RUN: Would place {side.upper()} bet for ${alloc.bet_size:.2f} @ {price}¢"
                )
                results["placed_bets"].append(
                    {
                        "ticker": opp.ticker,
                        "side": side,
                        "amount": alloc.bet_size,
                        "price": price,
                        "bet_line_prob": bet_line_prob,
                        "elo_prob": opp.elo_prob,
                        "market_prob": opp.market_prob,
                        "edge": opp.edge,
                        "expected_value": opp.expected_value,
                        "kelly_fraction": opp.kelly_fraction,
                        "sport": opp.sport,
                        "dry_run": True,
                    }
                )
            else:
                order_result = self.kalshi_client.place_bet(
                    ticker=opp.ticker,
                    side=side,
                    amount=alloc.bet_size,
                    price=price,
                    trade_date=date_str,
                )

                if order_result:
                    print(f"   ✓ Bet placed: Order {order_result.get('order_id')}")
                    results["placed_bets"].append(
                        {
                            "ticker": opp.ticker,
                            "side": side,
                            "amount": alloc.bet_size,
                            "price": price,
                            "order_id": order_result.get("order_id"),
                            "bet_line_prob": bet_line_prob,
                            "elo_prob": opp.elo_prob,
                            "market_prob": opp.market_prob,
                            "edge": opp.edge,
                            "expected_value": opp.expected_value,
                            "kelly_fraction": opp.kelly_fraction,
                            "sport": opp.sport,
                            "dry_run": False,
                        }
                    )
                else:
                    print("   ❌ Failed to place bet")
                    results["errors"].append(
                        {"ticker": opp.ticker, "error": "Failed to place bet"}
                    )

        print(f"\n{'─' * 80}")
        print("PLACEMENT SUMMARY")
        print(f"{'─' * 80}")
        print(f"Planned: {results['planned_bets']}")
        print(f"Placed:  {len(results['placed_bets'])}")
        print(f"Skipped: {len(results['skipped_bets'])}")
        print(f"Errors:  {len(results['errors'])}")

        return results

    def _get_rankings(self, sport: str) -> Dict[str, str]:
        """Get rankings and ratings for all teams in a sport.

        Returns:
            Dict mapping team name to "Ranking (Rating)" string
        """
        import pandas as pd

        ratings_files = []
        if sport.lower() == "tennis":
            ratings_files = ["data/atp_current_elo_ratings.csv", "data/wta_current_elo_ratings.csv"]
        else:
            ratings_files = [f"data/{sport.lower()}_current_elo_ratings.csv"]

        all_ratings = {}
        for f in ratings_files:
            path = Path(f)
            if path.exists():
                try:
                    df = pd.read_csv(path)
                    for _, row in df.iterrows():
                        all_ratings[row["team"]] = float(row["rating"])
                except Exception:
                    pass

        if not all_ratings:
            return {}

        # Sort by rating descending
        sorted_teams = sorted(all_ratings.items(), key=lambda x: x[1], reverse=True)

        rankings = {}
        for rank, (team, rating) in enumerate(sorted_teams, 1):
            rankings[team] = f"#{rank} ({rating:.0f})"

        return rankings

    def _print_comprehensive_table(
        self, allocations: List[PortfolioAllocation], results: Dict
    ) -> None:
        """Print comprehensive betting table with all probabilities.

        Args:
            allocations: List of portfolio allocations
            results: Results from bet placement
        """
        if not allocations:
            return

        # Build set of placed tickers for quick lookup
        placed_tickers = {b["ticker"] for b in results.get("placed_bets", [])}
        skipped_tickers = {b["ticker"] for b in results.get("skipped_bets", [])}
        error_tickers = {b["ticker"] for b in results.get("errors", [])}

        print(f"\n{'=' * 130}")
        print("PORTFOLIO OPTIMIZED BETTING RECOMMENDATIONS")
        print(f"{'=' * 130}")

        # Header matches user's request exactly
        header = (
            f"{'Matchup (Home vs Away)':<35} {'Elo Rankings (Rating)':<40} "
            f"{'Elo Prob':>10} {'Kalshi Prob':>12} {'Edge':>10}"
        )
        print(header)
        print("─" * 110)

        # Deduplicate by ticker before printing
        seen_tickers = set()
        unique_allocs = []
        for alloc in allocations:
            if alloc.opportunity.ticker not in seen_tickers:
                unique_allocs.append(alloc)
                seen_tickers.add(alloc.opportunity.ticker)

        # Sort by sport then by edge (to highlight best value)
        sorted_allocs = sorted(
            unique_allocs,
            key=lambda a: (a.opportunity.sport, -a.opportunity.edge)
        )

        current_sport = None
        sport_rankings = {}

        for alloc in sorted_allocs:
            opp = alloc.opportunity

            # Sport separator and rankings load
            if opp.sport != current_sport:
                if current_sport is not None:
                    print("─" * 110)
                current_sport = opp.sport
                print(f"[{current_sport.upper()}]")
                sport_rankings = self._get_rankings(current_sport)

            # Matchup
            matchup = f"{opp.team} vs {opp.opponent}"
            if len(matchup) > 33:
                matchup = matchup[:30] + "..."

            # Rankings (Rating)
            # Use explicit home/away team names from the opportunity object
            h_team = opp.home_team
            a_team = opp.away_team

            h_rating = opp.home_rating
            a_rating = opp.away_rating

            h_info = sport_rankings.get(h_team, f"({h_rating:.0f})")
            a_info = sport_rankings.get(a_team, f"({a_rating:.0f})")

            # Formatting as "HOME #Rank (Rating) vs AWAY #Rank (Rating)"
            rankings_str = f"{h_team} {h_info} vs {a_team} {a_info}"
            if len(rankings_str) > 38:
                rankings_str = rankings_str[:37] + "..."

            # Probabilities
            elo_pct = f"{opp.elo_prob * 100:.1f}%"
            kalshi_pct = f"{opp.market_prob * 100:.1f}%"
            edge_pct = f"{opp.edge * 100:+.1f}%"

            # Print row
            row = (
                f"{matchup:<35} {rankings_str:<40} "
                f"{elo_pct:>10} {kalshi_pct:>12} {edge_pct:>10}"
            )
            print(row)

        print("─" * 110)

        # Summary stats
        total_bet = sum(a.bet_size for a in allocations)
        total_exp_return = sum(a.bet_size * a.opportunity.expected_value for a in allocations)
        avg_edge = sum(a.opportunity.edge for a in allocations) / len(allocations) if allocations else 0

        print(f"\nSummary:")
        print(f"  Total Recommended Bets: {len(allocations)}")
        print(f"  Total Capital Allocated: ${total_bet:.2f}")
        print(f"  Expected Portfolio Return: ${total_exp_return:+.2f}")
        print(f"  Average Edge: {avg_edge * 100:.1f}%")
        print(f"{'=' * 130}\n")



def main():
    """Example usage."""
    import sys
    from pathlib import Path

    # Get date
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Get dry run flag
    dry_run = "--dry-run" in sys.argv or "--test" in sys.argv

    # Load Kalshi credentials from kalshkey file
    kalshkey_path = Path("kalshkey")
    if not kalshkey_path.exists():
        kalshkey_path = Path("/opt/airflow/kalshkey")

    if not kalshkey_path.exists():
        print("❌ kalshkey file not found")
        return

    content = kalshkey_path.read_text()

    # Extract API key ID
    api_key_id = None
    for line in content.split("\n"):
        if "API key id:" in line:
            api_key_id = line.split(":", 1)[1].strip()
            break

    if not api_key_id:
        print("❌ Could not find API key ID in kalshkey file")
        return

    # Save private key to temp PEM file for KalshiBetting
    private_key_lines = []
    in_key = False
    for line in content.split("\n"):
        if "-----BEGIN RSA PRIVATE KEY-----" in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if "-----END RSA PRIVATE KEY-----" in line:
            break

    temp_key_file = Path("kalshi_private_key.pem")
    temp_key_file.write_text("\n".join(private_key_lines))

    try:
        # Initialize Kalshi client
        kalshi_client = KalshiBetting(
            api_key_id=api_key_id, private_key_path=str(temp_key_file)
        )

        # Initialize portfolio manager
        manager = PortfolioBettingManager(
            kalshi_client=kalshi_client,
            max_daily_risk_pct=0.25,  # 25% max daily risk
            kelly_fraction=0.25,  # Quarter Kelly
            min_bet_size=2.0,
            max_bet_size=50.0,
            max_single_bet_pct=0.05,
            min_edge=0.05,
            min_confidence=0.68,
            dry_run=dry_run,
        )

        # Process daily bets
        manager.process_daily_bets(date_str)

        print("\n✓ Complete")

    finally:
        # Clean up temp key file
        if temp_key_file.exists():
            temp_key_file.unlink()


if __name__ == "__main__":
    main()
