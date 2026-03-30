#!/usr/bin/env python3
"""Debug script for portfolio betting issue."""

import sys
sys.path.insert(0, '/mnt/data2/nhlstats/plugins')

# Mock the dependencies
class MockKalshiBetting:
    def get_balance(self):
        return (1000.0, 0.0)

# Now import the actual module
from portfolio_betting import PortfolioBettingManager, DEFAULT_HEADER_WIDTH
from portfolio_types import PortfolioConfig, MAX_DAILY_RISK_PCT, KELLY_FRACTION, MAX_BET_SIZE, MAX_SINGLE_BET_PCT, MIN_EDGE_REQUIRED, MIN_BET_SIZE, ELO_BLEND_WEIGHT, BETMGM_BLEND_WEIGHT

print(f"DEFAULT_HEADER_WIDTH = {DEFAULT_HEADER_WIDTH}")

# Create a proper config using the actual PortfolioConfig class
config = PortfolioConfig(
    bankroll=1000.0,
    max_daily_risk_pct=MAX_DAILY_RISK_PCT,
    kelly_fraction=KELLY_FRACTION,
    min_bet_size=MIN_BET_SIZE,
    max_bet_size=MAX_BET_SIZE,
    max_single_bet_pct=MAX_SINGLE_BET_PCT,
    min_edge=MIN_EDGE_REQUIRED,
    min_confidence=0.0,
    excluded_segments=[],
    elo_blend_weight=ELO_BLEND_WEIGHT,
    betmgm_blend_weight=BETMGM_BLEND_WEIGHT
)

# Create manager
manager = PortfolioBettingManager(
    kalshi_client=MockKalshiBetting(),
    config=config,
    dry_run=False
)

print(f"manager.HEADER_WIDTH = {getattr(manager, 'HEADER_WIDTH', 'NOT SET')}")
print(f"manager.reporter.HEADER_WIDTH = {manager.reporter.HEADER_WIDTH}")

# Try to call process_daily_bets
try:
    results = manager.process_daily_bets("2026-03-22", sports=["nba"])
    print("Success!")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
