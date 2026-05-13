#!/usr/bin/env python3
"""Backfill missing ``elo_prob`` values in ``placed_bets``.

Strategy
--------
For each sport, we load the latest Elo rating snapshot from
``data/elo_backups/`` into the corresponding Elo system, then compute
``predict(home_team, away_team)`` for every bet whose ``elo_prob IS NULL``.
Team names are parsed from the ``market_title`` column and mapped to the
naming convention the Elo system uses (standard 3-letter codes for NBA/NHL,
full underscore-separated names for NCAAB/WNCAAB).

Idempotent
----------
Only updates rows where ``elo_prob IS NULL``.  Safe to re-run.

Usage
-----
    python scripts/backfill_elo_prob.py
"""

from __future__ import annotations

import csv
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Environment – must be set *before* importing DBManager
# ---------------------------------------------------------------------------
os.environ.setdefault("POSTGRES_HOST", "localhost")

# ---------------------------------------------------------------------------
# Ensure plugins/ is on sys.path — before any local imports
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plugins"))
sys.path.insert(0, str(ROOT / "plugins" / "elo"))

from plugins.db_manager import DBManager, default_db  # noqa: E402
from plugins.elo.factory import create_elo_instance  # noqa: E402
from plugins.elo.base_elo_rating import BaseEloRating  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_elo_prob")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BACKUP_DIR = ROOT / "data" / "elo_backups"

# Mapping from DB sport value → Elo factory key
SPORT_TO_ELO_KEY = {
    "NBA": "nba",
    "NHL": "nhl",
    "NCAAB": "ncaab",
    "WNCAAB": "wncaab",
    "TENNIS": "tennis",
}

# Latest backup suffix (most recent backup timestamp)
LATEST_BACKUP_SUFFIX = "20260205_162426"

# ---------------------------------------------------------------------------
# Team name mappings: market_title name → Elo system name
# ---------------------------------------------------------------------------

# NBA: market_title uses city names ("Boston") → Elo uses 3-letter code ("BOS")
NBA_NAME_TO_CODE: dict[str, str] = {
    "Atlanta": "ATL",
    "Boston": "BOS",
    "Brooklyn": "BKN",
    "Charlotte": "CHA",
    "Chicago": "CHI",
    "Cleveland": "CLE",
    "Dallas": "DAL",
    "Denver": "DEN",
    "Detroit": "DET",
    "Golden State": "GSW",
    "Houston": "HOU",
    "Indiana": "IND",
    "Los Angeles C": "LAC",
    "Los Angeles L": "LAL",
    "Memphis": "MEM",
    "Miami": "MIA",
    "Milwaukee": "MIL",
    "Minnesota": "MIN",
    "New Orleans": "NOP",
    "New York": "NYK",
    "Oklahoma City": "OKC",
    "Orlando": "ORL",
    "Philadelphia": "PHI",
    "Phoenix": "PHX",
    "Portland": "POR",
    "Sacramento": "SAC",
    "San Antonio": "SAS",
    "Toronto": "TOR",
    "Utah": "UTA",
    "Washington": "WAS",
}

# NHL: market_title city names → 3-letter codes
NHL_NAME_TO_CODE: dict[str, str] = {
    "Anaheim": "ANA",
    "Arizona": "ARI",
    "Boston": "BOS",
    "Buffalo": "BUF",
    "Calgary": "CGY",
    "Carolina": "CAR",
    "Chicago": "CHI",
    "Colorado": "COL",
    "Columbus": "CBJ",
    "Dallas": "DAL",
    "Detroit": "DET",
    "Edmonton": "EDM",
    "Florida": "FLA",
    "Los Angeles": "LAK",
    "Minnesota": "MIN",
    "Montreal": "MTL",
    "Nashville": "NSH",
    "New Jersey": "NJD",
    "New York I": "NYI",
    "New York R": "NYR",
    "Ottawa": "OTT",
    "Philadelphia": "PHI",
    "Pittsburgh": "PIT",
    "San Jose": "SJS",
    "Seattle": "SEA",
    "St. Louis": "STL",
    "Tampa Bay": "TBL",
    "Toronto": "TOR",
    "Utah": "UTA",
    "Vancouver": "VAN",
    "Vegas": "VGK",
    "Washington": "WSH",
    "Winnipeg": "WPG",
}

# NCAAB: market_title name → Elo backup name (underscore-separated)
# Most NCAAB names are the same, just need to normalize "St.", spaces → underscores
NCAAB_NAME_MAP: dict[str, str] = {
    "Alabama": "Alabama",
    "Arkansas": "Arkansas",
    "Davidson": "Davidson",
    "Dayton": "Dayton",
    "Duquesne": "Duquesne",
    "Florida International": "Florida_International",  # FIU
    "High Point": "High_Point",
    "Indiana": "Indiana",
    "LSU": "LSU",
    "Liberty": "Liberty",
    "Louisiana-Monroe": "Louisiana_Monroe",
    "Michigan St.": "Michigan_St",
    "North Texas": "North_Texas",
    "Ohio St.": "Ohio_St",
    "Oregon": "Oregon",
    "Purdue": "Purdue",
    "South Alabama": "South_Alabama",
    "TCU": "TCU",
    "Texas": "Texas",
    "UAB": "UAB",
    "UCF": "UCF",
    "UNC Asheville": "UNC_Asheville",
    "USC": "USC",
    "VMI": "VMI",
    "West Virginia": "West_Virginia",
    "Western Carolina": "Western_Carolina",
    "Wisconsin": "Wisconsin",
    "Wofford": "Wofford",
}

# WNCAAB
WNCAAB_NAME_MAP: dict[str, str] = {
    "Auburn": "Auburn",
    "Baylor": "Baylor",
    "Georgia": "Georgia",
    "Iowa St.": "Iowa_St",
    "Kansas St.": "Kansas_St",
    "Oregon": "Oregon",
    "Purdue": "Purdue",
    "TCU": "TCU",
    "UCF": "UCF",
    "West Virginia": "West_Virginia",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MARKET_TITLE_PATTERN = re.compile(
    r"^(?:(?:Game \d+: )?)?(.+?) at (.+?) Winner\?$"
)

TENNIS_TITLE_PATTERN = re.compile(
    r"^Will (.+?) win the (.+?) vs (.+?) : .+? match\?$"
)


def _get_sport_name_map(sport: str) -> dict[str, str]:
    """Return the team name → Elo code mapping for *sport*."""
    if sport == "NBA":
        return NBA_NAME_TO_CODE
    if sport == "NHL":
        return NHL_NAME_TO_CODE
    if sport == "NCAAB":
        return NCAAB_NAME_MAP
    if sport == "WNCAAB":
        return WNCAAB_NAME_MAP
    return {}


def parse_teams_from_title(
    market_title: str | None, sport: str
) -> tuple[str | None, str | None]:
    """Extract away/home team names from a Kalshi ``market_title``.

    Returns ``(away_team, home_team)`` as they should appear in the Elo
    system, or ``(None, None)`` if parsing fails.
    """
    if not market_title or not isinstance(market_title, str):
        return None, None

    m = MARKET_TITLE_PATTERN.match(market_title)
    if m:
        raw_away, raw_home = m.group(1), m.group(2)
        name_map = _get_sport_name_map(sport)
        if not name_map:
            # For sports without a specific map, return raw names
            return raw_away, raw_home
        away = name_map.get(raw_away)
        home = name_map.get(raw_home)
        return away, home

    # Tennis format
    if sport == "TENNIS":
        m2 = TENNIS_TITLE_PATTERN.match(market_title)
        if m2:
            p1 = m2.group(2)
            p2 = m2.group(3)
            # Determine which player is the "home" team
            # The bet_on player's surname is in the ticker
            # For Elo predict, we need player_a (home) and player_b (away)
            # We'll use p1 as "home" and p2 as "away"
            # The elo_prob is probability of home winning (p1)
            return p1, p2

    return None, None


def _normalize_tennis_name(name: str) -> str:
    """Normalize a tennis player name to ``Lastname I.`` format."""
    name = name.strip()
    if not name:
        return ""
    # Already formatted
    if name.endswith("."):
        return name
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[-1]} {parts[0][0]}."
    return name


def load_ratings_from_backup(
    elo: BaseEloRating, sport: str
) -> int:
    """Load Elo ratings from the latest backup CSV into *elo* instance.

    Returns the number of teams loaded.
    """
    backup_key = SPORT_TO_ELO_KEY.get(sport, sport.lower())
    backup_path = BACKUP_DIR / f"{backup_key}_current_elo_ratings_{LATEST_BACKUP_SUFFIX}.csv"

    if not backup_path.exists():
        logger.warning("No backup found: %s", backup_path)
        return 0

    count = 0
    with open(backup_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            team = row["team"].strip()
            rating = float(row["rating"])
            elo.set_rating(team, rating)
            count += 1

    logger.info("Loaded %d ratings for %s from %s", count, sport, backup_path.name)
    return count


def _load_tennis_ratings(tennis) -> int:
    """Load tennis ratings from backup CSV — special handling for ATP/WTA."""
    # Tennis backup has format: team,rating where team is "ATP:PlayerName" or "WTA:PlayerName"
    backup_path = BACKUP_DIR / f"tennis_current_elo_ratings_{LATEST_BACKUP_SUFFIX}.csv"
    if not backup_path.exists():
        logger.warning("No tennis backup found: %s", backup_path)
        return 0

    count = 0
    with open(backup_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            team = row["team"].strip()
            rating = float(row["rating"])
            if team.startswith("ATP:"):
                player = team[4:]
                tennis.atp_ratings[player] = rating
            elif team.startswith("WTA:"):
                player = team[4:]
                tennis.wta_ratings[player] = rating
            else:
                tennis.set_rating(team, rating)
            count += 1

    logger.info("Loaded %d tennis ratings from backup", count)
    return count


def backfill_sport(
    db: DBManager,
    sport: str,
    elo: BaseEloRating,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Backfill ``elo_prob`` for all bets in *sport* where it is NULL.

    Returns a summary dict.
    """
    # Fetch bets missing elo_prob for this sport
    rows = db.fetch_df(
        """
        SELECT bet_id, sport, market_title, placed_date
        FROM placed_bets
        WHERE sport = :sport AND elo_prob IS NULL
        ORDER BY placed_date
        """,
        {"sport": sport},
    )

    if rows.empty:
        return {"sport": sport, "found": 0, "updated": 0, "skipped": 0, "errors": 0}

    found = len(rows)
    updated = 0
    skipped = 0
    errors = 0

    for _, row in rows.iterrows():
        bet_id = row["bet_id"]
        market_title = row.get("market_title") or ""

        if not market_title:
            skipped += 1
            continue

        # Parse teams
        if sport == "TENNIS":
            away, home = parse_teams_from_title(market_title, sport)
            if away is None or home is None:
                skipped += 1
                continue
            # For tennis, determine tour from ticker
            ticker = db.fetch_scalar(
                "SELECT ticker FROM placed_bets WHERE bet_id = :bid",
                {"bid": bet_id},
            )
            tour = "ATP"
            if ticker and "WTA" in ticker.upper():
                tour = "WTA"

            # Normalize player names
            home_norm = _normalize_tennis_name(home)
            away_norm = _normalize_tennis_name(away)

            # Check if players have ratings
            elo_tennis = elo  # type: ignore[attr-defined]
            if not elo_tennis.has_real_rating(home_norm, tour) or not elo_tennis.has_real_rating(away_norm, tour):
                logger.debug(
                    "Skipping %s: no rating for %s or %s (%s)",
                    bet_id, home_norm, away_norm, tour,
                )
                skipped += 1
                continue

            try:
                prob = elo_tennis.predict(
                    home_norm, away_norm, tour=tour
                )
            except Exception:
                logger.exception("Error predicting %s", bet_id)
                errors += 1
                continue
        else:
            away, home = parse_teams_from_title(market_title, sport)
            if away is None or home is None:
                skipped += 1
                continue

            # Check if both teams have ratings
            if not elo.has_real_rating(home) or not elo.has_real_rating(away):
                logger.debug(
                    "Skipping %s: no rating for %s or %s", bet_id, home, away
                )
                skipped += 1
                continue

            try:
                prob = elo.predict(home, away)
            except Exception:
                logger.exception("Error predicting %s", bet_id)
                errors += 1
                continue

        # Update DB
        if dry_run:
            logger.info(
                "[DRY RUN] Would update %s: sport=%s, home=%s, away=%s, prob=%.4f",
                bet_id, sport, home, away, prob,
            )
            updated += 1
        else:
            try:
                db.execute(
                    "UPDATE placed_bets SET elo_prob = :prob WHERE bet_id = :bid AND elo_prob IS NULL",
                    {"prob": prob, "bid": bet_id},
                )
                updated += 1
            except Exception:
                logger.exception("Error updating %s", bet_id)
                errors += 1

    return {
        "sport": sport,
        "found": found,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


def print_coverage_summary(db: DBManager) -> None:
    """Print current elo_prob coverage."""
    df = db.fetch_df("""
        SELECT
            COALESCE(sport, '(empty)') as sport,
            COUNT(*) as total,
            SUM(CASE WHEN elo_prob IS NOT NULL THEN 1 ELSE 0 END) as with_elo,
            SUM(CASE WHEN status IN ('won','lost') AND elo_prob IS NOT NULL THEN 1 ELSE 0 END) as settled_with_elo
        FROM placed_bets
        GROUP BY sport
        ORDER BY sport
    """)
    print()
    print(f"  {'Sport':<12s} {'Total':>6s} {'With elo_prob':>14s} {'Settled+elo':>14s}")
    print(f"  {'─' * 12} {'─' * 6} {'─' * 14} {'─' * 14}")
    for _, row in df.iterrows():
        print(
            f"  {row['sport']:<12s} {int(row['total']):>6d} "
            f"{int(row['with_elo']):>14d} {int(row['settled_with_elo']):>14d}"
        )
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point."""
    print("=" * 60)
    print("  BACKFILL ELO PROBABILITIES")
    print("=" * 60)

    # ---- Connection --------------------------------------------------------
    try:
        db: DBManager = default_db
        db.fetch_scalar("SELECT 1")
    except Exception as exc:
        logger.error("Database connection failed: %s", exc)
        return 1

    print("  Connected to PostgreSQL at localhost:5432\n")

    # ---- Pre-backfill coverage ---------------------------------------------
    print("  ── Current elo_prob coverage ──")
    print_coverage_summary(db)

    # ---- Sports to process --------------------------------------------------
    sports_to_process = ["NBA", "NHL", "NCAAB", "WNCAAB", "TENNIS"]
    results: list[dict[str, Any]] = []

    # ---- Process each sport -------------------------------------------------
    for sport in sports_to_process:
        elo_key = SPORT_TO_ELO_KEY[sport]

        # Create Elo instance
        elo = create_elo_instance(elo_key)

        # Load ratings from backup
        if sport == "TENNIS":
            _load_tennis_ratings(elo)
        else:
            n_loaded = load_ratings_from_backup(elo, sport)
            if n_loaded == 0:
                logger.warning(
                    "No ratings loaded for %s — skipping", sport
                )
                results.append({
                    "sport": sport,
                    "found": 0,
                    "updated": 0,
                    "skipped": 0,
                    "errors": 0,
                    "note": "no backup ratings available",
                })
                continue

        # Backfill
        count_query = db.fetch_scalar(
            "SELECT COUNT(*) FROM placed_bets WHERE sport = :s AND elo_prob IS NULL",
            {"s": sport},
        )
        if count_query == 0:
            logger.info("No missing elo_prob for %s — skipping", sport)
            results.append({
                "sport": sport,
                "found": 0,
                "updated": 0,
                "skipped": 0,
                "errors": 0,
            })
            continue

        logger.info("Backfilling %s (%d bets)...", sport, count_query)
        result = backfill_sport(db, sport, elo)
        results.append(result)

        # Log per-sport result
        r = result
        logger.info(
            "%s: found=%d, updated=%d, skipped=%d, errors=%d",
            sport, r["found"], r["updated"], r["skipped"], r["errors"],
        )

    # ---- Summary ------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("  BACKFILL SUMMARY")
    print(f"{'=' * 60}\n")

    total_updated = 0
    for r in results:
        note = r.get("note", "")
        note_str = f" ({note})" if note else ""
        print(
            f"  {r['sport']:<12s}: updated={r['updated']:>3d}, "
            f"skipped={r['skipped']:>3d}, errors={r['errors']:>2d}"
            f"{note_str}"
        )
        total_updated += r["updated"]

    print(f"\n  Total rows updated: {total_updated}")

    # ---- Post-backfill coverage ---------------------------------------------
    print("\n  ── Post-backfill elo_prob coverage ──")
    print_coverage_summary(db)

    return 0 if total_updated > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
