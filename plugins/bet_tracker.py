"""Sync and track Kalshi fills in DuckDB.

This script is invoked by the Streamlit dashboard to sync fills and market
metadata (close time/title) into DuckDB so the UI can show "open bets" along
with scheduled times in Eastern.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from db_manager import DBManager, default_db

sys.path.insert(0, str(Path(__file__).parent))
from kalshi_betting import KalshiBetting


def create_portfolio_value_snapshots_table(db):
    """Create the portfolio_value_snapshots table if it does not exist."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_value_snapshots (
            snapshot_hour_utc TEXT PRIMARY KEY,
            balance_dollars REAL,
            portfolio_value_dollars REAL
        )
    """)


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


def _read_kalshkey() -> Tuple[str, Path]:
    """Read Kalshi API key id and write a temp PEM file."""
    kalshkey_path = Path("kalshkey")
    if not kalshkey_path.exists():
        kalshkey_path = Path("/opt/airflow/kalshkey")
    if not kalshkey_path.exists():
        raise FileNotFoundError("kalshkey file not found")

    content = kalshkey_path.read_text(encoding="utf-8")

    api_key_id = None
    for line in content.splitlines():
        if "API key id:" in line:
            api_key_id = line.split(":", 1)[1].strip()
            break
    if not api_key_id:
        raise ValueError("Could not find API key ID in kalshkey file")

    private_key_lines: List[str] = []
    in_key = False
    for line in content.splitlines():
        if "-----BEGIN RSA PRIVATE KEY-----" in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if "-----END RSA PRIVATE KEY-----" in line:
            break
    if not private_key_lines:
        raise ValueError("Could not extract RSA private key from kalshkey")

    pem_path = Path("/tmp/kalshi_private_key.pem")
    pem_path.write_text("\n".join(private_key_lines), encoding="utf-8")
    return api_key_id, pem_path


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
    """Load all fills from Kalshi API."""
    try:
        response = client._get("/trade-api/v2/portfolio/fills?limit=500")
        fills = response.get("fills", [])
        print(f"✓ Loaded {len(fills)} fills from Kalshi")
        return fills
    except Exception as e:
        print(f"⚠️  Error loading fills: {e}")
        return []


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
    """Backfill missing validation metrics (elo_prob, edge, etc) from recommendations.

    Links placed_bets to bet_recommendations via ticker.
    """
    try:
        # Use latest recommendation for each ticker
        # SQLite-compatible UPDATE using correlated subquery
        query = """
            UPDATE placed_bets
            SET elo_prob = (
                SELECT elo_prob FROM bet_recommendations
                WHERE placed_bets.ticker = bet_recommendations.ticker
                AND ticker IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
            ),
                market_prob = (
                SELECT market_prob FROM bet_recommendations
                WHERE placed_bets.ticker = bet_recommendations.ticker
                AND ticker IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
            ),
                edge = (
                SELECT edge FROM bet_recommendations
                WHERE placed_bets.ticker = bet_recommendations.ticker
                AND ticker IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
            ),
                confidence = (
                SELECT confidence FROM bet_recommendations
                WHERE placed_bets.ticker = bet_recommendations.ticker
                AND ticker IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
            )
            WHERE elo_prob IS NULL
        """
        db.execute(query)
        print("✓ Backfilled missing bet metrics from recommendations")
    except Exception as e:
        print(f"⚠️  Error backfilling metrics: {e}")


def sync_bets_to_database(db_path: Optional[str] = None, db: DBManager = default_db):
    """Sync all bets from Kalshi API to PostgreSQL database."""
    api_key_id, private_key_path = _read_kalshkey()

    client = KalshiBetting(
        api_key_id=api_key_id,
        private_key_path=str(private_key_path),
        max_bet_size=5.0,
        production=True,
    )

    fills = load_fills_from_kalshi(client)
    if not fills:
        print("⚠️  No fills found")
        return

    create_bets_table(db)
    existing_bets_df = db.fetch_df("SELECT bet_id FROM placed_bets")
    existing_bets = (
        set(existing_bets_df["bet_id"].tolist())
        if not existing_bets_df.empty
        else set()
    )

    added_count = 0
    updated_count = 0

    for fill in fills:
        ticker = fill.get("ticker", "")
        trade_id = fill.get("trade_id", "")
        bet_id = f"{ticker}_{trade_id}"

        sport = "UNKNOWN"
        if "NBAGAME" in ticker:
            sport = "NBA"
        elif "NHLGAME" in ticker:
            sport = "NHL"
        elif "MLBGAME" in ticker:
            sport = "MLB"
        elif "NFLGAME" in ticker:
            sport = "NFL"
        elif "NCAAMBGAME" in ticker:
            sport = "NCAAB"
        elif "ATPMATCH" in ticker or "WTAMATCH" in ticker:
            sport = "TENNIS"
        elif "EPLGAME" in ticker:
            sport = "EPL"

        side = fill.get("side", "")
        count = fill.get("count", 0)
        price = fill.get("yes_price", 0) if side == "yes" else fill.get("no_price", 0)
        cost = count * price / 100
        created_time = fill.get("created_time", "")
        placed_time_utc = _parse_iso_utc(created_time)
        placed_date = placed_time_utc.date().isoformat() if placed_time_utc else None

        market_info = get_market_status(client, ticker)
        market_status = market_info.get("status", "unknown")
        market_result = market_info.get("result", "")
        market_title = market_info.get("title")
        market_close_time_utc = _parse_iso_utc(market_info.get("close_time"))

        # Calculate bet_line_prob from the price at time of fill
        # For Kalshi: if betting YES at price P, bet_line_prob = (100 - P) / 100
        # If betting NO at price P, bet_line_prob = P / 100
        bet_line_prob = None
        if side and price:
            if side == "yes":
                bet_line_prob = (100 - price) / 100
            elif side == "no":
                bet_line_prob = price / 100

        # Calculate closing_line_prob if market is closed
        closing_line_prob = None
        if market_status in ["closed", "finalized"] and market_result:
            # For closed markets, the closing line is implied by the result
            # If result is 'yes', closing prob of yes winning = 1.0
            # If result is 'no', closing prob of yes winning = 0.0
            if market_result == "yes":
                closing_line_prob = 1.0 if side == "yes" else 0.0
            elif market_result == "no":
                closing_line_prob = 0.0 if side == "yes" else 1.0

        # Calculate CLV if we have both probabilities
        clv = None
        if bet_line_prob is not None and closing_line_prob is not None:
            clv = bet_line_prob - closing_line_prob

        if market_status in ["closed", "finalized"]:
            if market_result == side:
                status, payout = "won", count * 1.0
                profit = payout - cost
            elif market_result and market_result != side:
                status, payout, profit = "lost", 0, -cost
            else:
                status, payout, profit = "settled", 0, -cost
            settled_date = datetime.now().strftime("%Y-%m-%d")
        else:
            status, payout, profit, settled_date = "open", None, None, None

        if bet_id in existing_bets:
            db.execute(
                """
                UPDATE placed_bets
                SET status = :status,
                    settled_date = :settled_date,
                    payout_dollars = :payout,
                    profit_dollars = :profit,
                    placed_time_utc = COALESCE(placed_bets.placed_time_utc, :placed_time_utc),
                    market_title = COALESCE(placed_bets.market_title, :market_title),
                    market_close_time_utc = COALESCE(placed_bets.market_close_time_utc, :market_close_time_utc),
                    bet_line_prob = COALESCE(placed_bets.bet_line_prob, :bet_line_prob),
                    closing_line_prob = COALESCE(placed_bets.closing_line_prob, :closing_line_prob),
                    clv = COALESCE(placed_bets.clv, :clv),
                    updated_at = CURRENT_TIMESTAMP
                WHERE bet_id = :bet_id
            """,
                {
                    "status": status,
                    "settled_date": settled_date,
                    "payout": payout,
                    "profit": profit,
                    "placed_time_utc": placed_time_utc,
                    "market_title": market_title,
                    "market_close_time_utc": market_close_time_utc,
                    "bet_line_prob": bet_line_prob,
                    "closing_line_prob": closing_line_prob,
                    "clv": clv,
                    "bet_id": bet_id,
                },
            )
            updated_count += 1
        else:
            db.execute(
                """
                INSERT INTO placed_bets (
                    bet_id, sport, placed_date, placed_time_utc, ticker, side, contracts,
                    price_cents, cost_dollars, fees_dollars, status,
                    settled_date, payout_dollars, profit_dollars, market_title, market_close_time_utc,
                    bet_line_prob, closing_line_prob, clv
                ) VALUES (:bet_id, :sport, :placed_date, :placed_time_utc, :ticker, :side, :count,
                         :price, :cost, 0, :status, :settled_date, :payout, :profit, :market_title, :market_close_time_utc,
                         :bet_line_prob, :closing_line_prob, :clv)
            """,
                {
                    "bet_id": bet_id,
                    "sport": sport,
                    "placed_date": placed_date,
                    "placed_time_utc": placed_time_utc,
                    "ticker": ticker,
                    "side": side,
                    "count": count,
                    "price": price,
                    "cost": cost,
                    "status": status,
                    "settled_date": settled_date,
                    "payout": payout,
                    "profit": profit,
                    "market_title": market_title,
                    "market_close_time_utc": market_close_time_utc,
                    "bet_line_prob": bet_line_prob,
                    "closing_line_prob": closing_line_prob,
                    "clv": clv,
                },
            )
            added_count += 1

    print("\n✓ Synced bets to PostgreSQL:")
    print(f"  Added: {added_count}")
    print(f"  Updated: {updated_count}")

    # Backfill metrics for any new bets (or old ones)
    backfill_bet_metrics(db)

    return added_count, updated_count


def get_betting_summary(
    db_path: Optional[str] = None, db: DBManager = default_db, date: str = None
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
