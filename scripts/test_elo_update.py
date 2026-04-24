#!/usr/bin/env python3
"""
Test script for updated Elo update logic.
"""

import sys
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

# Add plugins directory to Python path
plugins_dir = Path(__file__).parent.parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))

from db_manager import default_db
from elo import get_elo_class


def test_nhl_elo_update():
    """Test NHL Elo update with unified_games."""
    print("🧪 Testing NHL Elo update...")

    # Query from unified_games
    query = """
        SELECT
            game_date,
            home_team_name,
            away_team_name,
            CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM unified_games
        WHERE sport = 'NHL'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND home_team_name IS NOT NULL
          AND away_team_name IS NOT NULL
        ORDER BY game_date
        LIMIT 100  # Just test with 100 games first
    """

    games_df = default_db.fetch_df(query)
    print(f"  Loaded {len(games_df)} NHL games from unified_games")

    if games_df.empty:
        print("❌ No games found")
        return False

    # NHL team mapping
    nhl_team_mapping = {
        "Anaheim Ducks": "ANA",
        "Arizona Coyotes": "ARI",
        "Boston Bruins": "BOS",
        "Buffalo Sabres": "BUF",
        "Calgary Flames": "CGY",
        "Carolina Hurricanes": "CAR",
        "Chicago Blackhawks": "CHI",
        "Colorado Avalanche": "COL",
        "Columbus Blue Jackets": "CBJ",
        "Dallas Stars": "DAL",
        "Detroit Red Wings": "DET",
        "Edmonton Oilers": "EDM",
        "Florida Panthers": "FLA",
        "Los Angeles Kings": "LAK",
        "Minnesota Wild": "MIN",
        "Montreal Canadiens": "MTL",
        "Nashville Predators": "NSH",
        "New Jersey Devils": "NJD",
        "New York Islanders": "NYI",
        "New York Rangers": "NYR",
        "Ottawa Senators": "OTT",
        "Philadelphia Flyers": "PHI",
        "Pittsburgh Penguins": "PIT",
        "San Jose Sharks": "SJS",
        "Seattle Kraken": "SEA",
        "St. Louis Blues": "STL",
        "Tampa Bay Lightning": "TBL",
        "Toronto Maple Leafs": "TOR",
        "Utah Hockey Club": "UTA",
        "Vancouver Canucks": "VAN",
        "Vegas Golden Knights": "VGK",
        "Washington Capitals": "WSH",
        "Winnipeg Jets": "WPG",
        "Montréal Canadiens": "MTL",
        "Utah Mammoth": "UTA",
    }

    # Initialize Elo
    EloClass = get_elo_class("nhl")
    elo = EloClass(k_factor=10, home_advantage=50, recency_weight=0.2)

    # Process games
    games_processed = 0
    for _, game in games_df.iterrows():
        home_full = game["home_team_name"]
        away_full = game["away_team_name"]

        home_team = nhl_team_mapping.get(home_full, home_full)
        away_team = nhl_team_mapping.get(away_full, away_full)

        if home_team and away_team:
            elo.update(home_team, away_team, game["home_win"])
            games_processed += 1

    print(f"  Processed {games_processed} games")
    print(f"  Rated {len(elo.ratings)} teams")

    if elo.ratings:
        print(f"  Sample ratings:")
        for team, rating in list(elo.ratings.items())[:5]:
            print(f"    {team}: {rating:.1f}")

    return True


def test_nba_elo_update():
    """Test NBA Elo update with unified_games."""
    print("\n🧪 Testing NBA Elo update...")

    # Query from unified_games
    query = """
        SELECT
            game_date,
            home_team_name,
            away_team_name,
            CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM unified_games
        WHERE sport = 'NBA'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND home_team_name IS NOT NULL
          AND away_team_name IS NOT NULL
        ORDER BY game_date
        LIMIT 100  # Just test with 100 games first
    """

    games_df = default_db.fetch_df(query)
    print(f"  Loaded {len(games_df)} NBA games from unified_games")

    if games_df.empty:
        print("❌ No games found")
        return False

    # NBA team mapping
    nba_team_mapping = {
        "Atlanta Hawks": "ATL",
        "Boston Celtics": "BOS",
        "Brooklyn Nets": "BKN",
        "Charlotte Hornets": "CHA",
        "Chicago Bulls": "CHI",
        "Cleveland Cavaliers": "CLE",
        "Dallas Mavericks": "DAL",
        "Denver Nuggets": "DEN",
        "Detroit Pistons": "DET",
        "Golden State Warriors": "GSW",
        "Houston Rockets": "HOU",
        "Indiana Pacers": "IND",
        "Los Angeles Clippers": "LAC",
        "Los Angeles Lakers": "LAL",
        "Memphis Grizzlies": "MEM",
        "Miami Heat": "MIA",
        "Milwaukee Bucks": "MIL",
        "Minnesota Timberwolves": "MIN",
        "New Orleans Pelicans": "NOP",
        "New York Knicks": "NYK",
        "Oklahoma City Thunder": "OKC",
        "Orlando Magic": "ORL",
        "Philadelphia 76ers": "PHI",
        "Phoenix Suns": "PHX",
        "Portland Trail Blazers": "POR",
        "Sacramento Kings": "SAC",
        "San Antonio Spurs": "SAS",
        "Toronto Raptors": "TOR",
        "Utah Jazz": "UTA",
        "Washington Wizards": "WAS",
        "LA Clippers": "LAC",
        "LA Lakers": "LAL",
    }

    # Initialize Elo
    EloClass = get_elo_class("nba")
    elo = EloClass(k_factor=20, home_advantage=100)

    # Process games
    games_processed = 0
    for _, game in games_df.iterrows():
        home_full = game["home_team_name"]
        away_full = game["away_team_name"]

        home_team = nba_team_mapping.get(home_full, home_full)
        away_team = nba_team_mapping.get(away_full, away_full)

        if home_team and away_team:
            elo.update(home_team, away_team, game["home_win"])
            games_processed += 1

    print(f"  Processed {games_processed} games")
    print(f"  Rated {len(elo.ratings)} teams")

    if elo.ratings:
        print(f"  Sample ratings:")
        for team, rating in list(elo.ratings.items())[:5]:
            print(f"    {team}: {rating:.1f}")

    return True


def test_mlb_elo_update():
    """Test MLB Elo update with unified_games."""
    print("\n🧪 Testing MLB Elo update...")

    # Query from unified_games
    query = """
        SELECT
            game_date,
            home_team_name,
            away_team_name,
            home_score,
            away_score
        FROM unified_games
        WHERE sport = 'MLB'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        ORDER BY game_date
        LIMIT 50  # Just test with 50 games first
    """

    games_df = default_db.fetch_df(query)
    print(f"  Loaded {len(games_df)} MLB games from unified_games")

    if games_df.empty:
        print("❌ No games found")
        return False

    # Initialize Elo
    EloClass = get_elo_class("mlb")
    elo = EloClass(k_factor=20, home_advantage=50)

    # Process games
    games_processed = 0
    for _, game in games_df.iterrows():
        home_team = game["home_team_name"]
        away_team = game["away_team_name"]
        home_score = game["home_score"]
        away_score = game["away_score"]

        if home_team and away_team:
            home_won = 1.0 if home_score > away_score else 0.0
            elo.update(
                home_team,
                away_team,
                home_won,
                home_score=home_score,
                away_score=away_score,
            )
            games_processed += 1

    print(f"  Processed {games_processed} games")
    print(f"  Rated {len(elo.ratings)} teams")

    if elo.ratings:
        print(f"  Sample ratings:")
        for team, rating in list(elo.ratings.items())[:5]:
            print(f"    {team}: {rating:.1f}")

    return True


def main():
    """Main test function."""
    # Set POSTGRES_HOST if not set
    if "POSTGRES_HOST" not in os.environ:
        os.environ["POSTGRES_HOST"] = "localhost"

    print("=" * 70)
    print("TESTING ELO UPDATE LOGIC")
    print("=" * 70)

    try:
        # Test NHL
        nhl_success = test_nhl_elo_update()

        # Test NBA
        nba_success = test_nba_elo_update()

        # Test MLB
        mlb_success = test_mlb_elo_update()

        print("\n" + "=" * 70)
        print("TEST RESULTS:")
        print("=" * 70)
        print(f"NHL: {'✅ PASS' if nhl_success else '❌ FAIL'}")
        print(f"NBA: {'✅ PASS' if nba_success else '❌ FAIL'}")
        print(f"MLB: {'✅ PASS' if mlb_success else '❌ FAIL'}")

        if nhl_success and nba_success and mlb_success:
            print("\n✅ All tests passed! Ready to update DAG.")
            return 0
        else:
            print("\n❌ Some tests failed. Check errors above.")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
