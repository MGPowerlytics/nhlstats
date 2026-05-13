"""
Multi-Sport Betting Workflow DAG
Unified workflow for NBA, NHL, MLB, and NFL betting opportunities using Elo ratings.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import sys
import json
import smtplib
import os
import math
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add plugins directory to Python path
plugins_dir = Path(__file__).parent.parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))

from constants import ALL_SPORTS, GLICKO2_SPORTS, SINGLE_BETTING_SPORTS


def is_valid_score(score: Optional[float]) -> bool:
    """Check if a score is a valid number (not None, NaN, or inf)."""
    if score is None:
        return False
    try:
        if math.isnan(score) or math.isinf(score):
            return False
    except (TypeError, ValueError):
        return False
    return True


@dataclass
class DailyBalanceSummary:
    """Data class for daily balance summary information.

    Groups related primitive parameters that are passed together through the system.
    """

    date_str: str  # Date in YYYY-MM-DD format
    cash_balance: float  # Current cash balance
    portfolio_value: float  # Current portfolio value

    @property
    def total_value(self) -> float:
        """Total value (cash + portfolio)."""
        return self.cash_balance + self.portfolio_value


# Import Elo factory


# SMTP alerting disabled - set to True to re-enable
SMTP_ALERTING_ENABLED = False

# Betting strategy parameters - extracted from magic numbers for clarity and maintainability
MIN_EDGE_THRESHOLD = 0.03  # Minimum 3% positive edge required (positive EV)
MAX_EDGE_THRESHOLD = 0.40  # Maximum 40% edge cap (reject likely data errors)
MAX_DAILY_RISK_PCT = 0.25  # Maximum 25% of bankroll risked per day
KELLY_FRACTION = 0.20  # Conservative Kelly fraction (20%) for more volume
MAX_BET_SIZE = 10.0  # Lower max bet size ($10) to spread across more bets
MAX_SINGLE_BET_PCT = 0.03  # Maximum 3% of bankroll on any single bet
MIN_CONFIDENCE_THRESHOLD = 0.65  # Minimum confidence threshold for high-confidence bets
MIN_GAMES_FOR_ANALYSIS = 15  # Minimum games required for statistical analysis
MIN_WINS_FOR_HIGH_CONFIDENCE = (
    5  # Minimum wins required for high confidence classification
)
MIN_WINS_FOR_MEDIUM_CONFIDENCE = (
    5  # Minimum wins required for medium confidence classification
)
MIN_WIN_RATE_FOR_BETTING = 0.80  # Minimum 80% win rate to consider betting on a segment
MIN_WIN_RATE_FOR_HIGH_CONFIDENCE = 0.80  # Minimum 80% win rate for high confidence bets

# UI and Reporting Constants
MAX_PLAYER_NAME_LEN_SMS = 15  # Maximum player/team name length in SMS
TOP_BETS_COUNT_SMS = 5  # Number of top bets to show in SMS summary
SMS_SUMMARY_NAME_LEN = 12  # Maximum name length in daily summary SMS
SMS_SUMMARY_MSG2_COUNT = 3  # Number of top bets in second summary SMS
SMS_SUMMARY_MSG3_MAX = 8  # Maximum bet index to show in third summary SMS

# DAG Configuration
DAG_START_YEAR = 2026
DAG_RETRY_COUNT = 2
DAG_RETRY_DELAY_MINS = 10
DEFAULT_SCHEDULE_DAY_OFFSETS = (-1, 0)
MLB_SCHEDULE_DAY_OFFSETS = (-1, 0, 1, 2)


def send_sms(to_number: str, subject: str, body: str) -> bool:
    """Send SMS via Verizon email gateway using Gmail SMTP.

    Args:
        to_number: Phone number (without formatting)
        subject: SMS subject line
        body: SMS message body

    Returns:
        True if sent successfully, False otherwise
    """
    if not SMTP_ALERTING_ENABLED:
        print(f"📵 SMTP alerting disabled - would have sent: {subject}")
        return True  # Return True so downstream tasks don't fail

    try:
        smtp_host = os.getenv("AIRFLOW__SMTP__SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("AIRFLOW__SMTP__SMTP_PORT", "587"))
        smtp_user = os.getenv("AIRFLOW__SMTP__SMTP_USER")
        smtp_password = os.getenv("AIRFLOW__SMTP__SMTP_PASSWORD")

        if not all([smtp_user, smtp_password]):
            print("⚠️  SMTP credentials not configured")
            return False

        # Create message
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = f"{to_number}@vtext.com"
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Send via Gmail SMTP
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        return True
    except Exception as e:
        print(f"⚠️  Failed to send SMS: {e}")
        return False


def serialize_datetime(obj: Any) -> Any:
    """Convert datetime objects to ISO format strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


__all__ = [
    "download_games",
    "load_data_to_db",
    "update_elo_ratings",
    "fetch_prediction_markets",
    "fetch_mlb_current_odds",
    "score_mlb_model_predictions",
    "train_tennis_probability_model",
    "update_glicko2_ratings",
    "load_bets_to_db",
    "identify_good_bets",
    "place_bets_on_recommendations",
    "place_portfolio_optimized_bets",
    "send_daily_summary",
    "update_clv_wrapper",
]

# Sport configurations
# Per-sport settings used by ingestion, Elo, and Kalshi market fetchers.
# Betting decisions use a pure positive-EV strategy (edge >= MIN_EDGE_THRESHOLD)
# with per-sport confidence floors enforced by
# PortfolioOptimizer._get_sport_min_confidence — there is no per-sport
# elo_threshold or market_confidence_cutoff anymore.
SPORTS_CONFIG = {
    "nba": {
        "elo_module": "elo",
        "games_module": "nba_games",
        "downloader_class": "NBAGames",
        "use_dates_loop": True,
        "has_error_handling": True,
        "kalshi_function": "fetch_nba_markets",
        "series_ticker": "KXNBAGAME",
        "team_mapping": {
            "ATL": "Hawks",
            "BOS": "Celtics",
            "BKN": "Nets",
            "CHA": "Hornets",
            "CHI": "Bulls",
            "CLE": "Cavaliers",
            "DAL": "Mavericks",
            "DEN": "Nuggets",
            "DET": "Pistons",
            "GSW": "Warriors",
            "HOU": "Rockets",
            "IND": "Pacers",
            "LAC": "Clippers",
            "LAL": "Lakers",
            "MEM": "Grizzlies",
            "MIA": "Heat",
            "MIL": "Bucks",
            "MIN": "Timberwolves",
            "NOP": "Pelicans",
            "NYK": "Knicks",
            "OKC": "Thunder",
            "ORL": "Magic",
            "PHI": "76ers",
            "PHX": "Suns",
            "POR": "Trail Blazers",
            "SAC": "Kings",
            "SAS": "Spurs",
            "TOR": "Raptors",
            "UTA": "Jazz",
            "WAS": "Wizards",
        },
    },
    "nhl": {
        "elo_module": "elo",
        "games_module": "nhl_game_events",
        "downloader_class": "NHLGameEvents",
        "use_dates_loop": True,
        "has_error_handling": False,
        "kalshi_function": "fetch_nhl_markets",
        "series_ticker": "KXNHLGAME",
        "team_mapping": {
            "ANA": "ANA",
            "BOS": "BOS",
            "BUF": "BUF",
            "CAR": "CAR",
            "CBJ": "CBJ",
            "CGY": "CGY",
            "CHI": "CHI",
            "COL": "COL",
            "DAL": "DAL",
            "DET": "DET",
            "EDM": "EDM",
            "FLA": "FLA",
            "LAK": "LAK",
            "MIN": "MIN",
            "MTL": "MTL",
            "NJD": "NJD",
            "NSH": "NSH",
            "NYI": "NYI",
            "NYR": "NYR",
            "OTT": "OTT",
            "PHI": "PHI",
            "PIT": "PIT",
            "SEA": "SEA",
            "SJS": "SJS",
            "STL": "STL",
            "TBL": "TBL",
            "TOR": "TOR",
            "VAN": "VAN",
            "VGK": "VGK",
            "WPG": "WPG",
            "WSH": "WSH",
            "ARI": "ARI",
        },
    },
    "mlb": {
        "elo_module": "elo",
        "games_module": "mlb_games",
        "downloader_class": "MLBGames",
        "use_dates_loop": True,
        "schedule_day_offsets": MLB_SCHEDULE_DAY_OFFSETS,
        "has_error_handling": False,
        "kalshi_function": "fetch_mlb_markets",
        "series_ticker": "KXMLBGAME",
        "team_mapping": {
            "ARI": "Arizona Diamondbacks",
            "ATH": "Athletics",
            "ATL": "Atlanta Braves",
            "BAL": "Baltimore Orioles",
            "BOS": "Boston Red Sox",
            "CHC": "Chicago Cubs",
            "CWS": "Chicago White Sox",
            "CIN": "Cincinnati Reds",
            "CLE": "Cleveland Guardians",
            "COL": "Colorado Rockies",
            "DET": "Detroit Tigers",
            "HOU": "Houston Astros",
            "KC": "Kansas City Royals",
            "LAA": "Los Angeles Angels",
            "LAD": "Los Angeles Dodgers",
            "MIA": "Miami Marlins",
            "MIL": "Milwaukee Brewers",
            "MIN": "Minnesota Twins",
            "NYM": "New York Mets",
            "NYY": "New York Yankees",
            "OAK": "Athletics",
            "PHI": "Philadelphia Phillies",
            "PIT": "Pittsburgh Pirates",
            "SD": "San Diego Padres",
            "SEA": "Seattle Mariners",
            "SF": "San Francisco Giants",
            "STL": "St. Louis Cardinals",
            "TB": "Tampa Bay Rays",
            "TEX": "Texas Rangers",
            "TOR": "Toronto Blue Jays",
            "WSH": "Washington Nationals",
        },
    },
    "nfl": {
        "elo_module": "elo",
        "games_module": "nfl_games",
        "downloader_class": "NFLGames",
        "use_dates_loop": True,
        "has_error_handling": False,
        "kalshi_function": "fetch_nfl_markets",
        "series_ticker": "KXNFLGAME",
        "team_mapping": {},  # Will be populated from database
    },
    "epl": {
        "elo_module": "elo",
        "games_module": "epl_games",
        "downloader_class": "EPLGames",
        "use_dates_loop": False,
        "has_error_handling": False,
        "kalshi_function": "fetch_epl_markets",
        "series_ticker": "KXEPLGAME",
        "team_mapping": {
            "MCI": "Man City",
            "MUN": "Man United",
            "NEW": "Newcastle",
            "WHU": "West Ham",
            "AVL": "Aston Villa",
            "BHA": "Brighton",
            "WOL": "Wolves",
            "SHU": "Sheffield United",
            "NOT": "Nott'm Forest",
            "NFO": "Nott'm Forest",
            "CRY": "Crystal Palace",
            "TOT": "Tottenham",
            "SOU": "Southampton",
            "LEI": "Leicester",
            "LEE": "Leeds",
        },
    },
    "tennis": {
        "elo_module": "elo",
        "games_module": "tennis_games",
        "downloader_class": "TennisGames",
        "use_dates_loop": False,
        "has_error_handling": False,
        "kalshi_function": "fetch_tennis_markets",
        "series_ticker": "TENNIS",  # Placeholder
        "team_mapping": {},
    },
    "ncaab": {
        "elo_module": "elo",
        "games_module": "ncaab_games",
        "downloader_class": "NCAABGames",
        "use_dates_loop": False,
        "has_error_handling": False,
        "kalshi_function": "fetch_ncaab_markets",
        "series_ticker": "KXNCAAMBGAME",
        "team_mapping": {},
    },
    "ligue1": {
        "elo_module": "elo",
        "games_module": "ligue1_games",
        "downloader_class": "Ligue1Games",
        "use_dates_loop": False,
        "has_error_handling": False,
        "kalshi_function": "fetch_ligue1_markets",
        "series_ticker": "KXLIGUE1GAME",
        "team_mapping": {
            "PSG": "PSG",
            "PAR": "PSG",
            "MAR": "Marseille",
            "OLM": "Marseille",
            "LYO": "Lyon",
            "OL": "Lyon",
            "MON": "Monaco",
            "ASM": "Monaco",
            "LIL": "Lille",
            "LOSC": "Lille",
            "NIC": "Nice",
            "OGCN": "Nice",
            "REN": "Rennes",
            "SRFC": "Rennes",
            "LEN": "Lens",
            "RCL": "Lens",
            "NAT": "Nantes",
            "FCN": "Nantes",
            "AUX": "Auxerre",
            "AJA": "Auxerre",
            "LHA": "Le Havre",
            "HAC": "Le Havre",
            "LOR": "Lorient",
            "FCL": "Lorient",
            "TOU": "Toulouse",
            "TFC": "Toulouse",
            "ANG": "Angers",
            "SCO": "Angers",
            "BRE": "Brest",
            "SB29": "Brest",
            "STR": "Strasbourg",
            "RCS": "Strasbourg",
            "REI": "Reims",
            "SDR": "Reims",
            "FCM": "Montpellier",
            "STB": "Brest",
        },
    },
    "wncaab": {
        "elo_module": "elo",
        "games_module": "wncaab_games",
        "downloader_class": "WNCAABGames",
        "use_dates_loop": False,
        "has_error_handling": False,
        "kalshi_function": "fetch_wncaab_markets",
        "series_ticker": "KXNCAAWBGAME",
        "team_mapping": {},
    },
    "unrivaled": {
        "elo_module": "elo",
        "games_module": "unrivaled_games",
        "downloader_class": "UnrivaledGames",
        "use_dates_loop": False,
        "has_error_handling": False,
        "kalshi_function": "fetch_unrivaled_markets",
        "series_ticker": "KXUNRIVALED",
        "team_mapping": {
            "ROSE": "Rose BC",
            "LUNAR": "Lunar Owls BC",
            "OWLS": "Lunar Owls BC",
            "PHANTOM": "Phantom BC",
            "MIST": "Mist BC",
            "VINYL": "Vinyl BC",
            "LACES": "Laces BC",
        },
    },
    "cba": {
        "elo_module": "elo",
        "games_module": "cba_games",
        "downloader_class": "CBAGames",
        "use_dates_loop": False,
        "has_error_handling": False,
        "kalshi_function": "fetch_cba_markets",
        "series_ticker": "KXCBAGAME",  # Placeholder for future Kalshi markets
        "team_mapping": {
            "GUA": "Guangdong Southern Tigers",
            "LIA": "Liaoning Flying Leopards",
            "BEI": "Beijing Ducks",
            "SHA": "Shanghai Sharks",
            "ZHE": "Zhejiang Lions",
            "SZN": "Shenzhen Leopards",
            "XIN": "Xinjiang Flying Tigers",
            "SDG": "Shandong Heroes",
            "JIL": "Jilin Northeast Tigers",
            "BRF": "Beijing Royal Fighters",
            "FUJ": "Fujian Sturgeons",
            "SXI": "Shanxi Loongs",
            "JSD": "Jiangsu Dragons",
            "QDE": "Qingdao Eagles",
            "GZL": "Guangzhou Loong Lions",
            "TJP": "Tianjin Pioneers",
            "SCH": "Sichuan Blue Whales",
            "NBO": "Ningbo Rockets",
            "NJT": "Nanjing Tongxi Monkey Kings",
            "SZY": "Shanxi Zhongyu",
        },
    },
}


def _get_schedule_dates_to_process(
    sport: str, date_str: str, use_dates_loop: bool = True
) -> List[str]:
    """Get schedule dates to ingest/load for a sport.

    MLB intentionally loads two future dates to match the current Kalshi
    lookahead window; other date-loop sports remain on yesterday + today.
    """
    if not use_dates_loop:
        return [date_str]

    current_date = datetime.strptime(date_str, "%Y-%m-%d")
    schedule_day_offsets = SPORTS_CONFIG.get(sport, {}).get(
        "schedule_day_offsets", DEFAULT_SCHEDULE_DAY_OFFSETS
    )
    return [
        (current_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        for day_offset in schedule_day_offsets
    ]


def download_games(sport: str, **context: Any) -> None:
    """Download latest games for a sport using registry pattern."""
    print(f"📥 Downloading {sport.upper()} games...")

    if sport not in SPORTS_CONFIG:
        print(f"⚠️  Unknown sport: {sport}")
        return

    # Get date from context
    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))

    config = SPORTS_CONFIG[sport]
    module_name = config["games_module"]
    class_name = config["downloader_class"]
    use_dates_loop = config["use_dates_loop"]
    has_error_handling = config.get("has_error_handling", False)

    # Dynamic import
    module = __import__(module_name, fromlist=[class_name])
    downloader_class = getattr(module, class_name)

    # Determine dates to process
    dates_to_process = _get_schedule_dates_to_process(sport, date_str, use_dates_loop)

    # Execute downloads
    for d_str in dates_to_process:
        try:
            if use_dates_loop:
                downloader = downloader_class(date_folder=d_str)
                downloader.download_games_for_date(d_str)
            else:
                downloader = downloader_class()
                downloader.download_games()
            print(f"✓ Successfully downloaded {sport.upper()} games for {d_str}")
        except Exception as e:
            if has_error_handling:
                print(f"⚠️  Failed to download {sport.upper()} games for {d_str}: {e}")
                print("⚠️  Continuing with other sports...")
            else:
                raise

    print(f"✓ {sport.upper()} games downloaded")


def load_data_to_db(sport: str, **context: Any) -> None:
    """Load downloaded games into PostgreSQL."""
    print(f"💾 Loading {sport.upper()} games into database...")

    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
    dates_to_process = _get_schedule_dates_to_process(sport, date_str)

    # Create DBManager instance with default connection string
    db_manager = _create_db_manager()

    # Load data using appropriate database backend
    count = _load_sport_data(sport, dates_to_process, date_str, db_manager)

    print(f"✓ Loaded {count} new games/updates for {dates_to_process}")


def _create_db_manager() -> Any:
    """Create DBManager instance.

    Returns:
        DBManager instance

    Raises:
        Exception: If PostgreSQL is unavailable
    """
    from db_manager import DBManager
    from sqlalchemy import text

    db_manager = DBManager()
    print(f"✓ DBManager created successfully: {db_manager}")

    # Test the connection to make sure it actually works
    try:
        # Try a simple query to test the connection
        with db_manager.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ PostgreSQL connection test successful")
        return db_manager
    except Exception as e:
        print(f"❌ PostgreSQL connection test failed: {e}")
        raise


def _load_sport_data(
    sport: str, dates_to_process: List[str], date_str: str, db_manager: Any
) -> Union[int, str]:
    """Load data for a specific sport using PostgreSQL loader.

    Returns:
        Number of games loaded (int) or "all" for tennis
    """
    try:
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader(db_manager=db_manager, sport=sport)
        return _load_sport_data_with_loader(sport, dates_to_process, date_str, loader)
    except Exception as e:
        print(f"⚠️ Failed to load data for {sport}: {e}")
        print("⚠️ This may happen for sports without proper database loaders")
        print("⚠️ Returning 0 to allow DAG to continue")
        import traceback

        traceback.print_exc()
        return 0


def _load_sport_data_with_loader(
    sport: str, dates_to_process: List[str], date_str: str, loader: Any
) -> Union[int, str]:
    """Load sport data using the provided loader.

    Args:
        sport: Sport identifier
        dates_to_process: List of dates to process
        date_str: Current date string
        loader: NHLDatabaseLoader instance

    Returns:
        Number of games loaded (int) or "all" for tennis
    """
    with loader:
        # Handle sports that need full history reload
        if sport in _get_full_history_sports():
            return _load_full_history_sport(sport, date_str, loader)

        # Handle sports that use dedicated fetchers
        if sport in _get_fetcher_based_sports():
            return _load_fetcher_based_sport(sport, loader)

        # Handle date-based sports (NBA, NHL, MLB, NFL)
        return _load_date_based_sport(dates_to_process, loader)


def _get_full_history_sports() -> List[str]:
    """Get list of sports that require full history reload."""
    return ["tennis", "epl", "ligue1"]


def _get_fetcher_based_sports() -> List[str]:
    """Get list of sports that use dedicated fetchers."""
    return ["ncaab", "wncaab", "unrivaled", "cba"]


def _load_full_history_sport(sport: str, date_str: str, loader: Any) -> str:
    """Load sport data for sports requiring full history reload.

    Args:
        sport: Sport identifier
        date_str: Current date string
        loader: NHLDatabaseLoader instance

    Returns:
        Always returns "all" to indicate full history was loaded
    """
    # Map sport names to CSV history identifiers
    csv_sport_map = {"tennis": "Tennis", "epl": "EPL", "ligue1": "Ligue1"}

    csv_sport = csv_sport_map.get(sport, sport)
    loader.load_csv_history(csv_sport, target_date=date_str)
    return "all"


def _load_fetcher_based_sport(sport: str, loader: Any) -> str:
    """Load sport data for sports using dedicated fetchers.

    Args:
        sport: Sport identifier
        loader: NHLDatabaseLoader instance

    Returns:
        Always returns "all" to indicate full history was loaded
    """
    loader.load_sport_history_from_fetcher(sport)
    return "all"


def _load_date_based_sport(dates_to_process: List[str], loader: Any) -> int:
    """Load sport data for date-based sports (NBA, NHL, MLB, NFL).

    Args:
        dates_to_process: List of dates to process
        loader: NHLDatabaseLoader instance

    Returns:
        Total number of games loaded
    """
    count = 0
    for date in dates_to_process:
        count += loader.load_date(date)
    return count


def _initialize_elo_system(sport: str, config) -> Any:
    """Initialize Elo rating system for a specific sport.

    Args:
        sport: Sport identifier (e.g., 'nba', 'nhl')
        config: Sport configuration from elo_update_config

    Returns:
        Initialized Elo rating instance
    """
    from elo import get_elo_class

    EloClass = get_elo_class(sport)

    # Initialize Elo instance with sport-specific parameters
    elo_init_kwargs = {
        "k_factor": config.k_factor,
        "home_advantage": config.home_advantage,
        "initial_rating": config.initial_rating,
    }
    if config.elo_init_kwargs:
        elo_init_kwargs.update(config.elo_init_kwargs)

    return EloClass(**elo_init_kwargs)


def _load_ligue1_ratings_from_csv(elo) -> None:
    """Load Ligue 1 ratings from CSV file if available.

    Args:
        elo: Elo rating instance to populate with team ratings
    """
    import csv

    ratings_path = Path("data/ligue1_current_elo_ratings.csv")
    if not ratings_path.exists():
        print(
            f"⚠️ Missing Ligue 1 ratings seed at {ratings_path}; "
            "continuing with empty ratings"
        )
        return

    with ratings_path.open("r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            elo.ratings[row["team"]] = float(row["rating"])
    print(f"✓ Loaded {len(elo.ratings)} Ligue 1 teams")


def _load_games_from_unified_table(sport: str, config) -> Any:
    """Load games from unified_games table for standard sports.

    Args:
        sport: Sport identifier
        config: Sport configuration

    Returns:
        DataFrame with game data or empty DataFrame if no games found
    """
    from plugins.db_manager import default_db

    query = (
        config.query
        or f"""
        SELECT game_date, home_team_name as home_team, away_team_name as away_team,
               home_score, away_score,
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM unified_games
        WHERE sport = '{sport.upper()}'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        ORDER BY game_date
    """
    )
    games_df = default_db.fetch_df(query)
    if games_df.empty:
        print(f"No {sport.upper()} games found in database")
    else:
        print(f"  Loaded {len(games_df)} {sport.upper()} games from unified_games")

    return games_df


def _load_soccer_games(sport: str, config) -> Any:
    """Load soccer games from their specific table.

    Args:
        sport: Sport identifier (epl or ligue1)
        config: Sport configuration

    Returns:
        DataFrame with game data or empty DataFrame if no games found
    """
    from plugins.db_manager import default_db

    table = f"{sport.lower()}_games"
    query = (
        config.query
        or f"""
        SELECT game_date, home_team, away_team, result
        FROM {table}
        WHERE game_date IS NOT NULL
        ORDER BY game_date
    """
    )
    games_df = default_db.fetch_df(query)
    if games_df.empty:
        print(f"No {sport.upper()} games found in database")
    else:
        print(f"  Loaded {len(games_df)} {sport.upper()} games")

    return games_df


def update_elo_ratings(sport: str, **context: Any) -> None:
    """Calculate current Elo ratings for a sport with logging."""
    print(f"📊 Updating {sport.upper()} Elo ratings...")

    # Import refactored helpers
    from plugins.elo.elo_update_helpers import (
        load_previous_ratings,
        process_games_with_elo,
        save_elo_ratings,
    )
    from plugins.elo.elo_update_config import get_sport_config

    # Load previous ratings for comparison
    previous_ratings = load_previous_ratings(sport)

    # Get sport configuration
    config = get_sport_config(sport)

    # Initialize Elo system
    elo = _initialize_elo_system(sport, config)

    # Load games based on sport type
    if sport in ["ncaab", "wncaab", "unrivaled", "tennis", "cba"]:
        # Sports that use their own games classes
        games_df = _load_games_from_sport_class(sport)
        if games_df.empty:
            print(f"⚠️ No {sport.upper()} games loaded")
            return
    elif sport in ["epl", "ligue1"]:
        # Soccer sports use their own tables for 3-way results
        games_df = _load_soccer_games(sport, config)
        if games_df.empty:
            return
    else:
        # Standard sports that use unified_games table
        games_df = _load_games_from_unified_table(sport, config)
        if games_df.empty:
            return

    # Process games through Elo system
    games_processed = process_games_with_elo(elo, games_df, config)
    print(f"  ✅ Processed {games_processed} total games")

    # Save ratings to CSV and push to XCom
    save_elo_ratings(sport, elo, previous_ratings, context)


def _load_games_from_sport_class(sport: str):
    """Load games using sport-specific games class from SPORTS_CONFIG."""
    if sport not in SPORTS_CONFIG:
        import pandas as pd

        return pd.DataFrame()

    config = SPORTS_CONFIG[sport]
    module_name = config["games_module"]
    class_name = config["downloader_class"]

    # Dynamic import
    module = __import__(module_name, fromlist=[class_name])
    games_class = getattr(module, class_name)
    games_obj = games_class()

    # CBA uses a different method name
    if sport == "cba":
        return games_obj.get_completed_games()

    return games_obj.load_games()


def fetch_prediction_markets(sport: str, **context: Any) -> None:
    """Fetch prediction markets for a sport."""
    print(f"💰 Fetching {sport.upper()} prediction markets...")

    if sport not in SPORTS_CONFIG:
        print(f"⚠️  Unknown sport: {sport}")
        return

    import kalshi_markets

    # Get fetch function name from config
    func_name = SPORTS_CONFIG[sport].get("kalshi_function")
    if not func_name:
        print(f"⚠️  No kalshi_function defined for {sport}")
        return

    fetch_function = getattr(kalshi_markets, func_name)

    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
    markets = fetch_function(date_str)

    if not markets:
        print(f"ℹ️  No {sport.upper()} markets available")
        return

    # Helper for JSON serialization
    def json_serial(obj: Any) -> Any:
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    # Save to file
    markets_file = Path(f"data/{sport}/markets_{date_str}.json")
    markets_file.parent.mkdir(parents=True, exist_ok=True)
    with open(markets_file, "w") as f:
        json.dump(markets, f, indent=2, default=json_serial)

    # Push to XCom
    context["task_instance"].xcom_push(key=f"{sport}_markets", value=markets)

    print(f"✓ Found {len(markets)} {sport.upper()} markets")


def score_mlb_model_predictions(**context: Any) -> Dict[str, int]:
    """Airflow callable for governed MLB model-health prediction rows."""
    print("🧮 Scoring MLB moneyline model predictions...")
    from plugins.mlb_modeling.airflow_tasks import score_mlb_moneyline_model

    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
    result = score_mlb_moneyline_model(run_date=date_str)
    print(
        "✓ MLB model scoring complete: "
        f"{result['predictions_written']} predictions, "
        f"{result['abstentions_written']} abstentions"
    )
    return result


def fetch_mlb_current_odds(**context: Any) -> int:
    """Fetch free/current MLB bookmaker odds for future ROI and CLV evidence."""
    print("📈 Fetching MLB current bookmaker odds...")
    from plugins.the_odds_api import TheOddsAPI

    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
    api = TheOddsAPI()
    saved = api.fetch_and_save_markets("mlb", date_str)
    print(f"✓ MLB current bookmaker odds saved: {saved}")
    return saved


def train_tennis_probability_model(**context: Any) -> Dict[str, Any]:
    """Refresh the production tennis probability-model artifact from PostgreSQL."""
    print("🎾 Training tennis probability model artifact...")
    from plugins.elo.tennis_probability_model import train_production_model

    result = train_production_model()
    payload = result.to_payload()
    print(
        "✓ Tennis model training complete: "
        f"{payload['feature_frame_rows']} feature rows, "
        f"enabled={payload['enabled']}, "
        f"metrics_published={payload['metrics_published']}"
    )
    return payload


def _initialize_glicko2_system(sport: str) -> Optional[Any]:
    """Initialize Glicko-2 rating system for a specific sport.

    Args:
        sport: Sport identifier (e.g., 'nba', 'nhl')

    Returns:
        Initialized Glicko-2 rating instance or None if not implemented
    """
    from glicko2_rating import (
        NBAGlicko2Rating,
        NHLGlicko2Rating,
        MLBGlicko2Rating,
        NFLGlicko2Rating,
    )

    glicko_classes = {
        "nba": NBAGlicko2Rating,
        "nhl": NHLGlicko2Rating,
        "mlb": MLBGlicko2Rating,
        "nfl": NFLGlicko2Rating,
    }

    if sport not in glicko_classes:
        print(f"⚠️  Glicko-2 not implemented for {sport}")
        return None

    return glicko_classes[sport]()


def _load_glicko2_games_df(sport: str) -> Any:
    """Load games from database for Glicko-2 updates.

    Args:
        sport: Sport identifier

    Returns:
        DataFrame with game data or empty DataFrame if no games found
    """
    from plugins.db_manager import default_db
    import pandas as pd

    if sport == "nba":
        # Query NBA games from database
        query = """
            SELECT game_date, home_team, away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM nba_games
            WHERE status = 'Final'
            ORDER BY game_date, game_id
        """
    elif sport == "nhl":
        query = """
            SELECT game_date, home_team_abbrev as home_team, away_team_abbrev as away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM games WHERE game_state IN ('OFF', 'FINAL', 'Final') ORDER BY game_date, game_id
        """
    elif sport in ["mlb", "nfl"]:
        table_name = f"{sport}_games"
        if sport == "mlb":
            # Mirror _get_mlb_query: exclude spring training (S), exhibitions (E),
            # and All-Star (A) games so Glicko-2 ratings stay aligned with Elo.
            query = f"""
                SELECT game_date, home_team, away_team,
                       CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
                FROM {table_name}
                WHERE game_date IS NOT NULL
                  AND home_score IS NOT NULL
                  AND away_score IS NOT NULL
                  AND game_type IN ('R', 'D', 'L', 'W', 'F')
                  AND status IN ('Final', 'Game Over', 'Completed Early')
                ORDER BY game_date
            """
        else:
            query = f"""
                SELECT game_date, home_team, away_team,
                       CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
                FROM {table_name}
                WHERE game_date IS NOT NULL
                  AND home_score IS NOT NULL
                  AND away_score IS NOT NULL
                ORDER BY game_date
            """
    else:
        return pd.DataFrame()

    return default_db.fetch_df(query)


def _save_glicko2_ratings_to_csv(sport: str, ratings: Dict[str, Any]) -> None:
    """Save Glicko-2 ratings to a CSV file and ensure the directory exists.

    Args:
        sport: Sport identifier
        ratings: Glicko-2 ratings dictionary
    """
    csv_path = Path(f"data/{sport}_current_glicko2_ratings.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, "w") as f:
        f.write("team,rating,rd,volatility\n")
        for team in sorted(ratings.keys()):
            r = ratings[team]
            f.write(f"{team},{r['rating']:.2f},{r['rd']:.2f},{r['vol']:.6f}\n")


def update_glicko2_ratings(sport: str, **context: Any) -> None:
    """Calculate current Glicko-2 ratings for a sport."""
    print(f"📊 Updating {sport.upper()} Glicko-2 ratings...")

    glicko = _initialize_glicko2_system(sport)
    if not glicko:
        return

    games_df = _load_glicko2_games_df(sport)
    if games_df.empty:
        print(f"⚠️ No {sport.upper()} games loaded for Glicko-2")
        return

    print(f"  Loaded {len(games_df)} {sport.upper()} games for Glicko-2")
    for _, game in games_df.iterrows():
        glicko.update(game["home_team"], game["away_team"], game["home_win"])

    # Save ratings to CSV
    _save_glicko2_ratings_to_csv(sport, glicko.ratings)

    # Push to XCom
    context["task_instance"].xcom_push(
        key=f"{sport}_glicko2_ratings", value=glicko.ratings
    )

    print(f"✓ {sport.upper()} Glicko-2 ratings updated: {len(glicko.ratings)} teams")


def load_bets_to_db(sport: str, **context: Any) -> None:
    """Load bet recommendations into database."""
    print(f"💾 Loading {sport.upper()} bets into database...")

    from bet_loader import BetLoader

    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
    loader = BetLoader()
    count = loader.load_bets_for_date(sport, date_str)

    print(f"✓ Loaded {count} {sport.upper()} bets into database")


def _load_elo_system(sport: str, elo_ratings: dict) -> object:
    """Load Elo ratings into the appropriate Elo system for a sport.

    Args:
        sport: Sport name (e.g., 'nba', 'tennis')
        elo_ratings: Elo ratings dictionary from XCom

    Returns:
        Initialized Elo system with ratings loaded
    """
    config = SPORTS_CONFIG[sport]

    # Import Elo module to get predict function
    elo_module_name: str = config["elo_module"]  # type: ignore
    elo_module = __import__(elo_module_name)
    # Map sport names to their Elo class names
    class_mapping = {
        "tennis": "TennisEloRating",
        "ncaab": "NCAABEloRating",
        "wncaab": "WNCAABEloRating",
        "ligue1": "Ligue1EloRating",
    }
    class_name = class_mapping.get(sport, f"{sport.upper()}EloRating")
    elo_class = getattr(elo_module, class_name)
    elo_system = elo_class()

    # Load sport-specific Elo ratings into the Elo system.
    if sport == "tennis":
        atp = (
            (elo_ratings or {}).get("ATP", {}) if isinstance(elo_ratings, dict) else {}
        )
        wta = (
            (elo_ratings or {}).get("WTA", {}) if isinstance(elo_ratings, dict) else {}
        )
        elo_system.atp_ratings = dict(atp)
        elo_system.wta_ratings = dict(wta)
    else:
        elo_system.ratings = elo_ratings

    if sport == "mlb":
        if _mlb_uses_governed_model():
            setattr(elo_system, "requires_governed_predictions", True)
            print("  🧮 MLB governed prediction mode enabled (no Elo fallback)")
        else:
            elo_system = _maybe_wrap_mlb_with_ensemble(elo_system)
    elif sport == "ligue1":
        elo_system = _maybe_wrap_ligue1_with_ensemble(elo_system)

    return elo_system


def _mlb_uses_governed_model() -> bool:
    """Return whether MLB betting must use governed prediction rows."""
    try:
        from elo_update_config import MLB_USE_GOVERNED_MODEL
    except ImportError:
        from plugins.elo.elo_update_config import MLB_USE_GOVERNED_MODEL

    return bool(MLB_USE_GOVERNED_MODEL)


def _maybe_wrap_ligue1_with_ensemble(elo_system):
    """Wrap a :class:`Ligue1EloRating` in an ensemble adapter when enabled.

    Blends team Elo with ML models (XGB/LGB) and bookmaker probabilities.
    """
    try:
        from elo_update_config import LIGUE1_USE_ENSEMBLE
    except ImportError:
        from plugins.elo.elo_update_config import LIGUE1_USE_ENSEMBLE

    if not LIGUE1_USE_ENSEMBLE:
        return elo_system

    try:
        from plugins.elo.ligue1_ensemble_adapter import Ligue1EnsembleAdapter
        from plugins.db_manager import default_db

        adapter = Ligue1EnsembleAdapter()
        # Seed ensemble's underlying team_elo with the trained ratings
        adapter.ratings = dict(getattr(elo_system, "ratings", {}) or {})
        # Pre-compute season context (Form, Goal averages)
        adapter.populate_from_db(default_db)
        setattr(adapter, "governed_probability_source", "ligue1_live_ensemble")

        print(
            f"  🏟️  Ligue 1 Ensemble enabled ({len(adapter.team_stats)} teams w/ stats cached)"
        )

        return adapter
    except Exception as exc:  # noqa: BLE001
        print(
            f"⚠️ Ligue 1 ensemble adapter failed to initialize: {exc} — using plain Elo"
        )
        return elo_system


def _maybe_wrap_mlb_with_ensemble(elo_system):
    """Wrap an :class:`MLBEloRating` in an ensemble adapter when enabled.

    The DAG calls ``OddsComparator`` with whatever this returns, so the
    adapter must preserve the ``predict(home, away)``/``ratings`` surface.
    Falls back to the original ``elo_system`` on any error so a bug in the
    adapter cannot break the daily MLB pipeline.
    """
    try:
        from elo_update_config import MLB_USE_ENSEMBLE
    except ImportError:
        from plugins.elo.elo_update_config import MLB_USE_ENSEMBLE

    if not MLB_USE_ENSEMBLE:
        return elo_system

    try:
        from plugins.elo.mlb_ensemble_adapter import MLBEnsembleAdapter
        from plugins.db_manager import default_db

        adapter = MLBEnsembleAdapter()
        # Seed ensemble's underlying team_elo with the trained ratings
        adapter.ratings = dict(getattr(elo_system, "ratings", {}) or {})
        # Load side-data (pitcher ratings)
        adapter.load_ratings()
        # Pre-compute season context (Pythagorean, form, rest)
        adapter.populate_from_db(default_db)

        # Verify if we found any pitchers
        p_count = len(adapter.ensemble.pitcher_elo.all_ratings())
        print(
            f"  🏟️  MLB Ensemble enabled ({p_count} pitcher ratings loaded, "
            f"{len(adapter.team_stats)} teams w/ stats, "
            f"{len(adapter.venues)} venues cached)"
        )

        return adapter
    except Exception as exc:  # noqa: BLE001 - intentional broad catch
        print(f"⚠️ MLB ensemble adapter failed to initialize: {exc} — using plain Elo")
        return elo_system


def _setup_ncaab_name_mapping() -> None:
    """Setup NCAAB name mappings for Kalshi and Elo systems."""
    from naming_resolver import NamingResolver, NamingContext

    ncaab_mapping = {
        "HOU": "Houston",
        "PUR": "Purdue",
        "AUB": "Auburn",
        "ALA": "Alabama",
        "BYU": "BYU",
        "UGA": "Georgia",
        "LSU": "LSU",
        "DAY": "Dayton",
        "VCU": "VCU",
        "KAN": "Kansas",
        "KEN": "Kentucky",
        "DUK": "Duke",
        "UNC": "North_Carolina",
        "AZ": "Arizona",
        "GONZ": "Gonzaga",
        "CONN": "Connecticut",
        "TENN": "Tennessee",
        "ISU": "Iowa_St",
        "BAY": "Baylor",
        "ORE": "Oregon",
        "KSU": "Kansas_St",
        "FIU": "Florida_Intl",
        "TCU": "TCU",
        "WIS": "Wisconsin",
        "IND": "Indiana",
        "WKU": "Western_Kentucky",
        "SLU": "Saint_Louis",
        "UVM": "Vermont",
        "SFA": "Stephen_F._Austin",
        "LMU": "Loyola_Marymount",
        "QUC": "Queens_University",
        "APP": "Appalachian_St",
        "UND": "North_Dakota",
        "CIN": "Cincinnati",
        "WVU": "West_Virginia",
        "TEX": "Texas",
    }
    # Inject mappings into NamingResolver for this run
    for raw, canon in ncaab_mapping.items():
        NamingResolver.add_mapping(
            context=NamingContext("ncaab", "kalshi", raw), canonical_name=canon
        )
        NamingResolver.add_mapping(
            context=NamingContext("ncaab", "elo", canon), canonical_name=canon
        )


def _find_betting_opportunities(
    sport: str,
    elo_system: object,
    elo_ratings: dict,
    config: dict,
    date_str: Optional[str] = None,
) -> list:
    """Find betting opportunities using OddsComparator.

    Args:
        sport: Sport name
        elo_system: Initialized Elo system with ratings
        elo_ratings: Raw Elo ratings dictionary
        config: Sport configuration from SPORTS_CONFIG (currently unused but
            retained for forward compatibility)
        date_str: Optional reference date in ``YYYY-MM-DD`` form. Pass the
            Airflow ``ds`` here so "today" filtering is deterministic across
            runs and timezones.

    Returns:
        List of betting opportunity dictionaries
    """
    from odds_comparator import (
        OddsComparator,
        BettingThresholds,
        BettingOpportunityConfig,
    )

    comparator = OddsComparator()

    # Pure positive-EV strategy: only edge bounds are needed. Per-sport
    # confidence floors are enforced downstream by
    # PortfolioOptimizer._get_sport_min_confidence.
    thresholds = BettingThresholds(
        min_edge=MIN_EDGE_THRESHOLD,
        max_edge=MAX_EDGE_THRESHOLD,
    )

    opportunity_config = BettingOpportunityConfig(
        sport=sport,
        elo_system=elo_system,
        thresholds=thresholds,
        date_str=date_str,
        enforce_governance=True,
    )

    return comparator.find_opportunities(opportunity_config)


def _deduplicate_bets(good_bets: list) -> list:
    """Deduplicate bets by ticker.

    Args:
        good_bets: List of betting opportunity dictionaries

    Returns:
        Deduplicated list of betting opportunities
    """
    seen_tickers = set()
    unique_bets = []
    for bet in good_bets:
        ticker = bet.get("ticker")
        if ticker and ticker not in seen_tickers:
            unique_bets.append(bet)
            seen_tickers.add(ticker)
        elif not ticker:
            unique_bets.append(bet)
    return unique_bets


def _save_bets_to_file(
    sport: str, good_bets: List[Dict[str, Any]], context: Dict[str, Any]
) -> None:
    """Save betting opportunities to JSON file.

    Args:
        sport: Sport name
        good_bets: List of betting opportunity dictionaries
        context: Airflow context dictionary
    """
    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
    bets_file = Path(f"data/{sport}/bets_{date_str}.json")
    bets_file.parent.mkdir(parents=True, exist_ok=True)

    # Serialize for JSON
    def json_serial(obj: Any) -> Any:
        """JSON serializer for objects not serializable by default json code."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    with open(bets_file, "w") as f:
        json.dump(good_bets, f, indent=2, default=json_serial)


def _print_betting_summary(sport: str, good_bets: List[Dict[str, Any]]) -> None:
    """Print summary of betting opportunities.

    Args:
        sport: Sport name
        good_bets: List of betting opportunity dictionaries
    """
    print(f"✓ Found {len(good_bets)} unique {sport.upper()} betting opportunities")

    if good_bets:
        print(f"\n{sport.upper()} Betting Opportunities:")
        for bet in good_bets:
            home = bet.get("home_team", "Unknown")
            away = bet.get("away_team", "Unknown")
            print(f"  {away} @ {home}")
            print(
                f"    Bet: {bet['bet_on']} | Edge: {bet['edge']:.1%} | Elo: {bet['elo_prob']:.1%} | Odds: {bet['market_odds']:.2f}"
            )


def identify_good_bets(sport: str, **context: Any) -> None:
    """Identify good betting opportunities for a sport using OddsComparator."""
    print(f"🎯 Identifying {sport.upper()} betting opportunities...")

    # Pull data from XCom
    ti = context["task_instance"]
    elo_ratings = ti.xcom_pull(
        key=f"{sport}_elo_ratings", task_ids=f"{sport}_update_elo"
    )

    # We don't need markets from XCom anymore as they are in the DB
    # But we still need elo_ratings

    if not elo_ratings:
        print(f"⚠️  Missing Elo ratings for {sport}")
        return

    # Load Elo system with ratings
    elo_system = _load_elo_system(sport, elo_ratings)

    # Setup NCAAB name mapping if needed
    if sport == "ncaab":
        _setup_ncaab_name_mapping()

    # Find betting opportunities (use Airflow ds for deterministic "today")
    config = SPORTS_CONFIG[sport]
    date_str = context.get("ds") or datetime.now().strftime("%Y-%m-%d")
    good_bets = _find_betting_opportunities(
        sport, elo_system, elo_ratings, config, date_str=date_str
    )

    # Deduplicate bets
    good_bets = _deduplicate_bets(good_bets)

    # Save results
    _save_bets_to_file(sport, good_bets, context)

    # Print summary
    _print_betting_summary(sport, good_bets)


def place_bets_on_recommendations(sport: str, **context: Any) -> None:
    """
    DEPRECATED: Use place_portfolio_optimized_bets instead for unified betting.

    Place bets on recommended games (NBA, NCAAB, and TENNIS).

    CRITICAL: Verifies games have not started using The Odds API or close_time.

    Args:
        sport: Sport name (nba, ncaab, tennis)
        **context: Airflow context with bet recommendations
    """
    print(f"⚠️  DEPRECATED: Use portfolio betting task instead for {sport.upper()}")
    print("⚠️  This task is kept for backwards compatibility only")
    return


def _initialize_kalshi_client() -> Any:
    """Initialize Kalshi client with runtime-injected credentials.

    Returns:
        Initialized KalshiBetting client
    """
    from kalshi_betting import KalshiBetting, KalshiConfig

    config = KalshiConfig.from_env(production=True)
    return KalshiBetting(config=config)


def _get_excluded_segments() -> list[tuple[str, str]]:
    """Get list of excluded sport-confidence segments based on profitability analysis.

    Returns:
        List of (sport, confidence) tuples to exclude
    """
    # EXCLUDED SEGMENTS: Based on performance analysis (Last 90 days as of 2026-02-28)
    # These sport+confidence combinations have been most unprofitable:
    # - ALL LOW CONFIDENCE: -28.6% ROI average
    # - NHL MEDIUM: -54.45% ROI (47 bets)
    # - TENNIS HIGH: -27.2% ROI (70 bets)
    # - TENNIS MEDIUM: -8.5% ROI (91 bets)
    # - WNCAAB HIGH/MEDIUM: Unreliable performance
    return [
        # Exclude all LOW confidence bets due to -28.6% ROI
        ("NBA", "LOW"),
        ("NHL", "LOW"),
        ("MLB", "LOW"),
        ("NFL", "LOW"),
        ("NCAAB", "LOW"),
        ("WNCAAB", "LOW"),
        ("TENNIS", "LOW"),
        ("EPL", "LOW"),
        ("LIGUE1", "LOW"),
        # Exclude specific unprofitable segments
        ("NHL", "MEDIUM"),  # -54.45% ROI
        ("TENNIS", "HIGH"),  # -27.2% ROI
        ("TENNIS", "MEDIUM"),  # -8.5% ROI
        ("WNCAAB", "HIGH"),  # -100% ROI
        ("WNCAAB", "MEDIUM"),  # -11.3% ROI
        ("NCAAB", "HIGH"),  # -1.3% ROI (recent analysis shows high unprofitability)
        (
            "NCAAB",
            "MEDIUM",
        ),  # -1.3% ROI (barely positive historically, currently negative)
    ]


def _initialize_portfolio_manager(
    kalshi_client: Any,
) -> Any:
    """Initialize portfolio manager with configuration.

    Args:
        kalshi_client: Initialized Kalshi client

    Returns:
        Initialized PortfolioBettingManager
    """
    from portfolio_betting import PortfolioBettingManager
    from portfolio_optimizer import PortfolioConfig

    excluded_segments = _get_excluded_segments()
    balance, _ = kalshi_client.get_balance()

    config = PortfolioConfig(
        bankroll=balance,
        max_daily_risk_pct=MAX_DAILY_RISK_PCT,  # 25% max daily risk
        kelly_fraction=KELLY_FRACTION,  # Conservative Kelly for more volume
        min_bet_size=2.0,
        max_bet_size=MAX_BET_SIZE,  # Lower max to spread across more bets
        max_single_bet_pct=MAX_SINGLE_BET_PCT,  # Lower single bet limit for more diversification
        min_edge=MIN_EDGE_THRESHOLD,  # Minimum positive edge for value betting
        min_confidence=MIN_CONFIDENCE_THRESHOLD,
        excluded_segments=excluded_segments,
    )

    return PortfolioBettingManager(
        kalshi_client=kalshi_client,
        config=config,
        dry_run=False,  # LIVE BETTING
    )


def _send_betting_summary_sms(date_str: str, results: dict) -> None:
    """Send SMS notification with betting results summary.

    Args:
        date_str: Date string for the betting day
        results: Dictionary with betting results
    """
    try:
        placed_count = len(results["placed_bets"])
        total_amount = sum(b.get("amount", 0) for b in results["placed_bets"])

        # Create SMS message (keep it short - SMS has 160 char limit)
        sms_body = f"BETS PLACED {date_str}\n"
        sms_body += f"{placed_count} bets, ${total_amount:.2f} total\n\n"

        # List top bets
        for i, bet in enumerate(results["placed_bets"][:TOP_BETS_COUNT_SMS], 1):
            player = bet.get("player", bet.get("home_team", "Unknown"))[
                :MAX_PLAYER_NAME_LEN_SMS
            ]
            amount = bet.get("amount", 0)
            sms_body += f"{i}. {player} ${amount:.0f}\n"

        if placed_count > TOP_BETS_COUNT_SMS:
            sms_body += f"...+{placed_count - TOP_BETS_COUNT_SMS} more"

        if send_sms(
            to_number="7244959219",
            subject=f"Bets: {placed_count} placed, ${total_amount:.0f}",
            body=sms_body,
        ):
            print("✓ SMS notification sent")
        else:
            print("⚠️  SMS notification failed")
    except Exception as e:
        print(f"⚠️  Failed to send SMS: {e}")


SEPARATOR_WIDTH = 80


def place_portfolio_optimized_bets(**context: Any) -> None:
    """
    Place portfolio-optimized bets across all sports using Kelly Criterion.

    This replaces the old sport-by-sport betting with a unified portfolio approach.
    """
    print(f"\n{'=' * SEPARATOR_WIDTH}")
    print("🎰 PORTFOLIO-OPTIMIZED BETTING")
    print(f"{'=' * SEPARATOR_WIDTH}\n")

    try:
        # Initialize Kalshi client from runtime environment secrets
        kalshi_client = _initialize_kalshi_client()

        # Initialize portfolio manager
        manager = _initialize_portfolio_manager(kalshi_client)

        # Process daily bets
        date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
        results = manager.process_daily_bets(
            date_str,
            sports=[
                "nhl",
                "nba",
                "mlb",
                "nfl",
                "ncaab",
                "wncaab",
                "tennis",
                "epl",
                "ligue1",
            ],
        )

        print("\n✓ Portfolio betting complete")
        print(f"  Planned: {results['planned_bets']}")
        print(f"  Placed: {len(results['placed_bets'])}")
        print(f"  Skipped: {len(results['skipped_bets'])}")
        print(f"  Errors: {len(results['errors'])}")

        # Send SMS notification with summary
        _send_betting_summary_sms(date_str, results)

        return results

    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}")
        return
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise


def _initialize_kalshi_client_for_summary() -> Optional[Any]:
    """Initialize Kalshi client with credentials for daily summary.

    Returns:
        KalshiBetting client if credentials are valid, None otherwise
    """
    try:
        from kalshi_betting import KalshiBetting, KalshiConfig

        config = KalshiConfig.from_env(production=True)
        client = KalshiBetting(config=config)
        return client
    except ValueError as e:
        print(f"⚠️  Missing Kalshi credentials - cannot fetch balance: {e}")
        return None
    except ImportError as e:
        print(f"❌ Failed to import KalshiBetting: {e}")
        return None
    except Exception as e:
        print(f"❌ Failed to initialize Kalshi client: {e}")
        return None


def _get_kalshi_runtime_secret_error() -> Optional[str]:
    """Return a runtime Kalshi secret error message, if one exists."""
    from kalshi_betting import load_runtime_kalshi_env

    try:
        _api_key_id, private_key_path = load_runtime_kalshi_env(env=os.environ)
    except ValueError as exc:
        return str(exc)

    if not Path(private_key_path).is_file():
        return f"Kalshi private key is not available at {private_key_path}"

    return None


def _fetch_current_balance(client: Any) -> Tuple[float, float]:
    """Fetch current balance and portfolio value from Kalshi.

    Args:
        client: Initialized KalshiBetting client

    Returns:
        Tuple of (balance, portfolio_value)
    """
    try:
        return client.get_balance()
    except Exception as e:
        print(f"❌ Failed to fetch balance: {e}")
        return 0.0, 0.0


def _calculate_yesterday_winnings(
    portfolio_value: float,
) -> Tuple[float, Optional[float]]:
    """Calculate yesterday's winnings by comparing with saved data.

    Args:
        portfolio_value: Current portfolio value

    Returns:
        Tuple of (winnings, yesterday_portfolio_value)
    """
    from datetime import datetime, timedelta
    from pathlib import Path
    import json

    yesterday = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    yesterday_file = Path(f"data/portfolio/balance_{yesterday_str}.json")
    yesterday_portfolio = None

    if yesterday_file.exists():
        with open(yesterday_file) as f:
            data = json.load(f)
            yesterday_portfolio = data.get("portfolio_value", portfolio_value)

    if yesterday_portfolio:
        winnings = portfolio_value - yesterday_portfolio
    else:
        winnings = 0.0
        print("⚠️  No yesterday data - cannot calculate winnings")

    return winnings, yesterday_portfolio


def _save_todays_balance(balance_summary: DailyBalanceSummary) -> None:
    """Save today's balance to JSON file.

    Args:
        balance_summary: Daily balance summary containing date, cash balance, and portfolio value
    """

    balance_file = balance_dir / f"balance_{balance_summary.date_str}.json"
    with open(balance_file, "w") as f:
        json.dump(
            {
                "date": balance_summary.date_str,
                "balance": balance_summary.cash_balance,
                "portfolio_value": balance_summary.portfolio_value,
                "timestamp": datetime.now().isoformat(),
            },
            f,
            indent=2,
        )


def _load_todays_placed_bets(today_str: str) -> Tuple[List[Dict], float]:
    """Load and aggregate today's placed bets from all sports.

    Args:
        today_str: Date string in YYYY-MM-DD format

    Returns:
        Tuple of (list of placed bets, total bet amount)
    """
    from pathlib import Path
    import json

    placed_bets = []
    for sport in ALL_SPORTS:
        result_file = Path(f"data/{sport}/betting_results_{today_str}.json")
        if result_file.exists():
            with open(result_file) as f:
                results = json.load(f)
                placed_bets.extend(results.get("placed", []))

    total_bet = sum(bet.get("amount", 0) for bet in placed_bets)
    return placed_bets, total_bet


def _print_daily_summary(
    balance_summary: DailyBalanceSummary,
    winnings: float,
    placed_bets: List[Dict],
    total_bet: float,
) -> None:
    """Print daily summary to console."""
    print(f"\n💰 Balance: ${balance_summary.cash_balance:.2f}")
    print(f"📊 Portfolio Value: ${balance_summary.portfolio_value:.2f}")
    print(f"{'📈' if winnings >= 0 else '📉'} Yesterday's P/L: ${winnings:+.2f}")
    print(f"🎲 Bets Placed Today: {len(placed_bets)} (${total_bet:.2f})")


def send_daily_summary(**context: Any) -> None:
    """Send daily summary SMS with balance, yesterday's winnings, and today's bets."""
    from datetime import datetime

    print("\n📧 Preparing daily summary SMS...")
    today_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))

    try:
        # 1. Initialize and Fetch Data
        client = _initialize_kalshi_client_for_summary()
        if client is None:
            print("❌ Cannot send daily summary - Kalshi client initialization failed")
            return

        balance, portfolio_value = _fetch_current_balance(client)
        winnings, _ = _calculate_yesterday_winnings(portfolio_value)
        balance_summary = DailyBalanceSummary(today_str, balance, portfolio_value)

        # 2. Persist and Load Local Data
        _save_todays_balance(balance_summary)
        placed_bets, total_bet = _load_todays_placed_bets(today_str)

        # 3. Report and Notify
        _print_daily_summary(balance_summary, winnings, placed_bets, total_bet)
        messages = _create_sms_messages(
            balance_summary, winnings, placed_bets, total_bet
        )

        if _send_sms_messages(messages):
            print("✅ Daily summary sent successfully!")
        else:
            print("⚠️  Daily summary partially sent with errors")

    except Exception as e:
        print(f"❌ Failed to send daily summary: {e}")
        import traceback

        traceback.print_exc()


def update_clv_wrapper(**context: Any) -> Any:
    """Wrapper to import and call update_clv_for_closed_markets."""
    from update_clv_data import update_clv_for_closed_markets

    return update_clv_for_closed_markets()


# Create DAG
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(DAG_START_YEAR, 1, 1),
    "email": ["7244959219@vtext.com"],  # Verizon SMS gateway
    "email_on_failure": False,  # Disabled due to SMTP authentication issues
    "email_on_retry": False,
    "retries": DAG_RETRY_COUNT,
    "retry_delay": timedelta(minutes=DAG_RETRY_DELAY_MINS),
}

dag = DAG(
    "multi_sport_betting_workflow",
    default_args=default_args,
    description="Multi-sport betting opportunities using Elo ratings",
    schedule="0 5 * * *",  # Run daily at 5 AM Eastern (using America/New_York timezone)
    catchup=False,
    tags=["betting", "elo", "multi-sport"],
)

# Create tasks for each sport
for sport in ALL_SPORTS:
    download_task = PythonOperator(
        task_id=f"{sport}_download_games",
        python_callable=download_games,
        op_kwargs={"sport": sport},
        dag=dag,
    )

    load_task = PythonOperator(
        task_id=f"{sport}_load_db",
        python_callable=load_data_to_db,
        op_kwargs={"sport": sport},
        dag=dag,
    )

    elo_task = PythonOperator(
        task_id=f"{sport}_update_elo",
        python_callable=update_elo_ratings,
        op_kwargs={"sport": sport},
        dag=dag,
    )

    # Add Glicko-2 task for supported sports
    if sport in GLICKO2_SPORTS:
        glicko2_task = PythonOperator(
            task_id=f"{sport}_update_glicko2",
            python_callable=update_glicko2_ratings,
            op_kwargs={"sport": sport},
            dag=dag,
        )

    markets_task = PythonOperator(
        task_id=f"{sport}_fetch_markets",
        python_callable=fetch_prediction_markets,
        op_kwargs={"sport": sport},
        dag=dag,
    )

    bets_task = PythonOperator(
        task_id=f"{sport}_identify_bets",
        python_callable=identify_good_bets,
        op_kwargs={"sport": sport},
        dag=dag,
    )

    model_scoring_task = None
    mlb_external_odds_task = None
    tennis_training_task = None
    if sport == "mlb":
        mlb_external_odds_task = PythonOperator(
            task_id="mlb_fetch_external_odds",
            python_callable=fetch_mlb_current_odds,
            dag=dag,
        )
        model_scoring_task = PythonOperator(
            task_id="mlb_score_model_predictions",
            python_callable=score_mlb_model_predictions,
            dag=dag,
        )
        markets_task >> mlb_external_odds_task >> model_scoring_task >> bets_task
    elif sport == "tennis":
        tennis_training_task = PythonOperator(
            task_id="tennis_train_probability_model",
            python_callable=train_tennis_probability_model,
            dag=dag,
        )
        markets_task >> tennis_training_task >> bets_task
    else:
        markets_task >> bets_task

    load_bets_task = PythonOperator(
        task_id=f"{sport}_load_bets_db",
        python_callable=load_bets_to_db,
        op_kwargs={"sport": sport},
        dag=dag,
    )

    # Place bets task (for NBA, NHL, NCAAB, WNCAAB, TENNIS, and LIGUE1)
    if sport in SINGLE_BETTING_SPORTS:
        place_bets_task = PythonOperator(
            task_id=f"{sport}_place_bets",
            python_callable=place_bets_on_recommendations,
            op_kwargs={"sport": sport},
            dag=dag,
        )

    # Set task dependencies
    if sport in GLICKO2_SPORTS:
        # With Glicko-2
        (
            download_task
            >> load_task
            >> [elo_task, glicko2_task]
            >> markets_task
            >> bets_task
        )
        if sport in SINGLE_BETTING_SPORTS:
            # Place bets, then load to DB
            bets_task >> place_bets_task >> load_bets_task
        else:
            bets_task >> load_bets_task
    else:
        # Without Glicko-2
        download_task >> load_task >> elo_task >> markets_task >> bets_task
        if sport in SINGLE_BETTING_SPORTS:
            bets_task >> place_bets_task >> load_bets_task
        else:
            bets_task >> load_bets_task

# Add unified portfolio betting task (runs after all sports have identified bets)
portfolio_betting_task = PythonOperator(
    task_id="portfolio_optimized_betting",
    python_callable=place_portfolio_optimized_bets,
    dag=dag,
)

# Portfolio betting depends on all bets being identified and loaded to DB
# Get all the load_bets_task for each sport
all_load_bets_tasks = [
    dag.get_task(f"{sport}_load_bets_db")
    for sport in [
        "nba",
        "nhl",
        "mlb",
        "nfl",
        "epl",
        "tennis",
        "ncaab",
        "wncaab",
        "ligue1",
        "unrivaled",
        "cba",
    ]
]

# Portfolio betting runs after all bets are loaded to DB
all_load_bets_tasks >> portfolio_betting_task

# Add CLV update task (runs after portfolio betting to update CLV data for closed markets)
clv_update_task = PythonOperator(
    task_id="update_clv_data",
    python_callable=update_clv_wrapper,
    dag=dag,
)

# CLV update runs after portfolio betting
portfolio_betting_task >> clv_update_task


# Add reconcile_placed_bets task – runs after CLV update, before daily summary
def _run_reconcile_placed_bets(**_kwargs: Any) -> dict:
    """Airflow callable: reconcile local placed_bets against Kalshi state.

    Uses a 15-minute cutoff window to avoid racing with the hourly
    ``bet_sync_hourly`` DAG, which can run simultaneously at the top of each
    hour.  Bets whose ``created_at`` is within the last 15 minutes are left
    for the next reconciliation cycle.
    """
    secret_error = _get_kalshi_runtime_secret_error()
    if secret_error:
        print(f"⚠️  Skipping reconcile_placed_bets: {secret_error}")
        return {"status": "skipped", "reason": secret_error}

    from bet_reconciliation import reconcile_all

    return reconcile_all(cutoff_minutes=15)


reconcile_bets_task = PythonOperator(
    task_id="reconcile_placed_bets",
    python_callable=_run_reconcile_placed_bets,
    retries=2,
    dag=dag,
)

# Reconcile runs after CLV update
clv_update_task >> reconcile_bets_task

# Add daily summary task (runs at the end)
daily_summary_task = PythonOperator(
    task_id="send_daily_summary",
    python_callable=send_daily_summary,
    dag=dag,
)

# Daily summary runs after reconciliation
reconcile_bets_task >> daily_summary_task
