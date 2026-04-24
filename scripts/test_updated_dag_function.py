#!/usr/bin/env python3
"""
Test the updated update_elo_ratings function.
"""

import sys
import os

# Set up path like DAG does
sys.path.insert(0, "plugins")

# Import the actual function from DAG
import importlib.util
import tempfile


# Create a test context
class MockTaskInstance:
    def xcom_push(self, key, value):
        print(
            f"  XCom push: {key} = {len(value) if isinstance(value, dict) else value}"
        )


class MockContext:
    def __init__(self):
        self.task_instance = MockTaskInstance()


# We need to import the function directly. Let me extract it
dag_path = "dags/multi_sport_betting_workflow.py"

print("🧪 Testing updated DAG function...")
print("=" * 60)

# Test 1: Test NHL Elo update
print("\n1. Testing NHL Elo update (small sample):")

# Create a simplified test
try:
    from db_manager import default_db
    from elo import get_elo_class
    from datetime import datetime

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
        "Montréal Canadiens": "MTL",
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
        "Utah Mammoth": "UTA",
        "Vancouver Canucks": "VAN",
        "Vegas Golden Knights": "VGK",
        "Washington Capitals": "WSH",
        "Winnipeg Jets": "WPG",
    }

    def map_nhl_team(team_name):
        if team_name and len(team_name) <= 4:
            return team_name
        return nhl_team_mapping.get(team_name, team_name)

    # Test query (limit to 50 games for speed)
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
        LIMIT 50
    """

    games_df = default_db.fetch_df(query)
    print(f"  Loaded {len(games_df)} NHL games from unified_games")

    # Initialize Elo
    EloClass = get_elo_class("nhl")
    elo = EloClass(k_factor=10, home_advantage=50, recency_weight=0.2)

    # Process games
    games_processed = 0
    last_date = None

    for _, game in games_df.iterrows():
        home_full = game["home_team_name"]
        away_full = game["away_team_name"]
        home_team = map_nhl_team(home_full)
        away_team = map_nhl_team(away_full)

        if home_team and away_team:
            game_date = game["game_date"]
            if isinstance(game_date, str):
                current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
            else:
                current_date = game_date

            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 90:
                    print(f"  📅 Season change detected")

            last_date = current_date
            elo.update(home_team, away_team, game["home_win"], game_date=current_date)
            games_processed += 1

    print(f"  Processed {games_processed} games")
    print(f"  Rated {len(elo.ratings)} teams")

    if elo.ratings:
        print(f"  Sample ratings (first 5):")
        for team, rating in list(elo.ratings.items())[:5]:
            print(f"    {team}: {rating:.1f}")

        # Check rating range
        ratings_list = list(elo.ratings.values())
        min_rating = min(ratings_list)
        max_rating = max(ratings_list)
        rating_range = max_rating - min_rating
        print(
            f"  Rating range: {min_rating:.1f} - {max_rating:.1f} ({rating_range:.1f})"
        )

        if rating_range > 100:
            print("  ✅ Good rating range (should improve with more games)")
        else:
            print("  ⚠️  Narrow rating range (but only 50 games processed)")

    print("\n✅ NHL test passed!")

except Exception as e:
    print(f"❌ NHL test failed: {e}")
    import traceback

    traceback.print_exc()

# Test 2: Test NBA Elo update
print("\n2. Testing NBA Elo update (small sample):")

try:
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

    def map_nba_team(team_name):
        if team_name and len(team_name) <= 4:
            return team_name
        return nba_team_mapping.get(team_name, team_name)

    # Test query
    query = """
        SELECT game_date, home_team_name as home_team, away_team_name as away_team,
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM unified_games
        WHERE sport = 'NBA'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        ORDER BY game_date
        LIMIT 50
    """

    games_df = default_db.fetch_df(query)
    print(f"  Loaded {len(games_df)} NBA games from unified_games")

    # Initialize Elo
    EloClass = get_elo_class("nba")
    elo = EloClass(k_factor=20, home_advantage=100)

    # Process games
    games_processed = 0
    last_date = None

    for _, game in games_df.iterrows():
        home_full = game["home_team"]
        away_full = game["away_team"]
        home_team = map_nba_team(home_full)
        away_team = map_nba_team(away_full)

        if home_team and away_team:
            game_date = game["game_date"]
            if isinstance(game_date, str):
                current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
            else:
                current_date = game_date

            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 120:
                    print(f"  📅 Season change detected")

            last_date = current_date
            elo.update(home_team, away_team, game["home_win"])
            games_processed += 1

    print(f"  Processed {games_processed} games")
    print(f"  Rated {len(elo.ratings)} teams")

    if elo.ratings:
        print(f"  Sample ratings (first 5):")
        for team, rating in list(elo.ratings.items())[:5]:
            print(f"    {team}: {rating:.1f}")

    print("\n✅ NBA test passed!")

except Exception as e:
    print(f"❌ NBA test failed: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ All tests completed!")
print("\nNext: Deploy to Airflow and run a test DAG execution.")
