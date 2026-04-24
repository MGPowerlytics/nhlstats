#!/usr/bin/env python3
"""
Update CLV data for closed markets.

This script runs regularly to:
1. Check for placed bets on markets that have closed
2. Update closing_line_prob based on market results
3. Calculate CLV = bet_line_prob - closing_line_prob

Should be run daily after markets close.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List, Tuple

from plugins.db_manager import default_db
from plugins.kalshi_betting import KalshiBetting, KalshiConfig


def _initialize_kalshi_client() -> Optional[KalshiBetting]:
    """Initialize the Kalshi betting client."""
    try:
        config = KalshiConfig.from_env(
            max_bet_size=5.0,
            production=True,
        )
        return KalshiBetting(config=config)
    except Exception as e:
        print(f"❌ Failed to initialize Kalshi client: {e}")
        return None


def _get_closing_probs(market: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Determine closing probabilities based on market result."""
    status = market.get("status")
    result = market.get("result")

    # Only process closed/finalized markets with results
    if status not in ["closed", "finalized"] or not result:
        return None

    if result == "yes":
        return {"yes": 1.0, "no": 0.0}
    elif result == "no":
        return {"yes": 0.0, "no": 1.0}

    print(f"  ⚠️  Unknown result '{result}'")
    return None


def _update_bet_clv(ticker: str, side: str, closing_prob: float) -> bool:
    """Update a single bet's CLV in the database."""
    update_query = """
        UPDATE placed_bets
        SET closing_line_prob = :closing_prob,
            clv = bet_line_prob - :closing_prob,
            updated_at = CURRENT_TIMESTAMP
        WHERE ticker = :ticker
        AND side = :side
        AND (closing_line_prob IS NULL OR clv IS NULL)
    """
    try:
        default_db.execute(
            update_query,
            {"closing_prob": closing_prob, "ticker": ticker, "side": side},
        )
        return True
    except Exception as e:
        print(f"  ❌ Error updating {ticker} ({side}): {e}")
        return False


def update_clv_for_closed_markets(days_back: int = 7) -> Dict[str, Any]:
    """
    Update CLV data for bets on markets that have closed.
    """
    print("🔄 Updating CLV data for closed markets...")

    client = _initialize_kalshi_client()
    if not client:
        return {"error": "Failed to initialize Kalshi client"}

    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    query = """
        SELECT DISTINCT ticker, side
        FROM placed_bets
        WHERE placed_date >= :cutoff_date
        AND status IN ('won', 'lost', 'settled')
        AND (closing_line_prob IS NULL OR clv IS NULL)
        AND ticker IS NOT NULL
    """

    bets_df = default_db.fetch_df(query, {"cutoff_date": cutoff_date})
    if bets_df.empty:
        return {"processed": 0, "updated": 0}

    print(f"📊 Found {len(bets_df)} unique (ticker, side) pairs needing updates")

    updated_count = 0
    error_count = 0
    processed_tickers = set()

    # Iterate over unique tickers to avoid redundant API calls
    for ticker in bets_df["ticker"].unique():
        try:
            market = client.get_market_details(ticker)
            if not market:
                print(f"  ⚠️  Could not fetch market {ticker}")
                continue

            probs = _get_closing_probs(market)
            if not probs:
                continue

            # Update all sides for this ticker present in our bets_df
            ticker_sides = bets_df[bets_df["ticker"] == ticker]["side"].tolist()
            for side in ticker_sides:
                if side in probs:
                    if _update_bet_clv(ticker, side, probs[side]):
                        updated_count += 1
                        print(
                            f"  ✅ Updated {ticker} ({side}): closing_prob = {probs[side]}"
                        )
                    else:
                        error_count += 1

        except Exception as e:
            print(f"  ❌ Error processing {ticker}: {e}")
            error_count += 1

    print(f"🎯 CLV update complete: {updated_count} updated, {error_count} errors")
    return {"processed": len(bets_df), "updated": updated_count, "errors": error_count}


def main():
    """Run CLV update for closed markets."""
    results = update_clv_for_closed_markets(days_back=30)

    print("\n📊 CLV Update Summary:")
    print(f"  Processed: {results.get('processed', 0)}")
    print(f"  Updated: {results.get('updated', 0)}")
    print(f"  Errors: {results.get('errors', 0)}")


if __name__ == "__main__":
    main()
