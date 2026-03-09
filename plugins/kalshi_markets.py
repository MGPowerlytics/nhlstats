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
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from base_games import UnifiedGameInfo

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
    from plugins.db_manager import DBManager, default_db
except ImportError:
    logger.warning("⚠️  db_manager not available - database operations disabled")
    DBManager = None
    default_db = None


@dataclass
class GameParseData:
    """Data structure for parsed game information from Kalshi markets."""

    sport: str
    home_team: str
    away_team: str
    game_date: str
    ticker: str = ""
    title: str = ""

    @property
    def has_teams(self) -> bool:
        """Check if both team names are present."""
        return bool(self.home_team and self.away_team)

    @property
    def has_date(self) -> bool:
        """Check if game date is present."""
        return bool(self.game_date)


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
            raise ImportError(
                "kalshi_python package not installed. Run: pip install kalshi-python"
            )

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
            market_count = len(result.get("markets", []))
            logger.info(
                f"✓ Fetched {market_count} markets from {series_ticker or 'all'}"
            )
            return result
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                logger.warning(
                    f"⚠️  Rate limited by Kalshi API for {series_ticker}: {e}"
                )
            elif "401" in error_msg or "403" in error_msg:
                logger.error(f"✗ Authentication failed for Kalshi API: {e}")
            else:
                logger.error(f"✗ Failed to get markets from {series_ticker}: {e}")
            return None


class TickerParser(ABC):
    """Abstract base for parsing Kalshi tickers into (home_team, away_team, game_date)."""

    @abstractmethod
    def parse(self, ticker: str, title: str) -> Optional[Tuple[str, str, str]]:
        """Return (home_team, away_team, game_date) or None if parsing fails."""
        pass


class StandardTickerParser(TickerParser):
    """Parses standard sport tickers (NBA, NHL, MLB, NFL, EPL, Ligue1, NCAAB, WNCAAB)."""

    # Ticker part indices
    DATE_PART_IDX = 1
    TEAMS_PART_IDX = 2
    TEAM_CODE_LENGTH = 3
    TOTAL_TEAM_CHARS = 6

    def parse(self, ticker: str, title: str) -> Optional[Tuple[str, str, str]]:
        parts = ticker.split("-")
        if len(parts) < 3:
            return None

        # Attempt 1: Old numeric date format (YYMMDD)
        date_part = parts[self.DATE_PART_IDX]
        teams_part = parts[self.TEAMS_PART_IDX]

        game_date = self._parse_numeric_date(date_part)
        if game_date and len(teams_part) == self.TOTAL_TEAM_CHARS:
            away_team = teams_part[: self.TEAM_CODE_LENGTH]
            home_team = teams_part[self.TEAM_CODE_LENGTH :]
            return home_team, away_team, game_date

        # Attempt 2: New alphanumeric date format (YYMMMDDTEAMS)
        if len(parts) >= 2:
            middle = parts[self.DATE_PART_IDX]
            match = re.match(r"^(\d{2})([A-Z]{3})(\d{2})([A-Z]+)$", middle)
            if match:
                y_str, m_str, d_str, teams_str = match.groups()
                try:
                    dt = datetime.strptime(f"{y_str}{m_str}{d_str}", "%y%b%d")
                    game_date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    return None

                if len(teams_str) == self.TOTAL_TEAM_CHARS:
                    away_team = teams_str[: self.TEAM_CODE_LENGTH]
                    home_team = teams_str[self.TEAM_CODE_LENGTH :]
                    return home_team, away_team, game_date

        # Fallback: try to extract teams from title
        if " vs " in title:
            # Simple fallback – caller may handle further resolution
            return None

        return None

    @staticmethod
    def _parse_numeric_date(date_part: str) -> Optional[str]:
        """Parse YYMMDD numeric date string to YYYY-MM-DD."""
        if len(date_part) == 6 and date_part.isdigit():
            try:
                year = 2000 + int(date_part[0:2])
                month = int(date_part[2:4])
                day = int(date_part[4:6])
                return f"{year}-{month:02d}-{day:02d}"
            except ValueError:
                pass
        return None


class TennisTickerParser(TickerParser):
    """Parses tennis tickers (ATP, WTA, Challenger)."""

    # Regex for extracting player names from title
    PLAYER_REGEXES = [
        r"win the (.*?) vs (.*?) (?:match|:)",
        r"win the (.*?) vs (.*?) match",
    ]

    def parse(self, ticker: str, title: str) -> Optional[Tuple[str, str, str]]:
        # Extract date from ticker (format: SERIES-YYMMMDD???-OUTCOME)
        parts = ticker.split("-")
        game_date = None
        if len(parts) >= 2:
            middle = parts[1]
            match = re.match(r"^(\d{2})([A-Z]{3})(\d{2})", middle)
            if match:
                y_str, m_str, d_str = match.groups()
                try:
                    dt = datetime.strptime(f"{y_str}{m_str}{d_str}", "%y%b%d")
                    game_date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    pass

        # Extract player names from title
        home_team = away_team = None
        for pattern in self.PLAYER_REGEXES:
            match = re.search(pattern, title)
            if match:
                home_team = match.group(1).strip()
                away_team = match.group(2).strip()
                if away_team.endswith(" match"):
                    away_team = away_team[:-6].strip()
                break

        if not home_team or not away_team:
            return None

        return home_team, away_team, game_date


def _get_parser(sport: str) -> TickerParser:
    """Return appropriate parser for the given sport."""
    if sport.lower() == "tennis":
        return TennisTickerParser()
    return StandardTickerParser()


def _parse_market(ticker: str, title: str, sport: str) -> Optional[GameParseData]:
    """Parse ticker and title into home_team, away_team, game_date."""
    parser = _get_parser(sport)
    result = parser.parse(ticker, title)
    if not result:
        return None
    home_team, away_team, game_date = result
    return GameParseData(
        sport=sport,
        home_team=home_team,
        away_team=away_team,
        game_date=game_date,
        ticker=ticker,
        title=title,
    )


def _resolve_names(game_data: GameParseData) -> Tuple[str, str]:
    """Resolve canonical team/player names using NamingResolver."""
    from naming_resolver import NamingResolver, NamingContext

    canon_home = (
        NamingResolver.resolve(
            context=NamingContext(game_data.sport, "kalshi", game_data.home_team)
        )
        or game_data.home_team
    )
    canon_away = (
        NamingResolver.resolve(
            context=NamingContext(game_data.sport, "kalshi", game_data.away_team)
        )
        or game_data.away_team
    )
    return canon_home, canon_away


def _generate_game_id(sport, game_date, home_team, away_team):
    """
    Generates a consistent and unique game_id.
    Format: SPORT_YYYYMMDD_HOME_AWAY (cleaned)
    """
    date_str = game_date.replace("-", "")
    home_slug = "".join(filter(str.isalnum, home_team)).upper()
    away_slug = "".join(filter(str.isalnum, away_team)).upper()
    return f"{sport.upper()}_{date_str}_{home_slug}_{away_slug}"


def _upsert_game(
    db_manager: DBManager,
    game: UnifiedGameInfo,
) -> str:
    """Upsert game into unified_games table and return game_id."""
    game_id = _generate_game_id(
        game.sport, game.game_date, game.canon_home, game.canon_away
    )
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
            "sport": game.sport.upper(),
            "game_date": game.game_date,
            "home_id": game.home_team,
            "home_name": game.canon_home,
            "away_id": game.away_team,
            "away_name": game.canon_away,
            "status": game.status,
        },
    )
    return game_id


def _upsert_odds(
    db_manager: DBManager,
    game_id: str,
    market: dict,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
    ticker: Optional[str] = None,
    game_data: Optional[GameParseData] = None,
) -> bool:
    """Upsert odds into game_odds table. Returns True if odds were inserted.

    Accepts either individual parameters (home_team, away_team, ticker) or a GameParseData object.
    GameParseData takes precedence if provided.
    """
    # Use game_data if provided, otherwise use individual parameters
    if game_data:
        home_team = game_data.home_team
        away_team = game_data.away_team
        ticker = game_data.ticker

    if not all([home_team, away_team, ticker]):
        logger.warning(
            f"Missing required parameters for _upsert_odds: home_team={home_team}, away_team={away_team}, ticker={ticker}"
        )
        return False

    parts = ticker.split("-")
    outcome_side = parts[-1] if len(parts) > 1 else None
    yes_price_cents = market.get("yes_ask", 0)

    if yes_price_cents <= 0 or not outcome_side:
        return False

    decimal_odds = 100.0 / yes_price_cents

    def _last_name_code(name: str) -> str:
        parts = name.split()
        return parts[-1][:3].upper() if parts else name[:3].upper()

    h_code = _last_name_code(home_team)
    a_code = _last_name_code(away_team)

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
    return True


def save_to_db(sport: str, markets: list, db_manager: DBManager = default_db):
    """
    Save Kalshi markets to the unified_games and game_odds tables in PostgreSQL.
    """
    if not markets:
        return 0

    odds_count = 0
    logger.info(
        f"💾 Saving {len(markets)} {sport.upper()} Kalshi markets to PostgreSQL..."
    )

    for market in markets:
        ticker = market.get("ticker", "")
        title = market.get("title", "")

        # Parse market
        game_data = _parse_market(ticker, title, sport)
        if not game_data:
            continue

        # If date missing, try to get it from close_time
        if not game_data.game_date:
            close_time = market.get("close_time")
            if close_time:
                if isinstance(close_time, str):
                    game_data.game_date = close_time.split("T")[0]
                else:
                    game_data.game_date = close_time.strftime("%Y-%m-%d")

        if not game_data.has_teams or not game_data.game_date:
            continue

        # Resolve canonical names
        canon_home, canon_away = _resolve_names(game_data)

        # Create game info object
        game_info = UnifiedGameInfo(
            sport=game_data.sport,
            game_date=game_data.game_date,
            home_team=game_data.home_team,
            away_team=game_data.away_team,
            canon_home=canon_home,
            canon_away=canon_away,
        )

        # Upsert game
        game_id = _upsert_game(db_manager, game_info)

        # Upsert odds using game_data object
        if _upsert_odds(db_manager, game_id, market, game_data=game_data):
            odds_count += 1

    return odds_count


def load_kalshi_credentials():
    """Load Kalshi credentials from standard files."""
    key_file = _get_kalshkey_path()
    if not key_file.exists():
        raise FileNotFoundError("Kalshi credentials file not found")

    content = key_file.read_text(encoding="utf-8")

    # 1. Extract API Key ID
    api_key_id = _extract_api_key_id(content)

    # 2. Extract Private Key
    private_key = _extract_private_key(content)

    if not api_key_id or not private_key:
        raise ValueError(
            "Could not find both API Key ID and Private Key in credentials"
        )

    return api_key_id, private_key


def _get_kalshkey_path() -> Path:
    """Determine the path to the kalshkey file."""
    paths = [
        Path("kalshkey"),
        Path("/opt/airflow/kalshkey"),
    ]
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def _extract_api_key_id(content: str) -> Optional[str]:
    """Extract API Key ID from the credentials content."""
    for line in content.splitlines():
        if "API key id:" in line:
            return line.split(": ")[1].strip()
    return None


def _extract_private_key(content: str) -> Optional[str]:
    """Extract Private Key from the credentials content or external file."""
    if "-----BEGIN RSA PRIVATE KEY-----" in content:
        # Key is embedded in the kalshkey file
        lines = content.splitlines()
        in_key = False
        key_lines = []
        for line in lines:
            if "-----BEGIN RSA PRIVATE KEY-----" in line:
                in_key = True
            if in_key:
                key_lines.append(line)
            if "-----END RSA PRIVATE KEY-----" in line:
                break
        return "\n".join(key_lines)

    # Look for external .pem file
    pem_paths = [
        Path("kalshi_private_key.pem"),
        Path("/opt/airflow/kalshi_private_key.pem"),
        Path(__file__).parent.parent / "kalshi_private_key.pem",
    ]

    for path in pem_paths:
        if path.exists():
            return path.read_text(encoding="utf-8")

    return None


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
    "unrivaled": ["KXUNRIVALED"],  # Unrivaled 3x3 women's basketball
    "cba": ["KXCBAGAME"],  # Chinese Basketball Association (placeholder for future)
}

# Sport-specific limits (NCAAB/WNCAAB have more games)
SPORT_LIMITS = {
    "ncaab": 1000,
    "wncaab": 1000,
}


def _init_kalshi_api(sport: str) -> Optional[KalshiAPI]:
    """Initialize Kalshi API with credentials."""
    try:
        api_key_id, private_key = load_kalshi_credentials()
        return KalshiAPI(api_key_id, private_key)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"✗ Cannot fetch {sport.upper()} markets: {e}")
    except Exception as e:
        logger.error(f"✗ Failed to initialize Kalshi API for {sport.upper()}: {e}")
    return None


def _fetch_all_markets(api: KalshiAPI, series_tickers: list, limit: int) -> list:
    """Fetch active markets for all provided series tickers."""
    all_markets = []
    for series_ticker in series_tickers:
        try:
            result = api.get_markets(series_ticker=series_ticker, limit=limit)
            if result and "markets" in result:
                markets = [
                    m
                    for m in result["markets"]
                    if m.get("status") in ["active", "initialized", "open"]
                ]
                all_markets.extend(markets)
                logger.info(f"  📊 {series_ticker}: {len(markets)} active markets")
        except Exception as e:
            logger.warning(f"  ⚠️  Failed to fetch {series_ticker}: {e}")
            continue
    return all_markets


def _save_and_log_markets(sport: str, all_markets: list) -> None:
    """Save fetched markets to DB and log the result."""
    if not all_markets:
        logger.info(f"ℹ️  {sport.upper()}: No active markets found")
        return

    try:
        saved = save_to_db(sport, all_markets)
        logger.info(
            f"✓ {sport.upper()}: Fetched {len(all_markets)} markets, saved {saved} odds"
        )
    except Exception as e:
        logger.error(f"✗ Failed to save {sport.upper()} markets to DB: {e}")


def _fetch_sport_markets(
    sport: str,
    series_tickers: Optional[list] = None,
    limit: Optional[int] = None,
    _date_str: str = None,  # kept for API compatibility, currently unused
) -> list:
    """
    Generic function to fetch markets for any sport with error handling.

    Args:
        sport: Sport code (e.g., 'nba', 'nhl', 'tennis')
        series_tickers: List of Kalshi series tickers to fetch (optional)
        limit: Max markets per series (optional)
        _date_str: Optional date string (currently unused, for API compatibility)

    Returns:
        List of market dictionaries, empty list on error
    """
    if not KALSHI_AVAILABLE:
        logger.error(
            f"✗ Cannot fetch {sport.upper()} markets: kalshi_python not installed"
        )
        return []

    # Use defaults if not provided
    if series_tickers is None:
        series_tickers = SPORT_SERIES.get(sport, [])
    if limit is None:
        limit = SPORT_LIMITS.get(sport, 200)

    api = _init_kalshi_api(sport)
    if not api:
        return []

    all_markets = _fetch_all_markets(api, series_tickers, limit)
    _save_and_log_markets(sport, all_markets)

    return all_markets


# Sport-specific fetch functions (unchanged signatures for Airflow compatibility)
def fetch_nba_markets(date_str=None):
    return _fetch_sport_markets("nba", _date_str=date_str)


def fetch_nhl_markets(date_str=None):
    return _fetch_sport_markets("nhl", _date_str=date_str)


def fetch_epl_markets(date_str=None):
    return _fetch_sport_markets("epl", _date_str=date_str)


def fetch_ligue1_markets(date_str=None):
    return _fetch_sport_markets("ligue1", _date_str=date_str)


def fetch_tennis_markets(date_str=None):
    return _fetch_sport_markets("tennis", _date_str=date_str)


def fetch_ncaab_markets(date_str=None):
    return _fetch_sport_markets("ncaab", _date_str=date_str)


def fetch_wncaab_markets(date_str=None):
    return _fetch_sport_markets("wncaab", _date_str=date_str)


def fetch_mlb_markets(date_str=None):
    return _fetch_sport_markets("mlb", _date_str=date_str)


def fetch_nfl_markets(date_str=None):
    return _fetch_sport_markets("nfl", _date_str=date_str)


def fetch_unrivaled_markets(date_str=None):
    return _fetch_sport_markets("unrivaled", _date_str=date_str)


def fetch_cba_markets(date_str=None):
    return _fetch_sport_markets("cba", _date_str=date_str)
