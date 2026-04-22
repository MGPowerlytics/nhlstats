"""Integration module connecting portfolio optimizer to Kalshi betting execution.

This module:
1. Uses PortfolioOptimizer to calculate optimal bet sizes
2. Places bets via KalshiBetting
3. Tracks results and updates bankroll
"""

from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
import json

from constants import ALL_SPORTS
from portfolio_optimizer import PortfolioOptimizer, PortfolioAllocation, PortfolioConfig
from kalshi_betting import KalshiBetting


@dataclass
class BetPlacementContext:
    """Context for placing a single bet within the portfolio."""

    allocation: PortfolioAllocation
    side: str
    price: float
    bet_line_prob: float
    date_str: str
    results: Dict

    def place_bet(self, kalshi_client: KalshiBetting, dry_run: bool = False) -> None:
        """Place the bet using the provided client."""
        if dry_run:
            self._place_dry_run_bet()
        else:
            self._place_real_bet(kalshi_client)

    def _place_dry_run_bet(self) -> None:
        """Simulate placing a bet (dry run)."""
        opp = self.allocation.opportunity
        print(
            f"   🔍 DRY RUN: Would place {self.side.upper()} bet for ${self.allocation.bet_size:.2f} @ {self.price}¢"
        )
        self.results["placed_bets"].append(
            {
                "ticker": opp.ticker,
                "side": self.side,
                "amount": self.allocation.bet_size,
                "price": self.price,
                "bet_line_prob": self.bet_line_prob,
                "elo_prob": opp.elo_prob,
                "market_prob": opp.market_prob,
                "edge": opp.edge,
                "expected_value": opp.expected_value,
                "kelly_fraction": opp.kelly_fraction,
                "sport": opp.sport,
                "dry_run": True,
            }
        )

    def _place_real_bet(self, kalshi_client: KalshiBetting) -> None:
        """Place a real bet via Kalshi API."""
        from kalshi_betting import MarketSide

        opp = self.allocation.opportunity
        market = MarketSide(ticker=opp.ticker, side=self.side, trade_date=self.date_str)

        order_result = kalshi_client.place_bet(
            market=market,
            amount=self.allocation.bet_size,
            price=self.price,
        )

        if order_result:
            print(f"   ✓ Bet placed: Order {order_result.get('order_id')}")
            self.results["placed_bets"].append(
                {
                    "ticker": opp.ticker,
                    "side": self.side,
                    "amount": self.allocation.bet_size,
                    "price": self.price,
                    "order_id": order_result.get("order_id"),
                    "bet_line_prob": self.bet_line_prob,
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
            self.results["errors"].append(
                {"ticker": opp.ticker, "error": "Failed to place bet"}
            )


class PortfolioBettingManager:
    """Manages portfolio-optimized betting with Kalshi."""

    # Table formatting constants
    HEADER_WIDTH = 80
    TABLE_WIDTH = 130
    SPORT_HEADER_WIDTH = 110

    def __init__(
        self,
        kalshi_client: KalshiBetting,
        config: PortfolioConfig,
        dry_run: bool = False,
    ):
        """Initialize portfolio betting manager.

        Args:
            kalshi_client: Initialized KalshiBetting client
            config: PortfolioConfig object
            dry_run: If True, don't actually place bets
        """
        self.kalshi_client = kalshi_client
        self.dry_run = dry_run
        self.config = config
        self.bankroll = config.bankroll

        # Initialize optimizer
        self.optimizer = PortfolioOptimizer(config=config)

    def process_daily_bets(
        self,
        date_str: str,
        sports: List[str] = ALL_SPORTS,
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

        print(f"\n{'=' * self.HEADER_WIDTH}")
        print(f"PORTFOLIO BETTING - {date_str}")
        print(f"{'=' * self.HEADER_WIDTH}")
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
            results["bankroll"] = self.bankroll
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
        results = self._initialize_placement_results(date_str)

        if not allocations:
            print("No bets to place.")
            return results

        self._print_betting_header()

        for i, alloc in enumerate(allocations, 1):
            self._process_single_allocation(i, alloc, date_str, results)

        self._print_placement_summary(results)
        return results

    def _initialize_placement_results(self, date_str: str) -> Dict:
        """Initialize the results dictionary for bet placement.

        Args:
            date_str: Date string for logging

        Returns:
            Dictionary with initialized placement results structure
        """
        return {
            "date": date_str,
            "dry_run": self.dry_run,
            "planned_bets": 0,  # Will be updated when allocations are processed
            "placed_bets": [],
            "skipped_bets": [],
            "errors": [],
            "bankroll": self.bankroll if hasattr(self, 'bankroll') else 0.0,
        }

    def _print_betting_header(self) -> None:
        """Print the header for the betting placement section."""
        print(f"\n{'─' * self.HEADER_WIDTH}")
        print("PLACING BETS")
        print(f"{'─' * self.HEADER_WIDTH}\n")

    def _process_single_allocation(
        self, index: int, allocation: PortfolioAllocation, date_str: str, results: Dict
    ) -> None:
        """Process a single portfolio allocation and place the bet.

        Args:
            index: Sequential number for display
            allocation: Portfolio allocation to process
            date_str: Date string for logging
            results: Results dictionary to update
        """
        opp = allocation.opportunity
        results["planned_bets"] += 1

        self._print_allocation_header(index, allocation)

        # Check market availability
        market_available, market_details = self._check_market_availability(
            opp.ticker, results
        )
        if not market_available:
            return

        # Check market status
        if not self._check_market_status(market_details, opp.ticker, results):
            return

        # Check market close time
        if not self._check_market_close_time(market_details, opp.ticker, results):
            return

        # Calculate bet line probability
        side = "yes"  # Since tickers are specific to the outcome, we always buy YES
        price = self._resolve_order_price(market_details, allocation, side)
        if price is None:
            print("   ❌ No ask price available")
            results["errors"].append(
                {"ticker": opp.ticker, "error": "No ask price available"}
            )
            return
        bet_line_prob = self._calculate_bet_line_probability(side, price)

        # Create placement context
        ctx = BetPlacementContext(
            allocation=allocation,
            side=side,
            price=price,
            bet_line_prob=bet_line_prob,
            date_str=date_str,
            results=results,
        )

        # Place the bet
        self._place_single_bet(ctx)

    def _print_allocation_header(
        self, index: int, allocation: PortfolioAllocation
    ) -> None:
        """Print header information for a single allocation.

        Args:
            index: Sequential number for display
            allocation: Portfolio allocation being processed
        """
        opp = allocation.opportunity
        print(f"{index}. {opp.ticker} - ${allocation.bet_size:.2f}")
        print(f"   {opp.team} vs {opp.opponent} ({opp.sport.upper()})")

    def _check_market_availability(
        self, ticker: str, results: Dict
    ) -> Tuple[bool, Optional[Dict]]:
        """Check if market details can be fetched.

        Args:
            ticker: Market ticker to check
            results: Results dictionary to update with errors

        Returns:
            Tuple of (market_available, market_details)
        """
        market_details = self.kalshi_client.get_market_details(ticker)
        if not market_details:
            print("   ❌ Cannot fetch market details")
            results["errors"].append(
                {"ticker": ticker, "error": "Cannot fetch market details"}
            )
            return False, None
        return True, market_details

    def _check_market_status(
        self, market_details: Dict, ticker: str, results: Dict
    ) -> bool:
        """Check if market is active.

        Args:
            market_details: Market details dictionary
            ticker: Market ticker
            results: Results dictionary to update with skips

        Returns:
            True if market is active, False otherwise
        """
        status = market_details.get("status")
        if status != "active":
            print(f"   ⚠️  Market not active (status: {status})")
            results["skipped_bets"].append(
                {"ticker": ticker, "reason": f"Market status: {status}"}
            )
            return False
        return True

    def _check_market_close_time(
        self, market_details: Dict, ticker: str, results: Dict
    ) -> bool:
        """Check if market has closed.

        Args:
            market_details: Market details dictionary
            ticker: Market ticker
            results: Results dictionary to update with skips

        Returns:
            True if market is still open, False if closed
        """
        close_time = market_details.get("close_time")
        if close_time:
            try:
                from datetime import datetime, timezone

                close_dt = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) >= close_dt:
                    print("   ⚠️  Market closed")
                    results["skipped_bets"].append(
                        {"ticker": ticker, "reason": "Market closed"}
                    )
                    return False
            except Exception:
                # If we can't parse the close time, assume market is open
                pass
        return True

    def _calculate_bet_line_probability(self, side: str, price: float) -> float:
        """Calculate implied probability from market price.

        Args:
            side: Bet side ("yes" or "no")
            price: Market price in cents

        Returns:
            Implied probability as decimal (0.0-1.0)
        """
        # Kalshi yes/no prices are quoted directly in cents of probability for
        # the side being purchased (e.g. YES at 37c implies 37%).
        return price / 100

    def _resolve_order_price(
        self,
        market_details: Dict,
        allocation: PortfolioAllocation,
        side: str,
    ) -> Optional[int]:
        """Prefer the live Kalshi ask over the stored recommendation price."""
        price_keys = {
            "yes": ("yes_ask", allocation.opportunity.yes_ask),
            "no": ("no_ask", allocation.opportunity.no_ask),
        }
        market_key, fallback_price = price_keys.get(
            side, ("yes_ask", allocation.opportunity.yes_ask)
        )

        for candidate in (market_details.get(market_key), fallback_price):
            if candidate in (None, ""):
                continue
            try:
                candidate_price = int(round(float(candidate)))
            except (TypeError, ValueError):
                continue
            if candidate_price > 0:
                return candidate_price

        return None

    def _place_single_bet(
        self,
        ctx: BetPlacementContext,
    ) -> None:
        """Place a single bet (dry run or real).

        Args:
            ctx: BetPlacementContext object
        """
        ctx.place_bet(self.kalshi_client, self.dry_run)

    def _print_placement_summary(self, results: Dict) -> None:
        """Print summary of bet placement results.

        Args:
            results: Results dictionary with placement statistics
        """
        print(f"\n{'─' * self.HEADER_WIDTH}")
        print("PLACEMENT SUMMARY")
        print(f"{'─' * self.HEADER_WIDTH}")
        print(f"Planned: {results['planned_bets']}")
        print(f"Placed:  {len(results['placed_bets'])}")
        print(f"Skipped: {len(results['skipped_bets'])}")
        print(f"Errors:  {len(results['errors'])}")

    def _get_rankings(self, sport: str) -> Dict[str, str]:
        """Get rankings and ratings for all teams in a sport.

        Returns:
            Dict mapping team name to "Ranking (Rating)" string
        """
        import pandas as pd

        ratings_files = []
        if sport.lower() == "tennis":
            ratings_files = [
                "data/atp_current_elo_ratings.csv",
                "data/wta_current_elo_ratings.csv",
            ]
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

    def _print_table_header(self) -> None:
        """Print the header for the betting table."""
        print(f"\n{'=' * self.TABLE_WIDTH}")
        print("PORTFOLIO OPTIMIZED BETTING RECOMMENDATIONS")
        print(f"{'=' * self.TABLE_WIDTH}")

        header = (
            f"{'Matchup (Home vs Away)':<35} {'Elo Rankings (Rating)':<40} "
            f"{'Elo Prob':>10} {'Kalshi Prob':>12} {'Edge':>10}"
        )
        print(header)
        print("─" * self.SPORT_HEADER_WIDTH)

    def _print_table_summary(self, allocations: List[PortfolioAllocation]) -> None:
        """Print summary statistics for the portfolio allocations."""
        if not allocations:
            return

        total_bet = sum(a.bet_size for a in allocations)
        total_exp_return = sum(
            a.bet_size * a.opportunity.expected_value for a in allocations
        )
        avg_edge = (
            sum(a.opportunity.edge for a in allocations) / len(allocations)
            if allocations
            else 0
        )

        print(f"\nSummary:")
        print(f"  Total Recommended Bets: {len(allocations)}")
        print(f"  Total Capital Allocated: ${total_bet:.2f}")
        print(f"  Expected Portfolio Return: ${total_exp_return:+.2f}")
        print(f"  Average Edge: {avg_edge * 100:.1f}%")
        print(f"{'=' * self.TABLE_WIDTH}\n")

    def _format_allocation_row(
        self, alloc: PortfolioAllocation, sport_rankings: Dict[str, str]
    ) -> str:
        """Format a single allocation row for display."""
        opp = alloc.opportunity
        matchup = opp.format_matchup()
        rankings_str = opp.format_rankings(sport_rankings)

        # Probabilities
        elo_pct = f"{opp.elo_prob * 100:.1f}%"
        kalshi_pct = f"{opp.market_prob * 100:.1f}%"
        edge_pct = f"{opp.edge * 100:+.1f}%"

        return (
            f"{matchup:<35} {rankings_str:<40} "
            f"{elo_pct:>10} {kalshi_pct:>12} {edge_pct:>10}"
        )

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

        self._print_table_header()

        # Deduplicate by ticker before printing
        seen_tickers = set()
        unique_allocs = []
        for alloc in allocations:
            if alloc.opportunity.ticker not in seen_tickers:
                unique_allocs.append(alloc)
                seen_tickers.add(alloc.opportunity.ticker)

        # Sort by sport then by edge (to highlight best value)
        sorted_allocs = sorted(
            unique_allocs, key=lambda a: (a.opportunity.sport, -a.opportunity.edge)
        )

        current_sport = None
        sport_rankings = {}

        for alloc in sorted_allocs:
            opp = alloc.opportunity

            # Sport separator and rankings load
            if opp.sport != current_sport:
                if current_sport is not None:
                    print("─" * self.SPORT_HEADER_WIDTH)
                current_sport = opp.sport
                print(f"[{current_sport.upper()}]")
                sport_rankings = self._get_rankings(current_sport)

            print(self._format_allocation_row(alloc, sport_rankings))

        print("─" * self.SPORT_HEADER_WIDTH)
        self._print_table_summary(allocations)


def parse_args():
    """Parse command line arguments."""
    import sys

    # Get date
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Get dry run flag
    dry_run = "--dry-run" in sys.argv or "--test" in sys.argv
    return date_str, dry_run


def get_kalshi_client() -> Optional[KalshiBetting]:
    """Initialize Kalshi client using the runtime secret contract."""
    try:
        return KalshiBetting()
    except Exception as e:
        print(f"❌ Failed to initialize Kalshi client: {e}")
        return None


def main():
    """Main execution entry point."""
    date_str, dry_run = parse_args()

    # Initialize Kalshi client
    kalshi_client = get_kalshi_client()
    if not kalshi_client:
        return

    try:
        # Initialize portfolio manager with standard configuration
        config = PortfolioConfig(
            bankroll=kalshi_client.get_balance()[0],
            max_daily_risk_pct=MAX_DAILY_RISK_PCT,  # 25% max daily risk
            kelly_fraction=KELLY_FRACTION,  # Quarter Kelly
            min_bet_size=2.0,
            max_bet_size=MAX_BET_SIZE,
            max_single_bet_pct=MAX_SINGLE_BET_PCT,
            min_edge=MIN_EDGE_FOR_BET,
            min_confidence=MIN_CONFIDENCE_FOR_BET,
        )
        manager = PortfolioBettingManager(
            kalshi_client=kalshi_client,
            config=config,
            dry_run=dry_run,
        )

        # Process daily bets
        manager.process_daily_bets(date_str)

        print("\n✓ Complete")

    except Exception as e:
        print(f"❌ Execution error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
