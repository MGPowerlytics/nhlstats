#!/usr/bin/env python3
"""
Utility to parse team/player names from Kalshi tickers.
"""

import re
from typing import Tuple, Optional


def parse_teams_from_ticker(ticker: str, market_title: str = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse home and away teams from Kalshi ticker or market title.

    Args:
        ticker: Kalshi ticker string (e.g., "KXNBAGAME-26FEB05LALGSW-LAL")
        market_title: Optional market title for additional context

    Returns:
        Tuple of (home_team, away_team) or (None, None) if cannot parse
    """
    if not ticker:
        return None, None

    ticker = ticker.upper()

    # Common team abbreviations mapping
    NBA_TEAMS = {
        'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
        'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
        'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
        'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
        'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
        'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
        'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
        'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
        'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
        'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
    }

    NHL_TEAMS = {
        'ANA': 'Anaheim Ducks', 'ARI': 'Arizona Coyotes', 'BOS': 'Boston Bruins',
        'BUF': 'Buffalo Sabres', 'CGY': 'Calgary Flames', 'CAR': 'Carolina Hurricanes',
        'CHI': 'Chicago Blackhawks', 'COL': 'Colorado Avalanche', 'CBJ': 'Columbus Blue Jackets',
        'DAL': 'Dallas Stars', 'DET': 'Detroit Red Wings', 'EDM': 'Edmonton Oilers',
        'FLA': 'Florida Panthers', 'LAK': 'Los Angeles Kings', 'MIN': 'Minnesota Wild',
        'MTL': 'Montreal Canadiens', 'NSH': 'Nashville Predators', 'NJD': 'New Jersey Devils',
        'NYI': 'New York Islanders', 'NYR': 'New York Rangers', 'OTT': 'Ottawa Senators',
        'PHI': 'Philadelphia Flyers', 'PIT': 'Pittsburgh Penguins', 'SJS': 'San Jose Sharks',
        'SEA': 'Seattle Kraken', 'STL': 'St. Louis Blues', 'TBL': 'Tampa Bay Lightning',
        'TOR': 'Toronto Maple Leafs', 'VAN': 'Vancouver Canucks', 'VGK': 'Vegas Golden Knights',
        'WSH': 'Washington Capitals', 'WPG': 'Winnipeg Jets'
    }

    # Try to parse from ticker pattern
    # Common patterns:
    # - KXNBAGAME-26JAN18TORLAL-LAL: TOR vs LAL, betting on LAL
    # - KXNHLGAME-26FEB05BOSNYR-BOS: BOS vs NYR, betting on BOS
    # - KXNCAAMBGAME-26JAN19PROVMARQ-MARQ: PROV vs MARQ, betting on MARQ

    # Extract the team codes part
    match = re.search(r'GAME-\d{2}[A-Z]{3}\d{2}([A-Z]+)([A-Z]+)-([A-Z]+)$', ticker)
    if match:
        # Pattern: GAME-DATEHOME_AWAY-BETON
        home_code = match.group(1)
        away_code = match.group(2)
        bet_on_code = match.group(3)

        # Determine which team is home/away based on sport
        if 'NBAGAME' in ticker:
            home_team = NBA_TEAMS.get(home_code, home_code)
            away_team = NBA_TEAMS.get(away_code, away_code)
        elif 'NHLGAME' in ticker:
            home_team = NHL_TEAMS.get(home_code, home_code)
            away_team = NHL_TEAMS.get(away_code, away_code)
        elif 'NCAAMBGAME' in ticker or 'NCAAWBGAME' in ticker:
            # College basketball - use codes as-is
            home_team = home_code
            away_team = away_code
        else:
            # Unknown sport
            home_team = home_code
            away_team = away_code

        return home_team, away_team

    # Try tennis pattern
    if 'ATPMATCH' in ticker or 'WTAMATCH' in ticker:
        # Tennis: KXWTAMATCH-26FEB05RADCHW-RAD
        # This is harder without player database
        # For now, return placeholder
        return "Player1", "Player2"

    # If market_title is provided, try to parse from it
    if market_title:
        # Common patterns in market titles:
        # - "Los Angeles Lakers at Golden State Warriors Winner?"
        # - "Boston Bruins vs New York Rangers Winner"
        # - "Emma Raducanu vs Iga Swiatek Winner"

        # Remove common suffixes
        title = market_title.replace(' Winner?', '').replace(' Winner', '')

        # Split by common separators
        for separator in [' at ', ' vs ', ' versus ', ' - ']:
            if separator in title:
                parts = title.split(separator)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()

    return None, None


def determine_bet_on(side: str, home_team: str, away_team: str, ticker: str = None) -> Optional[str]:
    """
    Determine which team/player the bet is on.

    Args:
        side: 'yes' or 'no' side of bet
        home_team: Home team name
        away_team: Away team name
        ticker: Optional ticker for additional parsing

    Returns:
        Team/player name the bet is on, or None
    """
    if not side or not home_team or not away_team:
        return None

    # For Kalshi moneyline markets:
    # - "yes" means betting on the team after the dash in ticker
    # - "no" means betting against that team

    if ticker and side == 'yes':
        # Try to parse bet_on from ticker
        match = re.search(r'-([A-Z]+)$', ticker)
        if match:
            bet_on_code = match.group(1)

            # Map code to team name
            if 'NBAGAME' in ticker:
                nba_teams = {
                    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
                    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
                    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
                    'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
                    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
                    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
                    'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
                    'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
                    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
                    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
                }
                return nba_teams.get(bet_on_code, bet_on_code)

    # Fallback: if side is 'yes' and we can't parse from ticker,
    # assume betting on home team (common convention)
    if side == 'yes':
        return home_team
    else:  # side == 'no'
        return away_team


def test_parsing():
    """Test the parsing functions."""
    test_cases = [
        ("KXNBAGAME-26JAN18TORLAL-LAL", "yes", None),
        ("KXNBAGAME-26JAN18NOPHOU-HOU", "yes", None),
        ("KXNHLGAME-26FEB05BOSNYR-BOS", "yes", None),
        ("KXNCAAMBGAME-26JAN19PROVMARQ-MARQ", "yes", None),
        ("KXWTAMATCH-26FEB05RADCHW-RAD", "yes", "Will Emma Raducanu win the Raducanu vs Chwalinska match?"),
    ]

    print("Testing team parsing from tickers:")
    for ticker, side, title in test_cases:
        home, away = parse_teams_from_ticker(ticker, title)
        bet_on = determine_bet_on(side, home, away, ticker)
        print(f"  {ticker}")
        print(f"    Home: {home}, Away: {away}, Bet on: {bet_on} (side: {side})")


if __name__ == "__main__":
    test_parsing()
