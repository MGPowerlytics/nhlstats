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
from pathlib import Path
from typing import Dict

try:
    from db_manager import default_db
    from kalshi_betting import KalshiBetting
except ImportError:
    from plugins.db_manager import default_db
    from plugins.kalshi_betting import KalshiBetting


def load_kalshi_credentials() -> tuple[str, str]:
    """Load Kalshi API credentials."""
    kalshkey_file = Path("/opt/airflow/kalshkey")
    if not kalshkey_file.exists():
        kalshkey_file = Path("kalshkey")

    if not kalshkey_file.exists():
        raise FileNotFoundError("Kalshi credentials file not found")

    content = kalshkey_file.read_text()

    # Extract API key ID
    api_key_id = None
    for line in content.split("\n"):
        if "API key id:" in line:
            api_key_id = line.split(":", 1)[1].strip()
            break

    if not api_key_id:
        raise ValueError("Could not find API key ID")

    # Extract private key
    private_key_lines = []
    in_key = False
    for line in content.split("\n"):
        if "-----BEGIN RSA PRIVATE KEY-----" in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if "-----END RSA PRIVATE KEY-----" in line:
            break

    private_key = "\n".join(private_key_lines)
    return api_key_id, private_key


def update_clv_for_closed_markets(days_back: int = 7) -> Dict[str, int]:
    """
    Update CLV data for bets on markets that have closed.

    Args:
        days_back: How many days back to check for closed markets

    Returns:
        Dict with counts of updated records
    """
    print("🔄 Updating CLV data for closed markets...")

    # Load Kalshi client
    try:
        api_key_id, private_key = load_kalshi_credentials()
        temp_key_file = Path("/tmp/kalshi_private_key.pem")
        temp_key_file.write_text(private_key)
        temp_key_file.chmod(0o600)

        client = KalshiBetting(
            api_key_id=api_key_id,
            private_key_path=str(temp_key_file),
            max_bet_size=5.0,
            production=True,
        )
    except Exception as e:
        print(f"❌ Failed to initialize Kalshi client: {e}")
        return {"error": str(e)}

    # Get bets that need CLV updates (markets closed but no closing_line_prob)
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
    print(f"📊 Found {len(bets_df)} unique tickers needing CLV updates")

    if bets_df.empty:
        return {"processed": 0, "updated": 0}

    updated_count = 0
    error_count = 0

    # Process each unique ticker
    for _, row in bets_df.iterrows():
        ticker = row["ticker"]

        try:
            # Get market details
            market = client.get_market_details(ticker)
            if not market:
                print(f"  ⚠️  Could not fetch market {ticker}")
                continue

            status = market.get("status")
            result = market.get("result")

            # Only process closed/finalized markets with results
            if status not in ["closed", "finalized"] or not result:
                continue

            # Calculate closing probability based on result
            # For Kalshi binary markets: result is 'yes' or 'no'
            # If result is 'yes', closing prob of yes = 1.0, no = 0.0
            # If result is 'no', closing prob of yes = 0.0, no = 1.0
            if result == "yes":
                closing_prob_yes = 1.0
                closing_prob_no = 0.0
            elif result == "no":
                closing_prob_yes = 0.0
                closing_prob_no = 1.0
            else:
                print(f"  ⚠️  Unknown result '{result}' for {ticker}")
                continue

            # Update all bets on this ticker
            for _, bet_row in bets_df[bets_df["ticker"] == ticker].iterrows():
                side = bet_row["side"]

                # Get the closing prob for this bet's side
                if side == "yes":
                    closing_line_prob = closing_prob_yes
                elif side == "no":
                    closing_line_prob = closing_prob_no
                else:
                    continue

                # Update the bet with closing line and CLV
                update_query = """
                    UPDATE placed_bets
                    SET closing_line_prob = :closing_prob,
                        clv = bet_line_prob - :closing_prob,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE ticker = :ticker
                    AND side = :side
                    AND closing_line_prob IS NULL
                """

                default_db.execute(
                    update_query,
                    {"closing_prob": closing_line_prob, "ticker": ticker, "side": side},
                )

                updated_count += 1
                print(
                    f"  ✅ Updated {ticker} ({side}): closing_prob = {closing_line_prob}"
                )

        except Exception as e:
            print(f"  ❌ Error processing {ticker}: {e}")
            error_count += 1

    # Clean up temp key file
    try:
        temp_key_file.unlink()
    except Exception:
        pass

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
