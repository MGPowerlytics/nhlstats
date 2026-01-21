#!/usr/bin/env python3
import sys
import os
import time
from pathlib import Path
from datetime import datetime, timezone

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))
from kalshi_betting import KalshiBetting
from kalshi_markets import load_kalshi_credentials

def place_manual_tennis_bets():
    print("🎾 Placing 1 unit bets on high-value Kalshi Tennis markets...")

    # Target tickers identified in previous step (All YES outcomes)
    # Strategy: High-edge markets vs Sharp/Elo
    target_tickers = [
        "KXATPMATCH-26JAN20VANSHA-SHA", # Shang vs Van de Zandschulp (+17.6% edge)
        "KXATPMATCH-26JAN20MAJMAR-MAJ", # Majchrzak vs Marozsan (+6.7% edge)
        "KXATPMATCH-26JAN20PAUTIR-TIR", # Tirante vs Paul (+6.1% edge)
        "KXATPMATCH-26JAN20FARRUB-FAR", # Faria vs Rublev (+6.0% edge)
        "KXATPMATCH-26JAN20MEDDE-MED",  # Medjedovic vs de Minaur (+5.0% edge)
        "KXATPMATCH-26JAN21MACTSI-TSI", # Tsitsipas vs Machac (+4.2% edge)
        "KXWTAMATCH-26JAN21KALGRA-GRA", # Grabher vs Kalinskaya (+4.2% edge)
        "KXWTAMATCH-26JAN20BOUSWI-BOU"  # Bouzkova vs Swiatek (+4.2% edge)
    ]

    # Load credentials
    api_key_id, private_key_path = load_kalshi_credentials()

    # Write temp pem file
    pem_file = Path("/tmp/kalshi_private_key.pem")
    pem_file.write_text(private_key_path)

    try:
        # Initialize betting client (limit max_bet to $5 just in case)
        client = KalshiBetting(
            api_key_id=api_key_id,
            private_key_path=str(pem_file),
            max_bet_size=5.0,
            production=True
        )

        results = []
        for ticker in target_tickers:
            print(f"\n🎯 Processing {ticker}...")
            # We bet 1 contract (count=1).
            # place_bet takes amount in DOLLARS, so we need to fetch price first.
            market = client.get_market_details(ticker)
            if not market:
                print(f"  ❌ Skipping: Market not found")
                continue

            price = market.get('yes_ask')
            if not price:
                print(f"  ❌ Skipping: No ask price")
                continue

            # Place bet for 1 contract
            # To get 1 contract, amount must be at least price/100
            # We add $0.01 buffer to avoid rounding issues
            amount = (price + 1) / 100.0

            print(f"  Price: {price}¢ | Betting: ${amount:.2f}")

            res = client.place_bet(ticker, 'yes', amount, price=price)
            if res:
                results.append(ticker)

            time.sleep(1) # Rate limit protection

        print(f"\n✅ Finished. Placed {len(results)}/{len(target_tickers)} bets.")

        # Sync to database
        print("\n🔄 Syncing new bets to database...")
        from bet_tracker import sync_bets_to_database
        sync_bets_to_database()

    finally:
        if pem_file.exists(): pem_file.unlink()

if __name__ == "__main__":
    place_manual_tennis_bets()
