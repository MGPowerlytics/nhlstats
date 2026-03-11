#!/usr/bin/env python3
import sys
sys.path.insert(0, '/mnt/data2/nhlstats')

from plugins.utils import upsert_record

# Mock DBManager
class MockDBManager:
    def __init__(self):
        self.executed_sql = None
        self.executed_params = None

    def execute(self, sql, params=None):
        self.executed_sql = sql
        self.executed_params = params
        print(f"SQL executed:\n{sql}")
        print(f"Params: {params}")
        # Simulate the error
        if "date_str" in (params or {}):
            raise Exception(f"Column 'date_str' does not exist (simulated error)")

# Test 1: params with date_str
print("Test 1: params with date_str")
db = MockDBManager()
params = {
    "bet_id": "test_123",
    "sport": "nba",
    "home_team": "PHX",
    "away_team": "NOP",
    "date_str": "2026-03-06",
    "recommendation_date": "2026-03-06"
}

try:
    upsert_record(
        db=db,
        table_name="bet_recommendations",
        params=params,
        conflict_columns=["bet_id"],
        update_columns=["elo_prob", "market_prob"]
    )
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*80 + "\n")

# Test 2: params without date_str
print("Test 2: params without date_str")
db2 = MockDBManager()
params2 = {
    "bet_id": "test_123",
    "sport": "nba",
    "home_team": "PHX",
    "away_team": "NOP",
    "recommendation_date": "2026-03-06"
}

try:
    upsert_record(
        db=db2,
        table_name="bet_recommendations",
        params=params2,
        conflict_columns=["bet_id"],
        update_columns=["elo_prob", "market_prob"]
    )
    print("Success!")
except Exception as e:
    print(f"Error: {e}")
