#!/usr/bin/env python3
"""
Improved utility to parse team/player names from Kalshi tickers.
"""

import re
from typing import Tuple, Optional, Dict


def parse_nba_teams_from_ticker(ticker: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse NBA teams from ticker like KXNBAGAME-26JAN30PORNYK-NYK"""
    # NBA team abbreviations (3 letters)
    NBA_TEAMS: Dict[str, str] = {
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

    # Pattern: KXNBAGAME-DATEHOMEAWAY-BETON
    # Example: KXNBAGAME-26JAN30PORNYK-NYK
    # Home: POR (Portland), Away: NYK (New York), Bet on: NYK

    # Extract the part after GAME- and before the dash
    match = re.search(r'GAME-(\d{2}[A-Z]{3}\d{2})([A-Z]{3})([A-Z]{3})-([A-Z]{3})$', ticker)
    if match:
        date_part = match.group(1)  # 26JAN30
        home_code = match.group(2)  # POR
        away_code = match.group(3)  # NYK
        bet_on_code = match.group(4)  # NYK

        home_team = NBA_TEAMS.get(home_code, home_code)
        away_team = NBA_TEAMS.get(away_code, away_code)

        return home_team, away_team

    return None, None


def parse_nhl_teams_from_ticker(ticker: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse NHL teams from ticker."""
    NHL_TEAMS: Dict[str, str] = {
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

    # Same pattern as NBA
    match = re.search(r'GAME-(\d{2}[A-Z]{3}\d{2})([A-Z]{3})([A-Z]{3})-([A-Z]{3})$', ticker)
    if match:
        home_code = match.group(2)
        away_code = match.group(3)

        home_team = NHL_TEAMS.get(home_code, home_code)
        away_team = NHL_TEAMS.get(away_code, away_code)

        return home_team, away_team

    return None, None


def parse_ncaab_teams_from_ticker(ticker: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse NCAAB teams from ticker."""
    # College basketball teams vary in abbreviation length
    # Pattern: KXNCAAMBGAME-DATEHOMEAWAY-BETON
    # Need to handle variable length codes

    # Try to find the dash before bet code
    parts = ticker.split('-')
    if len(parts) >= 3:
        # Last part is bet code
        bet_code = parts[-1]

        # The part before last dash contains date and teams
        middle = parts[-2]

        # Date is first 7 chars: 26JAN30
        if len(middle) >= 7:
            date_part = middle[:7]
            teams_part = middle[7:]

            # Teams part could be 6+ chars (3+3 or 4+2 etc.)
            # For now, split in middle
            if len(teams_part) >= 6:
                # Assume 3-letter codes
                home_code = teams_part[:3]
                away_code = teams_part[3:6]

                return home_code, away_code

    return None, None


def parse_teams_from_ticker(ticker: str, market_title: str = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse home and away teams from Kalshi ticker.

    Args:
        ticker: Kalshi ticker string
        market_title: Optional market title for fallback

    Returns:
        Tuple of (home_team, away_team)
    """
    if not ticker:
        return None, None

    ticker = ticker.upper()

    # Try sport-specific parsing
    if 'NBAGAME' in ticker:
        home, away = parse_nba_teams_from_ticker(ticker)
        if home and away:
            return home, away
    elif 'NHLGAME' in ticker:
        home, away = parse_nhl_teams_from_ticker(ticker)
        if home and away:
            return home, away
    elif 'NCAAMBGAME' in ticker or 'NCAAWBGAME' in ticker:
        home, away = parse_ncaab_teams_from_ticker(ticker)
        if home and away:
            return home, away

    # Fallback: parse from market title
    if market_title:
        # Remove common suffixes
        title = market_title.replace(' Winner?', '').replace(' Winner', '').replace(' winner?', '')

        # Split by common separators
        for separator in [' at ', ' vs ', ' versus ', ' - ']:
            if separator in title:
                parts = title.split(separator)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()

    return None, None


def determine_bet_on(side: str, home_team: str, away_team: str, ticker: str = None) -> Optional[str]:
    """
    Determine which team the bet is on.

    Args:
        side: 'yes' or 'no'
        home_team: Home team
        away_team: Away team
        ticker: Ticker for parsing bet code

    Returns:
        Team name or None
    """
    if not side or not home_team or not away_team:
        return None

    # For Kalshi: if side is 'yes', betting on the team after last dash
    if ticker and side == 'yes':
        # Extract bet code (team after last dash)
        parts = ticker.split('-')
        if len(parts) >= 2:
            bet_code = parts[-1].upper()

            # Check if bet_code matches home or away team codes
            # This is simplified - would need team code mapping
            if home_team and bet_code in home_team.upper():
                return home_team
            elif away_team and bet_code in away_team.upper():
                return away_team

    # Fallback logic
    if side == 'yes':
        return home_team  # Default to home team
    else:
        return away_team  # 'no' side typically means away team wins


def test_parsing():
    """Test the parsing functions."""
    test_cases = [
        ("KXNBAGAME-26JAN30PORNYK-NYK", "yes", "Portland at New York Knicks Winner?"),
        ("KXNBAGAME-26FEB01LALNYK-NYK", "yes", "Los Angeles Lakers at New York Knicks Winner?"),
        ("KXNBAGAME-26FEB06NOPMIN-MIN", "yes", "New Orleans Pelicans at Minnesota Timberwolves Winner?"),
        ("KXNBAGAME-26JAN31CHIMIA-MIA", "yes", "Chicago Bulls at Miami Heat Winner?"),
        ("KXNBAGAME-26JAN18CHADEN-DEN", "yes", "Charlotte Hornets at Denver Nuggets Winner?"),
    ]

    print("Testing team parsing from tickers:")
    for ticker, side, title in test_cases:
        home, away = parse_teams_from_ticker(ticker, title)
        bet_on = determine_bet_on(side, home, away, ticker)
        print(f"  {ticker}")
        print(f"    Home: {home}")
        print(f"    Away: {away}")
        print(f"    Bet on: {bet_on} (side: {side})")
        print()


if __name__ == "__main__":
    test_parsing()
