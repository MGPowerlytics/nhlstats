"""
Cloudbet API integration for fetching sports betting odds.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


class CloudbetAPI:
    """Interface to Cloudbet sports betting API."""

    BASE_URL = "https://www.cloudbet.com/api"
    FEED_URL = "https://sports-api.cloudbet.com/pub/v2/odds"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Cloudbet API client."""
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            })

    def fetch_markets(self, sport: str, date: Optional[str] = None) -> List[Dict]:
        """
        Fetch betting markets for a sport.

        Args:
            sport: Sport key (basketball, ice-hockey, baseball, american-football)
            date: Optional date filter (YYYY-MM-DD)

        Returns:
            List of market dictionaries
        """
        print(f"📥 Fetching Cloudbet {sport} markets...")

        # Map our sport names to Cloudbet keys
        sport_map = {
            'nba': 'basketball',
            'nhl': 'ice-hockey',
            'mlb': 'baseball',
            'nfl': 'american-football',
            'epl': 'soccer',
            'ncaab': 'basketball'
        }

        cloudbet_sport = sport_map.get(sport, sport)

        try:
            # Cloudbet Feed API is public (no auth needed for odds)
            url = f"{self.FEED_URL}/competitions"
            params = {'sport': cloudbet_sport}

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Extract markets
            markets = []

            if 'competitions' in data:
                for competition in data['competitions']:
                    # Filter for relevant leagues
                    comp_name = competition.get('name', '').lower()

                    # League filtering
                    if sport == 'nba' and 'nba' not in comp_name:
                        continue
                    elif sport == 'nhl' and 'nhl' not in comp_name:
                        continue
                    elif sport == 'mlb' and 'mlb' not in comp_name:
                        continue
                    elif sport == 'nfl' and 'nfl' not in comp_name:
                        continue
                    elif sport == 'epl' and 'premier league' not in comp_name:
                        continue
                    elif sport == 'ncaab' and 'ncaa' not in comp_name:
                        continue

                    # Get events/games
                    for event in competition.get('events', []):
                        market = self._parse_event(event, sport, competition.get('name'))
                        if market:
                            markets.append(market)

            print(f"✓ Found {len(markets)} Cloudbet {sport} markets")
            return markets

        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error fetching Cloudbet markets: {e}")
            return []

    def _parse_event(self, event: Dict, sport: str, competition: str) -> Optional[Dict]:
        """Parse Cloudbet event into standard format."""
        try:
            event_id = event.get('id')
            name = event.get('name', '')

            # Parse teams from event name (e.g., "Boston Celtics vs Miami Heat")
            if ' vs ' in name:
                home_team, away_team = name.split(' vs ')
            elif ' @ ' in name:
                away_team, home_team = name.split(' @ ')
            else:
                return None

            home_team = home_team.strip()
            away_team = away_team.strip()

            # Get moneyline odds
            home_odds = None
            away_odds = None

            for market in event.get('markets', []):
                if market.get('name') == 'Home/Away' or market.get('name') == 'Match Winner':
                    for selection in market.get('selections', []):
                        outcome = selection.get('outcome')
                        price = selection.get('price')

                        if outcome == 'home' or outcome == home_team:
                            home_odds = price
                        elif outcome == 'away' or outcome == away_team:
                            away_odds = price

            if not home_odds or not away_odds:
                return None

            # Convert decimal odds to probability
            home_prob = 1 / home_odds if home_odds else None
            away_prob = 1 / away_odds if away_odds else None

            return {
                'platform': 'cloudbet',
                'event_id': event_id,
                'sport': sport,
                'competition': competition,
                'home_team': home_team,
                'away_team': away_team,
                'home_odds': home_odds,
                'away_odds': away_odds,
                'home_prob': home_prob,
                'away_prob': away_prob,
                'event_time': event.get('cutoffTime'),
                'raw_data': event
            }

        except Exception as e:
            print(f"⚠️  Error parsing event: {e}")
            return None

    def fetch_and_save_markets(self, sport: str, date_str: str) -> int:
        """Fetch markets and save to JSON file."""
        markets = self.fetch_markets(sport, date_str)

        if not markets:
            return 0

        # Save to file
        output_dir = Path(f'data/{sport}')
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f'cloudbet_markets_{date_str}.json'

        with open(output_file, 'w') as f:
            json.dump(markets, f, indent=2)

        print(f"💾 Saved {len(markets)} markets to {output_file}")
        return len(markets)


def fetch_all_sports(date_str: str):
    """Fetch Cloudbet markets for all sports."""
    api = CloudbetAPI()

    sports = ['nba', 'nhl', 'mlb', 'nfl', 'epl', 'ncaab']
    total = 0

    for sport in sports:
        count = api.fetch_and_save_markets(sport, date_str)
        total += count

    print(f"\n✓ Total Cloudbet markets fetched: {total}")
    return total


if __name__ == '__main__':
    from datetime import date
    today = date.today().strftime('%Y-%m-%d')

    print("Testing Cloudbet API integration...")
    api = CloudbetAPI()

    # Test NBA markets
    markets = api.fetch_markets('nba')

    if markets:
        print(f"\n📊 Sample market:")
        print(json.dumps(markets[0], indent=2))
