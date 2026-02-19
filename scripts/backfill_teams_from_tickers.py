#!/usr/bin/env python3
"""
Backfill team data by parsing from tickers when recommendations unavailable.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'plugins'))
from db_manager import default_db


def parse_teams_from_ticker_simple(ticker: str, market_title: str = None):
    """
    Simple team parsing from Kalshi ticker.

    Handles patterns like:
    - KXNBAGAME-26JAN30PORNYK-NYK: POR vs NYK
    - KXNHLGAME-26FEB05BOSNYR-BOS: BOS vs NYR
    - KXNCAAMBGAME-26JAN19PROVMARQ-MARQ: PROV vs MARQ
    """
    if not ticker:
        return None, None

    ticker = ticker.upper()

    # NBA team mapping
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

    # NHL team mapping
    nhl_teams = {
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

    # Try to extract team codes
    # Pattern: GAME-DATE(7 chars) + HOME(3) + AWAY(3) + - + BETON(3)
    import re

    # For 3-letter team codes (NBA, NHL)
    match = re.search(r'GAME-\d{2}[A-Z]{3}\d{2}([A-Z]{3})([A-Z]{3})-([A-Z]{3})$', ticker)
    if match:
        home_code = match.group(1)
        away_code = match.group(2)
        bet_code = match.group(3)

        # Map to team names based on sport
        if 'NBAGAME' in ticker:
            home_team = nba_teams.get(home_code, home_code)
            away_team = nba_teams.get(away_code, away_code)
            return home_team, away_team
        elif 'NHLGAME' in ticker:
            home_team = nhl_teams.get(home_code, home_code)
            away_team = nhl_teams.get(away_code, away_code)
            return home_team, away_team
        elif 'NCAAMBGAME' in ticker or 'NCAAWBGAME' in ticker:
            # College basketball - use codes as-is
            return home_code, away_code

    # Fallback: parse from market title
    if market_title:
        # Clean up title
        title = market_title.replace(' Winner?', '').replace(' Winner', '').replace(' winner?', '')

        # Try different separators
        for sep in [' at ', ' vs ', ' versus ', ' - ']:
            if sep in title:
                parts = title.split(sep)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()

    return None, None


def determine_bet_on_simple(side: str, home_team: str, away_team: str, ticker: str = None):
    """Simple logic to determine which team bet is on."""
    if not side or not home_team or not away_team:
        return None

    # For Kalshi: if side is 'yes', betting on team after last dash
    if ticker and side == 'yes':
        parts = ticker.split('-')
        if len(parts) >= 2:
            bet_code = parts[-1].upper()

            # Check if bet_code appears in team names
            if bet_code in home_team.upper():
                return home_team
            elif bet_code in away_team.upper():
                return away_team

    # Fallback: 'yes' typically means home team wins
    if side == 'yes':
        return home_team
    else:
        return away_team


def backfill_teams_from_tickers():
    """Backfill missing team data by parsing from tickers."""
    print("Starting team data backfill from ticker parsing...")

    # Get bets still missing team data
    query = """
        SELECT
            bet_id, ticker, sport, side, market_title,
            home_team, away_team, bet_on
        FROM placed_bets
        WHERE (home_team IS NULL OR home_team = 'None')
          AND status IN ('won', 'lost')
          AND ticker IS NOT NULL
        ORDER BY placed_date
    """

    bets = default_db.fetch_df(query)

    if bets.empty:
        print("✅ No bets missing team data")
        return

    print(f"Found {len(bets)} bets missing team data")

    updated = 0
    failed = 0

    for idx, bet in bets.iterrows():
        bet_id = bet['bet_id']
        ticker = bet['ticker']
        sport = bet['sport']
        side = bet['side']
        market_title = bet['market_title']

        # Parse teams from ticker
        home_team, away_team = parse_teams_from_ticker_simple(ticker, market_title)

        if home_team and away_team:
            # Determine which team bet is on
            bet_on = determine_bet_on_simple(side, home_team, away_team, ticker)

            # Update database
            try:
                update_query = """
                    UPDATE placed_bets
                    SET home_team = :home_team,
                        away_team = :away_team,
                        bet_on = :bet_on
                    WHERE bet_id = :bet_id
                """

                default_db.execute(update_query, params={
                    'home_team': home_team,
                    'away_team': away_team,
                    'bet_on': bet_on,
                    'bet_id': bet_id
                })

                updated += 1

                if updated % 10 == 0:
                    print(f"  Updated {updated} bets...")

            except Exception as e:
                print(f"  ❌ Error updating bet {bet_id}: {e}")
                failed += 1
        else:
            print(f"  ⚠️  Could not parse teams from ticker: {ticker}")
            failed += 1

    print(f"\n✅ Backfill complete:")
    print(f"   Updated: {updated} bets")
    print(f"   Failed: {failed} bets")
    print(f"   Total processed: {len(bets)} bets")


def verify_backfill():
    """Verify the backfill was successful."""
    print("\nVerifying backfill results...")

    # Check remaining missing team data
    query = """
        SELECT
            sport,
            COUNT(*) as total_bets,
            SUM(CASE WHEN home_team IS NULL OR home_team = 'None' THEN 1 ELSE 0 END) as missing,
            ROUND((SUM(CASE WHEN home_team IS NULL OR home_team = 'None' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))::numeric, 1) as missing_pct
        FROM placed_bets
        WHERE status IN ('won', 'lost')
        GROUP BY sport
        ORDER BY total_bets DESC
    """

    results = default_db.fetch_df(query)

    print("Team data completeness after backfill:")
    for _, row in results.iterrows():
        sport = row['sport']
        total = row['total_bets']
        missing = row['missing']
        pct = row['missing_pct']

        if missing > 0:
            print(f"  ❌ {sport}: {missing}/{total} missing ({pct}%)")
        else:
            print(f"  ✅ {sport}: {total}/{total} complete")

    total_missing = results['missing'].sum()
    total_bets = results['total_bets'].sum()
    overall_pct = (total_missing / total_bets * 100) if total_bets > 0 else 100

    print(f"\nOverall: {total_missing}/{total_bets} missing ({overall_pct:.1f}%)")

    if overall_pct < 5:
        print("✅ SUCCESS: Team data completeness acceptable (<5% missing)")
        return True
    else:
        print("⚠️  WARNING: Still too much missing team data")
        return False


def main():
    """Main function."""
    # Set POSTGRES_HOST if not set
    if 'POSTGRES_HOST' not in os.environ:
        os.environ['POSTGRES_HOST'] = 'localhost'

    try:
        # Test connection
        test_query = "SELECT COUNT(*) as count FROM placed_bets WHERE status IN ('won', 'lost')"
        test_result = default_db.fetch_df(test_query)
        settled_bets = test_result.iloc[0]['count']
        print(f"Connected to database. Found {settled_bets} settled bets.\n")

        # Run backfill
        backfill_teams_from_tickers()

        # Verify results
        success = verify_backfill()

        if success:
            print("\n🎉 Team data backfill successful!")
            return 0
        else:
            print("\n⚠️  Team data backfill partially successful - review issues above")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
