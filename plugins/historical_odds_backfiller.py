"""
Historical Odds Backfiller using Sportsbook Review (SBR) data.
Backfills moneyline odds for NHL, NBA, MLB, and NFL back to 2021.
"""

import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(__file__))
from db_manager import default_db
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

class HistoricalOddsBackfiller:
    """
    Backfills historical odds from Sportsbook Review (SBR) HTML archives.
    Scrapes tables directly from pages like https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2022-23/
    """

    BASE_URL = "https://www.sportsbookreviewsonline.com/scoresoddsarchives"

    # Team name mappings (SBR Name -> Our Abbreviation/Name)
    TEAM_MAPPINGS = {
        # NHL
        'SanJose': 'SJS', 'TampaBay': 'TBL', 'Florida': 'FLA', 'Detroit': 'DET',
        'Colorado': 'COL', 'Boston': 'BOS', 'NYIslanders': 'NYI', 'Chicago': 'CHI',
        'Arizona': 'ARI', 'Vegas': 'VGK', 'Buffalo': 'BUF', 'Columbus': 'CBJ',
        'Montreal': 'MTL', 'Carolina': 'CAR', 'Winnipeg': 'WPG', 'NYRangers': 'NYR',
        'NewJersey': 'NJD', 'Philadelphia': 'PHI', 'Toronto': 'TOR', 'Ottawa': 'OTT',
        'Pittsburgh': 'PIT', 'Washington': 'WSH', 'St.Louis': 'STL', 'Dallas': 'DAL',
        'Edmonton': 'EDM', 'Nashville': 'NSH', 'Anaheim': 'ANA', 'LosAngeles': 'LAK',
        'Vancouver': 'VAN', 'Seattle': 'SEA', 'Calgary': 'CGY', 'Minnesota': 'MIN',

        # NBA
        'Boston': 'Celtics', 'Philadelphia': '76ers', 'Brooklyn': 'Nets', 'NewYork': 'Knicks', 'Toronto': 'Raptors',
        'Milwaukee': 'Bucks', 'Cleveland': 'Cavaliers', 'Chicago': 'Bulls', 'Indiana': 'Pacers', 'Detroit': 'Pistons',
        'Miami': 'Heat', 'Atlanta': 'Hawks', 'Charlotte': 'Hornets', 'Washington': 'Wizards', 'Orlando': 'Magic',
        'Denver': 'Nuggets', 'Minnesota': 'Timberwolves', 'OklahomaCity': 'Thunder', 'Utah': 'Jazz', 'Portland': 'Trail Blazers',
        'Sacramento': 'Kings', 'GoldenState': 'Warriors', 'Phoenix': 'Suns', 'LADrunkers': 'Clippers', 'LALakers': 'Lakers', # SBR weirdness
        'Memphis': 'Grizzlies', 'NewOrleans': 'Pelicans', 'Dallas': 'Mavericks', 'Houston': 'Rockets', 'SanAntonio': 'Spurs',
        'LAClip': 'Clippers', 'LAClippers': 'Clippers',

        # NFL
        'Buffalo': 'Bills', 'Miami': 'Dolphins', 'NewEngland': 'Patriots', 'NYJets': 'Jets',
        'Baltimore': 'Ravens', 'Cincinnati': 'Ravens', 'Cleveland': 'Browns', 'Pittsburgh': 'Steelers',
        'Houston': 'Texans', 'Indianapolis': 'Colts', 'Jacksonville': 'Jaguars', 'Tennessee': 'Titans',
        'Denver': 'Broncos', 'KansasCity': 'Chiefs', 'LasVegas': 'Raiders', 'LAChargers': 'Chargers',
        'Dallas': 'Cowboys', 'NYGiants': 'Giants', 'Philadelphia': 'Eagles', 'Washington': 'Commanders',
        'Chicago': 'Bears', 'Detroit': 'Lions', 'GreenBay': 'Packers', 'Minnesota': 'Vikings',
        'Atlanta': 'Falcons', 'Carolina': 'Panthers', 'NewOrleans': 'Saints', 'TampaBay': 'Buccaneers',
        'Arizona': 'Cardinals', 'LARams': 'Rams', 'SanFrancisco': '49ers', 'Seattle': 'Seahawks'
    }

    def __init__(self, data_dir: str = "data/historical_odds"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _normalize_team(self, team_name: str) -> str:
        """Normalizes SBR team name to our standard ID."""
        # Check mapping first
        if team_name in self.TEAM_MAPPINGS:
            return self.TEAM_MAPPINGS[team_name]

        # Try stripping spaces/dots
        clean_name = team_name.replace(' ', '').replace('.', '')
        if clean_name in self.TEAM_MAPPINGS:
            return self.TEAM_MAPPINGS[clean_name]

        return team_name

    def _generate_game_id(self, sport: str, game_date: datetime, home_team: str, away_team: str) -> str:
        """Generates consistent game_id."""
        date_str = game_date.strftime('%Y%m%d')
        # Use normalized names for ID generation
        home_norm = self._normalize_team(home_team)
        away_norm = self._normalize_team(away_team)

        home_slug = "".join(filter(str.isalnum, home_norm)).upper()
        away_slug = "".join(filter(str.isalnum, away_norm)).upper()
        return f"{sport.upper()}_{date_str}_{home_slug}_{away_slug}"

    def ml_to_decimal(self, ml) -> float:
        """Converts American Moneyline to Decimal odds."""
        try:
            # Remove any 'NL' or 'pk' or text
            if isinstance(ml, str):
                ml = ml.strip().lower()
                if ml == 'pk' or ml == 'ev': ml = 100
                elif ml == 'nl': return 1.0

            ml = float(ml)
            if ml == 0: return 1.0
            if ml > 0:
                return (ml / 100) + 1
            else:
                return (100 / abs(ml)) + 1
        except:
            return 1.0

    def scrape_sbr_season(self, sport: str, season: str) -> List[Dict]:
        """
        Scrapes SBR HTML page for a sport and season.
        season: '2023-24'
        """
        # Construct URL: https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl-odds-2023-24/
        # Note: Some older seasons might have different patterns, but recent ones seem consistent.
        url = f"{self.BASE_URL}/{sport}-odds-{season}/"

        print(f"🌐 Scraping {sport.upper()} {season} from {url}...")

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                # Try without trailing slash
                url = url.rstrip('/')
                response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                print(f"  ⚠️  Failed to fetch page: HTTP {response.status_code}")
                return []

            return self.parse_sbr_html(sport, response.text, season)

        except Exception as e:
            print(f"  ❌ Error scraping: {e}")
            return []

    def parse_sbr_html(self, sport: str, html_content: str, season_str: str) -> List[Dict]:
        """
        Parses the HTML table from SBR.
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find the main data table
        table = soup.find('table')
        if not table:
            print("  ⚠️  No table found on page.")
            return []

        rows = table.find_all('tr')
        if not rows:
            return []

        print(f"  Found {len(rows)} rows. Parsing...")

        games = []
        start_year = int(season_str.split('-')[0])

        # SBR format: Pairs of rows (Away/Home).
        # Skip header row(s). Look for rows with data.

        current_game = {}

        # Helper to clean cell text
        def clean_text(cell):
            return cell.get_text(strip=True)

        # Iterate through rows
        i = 0
        while i < len(rows):
            row = rows[i]
            cells = row.find_all('td')
            i += 1

            if not cells or len(cells) < 4: continue

            # Check if it's a header row
            if clean_text(cells[0]).lower() == 'date': continue

            # Assume this is the Away team row
            try:
                date_text = clean_text(cells[0])
                if not date_text or not date_text[0].isdigit(): continue

                rot = clean_text(cells[1])
                team_name = clean_text(cells[3])
                score = clean_text(cells[7]) # Final score usually at index 7

                # Odds columns can vary, but usually:
                # Open (8), Close (9), PuckLine (10), OpenOU (11), CloseOU (12)
                # Sometimes column counts differ.
                # We want Moneyline. Usually 'Close' (index 9) or 'Open' (index 8).
                # Let's try to get Closing ML.
                ml_close = clean_text(cells[9]) if len(cells) > 9 else None

                # Check for next row (Home team)
                if i >= len(rows): break
                home_row = rows[i]
                home_cells = home_row.find_all('td')
                i += 1

                if not home_cells or len(home_cells) < 4: continue

                home_team_name = clean_text(home_cells[3])
                home_score = clean_text(home_cells[7])
                home_ml_close = clean_text(home_cells[9]) if len(home_cells) > 9 else None

                # Parse Date
                # date_text is usually MMDD (e.g., 1012 for Oct 12)
                if len(date_text) == 3: date_text = '0' + date_text
                month = int(date_text[:2])
                day = int(date_text[2:])

                # Determine year
                # Season starts in late year (e.g. 2023) and ends in next year (2024)
                # If month >= 8, it's start_year. Else start_year + 1.
                year = start_year if month >= 8 else start_year + 1
                game_date = datetime(year, month, day)

                games.append({
                    'sport': sport,
                    'game_date': game_date,
                    'home_team': home_team_name,
                    'away_team': team_name,
                    'home_ml': home_ml_close,
                    'away_ml': ml_close,
                    'home_score': home_score,
                    'away_score': score,
                    'season': start_year
                })

            except Exception as e:
                # print(f"    Error parsing row {i}: {e}")
                continue

        print(f"  ✓ Extracted {len(games)} games.")
        return games

    def save_to_db(self, games: List[Dict]):
        """Saves backfilled games and odds to database."""
        if not games: return

        print(f"💾 Saving {len(games)} historical games to database...")

        try:
            count = 0
            for g in games:
                try:
                    game_id = self._generate_game_id(g['sport'], g['game_date'], g['home_team'], g['away_team'])
                    date_str = g['game_date'].strftime('%Y-%m-%d')

                    home_norm = self._normalize_team(g['home_team'])
                    away_norm = self._normalize_team(g['away_team'])

                    # 1. Insert into unified_games (ignore if exists)
                    unified_games_query = """
                        INSERT INTO unified_games (
                            game_id, sport, game_date, season, home_team_name,
                            away_team_name, home_score, away_score, status
                        ) VALUES (:game_id, :sport, :game_date, :season, :home_team_name,
                                :away_team_name, :home_score, :away_score, :status)
                        ON CONFLICT (game_id) DO NOTHING
                    """
                    default_db.execute(unified_games_query, {
                        'game_id': game_id,
                        'sport': g['sport'].upper(),
                        'game_date': date_str,
                        'season': g['season'],
                        'home_team_name': home_norm,
                        'away_team_name': away_norm,
                        'home_score': g['home_score'],
                        'away_score': g['away_score'],
                        'status': 'Final'
                    })

                    # 2. Insert into historical_betting_lines for CLV backfill
                    home_dec = self.ml_to_decimal(g['home_ml'])
                    away_dec = self.ml_to_decimal(g['away_ml'])

                    if home_dec > 1 and away_dec > 1:
                        # Convert decimal to implied probability
                        home_implied_prob = 1.0 / home_dec
                        away_implied_prob = 1.0 / away_dec

                        # Convert ML strings to numeric values for database storage
                        home_ml_numeric = self.ml_to_decimal(g['home_ml']) - 1  # Convert back to American odds
                        away_ml_numeric = self.ml_to_decimal(g['away_ml']) - 1  # Convert back to American odds

                        # Handle 'pk' (even money) case
                        if g['home_ml'].lower() in ['pk', 'ev']:
                            home_ml_numeric = 100
                        elif isinstance(g['home_ml'], str) and g['home_ml'].lower() not in ['nl']:
                            try:
                                home_ml_numeric = float(g['home_ml'])
                            except:
                                home_ml_numeric = None

                        if g['away_ml'].lower() in ['pk', 'ev']:
                            away_ml_numeric = 100
                        elif isinstance(g['away_ml'], str) and g['away_ml'].lower() not in ['nl']:
                            try:
                                away_ml_numeric = float(g['away_ml'])
                            except:
                                away_ml_numeric = None

                        if home_ml_numeric is not None and away_ml_numeric is not None:
                            # For historical lines, we assume closing odds are the same as opening
                            # In reality, we'd want both, but SBR gives us closing
                            historical_lines_query = """
                                INSERT INTO historical_betting_lines (
                                    game_date, home_team, away_team,
                                    home_ml_close, away_ml_close,
                                    home_implied_prob_close, away_implied_prob_close,
                                    source, fetched_at
                                ) VALUES (:game_date, :home_team, :away_team,
                                        :home_ml_close, :away_ml_close,
                                        :home_implied_prob_close, :away_implied_prob_close,
                                        :source, :fetched_at)
                                ON CONFLICT (game_date, home_team, away_team) DO NOTHING
                            """
                            default_db.execute(historical_lines_query, {
                                'game_date': date_str,
                                'home_team': home_norm,
                                'away_team': away_norm,
                                'home_ml_close': home_ml_numeric,
                                'away_ml_close': away_ml_numeric,
                                'home_implied_prob_close': home_implied_prob,
                                'away_implied_prob_close': away_implied_prob,
                                'source': 'SBR',
                                'fetched_at': datetime.now()
                            })
                            count += 1
                except Exception as e:
                    continue

            print(f"  ✓ Finished saving batch ({count} games with odds).")
        except Exception as e:
            print(f"❌ Error saving to database: {e}")

    def run_backfill(self, sports: List[str] = None, seasons: List[str] = None):
        """Runs the backfill for specified sports and seasons."""
        if not sports: sports = ['nhl', 'nba', 'mlb', 'nfl']
        # SBR archives seem to stop at 2022-23 currently
        if not seasons: seasons = ['2020-21', '2021-22', '2022-23']

        for sport in sports:
            print(f"\n🚀 Backfilling {sport.upper()}...")
            for season in seasons:
                # SBR has slightly different season naming for MLB (just the year)
                if sport == 'mlb':
                    year = season.split('-')[0]
                    # Check if year is valid for MLB (starts in spring)
                    # For MLB 2022, file is mlb-odds-2022
                    games = self.scrape_sbr_season(sport, year)
                else:
                    games = self.scrape_sbr_season(sport, season)

                self.save_to_db(games)

if __name__ == "__main__":
    backfiller = HistoricalOddsBackfiller()
    # Run full backfill
    backfiller.run_backfill()
