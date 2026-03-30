"""Shared types and functions for portfolio optimization.

This module contains dataclasses and utility functions shared between
portfolio optimization components to avoid circular imports.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from plugins.expected_value_mixin import ExpectedValueMixin
from plugins.constants import KELLY_FRACTION


# Betting parameter constants
DEFAULT_MARKET_ASK_PRICE = 50.0  # Default yes/no ask price when market data unavailable
ELO_BLEND_WEIGHT = 0.7  # Weight for Elo probability in blended probability (70%)
BETMGM_BLEND_WEIGHT = 0.3  # Weight for BetMGM probability in blended probability (30%)
MAX_DAILY_RISK_PCT = 0.25  # 25% maximum daily risk exposure
MAX_BET_SIZE = 100.0  # Maximum bet size in dollars
MAX_SINGLE_BET_PCT = 0.10  # 10% maximum of bankroll for single bet
MIN_EDGE_REQUIRED = 0.03  # Minimum 3% positive edge required (positive EV)
MIN_BET_SIZE = 2.0  # Minimum bet size in dollars


@dataclass
class BetOpportunity(ExpectedValueMixin):
    """Represents a single bet opportunity."""

    sport: str
    ticker: str
    bet_on: str  # "home" or "away"
    team: str
    opponent: str
    home_team: str = ""
    away_team: str = ""
    elo_prob: float = 0.5  # Elo-predicted win probability
    market_prob: float = 0.5  # Market-implied probability
    edge: float = 0.0  # elo_prob - market_prob
    confidence: str = "MEDIUM"  # "HIGH" or "MEDIUM"
    yes_ask: float = DEFAULT_MARKET_ASK_PRICE  # Market ask price (for buying)
    no_ask: float = DEFAULT_MARKET_ASK_PRICE  # Market ask price (for buying)
    home_rating: float = 0.0
    away_rating: float = 0.0
    game_time: Optional[str] = None
    game_id: Optional[str] = None
    betmgm_prob: Optional[float] = None
    bet_id: Optional[str] = None

    @property
    def kelly_fraction(self) -> float:
        """Calculate Kelly Criterion fraction for this bet."""
        # Kelly formula: f* = (bp - q) / b
        # where b = decimal odds - 1, p = our probability, q = 1 - p
        if self.market_prob <= 0 or self.market_prob >= 1:
            return 0.0

        # Decimal odds = 1 / market_prob
        b = (1.0 / self.market_prob) - 1.0
        p = self.elo_prob
        q = 1.0 - p

        if b <= 0:
            return 0.0

        kelly = (b * p - q) / b
        return max(kelly, 0.0)

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
    max_daily_risk_pct: float = MAX_DAILY_RISK_PCT  # 25% max daily risk
    kelly_fraction: float = KELLY_FRACTION  # Conservative Kelly fraction (20%)
    min_bet_size: float = MIN_BET_SIZE
    max_bet_size: float = MAX_BET_SIZE
    max_single_bet_pct: float = MAX_SINGLE_BET_PCT  # 10% max single bet
    min_edge: float = (
        MIN_EDGE_REQUIRED  # Minimum 3% positive edge required (positive EV)
    )
    min_confidence: float = 0.0
    excluded_segments: Optional[List[str]] = None
    elo_blend_weight: float = ELO_BLEND_WEIGHT  # Weight for Elo probability in blended probability (default: 70%)
    betmgm_blend_weight: float = BETMGM_BLEND_WEIGHT  # Weight for BetMGM probability in blended probability (default: 30%)


def extract_game_date(game_id: str) -> Optional[str]:
    """Extract game date from game_id like TENNIS_20260129_ALCARAZ_ZVEREV."""
    if not game_id or "_" not in game_id:
        return None

    parts = game_id.split("_")
    if len(parts) < 2:
        return None

    date_str = parts[1]
    if len(date_str) != 8 or not date_str.isdigit():
        return None

    try:
        year = date_str[0:4]
        month = date_str[4:6]
        day = date_str[6:8]
        return f"{year}-{month}-{day}"
    except (IndexError, ValueError):
        return None


def extract_ticker_date(ticker: str) -> Optional[str]:
    """Extract date from Kalshi ticker like KXATPMATCH-26JAN22CERRUB-RUB."""
    if not ticker or "-" not in ticker:
        return None

    # Try to find date pattern in ticker
    import re

    # Pattern for dates like 26JAN22
    date_pattern = r"(\d{2}[A-Z]{3}\d{2})"
    match = re.search(date_pattern, ticker)
    if not match:
        return None

    date_str = match.group(1)
    try:
        from datetime import datetime

        # Kalshi ticker date format is YYMONDD (e.g., 26MAR24 = 2026-03-24)
        dt = datetime.strptime(date_str, "%y%b%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def estimate_asks_from_market_prob(market_prob: float) -> Tuple[int, int]:
    """Estimate yes_ask and no_ask prices from market probability."""
    if market_prob <= 0 or market_prob >= 1:
        return int(DEFAULT_MARKET_ASK_PRICE), int(DEFAULT_MARKET_ASK_PRICE)

    yes_ask = int(round(market_prob * 100))
    no_ask = 100 - yes_ask
    return yes_ask, no_ask
