"""Sync and track Kalshi fills in PostgreSQL.

This script is invoked by the Streamlit dashboard to sync fills and market
metadata (close time/title) into PostgreSQL so the UI can show "open bets" along
with scheduled times in Eastern.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from plugins.db_manager import DBManager, default_db
from plugins.sql_params_mixin import SqlParamsMixin

sys.path.insert(0, str(Path(__file__).parent))
from kalshi_betting import KalshiBetting, KalshiConfig


@dataclass
class BetCalculationParams:
    """Parameters for bet status and profit calculation."""

    market_status: str
    market_result: str
    side: str
    count: int
    cost: float


@dataclass
class BetData(SqlParamsMixin):
    """Data class to hold bet information for processing."""

    bet_id: str
    sport: str
    ticker: str
    side: str
    count: int
    price: float
    cost: float
    fees_dollars: float
    placed_time_utc: Optional[datetime]
    placed_date: Optional[str]
    market_title: Optional[str]
    market_close_time_utc: Optional[datetime]
    bet_line_prob: Optional[float]
    closing_line_prob: Optional[float]
    clv: Optional[float]
    status: str
    settled_date: Optional[str]
    payout: Optional[float]
    profit: Optional[float]

    def _get_field_mapping(self) -> Dict[str, str]:
        """Get field name mappings for SQL parameters.

        Maps 'fees_dollars' dataclass field to 'fees' SQL column.
        """
        return {"fees_dollars": "fees"}


@dataclass
class FillData:
    """Extracted basic fill data from Kalshi API."""

    ticker: str
    trade_id: str
    bet_id: str
    sport: str
    side: str
    count: int
    price: float
    cost: float
    fees: float
    placed_time_utc: Optional[datetime]
    placed_date: Optional[str]


@dataclass
class MarketInfo:
    """Market information with caching support."""

    status: str
    result: str
    title: Optional[str]
    close_time_utc: Optional[datetime]


@dataclass
class ProbabilityData:
    """Calculated probability data including CLV."""

    bet_line_prob: Optional[float]
    closing_line_prob: Optional[float]
    clv: Optional[float]


@dataclass
class StatusData:
    """Calculated bet status and profit data."""

    status: str
    settled_date: Optional[str]
    payout: Optional[float]
    profit: Optional[float]


def _extract_basic_fill_data(fill: Dict) -> FillData:
    """Extract basic fill data from Kalshi API response.

    Args:
        fill: Fill data from Kalshi API. The Kalshi v2 fills API
            (``/trade-api/v2/portfolio/fills``) returns a single ``price``
            field per fill rather than separate ``yes_price``/``no_price``
            fields (those exist on *orders*, not fills). Legacy payloads that
            do carry ``yes_price``/``no_price`` are handled via the fallback.

    Returns:
        FillData object with extracted data

    Note:
        ROOT CAUSE FIX (price_cents=0 bug): The old code called
        ``fill.get("yes_price", 0)`` which always returned 0 because
        ``yes_price`` is absent from v2 fill payloads, causing every
        ``price_cents`` in ``placed_bets`` to be stored as 0.
        Fix: prefer ``yes_price``/``no_price`` for backward compatibility,
        but fall back to the canonical ``price`` field that v2 fills return.
    """
    ticker = fill.get("ticker", "")
    # Prefer fill_id (Kalshi v2 API) with fallback to legacy trade_id.
    trade_id = fill.get("fill_id", fill.get("trade_id", ""))
    bet_id = f"{ticker}_{trade_id}"
    sport = _detect_sport_from_ticker(ticker)

    side = fill.get("side", "")
    count = fill.get("count", 0)
    # ROOT CAUSE FIX: Kalshi v2 fills API returns a single ``price`` field.
    # ``yes_price``/``no_price`` are absent from fill payloads (they appear on
    # orders only).  Prefer the side-specific keys for backward compatibility,
    # then fall back to the generic ``price`` that v2 always supplies.
    if side == "yes":
        price = fill.get("yes_price", fill.get("price", 0))
    else:
        price = fill.get("no_price", fill.get("price", 0))
    cost = count * price / 100
    fees = float(fill.get("fee_cost", 0)) / 100

    created_time = fill.get("created_time", "")
    placed_time_utc = _parse_iso_utc(created_time)
    placed_date = placed_time_utc.date().isoformat() if placed_time_utc else None

    return FillData(
        ticker=ticker,
        trade_id=trade_id,
        bet_id=bet_id,
        sport=sport,
        side=side,
        count=count,
        price=price,
        cost=cost,
        fees=fees,
        placed_time_utc=placed_time_utc,
        placed_date=placed_date,
    )


def _get_market_info_with_caching(
    ticker: str,
    client: KalshiBetting,
    market_cache: Optional[Dict[str, Dict]] = None,
) -> MarketInfo:
    """Get market information with optional caching.

    Args:
        ticker: Market ticker
        client: KalshiBetting client
        market_cache: Optional cache dictionary

    Returns:
        MarketInfo object with market data
    """
    if market_cache is not None and ticker in market_cache:
        market_info = market_cache[ticker]
    else:
        market_info = get_market_status(client, ticker)
        if market_cache is not None:
            market_cache[ticker] = market_info

    market_status = market_info.get("status", "unknown")
    market_result = market_info.get("result", "")
    market_title = market_info.get("title")
    market_close_time_utc = _parse_iso_utc(market_info.get("close_time"))

    return MarketInfo(
        status=market_status,
        result=market_result,
        title=market_title,
        close_time_utc=market_close_time_utc,
    )


def _calculate_probabilities_and_clv(
    side: str,
    price: float,
    market_result: str,
) -> ProbabilityData:
    """Calculate bet probabilities and closing line value.

    Args:
        side: Bet side ("yes" or "no")
        price: Bet price in cents
        market_result: Market result

    Returns:
        ProbabilityData object with calculated probabilities
    """
    bet_line_prob = _calculate_bet_probabilities(side, price)
    closing_line_prob = _calculate_closing_probability(market_result, side)

    clv = None
    if bet_line_prob is not None and closing_line_prob is not None:
        clv = bet_line_prob - closing_line_prob

    return ProbabilityData(
        bet_line_prob=bet_line_prob,
        closing_line_prob=closing_line_prob,
        clv=clv,
    )


def _calculate_bet_status_and_profit_data(
    params: BetCalculationParams,
) -> StatusData:
    """Calculate bet status, profit, and settlement data.

    Args:
        params: Bet calculation parameters

    Returns:
        StatusData object with calculated status and profit
    """
    status, payout, profit, settled_date = _calculate_bet_status_and_profit(params)

    return StatusData(
        status=status,
        settled_date=settled_date,
        payout=payout,
        profit=profit,
    )


def create_portfolio_value_snapshots_table(db: DBManager = default_db) -> None:
    """Create the portfolio_value_snapshots table if it does not exist."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_value_snapshots (
            snapshot_hour_utc TEXT PRIMARY KEY,
            balance_dollars REAL,
            portfolio_value_dollars REAL
        )
    """
    )


def _parse_iso_utc(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def create_bets_table(db: DBManager = default_db) -> None:
    """Create bets tracking table if it doesn't exist."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS placed_bets (
            bet_id VARCHAR PRIMARY KEY,
            sport VARCHAR,
            placed_date DATE,
            placed_time_utc TIMESTAMP,
            ticker VARCHAR,
            home_team VARCHAR,
            away_team VARCHAR,
            bet_on VARCHAR,
            side VARCHAR,
            contracts INTEGER,
            price_cents INTEGER,
            cost_dollars DOUBLE PRECISION,
            fees_dollars DOUBLE PRECISION,
            elo_prob DOUBLE PRECISION,
            market_prob DOUBLE PRECISION,
            edge DOUBLE PRECISION,
            expected_value DOUBLE PRECISION,
            kelly_fraction DOUBLE PRECISION,
            confidence VARCHAR,
            market_title VARCHAR,
            market_close_time_utc TIMESTAMP,
            opening_line_prob DOUBLE PRECISION,
            bet_line_prob DOUBLE PRECISION,
            closing_line_prob DOUBLE PRECISION,
            clv DOUBLE PRECISION,
            status VARCHAR,
            settled_date DATE,
            payout_dollars DOUBLE PRECISION,
            profit_dollars DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def load_fills_from_kalshi(client: KalshiBetting, days_back: int = 30) -> List[Dict]:
    """Load all fills from Kalshi API.

    Raises:
        Exception: If the API call fails for any reason (network, authentication, etc.)
    """
    try:
        response = client._get("/trade-api/v2/portfolio/fills?limit=500")
        fills = response.get("fills", [])
        print(f"✓ Loaded {len(fills)} fills from Kalshi")
        return fills
    except Exception as e:
        print(f"❌ Error loading fills: {e}")
        raise  # Re-raise to fail the task with clear error


def get_market_status(client: KalshiBetting, ticker: str) -> Dict:
    """Get current market status and result."""
    try:
        market = client.get_market_details(ticker)
        if market:
            return {
                "status": market.get("status"),
                "result": market.get("result"),
                "close_time": market.get("close_time"),
                "title": market.get("title"),
            }
    except Exception:
        pass
    return {}


def backfill_bet_metrics(db: DBManager = default_db) -> None:
    """Backfill missing validation metrics (elo_prob, edge, expected_value, etc) from recommendations.

    Links placed_bets to bet_recommendations via ticker.
    """
    try:
        # Optimized PostgreSQL-specific query using DISTINCT ON to avoid redundant subqueries
        query = """
            WITH latest_recommendations AS (
                SELECT DISTINCT ON (ticker)
                    ticker, elo_prob, market_prob, edge, expected_value,
                    kelly_fraction, confidence, home_team, away_team, bet_on
                FROM bet_recommendations
                WHERE ticker IS NOT NULL
                ORDER BY ticker, created_at DESC
            )
            UPDATE placed_bets
            SET
                elo_prob = lr.elo_prob,
                market_prob = lr.market_prob,
                edge = lr.edge,
                expected_value = lr.expected_value,
                kelly_fraction = lr.kelly_fraction,
                confidence = lr.confidence,
                home_team = lr.home_team,
                away_team = lr.away_team,
                bet_on = lr.bet_on
            FROM latest_recommendations lr
            WHERE placed_bets.ticker = lr.ticker
              AND (placed_bets.elo_prob IS NULL
                   OR placed_bets.home_team IS NULL
                   OR placed_bets.home_team = 'None')
        """
        db.execute(query)
        print(
            "✓ Backfilled missing bet metrics INCLUDING team data from recommendations"
        )
    except Exception as e:
        print(f"⚠️  Error backfilling metrics: {e}")


def _create_kalshi_client() -> KalshiBetting:
    """Create and return a KalshiBetting client.

    Returns:
        KalshiBetting: Initialized Kalshi client

    Raises:
        Exception: If credentials are invalid or client creation fails
    """
    try:
        config = KalshiConfig.from_kalshkey(production=True)
        return KalshiBetting(config=config)
    except Exception as e:
        print(f"❌ Failed to create Kalshi client: {e}")
        raise


def _ensure_bets_table_exists(db: DBManager) -> None:
    """Ensure the placed_bets table exists.

    Args:
        db: Database manager instance
    """
    try:
        create_bets_table(db)
    except Exception as e:
        print(f"❌ Failed to create/ensure bets table: {e}")
        print("⚠️  Continuing sync attempt - table may already exist")


def _load_existing_bet_ids(db: DBManager) -> set:
    """Fetch existing bet IDs from database.

    Args:
        db: Database manager instance

    Returns:
        set: Set of existing bet IDs, empty set if error occurs
    """
    try:
        existing_bets_df = db.fetch_df("SELECT bet_id FROM placed_bets")
        return (
            set(existing_bets_df["bet_id"].tolist())
            if not existing_bets_df.empty
            else set()
        )
    except Exception as e:
        print(f"⚠️  Failed to fetch existing bets: {e}")
        print("⚠️  Assuming no existing bets (will attempt to insert all as new)")
        return set()


def _detect_sport_from_ticker(ticker: str) -> str:
    """Detect sport from Kalshi ticker.

    Args:
        ticker: Kalshi market ticker

    Returns:
        str: Sport name or "UNKNOWN" if not recognized
    """
    # Dictionary mapping ticker patterns to sport names
    # Note: Order matters for patterns that might overlap
    sport_patterns = [
        ("NBAGAME", "NBA"),
        ("NHLGAME", "NHL"),
        ("MLBGAME", "MLB"),
        ("NFLGAME", "NFL"),
        ("NCAAMBGAME", "NCAAB"),
        ("NCAAWBGAME", "WNCAAB"),  # Women's NCAA Basketball
        ("ATPMATCH", "TENNIS"),
        ("WTAMATCH", "TENNIS"),
        ("ATPCHALLENGERMATCH", "TENNIS"),  # Challenger tournaments are still tennis
        ("WTACHALLENGERMATCH", "TENNIS"),  # Challenger tournaments are still tennis
        ("EPLGAME", "EPL"),
        ("LIGUE1GAME", "LIGUE1"),
        ("CBAGAME", "CBA"),
    ]

    for pattern, sport in sport_patterns:
        if pattern in ticker:
            return sport

    return "UNKNOWN"


def _calculate_bet_probabilities(side: str, price: float) -> Optional[float]:
    """Calculate bet line probability from side and price.

    Args:
        side: Bet side ("yes" or "no")
        price: Price in cents (0-100)

    Returns:
        Optional[float]: Probability or None if invalid input
    """
    if not side or not price:
        return None

    # Both yes and no prices on Kalshi represent the probability of that side winning
    # e.g., if YES is 60c, market thinks YES has 60% prob.
    # if NO is 40c, market thinks NO has 40% prob.
    if side in ["yes", "no"]:
        return price / 100
    else:
        return None


def _calculate_closing_probability(market_result: str, side: str) -> Optional[float]:
    """Calculate closing line probability from market result.

    NOTE: This returns a binary placeholder (1.0/0.0) based on the game
    outcome. Real closing probabilities are computed by the hourly CLV
    task (``update_closing_lines`` in bet_sync_hourly) which looks up
    actual market closing prices from the ``game_odds`` table. The
    placeholder value here will be overwritten once that task runs.

    Args:
        market_result: Market result ("yes", "no", or empty)
        side: Bet side ("yes" or "no")

    Returns:
        Optional[float]: Placeholder closing probability or None if not settled
    """
    if not market_result:
        return None

    if market_result == "yes":
        return 1.0 if side == "yes" else 0.0
    elif market_result == "no":
        return 0.0 if side == "yes" else 1.0
    else:
        return None


def _calculate_bet_status_and_profit(
    params: BetCalculationParams,
) -> Tuple[str, Optional[float], Optional[float], Optional[str]]:
    """Calculate bet status, payout, profit, and settled date.

    Args:
        params: Bet calculation parameters

    Returns:
        Tuple[str, Optional[float], Optional[float], Optional[str]]:
        (status, payout, profit, settled_date)
    """
    if params.market_status in ["closed", "finalized"]:
        if params.market_result == params.side:
            status, payout = "won", params.count * 1.0
            profit = payout - params.cost
        elif params.market_result and params.market_result != params.side:
            status, payout, profit = "lost", 0, -params.cost
        else:
            status, payout, profit = "settled", 0, -params.cost
        settled_date = datetime.now().strftime("%Y-%m-%d")
    else:
        status, payout, profit, settled_date = "open", None, None, None

    return status, payout, profit, settled_date


def _process_fill(
    fill: Dict,
    client: KalshiBetting,
    existing_bets: set,
    market_cache: Optional[Dict[str, Dict]] = None,
) -> Optional[BetData]:
    """Process a single fill from Kalshi API.

    Args:
        fill: Fill data from Kalshi API
        client: KalshiBetting client instance
        existing_bets: Set of existing bet IDs
        market_cache: Optional cache of market status by ticker

    Returns:
        Optional[BetData]: Processed bet data or None if processing fails
    """
    try:
        # Extract basic fill data
        fill_data = _extract_basic_fill_data(fill)

        # Get market information with caching
        market_info = _get_market_info_with_caching(
            fill_data.ticker, client, market_cache
        )

        # Calculate probabilities and CLV
        probabilities = _calculate_probabilities_and_clv(
            fill_data.side, fill_data.price, market_info.result
        )

        # Calculate status and profit
        calc_params = BetCalculationParams(
            market_status=market_info.status,
            market_result=market_info.result,
            side=fill_data.side,
            count=fill_data.count,
            cost=fill_data.cost,
        )
        status_data = _calculate_bet_status_and_profit_data(calc_params)

        return BetData(
            bet_id=fill_data.bet_id,
            sport=fill_data.sport,
            ticker=fill_data.ticker,
            side=fill_data.side,
            count=fill_data.count,
            price=fill_data.price,
            cost=fill_data.cost,
            fees_dollars=fill_data.fees,
            placed_time_utc=fill_data.placed_time_utc,
            placed_date=fill_data.placed_date,
            market_title=market_info.title,
            market_close_time_utc=market_info.close_time_utc,
            bet_line_prob=probabilities.bet_line_prob,
            closing_line_prob=probabilities.closing_line_prob,
            clv=probabilities.clv,
            status=status_data.status,
            settled_date=status_data.settled_date,
            payout=status_data.payout,
            profit=status_data.profit,
        )
    except Exception as e:
        print(f"  ⚠️  Failed to process fill {fill.get('ticker', 'unknown')}: {e}")
        return None


UPSERT_BET_QUERY = """
    INSERT INTO placed_bets (
        bet_id, sport, placed_date, placed_time_utc, ticker, side, contracts,
        price_cents, cost_dollars, fees_dollars, status,
        settled_date, payout_dollars, profit_dollars, market_title, market_close_time_utc,
        bet_line_prob, closing_line_prob, clv
    ) VALUES (
        :bet_id, :sport, :placed_date, :placed_time_utc, :ticker, :side, :count,
        :price, :cost, :fees, :status, :settled_date, :payout, :profit, :market_title, :market_close_time_utc,
        :bet_line_prob, :closing_line_prob, :clv
    )
    ON CONFLICT (bet_id) DO UPDATE SET
        status = EXCLUDED.status,
        settled_date = EXCLUDED.settled_date,
        payout_dollars = EXCLUDED.payout_dollars,
        profit_dollars = EXCLUDED.profit_dollars,
        fees_dollars = COALESCE(placed_bets.fees_dollars, EXCLUDED.fees_dollars),
        placed_time_utc = COALESCE(placed_bets.placed_time_utc, EXCLUDED.placed_time_utc),
        market_title = COALESCE(placed_bets.market_title, EXCLUDED.market_title),
        market_close_time_utc = COALESCE(placed_bets.market_close_time_utc, EXCLUDED.market_close_time_utc),
        bet_line_prob = COALESCE(placed_bets.bet_line_prob, EXCLUDED.bet_line_prob),
        closing_line_prob = COALESCE(placed_bets.closing_line_prob, EXCLUDED.closing_line_prob),
        clv = COALESCE(placed_bets.clv, EXCLUDED.clv),
        updated_at = CURRENT_TIMESTAMP
"""


def _save_bet_to_database(
    db: DBManager, bet_data: BetData, existing_bets: set
) -> Tuple[bool, bool]:
    """Save bet data to database using an upsert operation.

    Args:
        db: Database manager instance
        bet_data: Processed bet data
        existing_bets: Set of existing bet IDs

    Returns:
        Tuple[bool, bool]: (was_added, was_updated)
    """
    try:
        was_added = bet_data.bet_id not in existing_bets
        was_updated = not was_added

        # Single SQL statement for both insert and update (PostgreSQL UPSERT)
        db.execute(UPSERT_BET_QUERY, bet_data.to_sql_params())

        if was_added:
            print(f"  ✓ Added new bet: {bet_data.bet_id}")
        else:
            print(f"  ✓ Updated bet: {bet_data.bet_id}")

        return was_added, was_updated

    except Exception as e:
        print(f"  ⚠️  Failed to save bet {bet_data.bet_id}: {e}")
        return False, False


def _process_and_save_fills(
    fills: List[Dict], client: KalshiBetting, db: DBManager, existing_bets: set
) -> Tuple[int, int]:
    """Process and save a list of fills to the database.

    Args:
        fills: List of fill data from Kalshi API
        client: KalshiBetting client instance
        db: Database manager instance
        existing_bets: Set of existing bet IDs

    Returns:
        Tuple[int, int]: (added_count, updated_count)
    """
    added_count = 0
    updated_count = 0
    market_cache: Dict[str, Dict] = {}

    for fill in fills:
        # Process fill into structured data
        bet_data = _process_fill(fill, client, existing_bets, market_cache)
        if bet_data is None:
            continue  # Skip failed fills

        # Save to database
        was_added, was_updated = _save_bet_to_database(db, bet_data, existing_bets)
        if was_added:
            added_count += 1
        elif was_updated:
            updated_count += 1

    return added_count, updated_count


def sync_bets_to_database(db: DBManager = default_db):
    """Sync all bets from Kalshi API to PostgreSQL database.

    Returns:
        Tuple[int, int]: (added_count, updated_count) of bets synced
    """
    # Create Kalshi client
    try:
        client = _create_kalshi_client()
    except Exception as e:
        print(f"❌ Failed to initialize Kalshi client: {e}")
        raise  # Re-raise to maintain backward compatibility

    # Load fills from Kalshi
    fills = load_fills_from_kalshi(client)
    if not fills:
        print("✓ No fills found (API call succeeded but no bets placed)")
        return 0, 0  # Return zero counts instead of None

    # Ensure database tables exist
    _ensure_bets_table_exists(db)

    # Get existing bet IDs
    existing_bets = _load_existing_bet_ids(db)

    # Process and save all fills
    added_count, updated_count = _process_and_save_fills(
        fills, client, db, existing_bets
    )

    print("\n✓ Synced bets to PostgreSQL:")
    print(f"  Added: {added_count}")
    print(f"  Updated: {updated_count}")

    # Backfill metrics for any new bets (or old ones)
    try:
        backfill_bet_metrics(db)
    except Exception as e:
        print(f"⚠️  Failed to backfill bet metrics: {e}")
        print("⚠️  Bet metrics will be backfilled on next successful run")

    return added_count, updated_count


def get_betting_summary(
    db: DBManager = default_db,
    date: Optional[str] = None,
):
    """Get summary of betting performance from PostgreSQL."""
    where_clause = "WHERE placed_date = :date" if date else ""
    params = {"date": date} if date else {}

    query = f"""
        SELECT
            COUNT(*) as total_bets,
            SUM(contracts) as total_contracts,
            SUM(cost_dollars) as total_cost,
            SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_bets,
            SUM(CASE WHEN status IN ('won', 'lost') THEN profit_dollars ELSE 0 END) as total_profit,
            AVG(CASE WHEN status IN ('won', 'lost') THEN profit_dollars ELSE NULL END) as avg_profit_per_bet
        FROM placed_bets
        {where_clause}
    """
    return db.fetch_df(query, params)


if __name__ == "__main__":
    print("Syncing bets from Kalshi API to PostgreSQL...")
    sync_bets_to_database()
    print("\n" + "=" * 80 + "\nBETTING SUMMARY\n" + "=" * 80)
    summary = get_betting_summary()
    print(summary.to_string(index=False))
