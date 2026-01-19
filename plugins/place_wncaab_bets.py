"""Place WNCAAB bets with an external (non-Kalshi) game-start-time gate.

CRITICAL REQUIREMENT:
- Do NOT place any bet if the scheduled game start time has passed.
- We verify start status using ESPN's public scoreboard API, not Kalshi market status.

This script recomputes today's WNCAAB opportunities from cached markets + Elo,
then places exactly 1 contract per opportunity if and only if:
- ESPN event state is 'pre' AND
- now < ESPN scheduled start time

Example:
    python3 plugins/place_wncaab_bets.py --date 2026-01-19 --dry-run
    python3 plugins/place_wncaab_bets.py --date 2026-01-19 --execute

Notes:
- Uses limit orders at current ask (YES for home bets, NO for away bets).
- Credentials are loaded from `kalshkey` like other scripts in this repo.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests


# Ensure sibling imports work when running `python3 plugins/...` from repo root.
import sys

sys.path.append(str(Path(__file__).resolve().parent))

from kalshi_betting import KalshiBetting  # noqa: E402
from preview_wncaab_bets import (  # noqa: E402
    BetCandidate,
    compute_bets_from_cached_markets,
)


@dataclass(frozen=True)
class EspnEvent:
    """A simplified ESPN scoreboard event."""

    start_time_utc: datetime
    state: str  # pre|in|post
    away_name: str
    home_name: str


def _read_kalshkey() -> Tuple[str, Path]:
    """Load API key ID and write PEM key file.

    Returns:
        (api_key_id, pem_path)

    Raises:
        FileNotFoundError: If `kalshkey` file is not found.
        ValueError: If required materials cannot be extracted.
    """

    kalshkey_path = Path("kalshkey")
    if not kalshkey_path.exists():
        kalshkey_path = Path("/opt/airflow/kalshkey")

    if not kalshkey_path.exists():
        raise FileNotFoundError("kalshkey file not found")

    content = kalshkey_path.read_text(encoding="utf-8")

    api_key_id: Optional[str] = None
    for line in content.split("\n"):
        if "API key id:" in line:
            api_key_id = line.split(":", 1)[1].strip()
            break

    if not api_key_id:
        raise ValueError("Could not find API key ID in kalshkey file")

    private_key_lines: List[str] = []
    in_key = False
    for line in content.split("\n"):
        if "-----BEGIN RSA PRIVATE KEY-----" in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if "-----END RSA PRIVATE KEY-----" in line:
            break

    if not private_key_lines:
        raise ValueError("Could not extract RSA private key from kalshkey")

    # Write to a unique temp file to avoid clobbering any existing path.
    # (Some environments may already have a directory named kalshi_private_key.pem.)
    fd, tmp_path = tempfile.mkstemp(prefix="kalshi_private_key_", suffix=".pem")
    pem_path = Path(tmp_path)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(private_key_lines))

    return api_key_id, pem_path


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_tokens(name: str) -> List[str]:
    s = (
        name.lower()
        .replace("&", "and")
        .replace("'", "")
        .replace(".", " ")
        .replace("-", " ")
        .replace("_", " ")
    )
    tokens = [t for t in s.split() if t]

    # Drop common filler words.
    drop = {"university", "college", "the", "of"}
    tokens = [t for t in tokens if t not in drop]

    # Normalize a few common abbreviations.
    out: List[str] = []
    for t in tokens:
        if t in {"st", "st."}:
            out.append("st")
        elif t == "state":
            out.append("st")
        else:
            out.append(t)
    return out


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _coverage(a: Sequence[str], b: Sequence[str]) -> float:
    """Token coverage of a within b.

    This is more robust than Jaccard for matching a short team name
    (e.g., "Houston") to ESPN strings that may include mascots.
    """

    sa, sb = set(a), set(b)
    if not sa:
        return 0.0
    return len(sa & sb) / len(sa)


def _fetch_espn_wncaab_scoreboard(date_str: str, timeout: float = 10.0) -> List[EspnEvent]:
    """Fetch ESPN WNCAAB scoreboard for a date.

    Args:
        date_str: YYYY-MM-DD
        timeout: HTTP timeout seconds

    Returns:
        List of simplified events with start time + state.
    """

    yyyymmdd = date_str.replace("-", "")
    # ESPN endpoints vary; try the stable "site" API first and fall back.
    urls = [
        "https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard",
        "https://site.web.api.espn.com/apis/v2/sports/basketball/womens-college-basketball/scoreboard",
    ]
    params = {"dates": yyyymmdd}

    last_exc: Optional[Exception] = None
    data: Optional[Dict[str, Any]] = None
    for url in urls:
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            last_exc = e
            continue

    if data is None:
        raise RuntimeError(f"Failed to fetch ESPN scoreboard ({yyyymmdd}): {last_exc}")

    events: List[EspnEvent] = []
    for event in data.get("events", []) or []:
        comps = event.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]

        date_iso = comp.get("date")
        if not date_iso:
            continue
        start_time = datetime.fromisoformat(date_iso.replace("Z", "+00:00")).astimezone(timezone.utc)

        status = comp.get("status", {}).get("type", {})
        state = str(status.get("state", "")).lower()

        competitors = comp.get("competitors") or []
        home_name, away_name = None, None
        for c in competitors:
            team = c.get("team") or {}
            # Prefer displayName (often includes full school name). Some shortDisplayName
            # values are abbreviations (e.g., "FAU"), which breaks matching.
            name = team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""
            if c.get("homeAway") == "home":
                home_name = name
            elif c.get("homeAway") == "away":
                away_name = name

        if not home_name or not away_name:
            continue

        events.append(
            EspnEvent(
                start_time_utc=start_time,
                state=state,
                away_name=str(away_name),
                home_name=str(home_name),
            )
        )

    return events


def _match_event(
    *,
    away_team: str,
    home_team: str,
    events: Sequence[EspnEvent],
    min_score: float = 0.80,
) -> Optional[EspnEvent]:
    """Best-effort match of a market matchup to an ESPN event."""

    away_tokens = _normalize_tokens(away_team)
    home_tokens = _normalize_tokens(home_team)

    best: Optional[Tuple[float, float, EspnEvent]] = None
    for ev in events:
        ev_away = _normalize_tokens(ev.away_name)
        ev_home = _normalize_tokens(ev.home_name)
        cov = 0.5 * _coverage(away_tokens, ev_away) + 0.5 * _coverage(home_tokens, ev_home)
        jac = 0.5 * _jaccard(away_tokens, ev_away) + 0.5 * _jaccard(home_tokens, ev_home)
        if best is None or cov > best[0] or (cov == best[0] and jac > best[1]):
            best = (cov, jac, ev)

    if not best:
        return None
    if best[0] < min_score:
        return None
    return best[2]


def _should_place_based_on_espn(
    *,
    bet: BetCandidate,
    events: Sequence[EspnEvent],
    now_utc: datetime,
) -> Tuple[bool, str]:
    """Return (eligible, reason)."""

    ev = _match_event(away_team=bet.away_team, home_team=bet.home_team, events=events)
    if not ev:
        return False, "No ESPN match"

    if ev.state != "pre":
        return False, f"ESPN state={ev.state}"

    if now_utc >= ev.start_time_utc:
        return False, f"Past start time ({ev.start_time_utc.isoformat()})"

    return True, f"ESPN pre; starts {ev.start_time_utc.isoformat()}"


def _extract_game_date_from_ticker(ticker: str) -> Optional[str]:
    """Extract YYYY-MM-DD game date from a Kalshi sports ticker.

    WNCAAB tickers in this repo look like:
        KXNCAAWBGAME-26JAN21HOUKSU-HOU
                     ^^^^^^^
    """

    parts = ticker.split("-")
    if len(parts) < 2:
        return None
    chunk = parts[1]
    if len(chunk) < 7:
        return None
    date_token = chunk[:7]  # e.g. 26JAN21
    try:
        dt = datetime.strptime(date_token, "%y%b%d")
    except Exception:
        return None
    return dt.strftime("%Y-%m-%d")


def _place_one_contract(
    *,
    client: KalshiBetting,
    ticker: str,
    side: str,
    trade_date: str,
) -> Optional[Dict[str, Any]]:
    """Place exactly 1 contract as a limit order at current ask."""

    market = client.get_market_details(ticker)
    if not market:
        print(f"   ❌ Cannot fetch market details")
        return None

    ask_key = f"{side}_ask"
    ask_price = market.get(ask_key)
    if ask_price is None:
        print(f"   ❌ Missing {ask_key}")
        return None

    # Use the shared place_bet() path so we inherit the global per-ticker dedupe.
    # Convert 1 contract at ask_price into an equivalent $ amount.
    amount = float(ask_price) / 100.0
    resp = client.place_bet(ticker=ticker, side=side, amount=amount, price=int(ask_price), trade_date=trade_date)
    if resp:
        print(f"   ✅ Order placed: {ticker} {side.upper()} 1 @ {ask_price}¢")
    return resp


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Place WNCAAB bets (1 contract each) gated by ESPN start time")
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
    parser.add_argument("--dry-run", action="store_true", help="Print what would be placed")
    parser.add_argument("--execute", action="store_true", help="Actually place orders")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)

    if args.execute and args.dry_run:
        raise ValueError("Use only one of --dry-run or --execute")
    if not args.execute and not args.dry_run:
        # Safer default.
        args.dry_run = True

    date_str = str(args.date)
    markets_path = Path(args.markets) if args.markets else Path(f"data/wncaab/markets_{date_str}.json")
    elo_path = Path(str(args.elo))

    markets = _load_json(markets_path)
    if not isinstance(markets, list):
        raise ValueError("Markets JSON must be a list")

    # Reuse preview module's Elo loader via its public entry point logic: read csv inline.
    elo_ratings: Dict[str, float] = {}
    with elo_path.open("r", encoding="utf-8") as f:
        header = f.readline()
        if "team" not in header or "rating" not in header:
            raise ValueError(f"Unexpected Elo ratings header: {header.strip()}")
        for line in f:
            line = line.strip()
            if not line:
                continue
            team, rating = line.split(",", 1)
            elo_ratings[team] = float(rating)

    bets = compute_bets_from_cached_markets(
        markets=markets,
        elo_ratings=elo_ratings,
        elo_threshold=float(args.elo_threshold),
        min_edge=float(args.min_edge),
        home_advantage=float(args.home_advantage),
    )

    print(f"✅ Bets to consider: {len(bets)}")
    if not bets:
        return

    now_utc = datetime.now(timezone.utc)

    # Fetch ESPN events for the actual game dates derived from tickers.
    date_to_events: Dict[str, List[EspnEvent]] = {}
    game_dates = sorted({(_extract_game_date_from_ticker(b.ticker) or date_str) for b in bets})
    for gd in game_dates:
        print(f"📡 Fetching ESPN scoreboard for {gd}...")
        date_to_events[gd] = _fetch_espn_wncaab_scoreboard(gd)
        print(f"✅ ESPN events ({gd}): {len(date_to_events[gd])}")

    eligible: List[BetCandidate] = []
    for b in bets:
        gd = _extract_game_date_from_ticker(b.ticker) or date_str
        ok, reason = _should_place_based_on_espn(
            bet=b,
            events=date_to_events.get(gd, []),
            now_utc=now_utc,
        )
        if ok:
            eligible.append(b)
            print(f"🟢 ELIGIBLE: {b.title} | {reason}")
        else:
            print(f"🔴 SKIP:     {b.title} | {reason}")

    if args.dry_run:
        print(f"\n🔍 DRY RUN: Would place {len(eligible)} orders (1 contract each)")
        for b in eligible:
            side = "yes" if b.bet_on == "home" else "no"
            print(f"  - {b.ticker} {side.upper()} (1 contract)")
        return

    # Execute orders
    api_key_id, pem_path = _read_kalshkey()
    try:
        client = KalshiBetting(api_key_id=api_key_id, private_key_path=str(pem_path))
        print(f"\n🚀 EXECUTING: placing {len(eligible)} orders (1 contract each)")
        for b in eligible:
            side = "yes" if b.bet_on == "home" else "no"
            print(f"\n🎯 {b.title}\n   ticker={b.ticker} side={side.upper()} (1 contract)")
            gd = _extract_game_date_from_ticker(b.ticker) or date_str
            _place_one_contract(client=client, ticker=b.ticker, side=side, trade_date=gd)
            time.sleep(1)
    finally:
        if pem_path.exists():
            pem_path.unlink()


if __name__ == "__main__":
    main()
