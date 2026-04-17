from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins"))

from naming_resolver import NamingContext, NamingResolver


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@lru_cache(maxsize=None)
def _elo_teams(sport: str) -> set[str]:
    """Load the current Elo-facing team names for a sport."""
    csv_path = DATA_DIR / f"{sport}_current_elo_ratings.csv"
    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        return {row["team"] for row in csv.DictReader(csv_file)}


@lru_cache(maxsize=None)
def _latest_bet_file(sport: str) -> Path:
    """Return the latest bet file for a sport."""
    bet_files = sorted((DATA_DIR / sport).glob("bets_20??-??-??.json"))
    assert bet_files, f"No bet files found for {sport}"
    return bet_files[-1]


@lru_cache(maxsize=None)
def _bet_file_names(sport: str) -> tuple[str, ...]:
    """Collect unique team names from the latest bet file for a sport."""
    with _latest_bet_file(sport).open(encoding="utf-8") as bet_file:
        payload = json.load(bet_file)

    names: set[str] = set()
    for entry in payload:
        for key in ("home_team", "away_team", "bet_on"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                names.add(value)

    return tuple(sorted(names))


def _resolve_kalshi_name(sport: str, raw_name: str) -> str:
    """Resolve a raw Kalshi team name to the canonical resolver name."""
    return NamingResolver.resolve(
        NamingContext(sport=sport, source="kalshi", name=raw_name)
    )


def _resolve_to_elo_name(sport: str, raw_name: str) -> str:
    """Resolve a raw Kalshi team name all the way to the Elo-facing name."""
    canonical_name = _resolve_kalshi_name(sport, raw_name)
    return NamingResolver.resolve(
        NamingContext(sport=sport, source="elo", name=canonical_name)
    )


@pytest.mark.parametrize(
    ("sport", "raw_name", "expected_name"),
    [
        ("epl", "WHU", "West Ham United"),
        ("epl", "WOL", "Wolverhampton Wanderers"),
        ("epl", "LFC", "Liverpool"),
        ("epl", "FUL", "Fulham"),
        ("nba", "ATL", "Atlanta Hawks"),
        ("nba", "MIA", "Miami Heat"),
        ("nba", "CLE", "Cleveland Cavaliers"),
        ("nba", "Atlanta Braves", "Atlanta Hawks"),
        ("nba", "Miami Marlins", "Miami Heat"),
        ("nba", "Cleveland Guardians", "Cleveland Cavaliers"),
        ("mlb", "LAD", "Los Angeles Dodgers"),
        ("mlb", "TEX", "Texas Rangers"),
        ("nhl", "ANA", "ANA"),
        ("nhl", "BOS", "BOS"),
    ],
)
def test_kalshi_names_resolve_to_expected_canonical_names(
    sport: str, raw_name: str, expected_name: str
) -> None:
    assert _resolve_kalshi_name(sport, raw_name) == expected_name


@pytest.mark.parametrize(
    ("sport", "required_names"),
    [
        ("epl", {"West Ham", "Wolves", "Liverpool", "Fulham"}),
        ("nba", {"ATL", "MIA", "CLE"}),
        (
            "mlb",
            {
                "Los Angeles Dodgers",
                "Texas Rangers",
                "Houston Astros",
                "Seattle Mariners",
            },
        ),
        ("nhl", {"ANA", "TOR", "NYI"}),
    ],
)
def test_latest_bet_file_names_resolve_to_current_elo_names(
    sport: str, required_names: set[str]
) -> None:
    resolved_names = {
        _resolve_to_elo_name(sport, name) for name in _bet_file_names(sport)
    }

    assert required_names <= resolved_names
    assert resolved_names <= _elo_teams(sport)


def test_cross_sport_fallback_only_applies_to_related_sports() -> None:
    assert _resolve_kalshi_name("wncaab", "hou") == "Houston"
    assert _resolve_kalshi_name("nba", "ATL") == "Atlanta Hawks"
