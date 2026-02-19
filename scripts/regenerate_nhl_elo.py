#!/usr/bin/env python3
"""
Regenerate NHL Elo ratings using ALL historical data from unified_games.
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add plugins directory to Python path (same as DAG)
plugins_dir = Path(__file__).parent.parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))

from db_manager import default_db
from elo.factory import get_elo_class


def map_team_name_to_abbreviation(full_name: str) -> str:
    """Map full team name to standard NHL abbreviation."""
    mapping = {
        'Anaheim Ducks': 'ANA',
        'Arizona Coyotes': 'ARI',
        'Boston Bruins': 'BOS',
        'Buffalo Sabres': 'BUF',
        'Calgary Flames': 'CGY',
        'Carolina Hurricanes': 'CAR',
        'Chicago Blackhawks': 'CHI',
        'Colorado Avalanche': 'COL',
        'Columbus Blue Jackets': 'CBJ',
        'Dallas Stars': 'DAL',
        'Detroit Red Wings': 'DET',
        'Edmonton Oilers': 'EDM',
        'Florida Panthers': 'FLA',
        'Los Angeles Kings': 'LAK',
        'Minnesota Wild': 'MIN',
        'Montreal Canadiens': 'MTL',
        'Nashville Predators': 'NSH',
        'New Jersey Devils': 'NJD',
        'New York Islanders': 'NYI',
        'New York Rangers': 'NYR',
        'Ottawa Senators': 'OTT',
        'Philadelphia Flyers': 'PHI',
        'Pittsburgh Penguins': 'PIT',
        'San Jose Sharks': 'SJS',
        'Seattle Kraken': 'SEA',
        'St. Louis Blues': 'STL',
        'Tampa Bay Lightning': 'TBL',
        'Toronto Maple Leafs': 'TOR',
        'Utah Hockey Club': 'UTA',
        'Vancouver Canucks': 'VAN',
        'Vegas Golden Knights': 'VGK',
        'Washington Capitals': 'WSH',
        'Winnipeg Jets': 'WPG',
        # Handle variations
        'Montréal Canadiens': 'MTL',
        'Utah Mammoth': 'UTA',  # Old name
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
    print(f"  Date range: {games_df['game_date'].min()} to {games_df['game_date'].max()}")

    # Initialize Elo system with optimal parameters from tuning
    # Based on tuning results: K=10, home_advantage=50, recency_weight=0.2
    EloClass = get_elo_class('nhl')
    elo = EloClass(k_factor=10, home_advantage=50, recency_weight=0.2)

    # Track season changes
    last_date = None
    games_processed = 0

    print("  Processing games chronologically...")

    for idx, game in games_df.iterrows():
        game_date = game['game_date']
        home_full = game['home_team_name']
        away_full = game['away_team_name']
        home_win = game['home_win']

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
        elo.update(
            home_team,
            away_team,
            home_win,
            game_date=current_date,
        )

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
    print(f"  Spread: ±{rating_range/2:.2f} from average")

    # Save to CSV (same format as DAG task)
    csv_path = "data/nhl_current_elo_ratings.csv"
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    with open(csv_path, 'w') as f:
        f.write("team,rating\n")
        for team, rating in sorted_ratings:
            f.write(f"{team},{rating:.2f}\n")

    print(f"\n💾 Saved ratings to {csv_path}")

    # Also save a backup with full names
    csv_full_path = "data/nhl_current_elo_ratings_full_names.csv"
    with open(csv_full_path, 'w') as f:
        f.write("abbreviation,full_name,rating\n")
        for team, rating in sorted_ratings:
            # Find full name for this abbreviation
            full_name = None
            for full, abbr in {
                'Anaheim Ducks': 'ANA',
                'Arizona Coyotes': 'ARI',
                'Boston Bruins': 'BOS',
                'Buffalo Sabres': 'BUF',
                'Calgary Flames': 'CGY',
                'Carolina Hurricanes': 'CAR',
                'Chicago Blackhawks': 'CHI',
                'Colorado Avalanche': 'COL',
                'Columbus Blue Jackets': 'CBJ',
                'Dallas Stars': 'DAL',
                'Detroit Red Wings': 'DET',
                'Edmonton Oilers': 'EDM',
                'Florida Panthers': 'FLA',
                'Los Angeles Kings': 'LAK',
                'Minnesota Wild': 'MIN',
                'Montreal Canadiens': 'MTL',
                'Nashville Predators': 'NSH',
                'New Jersey Devils': 'NJD',
                'New York Islanders': 'NYI',
                'New York Rangers': 'NYR',
                'Ottawa Senators': 'OTT',
                'Philadelphia Flyers': 'PHI',
                'Pittsburgh Penguins': 'PIT',
                'San Jose Sharks': 'SJS',
                'Seattle Kraken': 'SEA',
                'St. Louis Blues': 'STL',
                'Tampa Bay Lightning': 'TBL',
                'Toronto Maple Leafs': 'TOR',
                'Utah Hockey Club': 'UTA',
                'Vancouver Canucks': 'VAN',
                'Vegas Golden Knights': 'VGK',
                'Washington Capitals': 'WSH',
                'Winnipeg Jets': 'WPG',
            }.items():
                if abbr == team:
                    full_name = full
                    break

            if full_name:
                f.write(f"{team},{full_name},{rating:.2f}\n")

    print(f"💾 Saved full names to {csv_full_path}")

    return True


def test_elo_probabilities():
    """Test Elo probabilities with new ratings."""
    print("\n🧪 Testing Elo probabilities with new ratings...")

    # Load the newly generated ratings
    csv_path = "data/nhl_current_elo_ratings.csv"
    if not os.path.exists(csv_path):
        print(f"❌ {csv_path} not found")
        return

    # Initialize Elo with same parameters
    EloClass = get_elo_class('nhl')
    elo = EloClass(k_factor=10, home_advantage=50, recency_weight=0.2)

    # Load ratings from CSV
    import pandas as pd
    ratings_df = pd.read_csv(csv_path)

    for _, row in ratings_df.iterrows():
        elo.ratings[row['team']] = row['rating']

    print(f"  Loaded ratings for {len(elo.ratings)} teams")

    # Test some matchups
    test_matchups = [
        ('BOS', 'PHI'),  # Boston vs Philadelphia
        ('COL', 'DET'),  # Colorado vs Detroit
        ('FLA', 'WPG'),  # Florida vs Winnipeg
        ('VGK', 'SEA'),  # Vegas vs Seattle (expansion teams)
    ]

    print("\n  Sample matchup probabilities:")
    print("  " + "=" * 40)

    for home, away in test_matchups:
        if home in elo.ratings and away in elo.ratings:
            prob = elo.predict(home, away)
            home_rating = elo.ratings[home]
            away_rating = elo.ratings[away]
            rating_diff = home_rating - away_rating

            print(f"  {home} ({home_rating:.0f}) vs {away} ({away_rating:.0f}):")
            print(f"    Rating difference: {rating_diff:+.0f}")
            print(f"    Home win probability: {prob:.1%}")
            print(f"    Away win probability: {1-prob:.1%}")
            print()
        else:
            print(f"  ⚠️  Missing ratings for {home} vs {away}")

    # Calculate probability range
    all_teams = list(elo.ratings.keys())
    min_prob = 1.0
    max_prob = 0.0

    for i in range(min(10, len(all_teams))):
        for j in range(i+1, min(10, len(all_teams))):
            home = all_teams[i]
            away = all_teams[j]
            prob = elo.predict(home, away)
            min_prob = min(min_prob, prob)
            max_prob = max(max_prob, prob)

    print(f"  Probability range in sample: {min_prob:.1%} - {max_prob:.1%}")
    print(f"  Expected accuracy improvement: Should see >30% uniqueness in probabilities")


def main():
    """Main function."""
    # Set POSTGRES_HOST if not set
    if 'POSTGRES_HOST' not in os.environ:
        os.environ['POSTGRES_HOST'] = 'localhost'

    try:
        # Test connection
        test_query = "SELECT COUNT(*) as count FROM unified_games WHERE sport = 'NHL'"
        test_result = default_db.fetch_df(test_query)
        nhl_games = test_result.iloc[0]['count']
        print(f"Connected to database. Found {nhl_games} NHL games in unified_games.\n")

        # Regenerate Elo ratings
        success = regenerate_nhl_elo()

        if success:
            # Test the new ratings
            test_elo_probabilities()

            print("\n" + "="*60)
            print("🎉 NHL ELO REGENERATION COMPLETE!")
            print("="*60)
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
