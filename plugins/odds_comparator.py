"""
Compares Elo probabilities against unified market odds to find betting opportunities.
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from functools import lru_cache
from datetime import timedelta

import numpy as np
import pandas as pd

from plugins.db_manager import DBManager, default_db
from plugins.probability_calibration import (
    GovernedProbabilityDecision,
    publish_governed_probability_decision,
)
from naming_resolver import NamingResolver, NamingContext
from constants import (
    DEFAULT_MIN_EDGE,
    HIGH_CONFIDENCE_MIN_EDGE,
    MEDIUM_CONFIDENCE_MIN_EDGE,
    MAX_MARKET_PROBABILITY,
    MAX_EDGE_THRESHOLD,
)
from plugins.pricing_governance import (
    GovernedPriceQuote,
    PriceRole,
    build_single_venue_price_decision,
    select_best_executable_quote,
)

SHARP_PRO_EDGE_THRESHOLD = 0.15


def _detect_tennis_tour(
    game_id: str, tickers_by_bm: Optional[Dict[str, Dict[str, str]]] = None
) -> str:
    """Infer ATP/WTA tour from Kalshi tickers first, then game ID."""
    kalshi_tickers = tickers_by_bm.get("Kalshi", {}) if tickers_by_bm else {}
    ticker_text = " ".join(
        str(value or "") for value in kalshi_tickers.values()
    ).upper()
    game_id_upper = str(game_id or "").upper()

    if "KXATP" in ticker_text or "ATP" in game_id_upper:
        return "ATP"
    if "KXWTA" in ticker_text or "WTA" in game_id_upper:
        return "WTA"
    return "ATP"


@lru_cache(maxsize=1)
def _load_tennis_probability_history() -> pd.DataFrame:
    """Load tennis history once for optional probability-model inference."""
    try:
        from plugins.elo.tennis_probability_model import load_history_from_db

        return load_history_from_db()
    except Exception as exc:
        print(f"⚠️ Tennis probability history unavailable; using Elo fallback: {exc}")
        return pd.DataFrame()


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
    enforce_governance: bool = False


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
        opportunity = {
            "sport": context.normalized_sport,
            "game_id": context.game_id,
            "home_team": context.home_team_name,
            "away_team": context.away_team_name,
            "home_rating": context.get_rating(context.elo_home),
            "away_rating": context.get_rating(context.elo_away),
            "bet_on": context.contract_bet_on(self.side, self.team_name),
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
        if context.is_mlb:
            signal = context.market_signal_for_side(self.side)
            pro_edge = signal.get("pro_edge")
            reverse_line_movement = signal.get("reverse_line_movement")
            opportunity.update(
                {
                    "sharp_confirmed": bool(reverse_line_movement)
                    or (
                        pro_edge is not None
                        and float(pro_edge) >= SHARP_PRO_EDGE_THRESHOLD
                    ),
                    "pro_edge": pro_edge,
                    "reverse_line_movement": reverse_line_movement,
                    "market_signal_source": signal.get("source"),
                    "market_signal_availability": signal.get("availability"),
                }
            )
        if context.is_epl:
            opportunity["schema_version"] = "v1"
            opportunity["payload_kind"] = "bet_opportunity"
            if context.uses_persistence_contract:
                opportunity["recommendation_date"] = context.recommendation_date
                opportunity["bet_id"] = context.build_contract_bet_id(
                    self.side, opportunity["ticker"]
                )
        if context.is_tennis and context.tour:
            opportunity["tour"] = str(context.tour).upper()
        if context.governed_decision:
            opportunity.update(context.governed_decision.to_payload())
        return opportunity


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
    surface: Optional[str] = None
    market_signals_by_side: Optional[Dict[str, Dict[str, Any]]] = None
    enforce_governance: bool = False
    home_win_prob: float = 0.0
    draw_prob: Optional[float] = None
    away_win_prob: float = 0.0
    governed_decision: Optional[GovernedProbabilityDecision] = None

    @property
    def is_epl(self) -> bool:
        return self.sport.lower() == "epl"

    @property
    def is_mlb(self) -> bool:
        return self.sport.lower() == "mlb"

    @property
    def is_tennis(self) -> bool:
        return self.sport.lower() == "tennis"

    @property
    def normalized_sport(self) -> str:
        if self.is_epl:
            return "EPL"
        if self.is_mlb:
            return "MLB"
        if self.is_tennis:
            return "TENNIS"
        return self.sport

    @property
    def recommendation_date(self) -> str:
        if self.is_epl:
            parts = self.game_id.split("-")
            if len(parts) >= 4:
                return "-".join(parts[1:4])
        if self.is_tennis:
            # game_id format: TENNIS_<TOUR>_<YYYY-MM-DD>_<home_slug>_<away_slug>
            parts = self.game_id.split("_")
            if len(parts) >= 3:
                candidate = parts[2]
                if len(candidate) == 10 and candidate[4] == "-" and candidate[7] == "-":
                    return candidate
        return datetime.now().strftime("%Y-%m-%d")

    @property
    def uses_persistence_contract(self) -> bool:
        ticker = self.tickers_by_bm.get("Kalshi", {})
        return not any(
            isinstance(value, str)
            and value.upper().endswith(("-HOME", "-DRAW", "-AWAY"))
            for value in ticker.values()
        )

    def contract_bet_on(self, side: str, team_name: str) -> str:
        return side if self.is_epl else team_name

    def build_contract_bet_id(self, side: str, ticker: Optional[str]) -> str:
        if ticker:
            return f"EPL-{self.recommendation_date}-{ticker}-{side}"
        return f"{self.game_id}-{side}"

    def calculate_probabilities(self) -> bool:
        """Calculates Elo probabilities for this game context."""
        try:
            sport_lower = self.sport.lower()
            if sport_lower == "mlb" and getattr(
                self.elo_system, "requires_governed_predictions", False
            ):
                if not self._apply_governed_mlb_probabilities():
                    return self._finalize_governance()
            elif sport_lower == "tennis":
                self.tour = _detect_tennis_tour(self.game_id, self.tickers_by_bm)
                predict_with_payload = getattr(
                    type(self.elo_system), "predict_with_payload", None
                )
                if callable(predict_with_payload):
                    payload = predict_with_payload(
                        self.elo_system, self.elo_home, self.elo_away, tour=self.tour
                    )
                    tennis_result = self._maybe_apply_tennis_probability_model(
                        calibrated_elo_prob=float(payload["calibrated_prob_a"])
                    )
                    self.home_win_prob = float(tennis_result["probability"])
                    if self.enforce_governance:
                        self.governed_decision = publish_governed_probability_decision(
                            self.normalized_sport,
                            probability_source=str(tennis_result["probability_source"]),
                            evidence_state_source_artifact=str(
                                tennis_result["artifact_ref"]
                            ),
                        )
                else:
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
            return self._finalize_governance()
        except Exception as e:
            print(f"Error calculating probabilities for {self.game_id}: {e}")
            return False

    def _finalize_governance(self) -> bool:
        """Apply governed validation rules after probabilities are available."""
        if not self.enforce_governance:
            return True
        if self.governed_decision is not None:
            return True

        if self.is_tennis:
            self.governed_decision = publish_governed_probability_decision(
                self.normalized_sport,
                probability_source="tennis_calibrated_elo",
                evidence_state_source_artifact=f"tennis_calibrated_elo:{str(self.tour or 'ATP').upper()}",
            )
            return True

        if self.is_epl:
            self.governed_decision = publish_governed_probability_decision(
                self.normalized_sport,
                probability_source="governed_abstention",
                abstain=True,
                abstention_reason="runtime_consumer_mismatch, governed_artifact_not_consumed",
                evidence_state_source_artifact="epl_offline_ensemble:validation_state_publication",
            )
            return True

        if self.sport.lower() == "ligue1":
            governed_source = getattr(self.elo_system, "governed_probability_source", None)
            if governed_source == "ligue1_live_ensemble":
                self.governed_decision = publish_governed_probability_decision(
                    self.normalized_sport,
                    probability_source="ligue1_live_ensemble",
                    evidence_state_source_artifact="ligue1_live_ensemble:runtime_adapter",
                )
            else:
                self.governed_decision = publish_governed_probability_decision(
                    self.normalized_sport,
                    probability_source="governed_abstention",
                    abstain=True,
                    abstention_reason="governed_artifact_not_consumed",
                    evidence_state_source_artifact="ligue1_live_ensemble:validation_state_publication",
                )
            return True

        if self.normalized_sport.upper() in {"NBA", "NHL", "NFL", "NCAAB", "WNCAAB"}:
            self.governed_decision = publish_governed_probability_decision(
                self.normalized_sport.upper(),
                probability_source="governed_abstention",
                abstain=True,
                abstention_reason="missing_market_clv_evidence, missing_calibration_evidence, missing_walk_forward_evidence, missing_governed_artifact_lineage",
                evidence_state_source_artifact="governed_validation_publication",
            )
        return True

    def _apply_governed_mlb_probabilities(self) -> bool:
        """Use governed MLB prediction rows instead of runtime Elo inference."""
        if not hasattr(self.elo_system, "get_governed_probabilities"):
            print(
                f"⚠️  Skipping {self.game_id}: MLB governed mode requires persisted predictions"
            )
            if self.enforce_governance:
                self.governed_decision = publish_governed_probability_decision(
                    self.normalized_sport,
                    probability_source="mlb_model_predictions",
                    abstain=True,
                    abstention_reason="missing_governed_probability_artifact",
                    evidence_state_source_artifact="mlb_model_predictions",
                )
            return False
        probabilities = self.elo_system.get_governed_probabilities(self.game_id)
        if not probabilities:
            print(
                f"⚠️  Skipping {self.game_id}: missing governed MLB predictions for run"
            )
            if self.enforce_governance:
                self.governed_decision = publish_governed_probability_decision(
                    self.normalized_sport,
                    probability_source="mlb_model_predictions",
                    abstain=True,
                    abstention_reason="missing_governed_probability_artifact",
                    evidence_state_source_artifact="mlb_model_predictions",
                )
            return False
        home_win_prob = probabilities.get("home")
        away_win_prob = probabilities.get("away")
        if home_win_prob is None or away_win_prob is None:
            print(
                f"⚠️  Skipping {self.game_id}: incomplete governed MLB predictions for run"
            )
            return False
        total = float(home_win_prob) + float(away_win_prob)
        if not np.isfinite(total) or abs(total - 1.0) > 1e-6:
            print(
                f"⚠️  Skipping {self.game_id}: governed MLB probabilities must sum to 1.0"
            )
            return False
        self.home_win_prob = float(home_win_prob)
        self.away_win_prob = float(away_win_prob)
        self.draw_prob = None
        if self.enforce_governance:
            metadata = getattr(self.elo_system, "governed_prediction_metadata", {})
            artifact_ref = (
                f"mlb_model_predictions:{metadata.get('model_version')}@"
                f"{metadata.get('run_date')}"
            )
            self.governed_decision = publish_governed_probability_decision(
                self.normalized_sport,
                probability_source="mlb_model_predictions",
                evidence_state_source_artifact=artifact_ref,
            )
        return True

    def _maybe_apply_tennis_probability_model(
        self, calibrated_elo_prob: float
    ) -> Dict[str, Any]:
        """Prefer enabled tennis feature model, otherwise calibrated Elo."""
        try:
            from plugins.elo.tennis_probability_model import (
                DEFAULT_MODEL_PATH,
                predict_with_artifact,
            )

            if self.enforce_governance and not getattr(
                self.elo_system, "enable_governed_tennis_overlay", False
            ):
                return {
                    "probability": calibrated_elo_prob,
                    "probability_source": "tennis_calibrated_elo",
                    "artifact_ref": f"tennis_calibrated_elo:{str(self.tour or 'ATP').upper()}",
                }
            if not DEFAULT_MODEL_PATH.exists():
                return {
                    "probability": calibrated_elo_prob,
                    "probability_source": "tennis_calibrated_elo",
                    "artifact_ref": f"tennis_calibrated_elo:{str(self.tour or 'ATP').upper()}",
                }
            result = predict_with_artifact(
                player_a=self.elo_home,
                player_b=self.elo_away,
                tour=str(self.tour or "ATP"),
                surface=str(self.surface or "Hard"),
                as_of_date=self.recommendation_date,
                history=_load_tennis_probability_history(),
                calibrated_elo_prob_a=calibrated_elo_prob,
                model_path=DEFAULT_MODEL_PATH,
            )
            return {
                "probability": float(result.prob_a),
                "probability_source": "tennis_feature_model_overlay",
                "artifact_ref": str(result.model_version or "tennis_probability_model_v2"),
            }
        except Exception as exc:
            print(
                "⚠️ Tennis probability model unavailable for "
                f"{self.game_id}; using calibrated Elo fallback: {exc}"
            )
            return {
                "probability": calibrated_elo_prob,
                "probability_source": "tennis_calibrated_elo",
                "artifact_ref": f"tennis_calibrated_elo:{str(self.tour or 'ATP').upper()}",
            }

    def evaluate(self, config: BettingThresholds) -> List[Dict[str, Any]]:
        """Evaluates this game for betting opportunities based on context and thresholds."""
        if self.enforce_governance and self.governed_decision and self.governed_decision.abstain:
            return [self._build_abstention_payload()]
        opportunities = []
        outcomes = self._prepare_outcomes()

        for side, team_name, elo_prob in outcomes:
            opp = self._evaluate_outcome(side, team_name, elo_prob, config)
            if opp:
                opportunities.append(opp)

        return opportunities

    def _build_abstention_payload(self) -> Dict[str, Any]:
        """Emit an explicit governed abstention row for persistence/reporting."""
        ticker = self.tickers_by_bm.get("Kalshi", {}).get("home") or self.tickers_by_bm.get(
            "Kalshi", {}
        ).get("away")
        payload = {
            "sport": self.normalized_sport,
            "game_id": self.game_id,
            "home_team": self.home_team_name,
            "away_team": self.away_team_name,
            "home_rating": self.get_rating(self.elo_home),
            "away_rating": self.get_rating(self.elo_away),
            "bet_on": self.home_team_name,
            "side": "home",
            "elo_prob": float(self.home_win_prob or 0.5),
            "market_prob": 0.5,
            "market_odds": 2.0,
            "bookmaker": "Kalshi",
            "ticker": ticker,
            "edge": 0.0,
            "expected_value": 0.0,
            "kelly_fraction": 0.0,
            "sharp_confirmed": False,
            "confidence": "LOW",
            "agreement_diff": 0.0,
        }
        if self.governed_decision:
            payload.update(self.governed_decision.to_payload())
        return payload

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

        # MLB and TENNIS contracts enforce a hard 0.40 edge ceiling regardless
        # of the caller-supplied ``BettingThresholds.max_edge``. This guards
        # against data-error spikes leaking into the recommendation pipeline.
        # The clamp is intentionally limited to MLB and TENNIS to avoid
        # changing other sports' historical behaviour (covered by existing
        # tests using max_edge=1.0).
        if (self.is_mlb or self.is_tennis) and edge > MAX_EDGE_THRESHOLD:
            return None

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

    def market_signal_for_side(self, side: str) -> Dict[str, Any]:
        """Return latest market-signal metadata for an outcome side."""
        if not self.market_signals_by_side:
            return {}
        return self.market_signals_by_side.get(side, {})


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
            df = self.db.fetch_df(
                """
                SELECT bookmaker, outcome_name, price, last_update, loaded_at, external_id, odds_id
                FROM game_odds
                WHERE game_id = :game_id
            """,
                {"game_id": game_id},
            )
            if df.empty:
                return {}

            result = {}
            for side in ["home", "away", "draw"]:
                side_rows = df[df["outcome_name"] == side]
                if side_rows.empty:
                    continue

                quotes = [
                    GovernedPriceQuote(
                        role=PriceRole.EXECUTABLE,
                        decimal_price=float(row["price"]),
                        bookmaker=str(row["bookmaker"]),
                        market_ticker=row.get("external_id"),
                        selection_key=side,
                        observed_at=row.get("last_update"),
                        loaded_at=row.get("loaded_at"),
                        payload_ref=row.get("odds_id") or row.get("external_id"),
                    )
                    for _, row in side_rows.iterrows()
                    if float(row["price"]) > 0
                ]
                if not quotes:
                    continue
                parsed_times = []
                for quote in quotes:
                    if isinstance(quote.observed_at, datetime):
                        parsed_times.append(quote.observed_at)
                    elif quote.observed_at:
                        parsed = pd.to_datetime(quote.observed_at, utc=True, errors="coerce")
                        if not pd.isna(parsed):
                            parsed_times.append(parsed.to_pydatetime())
                as_of = max(parsed_times, default=datetime.now())

                decision = build_single_venue_price_decision(
                    executable_quote=max(quotes, key=lambda quote: quote.decimal_price),
                    best_quote_candidates=quotes,
                )
                best_quote = select_best_executable_quote(
                    quotes,
                    as_of=as_of,
                    max_age=timedelta(hours=4),
                )
                selected = best_quote or decision.executable_quote
                result[side] = {
                    "bookmaker": selected.bookmaker,
                    "decimal_odds": float(selected.decimal_price),
                    "last_update": selected.observed_at,
                    "price_role": selected.role.value,
                    "freshness_result": selected.freshness_result,
                    "payload_ref": selected.payload_ref,
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

        market_signals_by_side = (
            self._get_latest_mlb_market_signals(game_id)
            if sport.lower() == "mlb"
            else None
        )

        # Safety guard: never bet when either team lacks a real Elo rating.
        # get_rating() silently inserts a 1500 default for unknown teams; we
        # must use has_real_rating() to distinguish "computed" from "default".
        if not self._both_teams_have_real_ratings(
            elo_system, sport, elo_home, elo_away, game_id, tickers_by_bm
        ):
            return None

        if sport.lower() == "mlb" and getattr(
            elo_system, "requires_governed_predictions", False
        ):
            self._attach_governed_mlb_prediction_loader(
                elo_system=elo_system,
                game_id=game_id,
                run_date=getattr(elo_system, "governed_run_date", row["game_date"]),
            )

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
            surface=(
                self._infer_tennis_surface(
                    player_a=elo_home,
                    player_b=elo_away,
                    as_of_date=str(row["game_date"]),
                )
                if sport.lower() == "tennis"
                else None
            ),
            market_signals_by_side=market_signals_by_side,
            enforce_governance=getattr(self, "_enforce_governance", False),
        )

    def _attach_governed_mlb_prediction_loader(
        self,
        *,
        elo_system: Any,
        game_id: str,
        run_date: Any,
    ) -> None:
        """Attach a fail-closed governed MLB probability loader to the Elo object."""

        def _loader(target_game_id: str) -> Optional[Dict[str, float]]:
            if str(target_game_id) != str(game_id):
                return None
            probabilities = self._get_governed_mlb_probabilities(
                game_id=str(target_game_id),
                run_date=str(run_date)[:10],
            )
            setattr(
                elo_system,
                "governed_prediction_metadata",
                getattr(self, "_latest_governed_mlb_metadata", {}),
            )
            return probabilities

        setattr(elo_system, "get_governed_probabilities", _loader)

    def _get_governed_mlb_probabilities(
        self,
        *,
        game_id: str,
        run_date: str,
    ) -> Optional[Dict[str, float]]:
        """Return latest complete governed MLB model predictions for a game/run date."""
        try:
            df = self.db.fetch_df(
                """
                WITH latest_model AS (
                    SELECT model_version
                    FROM mlb_model_predictions
                    WHERE game_id = :game_id
                      AND run_date = CAST(:run_date AS DATE)
                      AND market_name = 'moneyline'
                    GROUP BY model_version
                    ORDER BY MAX(created_at) DESC, model_version DESC
                    LIMIT 1
                )
                SELECT
                    outcome_name,
                    model_prob,
                    abstain,
                    abstention_reason,
                    model_version,
                    run_date,
                    created_at
                FROM mlb_model_predictions
                WHERE game_id = :game_id
                  AND run_date = CAST(:run_date AS DATE)
                  AND market_name = 'moneyline'
                  AND model_version = (SELECT model_version FROM latest_model)
                """,
                {"game_id": game_id, "run_date": run_date},
            )
        except Exception as exc:
            print(f"⚠️ MLB governed predictions unavailable for {game_id}: {exc}")
            return None

        if df is None or df.empty:
            return None

        filtered = df.copy()
        if "game_id" in filtered.columns:
            filtered = filtered.loc[filtered["game_id"].astype(str) == str(game_id)]
        if "run_date" in filtered.columns:
            filtered = filtered.loc[
                pd.to_datetime(filtered["run_date"], errors="coerce")
                .dt.strftime("%Y-%m-%d")
                .eq(run_date)
            ]
        if "market_name" in filtered.columns:
            filtered = filtered.loc[filtered["market_name"].astype(str) == "moneyline"]
        if filtered.empty:
            return None

        if "model_version" in filtered.columns:
            if "created_at" in filtered.columns:
                created_at = pd.to_datetime(filtered["created_at"], errors="coerce")
                ranked = (
                    filtered.assign(_created_at=created_at)
                    .groupby("model_version", as_index=False)["_created_at"]
                    .max()
                    .sort_values(
                        ["_created_at", "model_version"], ascending=[False, False]
                    )
                )
                latest_model_version = str(ranked.iloc[0]["model_version"])
            else:
                latest_model_version = str(filtered["model_version"].astype(str).max())
            filtered = filtered.loc[
                filtered["model_version"].astype(str) == latest_model_version
            ]
        if filtered.empty:
            return None

        if (
            "abstain" in filtered.columns
            and filtered["abstain"].fillna(False).astype(bool).any()
        ):
            return None

        if "created_at" in filtered.columns:
            filtered = filtered.assign(
                _created_at=pd.to_datetime(filtered["created_at"], errors="coerce")
            ).sort_values("_created_at", ascending=False)

        filtered = filtered.drop_duplicates(subset=["outcome_name"], keep="first")
        if (
            "abstain" in filtered.columns
            and filtered["abstain"].fillna(False).astype(bool).any()
        ):
            return None

        probabilities = {
            str(row["outcome_name"]): float(row["model_prob"])
            for _, row in filtered.iterrows()
            if row["outcome_name"] in {"home", "away"}
        }
        if set(probabilities) != {"home", "away"}:
            return None
        first_row = filtered.iloc[0]
        self._latest_governed_mlb_metadata = {
            "model_version": str(first_row.get("model_version") or ""),
            "run_date": str(first_row.get("run_date") or run_date)[:10],
        }
        return probabilities

    def _get_latest_mlb_market_signals(self, game_id: str) -> Dict[str, Dict[str, Any]]:
        """Return latest MLB market-signal row by outcome side."""
        try:
            df = self.db.fetch_df(
                """
                SELECT DISTINCT ON (outcome_name)
                    outcome_name,
                    pro_edge,
                    reverse_line_movement,
                    source,
                    CASE
                        WHEN ticket_pct IS NULL OR money_pct IS NULL THEN 'unavailable'
                        ELSE 'available'
                    END AS availability
                FROM mlb_market_signals
                WHERE game_id = :game_id
                ORDER BY outcome_name, snapshot_at DESC
                """,
                {"game_id": game_id},
            )
        except Exception as exc:
            print(f"⚠️ MLB market signals unavailable for {game_id}: {exc}")
            return {}

        if df is None or df.empty:
            return {}

        return {
            str(row["outcome_name"]): {
                "pro_edge": (
                    None if pd.isna(row["pro_edge"]) else float(row["pro_edge"])
                ),
                "reverse_line_movement": bool(row["reverse_line_movement"]),
                "source": row.get("source"),
                "availability": row.get("availability"),
            }
            for _, row in df.iterrows()
        }

    @staticmethod
    def _normalize_tennis_name(name: str) -> str:
        """Strip periods and collapse whitespace for fuzzy name matching."""
        return " ".join(name.replace(".", "").split())

    def _infer_tennis_surface(
        self,
        *,
        player_a: str,
        player_b: str,
        as_of_date: str,
    ) -> str:
        """Infer the likely surface for an upcoming tennis matchup.

        Prefer the most recent surface that both players have appeared on
        (best indicator of the current tour surface).  Otherwise, fall back
        to the surface from their most recent head-to-head meeting, then the
        single most recent observed player surface.
        """
        norm_a = self._normalize_tennis_name(player_a)
        norm_b = self._normalize_tennis_name(player_b)
        try:
            df = self.db.fetch_df(
                """
                SELECT game_date, surface, winner, loser
                FROM tennis_games
                WHERE game_date <= CAST(:as_of_date AS DATE)
                  AND surface IS NOT NULL
                  AND surface <> ''
                  AND (
                        winner = :player_a
                     OR loser = :player_a
                     OR winner = :player_b
                     OR loser = :player_b
                     OR REPLACE(winner, '.', '') = :player_a_norm
                     OR REPLACE(loser, '.', '') = :player_a_norm
                     OR REPLACE(winner, '.', '') = :player_b_norm
                     OR REPLACE(loser, '.', '') = :player_b_norm
                  )
                ORDER BY game_date DESC
                LIMIT 60
                """,
                {
                    "player_a": player_a,
                    "player_b": player_b,
                    "player_a_norm": norm_a,
                    "player_b_norm": norm_b,
                    "as_of_date": as_of_date,
                },
            )
        except Exception as exc:
            print(f"⚠️ Tennis surface lookup unavailable; defaulting to Hard: {exc}")
            return "Hard"

        if df is None or df.empty:
            print(
                f"⚠️ No historical surface data found for {player_a} / {player_b} "
                f"(norm: {norm_a} / {norm_b}) — defaulting to Hard"
            )
            return "Hard"

        rows = [
            {
                "surface": str(row["surface"]).strip().title(),
                "winner": str(row["winner"]),
                "loser": str(row["loser"]),
                "winner_norm": self._normalize_tennis_name(str(row["winner"])),
                "loser_norm": self._normalize_tennis_name(str(row["loser"])),
            }
            for _, row in df.iterrows()
            if str(row.get("surface") or "").strip()
        ]
        if not rows:
            return "Hard"

        # Priority: 1) shared surface (best indicator of current tour),
        # 2) H2H surface (specific meeting), 3) most recent overall.
        player_a_surfaces = {
            row["surface"]
            for row in rows
            if row["winner_norm"] == norm_a or row["loser_norm"] == norm_a
        }
        player_b_surfaces = {
            row["surface"]
            for row in rows
            if row["winner_norm"] == norm_b or row["loser_norm"] == norm_b
        }
        shared_surfaces = player_a_surfaces & player_b_surfaces
        if shared_surfaces:
            shared_recent = next(
                (row["surface"] for row in rows if row["surface"] in shared_surfaces),
                None,
            )
            if shared_recent:
                return shared_recent

        h2h = next(
            (
                row["surface"]
                for row in rows
                if {row["winner_norm"], row["loser_norm"]} == {norm_a, norm_b}
            ),
            None,
        )
        if h2h:
            return h2h

        return rows[0]["surface"]

    def _both_teams_have_real_ratings(
        self,
        elo_system: Any,
        sport: str,
        elo_home: str,
        elo_away: str,
        game_id: str,
        tickers_by_bm: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> bool:
        """Check that both teams have real (non-default) Elo ratings.

        Args:
            elo_system: The Elo system to query.
            sport: Sport identifier (used for tennis tour detection).
            elo_home: Elo-canonical name for the home team/player.
            elo_away: Elo-canonical name for the away team/player.
            game_id: Game identifier (for logging only).
            tickers_by_bm: Market tickers by bookmaker/outcome, used to infer
                tennis ATP/WTA tour when generic game IDs do not include tour.

        Returns:
            True if both teams have ratings computed from real game data,
            False if either team is unknown to the Elo system.
        """
        if sport.lower() == "tennis":
            tour = _detect_tennis_tour(game_id, tickers_by_bm)
            home_ok = elo_system.has_real_rating(elo_home, tour=tour)
            away_ok = elo_system.has_real_rating(elo_away, tour=tour)
        else:
            home_ok = elo_system.has_real_rating(elo_home)
            away_ok = elo_system.has_real_rating(elo_away)

        if not home_ok:
            print(
                f"⚠️  Skipping {game_id}: no real Elo for home team '{elo_home}' "
                f"— would have used default 1500. Refusing to bet."
            )
        if not away_ok:
            print(
                f"⚠️  Skipping {game_id}: no real Elo for away team '{elo_away}' "
                f"— would have used default 1500. Refusing to bet."
            )

        return home_ok and away_ok

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
            self._enforce_governance = bool(config.enforce_governance)
            games_df = self._get_games(config.sport, config.date_str)
            print(
                f"🔍 Analyzing {len(games_df)} {config.sport.upper()} games for value bets..."
            )
            if config.sport.lower() == "mlb" and getattr(
                config.elo_system, "requires_governed_predictions", False
            ):
                setattr(
                    config.elo_system,
                    "governed_run_date",
                    str(config.date_str or datetime.now().strftime("%Y-%m-%d")),
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
