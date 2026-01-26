#!/usr/bin/env python3
"""
Backtest basketball (NBA, NCAAB, WNCAAB) using historical Kalshi market data.

This script:
1. Pulls historical Kalshi markets and trades for basketball series
2. Matches markets to games in our database
3. Calculates Elo predictions using ratings from BEFORE each game
4. Compares Elo probabilities to Kalshi market prices
5. Simulates betting performance with actual historical outcomes

Series Tickers:
- KXNBAGAME (NBA)
- KXCBBALLGAME (NCAA Basketball - Men's)
- KXWCBALLGAME (NCAA Basketball - Women's)

Example:
    # Backtest NBA for current season
    python backtest_basketball_kalshi.py --sport NBA --start 2024-10-01 --end 2025-01-20

    # Backtest NCAAB
    python backtest_basketball_kalshi.py --sport NCAAB --start 2024-11-01 --end 2025-01-20

    # Backtest WNCAAB
    python backtest_basketball_kalshi.py --sport WNCAAB --start 2024-11-01 --end 2025-01-20
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb
import pandas as pd

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent / "plugins"))

from plugins.elo import NBAEloRating
from plugins.elo import NCAABEloRating
from plugins.elo import WNCAABEloRating


# Sport configuration
SPORT_CONFIG = {
    "NBA": {
        "series_ticker": "KXNBAGAME",
        "elo_class": NBAEloRating,
        "k_factor": 20,
        "home_advantage": 100,
        "threshold": 0.73,
        "table": "nba_games",
        "db_query": """
            SELECT
                game_id,
                game_date,
                home_team_name as home_team,
                away_team_name as away_team,
                home_score,
                away_score,
                (home_score > away_score) AS home_won
            FROM nba_games
            WHERE game_date >= ? AND game_date < ?
            ORDER BY game_date ASC
        """,
    },
    "NCAAB": {
        "series_ticker": "KXNCAABGAME",
        "elo_class": NCAABEloRating,
        "k_factor": 20,
        "home_advantage": 100,
        "threshold": 0.72,
        "table": "ncaab_games",
        "db_query": """
            SELECT
                game_id,
                game_date,
                home_team,
                away_team,
                home_score,
                away_score,
                COALESCE(neutral_site, false) as neutral,
                (home_score > away_score) AS home_won
            FROM ncaab_games
            WHERE game_date >= ? AND game_date < ?
            ORDER BY game_date ASC
        """,
    },
    "WNCAAB": {
        "series_ticker": "KXNCAAWBGAME",
        "elo_class": WNCAABEloRating,
        "k_factor": 20,
        "home_advantage": 100,
        "threshold": 0.72,
        "table": "wncaab_games",
        "db_query": """
            SELECT
                game_id,
                game_date,
                home_team,
                away_team,
                home_score,
                away_score,
                COALESCE(neutral_site, false) as neutral,
                (home_score > away_score) AS home_won
            FROM wncaab_games
            WHERE game_date >= ? AND game_date < ?
            ORDER BY game_date ASC
        """,
    },
}


def _parse_ymd(value: str) -> datetime:
    """Parse YYYY-MM-DD string to datetime."""
    return datetime.strptime(value, "%Y-%m-%d")


def _norm_name(value: str) -> str:
    """Normalize team name for matching."""
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


@dataclass(frozen=True)
class MarketMatch:
    """Kalshi market metadata for matching."""

    ticker: str
    yes_team: str
    no_team: str
    close_time: datetime


def _extract_teams_from_market_row(row: Dict[str, Any]) -> Optional[MarketMatch]:
    """Parse Kalshi market row to extract team names."""
    ticker = row.get("ticker")
    yes_sub = row.get("yes_sub_title")
    no_sub = row.get("no_sub_title")
    close_time = row.get("close_time")

    if not ticker or not yes_sub or not no_sub or not close_time:
        return None

    return MarketMatch(
        ticker=str(ticker),
        yes_team=_norm_name(str(yes_sub)),
        no_team=_norm_name(str(no_sub)),
        close_time=close_time,
    )


def _team_match_score(team: str, candidate: str) -> int:
    """Calculate match score between team names (higher is better)."""
    team_n = _norm_name(team)
    cand_n = _norm_name(candidate)

    if team_n == cand_n:
        return 100
    if team_n in cand_n or cand_n in team_n:
        return 80

    team_tokens = set(team_n.split())
    cand_tokens = set(cand_n.split())
    overlap = len(team_tokens.intersection(cand_tokens))

    return overlap * 20


def _match_market_for_game(
    markets: List[MarketMatch],
    home_team: str,
    away_team: str,
) -> Optional[Tuple[str, bool, datetime]]:
    """
    Match a game to a Kalshi market.

    Returns:
        (ticker, yes_is_home, close_time) or None
    """
    best: Optional[Tuple[int, str, bool, datetime]] = None

    for m in markets:
        # Scenario 1: YES = home team, NO = away team
        score_home_yes = _team_match_score(home_team, m.yes_team)
        score_away_no = _team_match_score(away_team, m.no_team)
        score_yes_home = score_home_yes + score_away_no

        # Scenario 2: YES = away team, NO = home team
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
            best = (score, m.ticker, yes_is_home, m.close_time)

    if best is None:
        return None

    score, ticker, yes_is_home, close_time = best

    # Require minimum match confidence
    if score < 100:  # Require exact or substring match
        return None

    return ticker, yes_is_home, close_time


def _load_games(
    db_path: str, sport: str, start: datetime, end: datetime
) -> pd.DataFrame:
    """Load games from DuckDB."""
    config = SPORT_CONFIG[sport]

    con = duckdb.connect(db_path, read_only=True)
    try:
        df = con.execute(config["db_query"], [start.date(), end.date()]).fetchdf()
    finally:
        con.close()

    return df


def _load_kalshi_markets(
    db_path: str, start: datetime, end: datetime
) -> List[MarketMatch]:
    """Load Kalshi markets from DuckDB."""
    con = duckdb.connect(db_path, read_only=True)
    try:
        df = con.execute(
            """
            SELECT ticker, yes_sub_title, no_sub_title, close_time
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
    ticker: str,
    decision_ts: datetime,
) -> Optional[Tuple[float, float]]:
    """
    Get last trade prices before decision timestamp.

    Returns:
        (yes_price, no_price) in dollars or None
    """
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


@dataclass
class BacktestResult:
    """Results from backtesting."""

    sport: str
    start_date: str
    end_date: str
    total_games: int
    matched_games: int
    bets_taken: int
    bets_won: int
    bets_lost: int
    total_ev: float
    total_pnl: float
    win_rate: float
    avg_ev_per_bet: float
    avg_pnl_per_bet: float
    roi: float
    skipped_no_market: int
    skipped_no_price: int
    skipped_no_edge: int


def run_backtest(
    sport: str,
    start: datetime,
    end: datetime,
    db_path: str = "data/nhlstats.duckdb",
    min_edge: float = 0.05,
    decision_minutes_before_close: int = 30,
) -> BacktestResult:
    """
    Run backtest for a sport using historical Kalshi data.

    Args:
        sport: Sport name (NBA, NCAAB, WNCAAB)
        start: Start date
        end: End date
        db_path: Path to DuckDB database
        min_edge: Minimum edge required to bet (default 5%)
        decision_minutes_before_close: Minutes before market close to make decision

    Returns:
        BacktestResult with performance metrics
    """
    print(f"\n{'=' * 80}")
    print(f"🏀 BACKTESTING {sport} - {start.date()} to {end.date()}")
    print(f"{'=' * 80}\n")

    config = SPORT_CONFIG[sport]

    # Load games
    print(f"📥 Loading {sport} games...")
    games = _load_games(db_path, sport, start, end)
    if games.empty:
        print(f"⚠️  No {sport} games found in date range")
        return BacktestResult(
            sport=sport,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            total_games=0,
            matched_games=0,
            bets_taken=0,
            bets_won=0,
            bets_lost=0,
            total_ev=0.0,
            total_pnl=0.0,
            win_rate=0.0,
            avg_ev_per_bet=0.0,
            avg_pnl_per_bet=0.0,
            roi=0.0,
            skipped_no_market=0,
            skipped_no_price=0,
            skipped_no_edge=0,
        )

    print(f"   Found {len(games):,} games")

    # Load Kalshi markets
    print(f"📥 Loading Kalshi markets for {config['series_ticker']}...")
    markets = _load_kalshi_markets(db_path, start, end)
    if not markets:
        print("⚠️  No Kalshi markets found.")
        print("   Run: python -m plugins.kalshi_historical_data --mode markets \\")
        print(f"        --series-ticker {config['series_ticker']} \\")
        print(
            f"        --start {start.strftime('%Y-%m-%d')} --end {end.strftime('%Y-%m-%d')}"
        )
        return BacktestResult(
            sport=sport,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            total_games=len(games),
            matched_games=0,
            bets_taken=0,
            bets_won=0,
            bets_lost=0,
            total_ev=0.0,
            total_pnl=0.0,
            win_rate=0.0,
            avg_ev_per_bet=0.0,
            avg_pnl_per_bet=0.0,
            roi=0.0,
            skipped_no_market=len(games),
            skipped_no_price=0,
            skipped_no_edge=0,
        )

    print(f"   Found {len(markets):,} markets")

    # Initialize Elo system
    print("🎯 Initializing Elo rating system...")
    elo = config["elo_class"](
        k_factor=config["k_factor"], home_advantage=config["home_advantage"]
    )
    threshold = config["threshold"]
    print(f"   K-factor: {config['k_factor']}")
    print(f"   Home advantage: {config['home_advantage']}")
    print(f"   Betting threshold: {threshold:.1%}")
    print(f"   Minimum edge: {min_edge:.1%}")

    # Backtest loop
    print("\n📊 Running backtest...\n")

    total_bets = 0
    bets_won = 0
    bets_lost = 0
    total_pnl = 0.0
    total_ev = 0.0
    skipped_no_market = 0
    skipped_no_price = 0
    skipped_no_edge = 0
    matched_games = 0

    bet_details = []

    for idx, row in games.iterrows():
        home = str(row["home_team"])
        away = str(row["away_team"])
        home_score = row.get("home_score")
        away_score = row.get("away_score")
        game_date = row["game_date"]

        if home_score is None or away_score is None:
            continue

        home_won = bool(row.get("home_won", home_score > away_score))
        is_neutral = bool(row.get("neutral", False)) if "neutral" in row else False

        # Match game to Kalshi market
        match = _match_market_for_game(markets, home, away)
        if not match:
            skipped_no_market += 1
            # Still update Elo with outcome
            if sport in ["NCAAB", "WNCAAB"]:
                elo.update(home, away, home_won, is_neutral=is_neutral)
            else:
                elo.update(home, away, home_won)
            continue

        ticker, yes_is_home, close_time = match
        matched_games += 1

        # Get decision timestamp
        decision_ts = close_time - timedelta(minutes=decision_minutes_before_close)

        # Get Kalshi market price at decision time
        prices = _load_last_trade_price_before(db_path, ticker, decision_ts)
        if not prices:
            skipped_no_price += 1
            # Still update Elo
            if sport in ["NCAAB", "WNCAAB"]:
                elo.update(home, away, home_won, is_neutral=is_neutral)
            else:
                elo.update(home, away, home_won)
            continue

        yes_price, no_price = prices

        # CRITICAL: Predict BEFORE updating Elo
        if sport in ["NCAAB", "WNCAAB"]:
            p_home = float(elo.predict(home, away, is_neutral=is_neutral))
        else:
            p_home = float(elo.predict(home, away))

        # Convert to YES side probability
        p_yes = p_home if yes_is_home else (1.0 - p_home)

        # Calculate edge for both sides
        ev_yes = p_yes - yes_price
        ev_no = (1.0 - p_yes) - no_price

        # Determine actual outcome for YES side
        y_outcome = home_won if yes_is_home else (not home_won)

        # Choose side with better edge
        if ev_yes >= ev_no:
            chosen_side = "YES"
            edge = ev_yes
            model_prob = p_yes
            price = yes_price
            realized_pnl = (1.0 if y_outcome else 0.0) - price
            bet_won = y_outcome
        else:
            chosen_side = "NO"
            edge = ev_no
            model_prob = 1.0 - p_yes
            price = no_price
            realized_pnl = (1.0 if (not y_outcome) else 0.0) - price
            bet_won = not y_outcome

        # Check if bet meets criteria
        if edge < min_edge or model_prob < threshold:
            skipped_no_edge += 1
            # Update Elo after evaluation
            if sport in ["NCAAB", "WNCAAB"]:
                elo.update(home, away, home_won, is_neutral=is_neutral)
            else:
                elo.update(home, away, home_won)
            continue

        # Place bet
        total_bets += 1
        if bet_won:
            bets_won += 1
        else:
            bets_lost += 1

        total_ev += edge
        total_pnl += realized_pnl

        # Store bet details
        bet_details.append(
            {
                "date": game_date,
                "game": f"{home} vs {away}",
                "ticker": ticker,
                "side": chosen_side,
                "model_prob": f"{model_prob:.1%}",
                "price": f"${price:.2f}",
                "edge": f"{edge:.1%}",
                "outcome": "✅ WIN" if bet_won else "❌ LOSS",
                "pnl": f"${realized_pnl:+.2f}",
            }
        )

        # Update Elo AFTER prediction
        if sport in ["NCAAB", "WNCAAB"]:
            elo.update(home, away, home_won, is_neutral=is_neutral)
        else:
            elo.update(home, away, home_won)

    # Calculate metrics
    win_rate = (bets_won / total_bets) if total_bets > 0 else 0.0
    avg_ev = (total_ev / total_bets) if total_bets > 0 else 0.0
    avg_pnl = (total_pnl / total_bets) if total_bets > 0 else 0.0
    roi = (total_pnl / total_bets) if total_bets > 0 else 0.0

    # Print results
    print(f"\n{'=' * 80}")
    print(f"📈 BACKTEST RESULTS - {sport}")
    print(f"{'=' * 80}\n")

    print(f"📅 Date Range: {start.date()} to {end.date()}")
    print(f"🏀 Total Games: {len(games):,}")
    print(
        f"✅ Matched to Kalshi Markets: {matched_games:,} ({matched_games / len(games) * 100:.1f}%)"
    )
    print("\n🎲 BETTING PERFORMANCE:")
    print(f"   Bets Placed: {total_bets:,}")
    print(f"   Bets Won: {bets_won:,}")
    print(f"   Bets Lost: {bets_lost:,}")
    print(f"   Win Rate: {win_rate:.1%}")
    print("\n💰 FINANCIAL PERFORMANCE:")
    print(f"   Total EV: ${total_ev:+.2f} (per contract)")
    print(f"   Total P&L: ${total_pnl:+.2f} (per contract)")
    print(f"   Avg EV per Bet: ${avg_ev:+.2f}")
    print(f"   Avg P&L per Bet: ${avg_pnl:+.2f}")
    print(f"   ROI: {roi:+.1%}")
    print("\n⚠️  SKIPPED GAMES:")
    print(f"   No Market Match: {skipped_no_market:,}")
    print(f"   No Price Data: {skipped_no_price:,}")
    print(f"   Below Threshold/Edge: {skipped_no_edge:,}")

    # Show sample bets
    if bet_details:
        print("\n📋 SAMPLE BETS (first 10):")
        df_bets = pd.DataFrame(bet_details[:10])
        print(df_bets.to_string(index=False))

        if len(bet_details) > 10:
            print(f"\n   ... and {len(bet_details) - 10} more bets")

    print(f"\n{'=' * 80}\n")

    return BacktestResult(
        sport=sport,
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        total_games=len(games),
        matched_games=matched_games,
        bets_taken=total_bets,
        bets_won=bets_won,
        bets_lost=bets_lost,
        total_ev=total_ev,
        total_pnl=total_pnl,
        win_rate=win_rate,
        avg_ev_per_bet=avg_ev,
        avg_pnl_per_bet=avg_pnl,
        roi=roi,
        skipped_no_market=skipped_no_market,
        skipped_no_price=skipped_no_price,
        skipped_no_edge=skipped_no_edge,
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Backtest basketball betting using historical Kalshi data"
    )
    parser.add_argument(
        "--sport",
        choices=["NBA", "NCAAB", "WNCAAB", "ALL"],
        required=True,
        help="Sport to backtest",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--db",
        default="data/nhlstats.duckdb",
        help="Path to DuckDB database",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=0.05,
        help="Minimum edge to place bet (default: 0.05 = 5%%)",
    )
    parser.add_argument(
        "--decision-minutes",
        type=int,
        default=30,
        help="Minutes before close to make decision (default: 30)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    start = _parse_ymd(args.start)
    end = _parse_ymd(args.end)

    sports_to_test = ["NBA", "NCAAB", "WNCAAB"] if args.sport == "ALL" else [args.sport]

    results = []

    for sport in sports_to_test:
        result = run_backtest(
            sport=sport,
            start=start,
            end=end,
            db_path=args.db,
            min_edge=args.min_edge,
            decision_minutes_before_close=args.decision_minutes,
        )
        results.append(result)

    # Print summary if multiple sports
    if len(results) > 1:
        print(f"\n{'=' * 80}")
        print("🏆 OVERALL SUMMARY")
        print(f"{'=' * 80}\n")

        summary_data = []
        for r in results:
            summary_data.append(
                {
                    "Sport": r.sport,
                    "Games": r.total_games,
                    "Bets": r.bets_taken,
                    "Win Rate": f"{r.win_rate:.1%}",
                    "Avg P&L": f"${r.avg_pnl_per_bet:+.2f}",
                    "ROI": f"{r.roi:+.1%}",
                    "Total P&L": f"${r.total_pnl:+.2f}",
                }
            )

        df_summary = pd.DataFrame(summary_data)
        print(df_summary.to_string(index=False))
        print()


if __name__ == "__main__":
    main()
