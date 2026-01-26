import sys
from pathlib import Path

sys.path.append(str(Path.cwd()))
sys.path.append(str(Path.cwd() / "plugins"))

from plugins.ncaab_elo_rating import calculate_current_elo_ratings as calc_ncaab
from plugins.wncaab_elo_rating import calculate_current_elo_ratings as calc_wncaab
from plugins.nba_elo_rating import load_nba_games_from_json, NBAEloRating
from plugins.odds_comparator import OddsComparator
from plugins.db_manager import DBManager
import json


def calc_nba():
    print("Loading NBA games...")
    df = load_nba_games_from_json()
    if df.empty:
        print("Warning: No NBA games found.")
        return NBAEloRating()  # Return empty logic

    elo = NBAEloRating()
    df = df.sort_values("game_date")

    for _, game in df.iterrows():
        elo.update(game["home_team"], game["away_team"], game["home_win"])

    return elo


def main():
    db = DBManager()
    comparator = OddsComparator(db)
    target_date = "2026-01-22"

    # --- NBA ---
    print("\nCalculating NBA Ratings...")
    try:
        nba_elo = calc_nba()
        print("Finding NBA Opportunities...")
        nba_opps = comparator.find_opportunities(
            sport="nba",
            elo_ratings=nba_elo.ratings,
            elo_system=nba_elo,
            threshold=0.73,
            min_edge=0.05,
        )
        print(f"Found {len(nba_opps)} NBA opportunities.")
        if nba_opps:
            with open(f"data/nba/bets_{target_date}.json", "w") as f:
                json.dump(nba_opps, f, indent=2, default=str)
    except Exception as e:
        print(f"NBA Gen Error: {e}")

    # --- NCAAB ---
    print("Calculating NCAAB Ratings...")
    ncaab_elo = calc_ncaab()
    print("Finding NCAAB Opportunities...")
    ncaab_opps = comparator.find_opportunities(
        sport="ncaab",
        elo_ratings=ncaab_elo.ratings,  # Pass dict
        elo_system=ncaab_elo,  # Pass object too (comparator uses predict method)
        threshold=0.72,
        min_edge=0.05,
    )
    print(f"Found {len(ncaab_opps)} NCAAB opportunities.")
    if ncaab_opps:
        with open(f"data/ncaab/bets_{target_date}.json", "w") as f:
            json.dump(ncaab_opps, f, indent=2, default=str)
        print("Sample:", ncaab_opps[0])

    # --- WNCAAB ---
    print("\nCalculating WNCAAB Ratings...")
    wncaab_elo = calc_wncaab()
    print("Finding WNCAAB Opportunities...")
    wncaab_opps = comparator.find_opportunities(
        sport="wncaab",
        elo_ratings=wncaab_elo.ratings,
        elo_system=wncaab_elo,
        threshold=0.72,
        min_edge=0.05,
    )
    print(f"Found {len(wncaab_opps)} WNCAAB opportunities.")
    if wncaab_opps:
        with open(f"data/wncaab/bets_{target_date}.json", "w") as f:
            json.dump(wncaab_opps, f, indent=2, default=str)
        print("Sample:", wncaab_opps[0])


if __name__ == "__main__":
    main()
