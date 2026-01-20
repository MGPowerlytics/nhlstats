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
    """Load downloaded games into DuckDB."""
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
        import duckdb

        # Use read_only to avoid locking conflicts if other processes are analyzing data
        conn = duckdb.connect("data/nhlstats.duckdb", read_only=True)

        # Filter out:
        # 1. Exhibition games (non-NHL teams)
        # 2. Duplicates (keep first occurrence per matchup+date)
        exhibition_teams = (
            "CAN",
            "USA",
            "ATL",
            "MET",
            "CEN",
            "PAC",
            "SWE",
            "FIN",
            "EIS",
            "MUN",
            "SCB",
            "KLS",
            "KNG",
            "MKN",
            "HGS",
            "MAT",
            "MCD",
        )

        games = conn.execute(
            """
            WITH ranked_games AS (
                SELECT game_date, home_team_abbrev, away_team_abbrev,
                       CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win,
                       ROW_NUMBER() OVER (
                           PARTITION BY game_date, home_team_abbrev, away_team_abbrev 
                           ORDER BY game_id
                       ) as rn
                FROM games 
                WHERE game_state IN ('OFF', 'FINAL')
                  AND home_team_abbrev NOT IN ?
                  AND away_team_abbrev NOT IN ?
            )
            SELECT game_date, home_team_abbrev as home_team, 
                   away_team_abbrev as away_team, home_win
            FROM ranked_games
            WHERE rn = 1
            ORDER BY game_date, home_team
        """,
            [exhibition_teams, exhibition_teams],
        ).fetchall()
        conn.close()

        print(f"  Loaded {len(games)} NHL games (filtered duplicates and exhibitions)")

        elo = NHLEloRating(k_factor=10, home_advantage=50, recency_weight=0.2)

        last_date = None
        for game in games:
            game_date = game[0]
            # Handle both string and date objects from DuckDB
            if isinstance(game_date, str):
                current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
            else:
                current_date = game_date

            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 90:  # New season detected
                    print(
                        f"📅 New NHL season detected at {current_date} (Last game: {last_date}, Gap: {days_diff} days)"
                    )
                    elo.apply_season_reversion(0.45)

            last_date = current_date
            # Pass game_date for recency weighting
            elo.update(game[1], game[2], game[3], game_date=current_date)
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
        # Tennis: avoid DuckDB locking by using local CSV history.
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

    # Create sport-specific Glicko-2 instance
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

    # Load and process games (similar to Elo)
    if sport == "nba":
        from nba_elo_rating import load_nba_games_from_json
        import pandas as pd

        games_df = load_nba_games_from_json()
        for _, game in games_df.iterrows():
            glicko.update(game["home_team"], game["away_team"], game["home_win"])
    elif sport == "nhl":
        import duckdb

        conn = duckdb.connect("data/nhlstats.duckdb", read_only=True)
        games = conn.execute(
            """
            SELECT game_date, home_team_abbrev as home_team, away_team_abbrev as away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM games WHERE game_state IN ('OFF', 'FINAL') ORDER BY game_date, game_id
        """
        ).fetchall()
        conn.close()

        for game in games:
            glicko.update(game[1], game[2], game[3])
    elif sport in ["mlb", "nfl"]:
        # Load from database
        import duckdb

        conn = duckdb.connect("data/nhlstats.duckdb", read_only=True)
        table_name = f"{sport}_games"
        games = conn.execute(
            f"""
            SELECT game_date, home_team, away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM {table_name} WHERE game_date IS NOT NULL
            ORDER BY game_date
        """
        ).fetchall()
        conn.close()

        for game in games:
            glicko.update(game[1], game[2], game[3])

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
    """Identify good betting opportunities for a sport."""
    print(f"🎯 Identifying {sport.upper()} betting opportunities...")

    # Pull data from XCom
    ti = context["task_instance"]
    elo_ratings = ti.xcom_pull(
        key=f"{sport}_elo_ratings", task_ids=f"{sport}_update_elo"
    )
    markets = ti.xcom_pull(key=f"{sport}_markets", task_ids=f"{sport}_fetch_markets")

    if not elo_ratings or not markets:
        print(f"⚠️  Missing data for {sport}")
        return

    config = SPORTS_CONFIG[sport]
    team_mapping = config["team_mapping"]
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

    # Load calibration models (safe fallback if unavailable).
    college_calibrator = None
    tennis_calibrators = {}
    try:
        from production_calibration import (
            calibrate_probability,
            get_college_platt_params,
            get_tennis_bucketed_platt_params,
        )

        if sport in ["ncaab", "wncaab"]:
            college_calibrator = get_college_platt_params(league=sport)
        if sport == "tennis":
            tennis_calibrators = get_tennis_bucketed_platt_params()
    except Exception as e:
        print(f"⚠️  Calibration disabled (load error): {e}")

    good_bets = []

    def _normalize_team_name(name: str) -> str:
        """Normalize team names for matching Kalshi titles to Elo keys."""

        return (
            name.lower()
            .replace("&", "and")
            .replace(".", "")
            .replace("'", "")
            .replace(" ", "_")
            .strip()
        )

    def _resolve_team_name(raw_name: str) -> str | None:
        """Resolve a Kalshi title team name to an Elo key."""

        # Fast path: exact key
        if raw_name in elo_ratings:
            return raw_name

        candidate = _normalize_team_name(raw_name)
        # 1) Exact match after normalization
        for key in elo_ratings.keys():
            if _normalize_team_name(key) == candidate:
                return key

        # 2) Heuristic replacements common in titles
        alt = candidate.replace("_st", "_state")
        for key in elo_ratings.keys():
            nk = _normalize_team_name(key)
            if nk == alt:
                return key

        # 3) Substring match (best-effort)
        for key in elo_ratings.keys():
            nk = _normalize_team_name(key)
            if candidate and (candidate in nk or nk in candidate):
                return key

        return None

    for market in markets:
        ticker = market.get("ticker", "")
        if "-" not in ticker:
            continue

        parts = ticker.split("-")

        # NCAAB / WNCAAB LOGIC (Kalshi "Winner?" style markets)
        if sport in ["ncaab", "wncaab"]:
            title = market.get("title", "")
            if " at " not in title:
                continue

            # Parse "TeamA at TeamB Winner?" or just "TeamA at TeamB"
            teams_part = title.split(" Winner?")[0] if " Winner?" in title else title
            try:
                away_raw, home_raw = teams_part.split(" at ")
            except ValueError:
                continue

            away_team = _resolve_team_name(away_raw)
            home_team = _resolve_team_name(home_raw)
            if not away_team or not home_team:
                continue

            # Predict
            try:
                prob_raw = elo_system.predict(home_team, away_team)
            except:
                continue

            # Calibrate home-win probability, then map to target side.
            try:
                prob = calibrate_probability(college_calibrator, float(prob_raw))
            except Exception:
                prob = float(prob_raw)

            # Market probability for this contract (YES = the team identified by ticker suffix wins)
            yes_ask = market.get("yes_ask", 0) / 100.0

            # Determine whether this market is for home or away team.
            # Kalshi tickers look like:
            #   KXNCAAWBGAME-26JAN22MASSLUVM-UVM
            # where the event portion ends with the home code, and the final segment is the team code.
            event_part = parts[1]
            team_code = parts[-1]

            target_side = "away"
            if (
                isinstance(event_part, str)
                and isinstance(team_code, str)
                and event_part.endswith(team_code)
            ):
                target_side = "home"

            market_prob = yes_ask
            elo_prob = prob if target_side == "home" else (1.0 - prob)

            edge = elo_prob - market_prob
            if elo_prob > elo_threshold and edge > 0.05:
                confidence = "HIGH" if elo_prob > (elo_threshold + 0.1) else "MEDIUM"
                good_bets.append(
                    {
                        "home_team": home_team,
                        "away_team": away_team,
                        "elo_prob": elo_prob,
                        "market_prob": market_prob,
                        "edge": edge,
                        "bet_on": target_side,
                        "confidence": confidence,
                        "ticker": ticker,
                        "title": title,
                        "yes_ask": market.get("yes_ask"),
                        "no_ask": market.get("no_ask"),
                        "close_time": serialize_datetime(market.get("close_time")),
                        "status": market.get("status"),
                    }
                )

            continue  # Skip standard logic

        # EPL LOGIC
        if sport == "epl":
            title = market.get("title", "")
            if " vs " not in title or " Winner?" not in title:
                continue

            teams_str = title.split(" Winner?")[0]
            try:
                home_name, away_name = teams_str.split(" vs ")
            except ValueError:
                continue

            # Get predictions (Home, Draw, Away)
            try:
                probs = elo_system.predict_probs(home_name, away_name)
            except KeyError:
                # Try correcting names if needed or skip
                continue

            outcome_code = parts[-1]

            elo_prob = 0
            bet_on = "Unknown"

            if outcome_code == "TIE":
                elo_prob = probs[1]
                bet_on = "Draw"
            else:
                # Determine if Home or Away
                # Check mapping first
                mapped_name = team_mapping.get(outcome_code)
                if mapped_name == home_name:
                    elo_prob = probs[0]
                    bet_on = "Home"
                elif mapped_name == away_name:
                    elo_prob = probs[2]
                    bet_on = "Away"
                else:
                    # Fallback to prefix matching
                    if home_name.upper().startswith(outcome_code):
                        elo_prob = probs[0]
                        bet_on = "Home"
                    elif away_name.upper().startswith(outcome_code):
                        elo_prob = probs[2]
                        bet_on = "Away"
                    else:
                        continue

            # Market Prob
            yes_ask = market.get("yes_ask", 0) / 100.0
            market_prob = yes_ask

            edge = elo_prob - market_prob

            if elo_prob > elo_threshold and edge > 0.05:
                confidence = "HIGH" if elo_prob > (elo_threshold + 0.1) else "MEDIUM"
                good_bets.append(
                    {
                        "home_team": home_name,
                        "away_team": away_name,
                        "elo_prob": elo_prob,
                        "market_prob": market_prob,
                        "edge": edge,
                        "bet_on": bet_on,
                        "confidence": confidence,
                        "yes_ask": market.get("yes_ask"),
                        "no_ask": market.get("no_ask"),
                    }
                )
                print(
                    f"  ✓ {away_name} @ {home_name}: Bet {bet_on} (Edge: {edge:.1%}, Elo: {elo_prob:.1%})"
                )

            continue

        # LIGUE 1 LOGIC (same as EPL - 3-way markets)
        if sport == "ligue1":
            # Ticker format: KXLIGUE1GAME-26JAN25LILRCS-LIL
            # Parse team codes from ticker
            try:
                game_part = parts[1]  # LILRCS (home+away codes)
                outcome_code = parts[2] if len(parts) > 2 else None

                if not outcome_code or outcome_code not in [
                    "TIE",
                    "LIL",
                    "RCS",
                    "PAR",
                    "ANG",
                    "OL",
                    "FCM",
                    "TFC",
                    "STB",
                    "NIC",
                    "FCN",
                ]:
                    continue

                # Try to match to known teams
                home_team = None
                away_team = None

                # Simple heuristic: first 3 chars = away, next 3 = home
                # Or check team_mapping
                for code, team in team_mapping.items():
                    if code in game_part:
                        if not away_team and game_part.startswith(code):
                            away_team = team
                        elif not home_team:
                            home_team = team

                if not home_team or not away_team:
                    continue

                # Get 3-way predictions
                try:
                    probs = elo_system.predict_3way(home_team, away_team)
                except (KeyError, AttributeError):
                    continue

                elo_prob = 0
                bet_on = "Unknown"

                if outcome_code == "TIE":
                    elo_prob = probs["draw"]
                    bet_on = "Draw"
                else:
                    # Check if outcome matches home or away
                    mapped_team = team_mapping.get(outcome_code)
                    if mapped_team == home_team:
                        elo_prob = probs["home"]
                        bet_on = "home"
                    elif mapped_team == away_team:
                        elo_prob = probs["away"]
                        bet_on = "away"
                    else:
                        continue

                # Market probability
                yes_ask = market.get("yes_ask", 0) / 100.0
                market_prob = yes_ask

                edge = elo_prob - market_prob

                if elo_prob > elo_threshold and edge > 0.05:
                    confidence = (
                        "HIGH" if elo_prob > (elo_threshold + 0.1) else "MEDIUM"
                    )
                    good_bets.append(
                        {
                            "home_team": home_team,
                            "away_team": away_team,
                            "elo_prob": elo_prob,
                            "market_prob": market_prob,
                            "edge": edge,
                            "bet_on": bet_on,
                            "confidence": confidence,
                            "yes_ask": market.get("yes_ask"),
                            "no_ask": market.get("no_ask"),
                            "sport": "Ligue 1",
                            "ticker": ticker,
                        }
                    )
                    print(
                        f"  ✓ {away_team} @ {home_team}: Bet {bet_on} (Edge: {edge:.1%}, Elo: {elo_prob:.1%})"
                    )

            except Exception as e:
                print(f"  ⚠️  Error processing Ligue 1 market {ticker}: {e}")

            continue

        # TENNIS LOGIC
        if sport == "tennis":
            # Tennis ticker format: "KXATPMATCH-26JAN17DIMMAC-DIM" or "KXWTAMATCH-26JAN17PLAYER1PLAYER2-PLAYER"
            # Title: "Will [Player] win the [Player1] vs [Player2] : Round match?"

            title = market.get("title", "")
            ticker = market.get("ticker", "")

            # Parse player names from title
            # Format: "Will Grigor Dimitrov win the Dimitrov vs Machac : Round Of 128 match?"
            if "Will " not in title or " win the " not in title or " vs " not in title:
                continue

            try:
                # Extract the player from "Will X win"
                after_will = title.split("Will ")[1]
                yes_player_full = after_will.split(" win the ")[0].strip()

                # Extract matchup "Player1 vs Player2"
                rest = after_will.split(" win the ")[1]
                matchup = rest.split(":")[0].strip()  # "Dimitrov vs Machac"

                if " vs " not in matchup:
                    continue

                matchup_parts = matchup.split(" vs ")
                player1_short = matchup_parts[0].strip()
                player2_short = matchup_parts[1].strip()

                # Match to Elo system using full names
                # Build a more robust lookup: try full name match first, then lastname match
                def find_elo_player(search_name, ratings_dict):
                    """Find player in Elo system by name."""
                    search_lower = search_name.lower()

                    # Try exact match
                    for elo_name in ratings_dict.keys():
                        if elo_name.lower() == search_lower:
                            return elo_name

                    # Try lastname + first initial match
                    search_lastname = (
                        search_name.split()[-1].lower()
                        if " " in search_name
                        else search_name.lower()
                    )
                    candidates = []
                    for elo_name in ratings_dict.keys():
                        elo_lastname = elo_name.split()[0].lower()
                        if elo_lastname == search_lastname:
                            candidates.append(elo_name)

                    # If only one match, use it
                    if len(candidates) == 1:
                        return candidates[0]

                    # Multiple matches - try to use first name
                    if " " in search_name and len(candidates) > 1:
                        search_first = search_name.split()[0].lower()
                        for cand in candidates:
                            # Elo format: "Lastname F." or "Lastname F.I."
                            if len(cand.split()) > 1:
                                elo_first_initial = cand.split()[1][0].lower()
                                if search_first.startswith(elo_first_initial):
                                    return cand
                        # Return first candidate if no match
                        return candidates[0]

                    return None

                # Determine tour from ticker prefix
                tour = None
                if isinstance(ticker, str) and ticker.startswith("KXATPMATCH"):
                    tour = "ATP"
                elif isinstance(ticker, str) and ticker.startswith("KXWTAMATCH"):
                    tour = "WTA"

                if tour is None:
                    continue

                tour_ratings = (
                    elo_system.atp_ratings if tour == "ATP" else elo_system.wta_ratings
                )

                # The YES side is the player mentioned in "Will X win"
                yes_player_elo = find_elo_player(yes_player_full, tour_ratings)

                # Determine NO player (the other one in the matchup)
                # Check which short name matches the YES player
                if player1_short.lower() in yes_player_full.lower():
                    no_player_elo = find_elo_player(player2_short, tour_ratings)
                    player1_elo = yes_player_elo
                    player2_elo = no_player_elo
                    player1 = yes_player_full
                    player2 = player2_short
                else:
                    no_player_elo = find_elo_player(player1_short, tour_ratings)
                    player1_elo = no_player_elo
                    player2_elo = yes_player_elo
                    player1 = player1_short
                    player2 = yes_player_full

                if not yes_player_elo or not no_player_elo:
                    # Players not found in Elo system
                    continue

                # Get Elo predictions for YES player
                # YES player is the one mentioned in "Will X win"
                # Use a deterministic ordering for calibration consistency.
                a, b = sorted([yes_player_elo, no_player_elo])
                try:
                    p_a_raw = float(elo_system.predict(a, b, tour=tour))
                except Exception:
                    continue

                # Apply tour-specific calibrator to P(a wins), then map back.
                p_a_cal = p_a_raw
                try:
                    params = tennis_calibrators.get(tour)
                    p_a_cal = calibrate_probability(params, p_a_raw)
                except Exception:
                    p_a_cal = p_a_raw

                yes_player_win_prob = (
                    p_a_cal if yes_player_elo == a else (1.0 - p_a_cal)
                )

                # Market probability for YES player winning
                yes_ask = market.get("yes_ask", 0) / 100.0
                market_prob = yes_ask
                elo_prob = yes_player_win_prob

                # Calculate edge
                edge = elo_prob - market_prob

                # Check if YES player is a good bet
                if elo_prob > elo_threshold and edge > 0.05:
                    confidence = (
                        "HIGH" if elo_prob > (elo_threshold + 0.1) else "MEDIUM"
                    )

                    good_bets.append(
                        {
                            "player1": yes_player_full,
                            "player2": no_player_elo.split()[
                                0
                            ],  # Just lastname of opponent
                            "elo_prob": elo_prob,
                            "market_prob": market_prob,
                            "edge": edge,
                            "bet_on": yes_player_full,
                            "opponent": no_player_elo.split()[0],
                            "matchup": matchup,
                            "confidence": confidence,
                            "yes_ask": market.get("yes_ask"),
                            "no_ask": market.get("no_ask"),
                            "ticker": ticker,
                            "title": title,
                            "close_time": serialize_datetime(market.get("close_time")),
                            "status": market.get("status"),
                            "sport": "tennis",
                        }
                    )

                    print(
                        f"  ✓ {matchup}: Bet YES on {yes_player_full} (Edge: {edge:.1%}, Elo: {elo_prob:.1%})"
                    )

                # Check NO side (betting against YES player)
                no_player_win_prob = 1.0 - yes_player_win_prob
                edge_no = no_player_win_prob - (market.get("no_ask", 0) / 100.0)

                if no_player_win_prob > elo_threshold and edge_no > 0.05:
                    confidence = (
                        "HIGH"
                        if no_player_win_prob > (elo_threshold + 0.1)
                        else "MEDIUM"
                    )

                    good_bets.append(
                        {
                            "player1": no_player_elo.split()[0],
                            "player2": yes_player_full,
                            "elo_prob": no_player_win_prob,
                            "market_prob": market.get("no_ask", 0) / 100.0,
                            "edge": edge_no,
                            "bet_on": no_player_elo,
                            "opponent": yes_player_full.split()[-1],
                            "matchup": matchup,
                            "confidence": confidence,
                            "yes_ask": market.get("no_ask"),  # Buy NO = sell YES
                            "no_ask": market.get("yes_ask"),
                            "ticker": ticker,
                            "title": title,
                            "close_time": serialize_datetime(market.get("close_time")),
                            "status": market.get("status"),
                            "sport": "tennis",
                        }
                    )

                    print(
                        f"  ✓ {matchup}: Bet NO on {yes_player_full} (= {no_player_elo} wins) (Edge: {edge_no:.1%}, Elo: {no_player_win_prob:.1%})"
                    )

            except Exception as e:
                print(f"  ⚠️  Error parsing tennis match: {e}")
                continue

            continue

        # STANDARD LOGIC (NBA, NHL, MLB, NFL)
        if len(parts) < 3:
            continue

        matchup = parts[1]
        team_code = parts[2]

        # Extract team codes from matchup (e.g., "26JAN19MIAGSW")
        if len(matchup) < 13:
            continue

        away_code = matchup[7:10]
        home_code = matchup[10:13]

        # Map to Elo team names
        away_team = team_mapping.get(away_code)
        home_team = team_mapping.get(home_code)

        if not away_team or not home_team:
            continue

        # Calculate Elo prediction
        try:
            home_win_prob = elo_system.predict(home_team, away_team)
        except:
            continue

        # Determine market probability
        yes_ask = market.get("yes_ask", 0) / 100.0
        no_ask = market.get("no_ask", 0) / 100.0

        if team_code == home_code:
            market_prob = yes_ask
            elo_prob = home_win_prob
            bet_on = "home"
        else:
            market_prob = yes_ask
            elo_prob = 1 - home_win_prob
            bet_on = "away"

        # Calculate edge
        edge = elo_prob - market_prob

        # Check if this is a good bet
        if elo_prob > elo_threshold and edge > 0.05:
            confidence = "HIGH" if elo_prob > (elo_threshold + 0.1) else "MEDIUM"

            good_bets.append(
                {
                    "home_team": home_team,
                    "away_team": away_team,
                    "elo_prob": elo_prob,
                    "market_prob": market_prob,
                    "edge": edge,
                    "bet_on": bet_on,
                    "confidence": confidence,
                    "yes_ask": market.get("yes_ask"),
                    "no_ask": market.get("no_ask"),
                    "ticker": market.get("ticker"),
                    "title": market.get("title"),
                    "close_time": serialize_datetime(market.get("close_time")),
                    "status": market.get("status"),
                }
            )

            print(
                f"  ✓ {away_team} @ {home_team}: Bet {bet_on} (Edge: {edge:.1%}, Elo: {elo_prob:.1%})"
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
            kelly_fraction=0.25,  # Quarter Kelly
            min_bet_size=2.0,
            max_bet_size=50.0,
            max_single_bet_pct=0.05,
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
    if sport not in ["nba", "ncaab", "tennis"]:
        print(f"⚠️  Skipping {sport.upper()} - only betting on NBA/NCAAB/TENNIS")
        return

    print(f"\n{'='*80}")
    print(f"🎰 PLACING BETS FOR {sport.upper()}")
    print(f"{'='*80}\n")

    # Load bet recommendations from file
    bet_file = f'data/{sport}/bets_{context["ds"]}.json'

    if not Path(bet_file).exists():
        print(f"⚠️  No bet file found: {bet_file}")
        return

    with open(bet_file, "r") as f:
        recommendations = json.load(f)

    if not recommendations:
        print(f"ℹ️  No recommendations for {sport.upper()}")
        return

    print(f"📊 Found {len(recommendations)} recommendations")

    # Load Kalshi credentials (check data directory first, then root)
    kalshkey_file = Path("/opt/airflow/kalshkey")
    if not kalshkey_file.exists():
        kalshkey_file = Path("kalshkey")

    if not kalshkey_file.exists():
        print("❌ Kalshi credentials not found")
        return

    # Parse API key ID from kalshkey
    with open(kalshkey_file, "r") as f:
        first_line = f.readline().strip()
        if "API key id:" in first_line:
            api_key_id = first_line.split("API key id:")[1].strip()
        else:
            print("❌ Invalid Kalshi credentials format")
            return

    # Find private key file (check data directory)
    private_key_path = Path("data/kalshi_private_key.pem")
    if not private_key_path.exists():
        private_key_path = Path("/opt/airflow/data/kalshi_private_key.pem")
    if not private_key_path.exists():
        private_key_path = Path("/opt/airflow/kalshi_private_key.pem")

    if not private_key_path.exists():
        print("❌ Kalshi private key not found")
        return

    # Load Odds API key for game start verification
    odds_api_key = None
    odds_key_file = Path("data/odds_api_key")
    if not odds_key_file.exists():
        odds_key_file = Path("/opt/airflow/data/odds_api_key")
    if not odds_key_file.exists():
        odds_key_file = Path("/opt/airflow/odds_api_key")

    if odds_key_file.exists():
        with open(odds_key_file, "r") as f:
            odds_api_key = f.read().strip()
        print(f"✅ Loaded Odds API key for game verification")
    else:
        print(f"⚠️  No Odds API key - cannot verify game start times!")

    # Check for already placed bets
    placed_bets_file = Path(
        f'data/{sport}/bets_placed_{context["ds"].replace("-", "")[-4:]}.json'
    )
    already_placed_tickers = set()
    if placed_bets_file.exists():
        try:
            with open(placed_bets_file, "r") as f:
                placed_bets = json.load(f)
            already_placed_tickers = {
                bet.get("ticker") for bet in placed_bets if bet.get("ticker")
            }
            print(
                f"📋 Found {len(already_placed_tickers)} already placed bets to avoid"
            )
        except:
            pass

    # Filter out already placed bets
    original_count = len(recommendations)
    recommendations = [
        r for r in recommendations if r.get("ticker") not in already_placed_tickers
    ]
    if len(recommendations) < original_count:
        print(f"⏭️  Skipped {original_count - len(recommendations)} duplicate bets")

    # Filter out matches that have already started (unless we're winning)
    # Check close_time for tennis and other time-sensitive sports
    from datetime import timezone

    now = datetime.now(timezone.utc)
    started_filtered = []

    for rec in recommendations:
        close_time_str = rec.get("close_time")
        if close_time_str:
            try:
                close_time = datetime.fromisoformat(
                    close_time_str.replace("Z", "+00:00")
                )
                if close_time <= now:
                    print(f"⏭️  Skipping {rec.get('ticker')}: Match already started")
                    continue
            except:
                pass
        started_filtered.append(rec)

    skipped_started = len(recommendations) - len(started_filtered)
    if skipped_started > 0:
        print(f"⏭️  Skipped {skipped_started} matches that already started")

    recommendations = started_filtered

    if not recommendations:
        print(f"ℹ️  All recommendations already placed or started")
        return

    # Initialize betting client
    from kalshi_betting import KalshiBetting

    try:
        client = KalshiBetting(
            api_key_id=api_key_id,
            private_key_path=str(private_key_path),
            max_bet_size=5.0,
            production=True,
            odds_api_key=odds_api_key,
        )

        # Add sport to recommendations
        for rec in recommendations:
            rec["sport"] = sport.upper()

        # Process recommendations
        result = client.process_bet_recommendations(
            recommendations=recommendations,
            sport_filter=[sport.upper()],
            min_confidence=0.75,  # Only bet on >75% confidence
            min_edge=0.05,  # Minimum 5% edge
            dry_run=False,  # Set to True for testing
        )

        # Save betting results
        result_file = f'data/{sport}/betting_results_{context["ds"]}.json'
        with open(result_file, "w") as f:
            json.dump(result, f, indent=2, default=str)

        print(f"\n💾 Results saved to {result_file}")
        print(f"✅ Placed: {len(result['placed'])}")
        print(f"⏭️  Skipped: {len(result['skipped'])}")
        print(f"❌ Errors: {len(result['errors'])}")

        # Push to XCom
        context["task_instance"].xcom_push(
            key=f"{sport}_bets_placed", value=len(result["placed"])
        )

    except Exception as e:
        print(f"❌ Betting failed: {e}")
        import traceback

        traceback.print_exc()
        print("\n⚠️  Continuing with workflow (bets not placed)")


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
        for sport in ["nba", "ncaab", "tennis"]:
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
        pool="duckdb_pool",
    )

    elo_task = PythonOperator(
        task_id=f"{sport}_update_elo",
        python_callable=update_elo_ratings,
        op_kwargs={"sport": sport},
        dag=dag,
        pool="duckdb_pool",
    )

    # Add Glicko-2 task for supported sports
    if sport in ["nba", "nhl", "mlb", "nfl"]:
        glicko2_task = PythonOperator(
            task_id=f"{sport}_update_glicko2",
            python_callable=update_glicko2_ratings,
            op_kwargs={"sport": sport},
            dag=dag,
            pool="duckdb_pool",
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
        pool="duckdb_pool",
    )

    # Place bets task (for NBA, NCAAB, WNCAAB, and TENNIS)
    if sport in ["nba", "ncaab", "wncaab", "tennis"]:
        place_bets_task = PythonOperator(
            task_id=f"{sport}_place_bets",
            python_callable=place_bets_on_recommendations,
            op_kwargs={"sport": sport},
            dag=dag,
            pool="duckdb_pool",
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
        if sport in ["nba", "ncaab"]:
            # Place bets, then load to DB
            bets_task >> place_bets_task >> load_bets_task
        else:
            bets_task >> load_bets_task
    else:
        # Without Glicko-2
        download_task >> load_task >> elo_task >> markets_task >> bets_task
        if sport in ["ncaab", "wncaab", "tennis"]:
            bets_task >> place_bets_task >> load_bets_task
        else:
            bets_task >> load_bets_task

# Add unified portfolio betting task (runs after all sports have identified bets)
portfolio_betting_task = PythonOperator(
    task_id="portfolio_optimized_betting",
    python_callable=place_portfolio_optimized_bets,
    dag=dag,
    pool="duckdb_pool",
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

# Add daily summary task (runs at the end)
daily_summary_task = PythonOperator(
    task_id="send_daily_summary",
    python_callable=send_daily_summary,
    dag=dag,
)

# Daily summary runs after portfolio betting
portfolio_betting_task >> daily_summary_task
