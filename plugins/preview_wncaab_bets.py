"""Preview WNCAAB betting opportunities from cached Kalshi markets.

This is a lightweight, Airflow-independent verifier to answer:
"Should WNCAAB have 0 opportunities today?"

Inputs (by default):
- `data/wncaab/markets_{date}.json` from the market fetch task
- `data/wncaab_current_elo_ratings.csv` from the Elo update task

Outputs:
- Prints count + top opportunities
- Optionally diffs against `data/wncaab/bets_{date}.json`

Example:
    python3 plugins/preview_wncaab_bets.py --date 2026-01-19 --diff

"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class BetCandidate:
    """A single bet candidate derived from Elo + market price."""

    ticker: str
    title: str
    bet_on: str  # "home" or "away"
    home_team: str
    away_team: str
    elo_prob: float
    market_prob: float
    edge: float


def _normalize_team_name(name: str) -> str:
    """Normalize team names for matching Kalshi titles to Elo keys."""

    return (
        name.lower()
        .replace("&", "and")
        .replace(".", "")
        .replace("'", "")
        .replace(" ", "_")
        .strip()
    )


def _resolve_team_name(raw_name: str, *, elo_ratings: Dict[str, float]) -> Optional[str]:
    """Resolve a Kalshi title team name to an Elo key.

    Args:
        raw_name: Team name as it appears in Kalshi market title.
        elo_ratings: Elo ratings keyed by team name.

    Returns:
        Matched team key, or None if no match.
    """

    if raw_name in elo_ratings:
        return raw_name

    candidate = _normalize_team_name(raw_name)

    # 1) Exact match after normalization
    for key in elo_ratings.keys():
        if _normalize_team_name(key) == candidate:
            return key

    # 2) Common title variations
    alt = candidate.replace("_st", "_state")
    for key in elo_ratings.keys():
        if _normalize_team_name(key) == alt:
            return key

    # 3) Substring match (best-effort)
    for key in elo_ratings.keys():
        nk = _normalize_team_name(key)
        if candidate and (candidate in nk or nk in candidate):
            return key

    return None


def _load_elo_ratings(path: Path) -> Dict[str, float]:
    """Load `team,rating` CSV into a dict."""

    ratings: Dict[str, float] = {}
    with path.open("r", encoding="utf-8") as f:
        header = f.readline()
        if "team" not in header or "rating" not in header:
            raise ValueError(f"Unexpected Elo ratings header: {header.strip()}")
        for line in f:
            line = line.strip()
            if not line:
                continue
            team, rating = line.split(",", 1)
            ratings[team] = float(rating)
    return ratings


def _elo_expected(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def _predict_home_win_prob(
    *,
    elo_ratings: Dict[str, float],
    home_team: str,
    away_team: str,
    home_advantage: float,
    initial_rating: float = 1500.0,
) -> float:
    """Predict home win probability using standard Elo formula."""

    rh = elo_ratings.get(home_team, initial_rating)
    ra = elo_ratings.get(away_team, initial_rating)
    return _elo_expected(rh + home_advantage, ra)


def _parse_title_away_home(title: str) -> Optional[Tuple[str, str]]:
    if " at " not in title:
        return None
    teams_part = title.split(" Winner?")[0] if " Winner?" in title else title
    try:
        away_raw, home_raw = teams_part.split(" at ")
    except ValueError:
        return None
    return away_raw.strip(), home_raw.strip()


def compute_bets_from_cached_markets(
    *,
    markets: Sequence[Dict[str, Any]],
    elo_ratings: Dict[str, float],
    elo_threshold: float,
    min_edge: float,
    home_advantage: float,
) -> List[BetCandidate]:
    """Compute WNCAAB bets from cached markets using DAG-equivalent logic."""

    out: List[BetCandidate] = []

    for market in markets:
        ticker = str(market.get("ticker", ""))
        title = str(market.get("title", ""))
        if "-" not in ticker:
            continue

        parts = ticker.split("-")
        parsed = _parse_title_away_home(title)
        if not parsed:
            continue

        away_raw, home_raw = parsed
        away_team = _resolve_team_name(away_raw, elo_ratings=elo_ratings)
        home_team = _resolve_team_name(home_raw, elo_ratings=elo_ratings)
        if not away_team or not home_team:
            continue

        home_win_prob = _predict_home_win_prob(
            elo_ratings=elo_ratings,
            home_team=home_team,
            away_team=away_team,
            home_advantage=home_advantage,
        )

        yes_ask = float(market.get("yes_ask", 0)) / 100.0
        if yes_ask <= 0 or yes_ask >= 1.0:
            # Treat 0/100 as untradeable / missing pricing.
            continue

        event_part = parts[1] if len(parts) > 1 else ""
        team_code = parts[-1]

        # If event string ends with the code, it represents the home team.
        target_side = "home" if event_part.endswith(team_code) else "away"
        elo_prob = home_win_prob if target_side == "home" else (1.0 - home_win_prob)
        market_prob = yes_ask
        edge = elo_prob - market_prob

        if elo_prob > elo_threshold and edge > min_edge:
            out.append(
                BetCandidate(
                    ticker=ticker,
                    title=title,
                    bet_on=target_side,
                    home_team=home_team,
                    away_team=away_team,
                    elo_prob=float(elo_prob),
                    market_prob=float(market_prob),
                    edge=float(edge),
                )
            )

    out.sort(key=lambda b: b.edge, reverse=True)
    return out


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview WNCAAB bets from cached markets")
    parser.add_argument("--date", required=True, help="Date YYYY-MM-DD")
    parser.add_argument(
        "--markets",
        default=None,
        help="Override markets JSON path (default: data/wncaab/markets_{date}.json)",
    )
    parser.add_argument(
        "--elo",
        default="data/wncaab_current_elo_ratings.csv",
        help="WNCAAB Elo ratings CSV path",
    )
    parser.add_argument("--elo-threshold", type=float, default=0.65)
    parser.add_argument("--min-edge", type=float, default=0.05)
    parser.add_argument("--home-advantage", type=float, default=100.0)
    parser.add_argument("--top", type=int, default=20, help="Show top N")
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Diff against existing data/wncaab/bets_{date}.json if present",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    date_str = str(args.date)

    markets_path = Path(args.markets) if args.markets else Path(f"data/wncaab/markets_{date_str}.json")
    elo_path = Path(str(args.elo))

    if not markets_path.exists():
        raise FileNotFoundError(f"Markets file not found: {markets_path}")
    if not elo_path.exists():
        raise FileNotFoundError(f"Elo ratings file not found: {elo_path}")

    markets = _load_json(markets_path)
    if not isinstance(markets, list):
        raise ValueError("Markets JSON must be a list")

    elo_ratings = _load_elo_ratings(elo_path)

    bets = compute_bets_from_cached_markets(
        markets=markets,
        elo_ratings=elo_ratings,
        elo_threshold=float(args.elo_threshold),
        min_edge=float(args.min_edge),
        home_advantage=float(args.home_advantage),
    )

    print(f"✅ Markets loaded: {len(markets)}")
    print(f"✅ Elo teams loaded: {len(elo_ratings)}")
    print(f"🎯 Bets found: {len(bets)} (threshold={args.elo_threshold:.2f}, min_edge={args.min_edge:.2f})")

    for b in bets[: int(args.top)]:
        print(
            f"  ✓ {b.title} | bet_on={b.bet_on} | elo={b.elo_prob:.1%} | mkt={b.market_prob:.1%} | edge={b.edge:.1%}"
        )

    if args.diff:
        bets_file = Path(f"data/wncaab/bets_{date_str}.json")
        if not bets_file.exists():
            print(f"ℹ️ No existing bets file to diff: {bets_file}")
            return

        existing = _load_json(bets_file)
        existing_tickers = set()
        if isinstance(existing, list):
            for row in existing:
                if isinstance(row, dict) and row.get("ticker"):
                    existing_tickers.add(str(row.get("ticker")))

        new_tickers = {b.ticker for b in bets}
        added = sorted(new_tickers - existing_tickers)
        removed = sorted(existing_tickers - new_tickers)

        print("—")
        print(f"🔎 Diff vs {bets_file}:")
        print(f"  + would add: {len(added)}")
        print(f"  - would remove: {len(removed)}")
        if added[:10]:
            print(f"  sample added: {added[:10]}")
        if removed[:10]:
            print(f"  sample removed: {removed[:10]}")


if __name__ == "__main__":
    main()
