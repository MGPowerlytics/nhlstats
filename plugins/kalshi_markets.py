#!/usr/bin/env python3
"""
Fetch Kalshi markets for NHL/NBA games using official SDK.

Provides market fetching functions for all sports with:
- Proper error handling (graceful degradation on failures)
- Rate limiting (0.5s delay between API calls)
- Structured logging for Airflow visibility
- Import error handling for missing kalshi_python package
"""

import logging
import time
from datetime import datetime
from pathlib import Path
import re

# Configure module logger
logger = logging.getLogger(__name__)

# Try to import kalshi_python - handle gracefully if missing
try:
    from kalshi_python import Configuration, ApiClient, MarketsApi
    KALSHI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️  kalshi_python not installed: {e}")
    logger.warning("   Install with: pip install kalshi-python")
    KALSHI_AVAILABLE = False
    Configuration = None
    ApiClient = None
    MarketsApi = None

try:
    from db_manager import DBManager, default_db
except ImportError:
    logger.warning("⚠️  db_manager not available - database operations disabled")
    DBManager = None
    default_db = None


# Rate limiting - minimum time between API calls
API_RATE_LIMIT_SECONDS = 0.5
_last_api_call_time = 0


def _rate_limit():
    """Enforce rate limiting between API calls."""
    global _last_api_call_time
    elapsed = time.time() - _last_api_call_time
    if elapsed < API_RATE_LIMIT_SECONDS:
        sleep_time = API_RATE_LIMIT_SECONDS - elapsed
        logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
        time.sleep(sleep_time)
    _last_api_call_time = time.time()


class KalshiAPI:
    """Kalshi API client using official SDK"""

    def __init__(self, api_key_id, private_key_pem):
        if not KALSHI_AVAILABLE:
            raise ImportError("kalshi_python package not installed. Run: pip install kalshi-python")

        self.api_key_id = api_key_id
        self.private_key_pem = private_key_pem

        # Configure API client
        config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
        config.api_key["api_key_id"] = api_key_id
        config.api_key["private_key"] = private_key_pem

        # Create client
        self.api_client = ApiClient(configuration=config)
        self.markets_api = MarketsApi(self.api_client)

    def get_markets(
        self, event_ticker=None, series_ticker=None, status="open", limit=100
    ):
        """Get markets from Kalshi with rate limiting and error handling.

        Args:
            event_ticker: Optional event ticker filter
            series_ticker: Optional series ticker filter (e.g., 'KXNBAGAME')
            status: Market status filter (default: 'open')
            limit: Maximum number of markets to return

        Returns:
            dict with 'markets' key containing list of markets, or None on error
        """
        _rate_limit()  # Enforce rate limiting

        try:
            logger.debug(f"Fetching markets: series={series_ticker}, limit={limit}")
            response = self.markets_api.get_markets(
                event_ticker=event_ticker,
                series_ticker=series_ticker,
                status=status,
                limit=limit,
            )
            result = response.to_dict()
            market_count = len(result.get('markets', []))
            logger.info(f"✓ Fetched {market_count} markets from {series_ticker or 'all'}")
            return result
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                logger.warning(f"⚠️  Rate limited by Kalshi API for {series_ticker}: {e}")
            elif "401" in error_msg or "403" in error_msg:
                logger.error(f"✗ Authentication failed for Kalshi API: {e}")
            else:
                logger.error(f"✗ Failed to get markets from {series_ticker}: {e}")
            return None


def _generate_game_id(sport, game_date, home_team, away_team):
    """
    Generates a consistent and unique game_id.
    Format: SPORT_YYYYMMDD_HOME_AWAY (cleaned)
    """
    date_str = game_date.replace("-", "")
    home_slug = "".join(filter(str.isalnum, home_team)).upper()
    away_slug = "".join(filter(str.isalnum, away_team)).upper()
    return f"{sport.upper()}_{date_str}_{home_slug}_{away_slug}"


def save_to_db(sport: str, markets: list, db_manager: DBManager = default_db):
    """
    Save Kalshi markets to the unified_games and game_odds tables in PostgreSQL.
    """
    if not markets:
        return 0

    from naming_resolver import NamingResolver

    odds_count = 0
    print(f"💾 Saving {len(markets)} {sport.upper()} Kalshi markets to PostgreSQL...")

    for market in markets:
        ticker = market.get("ticker", "")
        title = market.get("title", "")

        home_team = None
        away_team = None
        game_date = None

        # Standard Kalshi Ticker Parsing
        # Attempt 1: SERIES-YYMMDD-AWAYHOME-OUTCOME (Old format)
        parts = ticker.split("-")
        parsed = False

        # For tennis, ALWAYS use title parsing for player names (to get full names, not 3-letter codes)
        # We only extract the date from the ticker for tennis
        if sport.lower() == "tennis":
            # Extract date from ticker but use title for names
            if len(parts) >= 2:
                middle = parts[1]
                match_date = re.match(r"^(\d{2})([A-Z]{3})(\d{2})", middle)
                if match_date:
                    y_str, m_str, d_str = match_date.groups()
                    try:
                        dt = datetime.strptime(f"{y_str}{m_str}{d_str}", "%y%b%d")
                        game_date = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        pass

            # Parse player names from title
            match = re.search(r"win the (.*?) vs (.*?) (?:match|:)", title)
            if not match:
                match = re.search(r"win the (.*?) vs (.*?) match", title)

            if match:
                home_team = match.group(1).strip()
                away_team = match.group(2).strip()
                if away_team.endswith(" match"):
                    away_team = away_team[:-6].strip()
                parsed = True

                # Use close_time as fallback for date
                if not game_date:
                    close_time = market.get("close_time")
                    if close_time:
                        if isinstance(close_time, str):
                            game_date = close_time.split("T")[0]
                        else:
                            game_date = close_time.strftime("%Y-%m-%d")

        # Non-tennis: use standard ticker parsing
        elif len(parts) >= 3:
            # Try numeric date format first (Old)
            try:
                date_part = parts[1]
                # Check if it's purely numeric and length 6 (YYMMDD)
                if len(date_part) == 6 and date_part.isdigit():
                    year = 2000 + int(date_part[0:2])
                    month = int(date_part[2:4])
                    day = int(date_part[4:6])
                    game_date = f"{year}-{month:02d}-{day:02d}"

                    teams_part = parts[2]
                    if len(teams_part) == 6:
                        away_team = teams_part[0:3]
                        home_team = teams_part[3:6]
                        parsed = True
            except Exception:
                pass

        # Attempt 2: SERIES-YYMMMDDTEAMS-OUTCOME (New format: 26JAN24LALDAL)
        if not parsed and len(parts) >= 2:
            try:
                # The middle part contains everything: Date + Teams
                middle = parts[1]
                # Regex for YYMMMDDTEAMS (e.g. 26JAN24LALDAL)
                # 2 digits Year, 3 letters Month, 2 digits Day, remaining is Teams
                match_new = re.match(r"^(\d{2})([A-Z]{3})(\d{2})([A-Z]+)$", middle)
                if match_new:
                    y_str, m_str, d_str, teams_str = match_new.groups()

                    # Parse date
                    dt = datetime.strptime(f"{y_str}{m_str}{d_str}", "%y%b%d")
                    game_date = dt.strftime("%Y-%m-%d")

                    # Teams: Assuming 3-char codes usually, so 6 chars total?
                    # Or split in half?
                    # NBA/NCAAB usually 3 chars.
                    if len(teams_str) == 6:
                        away_team = teams_str[0:3]
                        home_team = teams_str[3:6]
                        parsed = True
                    elif (
                        " vs " in title
                    ):  # Fallback to title if ticker teams are ambiguous
                        pass
            except Exception:
                # print(f"Failed new format parse: {e}")
                pass

        # Fallback for Tennis or others where Title is key
        if not home_team or not away_team or not game_date:
            if sport.lower() == "tennis":
                match = re.search(r"win the (.*?) vs (.*?) (?:match|:)", title)
                if not match:
                    match = re.search(r"win the (.*?) vs (.*?) match", title)

                if match:
                    home_team = match.group(1).strip()
                    away_team = match.group(2).strip()
                    if away_team.endswith(" match"):
                        away_team = away_team[:-6].strip()

                    close_time = market.get("close_time")
                    if close_time:
                        if isinstance(close_time, str):
                            game_date = close_time.split("T")[0]
                        else:
                            game_date = close_time.strftime("%Y-%m-%d")

        if not home_team or not away_team or not game_date:
            continue

        # Resolve canonical names
        canon_home = NamingResolver.resolve(sport, "kalshi", home_team) or home_team
        canon_away = NamingResolver.resolve(sport, "kalshi", away_team) or away_team

        game_id = _generate_game_id(sport, game_date, canon_home, canon_away)

        # 1. Upsert into unified_games
        db_manager.execute(
            """
            INSERT INTO unified_games (
                game_id, sport, game_date, home_team_id, home_team_name,
                away_team_id, away_team_name, status
            ) VALUES (:game_id, :sport, :game_date, :home_id, :home_name,
                     :away_id, :away_name, :status)
            ON CONFLICT (game_id) DO UPDATE SET
                status = EXCLUDED.status
        """,
            {
                "game_id": game_id,
                "sport": sport.upper(),
                "game_date": game_date,
                "home_id": home_team,
                "home_name": canon_home,
                "away_id": away_team,
                "away_name": canon_away,
                "status": "Scheduled",
            },
        )

        # 2. Upsert into game_odds for Kalshi
        outcome_side = parts[-1] if len(parts) > 1 else None
        yes_price_cents = market.get("yes_ask", 0)

        if yes_price_cents > 0 and outcome_side:
            decimal_odds = 100.0 / yes_price_cents

            def get_last_name_code(name):
                parts = name.split()
                return parts[-1][:3].upper() if parts else name[:3].upper()

            h_code = get_last_name_code(home_team)
            a_code = get_last_name_code(away_team)

            if outcome_side == h_code:
                outcome_name = "home"
            elif outcome_side == a_code:
                outcome_name = "away"
            else:
                outcome_name = "home" if outcome_side == home_team else "away"

            odds_id = f"{game_id}_kalshi_{outcome_name}"
            db_manager.execute(
                """
                INSERT INTO game_odds (
                    odds_id, game_id, bookmaker, market_name, outcome_name, price, is_pregame, external_id
                ) VALUES (:odds_id, :game_id, 'Kalshi', 'moneyline', :outcome_name, :price, True, :ticker)
                ON CONFLICT (odds_id) DO UPDATE SET
                    price = EXCLUDED.price,
                    external_id = EXCLUDED.external_id
            """,
                {
                    "odds_id": odds_id,
                    "game_id": game_id,
                    "outcome_name": outcome_name,
                    "price": decimal_odds,
                    "ticker": ticker,
                },
            )
            odds_count += 1
    return odds_count


def load_kalshi_credentials():
    """Load Kalshi credentials from standard files."""
    key_file = Path("kalshkey")
    if not key_file.exists():
        key_file = Path("/opt/airflow/kalshkey")

    if not key_file.exists():
        raise FileNotFoundError("Kalshi credentials file not found")

    content = key_file.read_text()

    # 1. Extract API Key ID
    api_key_id = None
    for line in content.split("\n"):
        if "API key id:" in line:
            api_key_id = line.split(": ")[1].strip()
            break

    # 2. Extract Private Key
    private_key = None
    if "-----BEGIN RSA PRIVATE KEY-----" in content:
        # Key is embedded in the kalshkey file
        lines = content.split("\n")
        in_key = False
        key_lines = []
        for line in lines:
            if "-----BEGIN RSA PRIVATE KEY-----" in line:
                in_key = True
            if in_key:
                key_lines.append(line)
            if "-----END RSA PRIVATE KEY-----" in line:
                break
        private_key = "\n".join(key_lines)
    else:
        # Look for external .pem file
        pem_file = Path("kalshi_private_key.pem")
        if not pem_file.exists():
            pem_file = Path("/opt/airflow/kalshi_private_key.pem")
        if not pem_file.exists():
            pem_file = Path(__file__).parent.parent / "kalshi_private_key.pem"

        if pem_file.exists():
            private_key = pem_file.read_text()

    if not api_key_id or not private_key:
        raise ValueError(
            "Could not find both API Key ID and Private Key in credentials"
        )

    return api_key_id, private_key


def _fetch_sport_markets(
    sport: str,
    series_tickers: list,
    limit: int = 200,
    date_str: str = None,
) -> list:
    """
    Generic function to fetch markets for any sport with error handling.

    Args:
        sport: Sport code (e.g., 'nba', 'nhl', 'tennis')
        series_tickers: List of Kalshi series tickers to fetch
        limit: Max markets per series (default 200)
        date_str: Optional date string (currently unused, for API compatibility)

    Returns:
        List of market dictionaries, empty list on error
    """
    if not KALSHI_AVAILABLE:
        logger.error(f"✗ Cannot fetch {sport.upper()} markets: kalshi_python not installed")
        return []

    try:
        api_key_id, private_key = load_kalshi_credentials()
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"✗ Cannot fetch {sport.upper()} markets: {e}")
        return []

    try:
        api = KalshiAPI(api_key_id, private_key)
    except Exception as e:
        logger.error(f"✗ Failed to initialize Kalshi API for {sport.upper()}: {e}")
        return []

    all_markets = []
    for series_ticker in series_tickers:
        try:
            result = api.get_markets(series_ticker=series_ticker, limit=limit)
            if result and "markets" in result:
                markets = [
                    m for m in result["markets"]
                    if m.get("status") in ["active", "initialized", "open"]
                ]
                all_markets.extend(markets)
                logger.info(f"  📊 {series_ticker}: {len(markets)} active markets")
        except Exception as e:
            logger.warning(f"  ⚠️  Failed to fetch {series_ticker}: {e}")
            continue  # Continue with other series if one fails

    if all_markets:
        try:
            saved = save_to_db(sport, all_markets)
            logger.info(f"✓ {sport.upper()}: Fetched {len(all_markets)} markets, saved {saved} odds")
        except Exception as e:
            logger.error(f"✗ Failed to save {sport.upper()} markets to DB: {e}")
    else:
        logger.info(f"ℹ️  {sport.upper()}: No active markets found")

    return all_markets


# Sport-specific series tickers
SPORT_SERIES = {
    "nba": ["KXNBAGAME"],
    "nhl": ["KXNHLGAME"],
    "mlb": ["KXMLBGAME"],
    "nfl": ["KXNFLGAME"],
    "epl": ["KXEPLGAME"],
    "ligue1": ["KXLIGUE1GAME"],
    "ncaab": ["KXNCAAMBGAME"],
    "wncaab": ["KXNCAAWBGAME"],
    "tennis": [
        "KXATPMATCH",
        "KXWTAMATCH",
        "KXATPCHALLENGERMATCH",
        "KXWTACHALLENGERMATCH",
    ],
}

# Sport-specific limits (NCAAB/WNCAAB have more games)
SPORT_LIMITS = {
    "ncaab": 1000,
    "wncaab": 1000,
}


def fetch_nba_markets(date_str=None):
    """Fetch NBA markets from Kalshi."""
    return _fetch_sport_markets("nba", SPORT_SERIES["nba"], date_str=date_str)


def fetch_nhl_markets(date_str=None):
    """Fetch NHL markets from Kalshi."""
    return _fetch_sport_markets("nhl", SPORT_SERIES["nhl"], date_str=date_str)


def fetch_epl_markets(date_str=None):
    """Fetch EPL (English Premier League) markets from Kalshi."""
    return _fetch_sport_markets("epl", SPORT_SERIES["epl"], date_str=date_str)


def fetch_ligue1_markets(date_str=None):
    """Fetch Ligue 1 (French) markets from Kalshi."""
    return _fetch_sport_markets("ligue1", SPORT_SERIES["ligue1"], date_str=date_str)


def fetch_tennis_markets(date_str=None):
    """Fetch all Tennis markets from Kalshi (ATP, WTA, Challenger)."""
    return _fetch_sport_markets("tennis", SPORT_SERIES["tennis"], date_str=date_str)


def fetch_ncaab_markets(date_str=None):
    """Fetch NCAAB (Men's College Basketball) markets from Kalshi."""
    return _fetch_sport_markets(
        "ncaab", SPORT_SERIES["ncaab"],
        limit=SPORT_LIMITS.get("ncaab", 200),
        date_str=date_str
    )


def fetch_wncaab_markets(date_str=None):
    """Fetch WNCAAB (Women's College Basketball) markets from Kalshi."""
    return _fetch_sport_markets(
        "wncaab", SPORT_SERIES["wncaab"],
        limit=SPORT_LIMITS.get("wncaab", 200),
        date_str=date_str
    )


def fetch_mlb_markets(date_str=None):
    """Fetch MLB markets from Kalshi."""
    return _fetch_sport_markets("mlb", SPORT_SERIES["mlb"], date_str=date_str)


def fetch_nfl_markets(date_str=None):
    """Fetch NFL markets from Kalshi."""
    return _fetch_sport_markets("nfl", SPORT_SERIES["nfl"], date_str=date_str)
