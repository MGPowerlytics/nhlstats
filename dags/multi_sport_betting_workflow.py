"""
Multi-Sport Betting Workflow DAG
Unified workflow for NBA, NHL, MLB, and NFL betting opportunities using Elo ratings.
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys
import json
import smtplib
import os
import time
import math
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add plugins directory to Python path
plugins_dir = Path(__file__).parent.parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))


def is_valid_score(score):
    """Check if a score is a valid number (not None, NaN, or inf)."""
    if score is None:
        return False
    try:
        if math.isnan(score) or math.isinf(score):
            return False
    except (TypeError, ValueError):
        return False
    return True


# Import Elo factory


# SMTP alerting disabled - set to True to re-enable
SMTP_ALERTING_ENABLED = False


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


def serialize_datetime(obj):
    """Convert datetime objects to ISO format strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


__all__ = [
    "download_games",
    "load_data_to_db",
    "update_elo_ratings",
    "fetch_prediction_markets",
    "update_glicko2_ratings",
    "load_bets_to_db",
    "identify_good_bets",
    "place_bets_on_recommendations",
    "place_portfolio_optimized_bets",
    "send_daily_summary",
    "update_clv_wrapper",
]

# Sport configurations
# Thresholds optimized based on lift/gain analysis (see docs/VALUE_BETTING_THRESHOLDS.md)
# NBA: 73% threshold captures top 20% of predictions with 1.39x lift
# NHL: 66% threshold (lowered from 77% which was too conservative)
# MLB: 67% threshold for consistent lift in high deciles
# NFL: 70% threshold for strong discrimination
# All thresholds validated on 55K+ historical games
SPORTS_CONFIG = {
    "nba": {
        "elo_module": "elo",
        "games_module": "nba_games",
        "kalshi_function": "fetch_nba_markets",
        "elo_threshold": 0.78,  # Optimized from 0.73 - focus on decile 9+ (69.2%+ win rate, lift 1.31+)
        "market_confidence_cutoff": 0.52,  # Lower cutoff for predictable NBA markets
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
        "kalshi_function": "fetch_nhl_markets",
        "elo_threshold": 0.70,  # Optimized from 0.66 - focus on decile 10 (71.8% win rate, lift 1.32+)
        "market_confidence_cutoff": 0.58,  # Higher cutoff for high-variance NHL
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
        "kalshi_function": "fetch_mlb_markets",
        "elo_threshold": 0.72,  # Optimized from 0.67 - focus on decile 10 (65.3% win rate, lift 1.23+)
        "market_confidence_cutoff": 0.58,  # Higher cutoff for high-variance MLB
        "series_ticker": "KXMLBGAME",
        "team_mapping": {},  # Will be populated from database
    },
    "nfl": {
        "elo_module": "elo",
        "games_module": "nfl_games",
        "kalshi_function": "fetch_nfl_markets",
        "elo_threshold": 0.75,  # Optimized from 0.70 - focus on decile 9+ (71.8%+ win rate, lift 1.32+)
        "market_confidence_cutoff": 0.55,  # Medium cutoff for NFL
        "series_ticker": "KXNFLGAME",
        "team_mapping": {},  # Will be populated from database
    },
    "epl": {
        "elo_module": "elo",
        "games_module": "epl_games",
        "kalshi_function": "fetch_epl_markets",
        "elo_threshold": 0.45,  # Threshold for 3-way markets
        "market_confidence_cutoff": 0.55,  # Standard cutoff for soccer
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
        "kalshi_function": "fetch_tennis_markets",
        "elo_threshold": 0.60,
        "market_confidence_cutoff": 0.55,  # Standard cutoff for tennis
        "series_ticker": "TENNIS",  # Placeholder
        "team_mapping": {},
    },
    "ncaab": {
        "elo_module": "elo",
        "games_module": "ncaab_games",
        "kalshi_function": "fetch_ncaab_markets",
        "elo_threshold": 0.78,  # Optimized from 0.72 - aligns with updated NBA pattern (focus on highest deciles)
        "market_confidence_cutoff": 0.58,  # Higher cutoff for college sports (higher variance)
        "series_ticker": "KXNCAAMBGAME",
        "team_mapping": {},
    },
    "ligue1": {
        "elo_module": "elo",
        "games_module": "ligue1_games",
        "kalshi_function": "fetch_ligue1_markets",
        "elo_threshold": 0.45,  # Threshold for 3-way markets
        "market_confidence_cutoff": 0.55,  # Standard cutoff for soccer
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
        "kalshi_function": "fetch_wncaab_markets",
        "elo_threshold": 0.78,  # Optimized from 0.72 - aligns with updated basketball pattern (focus on highest deciles)
        "market_confidence_cutoff": 0.58,  # Higher cutoff for college sports (higher variance)
        "series_ticker": "KXNCAAWBGAME",
        "team_mapping": {},
    },
    "unrivaled": {
        "elo_module": "elo",
        "games_module": "unrivaled_games",
        "kalshi_function": "fetch_unrivaled_markets",
        "elo_threshold": 0.70,  # Similar to other basketball leagues
        "market_confidence_cutoff": 0.58,  # Higher cutoff for experimental league
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
        "kalshi_function": "fetch_cba_markets",
        "elo_threshold": 0.70,  # Similar to other basketball leagues
        "market_confidence_cutoff": 0.58,  # Higher cutoff for international league
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


def download_games(sport, **context):
    """Download latest games for a sport."""
    print(f"📥 Downloading {sport.upper()} games...")

    # Get date from context
    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))

    # Calculate yesterday to ensure we capture final scores from previous day
    current_date = datetime.strptime(date_str, "%Y-%m-%d")
    yesterday_str = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
    dates_to_process = [yesterday_str, date_str]

    # Import the appropriate class
    if sport == "nba":
        from nba_games import NBAGames

        for d in dates_to_process:
            try:
                games = NBAGames(date_folder=d)
                games.download_games_for_date(d)
                print(f"✓ Successfully downloaded NBA games for {d}")
            except Exception as e:
                print(f"⚠️  Failed to download NBA games for {d}: {e}")
                print("⚠️  Continuing with other sports...")
                # Don't raise the exception - let other sports continue
                # We'll skip NBA for this run
    elif sport == "nhl":
        from nhl_game_events import NHLGameEvents

        for d in dates_to_process:
            games = NHLGameEvents(date_folder=d)
            games.download_games_for_date(d)
    elif sport == "mlb":
        from mlb_games import MLBGames

        for d in dates_to_process:
            games = MLBGames(date_folder=d)
            games.download_games_for_date(d)
    elif sport == "nfl":
        from nfl_games import NFLGames

        for d in dates_to_process:
            games = NFLGames(date_folder=d)
            games.download_games_for_date(d)
    elif sport == "epl":
        from epl_games import EPLGames

        games = EPLGames()
        games.download_games()
    elif sport == "ligue1":
        from ligue1_games import Ligue1Games

        games = Ligue1Games()
        games.download_games()
    elif sport == "tennis":
        from tennis_games import TennisGames

        games = TennisGames()
        games.download_games()
    elif sport == "ncaab":
        from ncaab_games import NCAABGames

        games = NCAABGames()
        games.download_games()
    elif sport == "wncaab":
        from wncaab_games import WNCAABGames

        games = WNCAABGames()
        games.download_games()
    elif sport == "unrivaled":
        from unrivaled_games import UnrivaledGames

        games = UnrivaledGames()
        games.download_games()
    elif sport == "cba":
        from cba_games import CBAGames

        games = CBAGames()
        games.download_games()

    print(f"✓ {sport.upper()} games downloaded")


def load_data_to_db(sport, **context):
    """Load downloaded games into PostgreSQL."""
    print(f"💾 Loading {sport.upper()} games into database...")

    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))

    # Calculate yesterday to ensure we update final scores
    current_date = datetime.strptime(date_str, "%Y-%m-%d")
    yesterday_str = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
    dates_to_process = [yesterday_str, date_str]

    from db_loader import NHLDatabaseLoader

    with NHLDatabaseLoader() as loader:
        if sport == "tennis":
            # Tennis needs full history reload to capture new matches
            loader.load_tennis_history(target_date=date_str)
            count = "all"
        else:
            count = 0
            for d in dates_to_process:
                count += loader.load_date(d)

    print(f"✓ Loaded {count} new games/updates for {dates_to_process}")


def update_elo_ratings(sport, **context):
    """Calculate current Elo ratings for a sport with logging."""
    print(f"📊 Updating {sport.upper()} Elo ratings...")

    # Load previous ratings for comparison (if available)
    previous_ratings = {}
    csv_path = f"data/{sport}_current_elo_ratings.csv"
    if os.path.exists(csv_path):
        try:
            import pandas as pd

            df = pd.read_csv(csv_path)
            previous_ratings = dict(zip(df["team"], df["rating"]))
            print(f"  Loaded {len(previous_ratings)} previous ratings from {csv_path}")
        except Exception as e:
            print(f"  ⚠️  Could not load previous ratings: {e}")

    SPORTS_CONFIG[sport]

    # Import sport-specific modules
    if sport == "nba":
        from elo import get_elo_class
        from db_manager import default_db

        # FIXED: Use unified_games instead of nba_games for complete historical data
        # NBA team name to abbreviation mapping
        nba_team_mapping = {
            "Atlanta Hawks": "ATL",
            "Boston Celtics": "BOS",
            "Brooklyn Nets": "BKN",
            "Charlotte Hornets": "CHA",
            "Chicago Bulls": "CHI",
            "Cleveland Cavaliers": "CLE",
            "Dallas Mavericks": "DAL",
            "Denver Nuggets": "DEN",
            "Detroit Pistons": "DET",
            "Golden State Warriors": "GSW",
            "Houston Rockets": "HOU",
            "Indiana Pacers": "IND",
            "Los Angeles Clippers": "LAC",
            "Los Angeles Lakers": "LAL",
            "Memphis Grizzlies": "MEM",
            "Miami Heat": "MIA",
            "Milwaukee Bucks": "MIL",
            "Minnesota Timberwolves": "MIN",
            "New Orleans Pelicans": "NOP",
            "New York Knicks": "NYK",
            "Oklahoma City Thunder": "OKC",
            "Orlando Magic": "ORL",
            "Philadelphia 76ers": "PHI",
            "Phoenix Suns": "PHX",
            "Portland Trail Blazers": "POR",
            "Sacramento Kings": "SAC",
            "San Antonio Spurs": "SAS",
            "Toronto Raptors": "TOR",
            "Utah Jazz": "UTA",
            "Washington Wizards": "WAS",
            "LA Clippers": "LAC",
            "LA Lakers": "LAL",
        }

        def map_nba_team(team_name):
            """Map NBA team name to abbreviation."""
            if team_name and len(team_name) <= 4:
                return team_name  # Already an abbreviation
            return nba_team_mapping.get(team_name, team_name)

        query = """
            SELECT game_date, home_team_name as home_team, away_team_name as away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM unified_games
            WHERE sport = 'NBA'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
            ORDER BY game_date
        """
        games_df = default_db.fetch_df(query)
        print(
            f"  Loaded {len(games_df)} NBA games from unified_games (complete historical data)"
        )

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=100)

        last_date = None
        games_processed = 0
        for _, game in games_df.iterrows():
            # Map team names
            home_full = game["home_team"]
            away_full = game["away_team"]
            home_team = map_nba_team(home_full)
            away_team = map_nba_team(away_full)

            # Season detection
            game_date = game["game_date"]
            if isinstance(game_date, str):
                current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
            else:
                current_date = game_date

            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 120:  # NBA offseason
                    print(f"📅 New NBA season detected at {current_date}")
                    # Check if NBA Elo class has season reversion method
                    if hasattr(elo, "apply_season_reversion"):
                        elo.apply_season_reversion(0.4)
                    else:
                        print(f"  ⚠️  NBA Elo class doesn't support season reversion")

            last_date = current_date
            elo.update(home_team, away_team, game["home_win"])

            games_processed += 1
            if games_processed % 1000 == 0:
                print(f"    Processed {games_processed} games...")

        print(f"  ✅ Processed {games_processed} total games")
    elif sport == "nhl":
        from elo import get_elo_class
        from db_manager import default_db

        # FIXED: Use unified_games instead of games table for complete historical data
        # Team name to abbreviation mapping
        # Whitelist of valid NHL abbreviations to prevent cross-sport contamination
        valid_nhl_teams = {
            "ANA",
            "ARI",
            "BOS",
            "BUF",
            "CGY",
            "CAR",
            "CHI",
            "COL",
            "CBJ",
            "DAL",
            "DET",
            "EDM",
            "FLA",
            "LAK",
            "MIN",
            "MTL",
            "NSH",
            "NJD",
            "NYI",
            "NYR",
            "OTT",
            "PHI",
            "PIT",
            "SJS",
            "SEA",
            "STL",
            "TBL",
            "TOR",
            "UTA",
            "VAN",
            "VGK",
            "WSH",
            "WPG",
        }

        # Known cross-sport contaminants to explicitly block
        contaminants = {
            "Celtics",
            "Bills",
            "Eagles",
            "Cowboys",
            "Lions",
            "Lakers",
            "Thunder",
        }

        nhl_team_mapping = {
            "Anaheim Ducks": "ANA",
            "Arizona Coyotes": "ARI",
            "Boston Bruins": "BOS",
            "Buffalo Sabres": "BUF",
            "Calgary Flames": "CGY",
            "Carolina Hurricanes": "CAR",
            "Chicago Blackhawks": "CHI",
            "Colorado Avalanche": "COL",
            "Columbus Blue Jackets": "CBJ",
            "Dallas Stars": "DAL",
            "Detroit Red Wings": "DET",
            "Edmonton Oilers": "EDM",
            "Florida Panthers": "FLA",
            "Los Angeles Kings": "LAK",
            "Minnesota Wild": "MIN",
            "Montreal Canadiens": "MTL",
            "Montréal Canadiens": "MTL",
            "Nashville Predators": "NSH",
            "New Jersey Devils": "NJD",
            "New York Islanders": "NYI",
            "New York Rangers": "NYR",
            "Ottawa Senators": "OTT",
            "Philadelphia Flyers": "PHI",
            "Pittsburgh Penguins": "PIT",
            "San Jose Sharks": "SJS",
            "Seattle Kraken": "SEA",
            "St. Louis Blues": "STL",
            "Tampa Bay Lightning": "TBL",
            "Toronto Maple Leafs": "TOR",
            "Utah Hockey Club": "UTA",
            "Utah Mammoth": "UTA",
            "Vancouver Canucks": "VAN",
            "Vegas Golden Knights": "VGK",
            "Washington Capitals": "WSH",
            "Winnipeg Jets": "WPG",
            "Utah": "UTA",
        }

        def map_nhl_team(team_name):
            """Map NHL team name to abbreviation."""
            if not team_name:
                return None
            if len(team_name) <= 4 and team_name.upper() in valid_nhl_teams:
                return team_name.upper()

            mapped = nhl_team_mapping.get(team_name)
            if mapped:
                return mapped

            # If not in mapping and is a known contaminant, block it
            if team_name in contaminants:
                return None

            return team_name  # Fallback for unknown but non-blocked names

        query = """
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
              AND home_team_name NOT IN ('Bills', 'Celtics', 'Eagles', 'Cowboys', 'Lions')
              AND away_team_name NOT IN ('Bills', 'Celtics', 'Eagles', 'Cowboys', 'Lions')
            ORDER BY game_date
        """

        games_df = default_db.fetch_df(query)
        print(f"  Loaded {len(games_df)} NHL games from unified_games")

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=10, home_advantage=50, recency_weight=0.2)

        last_date = None
        games_processed = 0
        for _, game in games_df.iterrows():
            # Map team names to abbreviations
            home_team = map_nhl_team(game["home_team_name"])
            away_team = map_nhl_team(game["away_team_name"])

            # Skip if either team is not a valid NHL team
            if not home_team or not away_team:
                continue

    elif sport == "mlb":
        from elo import get_elo_class
        from db_manager import default_db

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=50)
        # FIXED: Use unified_games instead of mlb_games
        query = """
            SELECT game_date, home_team_name as home_team, away_team_name as away_team,
                   home_score, away_score
            FROM unified_games
            WHERE sport = 'MLB'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
            ORDER BY game_date
        """
        df = default_db.fetch_df(query)
        if df.empty:
            print("No MLB games found in database")
            return

        print(f"  Loaded {len(df)} MLB games from unified_games")

        games_processed = 0
        for _, row in df.iterrows():
            home_team = row["home_team"]
            away_team = row["away_team"]
            home_score = row["home_score"]
            away_score = row["away_score"]
            # Check for valid scores (not None, NaN, or inf)
            if not is_valid_score(home_score) or not is_valid_score(away_score):
                continue
            home_won = home_score > away_score
            elo.update(
                home_team,
                away_team,
                home_won,
                home_score=home_score,
                away_score=away_score,
            )

            games_processed += 1
            if games_processed % 1000 == 0:
                print(f"    Processed {games_processed} games...")

        print(f"  ✅ Processed {games_processed} total games")
    elif sport == "nfl":
        from elo import get_elo_class
        from db_manager import default_db

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=65)
        # FIXED: Use unified_games instead of nfl_games
        query = """
            SELECT game_date, home_team_name as home_team, away_team_name as away_team,
                   home_score, away_score
            FROM unified_games
            WHERE sport = 'NFL'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
            ORDER BY game_date
        """
        df = default_db.fetch_df(query)
        if df.empty:
            print("No NFL games found in database")
            return

        print(f"  Loaded {len(df)} NFL games from unified_games")

        games_processed = 0
        for _, row in df.iterrows():
            home_team = row["home_team"]
            away_team = row["away_team"]
            home_score = row["home_score"]
            away_score = row["away_score"]
            # Check for valid scores (not None, NaN, or inf)
            if not is_valid_score(home_score) or not is_valid_score(away_score):
                continue
            home_won = home_score > away_score
            elo.update(
                home_team,
                away_team,
                home_won,
                home_score=home_score,
                away_score=away_score,
            )

            games_processed += 1
            if games_processed % 500 == 0:
                print(f"    Processed {games_processed} games...")

        print(f"  ✅ Processed {games_processed} total games")
    elif sport == "epl":
        from elo import get_elo_class
        from db_manager import default_db

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=60)
        # Query epl_games table
        query = """
            SELECT game_date, home_team, away_team, result
            FROM epl_games
            WHERE game_date IS NOT NULL
            ORDER BY game_date
        """
        df = default_db.fetch_df(query)
        if df.empty:
            print("No EPL games found in database")
            return

        for _, row in df.iterrows():
            elo.legacy_update(row["home_team"], row["away_team"], row["result"])
    elif sport == "ligue1":
        from elo import get_elo_class
        import csv

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=60)
        # Load pre-generated ratings from CSV
        with open("data/ligue1_current_elo_ratings.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                elo.ratings[row["team"]] = float(row["rating"])
        print(f"✓ Loaded {len(elo.ratings)} Ligue 1 teams")
    elif sport == "ncaab":
        from elo import get_elo_class
        from ncaab_games import NCAABGames

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=100)
        games_obj = NCAABGames()
        # Ensure data exists essentially
        df = games_obj.load_games()

        if df.empty:
            print("⚠️ No NCAAB games loaded")
            return

        df = df.sort_values("date")
        for _, game in df.iterrows():
            home_won = 1.0 if game["home_score"] > game["away_score"] else 0.0
            # load_games returns neutral flag
            elo.update(
                game["home_team"],
                game["away_team"],
                home_won,
                is_neutral=game["neutral"],
            )

        # Save ratings to CSV and push to XCom (same logic as common team sports branch)
        Path(f"data/{sport}_current_elo_ratings.csv").parent.mkdir(
            parents=True, exist_ok=True
        )
        # Filter out NaN values before saving
        valid_ratings = {
            team: rating
            for team, rating in elo.ratings.items()
            if is_valid_score(rating)
        }

        # LOGGING: Compare with previous ratings
        if previous_ratings:
            print(f"\n📊 {sport.upper()} Elo Rating Changes:")
            print("=" * 50)

            common_teams = set(valid_ratings.keys()) & set(previous_ratings.keys())
            new_teams = set(valid_ratings.keys()) - set(previous_ratings.keys())
            removed_teams = set(previous_ratings.keys()) - set(valid_ratings.keys())

            print(
                f"  Teams: {len(valid_ratings)} total ({len(common_teams)} updated, {len(new_teams)} new, {len(removed_teams)} removed)"
            )

            if common_teams:
                changes = []
                for team in common_teams:
                    old = previous_ratings[team]
                    new = valid_ratings[team]
                    change = new - old
                    changes.append((team, old, new, change))

                # Sort by absolute change
                changes.sort(key=lambda x: abs(x[3]), reverse=True)

                if changes:
                    avg_change = sum(c[3] for c in changes) / len(changes)
                    max_increase = max(c[3] for c in changes)
                    max_decrease = min(c[3] for c in changes)

                    print(f"  Average change: {avg_change:+.2f}")
                    print(f"  Maximum increase: {max_increase:+.2f}")
                    print(f"  Maximum decrease: {max_decrease:+.2f}")

                    print(f"\n  Top 3 increases:")
                    count = 0
                    for team, old, new, change in changes:
                        if change > 0 and count < 3:
                            print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")
                            count += 1

                    print(f"\n  Top 3 decreases:")
                    count = 0
                    for team, old, new, change in changes:
                        if change < 0 and count < 3:
                            print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")
                            count += 1

        with open(f"data/{sport}_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\n")
            for team in sorted(valid_ratings.keys()):
                f.write(f"{team},{valid_ratings[team]:.2f}\n")

        # Push to XCom
        context["task_instance"].xcom_push(
            key=f"{sport}_elo_ratings", value=valid_ratings
        )
        print(f"✓ {sport.upper()} Elo ratings updated: {len(valid_ratings)} teams")
        return

    elif sport == "wncaab":
        from elo import get_elo_class
        from wncaab_games import WNCAABGames

        EloClass = get_elo_class(sport)
        elo = EloClass(k_factor=20, home_advantage=100)
        games_obj = WNCAABGames()
        df = games_obj.load_games()

        if df.empty:
            print("⚠️ No WNCAAB games loaded")
            return

        df = df.sort_values("date")
        for _, game in df.iterrows():
            home_won = 1.0 if game["home_score"] > game["away_score"] else 0.0
            elo.update(
                game["home_team"],
                game["away_team"],
                home_won,
                is_neutral=game.get("neutral", False),
            )

    elif sport == "unrivaled":
        from elo import get_elo_class
        from unrivaled_games import UnrivaledGames

        EloClass = get_elo_class(sport)
        # Unrivaled: No home advantage (all games at same venue), higher K-factor for 3x3
        elo = EloClass(k_factor=24, home_advantage=0)
        games_obj = UnrivaledGames()
        df = games_obj.load_games()

        if df.empty:
            print("⚠️ No Unrivaled games loaded")
            return

        df = df.sort_values("date")
        for _, game in df.iterrows():
            home_won = 1.0 if game["home_score"] > game["away_score"] else 0.0
            # All Unrivaled games are neutral site
            elo.update(
                game["home_team"],
                game["away_team"],
                home_won,
                is_neutral=True,
            )

    elif sport == "tennis":
        # Tennis: load full history to capture new matches.
        from elo import get_elo_class
        from tennis_games import TennisGames

        EloClass = get_elo_class(sport)
        tg = TennisGames()
        df = tg.load_games()
        if df.empty:
            print("⚠️  No Tennis matches available")
            return

        df = df.sort_values("date")

        elo = EloClass(k_factor=32)
        for _, row in df.iterrows():
            try:
                elo.update(str(row["winner"]), str(row["loser"]), tour=str(row["tour"]))
            except Exception:
                continue

    elif sport == "cba":
        from elo import get_elo_class
        from cba_games import CBAGames

        EloClass = get_elo_class(sport)
        # CBA: Strong home advantage in China
        elo = EloClass(k_factor=20, home_advantage=80)
        games_obj = CBAGames()
        df = games_obj.get_completed_games()

        if df.empty:
            print("⚠️ No CBA games loaded")
            return

        df = df.sort_values("date")
        for _, game in df.iterrows():
            home_won = 1.0 if game["home_score"] > game["away_score"] else 0.0
            elo.update(
                game["home_team"],
                game["away_team"],
                home_won,
                is_neutral=game.get("neutral", False),
            )

    # Save ratings to CSV
    if sport == "tennis":
        Path("data").mkdir(parents=True, exist_ok=True)
        with open("data/atp_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\n")
            for player in sorted(elo.atp_ratings.keys()):
                f.write(f"{player},{elo.atp_ratings[player]:.2f}\n")

        with open("data/wta_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\n")
            for player in sorted(elo.wta_ratings.keys()):
                f.write(f"{player},{elo.wta_ratings[player]:.2f}\n")
    elif sport in [
        "nba",
        "nhl",
        "mlb",
        "nfl",
        "epl",
        "ligue1",
        "ncaab",
        "wncaab",
        "unrivaled",
        "cba",
    ]:
        Path(f"data/{sport}_current_elo_ratings.csv").parent.mkdir(
            parents=True, exist_ok=True
        )
        # Filter out NaN values before saving
        valid_ratings = {
            team: rating
            for team, rating in elo.ratings.items()
            if is_valid_score(rating)
        }

        # LOGGING: Compare with previous ratings
        if previous_ratings:
            print(f"\n📊 {sport.upper()} Elo Rating Changes:")
            print("=" * 50)

            common_teams = set(valid_ratings.keys()) & set(previous_ratings.keys())
            new_teams = set(valid_ratings.keys()) - set(previous_ratings.keys())
            removed_teams = set(previous_ratings.keys()) - set(valid_ratings.keys())

            print(
                f"  Teams: {len(valid_ratings)} total ({len(common_teams)} updated, {len(new_teams)} new, {len(removed_teams)} removed)"
            )

            if common_teams:
                changes = []
                for team in common_teams:
                    old = previous_ratings[team]
                    new = valid_ratings[team]
                    change = new - old
                    changes.append((team, old, new, change))

                # Sort by absolute change
                changes.sort(key=lambda x: abs(x[3]), reverse=True)

                if changes:
                    avg_change = sum(c[3] for c in changes) / len(changes)
                    max_increase = max(c[3] for c in changes)
                    max_decrease = min(c[3] for c in changes)

                    print(f"  Average change: {avg_change:+.2f}")
                    print(f"  Maximum increase: {max_increase:+.2f}")
                    print(f"  Maximum decrease: {max_decrease:+.2f}")

                    print(f"\n  Top 3 increases:")
                    count = 0
                    for team, old, new, change in changes:
                        if change > 0 and count < 3:
                            print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")
                            count += 1

                    print(f"\n  Top 3 decreases:")
                    count = 0
                    for team, old, new, change in changes:
                        if change < 0 and count < 3:
                            print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")
                            count += 1

        with open(f"data/{sport}_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\n")
            for team in sorted(valid_ratings.keys()):
                f.write(f"{team},{valid_ratings[team]:.2f}\n")

    # Push to XCom (filter NaN values to prevent JSON serialization errors)
    if sport == "tennis":
        context["task_instance"].xcom_push(
            key=f"{sport}_elo_ratings",
            value={"ATP": dict(elo.atp_ratings), "WTA": dict(elo.wta_ratings)},
        )
        total_players = len(elo.atp_ratings) + len(elo.wta_ratings)
        print(
            f"✓ {sport.upper()} Elo ratings updated: {total_players} players (ATP: {len(elo.atp_ratings)}, WTA: {len(elo.wta_ratings)})"
        )
    else:
        # Filter out any NaN or invalid values before XCom push
        valid_ratings = {
            team: rating
            for team, rating in elo.ratings.items()
            if is_valid_score(rating)
        }
        context["task_instance"].xcom_push(
            key=f"{sport}_elo_ratings", value=valid_ratings
        )
        print(f"✓ {sport.upper()} Elo ratings updated: {len(valid_ratings)} teams")


def fetch_prediction_markets(sport, **context):
    """Fetch prediction markets for a sport."""
    print(f"💰 Fetching {sport.upper()} prediction markets...")

    from kalshi_markets import (
        fetch_nba_markets,
        fetch_nhl_markets,
        fetch_mlb_markets,
        fetch_nfl_markets,
        fetch_epl_markets,
        fetch_tennis_markets,
        fetch_ncaab_markets,
        fetch_ligue1_markets,
        fetch_wncaab_markets,
        fetch_unrivaled_markets,
        fetch_cba_markets,
    )

    SPORTS_CONFIG[sport]
    fetch_function = {
        "nba": fetch_nba_markets,
        "nhl": fetch_nhl_markets,
        "mlb": fetch_mlb_markets,
        "nfl": fetch_nfl_markets,
        "epl": fetch_epl_markets,
        "tennis": fetch_tennis_markets,
        "ncaab": fetch_ncaab_markets,
        "ligue1": fetch_ligue1_markets,
        "wncaab": fetch_wncaab_markets,
        "unrivaled": fetch_unrivaled_markets,
        "cba": fetch_cba_markets,
    }[sport]

    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
    markets = fetch_function(date_str)

    if not markets:
        print(f"ℹ️  No {sport.upper()} markets available")
        return

    # Helper for JSON serialization
    def json_serial(obj):
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


def update_glicko2_ratings(sport, **context):
    """Calculate current Glicko-2 ratings for a sport."""
    print(f"📊 Updating {sport.upper()} Glicko-2 ratings...")

    from glicko2_rating import (
        NBAGlicko2Rating,
        NHLGlicko2Rating,
        MLBGlicko2Rating,
        NFLGlicko2Rating,
    )
    from db_manager import default_db

    glicko_classes = {
        "nba": NBAGlicko2Rating,
        "nhl": NHLGlicko2Rating,
        "mlb": MLBGlicko2Rating,
        "nfl": NFLGlicko2Rating,
    }

    if sport not in glicko_classes:
        print(f"⚠️  Glicko-2 not implemented for {sport}")
        return

    glicko = glicko_classes[sport]()

    if sport == "nba":
        # Query NBA games from database (same pattern as update_elo_ratings)
        query = """
            SELECT game_date, home_team, away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM nba_games
            WHERE status = 'Final'
            ORDER BY game_date, game_id
        """
        games_df = default_db.fetch_df(query)
        print(f"  Loaded {len(games_df)} NBA games for Glicko-2")
        for _, game in games_df.iterrows():
            glicko.update(game["home_team"], game["away_team"], game["home_win"])
    elif sport == "nhl":
        query = """
            SELECT game_date, home_team_abbrev as home_team, away_team_abbrev as away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM games WHERE game_state IN ('OFF', 'FINAL', 'Final') ORDER BY game_date, game_id
        """
        games_df = default_db.fetch_df(query)
        for _, game in games_df.iterrows():
            glicko.update(game["home_team"], game["away_team"], game["home_win"])
    elif sport in ["mlb", "nfl"]:
        table_name = f"{sport}_games"
        query = f"""
            SELECT game_date, home_team, away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM {table_name}
            WHERE game_date IS NOT NULL
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
            ORDER BY game_date
        """
        games_df = default_db.fetch_df(query)
        for _, game in games_df.iterrows():
            glicko.update(game["home_team"], game["away_team"], game["home_win"])

    # Save ratings to CSV
    Path(f"data/{sport}_current_glicko2_ratings.csv").parent.mkdir(
        parents=True, exist_ok=True
    )
    with open(f"data/{sport}_current_glicko2_ratings.csv", "w") as f:
        f.write("team,rating,rd,volatility\n")
        for team in sorted(glicko.ratings.keys()):
            r = glicko.ratings[team]
            f.write(f"{team},{r['rating']:.2f},{r['rd']:.2f},{r['vol']:.6f}\n")

    # Push to XCom
    context["task_instance"].xcom_push(
        key=f"{sport}_glicko2_ratings", value=glicko.ratings
    )

    print(f"✓ {sport.upper()} Glicko-2 ratings updated: {len(glicko.ratings)} teams")


def load_bets_to_db(sport, **context):
    """Load bet recommendations into database."""
    print(f"💾 Loading {sport.upper()} bets into database...")

    from bet_loader import BetLoader

    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
    loader = BetLoader()
    count = loader.load_bets_for_date(sport, date_str)

    print(f"✓ Loaded {count} {sport.upper()} bets into database")


def identify_good_bets(sport, **context):
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

    config = SPORTS_CONFIG[sport]
    elo_threshold = config["elo_threshold"]

    # Import Elo module to get predict function
    elo_module = __import__(config["elo_module"])
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

    from naming_resolver import NamingResolver

    # NCAAB specific name mapping for Elo lookup
    if sport == "ncaab":
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
            NamingResolver.add_mapping("ncaab", "kalshi", raw, canon)
            NamingResolver.add_mapping("ncaab", "elo", canon, canon)

    # Initialize OddsComparator
    from odds_comparator import OddsComparator

    comparator = OddsComparator()

    # Find opportunities
    market_confidence_cutoff = config.get("market_confidence_cutoff", 0.55)

    # Enable high-edge disagreement for sports where Elo has shown strong predictive power
    # NBA: Predictable league, Elo model should be strong
    # Tennis: Individual sport, Elo should be accurate
    # Other sports: Higher variance, be more conservative
    enable_high_edge_disagreement = sport in ["nba", "tennis"]
    high_edge_threshold = 0.12  # 12% edge required for disagreement bets

    good_bets = comparator.find_opportunities(
        sport=sport,
        elo_ratings=(
            elo_ratings if sport != "tennis" else {}
        ),  # Tennis handles ratings internally in predict
        elo_system=elo_system,
        threshold=elo_threshold,
        min_edge=0.05,
        use_sharp_confirmation=(sport in ["tennis", "nhl", "ligue1"]),
        market_confidence_cutoff=market_confidence_cutoff,
        enable_high_edge_disagreement=enable_high_edge_disagreement,
        high_edge_threshold=high_edge_threshold,
    )

    # Deduplicate by ticker
    seen_tickers = set()
    unique_bets = []
    for bet in good_bets:
        ticker = bet.get("ticker")
        if ticker and ticker not in seen_tickers:
            unique_bets.append(bet)
            seen_tickers.add(ticker)
        elif not ticker:
            unique_bets.append(bet)

    good_bets = unique_bets

    # Save results
    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
    bets_file = Path(f"data/{sport}/bets_{date_str}.json")
    bets_file.parent.mkdir(parents=True, exist_ok=True)

    # Serialize for JSON
    def json_serial(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    with open(bets_file, "w") as f:
        json.dump(good_bets, f, indent=2, default=json_serial)

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


def place_bets_on_recommendations(sport, **context):
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


def place_portfolio_optimized_bets(**context):
    """
    Place portfolio-optimized bets across all sports using Kelly Criterion.

    This replaces the old sport-by-sport betting with a unified portfolio approach.
    """
    from pathlib import Path

    print(f"\n{'=' * 80}")
    print("🎰 PORTFOLIO-OPTIMIZED BETTING")
    print(f"{'=' * 80}\n")

    # Import portfolio betting modules
    try:
        from portfolio_betting import PortfolioBettingManager
        from kalshi_betting import KalshiBetting
    except ImportError:
        print("❌ Portfolio betting modules not found")
        return

    # Load Kalshi credentials
    kalshkey_file = Path("/opt/airflow/kalshkey")
    if not kalshkey_file.exists():
        kalshkey_file = Path("kalshkey")

    if not kalshkey_file.exists():
        print("❌ Kalshi credentials not found")
        return

    content = kalshkey_file.read_text(encoding="utf-8")

    # Extract API key ID
    api_key_id = None
    for line in content.splitlines():
        if "API key id:" in line:
            api_key_id = line.split(":", 1)[1].strip()
            break

    if not api_key_id:
        print("❌ Could not find API key ID")
        return

    # Extract private key
    private_key_lines = []
    in_key = False
    for line in content.splitlines():
        if "-----BEGIN RSA PRIVATE KEY-----" in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if "-----END RSA PRIVATE KEY-----" in line:
            break

    # Save private key to temp file
    temp_key_file = Path("/tmp/kalshi_private_key.pem")
    temp_key_file.write_text("\n".join(private_key_lines), encoding="utf-8")

    try:
        # Initialize Kalshi client
        kalshi_client = KalshiBetting(
            api_key_id=api_key_id, private_key_path=str(temp_key_file)
        )

        # Initialize portfolio manager
        # EXCLUDED SEGMENTS: Based on backtest analysis (2026-01-28 to 2026-02-01)
        # These sport+confidence combinations have been unprofitable:
        # Based on analysis of bets since Feb 9, 2026:
        # - TENNIS LOW: 40% win rate, -54.09% ROI (15 bets, -$62.45 loss) - NEW
        # - WNCAAB LOW: 57% win rate, -22.77% ROI (7 bets, -$7.96 loss) - NEW
        # - NCAAB MEDIUM: 43% win rate, -22.32% ROI (14 bets, -$16.95 loss) - NEW
        # - WNCAAB HIGH: 0% win rate, -100.00% ROI (3 bets, -$2.06 loss) - KEEP
        # - NBA LOW: 20% win rate, -68.31% ROI (5 bets, -$10.78 loss) - KEEP
        # - TENNIS HIGH: 44% win rate, -45.97% ROI (9 bets, -$12.76 loss) - KEEP
        # - TENNIS MEDIUM: 61% win rate, -15.68% ROI (18 bets, -$7.44 loss) - KEEP
        # See: betting_analysis_since_20260209.md for full analysis
        excluded_segments = [
            ("TENNIS", "LOW"),  # Catastrophic: 40% win rate, -54% ROI
            ("WNCAAB", "LOW"),  # Poor: 57% win rate, -23% ROI
            ("NCAAB", "MEDIUM"),  # Poor: 43% win rate, -22% ROI
            ("WNCAAB", "HIGH"),  # Catastrophic: 0% win rate, -100% ROI
            ("NBA", "LOW"),  # Very poor: 20% win rate, -68% ROI
            ("TENNIS", "HIGH"),  # Poor: 44% win rate, -46% ROI
            ("TENNIS", "MEDIUM"),  # Unprofitable: 61% win rate but -16% ROI
        ]

        manager = PortfolioBettingManager(
            kalshi_client=kalshi_client,
            max_daily_risk_pct=0.25,  # 25% max daily risk
            kelly_fraction=0.20,  # Conservative Kelly for more volume
            min_bet_size=2.0,
            max_bet_size=10.0,  # Lower max to spread across more bets
            max_single_bet_pct=0.03,  # Lower single bet limit for more diversification
            min_edge=-1.0,  # Allow negative edge for Market Agreement strategy
            min_confidence=0.65,
            excluded_segments=excluded_segments,
            dry_run=False,  # LIVE BETTING
        )

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
        try:
            placed_count = len(results["placed_bets"])
            total_amount = sum(b.get("amount", 0) for b in results["placed_bets"])

            # Create SMS message (keep it short - SMS has 160 char limit)
            sms_body = f"BETS PLACED {date_str}\n"
            sms_body += f"{placed_count} bets, ${total_amount:.2f} total\n\n"

            # List top 5 bets
            for i, bet in enumerate(results["placed_bets"][:5], 1):
                player = bet.get("player", bet.get("home_team", "Unknown"))[:15]
                amount = bet.get("amount", 0)
                sms_body += f"{i}. {player} ${amount:.0f}\n"

            if placed_count > 5:
                sms_body += f"...+{placed_count - 5} more"

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

        return results

    finally:
        # Clean up temp key file
        if temp_key_file.exists():
            temp_key_file.unlink()
    # Only bet on selected sports


def send_daily_summary(**context):
    """Send daily summary SMS with balance, yesterday's winnings, and today's bets."""
    import os
    from pathlib import Path
    from datetime import datetime, timedelta

    print("\n📧 Preparing daily summary SMS...")

    # Initialize Kalshi client
    api_key_id = os.getenv("KALSHI_API_KEY")
    private_key_path = Path("/opt/airflow/kalshi_private_key.pem")

    if not api_key_id or not private_key_path.exists():
        print("⚠️  Missing Kalshi credentials - cannot fetch balance")
        return

    try:
        from kalshi_betting import KalshiBetting

        client = KalshiBetting(
            api_key_id=api_key_id,
            private_key_path=str(private_key_path),
            production=True,
        )

        # Get current balance and portfolio value
        balance, portfolio_value = client.get_balance()

        # Get yesterday's portfolio value to calculate winnings
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")

        # Try to get yesterday's balance from saved data
        yesterday_file = Path(f"data/portfolio/balance_{yesterday_str}.json")
        yesterday_portfolio = None
        if yesterday_file.exists():
            with open(yesterday_file) as f:
                data = json.load(f)
                yesterday_portfolio = data.get("portfolio_value", portfolio_value)

        # Calculate winnings
        if yesterday_portfolio:
            winnings = portfolio_value - yesterday_portfolio
        else:
            winnings = 0
            print("⚠️  No yesterday data - cannot calculate winnings")

        # Save today's balance
        today_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
        balance_dir = Path("data/portfolio")
        balance_dir.mkdir(parents=True, exist_ok=True)

        balance_file = balance_dir / f"balance_{today_str}.json"
        with open(balance_file, "w") as f:
            json.dump(
                {
                    "date": today_str,
                    "balance": balance,
                    "portfolio_value": portfolio_value,
                    "timestamp": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

        # Get today's placed bets
        placed_bets = []
        for sport in ["nba", "nhl", "ncaab", "tennis", "ligue1", "unrivaled", "cba"]:
            result_file = Path(f"data/{sport}/betting_results_{today_str}.json")
            if result_file.exists():
                with open(result_file) as f:
                    results = json.load(f)
                    placed_bets.extend(results.get("placed", []))

        # Calculate total bet amount
        total_bet = sum(bet.get("amount", 0) for bet in placed_bets)

        print(f"\n💰 Balance: ${balance:.2f}")
        print(f"📊 Portfolio Value: ${portfolio_value:.2f}")
        print(f"{'📈' if winnings >= 0 else '📉'} Yesterday's P/L: ${winnings:+.2f}")
        print(f"🎲 Bets Placed Today: {len(placed_bets)} (${total_bet:.2f})")

        # Send summary in multiple SMS messages (160 char limit per message)

        # Message 1: Summary stats
        msg1 = f"DAILY SUMMARY {today_str}\n"
        msg1 += f"Balance: ${balance:.2f}\n"
        msg1 += f"Portfolio: ${portfolio_value:.2f}\n"
        msg1 += f"Yesterday P/L: ${winnings:+.2f}"

        if send_sms("7244959219", "Daily Summary (1/3)", msg1):
            print("✓ Sent message 1/3")

        time.sleep(2)  # Brief delay between messages

        # Message 2: Bet summary
        msg2 = f"BETS TODAY: {len(placed_bets)} placed\n"
        msg2 += f"Total bet: ${total_bet:.2f}\n"

        if placed_bets:
            msg2 += "\nTop bets:\n"
            for i, bet in enumerate(placed_bets[:3], 1):
                team = bet.get("player", bet.get("home_team", "Unknown"))[:12]
                amt = bet.get("amount", 0)
                msg2 += f"{i}. {team} ${amt:.0f}\n"
        else:
            msg2 += "No bets placed today"

        if send_sms("7244959219", "Daily Summary (2/3)", msg2):
            print("✓ Sent message 2/3")

        time.sleep(2)

        # Message 3: Additional bets if more than 3
        if len(placed_bets) > 3:
            msg3 = "More bets:\n"
            for i, bet in enumerate(placed_bets[3:8], 4):  # Show bets 4-8
                team = bet.get("player", bet.get("home_team", "Unknown"))[:12]
                amt = bet.get("amount", 0)
                msg3 += f"{i}. {team} ${amt:.0f}\n"

            if len(placed_bets) > 8:
                msg3 += f"\n+{len(placed_bets) - 8} more bets"

            if send_sms("7244959219", "Daily Summary (3/3)", msg3):
                print("✓ Sent message 3/3")
        else:
            # Message 3: Available balance for tomorrow
            msg3 = "AVAILABLE TOMORROW\n"
            msg3 += f"Cash: ${balance:.2f}\n"
            msg3 += f"Total value: ${portfolio_value:.2f}\n"
            msg3 += f"\n{'💰 Win!' if winnings > 0 else '📉 Loss' if winnings < 0 else '➖ Flat'}"

            if send_sms("7244959219", "Daily Summary (3/3)", msg3):
                print("✓ Sent message 3/3")

        print("✅ Daily summary sent successfully!")

    except Exception as e:
        print(f"❌ Failed to send daily summary: {e}")
        import traceback

        traceback.print_exc()


def update_clv_wrapper(**context):
    """Wrapper to import and call update_clv_for_closed_markets."""
    from update_clv_data import update_clv_for_closed_markets

    return update_clv_for_closed_markets()


# Create DAG
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email": ["7244959219@vtext.com"],  # Verizon SMS gateway
    "email_on_failure": False,  # Disabled due to SMTP authentication issues
    "email_on_retry": False,
    "retries": 2,  # Increased from 1 to 2 for more resilience
    "retry_delay": timedelta(minutes=10),  # Increased delay between retries
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
]:
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
    if sport in ["nba", "nhl", "mlb", "nfl"]:
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

    load_bets_task = PythonOperator(
        task_id=f"{sport}_load_bets_db",
        python_callable=load_bets_to_db,
        op_kwargs={"sport": sport},
        dag=dag,
    )

    # Place bets task (for NBA, NHL, NCAAB, WNCAAB, TENNIS, and LIGUE1)
    if sport in ["nba", "nhl", "ncaab", "wncaab", "tennis", "ligue1"]:
        place_bets_task = PythonOperator(
            task_id=f"{sport}_place_bets",
            python_callable=place_bets_on_recommendations,
            op_kwargs={"sport": sport},
            dag=dag,
        )

    # Set task dependencies
    if sport in ["nba", "nhl", "mlb", "nfl"]:
        # With Glicko-2
        (
            download_task
            >> load_task
            >> [elo_task, glicko2_task]
            >> markets_task
            >> bets_task
        )
        if sport in ["nba", "nhl", "ncaab"]:
            # Place bets, then load to DB
            bets_task >> place_bets_task >> load_bets_task
        else:
            bets_task >> load_bets_task
    else:
        # Without Glicko-2
        download_task >> load_task >> elo_task >> markets_task >> bets_task
        if sport in ["ncaab", "wncaab", "tennis", "ligue1"]:
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

# Add daily summary task (runs at the end)
daily_summary_task = PythonOperator(
    task_id="send_daily_summary",
    python_callable=send_daily_summary,
    dag=dag,
)

# Daily summary runs after CLV update
clv_update_task >> daily_summary_task
