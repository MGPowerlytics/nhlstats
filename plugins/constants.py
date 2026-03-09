"""
Central constants for the Multi-Sport Betting System.
"""

# All supported sports in the system
ALL_SPORTS = [
    "nhl",
    "nba",
    "mlb",
    "nfl",
    "ncaab",
    "wncaab",
    "tennis",
    "epl",
    "ligue1",
    "cba",
    "unrivaled",
]

# Sport names in uppercase for display/filtering
ALL_SPORTS_UPPER = [s.upper() for s in ALL_SPORTS]

# Default sports to load in portfolio optimizer and other tools
DEFAULT_SPORTS = ALL_SPORTS

# Sports that support Glicko-2 ratings
GLICKO2_SPORTS = ["nba", "nhl", "mlb", "nfl"]

# Sports that support direct bet placement (single-sport workflow)
# Note: Most betting now goes through the unified portfolio_optimized_betting task
SINGLE_BETTING_SPORTS = ["nba", "nhl", "ncaab", "wncaab", "tennis", "ligue1"]

# Sports that should be included in the daily portfolio optimization
PORTFOLIO_SPORTS = ALL_SPORTS

# Betting threshold constants
# These values control the identification of betting opportunities
DEFAULT_THRESHOLD = 0.65  # Minimum Elo probability to consider a bet
DEFAULT_MIN_EDGE = 0.05  # Minimum edge (Elo prob - market prob) required
DEFAULT_MARKET_CONFIDENCE_CUTOFF = 0.55  # Market must show >55% for a side to bet
DEFAULT_HIGH_EDGE_THRESHOLD = 0.10  # Threshold for high edge disagreement

# Confidence level thresholds (edge-based: larger edge = higher confidence)
HIGH_CONFIDENCE_MIN_EDGE = 0.15  # Edge >= 15% = HIGH confidence
MEDIUM_CONFIDENCE_MIN_EDGE = 0.08  # Edge 8-15% = MEDIUM confidence
# Below 8% = LOW confidence

# Market probability sanity check
MAX_MARKET_PROBABILITY = 0.99  # Reject markets with probability > 99% (arbitrage check)

# Portfolio betting parameters
MAX_DAILY_RISK_PCT = 0.25  # 25% maximum daily risk exposure
KELLY_FRACTION = 0.25  # Quarter Kelly betting strategy
MAX_BET_SIZE = 50.0  # Maximum bet size in dollars (portfolio betting)
DEFAULT_KALSHI_BET_SIZE = 5.0  # Default bet size for Kalshi API (safety default)
MAX_SINGLE_BET_PCT = 0.05  # Maximum 5% of bankroll per bet
MIN_EDGE_FOR_BET = 0.05  # Minimum edge required for betting
MIN_CONFIDENCE_FOR_BET = 0.68  # Minimum confidence level required
