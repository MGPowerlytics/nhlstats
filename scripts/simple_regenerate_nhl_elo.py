#!/usr/bin/env python3
"""
Simple script to regenerate NHL Elo ratings using ALL historical data.
Implements Elo logic directly to avoid import issues.
"""

import sys
import os
import pandas as pd
from datetime import datetime
from pathlib import Path
import math

# Add plugins directory to Python path
plugins_dir = Path(__file__).parent.parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))

from db_manager import default_db


class SimpleNHLElo:
    """Simple NHL Elo implementation."""

    def __init__(
        self, k_factor=10, home_advantage=50, recency_weight=0.2, initial_rating=1500
    ):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.recency_weight = recency_weight
        self.initial_rating = initial_rating
        self.ratings = {}  # team -> rating
        self.games_processed = 0

    def get_rating(self, team):
        """Get current rating for a team, initializing if needed."""
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]

    def predict(self, home_team, away_team):
        """Predict probability of home team winning."""
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home advantage
        home_rating_adj = home_rating + self.home_advantage

        # Elo formula
        rating_diff = away_rating - home_rating_adj
        expected = 1 / (1 + 10 ** (rating_diff / 400))

        return expected

    def update(self, home_team, away_team, home_win, game_date=None):
        """Update ratings after a game."""
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home advantage for prediction
        home_rating_adj = home_rating + self.home_advantage

        # Calculate expected outcome
        rating_diff = away_rating - home_rating_adj
        expected_home = 1 / (1 + 10 ** (rating_diff / 400))

        # Actual outcome (1 for home win, 0 for away win, 0.5 for tie)
        actual_home = home_win

        # Update ratings
        home_update = self.k_factor * (actual_home - expected_home)
        away_update = self.k_factor * ((1 - actual_home) - (1 - expected_home))

        # Apply recency weighting if specified
        if self.recency_weight and self.games_processed > 0:
            # Simple linear recency - could be improved
            recency_factor = 1.0 + (self.recency_weight * (self.games_processed / 1000))
            home_update *= recency_factor
            away_update *= recency_factor

        self.ratings[home_team] = home_rating + home_update
        self.ratings[away_team] = away_rating + away_update

        self.games_processed += 1

    def apply_season_reversion(self, regression_factor=0.45):
        """Regress ratings toward the mean at season start."""
        if not self.ratings:
            return

        mean_rating = sum(self.ratings.values()) / len(self.ratings)

        for team in self.ratings:
            current = self.ratings[team]
            regressed = current + regression_factor * (mean_rating - current)
            self.ratings[team] = regressed

    def get_all_ratings(self):
        """Get all current ratings."""
        return self.ratings.copy()


def map_team_name_to_abbreviation(full_name: str) -> str:
    """Map full team name to standard NHL abbreviation."""
    mapping = {
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
        # Handle variations
        "Montréal Canadiens": "MTL",
        "Utah Mammoth": "UTA",  # Old name
    }

    return mapping.get(full_name, full_name)


def regenerate_nhl_elo():
    """Regenerate NHL Elo ratings using all historical data."""
    print("🔄 Regenerating NHL Elo ratings with ALL historical data...")

    # Query ALL historical NHL games from unified_games
    query = """
        SELECT
            game_date,
            home_team_name,
            away_team_name,
            home_score,
            away_score,
            CASE
                WHEN home_score > away_score THEN 1.0
                WHEN away_score > home_score THEN 0.0
                ELSE 0.5  -- Ties (though rare in NHL)
            END as home_win
        FROM unified_games
        WHERE sport = 'NHL'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND home_team_name IS NOT NULL
          AND away_team_name IS NOT NULL
          AND home_team_name != ''
          AND away_team_name != ''
        ORDER BY game_date
    """

    games_df = default_db.fetch_df(query)

    if games_df.empty:
        print("❌ No NHL games found in unified_games")
        return False

    print(f"  Loaded {len(games_df)} historical NHL games from unified_games")
    print(
        f"  Date range: {games_df['game_date'].min()} to {games_df['game_date'].max()}"
    )

    # Initialize Elo system with optimal parameters from tuning
    # Based on tuning results: K=10, home_advantage=50, recency_weight=0.2
    elo = SimpleNHLElo(k_factor=10, home_advantage=50, recency_weight=0.2)

    # Track season changes
    last_date = None
    games_processed = 0

    print("  Processing games chronologically...")

    for idx, game in games_df.iterrows():
        game_date = game["game_date"]
        home_full = game["home_team_name"]
        away_full = game["away_team_name"]
        home_win = game["home_win"]

        # Map to abbreviations
        home_team = map_team_name_to_abbreviation(home_full)
        away_team = map_team_name_to_abbreviation(away_full)

        # Skip if mapping failed
        if not home_team or not away_team:
            continue

        # Handle date
        if isinstance(game_date, str):
            current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
        else:
            current_date = game_date

        # Detect season changes (more than 90 days between games)
        if last_date:
            days_diff = (current_date - last_date).days
            if days_diff > 90:
                print(f"  📅 New NHL season detected at {current_date}")
                elo.apply_season_reversion(0.45)  # 45% regression toward mean

        last_date = current_date

        # Update Elo ratings
        elo.update(home_team, away_team, home_win)

        games_processed += 1

        if games_processed % 1000 == 0:
            print(f"    Processed {games_processed} games...")

    print(f"  ✅ Processed {games_processed} games total")

    # Get final ratings
    ratings = elo.get_all_ratings()

    print(f"\n📊 Final Elo ratings for {len(ratings)} teams:")
    print("=" * 40)

    # Sort by rating
    sorted_ratings = sorted(ratings.items(), key=lambda x: x[1], reverse=True)

    for i, (team, rating) in enumerate(sorted_ratings[:10], 1):
        print(f"  {i:2d}. {team:3s}: {rating:7.2f}")

    if len(sorted_ratings) > 10:
        print(f"  ... and {len(sorted_ratings) - 10} more teams")

    # Calculate rating statistics
    ratings_list = [r for _, r in sorted_ratings]
    avg_rating = sum(ratings_list) / len(ratings_list)
    min_rating = min(ratings_list)
    max_rating = max(ratings_list)
    rating_range = max_rating - min_rating

    print(f"\n📈 Rating statistics:")
    print(f"  Average: {avg_rating:.2f}")
    print(f"  Range: {min_rating:.2f} - {max_rating:.2f} ({rating_range:.2f})")
    print(f"  Spread: ±{rating_range / 2:.2f} from average")

    # Compare with current ratings
    current_csv = "data/nhl_current_elo_ratings.csv"
    if os.path.exists(current_csv):
        current_df = pd.read_csv(current_csv)
        current_ratings = dict(zip(current_df["team"], current_df["rating"]))

        print(f"\n🔍 Comparison with current ratings ({len(current_ratings)} teams):")

        # Find common teams
        common_teams = set(ratings.keys()) & set(current_ratings.keys())

        if common_teams:
            rating_changes = []
            for team in common_teams:
                old = current_ratings.get(team, 1500)
                new = ratings.get(team, 1500)
                change = new - old
                rating_changes.append(change)

            avg_change = sum(rating_changes) / len(rating_changes)
            max_increase = max(rating_changes) if rating_changes else 0
            max_decrease = min(rating_changes) if rating_changes else 0

            print(f"  Average rating change: {avg_change:+.2f}")
            print(f"  Maximum increase: {max_increase:+.2f}")
            print(f"  Maximum decrease: {max_decrease:+.2f}")

            # Show top changes
            changes = [
                (team, ratings.get(team, 1500) - current_ratings.get(team, 1500))
                for team in common_teams
            ]
            changes.sort(key=lambda x: abs(x[1]), reverse=True)

            print(f"\n  Top 5 rating changes:")
            for team, change in changes[:5]:
                print(f"    {team:3s}: {change:+.2f}")

    # Save to CSV (same format as DAG task)
    csv_path = "data/nhl_current_elo_ratings.csv"
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    with open(csv_path, "w") as f:
        f.write("team,rating\n")
        for team, rating in sorted_ratings:
            f.write(f"{team},{rating:.2f}\n")

    print(f"\n💾 Saved ratings to {csv_path}")

    # Test probability range
    print("\n🧪 Testing probability range with new ratings...")

    # Calculate probability range
    all_teams = list(ratings.keys())
    probabilities = []

    for i in range(min(20, len(all_teams))):
        for j in range(i + 1, min(20, len(all_teams))):
            home = all_teams[i]
            away = all_teams[j]
            prob = elo.predict(home, away)
            probabilities.append(prob)

    if probabilities:
        min_prob = min(probabilities)
        max_prob = max(probabilities)
        avg_prob = sum(probabilities) / len(probabilities)

        print(f"  Sample probability range: {min_prob:.1%} - {max_prob:.1%}")
        print(f"  Average probability: {avg_prob:.1%}")
        print(f"  Expected uniqueness: >{(max_prob - min_prob) * 100:.0f}%")

        # This should be MUCH better than the current ~5% range!
        if (max_prob - min_prob) > 0.2:  # At least 20% range
            print("  ✅ SIGNIFICANT IMPROVEMENT over current ~5% range!")
        else:
            print("  ⚠️  Still limited range - may need parameter adjustment")

    return True


def main():
    """Main function."""
    # Set POSTGRES_HOST if not set
    if "POSTGRES_HOST" not in os.environ:
        os.environ["POSTGRES_HOST"] = "localhost"

    try:
        # Test connection
        test_query = "SELECT COUNT(*) as count FROM unified_games WHERE sport = 'NHL'"
        test_result = default_db.fetch_df(test_query)
        nhl_games = test_result.iloc[0]["count"]
        print(f"Connected to database. Found {nhl_games} NHL games in unified_games.\n")

        # Regenerate Elo ratings
        success = regenerate_nhl_elo()

        if success:
            print("\n" + "=" * 60)
            print("🎉 NHL ELO REGENERATION COMPLETE!")
            print("=" * 60)
            print("\nNext steps:")
            print("1. The DAG will use the new ratings automatically")
            print("2. Run the DAG or wait for next scheduled run")
            print("3. New bet recommendations will use proper Elo probabilities")
            print("4. Re-run predictiveness analysis after new bets are placed")

            return 0
        else:
            print("\n❌ Failed to regenerate NHL Elo ratings")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
