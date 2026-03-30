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
DEFAULT_MIN_EDGE = (
    0.03  # Minimum 3% edge (Elo prob - market prob) required (positive EV)
)
DEFAULT_MARKET_CONFIDENCE_CUTOFF = 0.55  # Market must show >55% for a side to bet
DEFAULT_HIGH_EDGE_THRESHOLD = (
    0.12  # 12% edge required for high-confidence bets (updated to match DAG)
)

# Confidence level thresholds (edge-based: larger edge = higher confidence)
HIGH_CONFIDENCE_MIN_EDGE = 0.15  # Edge >= 15% = HIGH confidence
MEDIUM_CONFIDENCE_MIN_EDGE = 0.08  # Edge 8-15% = MEDIUM confidence
# Below 8% = LOW confidence

# Bookmaker configuration
# Primary bookmaker to use for betting (system is designed for Kalshi)
# If primary not available, system can fallback to secondary
PRIMARY_BOOKMAKER = "Kalshi"
SECONDARY_BOOKMAKER = "SBR"
# List of acceptable bookmakers in priority order
ACCEPTABLE_BOOKMAKERS = ["Kalshi", "SBR", "fanduel", "betrivers", "bovada"]

# Market probability sanity check
MAX_MARKET_PROBABILITY = 0.99  # Reject markets with probability > 99% (arbitrage check)

# Portfolio betting parameters
MAX_DAILY_RISK_PCT = 0.25  # 25% maximum daily risk exposure
KELLY_FRACTION = 0.20  # Conservative Kelly fraction (20%) for more volume (matches DAG)
MAX_BET_SIZE = 10.0  # Lower max bet size ($10) to spread across more bets (matches DAG)
DEFAULT_KALSHI_BET_SIZE = 5.0  # Default bet size for Kalshi API (safety default)
CENTS_PER_DOLLAR = (
    100.0  # Conversion factor: 100 cents = $1.00 (Kalshi prices are in cents)
)
MAX_SINGLE_BET_PCT = 0.03  # Maximum 3% of bankroll per bet (matches DAG)
MIN_EDGE_FOR_BET = 0.03  # Minimum 3% edge required for betting (positive EV)
MIN_CONFIDENCE_FOR_BET = 0.68  # Minimum confidence level required

# Edge threshold constants (matches DAG values for consistency)
MAX_EDGE_THRESHOLD = 0.40  # Maximum 40% edge cap (reject likely data errors)
MARKET_CONFIDENCE_CUTOFF = 0.55  # Minimum market probability to consider a bet (55%)

# Analysis thresholds
MIN_CONFIDENCE_THRESHOLD = 0.0  # Set to 0.0 to rely on sport-specific elo_thresholds
MIN_GAMES_FOR_ANALYSIS = 15  # Minimum games required for statistical analysis
MIN_WINS_FOR_HIGH_CONFIDENCE = (
    5  # Minimum wins required for high confidence classification
)
MIN_WINS_FOR_MEDIUM_CONFIDENCE = (
    5  # Minimum wins required for medium confidence classification
)
MIN_WIN_RATE_FOR_BETTING = 0.80  # Minimum 80% win rate to consider betting on a segment
MIN_WIN_RATE_FOR_HIGH_CONFIDENCE = 0.80  # Minimum 80% win rate for high confidence bets

# Game ID parsing constants
GAME_ID_LENGTH = 10  # Standard length for NHL and NBA game IDs
YEAR_PART_LENGTH = 4  # Length of year prefix in game IDs
MIN_YEAR = 2000  # Minimum valid year for game IDs
MAX_YEAR = 2099  # Maximum valid year for game IDs
NBA_GAME_ID_PREFIX = "002"  # Prefix for NBA game IDs
MILLISECONDS_TO_SECONDS_DIVISOR = 1000.0  # Convert milliseconds to seconds
SEASON_YEAR_LENGTH = 4  # Length of year in season strings

# Database column constants
BASE_GAME_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "is_neutral",
]

# Common column subsets for different use cases
GAME_IDENTITY_COLUMNS = ["game_id", "game_date", "season", "home_team", "away_team"]
GAME_SCORE_COLUMNS = ["home_score", "away_score"]
GAME_RESULT_COLUMNS = GAME_IDENTITY_COLUMNS + GAME_SCORE_COLUMNS + ["is_neutral"]

# P&L Diagnostic constants
# Date before which CLV data is known to be broken (binary outcomes, not real closing prices)
# All bets before this date have closing_line_prob of 0.0 or 1.0
from datetime import date

BUG_ERA_CUTOFF_DATE = date(2026, 3, 30)  # CLV fix deployed on this date

# Minimum settled bets per sport to include in diagnostic analysis
MIN_BETS_FOR_DIAGNOSTIC = 50

# Bootstrap test parameters
BOOTSTRAP_N_ITERATIONS = 10_000
BOOTSTRAP_CONFIDENCE_LEVEL = 0.95

# Stale closing price threshold (hours before market close)
STALE_CLOSING_PRICE_HOURS = 4.0

# Kalshi closing line tracking
KALSHI_CLOSING_BOOKMAKER = "Kalshi_close"
KALSHI_CLOSING_WINDOW_MINUTES = 30

# Timing analysis bucket boundaries (hours before game, for closing-line analysis)
TIMING_BUCKETS = [0, 1, 2, 4, 8, float("inf")]
TIMING_BUCKET_LABELS = ["<1hr", "1-2hr", "2-4hr", "4-8hr", "8+hr"]

# Fill time analysis bucket boundaries (hours before game at Kalshi fill time)
# placed_time_utc = Kalshi fill timestamp (created_time from fills API)
FILL_TIME_BUCKETS = [0, 2, 4, 8, 24, float("inf")]
FILL_TIME_BUCKET_LABELS = ["<2hr", "2-4hr", "4-8hr", "8-24hr", "24+hr"]
