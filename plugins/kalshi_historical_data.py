#!/usr/bin/env python3
"""Kalshi historical market data backfill utilities.

This module focuses on *historical* market data needed for research/backtesting:
- Market lists (by series, close/settle timestamps)
- Candlestick time series (batch endpoint)
- (Optionally) trade tape via the trades endpoint

It is intentionally read-only with respect to production trading/betting logic.

Example:
    # Backfill market metadata
    python -m plugins.kalshi_historical_data --mode markets --series-ticker KXNHLGAME --start 2025-10-01 --end 2026-01-19

    # Backfill candlesticks
    python -m plugins.kalshi_historical_data --mode candles --series-ticker KXNHLGAME --start 2025-10-01 --end 2026-01-19 --period-interval 60

    # Backfill trade tape
    python -m plugins.kalshi_historical_data --mode trades --series-ticker KXNHLGAME --start 2025-10-01 --end 2026-01-19

"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import duckdb
import pandas as pd
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


try:
    from .kalshi_markets import load_kalshi_credentials
except ImportError:  # pragma: no cover
    from kalshi_markets import load_kalshi_credentials


KALSHI_BASE_URL = "https://api.elections.kalshi.com"
TRADE_API_PREFIX = "/trade-api/v2"


def _parse_ymd(date_str: str) -> datetime:
    """Parse YYYY-MM-DD into a timezone-aware UTC datetime."""

    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _to_unix_seconds(dt: datetime) -> int:
    return int(dt.timestamp())


def _parse_kalshi_time(value: Any) -> Optional[datetime]:
    """Parse Kalshi timestamps into timezone-aware UTC datetimes.

    The API typically returns ISO-8601 strings (often with a trailing 'Z').
    """

    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = str(value).strip()
    if not text:
        return None

    # Normalize Zulu suffix for fromisoformat.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None

    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _chunks(items: Sequence[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


@dataclass(frozen=True)
class KalshiAuth:
    """Holds Kalshi request signing material."""

    api_key_id: str
    private_key: Any


def _load_auth_from_kalshkey() -> KalshiAuth:
    """Load Kalshi auth material from the local `kalshkey` file.

    Returns:
        KalshiAuth: Loaded API key id + parsed RSA private key.
    """

    api_key_id, private_key_pem = load_kalshi_credentials()
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"), password=None, backend=default_backend()
    )
    return KalshiAuth(api_key_id=api_key_id, private_key=private_key)


class KalshiRestClient:
    """Minimal REST client for Kalshi Trade API v2 (signed requests)."""

    def __init__(self, auth: KalshiAuth, base_url: str = KALSHI_BASE_URL):
        self._auth = auth
        self._base_url = base_url.rstrip("/")

    def _create_signature(self, timestamp_ms: str, method: str, path: str) -> str:
        path_without_query = path.split("?", 1)[0]
        message = f"{timestamp_ms}{method}{path_without_query}".encode("utf-8")
        signature = self._auth.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _headers(self, method: str, path: str) -> Dict[str, str]:
        timestamp_ms = str(int(datetime.now(tz=timezone.utc).timestamp() * 1000))
        signature = self._create_signature(timestamp_ms, method, path)
        return {
            "KALSHI-ACCESS-KEY": self._auth.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "Content-Type": "application/json",
        }

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Issue a signed GET request.

        Args:
            path: Full API path, e.g. `/trade-api/v2/markets`.
            params: Query params.

        Returns:
            Parsed JSON dict.
        """

        headers = self._headers("GET", path)
        resp = requests.get(self._base_url + path, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()


def fetch_trades_for_ticker(
    client: KalshiRestClient,
    *,
    market_ticker: str,
    min_ts: Optional[int] = None,
    max_ts: Optional[int] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """Fetch historical trades for a single market ticker.

    Args:
        client: Authenticated Kalshi REST client.
        market_ticker: Market ticker.
        min_ts: Optional Unix seconds lower bound.
        max_ts: Optional Unix seconds upper bound.
        limit: Page size (max 1000 per docs).

    Returns:
        A list of trade dicts.
    """

    trades: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        params: Dict[str, Any] = {"ticker": market_ticker, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        if min_ts is not None:
            params["min_ts"] = int(min_ts)
        if max_ts is not None:
            params["max_ts"] = int(max_ts)

        payload = client.get_json(f"{TRADE_API_PREFIX}/markets/trades", params=params)
        page = payload.get("trades", [])
        trades.extend(page)

        cursor = payload.get("cursor")
        if not cursor:
            break

    return trades


def list_markets_for_series(
    client: KalshiRestClient,
    series_ticker: str,
    *,
    min_close_ts: Optional[int] = None,
    max_close_ts: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """List markets for a series, optionally filtered by close timestamp.

    Notes:
        The Kalshi API supports pagination via `cursor`.

    Args:
        client: Authenticated Kalshi REST client.
        series_ticker: Series ticker (e.g., KXNHLGAME).
        min_close_ts: Optional Unix seconds lower bound.
        max_close_ts: Optional Unix seconds upper bound.
        status: Optional market status filter.
        limit: Page size (max 1000 per docs).

    Returns:
        List of market dicts.
    """

    markets: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        params: Dict[str, Any] = {
            "series_ticker": series_ticker,
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        if min_close_ts is not None:
            params["min_close_ts"] = min_close_ts
        if max_close_ts is not None:
            params["max_close_ts"] = max_close_ts

        payload = client.get_json(f"{TRADE_API_PREFIX}/markets", params=params)
        page = payload.get("markets", [])
        markets.extend(page)

        cursor = payload.get("cursor")
        if not cursor:
            break

    return markets


def fetch_candlesticks_batch(
    client: KalshiRestClient,
    market_tickers: Sequence[str],
    *,
    start_ts: int,
    end_ts: int,
    period_interval_minutes: int,
    include_latest_before_start: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch candlesticks for up to 100 markets (batch endpoint).

    Args:
        client: Authenticated Kalshi REST client.
        market_tickers: Up to 100 market tickers.
        start_ts: Unix seconds.
        end_ts: Unix seconds.
        period_interval_minutes: Candlestick interval in minutes.
        include_latest_before_start: Whether to include synthetic continuity candle.

    Returns:
        Mapping market_ticker -> list of candlestick dicts.
    """

    params = {
        "market_tickers": ",".join(market_tickers),
        "start_ts": start_ts,
        "end_ts": end_ts,
        "period_interval": period_interval_minutes,
        "include_latest_before_start": str(include_latest_before_start).lower(),
    }

    payload = client.get_json(f"{TRADE_API_PREFIX}/markets/candlesticks", params=params)
    out: Dict[str, List[Dict[str, Any]]] = {}

    for market_entry in payload.get("markets", []):
        ticker = market_entry.get("market_ticker")
        candles = market_entry.get("candlesticks", [])
        if ticker:
            out[ticker] = candles

    return out


def _flatten_candles(
    market_ticker: str, candles: Sequence[Dict[str, Any]], period_interval_minutes: int
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for c in candles:
        price = c.get("price", {}) or {}
        rows.append(
            {
                "market_ticker": market_ticker,
                "period_interval": int(period_interval_minutes),
                "end_period_ts": int(c.get("end_period_ts")),
                "price_open": price.get("open"),
                "price_high": price.get("high"),
                "price_low": price.get("low"),
                "price_close": price.get("close"),
                "price_mean": price.get("mean"),
                "price_previous": price.get("previous"),
                "volume": c.get("volume"),
                "open_interest": c.get("open_interest"),
            }
        )
    return rows


def upsert_candles_to_duckdb(
    db_path: str,
    *,
    rows: Sequence[Dict[str, Any]],
    delete_scope: Optional[Tuple[Sequence[str], int, int, int]] = None,
) -> int:
    """Store candlestick rows into DuckDB.

    Args:
        db_path: DuckDB file path.
        rows: Flattened candlestick rows.
        delete_scope: Optional tuple of (tickers, period_interval, start_ts, end_ts)
            used to delete existing rows before inserting.

    Returns:
        Number of rows inserted.
    """

    if not rows:
        return 0

    con = duckdb.connect(db_path)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS kalshi_candlesticks (
            market_ticker TEXT,
            period_interval INTEGER,
            end_period_ts BIGINT,
            price_open INTEGER,
            price_high INTEGER,
            price_low INTEGER,
            price_close INTEGER,
            price_mean INTEGER,
            price_previous INTEGER,
            volume BIGINT,
            open_interest BIGINT,
            retrieved_at TIMESTAMP DEFAULT now()
        )
        """
    )

    if delete_scope is not None:
        tickers, period_interval, start_ts, end_ts = delete_scope
        if tickers:
            in_list = ",".join(["?"] * len(tickers))
            con.execute(
                f"""
                DELETE FROM kalshi_candlesticks
                WHERE market_ticker IN ({in_list})
                  AND period_interval = ?
                  AND end_period_ts BETWEEN ? AND ?
                """,
                [*tickers, period_interval, start_ts, end_ts],
            )

    df = pd.DataFrame(list(rows))
    con.register("candles_df", df)
    con.execute(
        """
        INSERT INTO kalshi_candlesticks (
            market_ticker,
            period_interval,
            end_period_ts,
            price_open,
            price_high,
            price_low,
            price_close,
            price_mean,
            price_previous,
            volume,
            open_interest
        )
        SELECT
            market_ticker,
            period_interval,
            end_period_ts,
            price_open,
            price_high,
            price_low,
            price_close,
            price_mean,
            price_previous,
            volume,
            open_interest
        FROM candles_df
        """
    )
    con.unregister("candles_df")
    con.close()

    return len(df)


def upsert_markets_to_duckdb(db_path: str, *, markets: Sequence[Dict[str, Any]]) -> int:
    """Upsert basic market metadata into DuckDB.

    The table is keyed by `ticker`.
    """

    if not markets:
        return 0

    rows: List[Dict[str, Any]] = []
    for m in markets:
        rows.append(
            {
                "ticker": m.get("ticker"),
                "event_ticker": m.get("event_ticker"),
                "status": m.get("status"),
                "yes_sub_title": m.get("yes_sub_title"),
                "no_sub_title": m.get("no_sub_title"),
                "open_time": m.get("open_time"),
                "close_time": m.get("close_time"),
                "settlement_ts": m.get("settlement_ts"),
                "result": m.get("result"),
                "market_type": m.get("market_type"),
            }
        )

    con = duckdb.connect(db_path)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS kalshi_markets (
            ticker TEXT PRIMARY KEY,
            event_ticker TEXT,
            status TEXT,
            yes_sub_title TEXT,
            no_sub_title TEXT,
            open_time TIMESTAMP,
            close_time TIMESTAMP,
            settlement_ts TIMESTAMP,
            result TEXT,
            market_type TEXT,
            retrieved_at TIMESTAMP DEFAULT now()
        )
        """
    )

    df = pd.DataFrame(rows)
    con.register("markets_df", df)
    con.execute(
        """
        INSERT OR REPLACE INTO kalshi_markets (
            ticker,
            event_ticker,
            status,
            yes_sub_title,
            no_sub_title,
            open_time,
            close_time,
            settlement_ts,
            result,
            market_type
        )
        SELECT
            ticker,
            event_ticker,
            status,
            yes_sub_title,
            no_sub_title,
            open_time,
            close_time,
            settlement_ts,
            result,
            market_type
        FROM markets_df
        """
    )
    con.unregister("markets_df")
    con.close()

    return len(df)


def upsert_trades_to_duckdb(db_path: str, *, trades: Sequence[Dict[str, Any]]) -> int:
    """Insert trades into DuckDB.

    Trades are appended; de-duplication is handled with a UNIQUE constraint.
    """

    if not trades:
        return 0

    rows: List[Dict[str, Any]] = []
    for t in trades:
        rows.append(
            {
                "trade_id": t.get("trade_id"),
                "ticker": t.get("ticker"),
                "yes_price": t.get("yes_price"),
                "no_price": t.get("no_price"),
                "count": t.get("count"),
                "count_fp": t.get("count_fp"),
                "taker_side": t.get("taker_side"),
                "created_time": t.get("created_time"),
            }
        )

    con = duckdb.connect(db_path)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS kalshi_trades (
            trade_id TEXT,
            ticker TEXT,
            yes_price INTEGER,
            no_price INTEGER,
            count BIGINT,
            count_fp TEXT,
            taker_side TEXT,
            created_time TIMESTAMP,
            retrieved_at TIMESTAMP DEFAULT now(),
            UNIQUE(trade_id)
        )
        """
    )

    df = pd.DataFrame(rows)
    con.register("trades_df", df)
    con.execute(
        """
        INSERT OR IGNORE INTO kalshi_trades (
            trade_id,
            ticker,
            yes_price,
            no_price,
            count,
            count_fp,
            taker_side,
            created_time
        )
        SELECT
            trade_id,
            ticker,
            yes_price,
            no_price,
            count,
            count_fp,
            taker_side,
            created_time
        FROM trades_df
        """
    )
    con.unregister("trades_df")
    con.close()

    return len(df)


def backfill_series_candles(
    *,
    series_ticker: str,
    start_date: str,
    end_date: str,
    period_interval_minutes: int,
    db_path: str,
    market_status: Optional[str] = None,
) -> None:
    """Backfill candlesticks for all markets in a series within a time window."""

    auth = _load_auth_from_kalshkey()
    client = KalshiRestClient(auth)

    start_dt = _parse_ymd(start_date)
    end_dt = _parse_ymd(end_date)
    start_ts = _to_unix_seconds(start_dt)
    end_ts = _to_unix_seconds(end_dt)

    markets = list_markets_for_series(
        client,
        series_ticker,
        min_close_ts=start_ts,
        max_close_ts=end_ts,
        status=market_status,
    )

    tickers = [m.get("ticker") for m in markets if m.get("ticker")]
    tickers = sorted(set(tickers))

    print(
        f"📥 Found {len(tickers)} markets for {series_ticker} "
        f"in [{start_date}, {end_date}]"
    )

    total_inserted = 0
    for batch in _chunks(tickers, 100):
        candles_by_ticker = fetch_candlesticks_batch(
            client,
            batch,
            start_ts=start_ts,
            end_ts=end_ts,
            period_interval_minutes=period_interval_minutes,
        )

        rows: List[Dict[str, Any]] = []
        for t, candles in candles_by_ticker.items():
            rows.extend(_flatten_candles(t, candles, period_interval_minutes))

        inserted = upsert_candles_to_duckdb(
            db_path,
            rows=rows,
            delete_scope=(batch, period_interval_minutes, start_ts, end_ts),
        )
        total_inserted += inserted
        print(f"✅ Inserted {inserted} candlesticks (batch size {len(batch)})")

    print(f"🏁 Done. Total candlesticks inserted: {total_inserted}")


def backfill_series_markets(
    *,
    series_ticker: str,
    start_date: str,
    end_date: str,
    db_path: str,
    market_status: Optional[str] = None,
) -> None:
    """Backfill market metadata for a series within a close-time window."""

    auth = _load_auth_from_kalshkey()
    client = KalshiRestClient(auth)

    start_ts = _to_unix_seconds(_parse_ymd(start_date))
    end_ts = _to_unix_seconds(_parse_ymd(end_date))

    markets = list_markets_for_series(
        client,
        series_ticker,
        min_close_ts=start_ts,
        max_close_ts=end_ts,
        status=market_status,
    )
    inserted = upsert_markets_to_duckdb(db_path, markets=markets)
    print(f"✅ Upserted {inserted} markets into DuckDB")


def backfill_series_trades(
    *,
    series_ticker: str,
    start_date: str,
    end_date: str,
    db_path: str,
    market_status: Optional[str] = None,
    max_markets: Optional[int] = None,
) -> None:
    """Backfill trade tape for markets in a series over a date range."""

    auth = _load_auth_from_kalshkey()
    client = KalshiRestClient(auth)

    start_ts = _to_unix_seconds(_parse_ymd(start_date))
    end_ts = _to_unix_seconds(_parse_ymd(end_date))

    markets = list_markets_for_series(
        client,
        series_ticker,
        min_close_ts=start_ts,
        max_close_ts=end_ts,
        status=market_status,
    )
    # Keep full market dicts so we can bound trade queries by each market's active window.
    markets = [m for m in markets if m.get("ticker")]
    markets = sorted(markets, key=lambda m: str(m.get("ticker")))
    if max_markets is not None:
        markets = markets[: int(max_markets)]

    print(
        f"📥 Fetching trades for {len(markets)} markets in {series_ticker} "
        f"in [{start_date}, {end_date}]"
    )

    total = 0
    for i, market in enumerate(markets, start=1):
        ticker = str(market.get("ticker"))

        open_dt = _parse_kalshi_time(market.get("open_time"))
        close_dt = _parse_kalshi_time(market.get("close_time"))

        # Prefer per-market bounds; fall back to requested global window.
        # Add a small buffer to ensure we include trades slightly before open/close.
        min_dt = open_dt - timedelta(hours=6) if open_dt else _parse_ymd(start_date)
        max_dt = close_dt + timedelta(hours=6) if close_dt else _parse_ymd(end_date)
        min_dt = min_dt.astimezone(timezone.utc)
        max_dt = max_dt.astimezone(timezone.utc)

        min_ts_market = _to_unix_seconds(min_dt)
        max_ts_market = _to_unix_seconds(max_dt)

        trades = fetch_trades_for_ticker(
            client,
            market_ticker=str(ticker),
            min_ts=min_ts_market,
            max_ts=max_ts_market,
        )
        inserted = upsert_trades_to_duckdb(db_path, trades=trades)
        total += inserted
        if i % 10 == 0 or i == len(markets):
            print(f"✅ {i}/{len(markets)} markets processed; +{inserted} trades (total {total})")

    print(f"🏁 Done. Total trades inserted: {total}")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Kalshi historical candlesticks")
    parser.add_argument(
        "--mode",
        choices=["markets", "candles", "trades"],
        default="candles",
        help="Backfill mode",
    )
    parser.add_argument("--series-ticker", required=True, help="Kalshi series ticker, e.g. KXNHLGAME")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--period-interval",
        type=int,
        default=60,
        help="Candlestick interval in minutes (1, 60, 1440 recommended)",
    )
    parser.add_argument(
        "--db",
        default="data/nhlstats.duckdb",
        help="DuckDB path to store candlesticks",
    )
    parser.add_argument(
        "--status",
        default=None,
        help="Optional market status filter (unopened/open/paused/closed/settled)",
    )
    parser.add_argument(
        "--max-markets",
        type=int,
        default=None,
        help="Optional cap on number of markets (useful for testing trades backfill)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    status = None if args.status in (None, "") else str(args.status)
    if str(args.mode) == "markets":
        backfill_series_markets(
            series_ticker=str(args.series_ticker),
            start_date=str(args.start),
            end_date=str(args.end),
            db_path=str(args.db),
            market_status=status,
        )
        return

    if str(args.mode) == "trades":
        backfill_series_trades(
            series_ticker=str(args.series_ticker),
            start_date=str(args.start),
            end_date=str(args.end),
            db_path=str(args.db),
            market_status=status,
            max_markets=args.max_markets,
        )
        return

    backfill_series_candles(
        series_ticker=str(args.series_ticker),
        start_date=str(args.start),
        end_date=str(args.end),
        period_interval_minutes=int(args.period_interval),
        db_path=str(args.db),
        market_status=status,
    )


if __name__ == "__main__":
    main()
