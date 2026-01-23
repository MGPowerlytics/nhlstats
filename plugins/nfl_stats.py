#!/usr/bin/env python3
"""
NFL Stats Fetcher using nfl_data_py (nflfastR Python wrapper).
Collects play-by-play, roster, schedule, and advanced statistics.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd


class NFLStatsFetcher:
    """
    Fetch NFL statistics using nfl_data_py.

    Note: Requires 'pip install nfl_data_py pandas'
    """

    def __init__(self, output_dir="data/nfl"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Import nfl_data_py (will be installed via requirements.txt)
        try:
            import nfl_data_py as nfl
            self.nfl = nfl
        except ImportError:
            raise ImportError(
                "nfl_data_py is required. Install with: pip install nfl_data_py"
            )

    def get_schedule(self, season):
        """
        Get schedule for a specific season.

        Args:
            season: Year (e.g., 2023)

        Returns:
            pandas DataFrame with schedule
        """
        return self.nfl.import_schedules([season])

    def get_play_by_play(self, season):
        """
        Get play-by-play data for a season.
        Includes all plays with detailed information.

        Args:
            season: Year (e.g., 2023)

        Returns:
            pandas DataFrame with play-by-play data
        """
        return self.nfl.import_pbp_data([season])

    def get_weekly_data(self, season):
        """
        Get weekly player statistics.

        Args:
            season: Year

        Returns:
            pandas DataFrame with weekly stats
        """
        return self.nfl.import_weekly_data([season])

    def get_seasonal_data(self, season):
        """
        Get seasonal player statistics.

        Args:
            season: Year

        Returns:
            pandas DataFrame with seasonal stats
        """
        return self.nfl.import_seasonal_data([season])

    def get_rosters(self, season):
        """
        Get rosters for a season.

        Args:
            season: Year

        Returns:
            pandas DataFrame with roster data
        """
        return self.nfl.import_rosters([season])

    def get_team_descriptions(self):
        """
        Get team information and abbreviations.

        Returns:
            pandas DataFrame with team data
        """
        return self.nfl.import_team_desc()

    def get_injuries(self, season):
        """
        Get injury reports for a season.

        Args:
            season: Year

        Returns:
            pandas DataFrame with injury data
        """
        return self.nfl.import_injuries([season])

    def get_depth_charts(self, season):
        """
        Get depth charts for a season.

        Args:
            season: Year

        Returns:
            pandas DataFrame with depth chart data
        """
        return self.nfl.import_depth_charts([season])

    def get_next_gen_stats(self, season, stat_type='passing'):
        """
        Get Next Gen Stats (NGS) for a season.

        Args:
            season: Year
            stat_type: 'passing', 'rushing', 'receiving'

        Returns:
            pandas DataFrame with NGS data
        """
        return self.nfl.import_ngs_data(stat_type, [season])

    def download_season(self, season):
        """
        Download comprehensive data for an entire season.

        Args:
            season: Year (e.g., 2023)

        Returns:
            dict with all season data
        """
        print(f"Downloading NFL data for {season} season...")

        season_data = {
            'season': season,
            'timestamp': datetime.now().isoformat()
        }

        # Get schedule
        try:
            print("  Fetching schedule...")
            schedule = self.get_schedule(season)
            season_data['schedule'] = schedule

            sched_file = self.output_dir / f"{season}_schedule.csv"
            schedule.to_csv(sched_file, index=False)
            print(f"  ✓ Saved schedule ({len(schedule)} games) to {sched_file}")
        except Exception as e:
            print(f"  ✗ Error fetching schedule: {e}")

        # Get play-by-play
        try:
            print("  Fetching play-by-play data...")
            pbp = self.get_play_by_play(season)
            season_data['play_by_play'] = pbp

            pbp_file = self.output_dir / f"{season}_playbyplay.csv"
            pbp.to_csv(pbp_file, index=False)
            print(f"  ✓ Saved play-by-play ({len(pbp)} plays) to {pbp_file}")
        except Exception as e:
            print(f"  ✗ Error fetching play-by-play: {e}")

        # Get weekly stats
        try:
            print("  Fetching weekly stats...")
            weekly = self.get_weekly_data(season)
            season_data['weekly_stats'] = weekly

            weekly_file = self.output_dir / f"{season}_weekly_stats.csv"
            weekly.to_csv(weekly_file, index=False)
            print(f"  ✓ Saved weekly stats ({len(weekly)} records) to {weekly_file}")
        except Exception as e:
            print(f"  ✗ Error fetching weekly stats: {e}")

        # Get rosters
        try:
            print("  Fetching rosters...")
            rosters = self.get_rosters(season)
            season_data['rosters'] = rosters

            roster_file = self.output_dir / f"{season}_rosters.csv"
            rosters.to_csv(roster_file, index=False)
            print(f"  ✓ Saved rosters ({len(rosters)} players) to {roster_file}")
        except Exception as e:
            print(f"  ✗ Error fetching rosters: {e}")

        print(f"\nCompleted download for {season} season!")
        return season_data

    def download_week_games(self, season, week):
        """
        Download play-by-play data for a specific week.

        Args:
            season: Year
            week: Week number (1-18 for regular season)

        Returns:
            pandas DataFrame with week's play-by-play data
        """
        print(f"Fetching NFL games for {season} Week {week}...")

        # Get full season play-by-play
        pbp = self.get_play_by_play(season)

        # Filter to specific week
        week_pbp = pbp[pbp['week'] == week]

        if len(week_pbp) > 0:
            # Save to file
            week_file = self.output_dir / f"{season}_week{week:02d}_playbyplay.csv"
            week_pbp.to_csv(week_file, index=False)
            print(f"✓ Saved {len(week_pbp)} plays to {week_file}")

            # Print summary
            games = week_pbp['game_id'].nunique()
            print(f"  {games} games, {len(week_pbp)} plays")
        else:
            print(f"No data found for Week {week}")

        return week_pbp

    def extract_passing_stats(self, pbp_data):
        """
        Extract passing statistics from play-by-play data.

        Args:
            pbp_data: Play-by-play DataFrame

        Returns:
            pandas DataFrame with passing stats by player
        """
        passing_plays = pbp_data[pbp_data['play_type'] == 'pass'].copy()

        passing_stats = passing_plays.groupby(['passer_player_id', 'passer_player_name']).agg({
            'complete_pass': 'sum',
            'incomplete_pass': 'sum',
            'passing_yards': 'sum',
            'pass_touchdown': 'sum',
            'interception': 'sum',
            'sack': 'sum',
            'qb_hit': 'sum',
            'air_yards': 'sum',
            'yards_after_catch': 'sum',
        }).reset_index()

        # Calculate completion percentage
        passing_stats['attempts'] = passing_stats['complete_pass'] + passing_stats['incomplete_pass']
        passing_stats['completion_pct'] = (
            passing_stats['complete_pass'] / passing_stats['attempts'] * 100
        ).round(1)

        return passing_stats

    def extract_rushing_stats(self, pbp_data):
        """
        Extract rushing statistics from play-by-play data.

        Args:
            pbp_data: Play-by-play DataFrame

        Returns:
            pandas DataFrame with rushing stats by player
        """
        rushing_plays = pbp_data[pbp_data['play_type'] == 'run'].copy()

        rushing_stats = rushing_plays.groupby(['rusher_player_id', 'rusher_player_name']).agg({
            'rushing_yards': 'sum',
            'rush_touchdown': 'sum',
            'fumble_lost': 'sum',
        }).reset_index()

        rushing_stats['carries'] = rushing_plays.groupby('rusher_player_id').size().values
        rushing_stats['yards_per_carry'] = (
            rushing_stats['rushing_yards'] / rushing_stats['carries']
        ).round(2)

        return rushing_stats


def main():
    """Example usage and testing."""
    fetcher = NFLStatsFetcher()

    print("="*60)
    print("NFL Stats Fetcher Test")
    print("="*60)

    # Test 1: Get recent season schedule
    print("\n1. Testing schedule retrieval...")
    try:
        schedule = fetcher.get_schedule(2023)
        print(f"✓ Retrieved {len(schedule)} games for 2023 season")

        # Show sample game
        if len(schedule) > 0:
            game = schedule.iloc[0]
            print(f"  Sample: Week {game['week']} - {game['away_team']} @ {game['home_team']}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 2: Get play-by-play for a week
    print("\n2. Testing play-by-play retrieval...")
    try:
        pbp = fetcher.get_play_by_play(2023)
        week1 = pbp[pbp['week'] == 1]
        print(f"✓ Retrieved {len(week1)} plays for Week 1")

        # Show sample play
        if len(week1) > 0:
            play = week1.iloc[0]
            print(f"  Sample play: {play['desc'][:80]}...")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 3: Extract passing stats
    print("\n3. Testing stat extraction...")
    try:
        passing = fetcher.extract_passing_stats(pbp)
        passing_sorted = passing.sort_values('passing_yards', ascending=False)
        print(f"✓ Extracted passing stats for {len(passing)} players")

        if len(passing_sorted) > 0:
            top_passer = passing_sorted.iloc[0]
            print(f"  Top passer: {top_passer['passer_player_name']} - " +
                  f"{top_passer['passing_yards']:.0f} yards, " +
                  f"{top_passer['pass_touchdown']:.0f} TDs")
    except Exception as e:
        print(f"✗ Error: {e}")

    print("\n" + "="*60)
    print("Test complete!")
    print("="*60)
    print("\nNote: Full season downloads can take several minutes")
    print("Use download_week_games() for faster targeted data collection")


if __name__ == "__main__":
    main()
