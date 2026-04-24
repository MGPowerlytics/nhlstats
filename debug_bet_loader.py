#!/usr/bin/env python3
import sys
sys.path.insert(0, '/mnt/data2/nhlstats')

from plugins.bet_loader import BetData, BetContext, BetRecommendation

# Create a test bet
bet_data = BetData(
    home_team="PHX",
    away_team="NOP",
    ticker="KXNBAGAME-26MAR06NOPPHX-PHX",
    side="home",
    bet_on="home",
    elo_prob=0.8072216903714706,
    market_prob=0.6799999999999999,
    edge=0.12722169037147069,
    confidence="MEDIUM",
    home_rating=1485.720744834337,
    away_rating=1336.9468827540293,
    expected_value=0.18709072113451572,
    kelly_fraction=0.3975677824108458,
    yes_ask=None,
    no_ask=None
)

# Create context
context = BetContext(sport="nba", date_str="2026-03-06", index=0)

# Convert to recommendation
recommendation = bet_data.to_recommendation(context)

print("BetRecommendation fields:")
print(f"  bet_id: {recommendation.bet_id}")
print(f"  sport: {recommendation.sport}")
print(f"  recommendation_date: {recommendation.recommendation_date}")
print(f"  home_team: {recommendation.home_team}")
print(f"  away_team: {recommendation.away_team}")

# Get SQL params
params = recommendation.to_sql_params()
print("\nSQL params keys:")
for key in sorted(params.keys()):
    print(f"  {key}: {params[key]}")

# Check for date_str
if "date_str" in params:
    print(f"\n❌ ERROR: date_str is in params!")
    print(f"  date_str value: {params['date_str']}")
else:
    print(f"\n✅ Good: date_str is NOT in params")

# Check for recommendation_date
if "recommendation_date" in params:
    print(f"✅ Good: recommendation_date is in params")
    print(f"  recommendation_date value: {params['recommendation_date']}")
else:
    print(f"❌ ERROR: recommendation_date is NOT in params")
