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

# MLB parameters
# Empirically tuned via backtest (see plugins/elo/mlb_elo_rating.py docstring):
# K=4 + HA=20 yields +1.68 pts accuracy / +3.01% relative improvement vs the
# previous K=10/HA=75 settings.
MLB_K_FACTOR = 4.0
MLB_HOME_ADVANTAGE = 20.0

# Master switch for the MLB ensemble (team Elo + pythagorean + rest + park).
# When True, ``_load_elo_system('mlb', ...)`` returns an MLBEnsembleAdapter
# instead of a bare MLBEloRating. The adapter is a drop-in replacement so
# ``OddsComparator`` is unaffected. Set False to fall back to plain Elo.
MLB_USE_ENSEMBLE = True

# Governs the live MLB betting path. When True, the DAG requires persisted
# ``mlb_model_predictions`` rows and refuses to fall back to ensemble/plain Elo.
MLB_USE_GOVERNED_MODEL = True

# Master switch for the Ligue 1 ensemble (team Elo + ML + Bookmaker).
LIGUE1_USE_ENSEMBLE = True

# NFL parameters
NFL_K_FACTOR = 20.0
NFL_HOME_ADVANTAGE = 65.0

# Soccer (EPL, Ligue1) parameters
EPL_K_FACTOR = 40.0
EPL_HOME_ADVANTAGE = 60.0

LIGUE1_K_FACTOR = 20.0
LIGUE1_HOME_ADVANTAGE = 60.0

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
        "mlb": _create_mlb_config(),
    }

    # NFL uses standard unified_games query
    registry["nfl"] = SportEloConfig(
        sport_id="nfl",
        k_factor=NFL_K_FACTOR,
        home_advantage=NFL_HOME_ADVANTAGE,
        query=get_default_query("nfl"),
    )

    # Ligue 1 uses ligue1_games table for 3-way results
    registry["ligue1"] = SportEloConfig(
        sport_id="ligue1",
        k_factor=LIGUE1_K_FACTOR,
        home_advantage=LIGUE1_HOME_ADVANTAGE,
        query="""
            SELECT game_date, home_team, away_team, home_score, away_score, result
            FROM ligue1_games
            WHERE game_date IS NOT NULL
              AND home_score IS NOT NULL
              AND result IS NOT NULL
            ORDER BY game_date
        """,
    )

    # Add sports that use separate game classes (query=None)
    for sport_id, k, home in [
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


def _create_mlb_config() -> SportEloConfig:
    """Create MLB Elo configuration."""
    return SportEloConfig(
        sport_id="mlb",
        k_factor=MLB_K_FACTOR,
        home_advantage=MLB_HOME_ADVANTAGE,
        query=_get_mlb_query(),
        team_mapper=_create_mlb_team_mapper(),
    )


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
        k_factor=EPL_K_FACTOR,
        home_advantage=EPL_HOME_ADVANTAGE,
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


# NBA team name to abbreviation mappings.
# Covers full names, city-only, team-only, and no-space variants.
NBA_TEAM_NAME_MAPPING = {
    # Full names
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
    # LA shorthand
    "LA Clippers": "LAC",
    "LA Lakers": "LAL",
    # City-only
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
    # Team-only
    "Hawks": "ATL",
    "Celtics": "BOS",
    "Nets": "BKN",
    "Hornets": "CHA",
    "Bulls": "CHI",
    "Cavaliers": "CLE",
    "Mavericks": "DAL",
    "Nuggets": "DEN",
    "Pistons": "DET",
    "Warriors": "GSW",
    "Rockets": "HOU",
    "Pacers": "IND",
    "Clippers": "LAC",
    "Lakers": "LAL",
    "Grizzlies": "MEM",
    "Heat": "MIA",
    "Bucks": "MIL",
    "Timberwolves": "MIN",
    "Pelicans": "NOP",
    "Knicks": "NYK",
    "Thunder": "OKC",
    "Magic": "ORL",
    "76ers": "PHI",
    "Suns": "PHX",
    "Trail Blazers": "POR",
    "Kings": "SAC",
    "Spurs": "SAS",
    "Raptors": "TOR",
    "Jazz": "UTA",
    "Wizards": "WAS",
    # No-space variants
    "GoldenState": "GSW",
    "LAClippers": "LAC",
    "LALakers": "LAL",
    "NewOrleans": "NOP",
    "NewYork": "NYK",
    "OklahomaCity": "OKC",
    "SanAntonio": "SAS",
}

# Valid NBA team abbreviations (must be exactly these 30)
VALID_NBA_TEAM_ABBRS = {
    "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET",
    "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN",
    "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS",
    "TOR", "UTA", "WAS",
}

# Names that leak into NBA data but are not NBA teams
NBA_CONTAMINANTS = {
    # NFL teams
    "Bears", "Bengals", "Bills", "Broncos", "Browns", "Buccaneers",
    "Cardinals", "Chargers", "Chiefs", "Colts", "Commanders", "Cowboys",
    "Dolphins", "Eagles", "Falcons", "49ers", "Giants", "Jaguars", "Jets",
    "Lions", "Packers", "Panthers", "Patriots", "Raiders", "Rams", "Ravens",
    "Saints", "Seahawks", "Steelers", "Texans", "Titans", "Vikings",
    # International / non-NBA basketball
    "Adelaide 36ers", "Cairns Taipans", "Flamengo Flamengo",
    "Guangzhou Loong-Lions", "Hapoel Jerusalem B.C.",
    "Madrid Baloncesto", "Melbourne United", "New Zealand Breakers",
    "Ra'anana Maccabi Ra'anana", "Ratiopharm Ulm",
    "South East Melbourne Phoenix",
    # All-Star teams
    "East NBA All Stars East", "West NBA All Stars West",
}


def _create_nba_team_mapper() -> Callable[[str], Optional[str]]:
    """Create NBA team name to abbreviation mapper.

    Returns the canonical abbreviation for valid NBA team names,
    or None for known contaminants (NFL teams, international clubs, etc.).
    """

    def map_nba_team(team_name: str) -> Optional[str]:
        """Map NBA team name to abbreviation."""
        if not team_name:
            return None

        # Known contaminants -> skip
        if team_name in NBA_CONTAMINANTS:
            return None

        # Already a valid abbreviation
        if team_name in VALID_NBA_TEAM_ABBRS:
            return team_name

        # Look up in mapping (handles full names, city-only, team-only, no-space)
        mapped = NBA_TEAM_NAME_MAPPING.get(team_name)
        if mapped is not None:
            return mapped

        # If it's a short string that isn't a valid abbrev or in the mapping,
        # it's likely a contaminant abbreviation (e.g. NFL "Jets")
        if len(team_name) <= 4:
            return None

        # Unknown team — pass through (will create a new Elo entity)
        return team_name

    return map_nba_team


# NHL team name to abbreviation mappings
NHL_TEAM_NAME_MAPPING = {
    # Full names
    "Anaheim Ducks": "ANA",
    "Arizona Coyotes": "UTA",  # relocated to Utah (2024)
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
    "ARI": "UTA",  # historical abbreviation → current Utah
    # Team-only names
    "Ducks": "ANA",
    "Coyotes": "UTA",  # relocated to Utah
    "Bruins": "BOS",
    "Sabres": "BUF",
    "Flames": "CGY",
    "Hurricanes": "CAR",
    "Blackhawks": "CHI",
    "Avalanche": "COL",
    "Blue Jackets": "CBJ",
    "Stars": "DAL",
    "Red Wings": "DET",
    "Oilers": "EDM",
    "Panthers": "FLA",
    "Kings": "LAK",
    "Wild": "MIN",
    "Canadiens": "MTL",
    "Predators": "NSH",
    "Devils": "NJD",
    "Islanders": "NYI",
    "Rangers": "NYR",
    "Senators": "OTT",
    "Flyers": "PHI",
    "Penguins": "PIT",
    "Sharks": "SJS",
    "Kraken": "SEA",
    "Blues": "STL",
    "Lightning": "TBL",
    "Maple Leafs": "TOR",
    "Mammoth": "UTA",
    "Canucks": "VAN",
    "Golden Knights": "VGK",
    "Capitals": "WSH",
    "Jets": "WPG",
}

VALID_NHL_TEAM_ABBRS = {
    "ANA",
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


# MLB team name canonicalization - maps historical/variant names to current canonical names
MLB_TEAM_NAME_MAPPING = {
    "Cleveland Indians": "Cleveland Guardians",
    "Oakland Athletics": "Athletics",
    "Tampa Bay Devil Rays": "Tampa Bay Rays",
    "Florida Marlins": "Miami Marlins",
    "Montreal Expos": "Washington Nationals",
    "Anaheim Angels": "Los Angeles Angels",
    "Los Angeles Angels of Anaheim": "Los Angeles Angels",
    "California Angels": "Los Angeles Angels",
}


def _create_mlb_team_mapper() -> Callable[[str], str]:
    """Create MLB team name canonicalization mapper.

    Maps historical/variant team names to current canonical names
    (e.g. 'Cleveland Indians' -> 'Cleveland Guardians').
    """

    def map_mlb_team(team_name: str) -> str:
        """Map MLB team name to canonical form."""
        if not team_name:
            return team_name
        return MLB_TEAM_NAME_MAPPING.get(team_name, team_name)

    return map_mlb_team


def _create_nhl_team_mapper() -> Callable[[str], Optional[str]]:
    """Create NHL team name to abbreviation mapper."""
    from plugins.naming_resolver import NamingResolver, NamingContext

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
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win,
               home_pitcher_id, away_pitcher_id
        FROM mlb_games
        WHERE game_type IN ('R', 'D', 'L', 'W', 'F')
          AND status IN ('Final', 'Game Over', 'Completed Early')
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
