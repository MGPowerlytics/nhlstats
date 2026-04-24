"""
NHL Elo fix for DAG - updated section.
"""

# NHL team mapping (full names to abbreviations)
NHL_TEAM_MAPPING = {
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
}


def map_nhl_team(team_name):
    """Map NHL team name to abbreviation."""
    # If it's already an abbreviation (3-4 chars), return as-is
    if team_name and len(team_name) <= 4:
        return team_name
    # Otherwise try to map
    return NHL_TEAM_MAPPING.get(team_name, team_name)


# Updated NHL query for DAG
NHL_ELO_QUERY = """
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
    ORDER BY game_date
"""

print("NHL Elo fix ready for DAG deployment.")
print(f"Team mapping covers {len(NHL_TEAM_MAPPING)} team names.")
