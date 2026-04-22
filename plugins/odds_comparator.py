"""
Compares Elo probabilities against unified market odds to find betting opportunities.
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import pandas as pd

from plugins.db_manager import DBManager, default_db
from naming_resolver import NamingResolver, NamingContext
from constants import (
    DEFAULT_MIN_EDGE,
    HIGH_CONFIDENCE_MIN_EDGE,
    MEDIUM_CONFIDENCE_MIN_EDGE,
    MAX_MARKET_PROBABILITY,
)


@dataclass
class BettingThresholds:
    """Edge thresholds for identifying positive-EV betting opportunities.

    Only ``min_edge`` and ``max_edge`` are used by ``BettingOutcome.is_value_bet``.
    Confidence levels (HIGH/MEDIUM/LOW) are derived from edge size via the
    ``HIGH_CONFIDENCE_MIN_EDGE`` / ``MEDIUM_CONFIDENCE_MIN_EDGE`` constants, and
    per-sport confidence floors are enforced separately by
    ``PortfolioOptimizer._get_sport_min_confidence``.
    """

    min_edge: float = DEFAULT_MIN_EDGE
    max_edge: float = 1.0


@dataclass
class BettingOpportunityConfig:
    """Configuration for finding betting opportunities.

    Args:
        sport: Sport name (e.g. ``"mlb"``).
        elo_system: Elo/ensemble model providing ``predict``/``get_rating``.
        thresholds: Edge thresholds for value-bet identification.
        date_str: Reference date in ``YYYY-MM-DD`` form. When ``None``, defaults
            to the current local date. Pass the Airflow ``ds`` here to keep
            "today" deterministic across DAG runs and timezone boundaries.
    """

    sport: str
    elo_system: Any
    thresholds: BettingThresholds
    date_str: Optional[str] = None


@dataclass
class MatchIdentity:
    """Identity of a match, including sport and canonical team names."""

    sport: str
    game_id: str
    canon_home: str
    canon_away: str


@dataclass
class BettingOutcome:
    """Represents a specific betting outcome (e.g. 'home' win) with all its metrics."""

    side: str
    team_name: str
    elo_prob: float
    market_prob: float
    market_odds: float
    edge: float

    @property
    def expected_value(self) -> float:
        """Calculates Expected Value (EV) for the outcome."""
        return self.edge / self.market_prob if self.market_prob > 0 else 0.0

    @property
    def kelly_fraction(self) -> float:
        """Calculates the Kelly Fraction for optimal bet sizing."""
        if 0 < self.market_prob < 1:
            p = self.elo_prob
            q = 1 - self.elo_prob
            b = self.market_odds - 1
            return max(0, (p * b - q) / b) if b > 0 else 0.0
        return 0.0

    @property
    def agreement_diff(self) -> float:
        """Calculates the difference between Elo and market probabilities."""
        return abs(self.elo_prob - self.market_prob)

    def determine_confidence(self, config: "BettingThresholds") -> str:
        """Determines the confidence level based on edge size.

        Larger positive edge = higher confidence in the value bet.

        Returns:
            Confidence level string: HIGH, MEDIUM, or LOW.
        """
        if self.edge >= HIGH_CONFIDENCE_MIN_EDGE:
            return "HIGH"
        elif self.edge >= MEDIUM_CONFIDENCE_MIN_EDGE:
            return "MEDIUM"
        else:
            return "LOW"

    def is_value_bet(self, config: "BettingThresholds") -> bool:
        """Determines if the outcome constitutes a positive expected value bet.

        A value bet exists when our Elo model's probability exceeds the market's
        implied probability by more than the minimum edge threshold, indicating
        the market is mispricing the outcome.

        Args:
            config: Betting thresholds configuration.

        Returns:
            True if the bet has positive expected value within acceptable bounds.
        """
        # Edge must exceed the minimum threshold for positive EV
        if self.edge < config.min_edge:
            return False

        # Reject suspiciously large edges (likely data errors or stale markets)
        if self.edge > config.max_edge:
            return False

        return True

    def to_opportunity(
        self, context: "GameContext", config: "BettingThresholds"
    ) -> Dict[str, Any]:
        """Builds the final opportunity dictionary with all metrics."""
        return {
            "sport": context.sport,
            "game_id": context.game_id,
            "home_team": context.home_team_name,
            "away_team": context.away_team_name,
            "home_rating": context.get_rating(context.elo_home),
            "away_rating": context.get_rating(context.elo_away),
            "bet_on": self.team_name,
            "side": self.side,
            "elo_prob": self.elo_prob,
            "market_prob": self.market_prob,
            "market_odds": self.market_odds,
            "bookmaker": "Kalshi",
            "ticker": context.tickers_by_bm.get("Kalshi", {}).get(self.side),
            "edge": self.edge,
            "expected_value": self.expected_value,
            "kelly_fraction": self.kelly_fraction,
            "sharp_confirmed": False,
            "confidence": self.determine_confidence(config),
            "agreement_diff": self.agreement_diff,
        }


@dataclass
class GameContext:
    """Encapsulates the context and state for a single game during analysis."""

    sport: str
    game_id: str
    home_team_name: str
    away_team_name: str
    source: str
    canon_home: str
    canon_away: str
    elo_home: str
    elo_away: str
    odds_by_bm: Dict[str, Dict[str, float]]
    tickers_by_bm: Dict[str, Dict[str, str]]
    elo_system: Any
    tour: Optional[str] = None
    home_win_prob: float = 0.0
    draw_prob: Optional[float] = None
    away_win_prob: float = 0.0

    def calculate_probabilities(self) -> bool:
        """Calculates Elo probabilities for this game context."""
        try:
            sport_lower = self.sport.lower()
            if sport_lower == "tennis":
                # Determine tour from Kalshi ticker
                kalshi_ticker = (
                    self.tickers_by_bm.get("Kalshi", {}).get("home", "") or ""
                )
                if "KXATP" in kalshi_ticker.upper() or "ATP" in self.game_id.upper():
                    self.tour = "atp"
                elif "KXWTA" in kalshi_ticker.upper() or "WTA" in self.game_id.upper():
                    self.tour = "wta"
                else:
                    self.tour = "atp"
                self.home_win_prob = self.elo_system.predict(
                    self.elo_home, self.elo_away, tour=self.tour
                )
                self.away_win_prob = 1 - self.home_win_prob
            elif hasattr(self.elo_system, "predict_3way") and sport_lower in [
                "epl",
                "ligue1",
            ]:
                probs = self.elo_system.predict_3way(self.elo_home, self.elo_away)
                self.home_win_prob = probs["home"]
                self.draw_prob = probs["draw"]
                self.away_win_prob = probs["away"]
            else:
                self.home_win_prob = self.elo_system.predict(
                    self.elo_home, self.elo_away
                )
                self.away_win_prob = 1 - self.home_win_prob
            return True
        except Exception as e:
            print(f"Error calculating probabilities for {self.game_id}: {e}")
            return False

    def evaluate(self, config: BettingThresholds) -> List[Dict[str, Any]]:
        """Evaluates this game for betting opportunities based on context and thresholds."""
        opportunities = []
        outcomes = self._prepare_outcomes()

        for side, team_name, elo_prob in outcomes:
            opp = self._evaluate_outcome(side, team_name, elo_prob, config)
            if opp:
                opportunities.append(opp)

        return opportunities

    def _prepare_outcomes(self) -> List[tuple[str, str, float]]:
        """Prepares list of outcomes (side, team_name, elo_prob) to evaluate."""
        outcomes = [("home", self.home_team_name, self.home_win_prob)]
        if self.draw_prob is not None:
            outcomes.append(("draw", "Draw", self.draw_prob))
        outcomes.append(("away", self.away_team_name, self.away_win_prob))
        return outcomes

    def _evaluate_outcome(
        self, side: str, team_name: str, elo_prob: float, config: BettingThresholds
    ) -> Optional[Dict[str, Any]]:
        """Evaluates a single outcome for a betting opportunity."""
        kalshi_odds = self.odds_by_bm.get("Kalshi", {})
        if side not in kalshi_odds:
            return None

        market_odds = kalshi_odds[side]
        if market_odds <= 1.0:
            return None

        market_prob = 1 / market_odds
        if market_prob > MAX_MARKET_PROBABILITY:
            return None

        edge = elo_prob - market_prob

        outcome = BettingOutcome(
            side=side,
            team_name=team_name,
            elo_prob=elo_prob,
            market_prob=market_prob,
            market_odds=market_odds,
            edge=edge,
        )

        if not outcome.is_value_bet(config):
            return None

        return outcome.to_opportunity(self, config)

    def get_rating(self, elo_name: str) -> float:
        """Helper to get Elo rating based on sport and tour."""
        if self.sport.lower() != "tennis":
            return self.elo_system.get_rating(elo_name)
        return self.elo_system.get_rating(elo_name, tour=self.tour)


class OddsComparator:
    """
    Compares internal Elo probabilities with best available market odds.
    """

    def __init__(self, db_manager: DBManager = default_db):
        self.db = db_manager

    def _get_games(self, sport: str, date_str: Optional[str] = None) -> pd.DataFrame:
        """Fetches upcoming games for a sport from unified_games.

        Args:
            sport: Sport identifier (case-insensitive).
            date_str: Reference date in ``YYYY-MM-DD`` form. Defaults to the
                current local date when ``None``. Pass the Airflow ``ds`` to
                keep "today" deterministic across runs and timezones.
        """
        today = date_str or datetime.now().strftime("%Y-%m-%d")
        query = """
            SELECT game_id, game_date, home_team_name, away_team_name, status
            FROM unified_games
            WHERE sport = :sport
              AND game_date >= :today
              AND status NOT IN ('Final', 'Finalized', 'OFF', 'Closed')
            ORDER BY game_date
        """
        return self.db.fetch_df(query, {"sport": sport.upper(), "today": today})

    def get_best_odds(self, game_id: str) -> Dict[str, Dict]:
        """
        Retrieves the best available odds for a game from PostgreSQL.
        Returns a dictionary with 'home', 'away', and 'draw' best odds.
        """
        try:
            result = {}
            for side in ["home", "away", "draw"]:
                df = self.db.fetch_df(
                    """
                    SELECT bookmaker, price, last_update
                    FROM game_odds
                    WHERE game_id = :game_id AND outcome_name = :side
                    ORDER BY price DESC
                    LIMIT 1
                """,
                    {"game_id": game_id, "side": side},
                )

                if not df.empty:
                    row = df.iloc[0]
                    result[side] = {
                        "bookmaker": row["bookmaker"],
                        "decimal_odds": float(row["price"]),
                        "last_update": row["last_update"],
                    }
            return result
        except Exception as e:
            print(f"Error fetching best odds for {game_id}: {e}")
            return {}

    def get_all_odds(self, game_id: str) -> List[Dict]:
        """
        Retrieves all available odds for a game.
        """
        return self.db.fetch_df(
            """
            SELECT bookmaker, outcome_name, price, last_update, external_id
            FROM game_odds
            WHERE game_id = :game_id
        """,
            {"game_id": game_id},
        ).to_dict("records")

    def _resolve_game_context(
        self, sport: str, row: pd.Series, elo_system: Any
    ) -> Optional[GameContext]:
        """Resolves naming, odds, and creates a GameContext for a game."""
        game_id = row["game_id"]
        source = self._get_source(game_id)

        # Resolve Canonical Names
        canon_home = self._resolve_name(
            NamingContext(sport=sport, source=source, name=row["home_team_name"])
        )
        canon_away = self._resolve_name(
            NamingContext(sport=sport, source=source, name=row["away_team_name"])
        )

        # Resolve Elo Names
        elo_home = self._resolve_name(
            NamingContext(sport=sport, source="elo", name=canon_home)
        )
        elo_away = self._resolve_name(
            NamingContext(sport=sport, source="elo", name=canon_away)
        )

        # Get and organize odds
        match = MatchIdentity(sport, game_id, canon_home, canon_away)
        odds_data = self._organize_odds(match)
        if not odds_data:
            return None

        odds_by_bm, tickers_by_bm = odds_data

        if "Kalshi" not in odds_by_bm:
            return None

        return GameContext(
            sport=sport,
            game_id=game_id,
            home_team_name=row["home_team_name"],
            away_team_name=row["away_team_name"],
            source=source,
            canon_home=canon_home,
            canon_away=canon_away,
            elo_home=elo_home,
            elo_away=elo_away,
            odds_by_bm=odds_by_bm,
            tickers_by_bm=tickers_by_bm,
            elo_system=elo_system,
        )

    def _get_source(self, game_id: str) -> str:
        """Resolves the source of the game ID."""
        if "odds_api" in game_id.lower():
            return "the_odds_api"
        return "kalshi"  # Unified games default

    def _resolve_name(self, context: NamingContext) -> str:
        """Resolves a team name using the NamingResolver."""
        return NamingResolver.resolve(context) or context.name

    def _organize_odds(
        self, match: MatchIdentity
    ) -> Optional[tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, str]]]]:
        """Fetches and organizes odds for a game."""
        all_odds = self.get_all_odds(match.game_id)
        if not all_odds:
            return None

        odds_by_bm = {}
        tickers_by_bm = {}
        for o in all_odds:
            bm = o["bookmaker"]
            outcome = self._resolve_outcome(match, o["outcome_name"])

            if bm not in odds_by_bm:
                odds_by_bm[bm] = {}
            odds_by_bm[bm][outcome] = float(o["price"])

            if bm not in tickers_by_bm:
                tickers_by_bm[bm] = {}
            tickers_by_bm[bm][outcome] = o.get("external_id")

        return odds_by_bm, tickers_by_bm

    def _resolve_outcome(self, match: MatchIdentity, outcome: str) -> str:
        """Resolves a named outcome to 'home', 'away', or 'draw'."""
        if outcome in ["home", "away", "draw"]:
            return outcome

        canon_outcome = (
            NamingResolver.resolve(
                NamingContext(sport=match.sport, source="the_odds_api", name=outcome)
            )
            or outcome
        )
        if canon_outcome == match.canon_home:
            return "home"
        elif canon_outcome == match.canon_away:
            return "away"
        elif "draw" in outcome.lower():
            return "draw"

        return outcome

    def find_opportunities(
        self,
        config: BettingOpportunityConfig,
    ) -> List[Dict[str, Any]]:
        """
        Identifies betting opportunities using positive Expected Value (EV) strategy.
        Bets when our Elo model finds the market is mispricing a team.

        Args:
            config: Configuration for finding betting opportunities

        Returns:
            List of betting opportunity dictionaries
        """
        opportunities = []

        try:
            games_df = self._get_games(config.sport, config.date_str)
            print(
                f"🔍 Analyzing {len(games_df)} {config.sport.upper()} games for value bets..."
            )

            for _, row in games_df.iterrows():
                # 1. Resolve context
                ctx = self._resolve_game_context(config.sport, row, config.elo_system)
                if not ctx:
                    continue

                # 2. Calculate probabilities
                if not ctx.calculate_probabilities():
                    continue

                # 3. Evaluate outcomes
                game_opps = ctx.evaluate(config.thresholds)
                opportunities.extend(game_opps)

            return opportunities

        except Exception as e:
            print(f"Error finding opportunities: {e}")
            import traceback

            traceback.print_exc()
            return []
