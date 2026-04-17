"""
Configuration for Elo rating updates across different sports.

This module provides sport-specific configurations to eliminate duplication
in the update_elo_ratings function.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Callable, Any

# Default Elo parameters
DEFAULT_K_FACTOR = 20.0
DEFAULT_HOME_ADVANTAGE = 100.0
DEFAULT_INITIAL_RATING = 1500.0

# NBA parameters
NBA_K_FACTOR = 20.0
NBA_HOME_ADVANTAGE = 100.0
NBA_SEASON_REVERSION = 0.4

# NHL parameters
NHL_K_FACTOR = 10.0
NHL_HOME_ADVANTAGE = 50.0
NHL_RECENCY_WEIGHT = 0.2

# MLB parameters (updated from K=20, HA=50 to K=10, HA=75 for better calibration)
MLB_K_FACTOR = 10.0
MLB_HOME_ADVANTAGE = 75.0

# NFL parameters
NFL_K_FACTOR = 20.0
NFL_HOME_ADVANTAGE = 65.0

# Soccer (EPL, Ligue1) parameters
SOCCER_K_FACTOR = 20.0
SOCCER_HOME_ADVANTAGE = 60.0

# NCAAB parameters
NCAAB_K_FACTOR = 20.0
NCAAB_HOME_ADVANTAGE = 100.0

# Unrivaled (WNBA subset/related) parameters
UNRIVALED_K_FACTOR = 24.0
UNRIVALED_HOME_ADVANTAGE = 0.0

# Tennis parameters
TENNIS_K_FACTOR = 32.0
TENNIS_HOME_ADVANTAGE = 0.0

# CBA parameters
CBA_K_FACTOR = 20.0
CBA_HOME_ADVANTAGE = 80.0


@dataclass
class SportEloConfig:
    """Configuration for a sport's Elo update process."""

    # Sport identifier
    sport_id: str

    # Elo parameters
    k_factor: float = DEFAULT_K_FACTOR
    home_advantage: float = DEFAULT_HOME_ADVANTAGE
    initial_rating: float = DEFAULT_INITIAL_RATING

    # Sport-specific parameters
    recency_weight: Optional[float] = None  # For NHL
    season_reversion_factor: Optional[float] = None  # For NBA

    # Database query (None means use default unified_games query)
    query: Optional[str] = None

    # Team name mapping function
    team_mapper: Optional[Callable[[str], Optional[str]]] = None

    # Additional Elo class initialization parameters
    elo_init_kwargs: Optional[Dict[str, Any]] = None

    # Game processing function (for sports with special processing)
    process_game_func: Optional[Callable[[Any, Dict, Any], None]] = None

    # Whether to use legacy_update method
    use_legacy_update: bool = False

    # Whether this sport has separate ratings (e.g., tennis ATP/WTA)
    has_separate_ratings: bool = False

    def __post_init__(self):
        if self.elo_init_kwargs is None:
            self.elo_init_kwargs = {}


def get_sport_config(sport: str) -> SportEloConfig:
    """Get configuration for a specific sport."""
    config_registry = _create_sport_config_registry()
    return config_registry.get(sport, SportEloConfig(sport_id=sport))


def _create_sport_config_registry() -> Dict[str, SportEloConfig]:
    """Create registry of sport configurations."""
    registry = {
        "nba": _create_nba_config(),
        "nhl": _create_nhl_config(),
        "epl": _create_epl_config(),
        "tennis": _create_tennis_config(),
    }

    # MLB uses mlb_games table with game_type filter to exclude
    # spring training, exhibition, WBC, and All-Star games
    registry["mlb"] = SportEloConfig(
        sport_id="mlb",
        k_factor=MLB_K_FACTOR,
        home_advantage=MLB_HOME_ADVANTAGE,
        query=_get_mlb_query(),
    )

    # NFL uses standard unified_games query
    registry["nfl"] = SportEloConfig(
        sport_id="nfl",
        k_factor=NFL_K_FACTOR,
        home_advantage=NFL_HOME_ADVANTAGE,
        query=get_default_query("nfl"),
    )

    # Add sports that use separate game classes (query=None)
    for sport_id, k, home in [
        ("ligue1", SOCCER_K_FACTOR, SOCCER_HOME_ADVANTAGE),
        ("ncaab", NCAAB_K_FACTOR, NCAAB_HOME_ADVANTAGE),
        ("wncaab", NCAAB_K_FACTOR, NCAAB_HOME_ADVANTAGE),
        ("unrivaled", UNRIVALED_K_FACTOR, UNRIVALED_HOME_ADVANTAGE),
        ("cba", CBA_K_FACTOR, CBA_HOME_ADVANTAGE),
    ]:
        registry[sport_id] = SportEloConfig(
            sport_id=sport_id,
            k_factor=k,
            home_advantage=home,
            query=None,
        )

    return registry


def _create_nba_config() -> SportEloConfig:
    """Create NBA Elo configuration."""
    return SportEloConfig(
        sport_id="nba",
        k_factor=NBA_K_FACTOR,
        home_advantage=NBA_HOME_ADVANTAGE,
        season_reversion_factor=NBA_SEASON_REVERSION,
        query="""
            SELECT game_date, home_team_name as home_team, away_team_name as away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM unified_games
            WHERE sport = 'NBA'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
            ORDER BY game_date
        """,
        team_mapper=_create_nba_team_mapper(),
    )


def _create_nhl_config() -> SportEloConfig:
    """Create NHL Elo configuration."""
    return SportEloConfig(
        sport_id="nhl",
        k_factor=NHL_K_FACTOR,
        home_advantage=NHL_HOME_ADVANTAGE,
        recency_weight=NHL_RECENCY_WEIGHT,
        query="""
            SELECT
                game_date,
                home_team_name,
                away_team_name,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM unified_games
            WHERE sport = 'NHL'
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND home_team_name IS NOT NULL
              AND away_team_name IS NOT NULL
              AND home_team_name NOT IN ('Bills', 'Celtics', 'Eagles', 'Cowboys', 'Lions')
              AND away_team_name NOT IN ('Bills', 'Celtics', 'Eagles', 'Cowboys', 'Lions')
            ORDER BY game_date
        """,
        team_mapper=_create_nhl_team_mapper(),
        elo_init_kwargs={"recency_weight": NHL_RECENCY_WEIGHT},
    )


def _create_epl_config() -> SportEloConfig:
    """Create EPL Elo configuration."""
    return SportEloConfig(
        sport_id="epl",
        k_factor=SOCCER_K_FACTOR,
        home_advantage=SOCCER_HOME_ADVANTAGE,
        use_legacy_update=True,
        query="""
            SELECT game_date, home_team, away_team, result
            FROM epl_games
            WHERE game_date IS NOT NULL
            ORDER BY game_date
        """,
    )


def _create_tennis_config() -> SportEloConfig:
    """Create Tennis Elo configuration."""
    return SportEloConfig(
        sport_id="tennis",
        k_factor=TENNIS_K_FACTOR,
        home_advantage=TENNIS_HOME_ADVANTAGE,
        has_separate_ratings=True,
        # Uses TennisGames class instead of database query
        query=None,
    )


# NBA team name to abbreviation mappings
NBA_TEAM_NAME_MAPPING = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
    "LA Clippers": "LAC",
    "LA Lakers": "LAL",
}


def _create_nba_team_mapper() -> Callable[[str], str]:
    """Create NBA team name to abbreviation mapper."""

    def map_nba_team(team_name: str) -> str:
        """Map NBA team name to abbreviation."""
        if team_name and len(team_name) <= 4:
            return team_name  # Already an abbreviation
        return NBA_TEAM_NAME_MAPPING.get(team_name, team_name)

    return map_nba_team


# NHL team name to abbreviation mappings
NHL_TEAM_NAME_MAPPING = {
    "Anaheim Ducks": "ANA",
    "Arizona Coyotes": "ARI",
    "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY",
    "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI",
    "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ",
    "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET",
    "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA",
    "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN",
    "Montreal Canadiens": "MTL",
    "Montréal Canadiens": "MTL",
    "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD",
    "New York Islanders": "NYI",
    "New York Rangers": "NYR",
    "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR",
    "Utah Hockey Club": "UTA",
    "Utah Mammoth": "UTA",
    "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
    "Utah": "UTA",
}

VALID_NHL_TEAM_ABBRS = {
    "ANA",
    "ARI",
    "BOS",
    "BUF",
    "CGY",
    "CAR",
    "CHI",
    "COL",
    "CBJ",
    "DAL",
    "DET",
    "EDM",
    "FLA",
    "LAK",
    "MIN",
    "MTL",
    "NSH",
    "NJD",
    "NYI",
    "NYR",
    "OTT",
    "PHI",
    "PIT",
    "SJS",
    "SEA",
    "STL",
    "TBL",
    "TOR",
    "UTA",
    "VAN",
    "VGK",
    "WSH",
    "WPG",
}

NHL_CONTAMINANTS = {
    "Celtics",
    "Bills",
    "Eagles",
    "Cowboys",
    "Lions",
    "Lakers",
    "Thunder",
    "Raptors",
    "Bears",
    "Commanders",
    "Vikings",
    "Steelers",
    "Buccaneers",
    "Cardinals",
    "Seahawks",
    "Vanderbilt",
    "USA",
    "Sweden",
    "Finland",
    "Canada",
    "Team Matthews Team Matthews",
    "Team McDavid Team McDavid",
    "Team Kloss Team Kloss",
    "Central Central",
    "Atlantic Atlantic",
    "Pacific Pacific",
    "Metropolitan Metropolitan",
    "Bern SC Bern",
    "Berlin Eisbaren",
    "München EHC Red Bull München",
}


def _create_nhl_team_mapper() -> Callable[[str], Optional[str]]:
    """Create NHL team name to abbreviation mapper."""
    from naming_resolver import NamingResolver, NamingContext

    def map_nhl_team(team_name: str) -> Optional[str]:
        """Map NHL team name to abbreviation."""
        if not team_name:
            return None

        # Resolve via NamingResolver first
        resolved = NamingResolver.resolve(
            NamingContext(sport="nhl", source="elo", name=team_name)
        )

        if resolved and len(resolved) <= 4 and resolved.upper() in VALID_NHL_TEAM_ABBRS:
            return resolved.upper()

        # Check if it's a known contaminant
        if team_name in NHL_CONTAMINANTS or resolved in NHL_CONTAMINANTS:
            return None

        # Fallback to existing manual logic for any missed cases
        if len(team_name) <= 4 and team_name.upper() in VALID_NHL_TEAM_ABBRS:
            return team_name.upper()

        mapped = NHL_TEAM_NAME_MAPPING.get(team_name)
        if mapped:
            return mapped

        return team_name  # Fallback for unknown but non-blocked names

    return map_nhl_team


def _get_mlb_query() -> str:
    """Get MLB-specific query that filters to regular season and postseason only.

    Uses the mlb_games table which has game_type to exclude spring training (S),
    exhibition/WBC (E), and All-Star (A) games that contaminate Elo ratings.
    """
    return """
        SELECT game_date, home_team, away_team,
               home_score, away_score,
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM mlb_games
        WHERE game_type IN ('R', 'D', 'L', 'W', 'F')
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND home_team IS NOT NULL
          AND away_team IS NOT NULL
        ORDER BY game_date
    """


def get_default_query(sport: str) -> str:
    """Get default database query for a sport."""
    return f"""
        SELECT game_date, home_team_name as home_team, away_team_name as away_team,
               home_score, away_score,
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM unified_games
        WHERE sport = '{sport.upper()}'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND home_team_name IS NOT NULL
          AND away_team_name IS NOT NULL
        ORDER BY game_date
    """
