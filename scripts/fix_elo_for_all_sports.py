#!/usr/bin/env python3
"""
Fix Elo ratings for all sports by using unified_games table.
Also adds logging to show rating changes.
"""

import sys
import os
import pandas as pd
from datetime import datetime
from pathlib import Path
import json

# Add plugins directory to Python path
plugins_dir = Path(__file__).parent.parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))

from db_manager import default_db


def load_current_elo_ratings(sport: str):
    """Load current Elo ratings from CSV file."""
    csv_path = f"data/{sport}_current_elo_ratings.csv"
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        return dict(zip(df['team'], df['rating']))
    return {}


def save_elo_ratings_with_log(sport: str, new_ratings: dict, old_ratings: dict = None):
    """Save Elo ratings with logging of changes."""
    csv_path = f"data/{sport}_current_elo_ratings.csv"
    log_path = f"data/{sport}_elo_changes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Save new ratings
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    df = pd.DataFrame(list(new_ratings.items()), columns=['team', 'rating'])
    df = df.sort_values('rating', ascending=False)
    df.to_csv(csv_path, index=False)

    print(f"💾 Saved {len(new_ratings)} {sport.upper()} ratings to {csv_path}")

    # Log changes if old ratings provided
    if old_ratings:
        changes = []
        all_teams = set(list(old_ratings.keys()) + list(new_ratings.keys()))

        for team in all_teams:
            old = old_ratings.get(team, 1500)  # Default 1500 if not in old
            new = new_ratings.get(team, 1500)  # Default 1500 if not in new
            change = new - old

            changes.append({
                'team': team,
                'old_rating': float(old),
                'new_rating': float(new),
                'change': float(change),
                'in_old': team in old_ratings,
                'in_new': team in new_ratings
            })

        # Sort by absolute change
        changes.sort(key=lambda x: abs(x['change']), reverse=True)

        # Save log
        with open(log_path, 'w') as f:
            json.dump({
                'sport': sport,
                'timestamp': datetime.now().isoformat(),
                'old_count': len(old_ratings),
                'new_count': len(new_ratings),
                'changes': changes[:50]  # Top 50 changes
            }, f, indent=2)

        print(f"📝 Saved change log to {log_path}")

        # Print summary
        print(f"\n📊 {sport.upper()} Elo Rating Changes:")
        print("=" * 60)

        if changes:
            avg_change = sum(c['change'] for c in changes) / len(changes)
            max_increase = max(c['change'] for c in changes)
            max_decrease = min(c['change'] for c in changes)

            print(f"  Teams: {len(all_teams)} total ({len(old_ratings)} old, {len(new_ratings)} new)")
            print(f"  Average change: {avg_change:+.2f}")
            print(f"  Maximum increase: {max_increase:+.2f}")
            print(f"  Maximum decrease: {max_decrease:+.2f}")

            print(f"\n  Top 5 increases:")
            for c in changes[:5]:
                if c['change'] > 0:
                    print(f"    {c['team']:10s}: {c['old_rating']:7.1f} → {c['new_rating']:7.1f} ({c['change']:+.1f})")

            print(f"\n  Top 5 decreases:")
            for c in changes[:5]:
                if c['change'] < 0:
                    print(f"    {c['team']:10s}: {c['old_rating']:7.1f} → {c['new_rating']:7.1f} ({c['change']:+.1f})")

        return changes
    return []


def fix_nhl_elo():
    """Fix NHL Elo ratings using unified_games."""
    print("🔄 Fixing NHL Elo ratings...")

    # Load current ratings
    old_ratings = load_current_elo_ratings('nhl')
    print(f"  Loaded {len(old_ratings)} current NHL ratings")

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

    # Simple Elo implementation
    class SimpleElo:
        def __init__(self, k=10, home_adv=50):
            self.k = k
            self.home_adv = home_adv
            self.ratings = {}

        def get(self, team):
            return self.ratings.get(team, 1500)

        def predict(self, home, away):
            home_adj = self.get(home) + self.home_adv
            diff = self.get(away) - home_adj
            return 1 / (1 + 10 ** (diff / 400))

        def update(self, home, away, home_win):
            expected = self.predict(home, away)
            home_update = self.k * (home_win - expected)
            away_update = self.k * ((1 - home_win) - (1 - expected))

            self.ratings[home] = self.get(home) + home_update
            self.ratings[away] = self.get(away) + away_update

    # Map team names to abbreviations
    def map_team(name):
        mapping = {
            'Anaheim Ducks': 'ANA', 'Arizona Coyotes': 'ARI', 'Boston Bruins': 'BOS',
            'Buffalo Sabres': 'BUF', 'Calgary Flames': 'CGY', 'Carolina Hurricanes': 'CAR',
            'Chicago Blackhawks': 'CHI', 'Colorado Avalanche': 'COL', 'Columbus Blue Jackets': 'CBJ',
            'Dallas Stars': 'DAL', 'Detroit Red Wings': 'DET', 'Edmonton Oilers': 'EDM',
            'Florida Panthers': 'FLA', 'Los Angeles Kings': 'LAK', 'Minnesota Wild': 'MIN',
            'Montreal Canadiens': 'MTL', 'Nashville Predators': 'NSH', 'New Jersey Devils': 'NJD',
            'New York Islanders': 'NYI', 'New York Rangers': 'NYR', 'Ottawa Senators': 'OTT',
            'Philadelphia Flyers': 'PHI', 'Pittsburgh Penguins': 'PIT', 'San Jose Sharks': 'SJS',
            'Seattle Kraken': 'SEA', 'St. Louis Blues': 'STL', 'Tampa Bay Lightning': 'TBL',
            'Toronto Maple Leafs': 'TOR', 'Utah Hockey Club': 'UTA', 'Vancouver Canucks': 'VAN',
            'Vegas Golden Knights': 'VGK', 'Washington Capitals': 'WSH', 'Winnipeg Jets': 'WPG',
            'Montréal Canadiens': 'MTL', 'Utah Mammoth': 'UTA',
        }
        return mapping.get(name, name)

    # Process games
    elo = SimpleElo(k=10, home_adv=50)
    last_date = None

    for _, game in games_df.iterrows():
        home_full = game['home_team_name']
        away_full = game['away_team_name']
        home_win = game['home_win']

        home = map_team(home_full)
        away = map_team(away_full)

        if home and away:
            # Season detection (simplified)
            game_date = game['game_date']
            if isinstance(game_date, str):
                current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
            else:
                current_date = game_date

            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 90:
                    # Season regression
                    mean = sum(elo.ratings.values()) / len(elo.ratings) if elo.ratings else 1500
                    for team in elo.ratings:
                        elo.ratings[team] = elo.ratings[team] + 0.45 * (mean - elo.ratings[team])

            last_date = current_date
            elo.update(home, away, home_win)

    print(f"  Processed {len(games_df)} games, {len(elo.ratings)} teams rated")

    # Filter to only NHL teams (remove non-NHL teams that got mixed in)
    nhl_teams = {'ANA', 'ARI', 'BOS', 'BUF', 'CGY', 'CAR', 'CHI', 'COL', 'CBJ', 'DAL',
                 'DET', 'EDM', 'FLA', 'LAK', 'MIN', 'MTL', 'NSH', 'NJD', 'NYI', 'NYR',
                 'OTT', 'PHI', 'PIT', 'SJS', 'SEA', 'STL', 'TBL', 'TOR', 'UTA', 'VAN',
                 'VGK', 'WSH', 'WPG'}

    nhl_ratings = {team: rating for team, rating in elo.ratings.items() if team in nhl_teams}

    print(f"  Filtered to {len(nhl_ratings)} NHL teams")

    # Save with logging
    changes = save_elo_ratings_with_log('nhl', nhl_ratings, old_ratings)

    return True


def fix_nba_elo():
    """Fix NBA Elo ratings using unified_games."""
    print("\n🔄 Fixing NBA Elo ratings...")

    old_ratings = load_current_elo_ratings('nba')
    print(f"  Loaded {len(old_ratings)} current NBA ratings")

    # TODO: Implement NBA Elo fix similar to NHL
    print("  ⚠️  NBA Elo fix not implemented yet")

    return False


def check_sport_data(sport: str):
    """Check data availability for a sport."""
    print(f"\n🔍 Checking {sport.upper()} data in unified_games...")

    query = f"""
        SELECT
            COUNT(*) as total_games,
            COUNT(CASE WHEN home_score IS NOT NULL AND away_score IS NOT NULL THEN 1 END) as completed_games,
            MIN(game_date) as first_game,
            MAX(game_date) as last_game,
            COUNT(DISTINCT home_team_name) as unique_home_teams,
            COUNT(DISTINCT away_team_name) as unique_away_teams
        FROM unified_games
        WHERE sport = '{sport.upper()}'
    """

    try:
        stats = default_db.fetch_df(query)
        if not stats.empty:
            row = stats.iloc[0]
            print(f"  Total games: {row['total_games']}")
            print(f"  Completed games: {row['completed_games']}")
            print(f"  Date range: {row['first_game']} to {row['last_game']}")
            print(f"  Unique home teams: {row['unique_home_teams']}")
            print(f"  Unique away teams: {row['unique_away_teams']}")

            # Check current Elo file
            csv_path = f"data/{sport}_current_elo_ratings.csv"
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                print(f"  Current Elo file: {len(df)} teams")
            else:
                print(f"  Current Elo file: NOT FOUND")

        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Main function."""
    # Set POSTGRES_HOST if not set
    if 'POSTGRES_HOST' not in os.environ:
        os.environ['POSTGRES_HOST'] = 'localhost'

    print("=" * 70)
    print("ELO RATING FIX FOR ALL SPORTS")
    print("=" * 70)

    try:
        # Test connection
        test_query = "SELECT COUNT(*) as count FROM unified_games"
        test_result = default_db.fetch_df(test_query)
        total_games = test_result.iloc[0]['count']
        print(f"Connected to database. Found {total_games} total games in unified_games.\n")

        # Check each sport
        sports = ['NHL', 'NBA', 'MLB', 'NFL', 'NCAAB', 'WNCAAB', 'TENNIS']

        for sport in sports:
            check_sport_data(sport)

        print("\n" + "=" * 70)
        print("FIXING INDIVIDUAL SPORTS")
        print("=" * 70)

        # Fix NHL (most critical)
        nhl_success = fix_nhl_elo()

        # TODO: Fix other sports
        print("\n⚠️  Other sports will be fixed in future updates")
        print("   Priority: NHL (critical), then NBA, MLB, etc.")

        if nhl_success:
            print("\n" + "=" * 70)
            print("✅ NHL ELO FIXED SUCCESSFULLY!")
            print("=" * 70)
            print("\nNext steps for Airflow DAG fix:")
            print("1. Update update_elo_ratings() function in DAG to use unified_games")
            print("2. Add logging to show rating changes")
            print("3. Test DAG execution")
            print("4. Monitor new bet recommendations")
            print("\nThe fixed ratings are already saved and will be used by the DAG.")

        return 0 if nhl_success else 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
