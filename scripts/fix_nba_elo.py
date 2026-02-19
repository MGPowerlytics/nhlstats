#!/usr/bin/env python3
"""
Fix NBA Elo ratings using unified_games table.
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
            old = old_ratings.get(team, 1500)
            new = new_ratings.get(team, 1500)
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
                'changes': changes[:50]
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
            count = 0
            for c in changes:
                if c['change'] > 0 and count < 5:
                    print(f"    {c['team']:10s}: {c['old_rating']:7.1f} → {c['new_rating']:7.1f} ({c['change']:+.1f})")
                    count += 1

            print(f"\n  Top 5 decreases:")
            count = 0
            for c in changes:
                if c['change'] < 0 and count < 5:
                    print(f"    {c['team']:10s}: {c['old_rating']:7.1f} → {c['new_rating']:7.1f} ({c['change']:+.1f})")
                    count += 1

        return changes
    return []


def fix_nba_elo():
    """Fix NBA Elo ratings using unified_games."""
    print("🔄 Fixing NBA Elo ratings...")

    # Load current ratings
    old_ratings = load_current_elo_ratings('nba')
    print(f"  Loaded {len(old_ratings)} current NBA ratings")

    # Query ALL historical NBA games from unified_games
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
                ELSE 0.5  -- Overtime/rare cases
            END as home_win
        FROM unified_games
        WHERE sport = 'NBA'
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
        print("❌ No NBA games found in unified_games")
        return False

    print(f"  Loaded {len(games_df)} historical NBA games from unified_games")
    print(f"  Date range: {games_df['game_date'].min()} to {games_df['game_date'].max()}")

    # Simple Elo implementation for NBA
    class SimpleNBABElo:
        def __init__(self, k=20, home_adv=100):
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
            'Atlanta Hawks': 'ATL',
            'Boston Celtics': 'BOS',
            'Brooklyn Nets': 'BKN',
            'Charlotte Hornets': 'CHA',
            'Chicago Bulls': 'CHI',
            'Cleveland Cavaliers': 'CLE',
            'Dallas Mavericks': 'DAL',
            'Denver Nuggets': 'DEN',
            'Detroit Pistons': 'DET',
            'Golden State Warriors': 'GSW',
            'Houston Rockets': 'HOU',
            'Indiana Pacers': 'IND',
            'Los Angeles Clippers': 'LAC',
            'Los Angeles Lakers': 'LAL',
            'Memphis Grizzlies': 'MEM',
            'Miami Heat': 'MIA',
            'Milwaukee Bucks': 'MIL',
            'Minnesota Timberwolves': 'MIN',
            'New Orleans Pelicans': 'NOP',
            'New York Knicks': 'NYK',
            'Oklahoma City Thunder': 'OKC',
            'Orlando Magic': 'ORL',
            'Philadelphia 76ers': 'PHI',
            'Phoenix Suns': 'PHX',
            'Portland Trail Blazers': 'POR',
            'Sacramento Kings': 'SAC',
            'San Antonio Spurs': 'SAS',
            'Toronto Raptors': 'TOR',
            'Utah Jazz': 'UTA',
            'Washington Wizards': 'WAS',
            # Handle variations
            'LA Clippers': 'LAC',
            'LA Lakers': 'LAL',
        }
        return mapping.get(name, name)

    # Process games
    elo = SimpleNBABElo(k=20, home_adv=100)
    last_date = None
    games_processed = 0

    print("  Processing games chronologically...")

    for _, game in games_df.iterrows():
        home_full = game['home_team_name']
        away_full = game['away_team_name']
        home_win = game['home_win']

        home = map_team(home_full)
        away = map_team(away_full)

        if home and away:
            # Season detection
            game_date = game['game_date']
            if isinstance(game_date, str):
                current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
            else:
                current_date = game_date

            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 120:  # NBA offseason is longer
                    # Season regression
                    mean = sum(elo.ratings.values()) / len(elo.ratings) if elo.ratings else 1500
                    for team in elo.ratings:
                        elo.ratings[team] = elo.ratings[team] + 0.4 * (mean - elo.ratings[team])

            last_date = current_date
            elo.update(home, away, home_win)

            games_processed += 1

            if games_processed % 1000 == 0:
                print(f"    Processed {games_processed} games...")

    print(f"  ✅ Processed {games_processed} games total")
    print(f"  Rated {len(elo.ratings)} teams")

    # Filter to only NBA teams
    nba_teams = {'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW',
                 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN', 'NOP', 'NYK',
                 'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS'}

    nba_ratings = {team: rating for team, rating in elo.ratings.items() if team in nba_teams}

    print(f"  Filtered to {len(nba_ratings)} NBA teams")

    # Calculate statistics
    if nba_ratings:
        ratings_list = list(nba_ratings.values())
        min_rating = min(ratings_list)
        max_rating = max(ratings_list)
        rating_range = max_rating - min_rating
        avg_rating = sum(ratings_list) / len(ratings_list)

        print(f"\n📊 NBA Elo Statistics:")
        print(f"  Rating range: {min_rating:.1f} - {max_rating:.1f} ({rating_range:.1f})")
        print(f"  Average rating: {avg_rating:.1f}")

        # Expected range for NBA is ~300 points
        if rating_range < 150:
            print(f"  ⚠️  Range is narrow (expected ~300 for NBA)")
        else:
            print(f"  ✅ Good range for NBA")

        # Check probability variance
        teams = list(nba_ratings.keys())
        if len(teams) >= 10:
            probabilities = []
            for i in range(min(10, len(teams))):
                for j in range(i+1, min(10, len(teams))):
                    prob = elo.predict(teams[i], teams[j])
                    probabilities.append(prob)

            if probabilities:
                prob_range = max(probabilities) - min(probabilities)
                print(f"  Probability range: {min(probabilities):.1%} - {max(probabilities):.1%} ({prob_range:.1%})")

                if prob_range < 0.2:
                    print(f"  ⚠️  Probability range is narrow (expected ~40% for NBA)")
                else:
                    print(f"  ✅ Good probability range for NBA")

    # Save with logging
    changes = save_elo_ratings_with_log('nba', nba_ratings, old_ratings)

    return True


def main():
    """Main function."""
    # Set POSTGRES_HOST if not set
    if 'POSTGRES_HOST' not in os.environ:
        os.environ['POSTGRES_HOST'] = 'localhost'

    print("=" * 70)
    print("NBA ELO RATING FIX")
    print("=" * 70)

    try:
        # Test connection
        test_query = "SELECT COUNT(*) as count FROM unified_games WHERE sport = 'NBA'"
        test_result = default_db.fetch_df(test_query)
        nba_games = test_result.iloc[0]['count']
        print(f"Connected to database. Found {nba_games} NBA games in unified_games.\n")

        # Fix NBA Elo ratings
        success = fix_nba_elo()

        if success:
            print("\n" + "=" * 70)
            print("✅ NBA ELO FIXED SUCCESSFULLY!")
            print("=" * 70)
            print("\nNext steps:")
            print("1. The DAG will use the new ratings automatically")
            print("2. Run the DAG or wait for next scheduled run")
            print("3. Check new bet recommendations have proper probability ranges")
            print("4. Monitor NBA betting performance")

            return 0
        else:
            print("\n❌ Failed to fix NBA Elo ratings")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
