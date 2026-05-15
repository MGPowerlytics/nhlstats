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
from typing import Any, Dict, List, Optional, Tuple

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
    home_team_raw: str = ""
    away_team_raw: str = ""
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
    recommendation_id: Optional[str] = None
    betmgm_prob: Optional[float] = None
    probability_source: Optional[str] = None
    evidence_state: Optional[str] = None
    evidence_state_reason: Optional[str] = None
    evidence_state_source_artifact: Optional[str] = None
    governance_status: Optional[str] = None
    clv_evidence_tier: Optional[str] = None
    calibration_evidence_tier: Optional[str] = None
    walk_forward_evidence_tier: Optional[str] = None
    approval_grade_evidence: bool = False
    sizing_eligible: bool = True
    abstain: bool = False
    abstention_reason: Optional[str] = None

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
    min_elo_prob: float = 0.55
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
    def _is_nullish(value) -> bool:
        """Return True when a value should be treated as missing governance metadata."""
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        try:
            return bool(pd.isna(value))
        except TypeError:
            return False

    def _parse_governance_bool(
        self, data: Dict, key: str, fail_closed: bool
    ) -> Tuple[bool, bool]:
        """Parse a governance boolean while failing closed on missing/null/invalid values."""
        if key not in data:
            return fail_closed, True

        value = data.get(key)
        if self._is_nullish(value):
            return fail_closed, True

        if isinstance(value, bool):
            return value, False

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return bool(value), False

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "t", "1", "yes", "y"}:
                return True, False
            if normalized in {"false", "f", "0", "no", "n"}:
                return False, False

        return fail_closed, True

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        """Coerce loose boolean inputs for non-governance evidence metadata."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if pd.isna(value):
                return default
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "t", "1", "yes", "y"}:
                return True
            if normalized in {"false", "f", "0", "no", "n"}:
                return False
        return default

    def _resolve_governance_fields(
        self, data: Dict
    ) -> Tuple[bool, bool, Optional[str]]:
        """Resolve governance booleans and abstention reason with fail-closed semantics."""
        sizing_eligible, sizing_missing = self._parse_governance_bool(
            data, "sizing_eligible", fail_closed=False
        )
        abstain, abstain_missing = self._parse_governance_bool(
            data, "abstain", fail_closed=True
        )

        abstention_reason = data.get("abstention_reason")
        if self._is_nullish(abstention_reason):
            abstention_reason = None

        if sizing_missing or abstain_missing:
            missing_fields = []
            if sizing_missing:
                missing_fields.append("sizing_eligible")
            if abstain_missing:
                missing_fields.append("abstain")
            sizing_eligible = False
            abstain = True
            if abstention_reason is None:
                abstention_reason = (
                    "missing_governance_metadata:" + ",".join(missing_fields)
                )

        return sizing_eligible, abstain, abstention_reason

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
            sizing_eligible, abstain, abstention_reason = (
                self._resolve_governance_fields(row)
            )

            opportunity = BetOpportunity(
                sport=sport,
                ticker=ticker,
                bet_on=bet_direction,
                team=team,
                opponent=opponent,
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                home_team_raw=row.get("home_team_raw", row.get("home_team", "")),
                away_team_raw=row.get("away_team_raw", row.get("away_team", "")),
                elo_prob=self._get_numeric(row, "elo_prob"),
                market_prob=market_prob,
                edge=self._get_numeric(row, "edge"),
                confidence=row.get("confidence", "MEDIUM"),
                yes_ask=yes_ask,
                no_ask=no_ask,
                home_rating=self._get_numeric(row, "home_rating"),
                away_rating=self._get_numeric(row, "away_rating"),
                game_id=row.get("bet_id", ""),
                probability_source=row.get("probability_source"),
                evidence_state=row.get("evidence_state"),
                evidence_state_reason=row.get("evidence_state_reason"),
                evidence_state_source_artifact=row.get("evidence_state_source_artifact"),
                governance_status=row.get("governance_status"),
                clv_evidence_tier=row.get("clv_evidence_tier"),
                calibration_evidence_tier=row.get("calibration_evidence_tier"),
                walk_forward_evidence_tier=row.get("walk_forward_evidence_tier"),
                approval_grade_evidence=self._coerce_bool(
                    row.get("approval_grade_evidence")
                ),
                sizing_eligible=sizing_eligible,
                abstain=abstain,
                abstention_reason=abstention_reason,
            )
            canonical_game_id = row.get("canonical_game_id")
            if canonical_game_id:
                setattr(opportunity, "canonical_game_id", canonical_game_id)
            recommendation_id = row.get("recommendation_id")
            if recommendation_id:
                setattr(opportunity, "recommendation_id", recommendation_id)
            return opportunity
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
            sizing_eligible, abstain, abstention_reason = (
                self._resolve_governance_fields(data)
            )

            opportunity = BetOpportunity(
                sport=sport,
                ticker=ticker,
                bet_on=bet_direction,
                team=team,
                opponent=opponent,
                home_team=data.get("home_team", ""),
                away_team=data.get("away_team", ""),
                home_team_raw=data.get("home_team_raw", data.get("home_team", "")),
                away_team_raw=data.get("away_team_raw", data.get("away_team", "")),
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
                probability_source=data.get("probability_source"),
                evidence_state=data.get("evidence_state"),
                evidence_state_reason=data.get("evidence_state_reason"),
                evidence_state_source_artifact=data.get("evidence_state_source_artifact"),
                governance_status=data.get("governance_status"),
                clv_evidence_tier=data.get("clv_evidence_tier"),
                calibration_evidence_tier=data.get("calibration_evidence_tier"),
                walk_forward_evidence_tier=data.get("walk_forward_evidence_tier"),
                approval_grade_evidence=self._coerce_bool(
                    data.get("approval_grade_evidence")
                ),
                sizing_eligible=sizing_eligible,
                abstain=abstain,
                abstention_reason=abstention_reason,
            )
            canonical_game_id = data.get("canonical_game_id", game_id)
            if canonical_game_id:
                setattr(opportunity, "canonical_game_id", canonical_game_id)
            recommendation_id = data.get("recommendation_id")
            if recommendation_id:
                setattr(opportunity, "recommendation_id", recommendation_id)
            return opportunity
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

    OPEN_POSITION_STATUSES = frozenset({"pending", "open", "placed", "filled"})
    RESTING_ORDER_STATUSES = frozenset({"pending", "open", "placed"})
    EXECUTED_UNSETTLED_STATUSES = frozenset({"filled"})
    DEFAULT_OPERATOR_SEMANTICS_VERSION = "portfolio_risk_state_v1"

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
        self.min_elo_prob = config.min_elo_prob
        self.excluded_segments = config.excluded_segments or []
        self._last_risk_audit: List[Dict[str, Any]] = []

        # Initialize parsers
        self._db_parser = DatabaseRowParser()
        self._json_parser = JsonFileParser()

    @staticmethod
    def _coerce_float(value: Any, default: float = 0.0) -> float:
        """Return *value* as float when possible."""
        if value is None:
            return default
        try:
            if pd.isna(value):
                return default
        except TypeError:
            pass
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        """Return *value* as a best-effort boolean."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "t", "1", "yes", "y"}:
                return True
            if normalized in {"false", "f", "0", "no", "n"}:
                return False
            return default
        try:
            if pd.isna(value):
                return default
        except TypeError:
            pass
        return bool(value)

    @staticmethod
    def _get_opportunity_value(
        opportunity: BetOpportunity, name: str, default: Any = None
    ) -> Any:
        """Read a known or dynamically attached opportunity attribute."""
        return getattr(opportunity, name, default)

    @staticmethod
    def _match_prefix(value: Optional[str]) -> Optional[str]:
        """Return a match-level key from a Kalshi ticker-like identifier."""
        if not value:
            return None
        parts = str(value).split("-")
        if len(parts) >= 2:
            return "-".join(parts[:-1])
        return str(value)

    def _canonical_match_key(self, opportunity: BetOpportunity) -> Optional[str]:
        """Return the best available same-match key for an opportunity."""
        for candidate in (
            self._get_opportunity_value(opportunity, "canonical_game_id"),
            opportunity.game_id,
            self._get_opportunity_value(opportunity, "recommendation_id"),
        ):
            if candidate:
                return str(candidate)
        return self._match_prefix(opportunity.ticker)

    def _selection_key(self, opportunity: BetOpportunity) -> Optional[str]:
        """Return the best available selection identifier for a recommendation."""
        for candidate in (
            self._get_opportunity_value(opportunity, "selection_key"),
            opportunity.bet_on,
            opportunity.team,
        ):
            if candidate:
                return str(candidate).strip().lower()
        return None

    def _empty_risk_context(self, max_daily_allocation: float) -> Dict[str, Any]:
        """Return an empty governed risk context."""
        return {
            "live_bankroll_dollars": self.bankroll,
            "daily_risk_cap_dollars": max_daily_allocation,
            "governed_open_exposure_dollars": 0.0,
            "resting_order_exposure_dollars": 0.0,
            "executed_unsettled_exposure_dollars": 0.0,
            "remaining_daily_risk_budget_dollars": max_daily_allocation,
            "peak_portfolio_value_dollars": self.bankroll,
            "current_portfolio_value_dollars": self.bankroll,
            "drawdown_amount_dollars": 0.0,
            "drawdown_ratio": 0.0,
            "drawdown_state": "at_peak",
            "risk_of_ruin_state": "capital_available",
            "portfolio_guardrail_state": "eligible",
            "portfolio_guardrail_reason_code": None,
            "portfolio_guardrail_reason_detail": None,
            "sport_exposure_amounts": {},
            "same_event_exposure_amounts": {},
            "same_side_exposure_amounts": {},
            "open_positions": [],
            "sport_concentration_limit_dollars": None,
            "operator_semantics_version": self.DEFAULT_OPERATOR_SEMANTICS_VERSION,
        }

    def _build_runtime_risk_context(self, max_daily_allocation: float) -> Dict[str, Any]:
        """Load governed exposure truth and open-position state for live sizing."""
        from plugins.db_manager import default_db

        try:
            exposure_rows = default_db.fetch_df(
                """
                SELECT
                    sport,
                    open_exposure_amount,
                    resting_order_exposure_amount,
                    executed_unsettled_exposure_amount,
                    peak_portfolio_value_dollars,
                    current_portfolio_value_dollars,
                    drawdown_amount_dollars,
                    drawdown_ratio,
                    drawdown_state,
                    risk_of_ruin_state,
                    portfolio_guardrail_state,
                    portfolio_guardrail_reason_code,
                    portfolio_guardrail_reason_detail
                FROM governed_portfolio_risk_state_v1
                """
            )
            open_positions = default_db.fetch_df(
                """
                SELECT
                    UPPER(COALESCE(NULLIF(sport, ''), 'UNKNOWN')) AS sport,
                    COALESCE(
                        NULLIF(recommendation_canonical_game_id, ''),
                        NULLIF(canonical_game_id, ''),
                        NULLIF(recommendation_market_ticker, ''),
                        NULLIF(ticker, '')
                    ) AS canonical_match_key,
                    COALESCE(
                        NULLIF(recommendation_selection_key, ''),
                        NULLIF(bet_on, ''),
                        NULLIF(outcome_name, '')
                    ) AS selection_key,
                    COALESCE(NULLIF(recommendation_market_ticker, ''), NULLIF(ticker, '')) AS market_ticker,
                    LOWER(COALESCE(status, '')) AS position_status,
                    COALESCE(cost_dollars, 0.0) AS exposure_amount
                FROM placed_bets
                WHERE LOWER(COALESCE(status, '')) IN ('pending', 'open', 'placed', 'filled')
                """
            )
        except Exception as exc:
            error_message = str(exc).lower()
            if "placed_bets" in error_message or "open position" in error_message:
                raise RuntimeError(
                    "Unable to load governed open positions for live risk sizing."
                ) from exc
            raise RuntimeError(
                "Unable to load governed portfolio risk state for live risk sizing."
            ) from exc

        return self._build_risk_context_from_frames(
            exposure_rows=exposure_rows,
            open_positions=open_positions,
            max_daily_allocation=max_daily_allocation,
        )

    def _build_risk_context_from_frames(
        self,
        *,
        exposure_rows: Optional[pd.DataFrame],
        open_positions: Optional[pd.DataFrame],
        max_daily_allocation: float,
    ) -> Dict[str, Any]:
        """Build a governed risk context from read-model rows."""
        context = self._empty_risk_context(max_daily_allocation)
        exposure_rows = exposure_rows if exposure_rows is not None else pd.DataFrame()
        open_positions = open_positions if open_positions is not None else pd.DataFrame()

        sport_exposure_amounts: Dict[str, float] = {}
        total_open_exposure = 0.0
        total_resting = 0.0
        total_executed = 0.0
        portfolio_peak_value = self.bankroll
        portfolio_current_value = self.bankroll
        drawdown_amount = 0.0
        drawdown_ratio = 0.0
        drawdown_state = "at_peak"
        risk_of_ruin_state = "capital_available"
        portfolio_guardrail_state = "eligible"
        portfolio_guardrail_reason_code = None
        portfolio_guardrail_reason_detail = None

        if not exposure_rows.empty:
            for _, row in exposure_rows.iterrows():
                sport = str(row.get("sport") or "UNKNOWN").upper()
                sport_exposure = self._coerce_float(row.get("open_exposure_amount"))
                sport_exposure_amounts[sport] = sport_exposure
                total_open_exposure += sport_exposure
                total_resting += self._coerce_float(
                    row.get("resting_order_exposure_amount")
                )
                total_executed += self._coerce_float(
                    row.get("executed_unsettled_exposure_amount")
                )
                portfolio_peak_value = self._coerce_float(
                    row.get("peak_portfolio_value_dollars"), portfolio_peak_value
                )
                portfolio_current_value = self._coerce_float(
                    row.get("current_portfolio_value_dollars"), portfolio_current_value
                )
                drawdown_amount = self._coerce_float(
                    row.get("drawdown_amount_dollars"), drawdown_amount
                )
                drawdown_ratio = self._coerce_float(
                    row.get("drawdown_ratio"), drawdown_ratio
                )
                drawdown_state = str(row.get("drawdown_state") or drawdown_state)
                risk_of_ruin_state = str(
                    row.get("risk_of_ruin_state") or risk_of_ruin_state
                )
                portfolio_guardrail_state = str(
                    row.get("portfolio_guardrail_state") or portfolio_guardrail_state
                )
                portfolio_guardrail_reason_code = (
                    row.get("portfolio_guardrail_reason_code")
                    or portfolio_guardrail_reason_code
                )
                portfolio_guardrail_reason_detail = (
                    row.get("portfolio_guardrail_reason_detail")
                    or portfolio_guardrail_reason_detail
                )

        same_event_exposure_amounts: Dict[str, float] = {}
        same_side_exposure_amounts: Dict[Tuple[str, str], float] = {}
        normalized_open_positions: List[Dict[str, Any]] = []

        if not open_positions.empty:
            open_positions = open_positions.copy()
            open_positions["sport"] = open_positions["sport"].fillna("UNKNOWN").astype(str)
            open_positions["canonical_match_key"] = (
                open_positions["canonical_match_key"]
                .fillna(open_positions.get("market_ticker"))
                .astype(str)
            )
            if "market_ticker" in open_positions.columns:
                open_positions["canonical_match_key"] = open_positions.apply(
                    lambda row: row["canonical_match_key"]
                    if row["canonical_match_key"] not in {"", "None", "nan"}
                    else (self._match_prefix(row.get("market_ticker")) or ""),
                    axis=1,
                )
            open_positions["selection_key"] = (
                open_positions["selection_key"].fillna("").astype(str).str.lower()
            )
            open_positions["exposure_amount"] = open_positions["exposure_amount"].apply(
                self._coerce_float
            )

            for _, row in open_positions.iterrows():
                sport = str(row.get("sport") or "UNKNOWN").upper()
                match_key = str(row.get("canonical_match_key") or "")
                selection_key = str(row.get("selection_key") or "")
                exposure = self._coerce_float(row.get("exposure_amount"))
                status = str(row.get("position_status") or "").lower()
                normalized_open_positions.append(
                    {
                        "sport": sport,
                        "canonical_match_key": match_key,
                        "selection_key": selection_key,
                        "market_ticker": row.get("market_ticker"),
                        "position_status": status,
                        "exposure_amount": exposure,
                    }
                )

                if sport not in sport_exposure_amounts:
                    sport_exposure_amounts[sport] = 0.0
                    sport_exposure_amounts[sport] += exposure

                if match_key:
                    same_event_exposure_amounts[(sport, match_key)] = (
                        same_event_exposure_amounts.get((sport, match_key), 0.0)
                        + exposure
                    )
                    if selection_key:
                        same_side_exposure_amounts[(sport, f"{match_key}|{selection_key}")] = (
                            same_side_exposure_amounts.get(
                                (sport, f"{match_key}|{selection_key}"), 0.0
                            )
                            + exposure
                        )

        context.update(
            {
                "governed_open_exposure_dollars": round(total_open_exposure, 2),
                "resting_order_exposure_dollars": round(total_resting, 2),
                "executed_unsettled_exposure_dollars": round(total_executed, 2),
                "remaining_daily_risk_budget_dollars": round(
                    max(0.0, max_daily_allocation - total_open_exposure), 2
                ),
                "peak_portfolio_value_dollars": round(portfolio_peak_value, 2),
                "current_portfolio_value_dollars": round(portfolio_current_value, 2),
                "drawdown_amount_dollars": round(drawdown_amount, 2),
                "drawdown_ratio": drawdown_ratio,
                "drawdown_state": drawdown_state,
                "risk_of_ruin_state": risk_of_ruin_state,
                "portfolio_guardrail_state": portfolio_guardrail_state,
                "portfolio_guardrail_reason_code": portfolio_guardrail_reason_code,
                "portfolio_guardrail_reason_detail": portfolio_guardrail_reason_detail,
                "sport_exposure_amounts": sport_exposure_amounts,
                "same_event_exposure_amounts": same_event_exposure_amounts,
                "same_side_exposure_amounts": same_side_exposure_amounts,
                "open_positions": normalized_open_positions,
            }
        )
        return context

    def get_last_risk_audit(self) -> List[Dict[str, Any]]:
        """Return the latest portfolio-risk approval audit rows."""
        return [dict(row) for row in self._last_risk_audit]

    def _record_risk_decision(
        self,
        opportunity: BetOpportunity,
        *,
        risk_context: Dict[str, Any],
        requested_bet_size: Optional[float],
        approved_bet_size: float,
        evidence_tier: str,
        concentration_state: str,
        existing_position_state: str,
        same_match_conflict: bool,
        rejection_reason_code: Optional[str],
        rejection_reason_detail: Optional[str],
    ) -> None:
        """Persist one runtime-visible risk decision row."""
        requested = round(requested_bet_size, 2) if requested_bet_size is not None else None
        approved = round(approved_bet_size, 2)
        payload = {
            "sport": opportunity.sport.upper(),
            "ticker": opportunity.ticker,
            "canonical_match_key": self._canonical_match_key(opportunity),
            "selection_key": self._selection_key(opportunity),
            "live_bankroll_dollars": round(
                self._coerce_float(
                    risk_context.get("live_bankroll_dollars", self.bankroll), self.bankroll
                ),
                2,
            ),
            "daily_risk_cap_dollars": round(
                self._coerce_float(
                    risk_context.get(
                        "daily_risk_cap_dollars",
                        self.bankroll * self.max_daily_risk_pct,
                    )
                ),
                2,
            ),
            "current_open_exposure_dollars": round(
                self._coerce_float(risk_context.get("governed_open_exposure_dollars")), 2
            ),
            "resting_order_exposure_dollars": round(
                self._coerce_float(risk_context.get("resting_order_exposure_dollars")), 2
            ),
            "executed_unsettled_exposure_dollars": round(
                self._coerce_float(
                    risk_context.get("executed_unsettled_exposure_dollars")
                ),
                2,
            ),
            "remaining_daily_risk_budget_dollars": round(
                self._coerce_float(
                    risk_context.get("remaining_daily_risk_budget_dollars"),
                    self.bankroll * self.max_daily_risk_pct,
                ),
                2,
            ),
            "peak_portfolio_value_dollars": round(
                self._coerce_float(
                    risk_context.get("peak_portfolio_value_dollars"), self.bankroll
                ),
                2,
            ),
            "current_portfolio_value_dollars": round(
                self._coerce_float(
                    risk_context.get("current_portfolio_value_dollars"), self.bankroll
                ),
                2,
            ),
            "drawdown_amount_dollars": round(
                self._coerce_float(risk_context.get("drawdown_amount_dollars")), 2
            ),
            "drawdown_ratio": self._coerce_float(risk_context.get("drawdown_ratio")),
            "drawdown_state": str(risk_context.get("drawdown_state") or "at_peak"),
            "risk_of_ruin_state": str(
                risk_context.get("risk_of_ruin_state") or "capital_available"
            ),
            "portfolio_guardrail_state": str(
                risk_context.get("portfolio_guardrail_state") or "eligible"
            ),
            "portfolio_guardrail_reason_code": risk_context.get(
                "portfolio_guardrail_reason_code"
            ),
            "portfolio_guardrail_reason_detail": risk_context.get(
                "portfolio_guardrail_reason_detail"
            ),
            "requested_bet_size_dollars": requested,
            "approved_bet_size_dollars": approved,
            "evidence_tier": evidence_tier,
            "concentration_state": concentration_state,
            "existing_position_state": existing_position_state,
            "same_match_conflict": same_match_conflict,
            "rejection_reason_code": rejection_reason_code,
            "rejection_reason_detail": rejection_reason_detail,
            "operator_semantics_version": risk_context.get(
                "operator_semantics_version", self.DEFAULT_OPERATOR_SEMANTICS_VERSION
            ),
        }
        self._last_risk_audit.append(payload)
        setattr(opportunity, "portfolio_risk_state", payload)
        if rejection_reason_code is not None:
            setattr(opportunity, "rejection_reason_code", rejection_reason_code)
            setattr(opportunity, "rejection_reason_detail", rejection_reason_detail)

    def _evaluate_portfolio_guardrail(
        self, risk_context: Dict[str, Any]
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """Return the portfolio-level guardrail outcome before approval."""
        guardrail_state = str(risk_context.get("portfolio_guardrail_state") or "eligible")
        if guardrail_state == "eligible":
            return guardrail_state, None, None
        return (
            guardrail_state,
            risk_context.get("portfolio_guardrail_reason_code"),
            risk_context.get("portfolio_guardrail_reason_detail"),
        )

    def _evaluate_evidence_gate(
        self, opportunity: BetOpportunity, *, enforce_governed_risk: bool
    ) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """Return evidence eligibility and any fail-closed reason."""
        contamination_reasons: List[str] = []
        for field_name in ("contamination_flag", "clv_contaminated_flag"):
            if self._coerce_bool(self._get_opportunity_value(opportunity, field_name)):
                contamination_reasons.append(field_name)
        clv_source_type = self._get_opportunity_value(opportunity, "clv_source_type")
        if clv_source_type in {"binary_result_placeholder", "missing_close", "unlinked_close"}:
            contamination_reasons.append(str(clv_source_type))
        contamination_reason = self._get_opportunity_value(
            opportunity, "contamination_reason"
        )
        if contamination_reason:
            contamination_reasons.append(str(contamination_reason))

        if contamination_reasons:
            return (
                False,
                "contaminated",
                "contaminated_evidence",
                "Evidence is contaminated: " + ", ".join(dict.fromkeys(contamination_reasons)),
            )

        evidence_tiers = [
            self._get_opportunity_value(opportunity, "clv_evidence_tier"),
            self._get_opportunity_value(opportunity, "calibration_evidence_tier"),
            self._get_opportunity_value(opportunity, "walk_forward_evidence_tier"),
        ]
        approval_grade_evidence = self._coerce_bool(
            self._get_opportunity_value(opportunity, "approval_grade_evidence")
        )
        has_approval_grade_tiers = all(
            tier == "approval_grade" for tier in evidence_tiers
        )

        if approval_grade_evidence or has_approval_grade_tiers:
            return True, "approval_grade", None, None

        if not enforce_governed_risk:
            return True, "descriptive_only", None, None

        return (
            False,
            "missing",
            "missing_evidence",
            "Approval-grade CLV, calibration, and walk-forward evidence is required.",
        )

    def _evaluate_existing_position_state(
        self, opportunity: BetOpportunity, risk_context: Dict[str, Any]
    ) -> Tuple[str, bool]:
        """Return same-match position state for the opportunity."""
        match_key = self._canonical_match_key(opportunity)
        selection_key = self._selection_key(opportunity)
        if not match_key:
            return "no_existing_position", False

        for row in risk_context.get("open_positions", []):
            if row.get("sport") != opportunity.sport.upper():
                continue
            if row.get("canonical_match_key") != match_key:
                continue
            status = str(row.get("position_status") or "")
            same_selection = row.get("selection_key") == selection_key
            if status in self.EXECUTED_UNSETTLED_STATUSES:
                return (
                    "executed_unsettled_same_side"
                    if same_selection
                    else "executed_unsettled_conflict",
                    True,
                )
            if status in self.RESTING_ORDER_STATUSES:
                return (
                    "resting_order_same_side"
                    if same_selection
                    else "resting_order_conflict",
                    True,
                )
            return "existing_match_conflict", True

        return "no_existing_position", False

    def _evaluate_concentration_state(
        self,
        opportunity: BetOpportunity,
        *,
        proposed_bet_size: float,
        risk_context: Dict[str, Any],
        allocated_by_sport: Dict[str, float],
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """Return concentration state and any governed concentration breach."""
        sport = opportunity.sport.upper()
        sport_exposure = self._coerce_float(
            risk_context.get("sport_exposure_amounts", {}).get(sport)
        ) + self._coerce_float(allocated_by_sport.get(sport))
        concentration_limit = risk_context.get("sport_concentration_limit_dollars")
        if concentration_limit is not None and sport_exposure + proposed_bet_size > float(
            concentration_limit
        ):
            return (
                "governed_limit_breached",
                "concentration_breach",
                f"{sport} exposure would exceed governed concentration limit.",
            )
        if concentration_limit is not None:
            return "within_governed_limit", None, None
        return "descriptive_only_no_governed_limit", None, None

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
                    edge, confidence, yes_ask, no_ask, bet_id,
                    canonical_game_id,
                    probability_source, evidence_state, evidence_state_reason,
                    evidence_state_source_artifact, governance_status,
                    clv_evidence_tier, calibration_evidence_tier,
                    walk_forward_evidence_tier, approval_grade_evidence,
                    sizing_eligible, abstain, abstention_reason
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
        self,
        opportunities: List[BetOpportunity],
        *,
        risk_context: Optional[Dict[str, Any]] = None,
        enforce_governed_risk: bool = False,
    ) -> List[BetOpportunity]:
        """Filter opportunities based on minimum thresholds."""
        self._last_risk_audit = []
        filtered = []
        stats = {"segment": 0, "edge": 0, "elo_prob": 0, "confidence": 0, "kelly": 0, "governance": 0}
        sport_confidence_stats = {}
        risk_context = risk_context or self._empty_risk_context(
            self.bankroll * self.max_daily_risk_pct
        )

        for opp in opportunities:
            # Check excluded segments
            confidence_str = opp.confidence if opp.confidence else "UNKNOWN"
            if (opp.sport.upper(), confidence_str.upper()) in self.excluded_segments:
                stats["segment"] += 1
                continue

            if opp.abstain or not opp.sizing_eligible:
                stats["governance"] += 1
                if enforce_governed_risk:
                    rejection_reason = opp.abstention_reason or "governed_sizing_ineligible"
                    self._record_risk_decision(
                        opp,
                        risk_context=risk_context,
                        requested_bet_size=None,
                        approved_bet_size=0.0,
                        evidence_tier="blocked",
                        concentration_state="descriptive_only_no_governed_limit",
                        existing_position_state="no_existing_position",
                        same_match_conflict=False,
                        rejection_reason_code=(
                            "contaminated_evidence"
                            if "contamin" in rejection_reason
                            else "missing_evidence"
                        ),
                        rejection_reason_detail=rejection_reason,
                    )
                continue

            evidence_allowed, evidence_tier, rejection_code, rejection_detail = (
                self._evaluate_evidence_gate(
                    opp, enforce_governed_risk=enforce_governed_risk
                )
            )
            if not evidence_allowed:
                stats["governance"] += 1
                self._record_risk_decision(
                    opp,
                    risk_context=risk_context,
                    requested_bet_size=None,
                    approved_bet_size=0.0,
                    evidence_tier=evidence_tier,
                    concentration_state="descriptive_only_no_governed_limit",
                    existing_position_state="no_existing_position",
                    same_match_conflict=False,
                    rejection_reason_code=rejection_code,
                    rejection_reason_detail=rejection_detail,
                )
                continue

            existing_position_state, same_match_conflict = (
                self._evaluate_existing_position_state(opp, risk_context)
            )
            if enforce_governed_risk and same_match_conflict:
                stats["governance"] += 1
                self._record_risk_decision(
                    opp,
                    risk_context=risk_context,
                    requested_bet_size=None,
                    approved_bet_size=0.0,
                    evidence_tier=evidence_tier,
                    concentration_state="descriptive_only_no_governed_limit",
                    existing_position_state=existing_position_state,
                    same_match_conflict=True,
                    rejection_reason_code="existing_position_conflict",
                    rejection_reason_detail=(
                        "Same-match resting order or executed-but-unsettled position already exists."
                    ),
                )
                continue

            # Check minimum edge
            if opp.edge < self.min_edge:
                stats["edge"] += 1
                continue

            # Skip bets where Elo probability is too low
            if opp.elo_prob <= self.min_elo_prob:
                stats["elo_prob"] += 1
                continue

            # Check Kelly fraction - must be positive for valid value bets
            if opp.kelly_fraction <= 0:
                stats["kelly"] += 1
                continue

            setattr(opp, "risk_evidence_tier", evidence_tier)
            setattr(opp, "existing_position_state", existing_position_state)
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
        if stats["elo_prob"] > 0:
            print(
                f"🚫 Excluded {stats['elo_prob']} due to low Elo probability (<= {self.min_elo_prob:.0%})"
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
        if stats["governance"] > 0:
            print(
                f"🚫 Excluded {stats['governance']} due to governed sizing ineligibility"
            )

    def calculate_portfolio_allocation(
        self,
        opportunities: List[BetOpportunity],
        *,
        risk_context: Optional[Dict[str, Any]] = None,
    ) -> List[PortfolioAllocation]:
        """Calculate optimal bet sizes for portfolio of opportunities."""
        if not opportunities:
            return []

        max_daily_allocation = self.bankroll * self.max_daily_risk_pct
        if risk_context is None:
            risk_context = self._empty_risk_context(max_daily_allocation)

        # Kelly-based allocation for positive EV strategy
        return self._allocate_kelly_sizing(
            opportunities,
            max_daily_allocation,
            risk_context=risk_context,
        )

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
        self,
        opportunities: List[BetOpportunity],
        max_daily_allocation: float,
        *,
        risk_context: Optional[Dict[str, Any]] = None,
    ) -> List[PortfolioAllocation]:
        """Kelly Criterion-based allocation."""
        sorted_opps = self._prioritize_sport_diversity(opportunities)
        allocations = []
        total_allocated = 0.0
        if risk_context is None:
            risk_context = self._empty_risk_context(max_daily_allocation)
        remaining_budget = self._coerce_float(
            risk_context.get("remaining_daily_risk_budget_dollars"),
            max_daily_allocation,
        )
        allocated_by_sport: Dict[str, float] = {}

        for opp in sorted_opps:
            kelly_size = (
                self.bankroll * opp.kelly_fraction * self.kelly_fraction
                if opp.kelly_fraction > 0
                else self.min_bet_size
            )

            bet_size = max(self.min_bet_size, min(self.max_bet_size, kelly_size))
            bet_size = min(self.bankroll * self.max_single_bet_pct, bet_size)

            evidence_tier = getattr(opp, "risk_evidence_tier", "descriptive_only")
            existing_position_state = getattr(
                opp, "existing_position_state", "no_existing_position"
            )
            (
                portfolio_guardrail_state,
                portfolio_guardrail_code,
                portfolio_guardrail_detail,
            ) = self._evaluate_portfolio_guardrail(risk_context)
            if portfolio_guardrail_code is not None:
                self._record_risk_decision(
                    opp,
                    risk_context=risk_context,
                    requested_bet_size=bet_size,
                    approved_bet_size=0.0,
                    evidence_tier=evidence_tier,
                    concentration_state=portfolio_guardrail_state,
                    existing_position_state=existing_position_state,
                    same_match_conflict=False,
                    rejection_reason_code=portfolio_guardrail_code,
                    rejection_reason_detail=portfolio_guardrail_detail,
                )
                continue
            concentration_state, rejection_code, rejection_detail = (
                self._evaluate_concentration_state(
                    opp,
                    proposed_bet_size=bet_size,
                    risk_context=risk_context,
                    allocated_by_sport=allocated_by_sport,
                )
            )
            if rejection_code is not None:
                self._record_risk_decision(
                    opp,
                    risk_context=risk_context,
                    requested_bet_size=bet_size,
                    approved_bet_size=0.0,
                    evidence_tier=evidence_tier,
                    concentration_state=concentration_state,
                    existing_position_state=existing_position_state,
                    same_match_conflict=False,
                    rejection_reason_code=rejection_code,
                    rejection_reason_detail=rejection_detail,
                )
                continue

            if total_allocated + bet_size > remaining_budget:
                remaining = remaining_budget - total_allocated
                if remaining < self.min_bet_size:
                    self._record_risk_decision(
                        opp,
                        risk_context=risk_context,
                        requested_bet_size=bet_size,
                        approved_bet_size=0.0,
                        evidence_tier=evidence_tier,
                        concentration_state=concentration_state,
                        existing_position_state=existing_position_state,
                        same_match_conflict=False,
                        rejection_reason_code="remaining_budget_breach",
                        rejection_reason_detail=(
                            "Governed open exposure leaves insufficient remaining daily risk budget."
                        ),
                    )
                    break
                approved_bet_size = remaining
                downgrade_reason_code = "remaining_budget_downgrade"
                downgrade_reason_detail = (
                    "Bet size was reduced to the governed remaining daily risk budget."
                )
            else:
                approved_bet_size = bet_size
                downgrade_reason_code = None
                downgrade_reason_detail = None

            allocations.append(
                PortfolioAllocation(
                    opportunity=opp,
                    bet_size=round(approved_bet_size, 2),
                    kelly_fraction=(
                        opp.kelly_fraction
                        if opp.kelly_fraction > 0
                        else DEFAULT_MIN_KELLY_FRACTION
                    ),
                    allocation_pct=approved_bet_size / self.bankroll,
                )
            )
            total_allocated += approved_bet_size
            allocated_by_sport[opp.sport.upper()] = (
                self._coerce_float(allocated_by_sport.get(opp.sport.upper()))
                + approved_bet_size
            )
            self._record_risk_decision(
                opp,
                risk_context=risk_context,
                requested_bet_size=bet_size,
                approved_bet_size=approved_bet_size,
                evidence_tier=evidence_tier,
                concentration_state=concentration_state,
                existing_position_state=existing_position_state,
                same_match_conflict=False,
                rejection_reason_code=downgrade_reason_code,
                rejection_reason_detail=downgrade_reason_detail,
            )

            if total_allocated >= remaining_budget:
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
        data_source = "files"
        risk_context = self._empty_risk_context(self.bankroll * self.max_daily_risk_pct)
        if use_database:
            print(f"📊 Loading opportunities from database for {date_str}...")
            opportunities = self.load_opportunities_from_database(date_str, sports)
            data_source = "database"
            if not opportunities:
                print(
                    "🚫 Governed recommendations unavailable from database; blocking live approvals."
                )
                return [], self._build_summary(
                    date_str,
                    opportunities,
                    [],
                    [],
                    use_database,
                    data_source=data_source,
                    approval_blocked_reason="governed_recommendations_unavailable",
                )
            try:
                risk_context = self._build_runtime_risk_context(
                    self.bankroll * self.max_daily_risk_pct
                )
            except RuntimeError as exc:
                print(f"🚫 {exc}")
                return [], self._build_summary(
                    date_str,
                    opportunities,
                    [],
                    [],
                    use_database,
                    data_source=data_source,
                    approval_blocked_reason="governed_risk_context_unavailable",
                )
        else:
            print(f"📊 Loading opportunities from files for {date_str}...")
            opportunities = self.load_opportunities_from_files(date_str, sports)

        filtered_opps = self.filter_opportunities(
            opportunities,
            risk_context=risk_context,
            enforce_governed_risk=(data_source == "database"),
        )
        allocations = self.calculate_portfolio_allocation(
            filtered_opps,
            risk_context=risk_context,
        )

        summary = self._build_summary(
            date_str,
            opportunities,
            filtered_opps,
            allocations,
            use_database,
            data_source=data_source,
        )
        return allocations, summary

    def _build_summary(
        self,
        date_str: str,
        opportunities: List[BetOpportunity],
        filtered_opps: List[BetOpportunity],
        allocations: List[PortfolioAllocation],
        use_database: bool,
        data_source: Optional[str] = None,
        approval_blocked_reason: Optional[str] = None,
    ) -> Dict:
        """Build summary statistics dictionary."""
        total_bet = sum(a.bet_size for a in allocations)
        total_expected_profit = sum(
            a.bet_size * a.opportunity.expected_value for a in allocations
        )

        summary = {
            "date": date_str,
            "bankroll": self.bankroll,
            "data_source": data_source
            if data_source is not None
            else ("database" if use_database and opportunities else "files"),
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
        if approval_blocked_reason is not None:
            summary["approval_blocked_reason"] = approval_blocked_reason
        return summary

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
