"""Backtest NHL model edges vs historical Kalshi prices.

This script:
1) Loads NHL games from the repo's DuckDB.
2) Loads Kalshi market metadata and trade tape from DuckDB.
3) Attempts to match each game to a Kalshi market ticker in `KXNHLGAME`.
4) Uses the last trade price before a decision timestamp to compute:
   - model edge (EV per contract)
   - realized PnL per contract (using actual outcome)

Notes:
- Matching is best-effort using market yes/no subtitles.
- Pricing uses last trade before decision time; if none exists, the game is skipped.

Example:
    python3 plugins/backtest_kalshi_nhl.py --start 2025-10-01 --end 2025-10-15

"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import duckdb
import pandas as pd

from plugins.elo import NHLEloRating


def _parse_ymd(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _norm_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


@dataclass(frozen=True)
class MarketMatch:
    ticker: str
    yes_team: str
    no_team: str


def _extract_teams_from_market_row(row: Dict[str, Any]) -> Optional[MarketMatch]:
    ticker = row.get("ticker")
    yes_sub = row.get("yes_sub_title")
    no_sub = row.get("no_sub_title")
    if not ticker or not yes_sub or not no_sub:
        return None

    return MarketMatch(
        ticker=str(ticker),
        yes_team=_norm_name(str(yes_sub)),
        no_team=_norm_name(str(no_sub)),
    )


def _team_match_score(team: str, candidate: str) -> int:
    """Simple name match scoring.

    Higher is better.
    """

    team_n = _norm_name(team)
    cand_n = _norm_name(candidate)
    if team_n == cand_n:
        return 100
    if team_n in cand_n or cand_n in team_n:
        return 80

    team_tokens = set(team_n.split())
    cand_tokens = set(cand_n.split())
    overlap = len(team_tokens.intersection(cand_tokens))
    return overlap


def _match_market_for_game(
    *,
    markets: List[MarketMatch],
    home_team: str,
    away_team: str,
) -> Optional[Tuple[str, bool]]:
    """Match a game to a market.

    Returns:
        (ticker, yes_is_home)
    """

    best: Optional[Tuple[int, str, bool]] = None
    for m in markets:
        score_home_yes = _team_match_score(home_team, m.yes_team)
        score_away_no = _team_match_score(away_team, m.no_team)
        score_yes_home = score_home_yes + score_away_no

        score_home_no = _team_match_score(home_team, m.no_team)
        score_away_yes = _team_match_score(away_team, m.yes_team)
        score_yes_away = score_home_no + score_away_yes

        if score_yes_home >= score_yes_away:
            score = score_yes_home
            yes_is_home = True
        else:
            score = score_yes_away
            yes_is_home = False

        if best is None or score > best[0]:
            best = (score, m.ticker, yes_is_home)

    if best is None:
        return None

    score, ticker, yes_is_home = best
    if score < 6:
        return None

    return ticker, yes_is_home


def _load_games(db_path: str, *, start: datetime, end: datetime) -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    try:
        df = con.execute(
            """
            SELECT
                game_id,
                game_date,
                home_team_name AS home_team,
                away_team_name AS away_team,
                home_score,
                away_score
            FROM games
            WHERE game_date >= ? AND game_date < ?
            ORDER BY game_date ASC
            """,
            [start.date(), end.date()],
        ).fetchdf()
    finally:
        con.close()

    return df


def _load_kalshi_markets(db_path: str, *, start: datetime, end: datetime) -> List[MarketMatch]:
    con = duckdb.connect(db_path, read_only=True)
    try:
        df = con.execute(
            """
            SELECT ticker, yes_sub_title, no_sub_title
            FROM kalshi_markets
            WHERE close_time >= ? AND close_time < ?
            """,
            [start, end],
        ).fetchdf()
    finally:
        con.close()

    markets: List[MarketMatch] = []
    for row in df.to_dict(orient="records"):
        parsed = _extract_teams_from_market_row(row)
        if parsed:
            markets.append(parsed)
    return markets


def _load_last_trade_price_before(
    db_path: str,
    *,
    ticker: str,
    decision_ts: datetime,
) -> Optional[Tuple[float, float]]:
    """Return (yes_price, no_price) in dollars."""

    con = duckdb.connect(db_path, read_only=True)
    try:
        row = con.execute(
            """
            SELECT yes_price, no_price
            FROM kalshi_trades
            WHERE ticker = ? AND created_time <= ?
            ORDER BY created_time DESC
            LIMIT 1
            """,
            [ticker, decision_ts],
        ).fetchone()
    finally:
        con.close()

    if not row:
        return None

    yes_price_cents, no_price_cents = row
    if yes_price_cents is None or no_price_cents is None:
        return None

    return float(yes_price_cents) / 100.0, float(no_price_cents) / 100.0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest NHL Elo vs Kalshi historical prices")
    parser.add_argument("--db", default="data/nhlstats.duckdb", help="DuckDB path")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--decision-minutes-before-close",
        type=int,
        default=30,
        help="Decision time is market close_time minus this many minutes",
    )
    parser.add_argument(
        "--use-derived-decision-prices",
        action="store_true",
        help="Use kalshi_decision_prices table instead of scanning kalshi_trades",
    )
    parser.add_argument("--min-edge", type=float, default=0.05, help="Minimum edge to take a bet")
    parser.add_argument(
        "--min-model-prob",
        type=float,
        default=0.0,
        help="Optional minimum model probability for the chosen side",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    start = _parse_ymd(str(args.start))
    end = _parse_ymd(str(args.end))

    games = _load_games(str(args.db), start=start, end=end)
    if games.empty:
        print("⚠️ No games found in date range")
        return

    markets = _load_kalshi_markets(str(args.db), start=start, end=end)
    if not markets:
        print("⚠️ No Kalshi markets found. Run backfill with --mode markets")
        return

    elo = NHLEloRating(k_factor=10, home_advantage=50)

    total_bets = 0
    total_pnl = 0.0
    total_ev = 0.0
    skipped_no_market = 0
    skipped_no_price = 0

    for row in games.to_dict(orient="records"):
        home = str(row["home_team"])
        away = str(row["away_team"])
        home_score = row["home_score"]
        away_score = row["away_score"]
        if home_score is None or away_score is None:
            continue

        match = _match_market_for_game(markets=markets, home_team=home, away_team=away)
        if not match:
            skipped_no_market += 1
            continue

        ticker, yes_is_home = match

        if bool(args.use_derived_decision_prices):
            con = duckdb.connect(str(args.db), read_only=True)
            try:
                drow = con.execute(
                    """
                    SELECT yes_price_dollars, no_price_dollars
                    FROM kalshi_decision_prices
                    WHERE ticker = ? AND decision_minutes_before_close = ?
                    LIMIT 1
                    """,
                    [ticker, int(args.decision_minutes_before_close)],
                ).fetchone()
            finally:
                con.close()

            if not drow:
                skipped_no_price += 1
                continue
            yes_price, no_price = float(drow[0]), float(drow[1])
        else:
            # We use market close_time as reference; requires market metadata.
            # Fetch close_time for this ticker.
            con = duckdb.connect(str(args.db), read_only=True)
            try:
                close_row = con.execute(
                    "SELECT close_time FROM kalshi_markets WHERE ticker = ? LIMIT 1",
                    [ticker],
                ).fetchone()
            finally:
                con.close()

            if not close_row or close_row[0] is None:
                skipped_no_price += 1
                continue

            close_time: datetime = close_row[0]
            decision_ts = close_time - timedelta(minutes=int(args.decision_minutes_before_close))

            prices = _load_last_trade_price_before(str(args.db), ticker=ticker, decision_ts=decision_ts)
            if not prices:
                skipped_no_price += 1
                continue

            yes_price, no_price = prices

        # Model probability is for home team winning.
        p_home = float(elo.predict(home, away))

        # Determine which side corresponds to home.
        p_yes = p_home if yes_is_home else 1.0 - p_home

        # Choose side with positive EV and compute realized outcome.
        home_won = bool(home_score > away_score)
        y_outcome = home_won if yes_is_home else (not home_won)

        ev_yes = p_yes - yes_price
        ev_no = (1.0 - p_yes) - no_price

        if ev_yes >= ev_no:
            chosen = "YES"
            edge = ev_yes
            model_prob = p_yes
            price = yes_price
            realized = (1.0 if y_outcome else 0.0) - price
        else:
            chosen = "NO"
            edge = ev_no
            model_prob = 1.0 - p_yes
            price = no_price
            realized = (1.0 if (not y_outcome) else 0.0) - price

        if edge < float(args.min_edge) or model_prob < float(args.min_model_prob):
            # Always update Elo after evaluating the game.
            elo.update(home, away, home_won=home_won)
            continue

        total_bets += 1
        total_ev += edge
        total_pnl += realized

        # Predict-then-update
        elo.update(home, away, home_won=home_won)

    print(
        "\n".join(
            [
                f"✅ Games evaluated: {len(games)}",
                f"✅ Bets taken: {total_bets}",
                f"ℹ️ Skipped (no market match): {skipped_no_market}",
                f"ℹ️ Skipped (no price): {skipped_no_price}",
                f"📈 Total EV (per contract): {total_ev:.3f}",
                f"💰 Total realized PnL (per contract): {total_pnl:.3f}",
                ("—"),
                f"📊 Avg EV per bet: {(total_ev / total_bets) if total_bets else 0.0:.3f}",
                f"📊 Avg PnL per bet: {(total_pnl / total_bets) if total_bets else 0.0:.3f}",
            ]
        )
    )


if __name__ == "__main__":
    main()
