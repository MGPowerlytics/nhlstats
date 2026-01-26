from sqlalchemy import text
from plugins.db_manager import DBManager
from plugins.kalshi_markets import (
    fetch_nba_markets,
    fetch_ncaab_markets,
    fetch_wncaab_markets,
)


def check_db_games(date_str):
    print(f"\nChecking DB for games on {date_str}...")
    db = DBManager()
    engine = db.get_engine()

    queries = {
        "nba": "SELECT COUNT(*) FROM nba_games WHERE game_date = :date",
        "ncaab": "SELECT COUNT(*) FROM ncaab_games WHERE game_date = :date",
        "wncaab": "SELECT COUNT(*) FROM wncaab_games WHERE game_date = :date",
        "unified": "SELECT COUNT(*) FROM unified_games WHERE game_date = :date",
    }

    for sport, query in queries.items():
        try:
            with engine.connect() as conn:
                count = conn.execute(text(query), {"date": date_str}).scalar()
                print(f"  {sport.upper()}: {count} games found.")
        except Exception as e:
            print(f"  {sport.upper()}: Error querying - {e}")


def check_kalshi_markets():
    print("\nChecking Kalshi Markets (Live Fetch)...")

    # NBA
    print("\n--- NBA ---")
    try:
        markets = fetch_nba_markets()
        print(f"Fetched {len(markets)} NBA markets.")
        today_markets = [m for m in markets if "26JAN22" in m.get("ticker", "")]
        print(f"  Found {len(today_markets)} markets for TODAY (26JAN22).")
        if today_markets:
            print(f"  Sample: {today_markets[0]['ticker']}")
        else:
            print("  NO MARKETS FOR TODAY found in fetch result.")
    except Exception as e:
        print(f"Error fetching NBA: {e}")

    # NCAAB
    print("\n--- NCAAB ---")
    try:
        markets = fetch_ncaab_markets()
        print(f"Fetched {len(markets)} NCAAB markets.")
        today_markets = [m for m in markets if "26JAN22" in m.get("ticker", "")]
        print(f"  Found {len(today_markets)} markets for TODAY (26JAN22).")
    except Exception as e:
        print(f"Error fetching NCAAB: {e}")

    # WNCAAB
    print("\n--- WNCAAB ---")
    try:
        markets = fetch_wncaab_markets()
        print(f"Fetched {len(markets)} WNCAAB markets.")
        today_markets = [m for m in markets if "26JAN22" in m.get("ticker", "")]
        print(f"  Found {len(today_markets)} markets for TODAY (26JAN22).")
    except Exception as e:
        print(f"Error fetching WNCAAB: {e}")


if __name__ == "__main__":
    target_date = "2026-01-22"
    check_db_games(target_date)
    check_kalshi_markets()
