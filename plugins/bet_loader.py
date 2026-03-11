"""
Load bet recommendations into PostgreSQL for historical analysis.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from plugins.db_manager import DBManager, default_db
from plugins.utils import create_entity_upserter
from plugins.sql_params_mixin import SqlParamsMixin


@dataclass
class BetContext:
    """Context information for creating bet recommendations."""

    sport: str
    date_str: str
    index: int


@dataclass
class BetData:
    """Processed bet data for creating recommendations."""

    home_team: str
    away_team: str
    ticker: Optional[str] = None
    side: str = "unknown"
    bet_on: str = "unknown"
    elo_prob: float = 0.0
    market_prob: float = 0.0
    edge: float = 0.0
    expected_value: Optional[float] = None
    kelly_fraction: Optional[float] = None
    confidence: str = "unknown"
    home_rating: Optional[float] = None
    away_rating: Optional[float] = None
    yes_ask: Optional[int] = None
    no_ask: Optional[int] = None

    def computed_expected_value(self) -> Optional[float]:
        """Calculate expected value if not provided."""
        if self.expected_value is not None:
            return self.expected_value
        if self.market_prob > 0:
            return self.edge / self.market_prob
        return None

    def computed_kelly_fraction(self) -> Optional[float]:
        """Calculate Kelly fraction if not provided."""
        if self.kelly_fraction is not None:
            return self.kelly_fraction
        if 0 < self.market_prob < 1:
            p = self.elo_prob
            q = 1 - p
            b = (1 / self.market_prob) - 1
            if b > 0:
                return max(0, (p * b - q) / b)
        return 0.0

    def generate_id(self, context: BetContext) -> str:
        """Generate a stable ID for this bet."""
        if self.ticker:
            return f"{context.sport}_{context.date_str}_{self.ticker}_{self.side}"
        return f"{context.sport}_{context.date_str}_{self.home_team}_{self.away_team}_{self.side}_{context.index}"

    def to_recommendation(self, context: BetContext) -> "BetRecommendation":
        """Convert this BetData to a full BetRecommendation with context."""
        return BetRecommendation(
            bet_id=self.generate_id(context),
            sport=context.sport,
            recommendation_date=context.date_str,
            home_team=self.home_team,
            away_team=self.away_team,
            home_rating=self.home_rating,
            away_rating=self.away_rating,
            bet_on=self.bet_on,
            elo_prob=self.elo_prob,
            market_prob=self.market_prob,
            edge=self.edge,
            expected_value=self.computed_expected_value(),
            kelly_fraction=self.computed_kelly_fraction(),
            confidence=self.confidence,
            yes_ask=self.yes_ask,
            no_ask=self.no_ask,
            ticker=self.ticker,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BetData":
        """Create BetData from a raw dictionary with flexible key matching."""
        # Extract fields with helper methods
        side = _extract_side(data)
        home, away = _extract_teams(data)

        # Extract numeric fields with safe conversion
        elo_prob = _extract_float(data, "elo_prob")
        market_prob = _extract_float(data, "market_prob")
        edge = _extract_float(data, "edge")

        # Extract optional fields
        expected_value = _extract_optional_float(data, "expected_value")
        kelly_fraction = _extract_optional_float(data, "kelly_fraction")
        home_rating = _extract_optional_float(data, "home_rating")
        away_rating = _extract_optional_float(data, "away_rating")

        # Extract other fields
        ticker = data.get("ticker")
        confidence = data.get("confidence", "unknown")
        yes_ask = data.get("yes_ask")
        no_ask = data.get("no_ask")

        # Construct the object
        return cls(
            home_team=home,
            away_team=away,
            ticker=ticker,
            side=side,
            bet_on=side,
            elo_prob=elo_prob,
            market_prob=market_prob,
            edge=edge,
            expected_value=expected_value,
            kelly_fraction=kelly_fraction,
            confidence=confidence,
            home_rating=home_rating,
            away_rating=away_rating,
            yes_ask=yes_ask,
            no_ask=no_ask,
        )


def _extract_side(data: Dict[str, Any]) -> str:
    """Extract side/bet_on from data with flexible key matching."""
    return data.get("side", data.get("bet_on", "unknown"))


def _extract_teams(data: Dict[str, Any]) -> tuple[str, str]:
    """Extract home and away teams from data with flexible key matching."""
    home = data.get("home_team", data.get("player", "Unknown"))
    away = data.get("away_team", data.get("opponent", "Unknown"))
    return home, away


def _extract_float(data: Dict[str, Any], key: str) -> float:
    """Extract a float value from data with safe conversion."""
    val = data.get(key)
    try:
        return float(val) if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


def _extract_optional_float(data: Dict[str, Any], key: str) -> Optional[float]:
    """Extract an optional float value from data."""
    val = data.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


@dataclass
class BetRecommendation(SqlParamsMixin):
    """Data class representing a single bet recommendation."""

    bet_id: str
    sport: str
    recommendation_date: str
    home_team: str
    away_team: str
    bet_on: str
    elo_prob: float
    market_prob: float
    edge: float
    confidence: str
    home_rating: Optional[float] = None
    away_rating: Optional[float] = None
    expected_value: Optional[float] = None
    kelly_fraction: Optional[float] = None
    yes_ask: Optional[int] = None
    no_ask: Optional[int] = None
    ticker: Optional[str] = None

    def to_sql_params(self) -> Dict[str, Any]:
        """Convert dataclass to dictionary suitable for SQL parameters.

        Override to ensure 'date_str' is never in the output - the database
        column is 'recommendation_date'.
        """
        params = super().to_sql_params()

        # DEBUG: Log what we got from super()
        # print(f"DEBUG: to_sql_params() - params from super: {list(params.keys())}")

        # Ensure date_str is never in params - some code paths might add it
        if "date_str" in params:
            # If recommendation_date is missing but date_str exists, copy the value
            if "recommendation_date" not in params:
                params["recommendation_date"] = params["date_str"]
            # Remove date_str since the table column is recommendation_date
            del params["date_str"]

        # Double-check: ensure recommendation_date is present
        if "recommendation_date" not in params:
            # This should never happen, but if it does, use a default
            print(f"⚠️  WARNING: recommendation_date missing in to_sql_params()")
            params["recommendation_date"] = "1900-01-01"

        # Final check: ensure date_str is definitely not in params
        if "date_str" in params:
            print(f"⚠️  ERROR: date_str still in params after removal: {params.keys()}")
            del params["date_str"]

        return params

    @classmethod
    def from_dict(cls, bet: Dict[str, Any], context: BetContext) -> "BetRecommendation":
        """Factory method to create a BetRecommendation from a dictionary."""
        bet_data = BetData.from_dict(bet)
        return bet_data.to_recommendation(context)


class BetLoader:
    """Loads bet recommendations into PostgreSQL."""

    def __init__(
        self, db_manager: DBManager = default_db
    ) -> None:
        """Initialize the BetLoader with a database connection."""
        self.db = db_manager
        self._table_initialized = False
        self._upsert_bet = None

    def _lazy_initialize_table(self) -> None:
        """Lazily initialize the table and upsert function when first needed."""
        if not self._table_initialized:
            self._ensure_table()
            self._table_initialized = True

            # Create reusable upsert function for bet recommendations
            self._upsert_bet = create_entity_upserter(
                table_name="bet_recommendations",
                conflict_column="bet_id",
                update_columns=[
                    "elo_prob",
                    "market_prob",
                    "edge",
                    "expected_value",
                    "kelly_fraction",
                    "confidence",
                    "home_rating",
                    "away_rating",
                ],
            )

    def _ensure_table(self) -> None:
        """Create bet_recommendations table and associated indexes with retry logic."""
        import time

        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                self._create_bet_recommendations_table()
                self._create_bet_recommendations_indexes()
                print(f"✓ Successfully created bet_recommendations table (attempt {attempt + 1})")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  Failed to create table (attempt {attempt + 1}): {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    print(f"❌ Failed to create table after {max_retries} attempts: {e}")
                    raise

    def _create_bet_recommendations_table(self) -> None:
        """Create the bet_recommendations table schema."""
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS bet_recommendations (
                bet_id VARCHAR PRIMARY KEY,
                sport VARCHAR NOT NULL,
                recommendation_date DATE NOT NULL,
                home_team VARCHAR NOT NULL,
                away_team VARCHAR NOT NULL,
                home_rating DOUBLE PRECISION,
                away_rating DOUBLE PRECISION,
                bet_on VARCHAR NOT NULL,
                elo_prob DOUBLE PRECISION NOT NULL,
                market_prob DOUBLE PRECISION NOT NULL,
                edge DOUBLE PRECISION NOT NULL,
                expected_value DOUBLE PRECISION,
                kelly_fraction DOUBLE PRECISION,
                confidence VARCHAR NOT NULL,
                yes_ask INTEGER,
                no_ask INTEGER,
                ticker VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _create_bet_recommendations_indexes(self) -> None:
        """Create indexes for performance optimization."""
        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_bet_recs_date_sport
            ON bet_recommendations(recommendation_date, sport)
            """
        )

    def load_bets_for_date(self, sport: str, date_str: str) -> int:
        """
        Load bets from JSON file into PostgreSQL for a given sport and date.
        """
        # Lazily initialize table and upsert function
        self._lazy_initialize_table()

        bets = self._load_bets_from_file(sport, date_str)
        if bets is None:
            return 0

        loaded = 0
        for i, bet in enumerate(bets):
            context = BetContext(sport=sport, date_str=date_str, index=i)
            recommendation = BetRecommendation.from_dict(bet, context)
            params = self._process_bet_params(recommendation, context)

            if params:
                self._upsert_bet(self.db, params)
                loaded += 1

        print(f"✓ Loaded {loaded} {sport.upper()} bets for {date_str}")
        return loaded

    def _load_bets_from_file(
        self, sport: str, date_str: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Load bets from JSON file for a given sport and date."""
        bets_file = Path(f"data/{sport}/bets_{date_str}.json")

        if not bets_file.exists():
            print(f"⚠️  No bets file found for {sport} on {date_str}")
            return None

        with open(bets_file, "r") as f:
            bets = json.load(f)

        if not bets:
            print(f"ℹ️  No bets to load for {sport} on {date_str}")
            return None

        return bets

    def _process_bet_params(
        self, recommendation: BetRecommendation, context: BetContext
    ) -> Dict[str, Any]:
        """Process bet recommendation and return cleaned SQL parameters."""
        params = recommendation.to_sql_params()

        # NUCLEAR OPTION: Log what we got from to_sql_params()
        print(f"🔍 NUCLEAR DEBUG _process_bet_params: params from to_sql_params(): {list(params.keys())}")
        if "date_str" in params:
            print(f"🚨 NUCLEAR DEBUG _process_bet_params: date_str is in params! Value: {params['date_str']}")
        if "recommendation_date" in params:
            print(f"🔍 NUCLEAR DEBUG _process_bet_params: recommendation_date is in params! Value: {params['recommendation_date']}")

        # Ensure recommendation_date is present
        params = self._ensure_recommendation_date(params, context)

        # Remove date_str if present (database column is recommendation_date)
        params = self._remove_date_str_from_params(params)

        # FINAL NUCLEAR OPTION: Remove date_str no matter what
        if "date_str" in params:
            print(f"🚨 FINAL NUCLEAR OPTION: date_str STILL in params after all cleaning! Removing...")
            del params["date_str"]
        params.pop("date_str", None)  # Use pop with default for safety

        # FINAL CHECK: Log final params
        print(f"🔍 NUCLEAR DEBUG _process_bet_params: FINAL params: {list(params.keys())}")

        return params

    def _ensure_recommendation_date(
        self, params: Dict[str, Any], context: BetContext
    ) -> Dict[str, Any]:
        """Ensure recommendation_date is present in params."""
        if "recommendation_date" not in params:
            print(
                f"⚠️  Adding missing 'recommendation_date' from context: {context.date_str}"
            )
            params["recommendation_date"] = context.date_str

        return params

    def _remove_date_str_from_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove date_str from params (database column is recommendation_date)."""
        if "date_str" in params:
            print(
                f"⚠️  CRITICAL: Removing 'date_str' from params (should be 'recommendation_date'). Params keys: {list(params.keys())}"
            )
            del params["date_str"]

        # Final safety check
        params.pop("date_str", None)

        return params

    # _upsert_bet is created dynamically in __init__ using create_entity_upserter

    def get_bets_summary(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[List[Any]]:
        """Get summary of bet recommendations by sport and date."""
        # Lazily initialize table if needed
        self._lazy_initialize_table()

        query = """
            SELECT
                sport,
                recommendation_date,
                COUNT(*) as num_bets,
                AVG(edge) as avg_edge,
                AVG(elo_prob) as avg_elo_prob,
                SUM(CASE WHEN confidence = 'HIGH' THEN 1 ELSE 0 END) as high_confidence_bets
            FROM bet_recommendations
        """

        params = {}
        if start_date or end_date:
            query += " WHERE 1=1"
            if start_date:
                query += " AND recommendation_date >= :start_date"
                params["start_date"] = start_date
            if end_date:
                query += " AND recommendation_date <= :end_date"
                params["end_date"] = end_date

        query += " GROUP BY sport, recommendation_date ORDER BY recommendation_date DESC, sport"
        return self.db.fetch_df(query, params).values.tolist()


if __name__ == "__main__":
    # Test loading today's bets
    from datetime import date

    loader = BetLoader()
    today = date.today().strftime("%Y-%m-%d")

    print(f"Loading bets for {today}...")
    total = 0
    for s in ["nba", "nhl", "mlb", "nfl", "epl", "ncaab", "tennis"]:
        count = loader.load_bets_for_date(s, today)
        total += count

    print(f"\n✓ Total bets loaded: {total}")

    print("\n📊 Recent bets summary:")
    results = loader.get_bets_summary()
    for row in results[:20]:
        print(
            f"  {row[0]:6} {row[1]}: {row[2]:2} bets, avg edge: {row[3]:.1%}, "
            f"avg prob: {row[4]:.1%}, {row[5]} high conf"
        )
