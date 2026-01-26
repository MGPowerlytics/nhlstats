#!/usr/bin/env python3
import sys
import os
import re
from pathlib import Path
import pandas as pd

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))
from kalshi_markets import fetch_tennis_markets
from plugins.elo import TennisEloRating
from the_odds_api import TheOddsAPI


def normalize_name(name):
    """Normalize names for matching: 'Carlos Alcaraz' -> 'alcaraz' or 'Alcaraz C.' -> 'alcaraz'"""
    if not name:
        return ""
    name = name.lower()
    # Remove everything after a space if it's an initial (e.g. 'Alcaraz C.' -> 'Alcaraz')
    # Or take last part if it's full name (e.g. 'Carlos Alcaraz' -> 'Alcaraz')
    parts = name.split()
    if not parts:
        return ""

    if len(parts[-1]) <= 2 and "." in parts[-1]:
        # 'Alcaraz C.' format
        last_name = parts[0]
    else:
        # 'Carlos Alcaraz' format
        last_name = parts[-1]

    return re.sub(r"[^a-z]", "", last_name)


def get_elo_name(full_name, elo_names):
    """Find the Elo name matching a full name."""
    norm_full = normalize_name(full_name)
    for elo_name in elo_names:
        if normalize_name(elo_name) == norm_full:
            return elo_name
    return None


def find_value():
    print("🎾 Finding current Kalshi Tennis Value vs Sharp Odds & Elo...")

    # 1. Fetch Kalshi Markets
    kalshi_markets = fetch_tennis_markets()
    if not kalshi_markets:
        print("❌ No Kalshi markets found.")
        return

    # 2. Fetch External Odds
    api_key_file = Path("data/odds_api_key")
    if not api_key_file.exists():
        api_key_file = Path("odds_api_key")
    api_key = (
        api_key_file.read_text().strip()
        if api_key_file.exists()
        else os.getenv("ODDS_API_KEY")
    )

    odds_api = TheOddsAPI(api_key=api_key)
    # Patch the keys to include Tennis
    odds_api.SPORT_KEYS["tennis_atp"] = "tennis_atp_aus_open_singles"
    odds_api.SPORT_KEYS["tennis_wta"] = "tennis_wta_aus_open_singles"

    atp_odds = odds_api.fetch_markets("tennis_atp")
    wta_odds = odds_api.fetch_markets("tennis_wta")
    all_external_odds = atp_odds + wta_odds

    # 3. Load Elo Ratings
    elo = TennisEloRating()
    atp_elo_df = pd.read_csv("data/atp_current_elo_ratings.csv")
    wta_elo_df = pd.read_csv("data/wta_current_elo_ratings.csv")

    atp_elo_names = atp_elo_df["team"].tolist()
    wta_elo_names = wta_elo_df["team"].tolist()

    atp_ratings = dict(zip(atp_elo_df["team"], atp_elo_df["rating"]))
    wta_ratings = dict(zip(wta_elo_df["team"], wta_elo_df["rating"]))

    elo.atp_ratings = atp_ratings
    elo.wta_ratings = wta_ratings

    print(
        f"\n📊 Comparing {len(kalshi_markets)} Kalshi outcomes vs {len(all_external_odds)} external matches..."
    )
    print("-" * 100)
    print(f"{'MATCHUP':<40} | {'KALSHI':<7} | {'SHARP':<7} | {'ELO':<7} | {'EDGE'}")
    print("-" * 100)

    found_opportunities = 0

    for km in kalshi_markets:
        title = km.get("title", "")
        ticker = km.get("ticker", "")
        # Yes price is what we pay for 1 contract (pays $1 if win)
        yes_price = km.get("yes_ask", 0) / 100.0
        if yes_price <= 0:
            continue

        # Extract players from title
        match = re.search(r"win the (.*?) vs (.*?) (?:match|:)", title)
        if not match:
            match = re.search(r"win the (.*?) vs (.*?) match", title)
        if not match:
            continue

        p1 = match.group(1).strip()
        p2 = match.group(2).strip()
        if p2.endswith(" match"):
            p2 = p2[:-6].strip()

        # Ticker outcome matching
        ticker_parts = ticker.split("-")
        outcome_code = ticker_parts[-1]

        def get_last_name_code(name):
            parts = name.split()
            return parts[-1][:3].upper() if parts else name[:3].upper()

        bet_on = p1 if outcome_code == get_last_name_code(p1) else p2
        opponent = p2 if bet_on == p1 else p1

        # Find match in external odds
        ext_match = None
        norm_p1 = normalize_name(p1)
        norm_p2 = normalize_name(p2)

        for em in all_external_odds:
            em_home = normalize_name(em["home_team"])
            em_away = normalize_name(em["away_team"])
            if (norm_p1 == em_home and norm_p2 == em_away) or (
                norm_p1 == em_away and norm_p2 == em_home
            ):
                ext_match = em
                break

        # Get Elo prob
        tour = "atp" if "ATP" in ticker else "wta"
        elo_names = atp_elo_names if tour == "atp" else wta_elo_names

        elo_p1_name = get_elo_name(bet_on, elo_names)
        elo_p2_name = get_elo_name(opponent, elo_names)

        elo_prob = 0.5
        if elo_p1_name and elo_p2_name:
            elo_prob = elo.predict(elo_p1_name, elo_p2_name, tour=tour)

        # Get Sharp prob (Pinnacle preferred)
        sharp_prob = None
        if ext_match:
            # Try to find Pinnacle
            pin = (
                ext_match["bookmakers"].get("pinnacle")
                or ext_match["bookmakers"].get("betmgm")
                or list(ext_match["bookmakers"].values())[0]
            )
            if pin:
                if normalize_name(ext_match["home_team"]) == normalize_name(bet_on):
                    sharp_prob = pin["home_prob"]
                else:
                    sharp_prob = pin["away_prob"]

        # Output comparison
        matchup_str = f"{bet_on} vs {opponent}"
        kalshi_prob = yes_price

        # Edge vs Sharp or Elo
        comparison_prob = sharp_prob if sharp_prob else elo_prob
        edge = comparison_prob - kalshi_prob

        if edge > 0.03:  # 3% edge
            found_opportunities += 1
            sharp_str = f"{sharp_prob:.1%}" if sharp_prob else "N/A"
            print(
                f"{matchup_str[:40]:<40} | {kalshi_prob:6.1%} | {sharp_str:7} | {elo_prob:6.1%} | {edge:+.1%}"
            )

    if found_opportunities == 0:
        print("No opportunities found with >3% edge currently.")


if __name__ == "__main__":
    find_value()
