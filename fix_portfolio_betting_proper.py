#!/usr/bin/env python3
"""
Proper fix for portfolio_betting.py error reporting.
Distinguishes between:
- Already have position (skip, not error)
- Lock file exists from previous run (skip, not error)
- Actual API failure (error)
"""

import os

FIXED_CODE = '''    def _place_real_bet(self, kalshi_client: KalshiBetting) -> None:
        """Place a real bet via Kalshi API."""
        from kalshi_betting import MarketSide
        from pathlib import Path

        opp = self.allocation.opportunity
        market = MarketSide(ticker=opp.ticker, side=self.side, trade_date=self.date_str)

        try:
            # Check for existing positions before attempting
            match_prefix = kalshi_client.get_match_prefix(market.ticker)

            # 1. Check open positions
            open_positions = kalshi_client.get_open_positions()
            has_position = False
            for pos in open_positions:
                if kalshi_client.get_match_prefix(pos.get("ticker", "")) == match_prefix:
                    print(f"   ⚠️  Skipping: Already have open position on {match_prefix}")
                    self.results["skipped_bets"].append({
                        "ticker": opp.ticker,
                        "reason": f"Already have open position on {match_prefix}"
                    })
                    has_position = True
                    return

            # 2. Check resting orders
            resting_orders = kalshi_client.get_open_orders()
            for order in resting_orders:
                if kalshi_client.get_match_prefix(order.get("ticker", "")) == match_prefix:
                    print(f"   ⚠️  Skipping: Already have resting order on {match_prefix}")
                    self.results["skipped_bets"].append({
                        "ticker": opp.ticker,
                        "reason": f"Already have resting order on {match_prefix}"
                    })
                    has_position = True
                    return

            # 3. Check lock file - if exists from previous run, bet was already placed
            lock_dir = Path("data/order_dedup")
            lock_file = lock_dir / f"{market.ticker}_{market.side}.lock"

            if lock_file.exists():
                print(f"   ⚠️  Skipping: Lock file exists (bet likely already placed)")
                self.results["skipped_bets"].append({
                    "ticker": opp.ticker,
                    "reason": "Lock file exists - bet likely already placed in previous run"
                })
                return

            # Actually try to place bet
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
                # place_bet returned None - check why
                print(f"   ⚠️  Bet placement returned None (check logs)")
                # Check if lock was created during this attempt
                if lock_file.exists():
                    # Lock was just created, bet was likely placed
                    print(f"   ⚠️  Lock file created - recording as placed")
                    self.results["placed_bets"].append(
                        {
                            "ticker": opp.ticker,
                            "side": self.side,
                            "amount": self.allocation.bet_size,
                            "price": self.price,
                            "order_id": None,
                            "bet_line_prob": self.bet_line_prob,
                            "elo_prob": opp.elo_prob,
                            "market_prob": opp.market_prob,
                            "edge": opp.edge,
                            "expected_value": opp.expected_value,
                            "kelly_fraction": opp.kelly_fraction,
                            "sport": opp.sport,
                            "dry_run": False,
                            "note": "Lock file indicates bet was placed"
                        }
                    )
                else:
                    print("   ❌ Failed to place bet (no lock created)")
                    self.results["errors"].append(
                        {"ticker": opp.ticker, "error": "Failed to place bet - no lock created"}
                    )

        except Exception as e:
            print(f"   ❌ Error placing bet: {e}")
            import traceback
            traceback.print_exc()
            self.results["errors"].append(
                {"ticker": opp.ticker, "error": f"Exception: {e}"}
            )
'''


def apply_fix():
    """Apply proper fix to portfolio_betting.py."""
    filepath = "/opt/airflow/plugins/portfolio_betting.py"

    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return False

    with open(filepath, "r") as f:
        content = f.read()

    # Find the _place_real_bet method
    start_marker = (
        "    def _place_real_bet(self, kalshi_client: KalshiBetting) -> None:"
    )
    end_marker = "\n\n\nclass PortfolioBettingManager:"

    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("❌ Could not find _place_real_bet method")
        return False

    # Find the end of the method (next method/class definition)
    end_idx = content.find(end_marker, start_idx)
    if end_idx == -1:
        print("❌ Could not find end of method")
        return False

    # Replace the method
    new_content = content[:start_idx] + FIXED_CODE + content[end_idx:]

    # Backup original
    backup_path = filepath + ".backup_proper"
    with open(backup_path, "w") as f:
        f.write(content)
    print(f"✅ Backup created: {backup_path}")

    # Write fixed version
    with open(filepath, "w") as f:
        f.write(new_content)

    print(f"✅ Fixed {filepath}")
    return True


if __name__ == "__main__":
    print("Applying proper fix to portfolio_betting.py...")
    if apply_fix():
        print("\n✅ Fix applied successfully!")
        print("\nKey improvements:")
        print("1. Checks for existing positions/orders before attempting")
        print("2. Distinguishes between 'skip' (already have) vs 'error' (failed)")
        print("3. Checks lock file existence properly")
        print("4. Better error handling and logging")
        print("\nThis should fix the 'Failed to place bet' false positives.")
    else:
        print("\n❌ Fix failed")
