#!/usr/bin/env python3
"""
Debug what place_bet returns.
"""

import sys

sys.path.insert(0, "/opt/airflow")

from plugins.kalshi_betting import KalshiBetting, KalshiConfig, MarketSide


def test_place_bet():
    """Test place_bet with a settled market."""

    config = KalshiConfig.from_kalshkey("/opt/airflow/kalshkey")
    client = KalshiBetting(config=config)

    # Use a market that's likely settled (March 10 game)
    ticker = "KXNBAGAME-26MAR10CHIGSW-GSW"  # Chicago at Golden State March 10

    print(f"Testing place_bet with {ticker}")

    market = MarketSide(ticker=ticker, side="yes", trade_date="2026-03-10")

    try:
        # Try to place tiny bet - will likely fail because market settled
        result = client.place_bet(market=market, amount=0.01, price=50)
        print(f"Result type: {type(result)}")
        print(f"Result: {result}")

        if isinstance(result, dict):
            print(f"Result keys: {list(result.keys())}")
            for k, v in result.items():
                print(f"  {k}: {v}")

    except Exception as e:
        print(f"Exception: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_place_bet()
