#!/usr/bin/env python3
"""
Test the NHL Elo fix in DAG environment.
"""

import sys
import os

# Set up path like DAG does
sys.path.insert(0, 'plugins')

# Import what the DAG imports
from db_manager import default_db
from datetime import datetime

print("🧪 Testing NHL Elo fix for DAG...")
print("=" * 60)

# Test 1: Old query (current DAG)
print("\n1. Testing OLD query (from 'games' table):")
old_query = """
    WITH ranked_games AS (
        SELECT game_date, home_team_abbrev, away_team_abbrev,
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win,
               ROW_NUMBER() OVER (
                   PARTITION BY game_date, home_team_abbrev, away_team_abbrev
                   ORDER BY game_id
               ) as rn
        FROM games
        WHERE game_state IN ('OFF', 'FINAL', 'Final')
    )
    SELECT game_date, home_team_abbrev as home_team,
           away_team_abbrev as away_team, home_win
    FROM ranked_games
    WHERE rn = 1
    ORDER BY game_date, home_team
    LIMIT 10
"""

try:
    old_df = default_db.fetch_df(old_query)
    print(f"   ✅ OLD query works: {len(old_df)} games from 'games' table")
    print(f"   Sample: {old_df.iloc[0]['home_team']} vs {old_df.iloc[0]['away_team']} on {old_df.iloc[0]['game_date']}")
except Exception as e:
    print(f"   ❌ OLD query failed: {e}")

# Test 2: New query (proposed fix)
print("\n2. Testing NEW query (from 'unified_games' table):")
new_query = """
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
    LIMIT 10
"""

try:
    new_df = default_db.fetch_df(new_query)
    print(f"   ✅ NEW query works: {len(new_df)} games from 'unified_games' table")
    print(f"   Sample: {new_df.iloc[0]['home_team_name']} vs {new_df.iloc[0]['away_team_name']} on {new_df.iloc[0]['game_date']}")

    # Check if we have proper team names
    sample_home = new_df.iloc[0]['home_team_name']
    sample_away = new_df.iloc[0]['away_team_name']
    print(f"   Team names: '{sample_home}', '{sample_away}'")

except Exception as e:
    print(f"   ❌ NEW query failed: {e}")

# Test 3: Check total games in each table
print("\n3. Comparing data volume:")
try:
    # Count in games table
    count_games = """
        SELECT COUNT(*) as count
        FROM games
        WHERE game_state IN ('OFF', 'FINAL', 'Final')
    """
    games_count = default_db.fetch_df(count_games).iloc[0]['count']

    # Count in unified_games
    count_unified = """
        SELECT COUNT(*) as count
        FROM unified_games
        WHERE sport = 'NHL'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
    """
    unified_count = default_db.fetch_df(count_unified).iloc[0]['count']

    print(f"   'games' table: {games_count} completed NHL games")
    print(f"   'unified_games' table: {unified_count} completed NHL games")
    print(f"   Difference: {unified_count - games_count:,} more games in unified_games")

    if unified_count > games_count * 10:  # At least 10x more
        print(f"   ✅ unified_games has SIGNIFICANTLY more data!")
    else:
        print(f"   ⚠️  Not much difference between tables")

except Exception as e:
    print(f"   ❌ Count comparison failed: {e}")

# Test 4: Test team mapping
print("\n4. Testing team name mapping:")
nhl_team_mapping = {
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

# Get unique team names from unified_games
try:
    teams_query = """
        SELECT DISTINCT home_team_name as team_name
        FROM unified_games
        WHERE sport = 'NHL'
          AND home_team_name IS NOT NULL
        LIMIT 5
    """
    teams_df = default_db.fetch_df(teams_query)

    print(f"   Sample team names from unified_games:")
    for _, row in teams_df.iterrows():
        team_name = row['team_name']
        abbreviation = nhl_team_mapping.get(team_name, 'NOT FOUND')
        print(f"     '{team_name}' → '{abbreviation}'")

    # Check mapping coverage
    coverage_query = """
        SELECT
            COUNT(DISTINCT home_team_name) as total_teams,
            COUNT(DISTINCT CASE WHEN home_team_name IN (%s) THEN home_team_name END) as mapped_teams
        FROM unified_games
        WHERE sport = 'NHL'
    """ % ", ".join(["'%s'" % team for team in nhl_team_mapping.keys()])

    coverage_df = default_db.fetch_df(coverage_query)
    total = coverage_df.iloc[0]['total_teams']
    mapped = coverage_df.iloc[0]['mapped_teams']

    print(f"   Mapping coverage: {mapped}/{total} teams mapped ({mapped/total*100:.1f}%)")

except Exception as e:
    print(f"   ❌ Team mapping test failed: {e}")

print("\n" + "=" * 60)
print("✅ Test complete. If all queries work, DAG update should succeed.")
