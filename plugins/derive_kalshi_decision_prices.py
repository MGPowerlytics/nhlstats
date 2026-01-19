"""Derive decision-time Kalshi prices for fast joins/backtests.

Creates/updates a DuckDB table `kalshi_decision_prices` with, per ticker:
- `decision_minutes_before_close`
- `decision_ts` (close_time - N minutes)
- last trade at or before `decision_ts`

This makes it easy to join NHL model predictions to market prices at a consistent
"decision time".

Example:
    python3 plugins/derive_kalshi_decision_prices.py \
      --start 2025-10-01 --end 2026-01-19 --decision-minutes-before-close 30

"""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import Optional, Sequence

import duckdb


def _parse_ymd(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Derive decision-time Kalshi prices")
    parser.add_argument("--db", default="data/nhlstats.duckdb", help="DuckDB path")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--decision-minutes-before-close",
        type=int,
        default=30,
        help="Decision timestamp is close_time minus this many minutes",
    )
    parser.add_argument(
        "--series-prefix",
        default="KXNHLGAME",
        help="Only include markets whose ticker starts with this prefix",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    start = _parse_ymd(str(args.start))
    end = _parse_ymd(str(args.end))
    minutes = int(args.decision_minutes_before_close)
    prefix = str(args.series_prefix)

    con = duckdb.connect(str(args.db))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS kalshi_decision_prices (
                ticker TEXT,
                decision_minutes_before_close INTEGER,
                decision_ts TIMESTAMP,
                trade_created_time TIMESTAMP,
                yes_price_dollars DOUBLE,
                no_price_dollars DOUBLE,
                retrieved_at TIMESTAMP DEFAULT now(),
                PRIMARY KEY (ticker, decision_minutes_before_close)
            )
            """
        )

        # Delete scope for determinism / reruns
        con.execute(
            """
            DELETE FROM kalshi_decision_prices
            WHERE decision_minutes_before_close = ?
              AND decision_ts >= ? AND decision_ts < ?
              AND ticker LIKE ?
            """,
            [minutes, start, end, f"{prefix}%"],
        )

        con.execute(
            """
            WITH markets AS (
                SELECT
                    ticker,
                    close_time,
                    close_time - (INTERVAL '1 minute' * ?) AS decision_ts
                FROM kalshi_markets
                WHERE close_time >= ?
                  AND close_time < ?
                  AND ticker LIKE ?
            ),
            ranked AS (
                SELECT
                    m.ticker AS ticker,
                    ?::INTEGER AS decision_minutes_before_close,
                    m.decision_ts AS decision_ts,
                    t.created_time AS trade_created_time,
                    (t.yes_price / 100.0) AS yes_price_dollars,
                    (t.no_price / 100.0) AS no_price_dollars,
                    ROW_NUMBER() OVER (
                        PARTITION BY m.ticker
                        ORDER BY t.created_time DESC
                    ) AS rn
                FROM markets m
                JOIN kalshi_trades t
                  ON t.ticker = m.ticker
                 AND t.created_time <= m.decision_ts
            )
            INSERT INTO kalshi_decision_prices (
                ticker,
                decision_minutes_before_close,
                decision_ts,
                trade_created_time,
                yes_price_dollars,
                no_price_dollars
            )
            SELECT
                ticker,
                decision_minutes_before_close,
                decision_ts,
                trade_created_time,
                yes_price_dollars,
                no_price_dollars
            FROM ranked
            WHERE rn = 1
            """,
            [minutes, start, end, f"{prefix}%", minutes],
        )

        inserted = con.execute(
            """
            SELECT COUNT(*)
            FROM kalshi_decision_prices
            WHERE decision_minutes_before_close = ?
              AND decision_ts >= ? AND decision_ts < ?
              AND ticker LIKE ?
            """,
            [minutes, start, end, f"{prefix}%"],
        ).fetchone()[0]

        print(f"✅ Derived {inserted} decision-time prices (N={minutes}m)")
    finally:
        con.close()


if __name__ == "__main__":
    main()
