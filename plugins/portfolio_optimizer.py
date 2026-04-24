"""Portfolio-level bet sizing and optimization across all sports.

This module implements:
- Kelly Criterion for optimal bet sizing
- Portfolio-level risk management
- Daily spending limits
- Multi-sport allocation optimization
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Constants for portfolio optimization
YEAR_START_INDEX = 0
YEAR_END_INDEX = 4
MONTH_START_INDEX = 4
MONTH_END_INDEX = 6
DAY_START_INDEX = 6
DAY_END_INDEX = 8
CENTS_TO_PROBABILITY_FACTOR = 100.0
DEFAULT_ASK_PRICE = 50.0
DEFAULT_MAX_DAILY_RISK_PCT = 0.25
DEFAULT_KELLY_FRACTION = 0.25
DEFAULT_MAX_BET_SIZE = 100.0
DEFAULT_MAX_SINGLE_BET_PCT = 0.10
DEFAULT_MARKET_PROBABILITY = 0.5

MIN_PRACTICAL_BET_SIZE = 1.00

# Game ID parsing constants
MIN_GAME_ID_PARTS = 4  # SPORT_DATE_HOME_AWAY format
SPORT_INDEX = 0
DATE_INDEX = 1
HOME_TEAM_INDEX = 2
AWAY_TEAM_INDEX = 3

# Kelly fraction defaults
DEFAULT_MIN_KELLY_FRACTION = 0.01

# Minimum edge for profitable bets (3% positive edge)
DEFAULT_MIN_EDGE = 0.03

# Report formatting constants
REPORT_HEADER_WIDTH = 80

# Default configuration values for main() example
EXAMPLE_BANKROLL = 1000.0
EXAMPLE_MAX_DAILY_RISK_PCT = 0.10
EXAMPLE_KELLY_FRACTION = 0.25
EXAMPLE_MIN_BET_SIZE = 2.0
EXAMPLE_MAX_BET_SIZE = 50.0
EXAMPLE_MAX_SINGLE_BET_PCT = 0.05
EXAMPLE_MIN_EDGE = 0.05
EXAMPLE_MIN_CONFIDENCE = 0.68

# Probability blending weights (Elo vs BetMGM)
ELO_BLEND_WEIGHT = 0.7
BETMGM_BLEND_WEIGHT = 0.3


def extract_game_date(game_id: str) -> Optional[str]:
    """Extract game date from game_id like TENNIS_20260129_ALCARAZ_ZVEREV.

    Returns date in YYYY-MM-DD format or None if not found.
    """
    match = re.search(r"_(\d{8})_", game_id)
    if match:
        date_str = match.group(1)
        return (
            f"{date_str[YEAR_START_INDEX:YEAR_END_INDEX]}-"
            f"{date_str[MONTH_START_INDEX:MONTH_END_INDEX]}-"
            f"{date_str[DAY_START_INDEX:DAY_END_INDEX]}"
        )
    return None


def extract_ticker_date(ticker: str) -> Optional[str]:
    """Extract date from Kalshi ticker like KXATPMATCH-26JAN22CERRUB-RUB.

    Returns date in YYYY-MM-DD format or None if not found.
    Assumes year 2026 for tickers with format like 26JAN22.
    """
    match = re.search(
        r"-26(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2})", ticker.upper()
    )
    if match:
        month_map = {
            "JAN": "01",
            "FEB": "02",
            "MAR": "03",
            "APR": "04",
            "MAY": "05",
            "JUN": "06",
            "JUL": "07",
            "AUG": "08",
            "SEP": "09",
            "OCT": "10",
            "NOV": "11",
            "DEC": "12",
        }
        month = month_map[match.group(1)]
        day = match.group(2)
        return f"2026-{month}-{day}"
    return None


# Constants
CENTS_TO_PROBABILITY_FACTOR = 100.0
DEFAULT_MARKET_PROBABILITY = 0.5


def estimate_asks_from_market_prob(market_prob: float) -> Tuple[int, int]:
    """Estimate yes_ask and no_ask prices from market probability.

    Returns:
        Tuple of (yes_ask, no_ask) in cents.
    """
    yes_ask = int(market_prob * CENTS_TO_PROBABILITY_FACTOR)
    no_ask = int((1 - market_prob) * CENTS_TO_PROBABILITY_FACTOR)
    return yes_ask, no_ask


@dataclass
class BetOpportunity:
    """Represents a single bet opportunity."""

    sport: str
    ticker: str
    bet_on: str  # "home" or "away"
    team: str
    opponent: str
    home_team: str = ""
    away_team: str = ""
    elo_prob: float = DEFAULT_MARKET_PROBABILITY  # Elo-predicted win probability
    market_prob: float = DEFAULT_MARKET_PROBABILITY  # Market-implied probability
    edge: float = 0.0  # elo_prob - market_prob
    confidence: str = "MEDIUM"  # "HIGH" or "MEDIUM"
    yes_ask: float = DEFAULT_ASK_PRICE  # Market ask price (for buying)
    no_ask: float = DEFAULT_ASK_PRICE  # Market ask price (for buying)
    home_rating: float = 0.0
    away_rating: float = 0.0
    game_time: Optional[str] = None
    game_id: Optional[str] = None
    betmgm_prob: Optional[float] = None

    @property
    def kelly_fraction(self) -> float:
        """Calculate Kelly Criterion fraction for this bet."""
        if self.market_prob <= 0 or self.market_prob >= 1:
            return 0.0

        p = self.elo_prob
        q = 1 - p
        b = (1 / self.market_prob) - 1
        kelly = (p * b - q) / b
        return max(0, kelly)

    @property
    def expected_value(self) -> float:
        """Calculate expected value as percentage of stake."""
        return self.edge / self.market_prob

    @property
    def blended_prob(self) -> float:
        """Calculate blended probability (70% Elo, 30% BetMGM)."""
        if self.betmgm_prob is not None:
            return (self.elo_prob * ELO_BLEND_WEIGHT) + (
                self.betmgm_prob * BETMGM_BLEND_WEIGHT
            )
        return self.elo_prob

    def format_matchup(self) -> str:
        """Format the matchup as 'Home Team vs Away Team'."""
        if self.home_team and self.away_team:
            return f"{self.home_team} vs {self.away_team}"
        elif self.team and self.opponent:
            # For sports like tennis where home/away might not be meaningful
            return f"{self.team} vs {self.opponent}"
        else:
            return "Unknown Matchup"

    def format_rankings(self, rankings_dict: Dict[str, str]) -> str:
        """Format rankings for both teams.

        Args:
            rankings_dict: Dictionary mapping team names to ranking strings like "#1 (1560)"

        Returns:
            String like "#1 (1560) vs #5 (1480)" or "Unranked vs #3 (1520)"
        """
        home_rank = rankings_dict.get(
            self.home_team if self.home_team else self.team, "Unranked"
        )
        away_rank = rankings_dict.get(
            self.away_team if self.away_team else self.opponent, "Unranked"
        )
        return f"{home_rank} vs {away_rank}"


@dataclass
class PortfolioAllocation:
    """Represents optimized allocation for a bet."""

    opportunity: BetOpportunity
    bet_size: float
    kelly_fraction: float
    allocation_pct: float


@dataclass
class PortfolioConfig:
    """Configuration for portfolio optimization."""

    bankroll: float
    max_daily_risk_pct: float = DEFAULT_MAX_DAILY_RISK_PCT  # 25% max daily risk
    kelly_fraction: float = DEFAULT_KELLY_FRACTION  # Conservative Kelly for more volume
    min_bet_size: float = 2.0
    max_bet_size: float = DEFAULT_MAX_BET_SIZE
    max_single_bet_pct: float = DEFAULT_MAX_SINGLE_BET_PCT  # 10% max single bet
    min_edge: float = (
        DEFAULT_MIN_EDGE  # Minimum 3% positive edge required (positive EV)
    )
    min_confidence: float = 0.0
    excluded_segments: Optional[List[Tuple[str, str]]] = None


class OpportunityParser(ABC):
    """Abstract base for parsing bet opportunities from different sources."""

    @abstractmethod
    def parse(self, data: Dict, sport: str) -> Optional[BetOpportunity]:
        """Parse a single record into a BetOpportunity."""
        pass

    def _get_numeric(self, data: Dict, key: str, default: float = 0.0) -> float:
        """Safely get a numeric value from dict, handling NaN."""
        val = data.get(key, default)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return float(val)

    @staticmethod
    def _resolve_bet_direction(
        home_team: str, away_team: str, bet_on: str, side: Optional[str] = None
    ) -> str:
        """Resolve whether a recommendation targets the home or away side.

        ``bet_recommendations.bet_on`` has historically been persisted in two
        formats:
        1. ``home`` / ``away`` from the loader's normalized storage contract.
        2. Team name strings from older recommendation producers.

        The portfolio loaders must accept either representation.
        """
        normalized_side = str(side).lower() if side else ""
        if normalized_side in {"home", "away"}:
            return normalized_side

        normalized_bet_on = str(bet_on).lower()
        if normalized_bet_on in {"home", "away"}:
            return normalized_bet_on

        if bet_on == home_team:
            return "home"
        if bet_on == away_team:
            return "away"

        return "home"


class DatabaseRowParser(OpportunityParser):
    """Parse bet opportunities from database row (pandas Series)."""

    def parse(self, row: pd.Series, sport: str) -> Optional[BetOpportunity]:
        """Parse a database row into a BetOpportunity."""
        try:
            ticker = row.get("ticker")
            if not ticker or pd.isna(ticker):
                return None

            # Parse sport-specific fields
            team, opponent, bet_direction = self._parse_teams(row, sport)
            yes_ask, no_ask, market_prob = self._parse_prices(row, sport, bet_direction)

            return BetOpportunity(
                sport=sport,
                ticker=ticker,
                bet_on=bet_direction,
                team=team,
                opponent=opponent,
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                elo_prob=self._get_numeric(row, "elo_prob"),
                market_prob=market_prob,
                edge=self._get_numeric(row, "edge"),
                confidence=row.get("confidence", "MEDIUM"),
                yes_ask=yes_ask,
                no_ask=no_ask,
                home_rating=self._get_numeric(row, "home_rating"),
                away_rating=self._get_numeric(row, "away_rating"),
                game_id=row.get("bet_id", ""),
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _parse_teams(self, row: pd.Series, sport: str) -> Tuple[str, str, str]:
        """Extract team, opponent, and bet direction based on sport."""
        home_team = row.get("home_team", "")
        away_team = row.get("away_team", "")

        if sport == "tennis":
            team = row.get("bet_on", "")
            opponent = away_team if team == home_team else home_team
            return team, opponent, "home"

        bet_on_team = row.get("bet_on", "")
        bet_direction = self._resolve_bet_direction(home_team, away_team, bet_on_team)
        if bet_direction == "home":
            return home_team, away_team, "home"
        return away_team, home_team, "away"

    def _parse_prices(
        self, row: pd.Series, sport: str, bet_direction: str
    ) -> Tuple[float, float, float]:
        """Extract yes_ask, no_ask, and market_prob."""
        yes_ask = self._get_numeric(row, "yes_ask")
        no_ask = self._get_numeric(row, "no_ask")
        market_prob = self._get_numeric(row, "market_prob")

        # Estimate asks if missing
        if yes_ask == 0 and market_prob > 0:
            yes_ask, no_ask = estimate_asks_from_market_prob(market_prob)

        return yes_ask, no_ask, market_prob


class JsonFileParser(OpportunityParser):
    """Parse bet opportunities from JSON file dict."""

    def parse(self, data: Dict, sport: str) -> Optional[BetOpportunity]:
        """Parse a JSON dict into a BetOpportunity."""
        try:
            ticker = data.get("ticker")
            if not ticker:
                return None

            # Parse sport-specific fields
            team, opponent, bet_direction = self._parse_teams(data, sport)
            yes_ask, no_ask, market_prob = self._parse_prices(
                data, sport, bet_direction
            )

            if market_prob <= 0:
                return None

            # Generate game_id if missing
            game_id = data.get("game_id")
            if not game_id:
                game_id = self._generate_game_id(data, sport)

            return BetOpportunity(
                sport=sport,
                ticker=ticker,
                bet_on=bet_direction,
                team=team,
                opponent=opponent,
                home_team=data.get("home_team", ""),
                away_team=data.get("away_team", ""),
                elo_prob=self._get_numeric(data, "elo_prob"),
                market_prob=market_prob,
                edge=self._get_numeric(data, "edge"),
                confidence=data.get("confidence", "MEDIUM"),
                yes_ask=yes_ask,
                no_ask=no_ask,
                home_rating=self._get_numeric(data, "home_rating"),
                away_rating=self._get_numeric(data, "away_rating"),
                game_time=data.get("game_time", data.get("close_time")),
                game_id=game_id,
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _generate_game_id(self, data: Dict, sport: str) -> Optional[str]:
        """Generate game_id from available data."""
        home_team = data.get("home_team", "")
        away_team = data.get("away_team", "")
        game_time = data.get("game_time", data.get("close_time", ""))

        if not home_team or not away_team or not game_time:
            return None

        try:
            # Parse date from game_time
            from datetime import datetime

            dt = datetime.fromisoformat(game_time.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y%m%d")

            # Generate game_id in format: SPORT_YYYYMMDD_HOME_AWAY
            return f"{sport.upper()}_{date_str}_{home_team}_{away_team}"
        except (ValueError, AttributeError):
            return None

    def _parse_teams(self, data: Dict, sport: str) -> Tuple[str, str, str]:
        """Extract team, opponent, and bet direction based on sport."""
        home_team = data.get("home_team", "")
        away_team = data.get("away_team", "")

        if sport == "tennis":
            team = data.get("bet_on", data.get("player1", ""))
            opponent = data.get("opponent", data.get("player2", ""))
            return team, opponent, data.get("side", "home")

        bet_direction = data.get("side", data.get("bet_on", "home"))
        if bet_direction == "home":
            return home_team, away_team, "home"
        else:
            return away_team, home_team, "away"

    def _parse_prices(
        self, data: Dict, sport: str, bet_direction: str
    ) -> Tuple[float, float, float]:
        """Extract yes_ask, no_ask, and market_prob."""
        yes_ask = float(data.get("yes_ask", 0))
        no_ask = float(data.get("no_ask", 0))
        market_prob = self._get_numeric(data, "market_prob", 0.5)

        # Handle tennis-specific logic
        if sport == "tennis" and "market_prob" not in data:
            market_prob = self._parse_tennis_market_prob(data, yes_ask, no_ask)

        # Estimate asks if missing
        if yes_ask == 0 and market_prob > 0:
            yes_ask, no_ask = estimate_asks_from_market_prob(market_prob)

        # Derive market probability from ask prices if not provided
        if "market_prob" not in data and sport != "tennis":
            market_prob = self._derive_market_prob_from_asks(
                yes_ask, no_ask, bet_direction, market_prob
            )

        return yes_ask, no_ask, market_prob

    def _parse_tennis_market_prob(
        self, data: Dict, yes_ask: float, no_ask: float
    ) -> float:
        """Parse market probability for tennis matches.

        Tennis has special logic because we need to determine which player
        corresponds to the 'yes' side based on the bet_on field.
        """
        team = data.get("bet_on", "")
        player1 = data.get("player1", "")

        if team and player1 and (team in player1 or player1 in team):
            # Betting on player1 (yes side)
            return (
                yes_ask / CENTS_TO_PROBABILITY_FACTOR
                if yes_ask > 0
                else DEFAULT_MARKET_PROBABILITY
            )
        else:
            # Betting on player2 (no side)
            return (
                no_ask / CENTS_TO_PROBABILITY_FACTOR
                if no_ask > 0
                else DEFAULT_MARKET_PROBABILITY
            )

    def _derive_market_prob_from_asks(
        self, yes_ask: float, no_ask: float, bet_direction: str, fallback_prob: float
    ) -> float:
        """Derive market probability from ask prices.

        Uses the appropriate ask price (yes_ask for home bets, no_ask for away bets)
        to calculate the market-implied probability. If the primary ask is 0,
        tries to calculate from the opposite ask if available.
        """
        if bet_direction == "home":
            if yes_ask > 0:
                return yes_ask / CENTS_TO_PROBABILITY_FACTOR
            elif no_ask > 0:
                # Calculate from no_ask: market_prob = 1 - (no_ask / 100)
                return 1.0 - (no_ask / CENTS_TO_PROBABILITY_FACTOR)
            else:
                return fallback_prob
        else:  # away bet
            if no_ask > 0:
                return no_ask / CENTS_TO_PROBABILITY_FACTOR
            elif yes_ask > 0:
                # Calculate from yes_ask: market_prob = yes_ask / 100
                # For away bet, market_prob is probability of away winning
                # which is 1 - probability of home winning
                return 1.0 - (yes_ask / CENTS_TO_PROBABILITY_FACTOR)
            else:
                return fallback_prob


class PortfolioOptimizer:
    """Optimize bet sizing across all sports using Kelly Criterion and portfolio theory."""

    def __init__(
        self,
        config: PortfolioConfig,
    ):
        """Initialize portfolio optimizer.

        Args:
            config: PortfolioConfig object with all configuration parameters.

        Raises:
            ValueError: If config is None or config.bankroll is not provided.
        """
        if config is None:
            raise ValueError("PortfolioConfig must be provided")

        if config.bankroll is None:
            raise ValueError("bankroll must be provided in PortfolioConfig")

        # Use config object
        self.bankroll = config.bankroll
        self.max_daily_risk_pct = config.max_daily_risk_pct
        self.kelly_fraction = config.kelly_fraction
        self.min_bet_size = config.min_bet_size
        self.max_bet_size = config.max_bet_size
        self.max_single_bet_pct = config.max_single_bet_pct
        self.min_edge = config.min_edge
        self.min_confidence = config.min_confidence
        self.excluded_segments = config.excluded_segments or []

        # Initialize parsers
        self._db_parser = DatabaseRowParser()
        self._json_parser = JsonFileParser()

    def _fetch_betmgm_prob(
        self, game_id: Optional[str], bet_direction: str
    ) -> Optional[float]:
        """Fetch BetMGM implied probability from game_odds table."""
        if not game_id:
            return None

        try:
            from plugins.db_manager import default_db

            query = """
                SELECT outcome_name, price
                FROM game_odds
                WHERE game_id = :game_id
                  AND LOWER(bookmaker) = 'betmgm'
                  AND LOWER(market_name) = 'h2h'
            """
            result = default_db.fetch_df(query, {"game_id": game_id})

            # Fuzzy match if exact match fails
            if result.empty:
                result = self._fuzzy_match_betmgm(game_id, default_db)

            if result.empty:
                return None

            return self._extract_prob_from_rows(result, bet_direction)
        except Exception:
            return None

    def _extract_prob_from_rows(
        self, result: pd.DataFrame, bet_direction: str
    ) -> Optional[float]:
        """Extract probability for the given bet direction from database result rows."""
        for _, row in result.iterrows():
            outcome = str(row.get("outcome_name", "")).lower()
            price = float(row.get("price", 0))

            if price <= 0:
                continue

            # Convert decimal odds to implied probability
            prob = 1.0 / price

            if bet_direction == "home" and outcome in ["home", "h"]:
                return prob
            elif bet_direction == "away" and outcome in ["away", "a"]:
                return prob

        return None

    def _fuzzy_match_betmgm(self, game_id: str, db) -> pd.DataFrame:
        """Try fuzzy matching for BetMGM odds by sport, date, and team patterns."""
        parts = game_id.split("_")
        if len(parts) < MIN_GAME_ID_PARTS:
            return pd.DataFrame()

        sport = parts[SPORT_INDEX]
        date_part = parts[DATE_INDEX]
        home_abbr = parts[HOME_TEAM_INDEX].upper()
        away_abbr = parts[AWAY_TEAM_INDEX].upper()

        try:
            base_date = datetime.strptime(date_part, "%Y%m%d")
            dates_to_try = [
                base_date.strftime("%Y%m%d"),
                (base_date + timedelta(days=1)).strftime("%Y%m%d"),
                (base_date - timedelta(days=1)).strftime("%Y%m%d"),
            ]
        except ValueError:
            dates_to_try = [date_part]

        for try_date in dates_to_try:
            query = """
                SELECT game_id, outcome_name, price
                FROM game_odds
                WHERE LOWER(bookmaker) = 'betmgm'
                  AND LOWER(market_name) = 'h2h'
                  AND game_id LIKE :date_pattern
                  AND (UPPER(game_id) LIKE :home_pattern
                       AND UPPER(game_id) LIKE :away_pattern)
            """
            result = db.fetch_df(
                query,
                {
                    "date_pattern": f"{sport}_{try_date}_%",
                    "home_pattern": f"%{home_abbr}%",
                    "away_pattern": f"%{away_abbr}%",
                },
            )
            if not result.empty:
                return result
        return pd.DataFrame()

    def load_opportunities_from_database(
        self,
        date_str: str,
        sports: List[str] = None,
    ) -> List[BetOpportunity]:
        """Load all bet opportunities from PostgreSQL database for a given date."""
        if sports is None:
            sports = ["nhl", "nba", "mlb", "nfl", "ncaab", "tennis"]

        from plugins.db_manager import default_db

        opportunities = []
        skipped_stale = 0

        normalized_sports = [sport.upper() for sport in sports]
        sports_list = ", ".join([f"'{sport}'" for sport in normalized_sports])
        query = f"""
            SELECT sport, ticker, bet_on, home_team, away_team,
                   home_rating, away_rating, elo_prob, market_prob,
                   edge, confidence, yes_ask, no_ask, bet_id
            FROM bet_recommendations
            WHERE recommendation_date = :rec_date
                AND sport IN ({sports_list})
                AND ticker IS NOT NULL AND ticker != ''
            ORDER BY sport, home_team, away_team
        """

        try:
            results = default_db.fetch_df(query, {"rec_date": date_str})
            if results.empty:
                print(f"⚠️  No bet recommendations found in database for {date_str}")
                return opportunities

            print(
                f"📊 Loaded {len(results)} bet recommendations from database for {date_str}"
            )

            for _, row in results.iterrows():
                sport = row["sport"]
                ticker = row["ticker"]

                # Skip stale tickers
                ticker_date = extract_ticker_date(ticker)
                if ticker_date and ticker_date < date_str:
                    skipped_stale += 1
                    continue

                opp = self._db_parser.parse(row, sport)
                if opp:
                    opportunities.append(opp)

        except Exception as e:
            print(f"❌ Error loading opportunities from database: {e}")

        if skipped_stale > 0:
            print(f"⚠️  Skipped {skipped_stale} stale opportunities")

        return opportunities

    def load_opportunities_from_files(
        self,
        date_str: str,
        sports: List[str] = None,
    ) -> List[BetOpportunity]:
        """Load all bet opportunities from JSON files for a given date."""
        if sports is None:
            sports = ["nhl", "nba", "mlb", "nfl", "ncaab", "tennis"]

        opportunities = []
        skipped_stale = 0

        for sport in sports:
            sport_opportunities, sport_skipped = (
                self._load_sport_opportunities_from_file(sport, date_str)
            )
            opportunities.extend(sport_opportunities)
            skipped_stale += sport_skipped

        if skipped_stale > 0:
            print(f"📅 Skipped {skipped_stale} stale opportunities")

        return opportunities

    def _load_sport_opportunities_from_file(
        self, sport: str, date_str: str
    ) -> Tuple[List[BetOpportunity], int]:
        """Load opportunities from a single sport's JSON file."""
        bet_file = Path(f"data/{sport}/bets_{date_str}.json")
        if not bet_file.exists():
            return [], 0

        try:
            with open(bet_file, "r") as f:
                bets_data = json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading {bet_file}: {e}")
            return [], 0

        if not isinstance(bets_data, list):
            return [], 0

        return self._process_bets_data(bets_data, sport, date_str)

    def _process_bets_data(
        self, bets_data: List[Dict], sport: str, date_str: str
    ) -> Tuple[List[BetOpportunity], int]:
        """Process a list of bet data entries."""
        opportunities = []
        skipped_stale = 0

        for bet in bets_data:
            opportunity, is_stale = self._process_single_bet(bet, sport, date_str)
            if is_stale:
                skipped_stale += 1
            elif opportunity:
                opportunities.append(opportunity)

        return opportunities, skipped_stale

    def _process_single_bet(
        self, bet: Dict, sport: str, date_str: str
    ) -> Tuple[Optional[BetOpportunity], bool]:
        """Process a single bet entry, returning opportunity and stale flag."""
        ticker = bet.get("ticker")
        if not ticker:
            return None, False

        if self._is_stale_bet(bet, ticker, date_str):
            return None, True

        opp = self._json_parser.parse(bet, sport)
        if not opp:
            return None, False

        # Fetch BetMGM probability for file-based loading
        opp.betmgm_prob = self._fetch_betmgm_prob(opp.game_id, opp.bet_on)
        return opp, False

    def _is_stale_bet(self, bet: Dict, ticker: str, date_str: str) -> bool:
        """Check if a bet is stale based on game date or ticker date."""
        game_date = extract_game_date(bet.get("game_id", ""))
        ticker_date = extract_ticker_date(ticker)

        return (game_date and game_date < date_str) or (
            ticker_date and ticker_date < date_str
        )

    def filter_opportunities(
        self, opportunities: List[BetOpportunity]
    ) -> List[BetOpportunity]:
        """Filter opportunities based on minimum thresholds."""
        filtered = []
        stats = {"segment": 0, "edge": 0, "confidence": 0, "kelly": 0}
        sport_confidence_stats = {}

        for opp in opportunities:
            # Check excluded segments
            confidence_str = opp.confidence if opp.confidence else "UNKNOWN"
            if (opp.sport.upper(), confidence_str.upper()) in self.excluded_segments:
                stats["segment"] += 1
                continue

            # Check minimum edge
            if opp.edge < self.min_edge:
                stats["edge"] += 1
                continue

            # Check Kelly fraction - must be positive for valid value bets
            if opp.kelly_fraction <= 0:
                stats["kelly"] += 1
                continue

            filtered.append(opp)

        self._print_filter_stats(stats, sport_confidence_stats)
        return filtered

    def _print_filter_stats(
        self, stats: Dict[str, int], sport_confidence_stats: Dict[str, int] = None
    ) -> None:
        """Print filtering statistics."""
        if stats["segment"] > 0:
            print(
                f"🚫 Excluded {stats['segment']} from unprofitable segments: {self.excluded_segments}"
            )
        if stats["edge"] > 0:
            print(
                f"🚫 Excluded {stats['edge']} due to low edge (< {self.min_edge:.1%})"
            )
        if stats["confidence"] > 0:
            print(f"🚫 Excluded {stats['confidence']} due to low confidence")
            if sport_confidence_stats:
                for sport, count in sport_confidence_stats.items():
                    sport_threshold = self._get_sport_min_confidence(sport)
                    print(
                        f"     - {sport.upper()}: {count} bets (< {sport_threshold:.1%})"
                    )
        if stats["kelly"] > 0:
            print(f"🚫 Excluded {stats['kelly']} due to zero/negative Kelly fraction")

    def calculate_portfolio_allocation(
        self, opportunities: List[BetOpportunity]
    ) -> List[PortfolioAllocation]:
        """Calculate optimal bet sizes for portfolio of opportunities."""
        if not opportunities:
            return []

        max_daily_allocation = self.bankroll * self.max_daily_risk_pct

        # Kelly-based allocation for positive EV strategy
        return self._allocate_kelly_sizing(opportunities, max_daily_allocation)

    def _allocate_equal_sizing(
        self, opportunities: List[BetOpportunity], max_daily_allocation: float
    ) -> List[PortfolioAllocation]:
        """Equal sizing for market agreement strategy."""
        max_bets = int(max_daily_allocation / MIN_PRACTICAL_BET_SIZE)
        num_bets = min(max_bets, len(opportunities))

        bet_size = MIN_PRACTICAL_BET_SIZE
        if num_bets > 0:
            bet_size = max_daily_allocation / num_bets
            bet_size = min(bet_size, self.max_bet_size)
            bet_size = min(bet_size, self.bankroll * self.max_single_bet_pct)
            bet_size = max(bet_size, MIN_PRACTICAL_BET_SIZE)

        sorted_opps = sorted(
            opportunities, key=lambda x: x.expected_value, reverse=True
        )
        allocations = []
        total_allocated = 0.0

        for opp in sorted_opps:
            if total_allocated + bet_size > max_daily_allocation:
                break
            allocations.append(
                PortfolioAllocation(
                    opportunity=opp,
                    bet_size=round(bet_size, 2),
                    kelly_fraction=DEFAULT_MIN_KELLY_FRACTION,
                    allocation_pct=bet_size / self.bankroll,
                )
            )
            total_allocated += bet_size

        return allocations

    def _allocate_kelly_sizing(
        self, opportunities: List[BetOpportunity], max_daily_allocation: float
    ) -> List[PortfolioAllocation]:
        """Kelly Criterion-based allocation."""
        sorted_opps = self._prioritize_sport_diversity(opportunities)
        allocations = []
        total_allocated = 0.0

        for opp in sorted_opps:
            kelly_size = (
                self.bankroll * opp.kelly_fraction * self.kelly_fraction
                if opp.kelly_fraction > 0
                else self.min_bet_size
            )

            bet_size = max(self.min_bet_size, min(self.max_bet_size, kelly_size))
            bet_size = min(self.bankroll * self.max_single_bet_pct, bet_size)

            if total_allocated + bet_size > max_daily_allocation:
                remaining = max_daily_allocation - total_allocated
                if remaining < self.min_bet_size:
                    break
                bet_size = remaining

            allocations.append(
                PortfolioAllocation(
                    opportunity=opp,
                    bet_size=round(bet_size, 2),
                    kelly_fraction=(
                        opp.kelly_fraction
                        if opp.kelly_fraction > 0
                        else DEFAULT_MIN_KELLY_FRACTION
                    ),
                    allocation_pct=bet_size / self.bankroll,
                )
            )
            total_allocated += bet_size

            if total_allocated >= max_daily_allocation:
                break

        return allocations

    def _prioritize_sport_diversity(
        self, opportunities: List[BetOpportunity]
    ) -> List[BetOpportunity]:
        """Return opportunities ordered to give each sport an initial seat.

        The live portfolio is intended to allocate across sports, not let one
        slate of cheap longshots consume the full daily budget before another
        sport's best opportunity is considered. We therefore take the highest-EV
        opportunity from each sport first, then fill the remaining queue by EV.
        """
        if not opportunities:
            return []

        top_by_sport: Dict[str, BetOpportunity] = {}
        for opp in opportunities:
            sport_key = opp.sport.upper()
            current = top_by_sport.get(sport_key)
            if current is None or opp.expected_value > current.expected_value:
                top_by_sport[sport_key] = opp

        prioritized = sorted(
            top_by_sport.values(), key=lambda opp: opp.expected_value, reverse=True
        )
        selected_ids = {id(opp) for opp in prioritized}
        remaining = sorted(
            [opp for opp in opportunities if id(opp) not in selected_ids],
            key=lambda opp: opp.expected_value,
            reverse=True,
        )
        return prioritized + remaining

    def optimize_daily_bets(
        self,
        date_str: str,
        sports: List[str] = None,
        use_database: bool = True,
    ) -> Tuple[List[PortfolioAllocation], Dict]:
        """Main entry point: Load, filter, and optimize bets for a given date."""
        if sports is None:
            sports = ["nhl", "nba", "mlb", "nfl", "ncaab", "tennis"]

        # Load opportunities
        if use_database:
            print(f"📊 Loading opportunities from database for {date_str}...")
            opportunities = self.load_opportunities_from_database(date_str, sports)
            if not opportunities:
                print("⚠️  No opportunities found in database, falling back to files...")
                opportunities = self.load_opportunities_from_files(date_str, sports)
        else:
            print(f"📊 Loading opportunities from files for {date_str}...")
            opportunities = self.load_opportunities_from_files(date_str, sports)

        filtered_opps = self.filter_opportunities(opportunities)
        allocations = self.calculate_portfolio_allocation(filtered_opps)

        summary = self._build_summary(
            date_str, opportunities, filtered_opps, allocations, use_database
        )
        return allocations, summary

    def _build_summary(
        self,
        date_str: str,
        opportunities: List[BetOpportunity],
        filtered_opps: List[BetOpportunity],
        allocations: List[PortfolioAllocation],
        use_database: bool,
    ) -> Dict:
        """Build summary statistics dictionary."""
        total_bet = sum(a.bet_size for a in allocations)
        total_expected_profit = sum(
            a.bet_size * a.opportunity.expected_value for a in allocations
        )

        return {
            "date": date_str,
            "bankroll": self.bankroll,
            "data_source": "database" if use_database and opportunities else "files",
            "opportunities_found": len(opportunities),
            "opportunities_filtered": len(filtered_opps),
            "bets_placed": len(allocations),
            "total_bet_amount": round(total_bet, 2),
            "total_bet_pct": round(total_bet / self.bankroll, 4),
            "expected_profit": round(total_expected_profit, 2),
            "expected_roi": (
                round(total_expected_profit / total_bet, 4) if total_bet > 0 else 0
            ),
            "avg_bet_size": (
                round(total_bet / len(allocations), 2) if allocations else 0
            ),
            "avg_edge": (
                round(
                    sum(a.opportunity.edge for a in allocations) / len(allocations), 4
                )
                if allocations
                else 0
            ),
        }

    def generate_bet_report(
        self,
        allocations: List[PortfolioAllocation],
        summary: Dict,
        output_file: Optional[Path] = None,
    ) -> str:
        """Generate human-readable betting report."""
        lines = [
            "=" * REPORT_HEADER_WIDTH,
            "PORTFOLIO-OPTIMIZED BETTING REPORT",
            "=" * REPORT_HEADER_WIDTH,
            f"Date: {summary['date']}",
            f"Bankroll: ${summary['bankroll']:,.2f}",
            f"Max Daily Risk: {self.max_daily_risk_pct:.1%} (${self.bankroll * self.max_daily_risk_pct:,.2f})",
            f"Kelly Fraction: {self.kelly_fraction:.2%}",
            "",
            "SUMMARY",
            "-" * REPORT_HEADER_WIDTH,
            f"Opportunities Found:     {summary['opportunities_found']}",
            f"After Filtering:         {summary['opportunities_filtered']}",
            f"Bets to Place:           {summary['bets_placed']}",
            f"Total Bet Amount:        ${summary['total_bet_amount']:,.2f} ({summary['total_bet_pct']:.2%})",
            f"Expected Profit:         ${summary['expected_profit']:,.2f}",
            f"Expected ROI:            {summary['expected_roi']:.2%}",
            f"Average Bet Size:        ${summary['avg_bet_size']:,.2f}",
            f"Average Edge:            {summary['avg_edge']:.2%}",
            "",
        ]

        if allocations:
            lines.append("BET ALLOCATIONS")
            lines.append("-" * REPORT_HEADER_WIDTH)
            by_sport = {}
            for alloc in allocations:
                sport = alloc.opportunity.sport.upper()
                by_sport.setdefault(sport, []).append(alloc)

            for sport in sorted(by_sport.keys()):
                lines.append(f"\n{sport}:")
                sport_total = sum(a.bet_size for a in by_sport[sport])
                lines.append(f"  Sport Total: ${sport_total:.2f}\n")

                for i, alloc in enumerate(by_sport[sport], 1):
                    opp = alloc.opportunity
                    lines.extend(
                        [
                            f"  {i}. {opp.team} vs {opp.opponent}",
                            f"     Ticker: {opp.ticker}",
                            f"     Bet Size: ${alloc.bet_size:.2f} ({alloc.allocation_pct:.2%})",
                            f"     Elo: {opp.elo_prob:.1%} | Market: {opp.market_prob:.1%} | Edge: {opp.edge:+.1%}",
                            f"     Kelly: {opp.kelly_fraction:.3f} | EV: {opp.expected_value:+.2%}",
                            f"     Confidence: {opp.confidence}",
                            "",
                        ]
                    )
        else:
            lines.append("No bets meet criteria.")

        lines.append("=" * REPORT_HEADER_WIDTH)
        report = "\n".join(lines)

        if output_file:
            output_file.write_text(report)

        return report


def main():
    """Example usage of portfolio optimizer."""
    import sys

    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")

    # Create PortfolioConfig object instead of using individual parameters
    config = PortfolioConfig(
        bankroll=EXAMPLE_BANKROLL,
        max_daily_risk_pct=EXAMPLE_MAX_DAILY_RISK_PCT,
        kelly_fraction=EXAMPLE_KELLY_FRACTION,
        min_bet_size=EXAMPLE_MIN_BET_SIZE,
        max_bet_size=EXAMPLE_MAX_BET_SIZE,
        max_single_bet_pct=EXAMPLE_MAX_SINGLE_BET_PCT,
        min_edge=EXAMPLE_MIN_EDGE,
        min_confidence=EXAMPLE_MIN_CONFIDENCE,
    )

    optimizer = PortfolioOptimizer(config=config)

    allocations, summary = optimizer.optimize_daily_bets(date_str)
    print(optimizer.generate_bet_report(allocations, summary))


if __name__ == "__main__":
    main()
