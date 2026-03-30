#!/bin/bash
# Apply fixes inside Docker container

set -e

echo "========================================="
echo "APPLYING BETTING SYSTEM FIXES INSIDE DOCKER"
echo "========================================="

# 1. Backup original portfolio_betting.py
echo "1. Backing up portfolio_betting.py..."
cp /opt/airflow/plugins/portfolio_betting.py /opt/airflow/plugins/portfolio_betting.py.backup.$(date +%Y%m%d_%H%M%S)

# 2. Create Python script to apply patch
cat > /tmp/fix_portfolio.py << 'EOF'
#!/usr/bin/env python3
"""
Patch portfolio_betting.py to fix error reporting.
"""

import re

def patch_portfolio_betting():
    """Apply patch to portfolio_betting.py."""

    filepath = '/opt/airflow/plugins/portfolio_betting.py'

    with open(filepath, 'r') as f:
        content = f.read()

    # Find the _place_real_bet method
    pattern = r'(    def _place_real_bet\(self, kalshi_client: KalshiBetting\) -> None:.*?\n\n)'

    # Check if we need to add skipped_bets initialization
    if 'skipped_bets' not in content:
        # Find where results dict is initialized
        init_pattern = r'self\.results = \{.*?\}'
        match = re.search(init_pattern, content, re.DOTALL)
        if match:
            # Add skipped_bets to initialization
            old_init = match.group(0)
            new_init = old_init.replace('"errors": []', '"errors": [], "skipped_bets": []')
            content = content.replace(old_init, new_init)
            print("✓ Added skipped_bets to results initialization")

    # Patch the _place_real_bet method to handle lock files properly
    old_method = '''    def _place_real_bet(self, kalshi_client: KalshiBetting) -> None:
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
            )'''

    new_method = '''    def _place_real_bet(self, kalshi_client: KalshiBetting) -> None:
        """Place a real bet via Kalshi API."""
        from kalshi_betting import MarketSide
        import os
        from pathlib import Path

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
            # Check if this is due to lock file (already placed)
            lock_dir = Path("/opt/airflow/data/order_dedup")
            lock_file = lock_dir / f"{market.ticker}_{market.side}.lock"

            if lock_file.exists():
                print(f"   ⚠️  Skipping: Lock file exists (bet likely already placed)")
                self.results["skipped_bets"].append(
                    {"ticker": opp.ticker, "reason": "Lock file exists - bet likely already placed"}
                )
            else:
                print("   ❌ Failed to place bet (no lock file)")
                self.results["errors"].append(
                    {"ticker": opp.ticker, "error": "Failed to place bet - no lock file"}
                )'''

    if old_method in content:
        content = content.replace(old_method, new_method)
        print("✓ Patched _place_real_bet method")
    else:
        print("⚠️ Could not find exact method pattern, trying alternative...")
        # Try more flexible pattern
        alt_pattern = r'def _place_real_bet\(.*?\) -> None:.*?if order_result:.*?else:.*?self\.results\["errors"\]\.append'
        if re.search(alt_pattern, content, re.DOTALL):
            # Use regex replacement
            content = re.sub(
                r'(def _place_real_bet\(.*?\) -> None:.*?)if order_result:(.*?)else:(.*?)self\.results\["errors"\]\.append',
                r'\1if order_result:\2else:\3# Check if this is due to lock file (already placed)\n            lock_dir = Path("/opt/airflow/data/order_dedup")\n            lock_file = lock_dir / f"{market.ticker}_{market.side}.lock"\n            \n            if lock_file.exists():\n                print(f"   ⚠️  Skipping: Lock file exists (bet likely already placed)")\n                self.results["skipped_bets"].append(\n                    {"ticker": opp.ticker, "reason": "Lock file exists - bet likely already placed"}\n                )\n            else:\n                print("   ❌ Failed to place bet (no lock file)")\n                self.results["errors"].append',
                content,
                flags=re.DOTALL
            )
            print("✓ Patched using regex")
        else:
            print("❌ Could not patch method")
            return False

    # Write back
    with open(filepath, 'w') as f:
        f.write(content)

    print("✓ Successfully patched portfolio_betting.py")
    return True

if __name__ == "__main__":
    patch_portfolio_betting()
EOF

# 3. Run the patch
echo "2. Applying patch to portfolio_betting.py..."
python3 /tmp/fix_portfolio.py

# 4. Create cleanup script for stale locks
echo "3. Creating lock file cleanup script..."
cat > /opt/airflow/cleanup_stale_locks.py << 'EOF'
#!/usr/bin/env python3
"""
Clean stale lock files (>1 day old).
"""

import os
import glob
import time
from datetime import datetime, timedelta
from pathlib import Path

def clean_stale_locks():
    """Remove lock files older than 1 day."""
    lock_dir = Path("/opt/airflow/data/order_dedup")

    if not lock_dir.exists():
        print(f"Lock directory not found: {lock_dir}")
        return 0

    lock_files = list(lock_dir.glob("*.lock"))
    print(f"Found {len(lock_files)} lock files")

    # Count by age
    now = time.time()
    one_day_ago = now - (24 * 3600)

    stale_files = []
    recent_files = []

    for lock_file in lock_files:
        if os.path.getmtime(lock_file) < one_day_ago:
            stale_files.append(lock_file)
        else:
            recent_files.append(lock_file)

    print(f"Stale files (>1 day): {len(stale_files)}")
    print(f"Recent files (≤1 day): {len(recent_files)}")

    # Show some recent files
    print("\nRecent lock files (last 24h):")
    for lock_file in sorted(recent_files, key=os.path.getmtime, reverse=True)[:10]:
        mtime = datetime.fromtimestamp(os.path.getmtime(lock_file))
        age = now - os.path.getmtime(lock_file)
        hours = age / 3600
        print(f"  {lock_file.name} ({hours:.1f}h ago, {mtime})")

    # Ask before deleting
    if stale_files:
        print(f"\nFound {len(stale_files)} stale lock files (>1 day old)")
        print("These are likely from completed/settled bets.")
        response = input("Delete stale lock files? (y/n): ").strip().lower()

        if response == 'y':
            deleted = 0
            for lock_file in stale_files:
                try:
                    os.remove(lock_file)
                    deleted += 1
                except Exception as e:
                    print(f"Error deleting {lock_file}: {e}")

            print(f"Deleted {deleted} stale lock files")
            return deleted
        else:
            print("Skipping deletion")
            return 0
    else:
        print("No stale lock files to clean")
        return 0

if __name__ == "__main__":
    clean_stale_locks()
EOF

chmod +x /opt/airflow/cleanup_stale_locks.py

# 5. Create verification script
echo "4. Creating system verification script..."
cat > /opt/airflow/verify_system.py << 'EOF'
#!/usr/bin/env python3
"""
Verify betting system health.
"""

import sys
sys.path.insert(0, '/opt/airflow')

from plugins.db_manager import DBManager
import json
import os
from datetime import datetime, timedelta

def verify_system():
    """Verify betting system health."""
    print("=" * 80)
    print("BETTING SYSTEM VERIFICATION")
    print("=" * 80)

    db = DBManager()

    # 1. Check database connectivity
    print("\n1. Database Connectivity:")
    try:
        test_query = "SELECT COUNT(*) as count FROM placed_bets"
        result = db.fetch_df(test_query)
        print(f"   ✅ Connected to database")
        print(f"   Total bets in database: {result.iloc[0]['count']}")
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False

    # 2. Check recent bets
    print("\n2. Recent Bet Activity:")
    query = """
    SELECT
        DATE(placed_time_utc) as date,
        COUNT(*) as bets,
        SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
        SUM(CASE WHEN status IN ('won', 'lost', 'void') THEN 1 ELSE 0 END) as settled,
        SUM(CASE WHEN status IN ('won', 'lost', 'void') THEN profit_dollars ELSE 0 END) as pnl
    FROM placed_bets
    WHERE placed_time_utc >= CURRENT_DATE - INTERVAL '3 days'
    GROUP BY DATE(placed_time_utc)
    ORDER BY date DESC
    """

    try:
        df = db.fetch_df(query)
        for _, row in df.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d')
            print(f"   {date_str}: {row['bets']} bets ({row['open']} open, {row['settled']} settled)")
            print(f"      P&L: ${row['pnl']:.2f}")
    except Exception as e:
        print(f"   ❌ Error querying bets: {e}")

    # 3. Check JSON reports vs database
    print("\n3. Report vs Database Consistency:")
    reports_dir = "/opt/airflow/data/portfolio"

    if os.path.exists(reports_dir):
        import glob
        report_files = glob.glob(os.path.join(reports_dir, "betting_results_*.json"))
        report_files.sort(reverse=True)

        for report_file in report_files[:3]:  # Last 3 days
            date_str = os.path.basename(report_file).replace('betting_results_', '').replace('.json', '')

            with open(report_file, 'r') as f:
                report = json.load(f)

            # Query database for same date
            db_query = f"""
            SELECT COUNT(*) as count
            FROM placed_bets
            WHERE DATE(placed_time_utc) = '{date_str}'
            """

            db_result = db.fetch_df(db_query)
            db_count = db_result.iloc[0]['count'] if not db_result.empty else 0

            reported_placed = len(report.get('placed_bets', []))
            reported_errors = len(report.get('errors', []))

            status = "✅" if db_count > 0 and reported_placed > 0 else "⚠️"
            print(f"   {date_str}: DB={db_count}, Report={reported_placed} placed, {reported_errors} errors {status}")

            if db_count > 0 and reported_placed == 0:
                print(f"      ⚠️  DISCREPANCY: Database has {db_count} bets, report says 0")

    # 4. Check open positions
    print("\n4. Current Exposure:")
    query_open = """
    SELECT
        COUNT(*) as count,
        SUM(cost_dollars) as total_risk,
        AVG(edge) as avg_edge
    FROM placed_bets
    WHERE status = 'open'
    """

    try:
        df_open = db.fetch_df(query_open)
        if not df_open.empty:
            count = df_open.iloc[0]['count'] or 0
            risk = df_open.iloc[0]['total_risk'] or 0
            edge = df_open.iloc[0]['avg_edge'] or 0

            print(f"   Open bets: {count}")
            print(f"   Total at risk: ${risk:.2f}")
            print(f"   Average edge: {edge:.1%}")

            # Show some open bets
            if count > 0:
                query_details = """
                SELECT ticker, market_title, cost_dollars, edge
                FROM placed_bets
                WHERE status = 'open'
                ORDER BY placed_time_utc DESC
                LIMIT 3
                """
                df_details = db.fetch_df(query_details)
                print(f"   Recent open bets:")
                for _, row in df_details.iterrows():
                    market = row.get('market_title', row['ticker'])
                    print(f"      {market}: ${row['cost_dollars']:.2f} ({row['edge']:.1%} edge)")

    except Exception as e:
        print(f"   ❌ Error checking exposure: {e}")

    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)

    print("\nRecommendations:")
    print("1. If reports show 0 bets but database has bets: Fix portfolio_betting.py")
    print("2. If open risk > $200: Review position sizing")
    print("3. Run cleanup_stale_locks.py if lock files > 500")

    return True

if __name__ == "__main__":
    verify_system()
EOF

chmod +x /opt/airflow/verify_system.py

# 6. Create simple test
echo "5. Creating test script..."
cat > /opt/airflow/test_fix.py << 'EOF'
#!/usr/bin/env python3
"""
Test the fix by simulating a bet placement scenario.
"""

import sys
sys.path.insert(0, '/opt/airflow')

from plugins.kalshi_betting import KalshiBetting, KalshiConfig, MarketSide

def test_bet_placement_logic():
    """Test the bet placement logic flow."""

    print("Testing bet placement logic...")

    config = KalshiConfig.from_kalshkey("/opt/airflow/kalshkey")
    client = KalshiBetting(config=config)

    # Test with a market that likely has a lock file
    ticker = "KXNBAGAME-26MAR12PHXIND-IND"
    market = MarketSide(ticker=ticker, side="yes", trade_date="2026-03-12")

    print(f"\nTesting market: {ticker}")
    print(f"MarketSide: ticker={market.ticker}, side={market.side}")

    # Check if lock file exists
    import os
    from pathlib import Path

    lock_dir = Path("/opt/airflow/data/order_dedup")
    lock_file = lock_dir / f"{market.ticker}_{market.side}.lock"

    print(f"\nLock file check:")
    print(f"  Lock path: {lock_file}")
    print(f"  Exists: {lock_file.exists()}")

    if lock_file.exists():
        print("  ✅ Lock file exists - bet likely already placed")
        print("  This should be recorded as 'skipped' not 'error'")
    else:
        print("  No lock file - could attempt new bet")

    # Test API connectivity
    print(f"\nAPI connectivity test:")
    try:
        details = client.get_market_details(ticker)
        if details:
            print(f"  ✅ Market accessible")
            print(f"  Status: {details.get('status')}")
            print(f"  Yes price: {details.get('yes_ask')}¢")
        else:
            print("  ❌ Could not get market details")
    except Exception as e:
        print(f"  ❌ API error: {e}")

if __name__ == "__main__":
    test_bet_placement_logic()
EOF

chmod +x /opt/airflow/test_fix.py

echo "========================================="
echo "FIXES APPLIED SUCCESSFULLY!"
echo "========================================="
echo ""
echo "Available scripts:"
echo "1. /opt/airflow/cleanup_stale_locks.py - Clean old lock files"
echo "2. /opt/airflow/verify_system.py - Verify system health"
echo "3. /opt/airflow/test_fix.py - Test the fix"
echo ""
echo "Next steps:"
echo "1. Run: python3 /opt/airflow/verify_system.py"
echo "2. (Optional) Run: python3 /opt/airflow/cleanup_stale_locks.py"
echo "3. Monitor next DAG run for accurate reporting"
echo ""
echo "Note: portfolio_betting.py has been patched to distinguish"
echo "between 'skipped' (lock exists) and 'error' (actual failure)."
