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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add plugins directory to Python path
plugins_dir = Path(__file__).parent.parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))


def send_sms(to_number: str, subject: str, body: str) -> bool:
    """Send SMS via Verizon email gateway using Gmail SMTP.

    Args:
        to_number: Phone number (without formatting)
        subject: SMS subject line
        body: SMS message body

    Returns:
        True if sent successfully, False otherwise
    """
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

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Sport configurations
# Thresholds optimized based on lift/gain analysis (see docs/VALUE_BETTING_THRESHOLDS.md)
# NBA: 73% threshold captures top 20% of predictions with 1.39x lift
# NHL: 66% threshold (lowered from 77% which was too conservative)
# MLB: 67% threshold for consistent lift in high deciles
# NFL: 70% threshold for strong discrimination
# All thresholds validated on 55K+ historical games
SPORTS_CONFIG = {
    "nba": {
        "elo_module": "nba_elo_rating",
        "games_module": "nba_games",
        "kalshi_function": "fetch_nba_markets",
        "elo_threshold": 0.73,  # Optimized from 0.64 - focuses on highest lift deciles (1.39x lift)
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
        "elo_module": "nhl_elo_rating",
        "games_module": "nhl_game_events",
        "kalshi_function": "fetch_nhl_markets",
        "elo_threshold": 0.66,  # Optimized from 0.77 - was too conservative (1.28x lift at 66%)
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
        "elo_module": "mlb_elo_rating",
        "games_module": "mlb_games",
        "kalshi_function": "fetch_mlb_markets",
        "elo_threshold": 0.67,  # Optimized from 0.62 - captures top deciles with 1.18x lift
        "series_ticker": "KXMLBGAME",
        "team_mapping": {},  # Will be populated from database
    },
    "nfl": {
        "elo_module": "nfl_elo_rating",
        "games_module": "nfl_games",
        "kalshi_function": "fetch_nfl_markets",
        "elo_threshold": 0.70,  # Optimized from 0.68 - strong 1.34x lift in top deciles
        "series_ticker": "KXNFLGAME",
        "team_mapping": {},  # Will be populated from database
    },
    "epl": {
        "elo_module": "epl_elo_rating",
        "games_module": "epl_games",
        "kalshi_function": "fetch_epl_markets",
        "elo_threshold": 0.45,  # Threshold for 3-way markets
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
        "elo_module": "tennis_elo_rating",
        "games_module": "tennis_games",
        "kalshi_function": "fetch_tennis_markets",
        "elo_threshold": 0.60,
        "series_ticker": "TENNIS",  # Placeholder
        "team_mapping": {},
    },
    "ncaab": {
        "elo_module": "ncaab_elo_rating",
        "games_module": "ncaab_games",
        "kalshi_function": "fetch_ncaab_markets",
        "elo_threshold": 0.72,  # Optimized from 0.65 - aligns with NBA pattern
        "series_ticker": "KXNCAAMBGAME",
        "team_mapping": {},
    },
    "ligue1": {
        "elo_module": "ligue1_elo_rating",
        "games_module": "ligue1_games",
        "kalshi_function": "fetch_ligue1_markets",
        "elo_threshold": 0.45,  # Threshold for 3-way markets
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
            "MON": "Montpellier",
            "FCM": "Montpellier",
            "STB": "Brest",
        },
    },
    "wncaab": {
        "elo_module": "wncaab_elo_rating",
        "games_module": "wncaab_games",
        "kalshi_function": "fetch_wncaab_markets",
        "elo_threshold": 0.72,  # Optimized from 0.65 - aligns with other basketball
        "series_ticker": "KXNCAAWBGAME",
        "team_mapping": {},
    },
}


def download_games(sport, **context):
    """Download latest games for a sport."""
    print(f"📥 Downloading {sport.upper()} games...")

    # Get date from context
    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))

    # Import the appropriate class
    if sport == "nba":
        from nba_games import NBAGames

        games = NBAGames(date_folder=date_str)
        games.download_games_for_date(date_str)
    elif sport == "nhl":
        from nhl_game_events import NHLGameEvents

        games = NHLGameEvents(date_folder=date_str)
        games.download_games_for_date(date_str)
    elif sport == "mlb":
        from mlb_games import MLBGames

        games = MLBGames(date_folder=date_str)
        games.download_games_for_date(date_str)
    elif sport == "nfl":
        from nfl_games import NFLGames

        games = NFLGames(date_folder=date_str)
        games.download_games_for_date(date_str)
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

    print(f"✓ {sport.upper()} games downloaded")


def load_data_to_db(sport, **context):
    """Load downloaded games into PostgreSQL."""
    print(f"💾 Loading {sport.upper()} games into database...")

    date_str = context.get("ds", datetime.now().strftime("%Y-%m-%d"))
    from db_loader import NHLDatabaseLoader

    with NHLDatabaseLoader() as loader:
        if sport == "tennis":
            # Tennis needs full history reload to capture new matches
            loader.load_tennis_history(target_date=date_str)
            count = "all"
        else:
            count = loader.load_date(date_str)

    print(f"✓ Loaded {count} new games/updates for {date_str}")


def update_elo_ratings(sport, **context):
    """Calculate current Elo ratings for a sport."""
    print(f"📊 Updating {sport.upper()} Elo ratings...")

    config = SPORTS_CONFIG[sport]

    # Import sport-specific modules
    if sport == "nba":
        from nba_elo_rating import NBAEloRating, load_nba_games_from_json
        import pandas as pd

        games_df = load_nba_games_from_json()
        elo = NBAEloRating(k_factor=20, home_advantage=100)
        for _, game in games_df.iterrows():
            elo.update(game["home_team"], game["away_team"], game["home_win"])
    elif sport == "nhl":
        from nhl_elo_rating import NHLEloRating
        from db_manager import default_db

        # Filter out:
        # 1. Exhibition games (non-NHL teams)
        # 2. Duplicates (keep first occurrence per matchup+date)
        exhibition_teams = (
            "CAN", "USA", "ATL", "MET", "CEN", "PAC", "SWE", "FIN", "EIS", "MUN",
            "SCB", "KLS", "KNG", "MKN", "HGS", "MAT", "MCD",
        )

        query = """
            WITH ranked_games AS (
                SELECT game_date, home_team_abbrev, away_team_abbrev,
                       CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win,
                       ROW_NUMBER() OVER (
                           PARTITION BY game_date, home_team_abbrev, away_team_abbrev
                           ORDER BY game_id
                       ) as rn
                FROM games
                WHERE game_state IN ('OFF', 'FINAL', 'Final')
                  AND home_team_abbrev NOT IN :ex_teams
                  AND away_team_abbrev NOT IN :ex_teams
            )
            SELECT game_date, home_team_abbrev as home_team,
                   away_team_abbrev as away_team, home_win
            FROM ranked_games
            WHERE rn = 1
            ORDER BY game_date, home_team
        """

        games_df = default_db.fetch_df(query, {'ex_teams': exhibition_teams})
        print(f"  Loaded {len(games_df)} NHL games from PostgreSQL (filtered duplicates and exhibitions)")

        elo = NHLEloRating(k_factor=10, home_advantage=50, recency_weight=0.2)

        last_date = None
        for _, game in games_df.iterrows():
            game_date = game['game_date']
            if isinstance(game_date, str):
                current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
            else:
                current_date = game_date

            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 90:
                    print(f"📅 New NHL season detected at {current_date}")
                    elo.apply_season_reversion(0.45)

            last_date = current_date
            elo.update(game['home_team'], game['away_team'], game['home_win'], game_date=current_date)
    elif sport == "mlb":
        from mlb_elo_rating import calculate_current_elo_ratings

        elo = calculate_current_elo_ratings(
            output_path=f"data/{sport}_current_elo_ratings.csv"
        )
        if not elo:
            print(f"⚠️  No MLB games available yet")
            return
    elif sport == "nfl":
        from nfl_elo_rating import calculate_current_elo_ratings

        elo = calculate_current_elo_ratings(
            output_path=f"data/{sport}_current_elo_ratings.csv"
        )
        if not elo:
            print(f"⚠️  No NFL games available yet")
            return
    elif sport == "epl":
        from epl_elo_rating import calculate_current_elo_ratings

        elo = calculate_current_elo_ratings()
        if not elo:
            print(f"⚠️  No EPL games available yet")
            return
    elif sport == "ligue1":
        from ligue1_elo_rating import Ligue1EloRating
        import csv

        # Load pre-generated ratings
        elo = Ligue1EloRating(k_factor=20, home_advantage=60)
        with open(f"data/ligue1_current_elo_ratings.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                elo.ratings[row["team"]] = float(row["rating"])
        print(f"✓ Loaded {len(elo.ratings)} Ligue 1 teams")
    elif sport == "ncaab":
        from ncaab_elo_rating import NCAABEloRating
        from ncaab_games import NCAABGames

        elo = NCAABEloRating(k_factor=20, home_advantage=100)
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

    elif sport == "wncaab":
        from wncaab_elo_rating import WNCAABEloRating
        from wncaab_games import WNCAABGames

        elo = WNCAABEloRating(k_factor=20, home_advantage=100)
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

    elif sport == "tennis":
        # Tennis: load full history to capture new matches.
        from tennis_elo_rating import TennisEloRating
        from tennis_games import TennisGames

        tg = TennisGames()
        df = tg.load_games()
        if df.empty:
            print("⚠️  No Tennis matches available")
            return

        df = df.sort_values("date")

        elo = TennisEloRating(k_factor=32)
        for _, row in df.iterrows():
            try:
                elo.update(str(row["winner"]), str(row["loser"]), tour=str(row["tour"]))
            except Exception:
                continue

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
    elif sport in ["nba", "nhl", "epl", "ncaab", "wncaab"]:
        Path(f"data/{sport}_current_elo_ratings.csv").parent.mkdir(
            parents=True, exist_ok=True
        )
        with open(f"data/{sport}_current_elo_ratings.csv", "w") as f:
            f.write("team,rating\n")
            for team in sorted(elo.ratings.keys()):
                f.write(f"{team},{elo.ratings[team]:.2f}\n")

    # Push to XCom
    if sport == "tennis":
        context["task_instance"].xcom_push(
            key=f"{sport}_elo_ratings",
            value={"ATP": dict(elo.atp_ratings), "WTA": dict(elo.wta_ratings)},
        )
        total_players = len(elo.atp_ratings) + len(elo.wta_ratings)
        print(f"✓ {sport.upper()} Elo ratings updated: {total_players} players (ATP: {len(elo.atp_ratings)}, WTA: {len(elo.wta_ratings)})")
    else:
        context["task_instance"].xcom_push(
            key=f"{sport}_elo_ratings", value=elo.ratings
        )
        print(f"✓ {sport.upper()} Elo ratings updated: {len(elo.ratings)} teams")


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
    )

    config = SPORTS_CONFIG[sport]
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
    }[sport]

    date_str = context["ds"]
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
        from nba_elo_rating import load_nba_games_from_json
        games_df = load_nba_games_from_json()
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
            glicko.update(game['home_team'], game['away_team'], game['home_win'])
    elif sport in ["mlb", "nfl"]:
        table_name = f"{sport}_games"
        query = f"""
            SELECT game_date, home_team, away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM {table_name} WHERE game_date IS NOT NULL
            ORDER BY game_date
        """
        games_df = default_db.fetch_df(query)
        for _, game in games_df.iterrows():
            glicko.update(game['home_team'], game['away_team'], game['home_win'])

    # Save ratings to CSV
    Path(f"data/{sport}_current_glicko2_ratings.csv").parent.mkdir(
        parents=True, exist_ok=True
    )
    with open(f"data/{sport}_current_glicko2_ratings.csv", "w") as f:
        f.write("team,rating,rd,volatility\n")
        for team in sorted(glicko.ratings.keys()):
            r = glicko.ratings[team]
            f.write(f'{team},{r["rating"]:.2f},{r["rd"]:.2f},{r["vol"]:.6f}\n')

    # Push to XCom
    context["task_instance"].xcom_push(
        key=f"{sport}_glicko2_ratings", value=glicko.ratings
    )

    print(f"✓ {sport.upper()} Glicko-2 ratings updated: {len(glicko.ratings)} teams")


def load_bets_to_db(sport, **context):
    """Load bet recommendations into database."""
    print(f"💾 Loading {sport.upper()} bets into database...")

    from bet_loader import BetLoader

    date_str = context["ds"]
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

    # Initialize OddsComparator
    from odds_comparator import OddsComparator
    comparator = OddsComparator()

    # Find opportunities
    good_bets = comparator.find_opportunities(
        sport=sport,
        elo_ratings=elo_ratings if sport != 'tennis' else {}, # Tennis handles ratings internally in predict
        elo_system=elo_system,
        threshold=elo_threshold,
        min_edge=0.05,
        use_sharp_confirmation=(sport in ['tennis', 'nhl', 'ligue1']) # Enable for tennis, NHL and Ligue 1
    )

    # Save results
    date_str = context["ds"]
    bets_file = Path(f"data/{sport}/bets_{date_str}.json")
    bets_file.parent.mkdir(parents=True, exist_ok=True)

    # Serialize for JSON
    def json_serial(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    with open(bets_file, "w") as f:
        json.dump(good_bets, f, indent=2, default=json_serial)

    print(f"✓ Found {len(good_bets)} {sport.upper()} betting opportunities")

    if good_bets:
        print(f"\n{sport.upper()} Betting Opportunities:")
        for bet in good_bets:
            print(f"  {bet['away_team']} @ {bet['home_team']}")
            print(
                f"    Bet: {bet['bet_on']} ({bet['bookmaker']}) | Edge: {bet['edge']:.1%} | Elo: {bet['elo_prob']:.1%} | Odds: {bet['market_odds']:.2f}"
            )

    # Save results
    date_str = context["ds"]
    bets_file = Path(f"data/{sport}/bets_{date_str}.json")
    bets_file.parent.mkdir(parents=True, exist_ok=True)
    with open(bets_file, "w") as f:
        json.dump(good_bets, f, indent=2)

    print(f"✓ Found {len(good_bets)} {sport.upper()} betting opportunities")

    if good_bets:
        print(f"\n{sport.upper()} Betting Opportunities:")
        for bet in good_bets:
            if sport == "tennis":
                print(f"  {bet.get('matchup', 'Unknown')}")
                print(
                    f"    Bet: {bet['bet_on']} | Edge: {bet['edge']:.1%} | Confidence: {bet['confidence']}"
                )
            else:
                print(f"  {bet['away_team']} @ {bet['home_team']}")
                print(
                    f"    Bet: {bet['bet_on']} | Edge: {bet['edge']:.1%} | Confidence: {bet['confidence']}"
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
    print(f"⚠️  This task is kept for backwards compatibility only")
    return


def place_portfolio_optimized_bets(**context):
    """
    Place portfolio-optimized bets across all sports using Kelly Criterion.

    This replaces the old sport-by-sport betting with a unified portfolio approach.
    """
    from pathlib import Path

    print(f"\n{'='*80}")
    print(f"🎰 PORTFOLIO-OPTIMIZED BETTING")
    print(f"{'='*80}\n")

    # Import portfolio betting modules
    try:
        from portfolio_betting import PortfolioBettingManager
        from kalshi_betting import KalshiBetting
        from update_clv_data import update_clv_for_closed_markets
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

    content = kalshkey_file.read_text()

    # Extract API key ID
    api_key_id = None
    for line in content.split("\n"):
        if "API key id:" in line:
            api_key_id = line.split(":", 1)[1].strip()
            break

    if not api_key_id:
        print("❌ Could not find API key ID")
        return

    # Extract private key
    private_key_lines = []
    in_key = False
    for line in content.split("\n"):
        if "-----BEGIN RSA PRIVATE KEY-----" in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if "-----END RSA PRIVATE KEY-----" in line:
            break

    # Save private key to temp file
    temp_key_file = Path("/tmp/kalshi_private_key.pem")
    temp_key_file.write_text("\n".join(private_key_lines))

    try:
        # Initialize Kalshi client
        kalshi_client = KalshiBetting(
            api_key_id=api_key_id, private_key_path=str(temp_key_file)
        )

        # Initialize portfolio manager
        manager = PortfolioBettingManager(
            kalshi_client=kalshi_client,
            max_daily_risk_pct=0.25,  # 25% max daily risk
            kelly_fraction=0.20,  # Conservative Kelly for more volume
            min_bet_size=2.0,
            max_bet_size=10.0,  # Lower max to spread across more bets
            max_single_bet_pct=0.03,  # Lower single bet limit for more diversification
            min_edge=0.05,
            min_confidence=0.68,
            dry_run=False,  # LIVE BETTING
        )

        # Process daily bets
        date_str = context["ds"]
        results = manager.process_daily_bets(
            date_str, sports=["nhl", "nba", "mlb", "nfl", "ncaab", "tennis"]
        )

        print(f"\n✓ Portfolio betting complete")
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
                print(f"✓ SMS notification sent")
            else:
                print(f"⚠️  SMS notification failed")
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
        today_str = context["ds"]
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
        for sport in ["nba", "nhl", "ncaab", "tennis", "ligue1"]:
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
            msg2 += f"\nTop bets:\n"
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
            msg3 = f"AVAILABLE TOMORROW\n"
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
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
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
for sport in ["nba", "nhl", "mlb", "nfl", "epl", "tennis", "ncaab", "wncaab", "ligue1"]:
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

# Portfolio betting depends on all bets being identified
# Get all the bets_task for each sport
all_bets_tasks = [
    dag.get_task(f"{sport}_identify_bets")
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
    ]
]

# Portfolio betting runs after all bets are identified
all_bets_tasks >> portfolio_betting_task

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
