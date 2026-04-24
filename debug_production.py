#!/usr/bin/env python3
import sys
sys.path.insert(0, '/mnt/data2/nhlstats')

from plugins.bet_loader import BetData, BetContext, BetRecommendation, BetLoader
from plugins.utils import DBManager
import json

# Create a mock bet like the one in the error log
bet_dict = {
    "home_team": "PHX",
    "away_team": "NOP",
    "ticker": "KXNBAGAME-26MAR06NOPPHX-PHX",
    "side": "home",
    "bet_on": "home",
    "elo_prob": 0.8072216903714706,
    "market_prob": 0.6799999999999999,
    "edge": 0.12722169037147069,
    "confidence": "MEDIUM",
    "home_rating": 1485.720744834337,
    "away_rating": 1336.9468827540293,
    "expected_value": 0.18709072113451572,
    "kelly_fraction": 0.3975677824108458,
    "yes_ask": None,
    "no_ask": None
}

print("Creating BetData from dict...")
bet_data = BetData.from_dict(bet_dict)
print(f"BetData created: home_team={bet_data.home_team}, away_team={bet_data.away_team}")

print("\nCreating BetContext...")
context = BetContext(sport="nba", date_str="2026-03-06", index=0)

print("\nCreating BetRecommendation...")
recommendation = BetRecommendation.from_dict(bet_dict, context)
print(f"BetRecommendation created:")
print(f"  bet_id: {recommendation.bet_id}")
print(f"  sport: {recommendation.sport}")
print(f"  recommendation_date: {recommendation.recommendation_date}")
print(f"  home_team: {recommendation.home_team}")
print(f"  away_team: {recommendation.away_team}")

print("\nGetting SQL params...")
params = recommendation.to_sql_params()
print(f"Params keys: {list(params.keys())}")

# Check for date_str
if "date_str" in params:
    print(f"❌ ERROR: date_str is in params! Value: {params['date_str']}")
else:
    print(f"✅ Good: date_str is NOT in params")

# Check for recommendation_date
if "recommendation_date" in params:
    print(f"✅ Good: recommendation_date is in params. Value: {params['recommendation_date']}")
else:
    print(f"❌ ERROR: recommendation_date is NOT in params")

# Now test the full load_bets_for_date flow
print("\n" + "="*80)
print("Testing full load_bets_for_date flow...")

# Create a mock bets file
import tempfile
import os
from pathlib import Path

# Create temp directory
temp_dir = tempfile.mkdtemp()
bets_file = Path(temp_dir) / "nba" / "bets_2026-03-06.json"
bets_file.parent.mkdir(parents=True, exist_ok=True)

# Write test bet to file
with open(bets_file, "w") as f:
    json.dump([bet_dict], f)

print(f"Created test bets file: {bets_file}")

# Mock DBManager that captures SQL
class CaptureDBManager:
    def __init__(self):
        self.captured_sql = []
        self.captured_params = []

    def execute(self, sql, params=None):
        self.captured_sql.append(sql)
        self.captured_params.append(params)
        print(f"SQL captured:\n{sql}")
        print(f"Params: {params}")
        # Check for date_str in SQL
        if "date_str" in sql:
            print("❌ ERROR: date_str found in SQL!")
        if params and "date_str" in params:
            print("❌ ERROR: date_str found in params!")
        # Don't actually execute
        return None

    def commit(self):
        pass

    def close(self):
        pass

# Create BetLoader with mock DB
db = CaptureDBManager()
bet_loader = BetLoader(db_manager=db)

# Monkey-patch the data directory
import plugins.bet_loader as bl_module
original_init = bl_module.BetLoader.__init__

def patched_init(self, db_path=None, db_manager=None):
    original_init(self, db_path=db_path, db_manager=db_manager)
    # Override data directory
    self.data_dir = Path(temp_dir)

bl_module.BetLoader.__init__ = patched_init

# Try to load bets
print("\nCalling load_bets_for_date...")
try:
    loaded = bet_loader.load_bets_for_date("nba", "2026-03-06")
    print(f"Loaded {loaded} bets")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Cleanup
import shutil
shutil.rmtree(temp_dir)
