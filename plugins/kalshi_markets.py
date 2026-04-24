#!/usr/bin/env python3
"""
Fetch Kalshi markets for NHL/NBA games using official SDK.

Provides market fetching functions for all sports with:
- Proper error handling (graceful degradation on failures)
- Rate limiting (0.5s delay between API calls)
- Structured logging for Airflow visibility
- Import error handling for missing kalshi_python package
"""

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple, Union, List, Dict

import sqlalchemy
from sqlalchemy import text

from plugins.base_games import UnifiedGameInfo
from plugins.the_odds_api import TheOddsAPI

try:
    from plugins.kalshi_betting import load_runtime_kalshi_env
except ImportError:  # pragma: no cover - test path injection imports top-level module
    from kalshi_betting import load_runtime_kalshi_env

# Configure module logger
logger = logging.getLogger(__name__)

try:
    from kalshi_python import Configuration, ApiClient, MarketsApi

    KALSHI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in environments without SDK
    Configuration = ApiClient = MarketsApi = None
    KALSHI_AVAILABLE = False

from plugins.db_manager import DBManager, default_db


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

    def __init__(self, api_key_id: str, private_key_pem: str) -> None:
        """Initialize Kalshi API client.

        Args:
            api_key_id: Kalshi API key ID
            private_key_pem: PEM-encoded private key for authentication
        """
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
        self,
        event_ticker: Optional[str] = None,
        series_ticker: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> Optional[dict]:
        """Get markets from Kalshi with rate limiting and error handling.

        Args:
            event_ticker: Optional event ticker filter
            series_ticker: Optional series ticker filter (e.g., 'KXNBAGAME')
            status: Market status filter. Valid Kalshi API values vary by version.
                If None, fetches all statuses and filters client-side.
            limit: Maximum number of markets to return

        Returns:
            dict with 'markets' key containing list of markets, or None on error
        """
        _rate_limit()  # Enforce rate limiting

        try:
            logger.debug(f"Fetching markets: series={series_ticker}, limit={limit}")
            kwargs = {
                "series_ticker": series_ticker,
                "limit": limit,
            }
            if event_ticker:
                kwargs["event_ticker"] = event_ticker
            if status:
                kwargs["status"] = status
            response = self.markets_api.get_markets(**kwargs)
            result = response.to_dict()
            market_count = len(result.get("markets", []))
            logger.info(
                f"✓ Fetched {market_count} markets from {series_ticker or 'all'}"
            )
            return result
        except Exception as e:
            error_msg = str(e)
            # Handle SDK Pydantic validation errors (e.g., unknown status values
            # like 'finalized') by falling back to raw HTTP request
            if "validation error" in error_msg.lower():
                logger.warning(
                    f"⚠️  SDK validation error for {series_ticker}, "
                    f"falling back to raw HTTP request"
                )
                return self._get_markets_raw(series_ticker, limit)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                logger.warning(
                    f"⚠️  Rate limited by Kalshi API for {series_ticker}: {e}"
                )
            elif "401" in error_msg or "403" in error_msg:
                logger.error(f"✗ Authentication failed for Kalshi API: {e}")
            else:
                logger.error(f"✗ Failed to get markets from {series_ticker}: {e}")
            return None

    def _get_markets_raw(
        self, series_ticker: Optional[str], limit: int
    ) -> Optional[dict]:
        """Fetch markets via raw HTTP when SDK deserialization fails.

        Args:
            series_ticker: Series ticker filter
            limit: Maximum number of markets

        Returns:
            dict with 'markets' key, or None on error
        """
        import requests

        try:
            base_url = self.api_client.configuration.host
            url = f"{base_url}/markets"
            params = {"limit": limit}
            if series_ticker:
                params["series_ticker"] = series_ticker

            headers = dict(self.api_client.default_headers)
            headers["Accept"] = "application/json"

            resp = requests.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            market_count = len(data.get("markets", []))
            logger.info(
                f"✓ Fetched {market_count} markets from {series_ticker or 'all'} "
                f"(raw HTTP fallback)"
            )
            return data
        except Exception as e:
            logger.error(f"✗ Raw HTTP fallback also failed for {series_ticker}: {e}")
            return None

    def get_market(self, ticker: str) -> Optional[dict]:
        """Get detailed market information including prices.

        The Kalshi SDK v2.1.0 model does not map dollar-denominated price
        fields (yes_ask_dollars, last_price_dollars, etc.) returned by the
        API, so we parse the raw JSON response directly.

        Args:
            ticker: Market ticker (e.g., 'KXNBAGAME-26MAR22MINBOS-MIN')

        Returns:
            dict with detailed market information including prices, or None on error
        """
        _rate_limit()  # Enforce rate limiting

        try:
            logger.debug(f"Fetching market details: {ticker}")
            response = self.markets_api.get_market_with_http_info(ticker=ticker)
            raw = json.loads(response.raw_data)
            market_data = raw.get("market", {})

            # Convert dollar-string prices to cent-integer prices for backward
            # compatibility with the rest of the codebase.
            self._convert_dollar_prices(market_data)

            # Log market data structure once
            if not hasattr(self, "_logged_market_data"):
                logger.info(f"Sample Market Data for {ticker}: {market_data}")
                self._logged_market_data = True

            # Also try order book as supplementary price source
            self._add_order_book_data(ticker, market_data)

            logger.info(f"✓ Fetched market details for {ticker}")
            return market_data
        except Exception as e:
            self._handle_market_error(ticker, e)
            return None

    @staticmethod
    def _convert_dollar_prices(market_data: dict) -> None:
        """Convert dollar-string price fields to cents (int).

        The Kalshi v2 API returns prices as dollar strings
        (e.g., ``"0.5900"``).  The rest of the codebase expects
        cent-integer values (e.g., ``59``).

        Mutates *market_data* in-place.
        """
        DOLLAR_TO_CENTS = {
            "yes_ask_dollars": "yes_ask",
            "yes_bid_dollars": "yes_bid",
            "no_ask_dollars": "no_ask",
            "no_bid_dollars": "no_bid",
            "last_price_dollars": "last_price",
            "previous_price_dollars": "previous_price",
            "previous_yes_ask_dollars": "previous_yes_ask",
            "previous_yes_bid_dollars": "previous_yes_bid",
        }
        for dollar_key, cents_key in DOLLAR_TO_CENTS.items():
            value = market_data.get(dollar_key)
            if value is not None:
                try:
                    market_data[cents_key] = int(round(float(value) * 100))
                except (ValueError, TypeError):
                    pass

    def _add_order_book_data(self, ticker: str, market_data: dict) -> None:
        """Fetch and add order book data to market data.

        The Kalshi v2 API returns order book data under ``orderbook_fp``
        with ``yes_dollars`` / ``no_dollars`` arrays.  The SDK model
        does not map these, so we parse the raw JSON.

        Only overwrites ``yes_ask`` if it is not already present
        (i.e., the market endpoint already provided it).

        Args:
            ticker: Market ticker
            market_data: Dictionary to add order book data to
        """
        # Skip if we already have a price from the market endpoint
        if market_data.get("yes_ask", 0) > 0:
            return

        try:
            response = self.markets_api.get_market_orderbook_with_http_info(
                ticker=ticker
            )
            raw = json.loads(response.raw_data)

            orderbook = raw.get("orderbook_fp") or raw.get("orderbook") or {}

            # yes_dollars is a list of [price_str, qty_str] sorted ascending
            yes_levels = orderbook.get("yes_dollars") or orderbook.get("yes") or []
            no_levels = orderbook.get("no_dollars") or orderbook.get("no") or []

            # Best yes ask = highest yes bid price (last element)
            if yes_levels:
                best_yes_price = float(yes_levels[-1][0])
                market_data["yes_ask"] = int(round(best_yes_price * 100))

            if no_levels:
                best_no_price = float(no_levels[-1][0])
                market_data["no_ask"] = int(round(best_no_price * 100))

        except Exception as e:
            logger.warning(f"⚠️  Could not get order book for {ticker}: {e}")

    def _handle_market_error(self, ticker: str, error: Exception) -> None:
        """Handle errors from market API calls.

        Args:
            ticker: Market ticker that failed
            error: Exception that was raised
        """
        error_msg = str(error)
        if "429" in error_msg or "Too Many Requests" in error_msg:
            logger.warning(f"⚠️  Rate limited by Kalshi API for {ticker}: {error}")
        elif "401" in error_msg or "403" in error_msg:
            logger.error(f"✗ Authentication failed for Kalshi API: {error}")
        else:
            logger.error(f"✗ Failed to get market {ticker}: {error}")


class TickerParser(ABC):
    """Abstract base for parsing Kalshi tickers into (home_team, away_team, game_date)."""

    @abstractmethod
    def parse(self, ticker: str, title: str) -> Optional[Tuple[str, str, str]]:
        """Return (home_team, away_team, game_date) or None if parsing fails."""
        pass


EPL_GAME_ID_TEAM_CODES = {
    "arsenal": "ARS",
    "aston villa": "AVL",
    "bournemouth": "BOU",
    "brentford": "BRE",
    "brighton": "BHA",
    "burnley": "BUR",
    "chelsea": "CHE",
    "crystal palace": "CRY",
    "everton": "EVE",
    "fulham": "FUL",
    "ipswich": "IPS",
    "ipswich town": "IPS",
    "leeds": "LEE",
    "leeds united": "LEE",
    "leicester": "LEI",
    "leicester city": "LEI",
    "liverpool": "LIV",
    "luton": "LUT",
    "luton town": "LUT",
    "man city": "MCI",
    "manchester city": "MCI",
    "man united": "MUN",
    "manchester united": "MUN",
    "newcastle": "NEW",
    "newcastle united": "NEW",
    "nott'm forest": "NFO",
    "nottingham forest": "NFO",
    "norwich": "NOR",
    "norwich city": "NOR",
    "sheffield united": "SHU",
    "sheffield utd": "SHU",
    "southampton": "SOU",
    "sunderland": "SUN",
    "tottenham": "TOT",
    "tottenham hotspur": "TOT",
    "watford": "WAT",
    "west ham": "WHU",
    "west ham united": "WHU",
    "wolves": "WOL",
    "wolverhampton": "WOL",
    "wolverhampton wanderers": "WOL",
}
EPL_DRAW_OUTCOMES = {"DRAW", "TIE"}
EPL_SIDE_OUTCOMES = {"HOME", "AWAY"}


def _normalize_epl_date_token(date_token: str) -> Optional[str]:
    """Return YYYYMMDD for supported EPL ticker date shapes."""
    if re.fullmatch(r"\d{8}", date_token):
        return date_token
    if re.fullmatch(r"\d{6}", date_token):
        parsed = StandardTickerParser._parse_numeric_date(date_token)
        return parsed.replace("-", "") if parsed else None
    return None


def _extract_epl_ticker_metadata(ticker: str) -> Optional[Tuple[str, str, str]]:
    """Extract compact teams token, YYYYMMDD date, and outcome token from an EPL ticker."""
    parts = ticker.split("-")
    if len(parts) < 4:
        return None

    prefix = parts[0].upper()
    if prefix == "KXHEPL":
        teams_token = parts[1].upper()
        date_token = _normalize_epl_date_token(parts[2])
    elif prefix == "KXEPLGAME":
        teams_token = parts[2].upper()
        date_token = _normalize_epl_date_token(parts[1])
    else:
        return None

    if not date_token or not re.fullmatch(r"[A-Z]{6}", teams_token):
        return None

    return teams_token, date_token, parts[-1].upper()


def _normalize_epl_outcome_token(outcome_token: str, teams_token: str) -> str:
    """Normalize EPL outcome token into HOME/AWAY/DRAW/TIE."""
    outcome = outcome_token.upper()
    if outcome in EPL_DRAW_OUTCOMES or outcome in EPL_SIDE_OUTCOMES:
        return outcome
    if outcome == teams_token[:3]:
        return "HOME"
    if outcome == teams_token[3:]:
        return "AWAY"
    return outcome


def _normalize_epl_market_identity(market: dict) -> dict:
    """Mutate an EPL market into the canonical contract ticker shape when possible."""
    ticker = market.get("ticker")
    if not ticker:
        return market

    metadata = _extract_epl_ticker_metadata(ticker)
    if not metadata:
        return market

    teams_token, date_token, outcome_token = metadata
    canonical_ticker = (
        f"KXHEPL-{teams_token}-{date_token}-"
        f"{_normalize_epl_outcome_token(outcome_token, teams_token)}"
    )
    market["ticker"] = canonical_ticker
    market["market_id"] = canonical_ticker
    return market


class EPLTickerParser(TickerParser):
    """Parse EPL Kalshi tickers using EPL-specific title and contract rules."""

    @staticmethod
    def _parse_title_matchup(title: str) -> Optional[Tuple[str, str]]:
        cleaned_title = StandardTickerParser._strip_title_market_suffix(title)

        at_match = re.match(
            r"^\s*(.*?)\s+at\s+(.*?)\s*$", cleaned_title, flags=re.IGNORECASE
        )
        if at_match:
            away_team, home_team = at_match.groups()
            return home_team.strip(), away_team.strip()

        vs_match = re.match(
            r"^\s*(.*?)\s+vs\.?\s+(.*?)\s*$", cleaned_title, flags=re.IGNORECASE
        )
        if vs_match:
            home_team, away_team = vs_match.groups()
            return home_team.strip(), away_team.strip()

        return None

    def parse(self, ticker: str, title: str) -> Optional[Tuple[str, str, str]]:
        metadata = _extract_epl_ticker_metadata(ticker)
        if not metadata:
            return None

        _, date_token, _ = metadata
        try:
            game_date = datetime.strptime(date_token, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            return None

        title_matchup = self._parse_title_matchup(title)
        if not title_matchup:
            return None

        return title_matchup[0], title_matchup[1], game_date


class StandardTickerParser(TickerParser):
    """Parses standard sport tickers (NBA, NHL, MLB, NFL, EPL, Ligue1, NCAAB, WNCAAB)."""

    # Ticker part indices and validation constants
    MIN_TICKER_PARTS = 3  # Minimum parts needed for valid ticker: sport-date-teams
    DATE_PART_IDX = 1
    TEAMS_PART_IDX = 2
    TEAM_CODE_LENGTH = 3
    TOTAL_TEAM_CHARS = 6
    MLB_COMPACT_TEAM_CHARS = 5

    def __init__(self, sport: str) -> None:
        self.sport = sport.lower()

    def parse(self, ticker: str, title: str) -> Optional[Tuple[str, str, str]]:
        parts = ticker.split("-")
        if len(parts) < self.MIN_TICKER_PARTS:
            return None

        # Attempt 1: Old numeric date format (YYMMDD)
        date_part = parts[self.DATE_PART_IDX]
        teams_part = parts[self.TEAMS_PART_IDX]

        game_date = self._parse_numeric_date(date_part)
        if game_date:
            parsed_teams = self._parse_teams(teams_part, title)
            if parsed_teams:
                home_team, away_team = parsed_teams
                return home_team, away_team, game_date

        # Attempt 2: New alphanumeric date format (YYMMMDDTEAMS or YYMMMDDHHMMTEAMS)
        if len(parts) >= 2:
            middle = parts[self.DATE_PART_IDX]
            match = re.match(r"^(\d{2})([A-Z]{3})(\d{2})(\d{2,4})?([A-Z]+)$", middle)
            if match:
                y_str, m_str, d_str, _time_str, teams_str = match.groups()
                try:
                    dt = datetime.strptime(f"{y_str}{m_str}{d_str}", "%y%b%d")
                    game_date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    return None

                parsed_teams = self._parse_teams(teams_str, title)
                if parsed_teams:
                    home_team, away_team = parsed_teams
                    return home_team, away_team, game_date

        # Fallback: try to extract teams from title
        if " vs " in title:
            # Simple fallback – caller may handle further resolution
            return None

        return None

    def _parse_teams(self, teams_str: str, title: str) -> Optional[Tuple[str, str]]:
        if self.sport != "mlb":
            if len(teams_str) != self.TOTAL_TEAM_CHARS:
                return None
            away_team = teams_str[: self.TEAM_CODE_LENGTH]
            home_team = teams_str[self.TEAM_CODE_LENGTH :]
            return home_team, away_team

        return self._parse_mlb_teams(teams_str, title)

    def _parse_mlb_teams(self, teams_str: str, title: str) -> Optional[Tuple[str, str]]:
        if len(teams_str) == self.TOTAL_TEAM_CHARS:
            away_team = teams_str[: self.TEAM_CODE_LENGTH]
            home_team = teams_str[self.TEAM_CODE_LENGTH :]
            return home_team, away_team

        if len(teams_str) != self.MLB_COMPACT_TEAM_CHARS:
            return None

        title_matchup = self._parse_title_matchup(title)
        if not title_matchup:
            return None

        candidate_splits = ((2, 3), (3, 2))
        matching_candidates = []
        for away_len, home_len in candidate_splits:
            away_code = teams_str[:away_len]
            home_code = teams_str[away_len : away_len + home_len]
            if self._mlb_candidate_matches_title(
                away_code,
                home_code,
                title_matchup["away"],
                title_matchup["home"],
            ):
                matching_candidates.append(
                    (
                        self._resolve_mlb_team_code(home_code),
                        self._resolve_mlb_team_code(away_code),
                    )
                )

        if len(matching_candidates) == 1:
            return matching_candidates[0]

        return None

    @staticmethod
    def _resolve_mlb_team_code(team_code: str) -> str:
        from plugins.naming_resolver import NamingResolver, NamingContext

        return NamingResolver.resolve(NamingContext("mlb", "kalshi", team_code.upper()))

    @staticmethod
    def _parse_title_matchup(title: str) -> Optional[Dict[str, str]]:
        cleaned_title = StandardTickerParser._strip_title_market_suffix(title)

        explicit_match = re.match(
            r"^\s*(.*?)\s+at\s+(.*?)\s*$", cleaned_title, flags=re.IGNORECASE
        )
        if explicit_match:
            away_team, home_team = explicit_match.groups()
            return {"away": away_team.strip(), "home": home_team.strip()}

        vs_match = re.match(
            r"^\s*(.*?)\s+vs\.?\s+(.*?)\s*$", cleaned_title, flags=re.IGNORECASE
        )
        if vs_match:
            away_team, home_team = vs_match.groups()
            return {"away": away_team.strip(), "home": home_team.strip()}

        return None

    def _mlb_candidate_matches_title(
        self,
        away_code: str,
        home_code: str,
        title_away: str,
        title_home: str,
    ) -> bool:
        return self._code_matches_mlb_title_team(away_code, title_away) and (
            self._code_matches_mlb_title_team(home_code, title_home)
        )

    def _code_matches_mlb_title_team(self, team_code: str, title_team: str) -> bool:
        from plugins.naming_resolver import NamingResolver, NamingContext

        resolved_name = NamingResolver.resolve(
            NamingContext("mlb", "kalshi", team_code.upper())
        )
        normalized_title = self._normalize_team_text(title_team)
        normalized_resolved = self._normalize_team_text(resolved_name)

        if normalized_resolved == normalized_title:
            return True

        return team_code.upper() in self._derive_title_team_codes(title_team)

    @staticmethod
    def _derive_title_team_codes(title_team: str) -> set[str]:
        cleaned_title = StandardTickerParser._strip_title_market_suffix(title_team)
        normalized_title = StandardTickerParser._normalize_team_text(cleaned_title)
        overrides = {
            "ARIZONA": {"AZ", "ARI"},
            "ARIZONADIAMONDBACKS": {"AZ", "ARI"},
        }

        words = re.findall(r"[A-Za-z]+", cleaned_title)
        if not words:
            return overrides.get(normalized_title, set())

        codes = set(overrides.get(normalized_title, set()))
        codes.update(StandardTickerParser._derive_single_word_title_codes(words))
        codes.update(StandardTickerParser._derive_multi_word_title_codes(words))
        return {code for code in codes if code}

    @staticmethod
    def _derive_single_word_title_codes(words: List[str]) -> set[str]:
        if len(words) != 1:
            return set()

        word = words[0].upper()
        return {word[:2], word[:3]}

    @staticmethod
    def _derive_multi_word_title_codes(words: List[str]) -> set[str]:
        if len(words) < 2:
            return set()

        location_words = [word.upper() for word in words[:-1]]
        location_compact = "".join(location_words)
        codes = {
            "".join(word[0] for word in location_words),
            location_words[0][:2],
            location_words[0][:3],
            location_compact[:2],
            location_compact[:3],
            StandardTickerParser._title_word_initialism(words),
        }
        return codes

    @staticmethod
    def _title_word_initialism(words: List[str]) -> str:
        initials = []
        for word in words:
            if len(word) <= 3 and word.isalpha() and word.isupper():
                initials.append(word.upper())
            else:
                initials.append(word[0].upper())
        return "".join(initials)

    @staticmethod
    def _strip_title_market_suffix(title: str) -> str:
        return re.sub(r"\s+winner\?\s*$", "", title, flags=re.IGNORECASE).strip()

    @staticmethod
    def _normalize_team_text(team_name: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", team_name.upper())

    @staticmethod
    def _parse_numeric_date(date_part: str) -> Optional[str]:
        """Parse YYMMDD numeric date string to YYYY-MM-DD."""
        NUMERIC_DATE_LENGTH = 6  # YYMMDD format length
        CENTURY_OFFSET = 2000  # Offset for 2-digit years (2000s)
        YEAR_SLICE = slice(0, 2)  # YY in YYMMDD
        MONTH_SLICE = slice(2, 4)  # MM in YYMMDD
        DAY_SLICE = slice(4, 6)  # DD in YYMMDD

        if len(date_part) == NUMERIC_DATE_LENGTH and date_part.isdigit():
            try:
                year = CENTURY_OFFSET + int(date_part[YEAR_SLICE])
                month = int(date_part[MONTH_SLICE])
                day = int(date_part[DAY_SLICE])
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
    normalized_sport = sport.lower()
    if normalized_sport == "tennis":
        return TennisTickerParser()
    if normalized_sport == "epl":
        return EPLTickerParser()
    return StandardTickerParser(sport)


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
    from plugins.naming_resolver import NamingResolver, NamingContext

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


def _generate_game_id(
    sport_or_game: Union[str, GameParseData, UnifiedGameInfo],
    game_date: Optional[str] = None,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
) -> str:
    """
    Generates a consistent and unique game_id.
    Format: SPORT_YYYYMMDD_HOME_AWAY (cleaned)

    Accepts either:
    1. Primitive parameters: (sport: str, game_date: str, home_team: str, away_team: str)
    2. GameParseData object
    3. UnifiedGameInfo object

    For backward compatibility, supports both calling styles.
    """
    # Handle object parameter (GameParseData or UnifiedGameInfo)
    if isinstance(sport_or_game, (GameParseData, UnifiedGameInfo)):
        game = sport_or_game
        sport = game.sport
        game_date = game.game_date
        # Use canon_home/canon_away if available (UnifiedGameInfo), otherwise home_team/away_team
        if hasattr(game, "canon_home") and hasattr(game, "canon_away"):
            home_team = game.canon_home
            away_team = game.canon_away
        else:
            home_team = game.home_team
            away_team = game.away_team
    else:
        # Handle primitive parameters (backward compatibility)
        sport = sport_or_game
        # game_date, home_team, away_team are passed as separate parameters

    if game_date is None or home_team is None or away_team is None:
        raise ValueError("Missing required parameters for game ID generation")

    if sport.lower() == "epl":
        return (
            f"EPL-{game_date}-"
            f"{_epl_game_id_team_code(home_team)}-"
            f"{_epl_game_id_team_code(away_team)}"
        )

    date_str = game_date.replace("-", "")
    home_slug = "".join(filter(str.isalnum, home_team)).upper()
    away_slug = "".join(filter(str.isalnum, away_team)).upper()
    return f"{sport.upper()}_{date_str}_{home_slug}_{away_slug}"


def _epl_game_id_team_code(team_name: str) -> str:
    """Return the canonical three-letter team code used in EPL contract game IDs."""
    normalized_team_name = team_name.strip().lower()
    if normalized_team_name in EPL_GAME_ID_TEAM_CODES:
        return EPL_GAME_ID_TEAM_CODES[normalized_team_name]

    compact_name = re.sub(r"[^a-z]", "", normalized_team_name).upper()
    return compact_name[:3]


def _resolve_existing_mlb_game_id(
    db_manager: DBManager,
    game: UnifiedGameInfo,
) -> Optional[str]:
    """Return the canonical MLB native gamePk when schedule data already exists."""
    native_game_id = db_manager.fetch_scalar(
        """
        SELECT CAST(mg.game_id AS VARCHAR) AS game_id
        FROM mlb_games mg
        WHERE mg.game_date = :game_date
          AND mg.home_team = :home_team_name
          AND mg.away_team = :away_team_name
        LIMIT 1
    """,
        {
            "game_date": game.game_date,
            "home_team_name": game.canon_home,
            "away_team_name": game.canon_away,
        },
    )
    if native_game_id is not None:
        return str(native_game_id)

    fallback_game_id = db_manager.fetch_scalar(
        """
        SELECT ug.game_id
        FROM unified_games ug
        WHERE ug.sport = 'MLB'
          AND ug.game_date = :game_date
          AND ug.home_team_name = :home_team_name
          AND ug.away_team_name = :away_team_name
          AND SUBSTR(ug.game_id, 1, 4) <> 'MLB_'
        LIMIT 1
    """,
        {
            "game_date": game.game_date,
            "home_team_name": game.canon_home,
            "away_team_name": game.canon_away,
        },
    )
    return str(fallback_game_id) if fallback_game_id is not None else None


def _reconcile_mlb_game_identity(
    db_manager: DBManager,
    game: UnifiedGameInfo,
    canonical_game_id: str,
) -> None:
    """Move any synthetic MLB rows/odds onto the canonical native gamePk."""
    synthetic_game_id = _generate_game_id(game)
    if synthetic_game_id == canonical_game_id:
        return

    params = {
        "native_game_id": canonical_game_id,
        "synthetic_game_id": synthetic_game_id,
        "synthetic_odds_pattern": f"{synthetic_game_id}_%",
        "game_date": game.game_date,
        "home_team_name": game.canon_home,
        "away_team_name": game.canon_away,
        "status": game.status,
        "commence_time": game.commence_time,
    }
    native_unified_exists_sql = """
        SELECT 1
        FROM unified_games
        WHERE sport = 'MLB'
          AND game_id = :native_game_id
        LIMIT 1
    """
    ensure_native_unified_sql = """
        INSERT INTO unified_games (
            game_id, sport, game_date, season, status,
            home_team_id, home_team_name, away_team_id, away_team_name,
            home_score, away_score, commence_time, venue
        )
        SELECT
            CAST(mg.game_id AS VARCHAR) AS game_id,
            'MLB' AS sport,
            mg.game_date,
            mg.season,
            COALESCE(NULLIF(mg.status, ''), synthetic.status, :status) AS status,
            synthetic.home_team_id,
            COALESCE(mg.home_team, synthetic.home_team_name, :home_team_name),
            synthetic.away_team_id,
            COALESCE(mg.away_team, synthetic.away_team_name, :away_team_name),
            mg.home_score,
            mg.away_score,
            COALESCE(synthetic.commence_time, :commence_time),
            synthetic.venue
        FROM mlb_games mg
        LEFT JOIN unified_games synthetic
          ON synthetic.sport = 'MLB'
         AND synthetic.game_id = :synthetic_game_id
        WHERE CAST(mg.game_id AS VARCHAR) = :native_game_id
          AND mg.game_date = :game_date
          AND mg.home_team = :home_team_name
          AND mg.away_team = :away_team_name
        ON CONFLICT (game_id) DO UPDATE SET
            sport = EXCLUDED.sport,
            game_date = EXCLUDED.game_date,
            season = COALESCE(EXCLUDED.season, unified_games.season),
            status = COALESCE(EXCLUDED.status, unified_games.status),
            home_team_id = COALESCE(unified_games.home_team_id, EXCLUDED.home_team_id),
            home_team_name = COALESCE(unified_games.home_team_name, EXCLUDED.home_team_name),
            away_team_id = COALESCE(unified_games.away_team_id, EXCLUDED.away_team_id),
            away_team_name = COALESCE(unified_games.away_team_name, EXCLUDED.away_team_name),
            home_score = COALESCE(EXCLUDED.home_score, unified_games.home_score),
            away_score = COALESCE(EXCLUDED.away_score, unified_games.away_score),
            commence_time = COALESCE(EXCLUDED.commence_time, unified_games.commence_time),
            venue = COALESCE(EXCLUDED.venue, unified_games.venue)
    """
    statements = [
        """
        DELETE FROM game_odds
        WHERE odds_id LIKE :synthetic_odds_pattern
          AND EXISTS (
              SELECT 1
              FROM game_odds native
              WHERE native.odds_id = REPLACE(
                  game_odds.odds_id,
                  :synthetic_game_id,
                  :native_game_id
              )
          )
    """,
        """
        UPDATE game_odds
        SET game_id = :native_game_id,
            odds_id = REPLACE(odds_id, :synthetic_game_id, :native_game_id)
        WHERE odds_id LIKE :synthetic_odds_pattern
    """,
        """
        UPDATE game_odds
        SET game_id = :native_game_id
        WHERE game_id = :synthetic_game_id
    """,
        """
        INSERT INTO team_game_stats (
            game_id, sport, team, opponent, is_home, game_date, season,
            points_for, points_against, won, off_rating, def_rating, pace, margin
        )
        SELECT
            :native_game_id,
            sport,
            team,
            opponent,
            is_home,
            game_date,
            season,
            points_for,
            points_against,
            won,
            off_rating,
            def_rating,
            pace,
            margin
        FROM team_game_stats
        WHERE sport = 'MLB'
          AND game_id = :synthetic_game_id
        ON CONFLICT (game_id, team) DO UPDATE SET
            sport = EXCLUDED.sport,
            opponent = EXCLUDED.opponent,
            is_home = EXCLUDED.is_home,
            game_date = EXCLUDED.game_date,
            season = EXCLUDED.season,
            points_for = EXCLUDED.points_for,
            points_against = EXCLUDED.points_against,
            won = EXCLUDED.won,
            off_rating = EXCLUDED.off_rating,
            def_rating = EXCLUDED.def_rating,
            pace = EXCLUDED.pace,
            margin = EXCLUDED.margin,
            updated_at = CURRENT_TIMESTAMP
    """,
        """
        INSERT INTO mlb_team_game_stats_ext (
            game_id, team, hits, errors, lob, doubles, triples, home_runs, rbi,
            stolen_bases, strikeouts, walks, at_bats, obp, slg, ops, woba, era
        )
        SELECT
            :native_game_id,
            team,
            hits,
            errors,
            lob,
            doubles,
            triples,
            home_runs,
            rbi,
            stolen_bases,
            strikeouts,
            walks,
            at_bats,
            obp,
            slg,
            ops,
            woba,
            era
        FROM mlb_team_game_stats_ext
        WHERE game_id = :synthetic_game_id
        ON CONFLICT (game_id, team) DO UPDATE SET
            hits = EXCLUDED.hits,
            errors = EXCLUDED.errors,
            lob = EXCLUDED.lob,
            doubles = EXCLUDED.doubles,
            triples = EXCLUDED.triples,
            home_runs = EXCLUDED.home_runs,
            rbi = EXCLUDED.rbi,
            stolen_bases = EXCLUDED.stolen_bases,
            strikeouts = EXCLUDED.strikeouts,
            walks = EXCLUDED.walks,
            at_bats = EXCLUDED.at_bats,
            obp = EXCLUDED.obp,
            slg = EXCLUDED.slg,
            ops = EXCLUDED.ops,
            woba = EXCLUDED.woba,
            era = EXCLUDED.era
    """,
        """
        DELETE FROM mlb_team_game_stats_ext
        WHERE game_id = :synthetic_game_id
    """,
        """
        DELETE FROM team_game_stats
        WHERE sport = 'MLB'
          AND game_id = :synthetic_game_id
    """,
        """
        DELETE FROM unified_games
        WHERE sport = 'MLB'
          AND game_id = :synthetic_game_id
          AND game_id <> :native_game_id
    """,
    ]

    engine = getattr(db_manager, "engine", None)
    if isinstance(engine, sqlalchemy.engine.Engine):
        with engine.begin() as conn:
            native_unified_exists = conn.execute(
                text(native_unified_exists_sql), params
            ).scalar()
            if native_unified_exists is None:
                conn.execute(text(ensure_native_unified_sql), params)
                native_unified_exists = conn.execute(
                    text(native_unified_exists_sql), params
                ).scalar()
            if native_unified_exists is None:
                logger.warning(
                    "Skipping destructive MLB identity migration for %s because "
                    "the native unified_games row could not be established safely.",
                    canonical_game_id,
                )
                return
            for statement in statements:
                conn.execute(text(statement), params)
        return

    native_unified_exists = db_manager.fetch_scalar(native_unified_exists_sql, params)
    if native_unified_exists is None:
        db_manager.execute(ensure_native_unified_sql, params)
        native_unified_exists = db_manager.fetch_scalar(
            native_unified_exists_sql, params
        )
    if native_unified_exists is None:
        logger.warning(
            "Skipping destructive MLB identity migration for %s because "
            "the native unified_games row could not be established safely.",
            canonical_game_id,
        )
        return
    for statement in statements:
        db_manager.execute(statement, params)


def _upsert_game(
    db_manager: DBManager,
    game: UnifiedGameInfo,
) -> str:
    """Upsert game into unified_games table and return game_id."""
    game_id = game.game_id or _generate_game_id(game)
    db_manager.execute(
        """
        INSERT INTO unified_games (
            game_id, sport, game_date, home_team_id, home_team_name,
            away_team_id, away_team_name, commence_time, status
        ) VALUES (:game_id, :sport, :game_date, :home_id, :home_name,
                 :away_id, :away_name, :commence_time, :status)
        ON CONFLICT (game_id) DO UPDATE SET
            home_team_id = COALESCE(unified_games.home_team_id, EXCLUDED.home_team_id),
            home_team_name = COALESCE(unified_games.home_team_name, EXCLUDED.home_team_name),
            away_team_id = COALESCE(unified_games.away_team_id, EXCLUDED.away_team_id),
            away_team_name = COALESCE(unified_games.away_team_name, EXCLUDED.away_team_name),
            commence_time = COALESCE(EXCLUDED.commence_time, unified_games.commence_time),
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
            "commence_time": game.commence_time,
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
    # Normalize parameters
    home_team, away_team, ticker = _normalize_odds_parameters(
        home_team, away_team, ticker, game_data
    )

    if not all([home_team, away_team, ticker]):
        logger.warning(
            f"Missing required parameters for _upsert_odds: home_team={home_team}, away_team={away_team}, ticker={ticker}"
        )
        return False

    # Extract outcome side and price from ticker and market
    outcome_side = _extract_outcome_side_from_ticker(ticker)
    yes_price_cents = market.get("yes_ask", 0)

    if not outcome_side:
        logger.warning(f"Could not extract side from {ticker}")
        return False

    decimal_odds = 0.0
    if yes_price_cents > 0:
        decimal_odds = _calculate_decimal_odds(yes_price_cents)
    else:
        logger.warning(
            f"Invalid price for {ticker}: {yes_price_cents}. Saving ticker only."
        )

    # Determine outcome name based on team codes
    outcome_name = _determine_outcome_name(outcome_side, home_team, away_team)

    # Insert or update odds in database
    return _upsert_odds_to_database(
        db_manager, game_id, outcome_name, decimal_odds, ticker
    )


def _normalize_odds_parameters(
    home_team: Optional[str],
    away_team: Optional[str],
    ticker: Optional[str],
    game_data: Optional[GameParseData],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Normalize odds parameters, preferring game_data if provided.

    Returns:
        Tuple of (home_team, away_team, ticker)
    """
    if game_data:
        return game_data.home_team, game_data.away_team, game_data.ticker
    return home_team, away_team, ticker


def _extract_outcome_side_from_ticker(ticker: str) -> Optional[str]:
    """Extract outcome side from ticker string.

    Args:
        ticker: Market ticker (e.g., 'KXNBAGAME-26MAR22MINBOS-MIN')

    Returns:
        Outcome side (e.g., 'MIN') or None if cannot extract
    """
    parts = ticker.split("-")
    return parts[-1] if len(parts) > 1 else None


def _calculate_decimal_odds(yes_price_cents: float) -> float:
    """Calculate decimal odds from yes price in cents.

    Args:
        yes_price_cents: Price in cents for 'yes' outcome

    Returns:
        Decimal odds
    """
    CENTS_PER_DOLLAR = 100.0  # Conversion factor: 100 cents = $1.00
    return round(CENTS_PER_DOLLAR / yes_price_cents, 10)


def _determine_outcome_name(outcome_side: str, home_team: str, away_team: str) -> str:
    """Determine outcome name (home/away) based on outcome side and team names.

    Args:
        outcome_side: Outcome side from ticker (e.g., 'MIN')
        home_team: Home team name
        away_team: Away team name

    Returns:
        'home' or 'away'
    """

    normalized_outcome_side = outcome_side.upper()
    if normalized_outcome_side in EPL_DRAW_OUTCOMES:
        return "draw"
    if normalized_outcome_side in EPL_SIDE_OUTCOMES:
        return normalized_outcome_side.lower()

    # MLB franchise-code aware resolution. Kalshi MLB tickers use franchise
    # codes (e.g. "SF", "LAD", "NYY") rather than 3-char last-name slugs, so
    # the legacy ``_last_name_code`` heuristic below misclassifies home-side
    # tickers like ``...-SF`` for ``San Francisco Giants``. Try resolving the
    # outcome side via NamingResolver under the MLB Kalshi context first; if
    # the resolved canonical matches one of the supplied team names, use it.
    # For non-MLB sports the resolver will not match, so behaviour is
    # preserved by falling through to the legacy logic.
    try:
        from plugins.naming_resolver import NamingContext, NamingResolver

        mlb_resolved = NamingResolver.resolve(
            NamingContext("mlb", "kalshi", normalized_outcome_side)
        )
        if mlb_resolved and mlb_resolved != normalized_outcome_side:
            if mlb_resolved == home_team:
                return "home"
            if mlb_resolved == away_team:
                return "away"
    except Exception:
        # Defensive: never let resolver errors break legacy classification.
        pass

    def _last_name_code(name: str) -> str:
        TEAM_CODE_LENGTH = 3  # Standard team code length (e.g., "LAL", "BOS")
        parts = name.split()
        return (
            parts[-1][:TEAM_CODE_LENGTH].upper()
            if parts
            else name[:TEAM_CODE_LENGTH].upper()
        )

    h_code = _last_name_code(home_team)
    a_code = _last_name_code(away_team)

    if normalized_outcome_side == h_code:
        return "home"
    elif normalized_outcome_side == a_code:
        return "away"
    else:
        return "home" if normalized_outcome_side == home_team.upper() else "away"


def _upsert_odds_to_database(
    db_manager: DBManager,
    game_id: str,
    outcome_name: str,
    decimal_odds: float,
    ticker: str,
) -> bool:
    """Insert or update odds in game_odds table.

    Args:
        db_manager: Database manager instance
        game_id: Game identifier
        outcome_name: 'home' or 'away'
        decimal_odds: Decimal odds
        ticker: Market ticker

    Returns:
        True if successful
    """
    odds_id = f"{game_id}_kalshi_{outcome_name}"
    db_manager.execute(
        """
        INSERT INTO game_odds (
            odds_id, game_id, bookmaker, market_name, outcome_name, price, is_pregame, external_id
        ) VALUES (:odds_id, :game_id, 'Kalshi', 'moneyline', :outcome_name, :price, True, :ticker)
        ON CONFLICT (odds_id) DO UPDATE SET
            price = EXCLUDED.price,
            external_id = EXCLUDED.external_id,
            last_update = CURRENT_TIMESTAMP
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


def _kalshi_tennis_full_name(market: dict) -> Optional[str]:
    """Extract full player name from a Kalshi tennis market.

    Kalshi tennis markets carry the YES-side player's full name in
    ``yes_sub_title`` (e.g., "Flavio Cobolli"). We fall back to parsing the
    title prefix ("Will <Full Name> win the …") if that field is absent.

    Args:
        market: Kalshi market dictionary

    Returns:
        Full player name or None if it cannot be determined
    """
    yes_sub = market.get("yes_sub_title")
    if isinstance(yes_sub, str) and yes_sub.strip():
        return yes_sub.strip()
    title = market.get("title", "") or ""
    match = re.search(r"Will\s+(.+?)\s+win\s+the\b", title)
    if match:
        return match.group(1).strip()
    return None


def _kalshi_tennis_event_key(market: dict) -> Optional[str]:
    """Return the matchup-level event ticker for a tennis market.

    Both YES-side markets for a single ATP/WTA match share the same
    ``event_ticker`` (e.g., ``KXATPMATCH-26APR07COBBLO``), which we use as
    the grouping key when consolidating into a unified game.
    """
    event_ticker = market.get("event_ticker")
    if isinstance(event_ticker, str) and event_ticker:
        return event_ticker
    ticker = market.get("ticker", "") or ""
    parts = ticker.rsplit("-", 1)
    return parts[0] if len(parts) == 2 else None


def _kalshi_tennis_tour(event_key: str) -> str:
    """Infer ATP vs WTA from the event ticker prefix."""
    upper = event_key.upper()
    if "WTA" in upper:
        return "WTA"
    return "ATP"


def _kalshi_tennis_game_date(market: dict, event_key: str) -> Optional[str]:
    """Determine the match date from event ticker (preferred) or close_time."""
    parts = event_key.split("-")
    if len(parts) >= 2:
        match = re.match(r"^(\d{2})([A-Z]{3})(\d{2})", parts[1])
        if match:
            try:
                dt = datetime.strptime("".join(match.groups()), "%y%b%d")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
    close_time = market.get("close_time")
    if isinstance(close_time, str) and close_time:
        return close_time.split("T")[0]
    if hasattr(close_time, "strftime"):
        return close_time.strftime("%Y-%m-%d")
    return None


def _save_tennis_kalshi_markets(markets: list, db_manager: DBManager) -> int:
    """Save Kalshi tennis markets into unified_games / game_odds.

    Tennis on Kalshi exposes one binary market per player ("Will <player> win
    the <X> vs <Y> match?"), so a single ATP/WTA matchup yields two markets
    that share an ``event_ticker``. We aggregate by event ticker, derive both
    full player names from each market's ``yes_sub_title``, and emit:

      * one ``unified_games`` row per matchup, with home/away assigned by
        alphabetical order of the players' full names (tennis has no real
        home/away — alphabetical sort gives a deterministic mapping);
      * one ``game_odds`` row per market, with ``outcome_name`` resolved by
        comparing the YES-side player to the alphabetic ordering.

    Args:
        markets: List of raw Kalshi market dictionaries
        db_manager: Database manager

    Returns:
        Number of odds rows written
    """
    # 1. Group markets by event ticker
    events: Dict[str, list] = {}
    for market in markets:
        event_key = _kalshi_tennis_event_key(market)
        if not event_key:
            logger.warning(
                f"Skipping tennis market without event_ticker: {market.get('ticker')}"
            )
            continue
        events.setdefault(event_key, []).append(market)

    odds_count = 0

    for event_key, event_markets in events.items():
        # 2. Resolve the full names for each YES side
        side_to_player: Dict[str, str] = {}
        for market in event_markets:
            ticker = market.get("ticker", "") or ""
            side_code = ticker.rsplit("-", 1)[-1].upper() if "-" in ticker else None
            full_name = _kalshi_tennis_full_name(market)
            if not side_code or not full_name:
                continue
            side_to_player[side_code] = full_name

        # 3. Need at least one player to proceed; if only one side is present
        # we fall back to extracting the opponent's last name from the title.
        if not side_to_player:
            logger.warning(
                f"Tennis event {event_key}: could not resolve any player names"
            )
            continue

        # Derive opponent last name (last 3 chars of event ticker matchup code
        # — e.g., COBBLO splits into COB and BLO) so we can hydrate the
        # opponent slot if we only have one market available.
        matchup_part = event_key.split("-")[1] if "-" in event_key else ""
        m = re.match(r"^\d{2}[A-Z]{3}\d{2}([A-Z]{6})$", matchup_part)
        side_codes = [m.group(1)[:3], m.group(1)[3:]] if m else list(side_to_player)

        for side_code in side_codes:
            if side_code in side_to_player:
                continue
            # Pull last name from the title's "<X> vs <Y>" segment.
            for market in event_markets:
                title = market.get("title", "") or ""
                vs_match = re.search(
                    r"win\s+the\s+(.+?)\s+vs\s+(.+?)\s*(?:[:\-]|match)", title
                )
                if not vs_match:
                    continue
                p1, p2 = vs_match.group(1).strip(), vs_match.group(2).strip()
                for candidate in (p1, p2):
                    code = candidate.split()[-1][:3].upper()
                    if code == side_code:
                        side_to_player[side_code] = candidate
                        break
                if side_code in side_to_player:
                    break

        if len(side_to_player) < 2:
            logger.warning(
                f"Tennis event {event_key}: only resolved {len(side_to_player)} player(s); "
                f"skipping unified game upsert"
            )
            continue

        # 4. Build the unified game (alphabetical order is the canonical
        # home/away mapping for sports without a real home side).
        ordered_sides = sorted(side_to_player.items(), key=lambda kv: kv[1].lower())
        home_side, home_name = ordered_sides[0]
        away_side, away_name = ordered_sides[1]

        game_date = _kalshi_tennis_game_date(event_markets[0], event_key)
        if not game_date:
            logger.warning(f"Tennis event {event_key}: missing game_date; skipping")
            continue

        # Tour goes into the game_id so odds_comparator can detect ATP vs WTA
        # even when the Kalshi ticker is unavailable downstream.
        tour = _kalshi_tennis_tour(event_key)
        game_id = (
            f"TENNIS_{tour}_{game_date}_"
            f"{re.sub(r'[^A-Za-z0-9]', '', home_name)}_"
            f"{re.sub(r'[^A-Za-z0-9]', '', away_name)}"
        )

        commence_time = event_markets[0].get("close_time")
        if hasattr(commence_time, "isoformat"):
            commence_time = commence_time.isoformat()

        game_info = UnifiedGameInfo(
            sport="tennis",
            game_date=game_date,
            home_team=home_name,
            away_team=away_name,
            canon_home=home_name,
            canon_away=away_name,
            commence_time=commence_time,
        )
        game_info.game_id = game_id
        _upsert_game(db_manager, game_info)

        # 5. Persist odds for each Kalshi market
        for market in event_markets:
            ticker = market.get("ticker", "") or ""
            side_code = ticker.rsplit("-", 1)[-1].upper() if "-" in ticker else None
            if side_code == home_side:
                outcome_name = "home"
            elif side_code == away_side:
                outcome_name = "away"
            else:
                logger.warning(
                    f"Tennis market {ticker} side '{side_code}' does not match "
                    f"resolved sides ({home_side}/{away_side}); skipping"
                )
                continue

            yes_price_cents = market.get("yes_ask", 0) or 0
            if yes_price_cents <= 0:
                logger.warning(
                    f"Tennis market {ticker}: invalid yes_ask {yes_price_cents}; skipping"
                )
                continue
            decimal_odds = _calculate_decimal_odds(yes_price_cents)

            if _upsert_odds_to_database(
                db_manager, game_id, outcome_name, decimal_odds, ticker
            ):
                odds_count += 1

    return odds_count


def save_to_db(sport: str, markets: list, db_manager: DBManager = default_db) -> int:
    """
    Save Kalshi markets to the unified_games and game_odds tables in PostgreSQL.

    Returns:
        Number of odds records saved
    """
    if not markets:
        return 0

    # Ensure database schema is initialized
    from plugins.database_schema_manager import DatabaseSchemaManager

    schema_manager = DatabaseSchemaManager(db_manager)
    schema_manager.initialize_schema()

    if sport.lower() == "tennis":
        # Kalshi tennis markets are one-sided binaries that aggregate by
        # event_ticker into a single matchup; use a dedicated save path.
        logger.info(f"💾 Saving {len(markets)} TENNIS Kalshi markets to PostgreSQL...")
        return _save_tennis_kalshi_markets(markets, db_manager)

    odds_count = 0
    logger.info(
        f"💾 Saving {len(markets)} {sport.upper()} Kalshi markets to PostgreSQL..."
    )

    for market in markets:
        if sport.lower() == "epl":
            market = _normalize_epl_market_identity(market)

        ticker = market.get("ticker", "")
        title = market.get("title", "")

        # Parse market
        game_data = _parse_market(ticker, title, sport)
        if not game_data:
            logger.warning(f"Failed to parse market: {ticker} ({title})")
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
            logger.warning(
                f"Missing teams/date for {ticker}: teams={game_data.has_teams}, date={game_data.game_date}"
            )
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

        if sport.lower() == "mlb":
            native_game_id = _resolve_existing_mlb_game_id(db_manager, game_info)
            if native_game_id:
                _reconcile_mlb_game_identity(db_manager, game_info, native_game_id)
                game_info.game_id = str(native_game_id)

        # Upsert game
        game_id = _upsert_game(db_manager, game_info)

        # Upsert odds using game_data object
        if _upsert_odds(db_manager, game_id, market, game_data=game_data):
            odds_count += 1
        else:
            logger.warning(f"Failed to upsert odds for {ticker}")

    return odds_count


def load_kalshi_credentials():
    """Load Kalshi credentials from the approved runtime environment."""
    api_key_id, private_key_path = load_runtime_kalshi_env()
    private_key = Path(private_key_path).read_text(encoding="utf-8")
    return api_key_id, private_key


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


def _filter_active_markets(result: dict) -> list:
    """Filter markets to only include active, initialized, or open ones.

    Args:
        result: API response containing markets list

    Returns:
        List of active markets
    """
    if not result or "markets" not in result:
        return []

    return [
        m
        for m in result["markets"]
        if m.get("status") in ["active", "initialized", "open"]
    ]


def _get_detailed_market(api: KalshiAPI, market: dict) -> dict:
    """Fetch detailed price data for a single market.

    Args:
        api: KalshiAPI instance
        market: Basic market data

    Returns:
        Market with detailed price data if available
    """
    ticker = market.get("ticker")
    if not ticker:
        return market

    try:
        detailed_market = api.get_market(ticker)
        if detailed_market:
            # Merge basic and detailed data
            market.update(detailed_market)
    except Exception as e:
        logger.warning(f"    ⚠️  Could not get details for {ticker}: {e}")

    return market


def _process_series_ticker(api: KalshiAPI, series_ticker: str, limit: int) -> list:
    """Fetch and process markets for a single series ticker.

    Args:
        api: KalshiAPI instance
        series_ticker: Series ticker to fetch
        limit: Maximum number of markets to fetch

    Returns:
        List of detailed markets for this series
    """
    try:
        result = api.get_markets(series_ticker=series_ticker, limit=limit)
        markets = _filter_active_markets(result)

        if not markets:
            return []

        # Get detailed market data with prices for each market
        detailed_markets = [_get_detailed_market(api, market) for market in markets]
        if series_ticker == "KXEPLGAME":
            detailed_markets = [
                _normalize_epl_market_identity(market) for market in detailed_markets
            ]

        logger.info(
            f"  📊 {series_ticker}: {len(detailed_markets)} active markets with price data"
        )
        return detailed_markets

    except Exception as e:
        logger.warning(f"  ⚠️  Failed to fetch {series_ticker}: {e}")
        return []


def _fetch_all_markets(api: KalshiAPI, series_tickers: list, limit: int) -> list:
    """Fetch active markets for all provided series tickers with detailed price data."""
    all_markets = []

    for series_ticker in series_tickers:
        detailed_markets = _process_series_ticker(api, series_ticker, limit)
        all_markets.extend(detailed_markets)

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
) -> list:
    """
    Generic function to fetch markets for any sport with error handling.

    Note: The Kalshi API only returns currently-active markets. There is no
    server-side date filter, so per-sport public wrappers accept ``date_str``
    only for Airflow callable-signature compatibility — the value is logged
    upstream but not threaded into the API call.

    Args:
        sport: Sport code (e.g., 'nba', 'nhl', 'tennis')
        series_tickers: List of Kalshi series tickers to fetch (optional)
        limit: Max markets per series (optional)

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
# Generated dynamically to eliminate code duplication while maintaining backward compatibility


def _create_sport_market_fetcher(
    sport: str, description: str
) -> Callable[[Optional[str]], list]:
    """Create a sport-specific market fetch function.

    Args:
        sport: Sport identifier (e.g., "nba", "nhl")
        description: Function docstring description

    Returns:
        Function that fetches markets for the specified sport. The returned
        function accepts ``date_str`` for Airflow signature compatibility but
        the value is unused — Kalshi only exposes currently-active markets.
    """

    def fetch_sport_markets(date_str: Optional[str] = None) -> list:
        """{description}"""
        return _fetch_sport_markets(sport)

    # Set function metadata
    fetch_sport_markets.__doc__ = description
    fetch_sport_markets.__name__ = f"fetch_{sport}_markets"
    return fetch_sport_markets


# Dynamically generate sport-specific market fetch functions
# This eliminates code duplication while maintaining backward compatibility
fetch_nba_markets = _create_sport_market_fetcher(
    "nba", "Fetch NBA markets from Kalshi."
)
fetch_nhl_markets = _create_sport_market_fetcher(
    "nhl", "Fetch NHL markets from Kalshi."
)
fetch_epl_markets = _create_sport_market_fetcher(
    "epl", "Fetch EPL (English Premier League) markets from Kalshi."
)
fetch_ligue1_markets = _create_sport_market_fetcher(
    "ligue1", "Fetch Ligue 1 (French football) markets from Kalshi."
)
fetch_ncaab_markets = _create_sport_market_fetcher(
    "ncaab", "Fetch NCAAB (men's college basketball) markets from Kalshi."
)
fetch_wncaab_markets = _create_sport_market_fetcher(
    "wncaab", "Fetch WNCAAB (women's college basketball) markets from Kalshi."
)
fetch_mlb_markets = _create_sport_market_fetcher(
    "mlb", "Fetch MLB (baseball) markets from Kalshi."
)
fetch_nfl_markets = _create_sport_market_fetcher(
    "nfl", "Fetch NFL (American football) markets from Kalshi."
)

# Manual implementations for sports using alternative sources or placeholders


def fetch_tennis_markets(date_str: Optional[str] = None) -> list:
    """Fetch tennis markets (ATP, WTA, Challenger) from Kalshi.

    Tennis on Kalshi is exposed as one binary market per player using the
    series tickers configured in :data:`SPORT_SERIES`. The shared
    :func:`_fetch_sport_markets` helper handles credentials, rate limiting,
    and persistence (which dispatches to :func:`_save_tennis_kalshi_markets`).
    """
    return _fetch_sport_markets("tennis")


def fetch_cba_markets(date_str: Optional[str] = None) -> list:
    """Fetch CBA (Chinese Basketball Association) markets from Kalshi."""
    return _fetch_sport_markets("cba")


def fetch_unrivaled_markets(date_str: Optional[str] = None) -> list:
    """Fetch Unrivaled (3x3 women's basketball) markets (Placeholder)."""
    logger.info("💰 Fetching Unrivaled prediction markets (Placeholder)...")
    return []
