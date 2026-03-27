"""Parsers for portfolio optimization.

This module contains parsers for converting data from various sources
(database rows, JSON files) into BetOpportunity objects.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd

from plugins.constants import CENTS_PER_DOLLAR
from plugins.portfolio_types import BetOpportunity


@dataclass
class MarketAskParams:
    """Parameter object for market probability calculation from ask prices.

    Addresses Primitive Obsession smell by grouping related parameters
    that appear repeatedly in _parse_tennis_market_prob and
    _derive_market_prob_from_asks methods.
    """

    yes_ask: float
    no_ask: float
    bet_direction: str
    fallback_prob: float = 0.5

    def derive_market_prob(self) -> float:
        """Derive market probability from ask prices.

        Uses the appropriate ask price (yes_ask for home bets, no_ask for away bets)
        to calculate the market-implied probability. If the primary ask is 0,
        tries to calculate from the opposite ask if available.
        """
        if self.bet_direction == "home":
            if self.yes_ask > 0:
                return self.yes_ask / CENTS_PER_DOLLAR
            elif self.no_ask > 0:
                # Calculate from no_ask: market_prob = 1 - (no_ask / CENTS_PER_DOLLAR)
                return 1.0 - (self.no_ask / CENTS_PER_DOLLAR)
            else:
                return self.fallback_prob
        else:  # away bet
            if self.no_ask > 0:
                return self.no_ask / CENTS_PER_DOLLAR
            elif self.yes_ask > 0:
                # Calculate from yes_ask: market_prob = yes_ask / CENTS_PER_DOLLAR
                # For away bet, market_prob is probability of away winning
                # which is 1 - probability of home winning
                return 1.0 - (self.yes_ask / CENTS_PER_DOLLAR)
            else:
                return self.fallback_prob


class OpportunityParser(ABC):
    """Abstract base for parsing bet opportunities from different sources."""

    @abstractmethod
    def parse(self, data: Dict, sport: str) -> Optional[BetOpportunity]:
        """Parse a single record into a BetOpportunity."""
        pass

    def _get_numeric(self, data: Dict, key: str, default: float) -> float:
        """Safely get a numeric value from dict, handling NaN."""
        value = data.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default


class DatabaseRowParser(OpportunityParser):
    """Parse bet opportunities from database row (pandas Series)."""

    def parse(self, row: pd.Series, sport: str) -> Optional[BetOpportunity]:
        """Parse a database row into a BetOpportunity.

        Recommendations without tickers are still parsed — ticker
        resolution happens separately in OpportunityLoader.
        """
        # Parse sport-specific fields
        team, opponent, bet_direction = self._parse_teams(row, sport)
        yes_ask, no_ask, market_prob = self._parse_prices(row, sport, bet_direction)

        return BetOpportunity(
            sport=sport,
            ticker=row.get("ticker") or "",
            bet_on=bet_direction,
            team=team,
            opponent=opponent,
            home_team=row.get("home_team", ""),
            away_team=row.get("away_team", ""),
            elo_prob=self._get_numeric(row, "elo_prob", 0.5),
            market_prob=market_prob,
            edge=self._get_numeric(row, "edge", 0.0),
            confidence=row.get("confidence", "MEDIUM"),
            yes_ask=yes_ask,
            no_ask=no_ask,
            home_rating=self._get_numeric(row, "home_rating", 0.0),
            away_rating=self._get_numeric(row, "away_rating", 0.0),
            game_id=row.get("game_id"),
            bet_id=row.get("bet_id"),
        )

    def _parse_teams(self, row: pd.Series, sport: str) -> Tuple[str, str, str]:
        """Extract team, opponent, and bet direction based on sport."""
        home_team = row.get("home_team", "")
        away_team = row.get("away_team", "")
        bet_on = row.get("bet_on", "home")

        if bet_on == "home":
            return home_team, away_team, "home"
        else:
            return away_team, home_team, "away"

    def _parse_prices(
        self, row: pd.Series, sport: str, bet_direction: str
    ) -> Tuple[float, float, float]:
        """Extract yes_ask, no_ask, and market_prob."""
        yes_ask = self._get_numeric(row, "yes_ask", 50.0)
        no_ask = self._get_numeric(row, "no_ask", 50.0)
        market_prob = self._get_numeric(row, "market_prob", 0.5)

        # Ensure valid probabilities
        if market_prob <= 0 or market_prob >= 1:
            market_prob = yes_ask / CENTS_PER_DOLLAR if yes_ask > 0 else 0.5

        return yes_ask, no_ask, market_prob


class JsonFileParser(OpportunityParser):
    """Parse bet opportunities from JSON file dict."""

    def parse(self, data: Dict, sport: str) -> Optional[BetOpportunity]:
        """Parse a JSON dict into a BetOpportunity."""
        ticker = data.get("ticker")
        if not ticker:
            return None

        # Generate game_id if not present
        game_id = self._generate_game_id(data, sport)

        # Parse sport-specific fields
        team, opponent, bet_direction = self._parse_teams(data, sport)
        yes_ask, no_ask, market_prob = self._parse_prices(data, sport, bet_direction)

        return BetOpportunity(
            sport=sport,
            ticker=ticker,
            bet_on=bet_direction,
            team=team,
            opponent=opponent,
            home_team=data.get("home_team", ""),
            away_team=data.get("away_team", ""),
            elo_prob=self._get_numeric(data, "elo_prob", 0.5),
            market_prob=market_prob,
            edge=self._get_numeric(data, "edge", 0.0),
            confidence=data.get("confidence", "MEDIUM"),
            yes_ask=yes_ask,
            no_ask=no_ask,
            home_rating=self._get_numeric(data, "home_rating", 0.0),
            away_rating=self._get_numeric(data, "away_rating", 0.0),
            game_id=game_id,
            bet_id=data.get("bet_id"),
        )

    def _generate_game_id(self, data: Dict, sport: str) -> Optional[str]:
        """Generate game_id from available data."""
        game_id = data.get("game_id")
        if game_id:
            return game_id

        # Try to construct from available data
        home_team = data.get("home_team", "")
        away_team = data.get("away_team", "")
        game_date = data.get("game_date", "")

        # Also check game_time if game_date is not available
        if not game_date:
            game_time = data.get("game_time", "")
            if game_time and "T" in game_time:
                # Extract date from ISO format: "2026-03-02T19:00:00"
                game_date = game_time.split("T")[0]

        if home_team and away_team and game_date:
            # Convert date from YYYY-MM-DD to YYYYMMDD
            date_part = game_date.replace("-", "")
            return f"{sport.upper()}_{date_part}_{home_team}_{away_team}"

        return None

    def _parse_teams(self, data: Dict, sport: str) -> Tuple[str, str, str]:
        """Extract team, opponent, and bet direction based on sport."""
        home_team = data.get("home_team", "")
        away_team = data.get("away_team", "")
        bet_on = data.get("bet_on", "home")

        if bet_on == "home":
            return home_team, away_team, "home"
        else:
            return away_team, home_team, "away"

    def _parse_prices(
        self, data: Dict, sport: str, bet_direction: str
    ) -> Tuple[float, float, float]:
        """Extract yes_ask, no_ask, and market_prob."""
        yes_ask = self._get_numeric(data, "yes_ask", 50.0)
        no_ask = self._get_numeric(data, "no_ask", 50.0)
        market_prob = self._get_numeric(data, "market_prob", 0.5)

        # For tennis, use specialized parsing
        if sport == "tennis":
            ask_params = MarketAskParams(
                yes_ask=yes_ask,
                no_ask=no_ask,
                bet_direction=bet_direction,
                fallback_prob=0.5,
            )
            market_prob = self._parse_tennis_market_prob(data, ask_params)

        # If market_prob is invalid, derive from asks
        if market_prob <= 0 or market_prob >= 1:
            ask_params = MarketAskParams(
                yes_ask=yes_ask,
                no_ask=no_ask,
                bet_direction=bet_direction,
                fallback_prob=0.5,
            )
            market_prob = ask_params.derive_market_prob()

        return yes_ask, no_ask, market_prob

    def _parse_tennis_market_prob(
        self, data: Dict, ask_params: MarketAskParams
    ) -> float:
        """Parse market probability for tennis matches.

        Tennis has special logic because we need to determine which player
        corresponds to the 'yes' side based on the bet_on field.
        """
        # Try to get from data first
        market_prob = self._get_numeric(data, "market_prob", 0.0)
        if 0 < market_prob < 1:
            return market_prob

        team = data.get("bet_on", "")
        player1 = data.get("player1", "")

        if team and player1 and (team in player1 or player1 in team):
            # Betting on player1 (yes side)
            return (
                ask_params.yes_ask / CENTS_PER_DOLLAR
                if ask_params.yes_ask > 0
                else ask_params.fallback_prob
            )
        else:
            # Betting on player2 (no side)
            return (
                ask_params.no_ask / CENTS_PER_DOLLAR
                if ask_params.no_ask > 0
                else ask_params.fallback_prob
            )
