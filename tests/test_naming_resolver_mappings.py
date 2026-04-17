from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from naming_resolver import NamingContext, NamingResolver


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@lru_cache(maxsize=None)
def _elo_teams(sport: str) -> set[str]:
    """Load the current Elo team names for a sport."""
    csv_path = DATA_DIR / f"{sport}_current_elo_ratings.csv"
    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        return {row["team"] for row in csv.DictReader(csv_file)}


def _resolve_to_elo_name(sport: str, raw_name: str) -> str:
    """Resolve a raw sportsbook name all the way to the Elo-facing name."""
    canonical_name = NamingResolver.resolve(
        NamingContext(sport=sport, source="kalshi", name=raw_name)
    )
    return NamingResolver.resolve(
        NamingContext(sport=sport, source="elo", name=canonical_name)
    )


@pytest.mark.parametrize(
    ("raw_name", "expected_name"),
    [
        ("ARS", "Arsenal"),
        ("AVL", "Aston Villa"),
        ("BOU", "Bournemouth"),
        ("BRE", "Brentford"),
        ("BRI", "Brighton"),
        ("Brighton and Hove Albion", "Brighton"),
        ("BUR", "Burnley"),
        ("CFC", "Chelsea"),
        ("CRY", "Crystal Palace"),
        ("EVE", "Everton"),
        ("FUL", "Fulham"),
        ("IPS", "Ipswich"),
        ("LEE", "Leeds"),
        ("Leeds United", "Leeds"),
        ("LEI", "Leicester"),
        ("LFC", "Liverpool"),
        ("LUT", "Luton"),
        ("MCI", "Man City"),
        ("Manchester City", "Man City"),
        ("MUN", "Man United"),
        ("Manchester United", "Man United"),
        ("NEW", "Newcastle"),
        ("Newcastle United", "Newcastle"),
        ("NFO", "Nott'm Forest"),
        ("Nottingham", "Nott'm Forest"),
        ("Nottingham Forest", "Nott'm Forest"),
        ("NOR", "Norwich"),
        ("SHU", "Sheffield United"),
        ("SOU", "Southampton"),
        ("SUN", "Sunderland"),
        ("TOT", "Tottenham"),
        ("Tottenham Hotspur", "Tottenham"),
        ("WAT", "Watford"),
        ("WHU", "West Ham"),
        ("West Ham United", "West Ham"),
        ("WOL", "Wolves"),
        ("Wolverhampton Wanderers", "Wolves"),
    ],
)
def test_epl_names_resolve_to_current_elo_team_names(
    raw_name: str, expected_name: str
) -> None:
    resolved_name = _resolve_to_elo_name("epl", raw_name)

    assert expected_name in _elo_teams("epl")
    assert resolved_name == expected_name


@pytest.mark.parametrize(
    ("raw_name", "expected_name"),
    [
        ("ATL", "ATL"),
        ("Atlanta", "ATL"),
        ("Atlanta Hawks", "ATL"),
        ("Atlanta Braves", "ATL"),
        ("BKN", "BKN"),
        ("Brooklyn Nets", "BKN"),
        ("BOS", "BOS"),
        ("Boston Celtics", "BOS"),
        ("Celtics", "BOS"),
        ("CHA", "CHA"),
        ("Charlotte Hornets", "CHA"),
        ("Hornets", "CHA"),
        ("CHI", "CHI"),
        ("Chicago Bulls", "CHI"),
        ("Bulls", "CHI"),
        ("CLE", "CLE"),
        ("Cleveland Cavaliers", "CLE"),
        ("Cleveland Guardians", "CLE"),
        ("DAL", "DAL"),
        ("Dallas Mavericks", "DAL"),
        ("Mavericks", "DAL"),
        ("DEN", "DEN"),
        ("Denver Nuggets", "DEN"),
        ("Nuggets", "DEN"),
        ("DET", "DET"),
        ("Detroit Pistons", "DET"),
        ("GSW", "GSW"),
        ("Golden State Warriors", "GSW"),
        ("Warriors", "GSW"),
        ("HOU", "HOU"),
        ("Houston", "HOU"),
        ("Houston Rockets", "HOU"),
        ("Rockets", "HOU"),
        ("IND", "IND"),
        ("Indiana", "IND"),
        ("Indiana Pacers", "IND"),
        ("LAC", "LAC"),
        ("Los Angeles Clippers", "LAC"),
        ("Clippers", "LAC"),
        ("LAL", "LAL"),
        ("Los Angeles Lakers", "LAL"),
        ("Lakers", "LAL"),
        ("MEM", "MEM"),
        ("Memphis Grizzlies", "MEM"),
        ("Grizzlies", "MEM"),
        ("MIA", "MIA"),
        ("Miami Heat", "MIA"),
        ("Miami Marlins", "MIA"),
        ("Heat", "MIA"),
        ("MIL", "MIL"),
        ("Milwaukee Bucks", "MIL"),
        ("Bucks", "MIL"),
        ("MIN", "MIN"),
        ("Minnesota Timberwolves", "MIN"),
        ("NOP", "NOP"),
        ("New Orleans Pelicans", "NOP"),
        ("Pelicans", "NOP"),
        ("NYK", "NYK"),
        ("New York Knicks", "NYK"),
        ("Knicks", "NYK"),
        ("OKC", "OKC"),
        ("Oklahoma City Thunder", "OKC"),
        ("Thunder", "OKC"),
        ("ORL", "ORL"),
        ("Orlando Magic", "ORL"),
        ("Magic", "ORL"),
        ("PHI", "PHI"),
        ("Philadelphia 76ers", "PHI"),
        ("PHX", "PHX"),
        ("Phoenix Suns", "PHX"),
        ("Suns", "PHX"),
        ("POR", "POR"),
        ("Portland Trail Blazers", "POR"),
        ("SAC", "SAC"),
        ("Sacramento Kings", "SAC"),
        ("Kings", "SAC"),
        ("SAS", "SAS"),
        ("San Antonio Spurs", "SAS"),
        ("Spurs", "SAS"),
        ("TOR", "TOR"),
        ("Toronto Raptors", "TOR"),
        ("Raptors", "TOR"),
        ("UTA", "UTA"),
        ("Utah Jazz", "UTA"),
        ("WAS", "WAS"),
        ("Washington Wizards", "WAS"),
    ],
)
def test_nba_names_resolve_to_current_elo_team_names(
    raw_name: str, expected_name: str
) -> None:
    resolved_name = _resolve_to_elo_name("nba", raw_name)

    assert expected_name in _elo_teams("nba")
    assert resolved_name == expected_name


@pytest.mark.parametrize(
    ("raw_name", "expected_name"),
    [
        ("LAD", "Los Angeles Dodgers"),
        ("Arizona", "Arizona Diamondbacks"),
        ("SEA", "Seattle Mariners"),
        ("Houston", "Houston Astros"),
        ("Texas", "Texas Rangers"),
        ("TEX", "Texas Rangers"),
        ("TB", "Tampa Bay Rays"),
        ("WSH", "Washington Nationals"),
    ],
)
def test_mlb_names_resolve_to_current_elo_team_names(
    raw_name: str, expected_name: str
) -> None:
    resolved_name = _resolve_to_elo_name("mlb", raw_name)

    assert expected_name in _elo_teams("mlb")
    assert resolved_name == expected_name


@pytest.mark.parametrize(
    ("raw_name", "expected_name"),
    [
        ("LA", "LAK"),
        ("Los Angeles Kings", "LAK"),
        ("NJ", "NJD"),
        ("New Jersey Devils", "NJD"),
        ("SJ", "SJS"),
        ("San Jose Sharks", "SJS"),
        ("TB", "TBL"),
        ("Tampa Bay Lightning", "TBL"),
    ],
)
def test_nhl_names_resolve_to_current_elo_team_names(
    raw_name: str, expected_name: str
) -> None:
    resolved_name = _resolve_to_elo_name("nhl", raw_name)

    assert expected_name in _elo_teams("nhl")
    assert resolved_name == expected_name


def test_cross_sport_fallback_stays_available_for_related_sports() -> None:
    resolved_name = NamingResolver.resolve(
        NamingContext(sport="wncaab", source="kalshi", name="hou")
    )

    assert resolved_name == "Houston"
