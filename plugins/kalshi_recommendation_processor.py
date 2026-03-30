"""
Kalshi Recommendation Processor - Handles processing of bet recommendations.

Extracted from KalshiBetting class to reduce class size and improve maintainability.
Responsibility: Process bet recommendations, validate them, and prepare for betting.
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from plugins.constants import MIN_EDGE_FOR_BET
from plugins.kalshi_betting import BettingConfig
from plugins.betting_types import GameIdentity


@dataclass
class RecommendationValidationResult:
    """Result of validating a bet recommendation."""

    should_process: bool
    reason: Optional[str] = None
    market: Optional[Dict] = None
    bet_side: Optional[str] = None


class KalshiRecommendationProcessor:
    """Processes bet recommendations for Kalshi betting."""

    def __init__(self, kalshi_betting):
        """
        Initialize with a KalshiBetting instance.

        Args:
            kalshi_betting: Instance of KalshiBetting for API operations
        """
        self.kalshi_betting = kalshi_betting

    def process_bet_recommendations(
        self,
        recommendations: List[Dict],
        *args,
        config: Optional[BettingConfig] = None,
        **kwargs,
    ) -> Dict:
        """Process bet recommendations using provided configuration.

        Preferred usage: process_bet_recommendations(recommendations, config=BettingConfig(...))

        Legacy usage (deprecated): process_bet_recommendations(recommendations, min_confidence=0.75, ...)
        """
        config = self._create_betting_config_from_kwargs(config, kwargs)
        trade_date = self._get_trade_date_from_config(config)

        balance, portfolio_value = self.kalshi_betting.get_balance()
        self._print_balance_info(balance, portfolio_value)

        return self._process_recommendations_loop(
            recommendations, config, trade_date, balance
        )

    def _create_betting_config_from_kwargs(
        self, config: Optional[BettingConfig], kwargs: Dict[str, Any]
    ) -> BettingConfig:
        """Create BettingConfig from kwargs if config not provided.

        Handles legacy keyword argument support with deprecation warning.

        Args:
            config: Existing BettingConfig or None
            kwargs: Keyword arguments for legacy support

        Returns:
            BettingConfig instance
        """
        if config is not None:
            return config

        if not kwargs:
            return BettingConfig()

        import warnings

        warnings.warn(
            "Keyword arguments for process_bet_recommendations are deprecated. "
            "Use config=BettingConfig(...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        min_confidence = kwargs.pop("min_confidence", 0.0)
        min_edge = kwargs.pop("min_edge", MIN_EDGE_FOR_BET)
        dry_run = kwargs.pop("dry_run", False)
        trade_date = kwargs.pop("trade_date", None)
        sport_filter = kwargs.pop("sport_filter", None)

        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {list(kwargs.keys())}")

        return BettingConfig(
            min_confidence=min_confidence,
            min_edge=min_edge,
            dry_run=dry_run,
            trade_date=trade_date,
            sport_filter=sport_filter,
        )

    def _get_trade_date_from_config(self, config: BettingConfig) -> str:
        """Extract trade date from config, defaulting to current UTC date."""
        if config.trade_date:
            return config.trade_date
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _print_balance_info(self, balance: float, portfolio_value: float) -> None:
        """Print balance and portfolio value information."""
        print(
            f"\n💰 Starting balance: ${balance:.2f}\n📊 Portfolio value: ${portfolio_value:.2f}\n"
        )

    def _process_recommendations_loop(
        self,
        recommendations: List[Dict],
        config: BettingConfig,
        trade_date: str,
        initial_balance: float,
    ) -> Dict[str, Any]:
        """Process list of bet recommendations in a loop."""
        placed, skipped, errors = [], [], []
        balance = initial_balance

        for rec in recommendations:
            res, skip, err, balance = self._process_recommendation_item(
                rec, config, balance, trade_date
            )
            if res:
                placed.append(res)
            if skip:
                skipped.append({"rec": rec, "reason": skip})
            if err:
                errors.append(err)
            time.sleep(1)

        return {
            "placed": placed,
            "skipped": skipped,
            "errors": errors,
            "balance": balance,
        }

    def _process_recommendation_item(
        self,
        rec: Dict[str, Any],
        config: BettingConfig,
        balance: float,
        trade_date: str,
    ) -> Tuple[Optional[Dict], Optional[str], Optional[str], float]:
        """Process a single recommendation item."""
        should_process, skip_reason = self._should_process_recommendation(rec, config)
        if not should_process:
            return None, skip_reason, None, balance

        is_valid, error_msg, market_details = self._validate_recommendation(rec)
        if not is_valid:
            return None, None, error_msg, balance

        # market_details is guaranteed to be non-None after validation
        assert market_details is not None, (
            "market_details should not be None after validation"
        )

        should_skip, skip_reason = self._check_game_started(rec, market_details)
        if should_skip:
            return None, skip_reason, None, balance

        bet_size = self.kalshi_betting.calculate_bet_size(rec, balance)
        # Note: BetSizeCalculator already ensures bet_size >= MIN_BET_SIZE
        # so we don't need to check it here

        sport = rec.get("sport", "NBA")
        ticker = rec.get("ticker", "")
        side = self._determine_bet_side(rec, sport, ticker, market_details)
        match_info, bet_player = self._format_match_info(rec, sport)

        from .kalshi_betting import BetContext

        ctx = BetContext(
            rec,
            ticker,
            side,
            bet_size,
            rec.get("elo_prob", 0),
            rec.get("edge", 0),
            match_info,
            bet_player,
            config.dry_run,
            trade_date,
            balance,
        )

        res, err, balance = ctx.process(self.kalshi_betting)
        return res, None, err, balance

    def _should_process_recommendation(
        self, rec: Dict, config: BettingConfig
    ) -> Tuple[bool, Optional[str]]:
        """Check if a recommendation should be processed."""
        if config.sport_filter and rec.get("sport", "").upper() not in [
            s.upper() for s in config.sport_filter
        ]:
            return False, "Sport filter"

        if rec.get("elo_prob", 0) < config.min_confidence:
            return False, "Low confidence"

        if rec.get("edge", 0) < config.min_edge:
            return False, "Low edge"

        return True, None

    def _validate_recommendation(
        self, rec: Dict
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Validate recommendation and get market details."""
        # Check for required fields
        if "ticker" not in rec:
            return False, "Missing ticker", None

        ticker = rec["ticker"]
        market = self.kalshi_betting.get_market_details(ticker)

        if not market:
            return False, f"Market not found: {ticker}", None

        return True, None, market

    def _check_game_started(
        self, rec: Dict, market: Dict
    ) -> Tuple[bool, Optional[str]]:
        """Check if game has started or market is closed."""
        sport = rec.get("sport", "NBA")

        if sport.lower() != "tennis":
            game = GameIdentity(rec["home_team"], rec["away_team"], sport)
            if not self.kalshi_betting.verify_game_not_started(game):
                return True, "Game already started"

        if self.kalshi_betting.is_game_started(market):
            return True, "Market closed"

        return False, None

    def _determine_bet_side(
        self, rec: Dict, sport: str, ticker: str, market: Dict
    ) -> str:
        """Determine bet side (YES or NO)."""
        if sport.lower() == "tennis":
            ticker_parts = ticker.split("-")
            if len(ticker_parts) >= 3:
                yes_abbr = ticker_parts[-1].upper()
                bet_on = rec["bet_on"].upper()
                return (
                    "yes"
                    if any(w[:3].upper() == yes_abbr[:3] for w in bet_on.split())
                    else "no"
                )
            return "yes" if rec["bet_on"] in market.get("title", "") else "no"
        return "yes" if rec["bet_on"] == "home" else "no"

    def _format_match_info(self, rec: Dict, sport: str) -> Tuple[str, str]:
        """Format match info for display."""
        if sport.lower() == "tennis":
            return rec.get("matchup", "Unknown match"), rec["bet_on"]
        return f"{rec['away_team']} @ {rec['home_team']}", rec["bet_on"]
