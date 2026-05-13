#!/usr/bin/env python3
"""
CLV (Closing Line Value) Tracker

This module tracks closing line values to validate that our model beats the market.

CLV = Bet Line Probability - Closing Line Probability

- Positive CLV means we got better odds than the closing line (good!)
- Negative CLV means the market moved against us (bad)

Consistent positive CLV is the #1 indicator of long-term profitability.

Real closing prices are sourced from the game_odds table — the last pre-market-close
snapshot of decimal odds from any acceptable bookmaker, converted to implied probability.
"""

import sys
import os
from functools import lru_cache

sys.path.append(os.path.dirname(__file__))

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import inspect

from plugins.constants import (
    ACCEPTABLE_BOOKMAKERS,
    STALE_CLOSING_PRICE_HOURS,
)
from plugins.db_manager import default_db
from plugins.pricing_governance import (
    CLVEvidenceTier,
    GovernedPriceQuote,
    PriceRole,
    build_clv_governance_snapshot,
    select_close_quote,
)


def _resolve_outcome_name(bet_on: str, home_team: str, away_team: str) -> str:
    """Map bet_on value to game_odds outcome_name ('home' or 'away').

    Args:
        bet_on: Value from placed_bets — 'home', 'away', or a team abbreviation.
        home_team: Home team identifier from placed_bets.
        away_team: Away team identifier from placed_bets.

    Returns:
        'home' or 'away' matching game_odds.outcome_name convention.
    """
    bet_on_lower = bet_on.strip().lower() if bet_on else "home"
    if bet_on_lower == "home":
        return "home"
    if bet_on_lower == "away":
        return "away"
    # bet_on is a team abbreviation — match against home/away
    if bet_on.upper() == home_team.upper():
        return "home"
    if bet_on.upper() == away_team.upper():
        return "away"
    # Default to home if can't resolve
    return "home"


def compute_real_closing_price(
    bet_id: str,
    sport: str,
    home_team: str,
    away_team: str,
    bet_on: str,
    placed_date: str,
    market_close_time_utc: Optional[datetime] = None,
) -> Optional[float]:
    """Compute real closing price from game_odds for a placed bet.

    Joins placed_bets → unified_games (via sport/date/teams) → game_odds to find
    the last pre-close odds snapshot, then converts decimal odds to implied probability.

    Args:
        bet_id: Bet identifier (for logging).
        sport: Sport code (e.g., 'NBA', 'NHL').
        home_team: Home team from placed_bets.
        away_team: Away team from placed_bets.
        bet_on: 'home', 'away', or team abbreviation.
        placed_date: Date string (YYYY-MM-DD) from placed_bets.
        market_close_time_utc: When the market closed (for snapshot filtering).

    Returns:
        Implied probability (0.0–1.0) from closing odds, or None if unavailable.
    """
    outcome_name = _resolve_outcome_name(bet_on, home_team, away_team)

    # Step 1: Find game_id from unified_games
    game_id = _find_game_id(sport, placed_date, home_team, away_team)
    if not game_id:
        return None

    # Step 2: Find latest pre-close odds snapshot
    closing_quote = _find_closing_quote(game_id, outcome_name, market_close_time_utc)
    if closing_quote is None:
        return None

    # Step 3: Convert decimal odds to implied probability
    closing_odds = closing_quote["decimal_odds"]
    if closing_odds <= 0:
        return None
    implied_prob = 1.0 / closing_odds
    return min(max(implied_prob, 0.01), 0.99)  # clamp to reasonable range


def _find_game_id(
    sport: str, placed_date: str, home_team: str, away_team: str
) -> Optional[str]:
    """Find game_id from unified_games matching a bet's teams and date.

    Args:
        sport: Sport code (case-insensitive).
        placed_date: Game date string.
        home_team: Home team name/abbreviation.
        away_team: Away team name/abbreviation.

    Returns:
        game_id string or None if no match.
    """
    query = """
        SELECT game_id FROM unified_games
        WHERE LOWER(sport) = LOWER(:sport)
          AND game_date = :placed_date
          AND (home_team_name = :home_team OR home_team_id = :home_team)
          AND (away_team_name = :away_team OR away_team_id = :away_team)
        LIMIT 1
    """
    try:
        result = default_db.execute(
            query,
            {
                "sport": sport,
                "placed_date": placed_date,
                "home_team": home_team,
                "away_team": away_team,
            },
        )
        row = result.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _find_closing_quote(
    game_id: str,
    outcome_name: str,
    market_close_time_utc: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Find the last pre-close odds price for a game outcome.

    Searches game_odds for the latest snapshot of the specified outcome
    before market close time. Uses bookmaker priority ordering.
    NULL last_update timestamps are treated as pre-close (many SBR rows lack them).

    Args:
        game_id: The unified_games.game_id to look up.
        outcome_name: 'home' or 'away'.
        market_close_time_utc: Cutoff time; only snapshots before this are used.

    Returns:
        Governed close quote details, or None if no snapshot found.
    """
    try:
        query = """
            SELECT odds_id, bookmaker, price, last_update, loaded_at, external_id, is_pregame
            FROM game_odds
            WHERE game_id = :game_id
              AND outcome_name = :outcome_name
        """
        result = default_db.execute(
            query, {"game_id": game_id, "outcome_name": outcome_name}
        )
        rows = result.fetchall()
        quotes = []
        for row in rows:
            odds_id, bookmaker, price, last_update, loaded_at, external_id, _ = row
            if price is None:
                continue
            quotes.append(
                GovernedPriceQuote(
                    role=PriceRole.CLOSE,
                    decimal_price=float(price),
                    bookmaker=str(bookmaker),
                    market_ticker=external_id,
                    selection_key=outcome_name,
                    observed_at=last_update,
                    loaded_at=loaded_at,
                    payload_ref=odds_id or external_id,
                )
            )
        selected = select_close_quote(
            quotes,
            market_close_time=market_close_time_utc,
            source_priority=ACCEPTABLE_BOOKMAKERS,
            max_age=timedelta(hours=STALE_CLOSING_PRICE_HOURS),
        )
        if selected is not None:
            return {
                "decimal_odds": float(selected.decimal_price),
                "bookmaker": selected.bookmaker,
                "observed_at": selected.observed_at,
                "loaded_at": selected.loaded_at,
                "payload_ref": selected.payload_ref,
                "freshness_result": selected.freshness_result,
                "selected_close_rule": selected.selection_rule,
                "selected_close_provenance": selected.selection_provenance,
            }
        return None
    except Exception:
        return None


def _bookmaker_priority_sql() -> str:
    """Generate SQL CASE expression for bookmaker priority ordering."""
    cases = []
    for i, bookmaker in enumerate(ACCEPTABLE_BOOKMAKERS):
        cases.append(f"WHEN '{bookmaker}' THEN {i}")
    cases.append(f"ELSE {len(ACCEPTABLE_BOOKMAKERS)}")
    return " ".join(cases)


def _is_stale_snapshot(
    last_update: Optional[datetime],
    market_close_time_utc: Optional[datetime],
) -> bool:
    """Check if an odds snapshot is stale (>4hr before market close).

    Args:
        last_update: Timestamp of the odds snapshot.
        market_close_time_utc: When the market closed.

    Returns:
        True if stale, False otherwise. Returns False if timestamps are None.
    """
    if last_update is None or market_close_time_utc is None:
        return False
    gap = market_close_time_utc - last_update
    return gap > timedelta(hours=STALE_CLOSING_PRICE_HOURS)


def backfill_real_clv() -> Dict[str, int]:
    """Backfill historical placed_bets with real closing prices from game_odds.

    Finds all settled bets with binary CLV (closing_line_prob IN (0.0, 1.0))
    and attempts to replace them with real market closing prices.

    Returns:
        Dict with keys: 'updated', 'null_count', 'stale_count', 'total_processed'.
    """
    counts = {"updated": 0, "null_count": 0, "stale_count": 0, "total_processed": 0}

    # Find bets with binary CLV (the bug)
    query = """
        SELECT bet_id, sport, home_team, away_team, bet_on,
               placed_date, market_close_time_utc, bet_line_prob
        FROM placed_bets
        WHERE status IN ('won', 'lost')
          AND (closing_line_prob = 0.0 OR closing_line_prob = 1.0)
    """
    try:
        result = default_db.execute(query)
        rows = result.fetchall()
    except Exception as e:
        print(f"❌ Error querying bets for CLV backfill: {e}")
        return counts

    print(f"📊 Found {len(rows)} bets with binary CLV to backfill")

    for row in rows:
        counts["total_processed"] += 1
        bet_id, sport, home_team, away_team, bet_on = (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
        )
        placed_date, market_close_time_utc, bet_line_prob = row[5], row[6], row[7]

        # Parse market_close_time if it's a string
        if isinstance(market_close_time_utc, str):
            try:
                market_close_time_utc = datetime.fromisoformat(
                    market_close_time_utc.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                market_close_time_utc = None

        # Compute real closing price
        closing_quote = build_clv_evidence_snapshot(
            bet_id=bet_id,
            sport=sport,
            home_team=home_team or "",
            away_team=away_team or "",
            bet_on=bet_on or "home",
            placed_date=str(placed_date) if placed_date else "",
            market_close_time_utc=market_close_time_utc,
        )
        closing_prob = closing_quote["closing_probability"] if closing_quote else None

        if closing_prob is None:
            counts["null_count"] += 1
            continue

        if closing_quote["close_freshness_result"] == "stale":
            counts["stale_count"] += 1

        # Update the bet with real closing price
        clv = (bet_line_prob - closing_prob) if bet_line_prob is not None else None
        _update_bet_clv(bet_id, closing_prob, clv, closing_quote)
        counts["updated"] += 1

    print(
        f"✅ CLV backfill complete: {counts['updated']} updated, "
        f"{counts['null_count']} no closing price, {counts['stale_count']} stale"
    )
    return counts


def _check_and_count_stale(
    game_id: str,
    bet_on: str,
    home_team: str,
    away_team: str,
    market_close_time_utc: datetime,
    counts: Dict[str, int],
) -> None:
    """Check if the closing odds snapshot is stale and increment counter."""
    outcome_name = _resolve_outcome_name(bet_on, home_team, away_team)
    try:
        result = default_db.execute(
            """
            SELECT last_update FROM game_odds
            WHERE game_id = :game_id AND outcome_name = :outcome_name
            ORDER BY last_update DESC NULLS LAST
            LIMIT 1
            """,
            {"game_id": game_id, "outcome_name": outcome_name},
        )
        row = result.fetchone()
        if row and row[0]:
            last_update = row[0]
            if isinstance(last_update, str):
                last_update = datetime.fromisoformat(last_update)
            if _is_stale_snapshot(last_update, market_close_time_utc):
                counts["stale_count"] += 1
    except Exception:
        pass


def build_clv_evidence_snapshot(
    bet_id: str,
    sport: str,
    home_team: str,
    away_team: str,
    bet_on: str,
    placed_date: str,
    market_close_time_utc: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    outcome_name = _resolve_outcome_name(bet_on, home_team, away_team)
    game_id = _find_game_id(sport, placed_date, home_team, away_team)
    if not game_id:
        return None

    closing_quote = _find_closing_quote(game_id, outcome_name, market_close_time_utc)
    if closing_quote is None:
        snapshot = build_clv_governance_snapshot(
            entry_quote=GovernedPriceQuote(
                role=PriceRole.EXECUTABLE,
                decimal_price=1.0,
                bookmaker="placed_bets",
                selection_key=outcome_name,
            ),
            close_quote=None,
            clv_source_type="missing_close",
        )
        return {
            "bet_id": bet_id,
            "closing_probability": None,
            "clv_source_type": "missing_close",
            "close_freshness_result": snapshot.close_freshness_result,
            "close_quote_source": "missing_close",
            "close_quote_at": None,
            "close_quote_loaded_at": None,
            "close_quote_payload_ref": None,
            "close_price_role": "descriptive_placeholder",
            "selected_close_rule": "missing_close",
            "selected_close_provenance": None,
            "close_fallback_status": "missing_close",
            "clv_evidence_tier": snapshot.evidence_tier.value,
            "clv_contaminated_flag": snapshot.contaminated,
            "contamination_reason": snapshot.contamination_reason,
        }

    closing_probability = min(max(1.0 / closing_quote["decimal_odds"], 0.01), 0.99)
    snapshot = build_clv_governance_snapshot(
        entry_quote=GovernedPriceQuote(
            role=PriceRole.EXECUTABLE,
            decimal_price=1.0,
            bookmaker="placed_bets",
            selection_key=outcome_name,
        ),
        close_quote=GovernedPriceQuote(
            role=PriceRole.CLOSE,
            decimal_price=closing_quote["decimal_odds"],
            bookmaker=closing_quote["bookmaker"],
            selection_key=outcome_name,
            observed_at=closing_quote["observed_at"],
            loaded_at=closing_quote["loaded_at"],
            payload_ref=closing_quote["payload_ref"],
            freshness_result=closing_quote["freshness_result"],
            selection_rule=closing_quote["selected_close_rule"],
            selection_provenance=closing_quote["selected_close_provenance"],
        ),
        clv_source_type="market_close",
    )
    return {
        "bet_id": bet_id,
        "closing_probability": closing_probability,
        "clv_source_type": "market_close",
        "close_quote_source": closing_quote["bookmaker"],
        "close_quote_at": closing_quote["observed_at"],
        "close_quote_loaded_at": closing_quote["loaded_at"],
        "close_quote_payload_ref": closing_quote["payload_ref"],
        "close_price_role": "close",
        "close_freshness_result": snapshot.close_freshness_result,
        "selected_close_rule": closing_quote["selected_close_rule"],
        "selected_close_provenance": closing_quote["selected_close_provenance"],
        "close_fallback_status": closing_quote["selected_close_rule"],
        "closing_quote_source": closing_quote["bookmaker"],
        "closing_quote_at": closing_quote["observed_at"],
        "clv_evidence_tier": snapshot.evidence_tier.value,
        "clv_contaminated_flag": snapshot.contaminated,
        "contamination_reason": snapshot.contamination_reason,
    }


@lru_cache(maxsize=1)
def _placed_bets_columns() -> Tuple[str, ...]:
    """Return the currently available placed_bets columns for compatibility-safe updates."""
    try:
        return tuple(
            column["name"] for column in inspect(default_db.engine).get_columns("placed_bets")
        )
    except Exception:
        return ()


def _update_bet_clv(
    bet_id: str,
    closing_prob: Optional[float],
    clv: Optional[float],
    snapshot: Optional[Dict[str, Any]] = None,
) -> None:
    """Update a single bet's closing_line_prob and CLV."""
    available_columns = set(_placed_bets_columns())
    assignments = [
        "closing_line_prob = :closing_prob",
        "clv = :clv",
        "updated_at = CURRENT_TIMESTAMP",
    ]
    params: Dict[str, Any] = {
        "closing_prob": closing_prob,
        "clv": clv,
        "bet_id": bet_id,
    }
    optional_snapshot_fields = {
        "close_quote_source": "close_quote_source",
        "close_quote_at": "close_quote_at",
        "close_quote_loaded_at": "close_quote_loaded_at",
        "close_quote_payload_ref": "close_quote_payload_ref",
        "close_price_role": "close_price_role",
        "close_freshness_result": "close_freshness_result",
        "selected_close_rule": "selected_close_rule",
        "selected_close_provenance": "selected_close_provenance",
        "close_fallback_status": "close_fallback_status",
        "clv_source_type": "clv_source_type",
    }
    snapshot = snapshot or {}

    for column_name, param_name in optional_snapshot_fields.items():
        if column_name not in available_columns:
            continue
        assignments.append(
            f"{column_name} = COALESCE(:{param_name}, {column_name})"
        )
        params[param_name] = snapshot.get(param_name)

    try:
        default_db.execute(
            f"""
            UPDATE placed_bets
            SET {", ".join(assignments)}
            WHERE bet_id = :bet_id
            """,
            params,
        )
    except Exception as e:
        print(f"  ⚠️ Failed to update CLV for {bet_id}: {e}")


def update_real_closing_lines() -> int:
    """Update CLV for recently settled bets that still have binary closing prices.

    Designed to be called from the hourly bet_sync DAG. Only processes bets
    that are settled and still have binary CLV values (0.0 or 1.0).

    Returns:
        Number of bets updated.
    """
    result = backfill_real_clv()
    return result.get("updated", 0)


class CLVTracker:
    """Track and analyze closing line values for bets."""

    def __init__(self, odds_api_key: Optional[str] = None):
        self.odds_api_key = odds_api_key

    def record_bet_line(self, bet_id: str, market_prob: float):
        """Record the line we bet at."""
        query = """
            UPDATE placed_bets
            SET bet_line_prob = :market_prob, updated_at = CURRENT_TIMESTAMP
            WHERE bet_id = :bet_id
        """
        default_db.execute(query, {"market_prob": market_prob, "bet_id": bet_id})

    def update_closing_line(self, bet_id: str, closing_prob: float):
        """Update the closing line for a bet."""
        # Get the bet line probability
        query = "SELECT bet_line_prob FROM placed_bets WHERE bet_id = :bet_id"
        result = default_db.execute(query, {"bet_id": bet_id})
        bet_line = result.fetchone()

        if bet_line and bet_line[0]:
            clv = bet_line[0] - closing_prob

            # Update with closing line and CLV
            update_query = """
                UPDATE placed_bets
                SET closing_line_prob = :closing_prob, clv = :clv, updated_at = CURRENT_TIMESTAMP
                WHERE bet_id = :bet_id
            """
            default_db.execute(
                update_query,
                {"closing_prob": closing_prob, "clv": clv, "bet_id": bet_id},
            )

            print(
                f"  CLV for {bet_id}: {clv:+.2%} ({bet_line[0]:.1%} bet → {closing_prob:.1%} close)"
            )

    def fetch_closing_lines_from_kalshi(self, days_back: int = 7):
        """Fetch closing lines from game_odds (Kalshi bookmaker priority).

        Uses real closing prices from game_odds table instead of binary outcomes.
        Delegates to backfill_real_clv() which handles all bookmakers with priority.
        """
        result = backfill_real_clv()
        print(
            f"✅ Closing lines updated: {result['updated']} bets, "
            f"{result['null_count']} missing"
        )

    def fetch_closing_lines_from_sbr(self, days_back: int = 7):
        """Fetch closing lines from game_odds (SBR and all bookmakers).

        Uses real closing prices from game_odds table.
        Delegates to backfill_real_clv() which handles all bookmakers with priority.
        """
        result = backfill_real_clv()
        print(
            f"✅ Closing lines updated: {result['updated']} bets, "
            f"{result['null_count']} missing"
        )

    def analyze_clv(self, days_back: int = 30) -> Dict:
        """
        Analyze CLV performance over recent bets.

        Returns dict with:
        - avg_clv: Average CLV across all bets
        - positive_clv_pct: Percentage of bets with positive CLV
        - clv_by_sport: CLV broken down by sport
        """
        cutoff_date = self._calculate_cutoff_date(days_back)

        overall_stats = self._fetch_overall_clv_stats(cutoff_date)
        if not overall_stats or overall_stats[0] == 0:
            return {"num_bets": 0, "message": "No CLV data available"}

        sport_stats = self._fetch_clv_stats_by_sport(cutoff_date)

        return self._build_clv_analysis_result(overall_stats, sport_stats)

    def _calculate_cutoff_date(self, days_back: int) -> str:
        """Calculate cutoff date for CLV analysis."""
        from datetime import datetime, timedelta

        return (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    def _fetch_overall_clv_stats(self, cutoff_date: str) -> Optional[Tuple]:
        """Fetch overall CLV statistics from database."""
        query_result = self._execute_clv_query(cutoff_date, group_by_sport=False)
        return query_result.fetchone() if query_result else None

    def _fetch_clv_stats_by_sport(self, cutoff_date: str) -> List[Tuple]:
        """Fetch CLV statistics grouped by sport from database."""
        query_result = self._execute_clv_query(cutoff_date, group_by_sport=True)
        return query_result.fetchall() if query_result else []

    def _execute_clv_query(self, cutoff_date: str, group_by_sport: bool = False):
        """
        Execute CLV statistics query with optional grouping by sport.

        Args:
            cutoff_date: Date cutoff for analysis
            group_by_sport: Whether to group results by sport

        Returns:
            Database cursor with query results
        """
        # Build SELECT clause
        if group_by_sport:
            select_clause = """
                sport,
                COUNT(*) as num_bets,
                AVG(clv) as avg_clv,
                SUM(CASE WHEN clv > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as positive_clv_pct
            """
        else:
            select_clause = """
                COUNT(*) as num_bets,
                AVG(clv) as avg_clv,
                SUM(CASE WHEN clv > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as positive_clv_pct
            """

        # Build GROUP BY and ORDER BY clauses
        group_by_clause = "GROUP BY sport" if group_by_sport else ""
        order_by_clause = "ORDER BY avg_clv DESC" if group_by_sport else ""

        # Construct full query
        query = f"""
            SELECT
                {select_clause}
            FROM placed_bets
            WHERE placed_date >= :cutoff_date
            AND clv IS NOT NULL
            {group_by_clause}
            {order_by_clause}
        """

        return default_db.execute(query, {"cutoff_date": cutoff_date})

    def _build_clv_analysis_result(
        self, overall_stats: Tuple, sport_stats: List[Tuple]
    ) -> Dict:
        """Build CLV analysis result dictionary from database query results."""
        return {
            "num_bets": overall_stats[0],
            "avg_clv": overall_stats[1],
            "positive_clv_pct": overall_stats[2],
            "by_sport": [
                {
                    "sport": row[0],
                    "num_bets": row[1],
                    "avg_clv": row[2],
                    "positive_clv_pct": row[3],
                }
                for row in sport_stats
            ],
        }

    def print_clv_report(self, days_back: int = 30):
        """Print a formatted CLV report."""
        analysis = self.analyze_clv(days_back)

        if analysis.get("num_bets", 0) == 0:
            print("❌ No CLV data available")
            return

        print(f"\n{'=' * 60}")
        print(f"CLV ANALYSIS - Last {days_back} Days")
        print(f"{'=' * 60}\n")

        print("Overall Performance:")
        print(f"  Total Bets: {analysis['num_bets']}")
        print(f"  Average CLV: {analysis['avg_clv']:+.2%}")
        print(f"  Positive CLV %: {analysis['positive_clv_pct']:.1f}%")

        if analysis["avg_clv"] > 0:
            print("  ✅ POSITIVE CLV - Model is beating closing lines!")
        else:
            print("  ❌ NEGATIVE CLV - Model is NOT beating closing lines")

        print("\nBy Sport:")
        for sport_data in analysis["by_sport"]:
            indicator = "✅" if sport_data["avg_clv"] > 0 else "❌"
            print(
                f"  {indicator} {sport_data['sport'].upper():8} | "
                f"Bets: {sport_data['num_bets']:3} | "
                f"CLV: {sport_data['avg_clv']:+.2%} | "
                f"Positive: {sport_data['positive_clv_pct']:.0f}%"
            )

        print(f"\n{'=' * 60}\n")


def main():
    """Run CLV analysis."""
    tracker = CLVTracker()

    # Fetch closing lines for recent bets (using SBR/OddsPortal instead of Odds API)
    # tracker.fetch_closing_lines_from_sbr(days_back=7)

    # Print CLV report
    tracker.print_clv_report(days_back=30)


if __name__ == "__main__":
    main()
