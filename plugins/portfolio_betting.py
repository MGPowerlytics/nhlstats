"""Integration module connecting portfolio optimizer to Kalshi betting execution.

This module:
1. Uses PortfolioOptimizer to calculate optimal bet sizes
2. Places bets via KalshiBetting
3. Tracks results and updates bankroll
"""

from typing import Dict, List, Optional
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

        print(f'\n{"="*80}')
        print(f"PORTFOLIO BETTING - {date_str}")
        print(f'{"="*80}')
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

        print(f'\n{"─"*80}')
        print(f"PLACING BETS")
        print(f'{"─"*80}\n')

        for i, alloc in enumerate(allocations, 1):
            opp = alloc.opportunity

            print(f"{i}. {opp.ticker} - ${alloc.bet_size:.2f}")
            print(f"   {opp.team} vs {opp.opponent} ({opp.sport.upper()})")

            # Check if market is still active
            market_details = self.kalshi_client.get_market_details(opp.ticker)
            if not market_details:
                print(f"   ❌ Cannot fetch market details")
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
                        print(f"   ⚠️  Market closed")
                        results["skipped_bets"].append(
                            {"ticker": opp.ticker, "reason": "Market closed"}
                        )
                        continue
                except:
                    pass

            # Determine side (yes/no)
            if opp.bet_on == "home":
                side = "yes"
                price = opp.yes_ask
            else:
                side = "no"
                price = opp.no_ask

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
                        "dry_run": True,
                    }
                )
            else:
                order_result = self.kalshi_client.place_bet(
                    ticker=opp.ticker, side=side, amount=alloc.bet_size, price=price
                )

                if order_result:
                    print(f'   ✓ Bet placed: Order {order_result.get("order_id")}')
                    results["placed_bets"].append(
                        {
                            "ticker": opp.ticker,
                            "side": side,
                            "amount": alloc.bet_size,
                            "price": price,
                            "order_id": order_result.get("order_id"),
                            "dry_run": False,
                        }
                    )
                else:
                    print(f"   ❌ Failed to place bet")
                    results["errors"].append(
                        {"ticker": opp.ticker, "error": "Failed to place bet"}
                    )

        print(f'\n{"─"*80}')
        print(f"PLACEMENT SUMMARY")
        print(f'{"─"*80}')
        print(f'Planned: {results["planned_bets"]}')
        print(f'Placed:  {len(results["placed_bets"])}')
        print(f'Skipped: {len(results["skipped_bets"])}')
        print(f'Errors:  {len(results["errors"])}')

        return results


def main():
    """Example usage."""
    import sys
    from datetime import datetime
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
        results = manager.process_daily_bets(date_str)

        print(f"\n✓ Complete")

    finally:
        # Clean up temp key file
        if temp_key_file.exists():
            temp_key_file.unlink()


if __name__ == "__main__":
    main()
