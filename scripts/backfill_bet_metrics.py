import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging to show info
logging.basicConfig(level=logging.INFO)

try:
    from plugins.bet_tracker import backfill_bet_metrics

    if __name__ == "__main__":
        print("Starting backfill of bet metrics...")
        backfill_bet_metrics()
        print("Backfill complete.")
except ImportError as e:
    print(f"Error importing backfill_bet_metrics: {e}")
    # Try adding plugins explicitly
    sys.path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../plugins"))
    )
    from bet_tracker import backfill_bet_metrics

    print("Retry import successful.")
    backfill_bet_metrics()
