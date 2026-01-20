"""
BetMGM Odds Integration via The Odds API.
Fetches live odds from BetMGM and compares with our Elo predictions.
"""

import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import duckdb


class BetMGMOddsAPI:
    """Interface to The Odds API for BetMGM odds."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._load_api_key()
        self.base_url = "https://api.the-odds-api.com/v4"
        self.bookmaker = "betmgm"

    def _load_api_key(self) -> str:
        """Load API key from file."""
        key_file = Path("data/odds_api_key")
        if key_file.exists():
            return key_file.read_text().strip()
        raise ValueError("No API key found. Create data/odds_api_key file.")

    def get_odds(self, sport: str, markets: str = "h2h") -> List[Dict]:
        """
        Fetch odds from The Odds API.

        Args:
            sport: Sport key (basketball_nba, basketball_ncaab, tennis_atp, etc.)
            markets: Markets to fetch (h2h, spreads, totals)

        Returns:
            List of games with odds
        """
        url = f"{self.base_url}/sports/{sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": markets,
            "bookmakers": self.bookmaker,
            "oddsFormat": "american",
        }

        print(f"📥 Fetching {sport} odds from BetMGM...")
        response = requests.get(url, params=params)

        if response.status_code != 200:
            print(f"⚠️  API error {response.status_code}: {response.text}")
            return []

        data = response.json()
        print(f"✓ Found {len(data)} {sport} games with BetMGM odds")

        # Check remaining requests
        remaining = response.headers.get("x-requests-remaining")
        if remaining:
            print(f"  API requests remaining: {remaining}")

        return data

    def american_to_probability(self, american_odds: int) -> float:
        """Convert American odds to implied probability."""
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)


class TeamNameMapper:
    """Maps team names between different systems."""

    def __init__(self):
        self.mappings = self._load_mappings()

    def _load_mappings(self) -> Dict[str, Dict[str, str]]:
        """Load team name mappings from files."""
        mappings = {}

        # BetMGM to our team names
        mapping_files = {
            "nba": "data/betmgm_to_nba_mapping.json",
            "ncaab": "data/betmgm_to_ncaab_mapping.json",
            "wncaab": "data/betmgm_to_wncaab_mapping.json",
        }

        for sport, filepath in mapping_files.items():
            file = Path(filepath)
            if file.exists():
                with open(file) as f:
                    mappings[sport] = json.load(f)

        return mappings

    def normalize_team_name(self, team: str, sport: str = None) -> str:
        """
        Normalize team name for matching.
        Handles common variations.
        """
        # Basic normalization
        normalized = team.strip()
        normalized = normalized.replace(".", "")
        normalized = normalized.replace("'", "")

        # Common replacements
        replacements = {
            "St ": "State ",
            "St.": "State",
            "&": "and",
            " College": "",
            " University": "",
        }

        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        return normalized

    def find_match(self, team: str, candidates: List[str], sport: str = None) -> Optional[str]:
        """
        Find best matching team name from candidates.

        Args:
            team: Team name to match (from BetMGM)
            candidates: List of possible matches (our team names)
            sport: Sport context for better matching

        Returns:
            Best matching team name or None
        """
        # Check manual mapping first
        if sport and sport in self.mappings:
            if team in self.mappings[sport]:
                mapped = self.mappings[sport][team]
                if mapped in candidates:
                    return mapped

        # Direct match
        if team in candidates:
            return team

        # Normalized match
        normalized_team = self.normalize_team_name(team, sport)
        for candidate in candidates:
            if self.normalize_team_name(candidate, sport) == normalized_team:
                return candidate

        # Fuzzy match - contains
        for candidate in candidates:
            if normalized_team in self.normalize_team_name(candidate, sport):
                return candidate
            if self.normalize_team_name(candidate, sport) in normalized_team:
                return candidate

        return None


class BetMGMComparison:
    """Compare BetMGM odds with our Elo predictions."""

    def __init__(self, db_path: str = "data/nhlstats.duckdb"):
        self.db_path = db_path
        self.odds_api = BetMGMOddsAPI()
        self.mapper = TeamNameMapper()

    def get_todays_schedule(self, sport: str) -> List[Dict]:
        """Get today's game schedule from database."""
        conn = duckdb.connect(self.db_path, read_only=True)

        # Map our sport names to table names
        table_map = {
            "nba": "nba_games",
            "ncaab": "ncaab_games",
            "wncaab": "wncaab_games",
            "tennis": "tennis_games",
        }

        table = table_map.get(sport)
        if not table:
            print(f"⚠️  Unknown sport: {sport}")
            return []

        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        try:
            query = f"""
                SELECT 
                    game_date,
                    home_team,
                    away_team,
                    home_score,
                    away_score
                FROM {table}
                WHERE game_date >= '{today}' 
                  AND game_date < '{tomorrow}'
                ORDER BY game_date
            """
            result = conn.execute(query).fetchall()
            conn.close()

            games = []
            for row in result:
                games.append({
                    "date": row[0],
                    "home_team": row[1],
                    "away_team": row[2],
                    "home_score": row[3],
                    "away_score": row[4],
                })
            return games
        except Exception as e:
            print(f"⚠️  Error querying {table}: {e}")
            conn.close()
            return []

    def get_elo_ratings(self, sport: str) -> Dict[str, float]:
        """Load current Elo ratings for a sport."""
        ratings_file = Path(f"data/{sport}_current_elo_ratings.csv")

        if not ratings_file.exists():
            print(f"⚠️  No Elo ratings file for {sport}")
            return {}

        ratings = {}
        with open(ratings_file) as f:
            for line in f:
                if "," in line:
                    parts = line.strip().split(",")
                    if len(parts) >= 2:
                        team, rating = parts[0], parts[1]
                        try:
                            ratings[team] = float(rating)
                        except ValueError:
                            pass

        return ratings

    def calculate_elo_prediction(
        self, home_team: str, away_team: str, ratings: Dict[str, float], home_advantage: float = 100
    ) -> Tuple[float, float]:
        """
        Calculate Elo-based win probability.

        Returns:
            (home_prob, away_prob)
        """
        home_rating = ratings.get(home_team, 1500)
        away_rating = ratings.get(away_team, 1500)

        # Apply home advantage
        home_rating_adj = home_rating + home_advantage

        # Calculate expected score
        home_prob = 1 / (1 + 10 ** ((away_rating - home_rating_adj) / 400))
        away_prob = 1 - home_prob

        return home_prob, away_prob

    def compare_sport(self, sport: str, odds_sport_key: str, home_advantage: float = 100) -> List[Dict]:
        """
        Compare BetMGM odds with our predictions for a sport.

        Args:
            sport: Our sport name (nba, ncaab, etc.)
            odds_sport_key: The Odds API sport key
            home_advantage: Home advantage Elo points

        Returns:
            List of opportunities
        """
        print(f"\n{'='*60}")
        print(f"📊 Analyzing {sport.upper()} - BetMGM vs Elo")
        print(f"{'='*60}\n")

        # Get BetMGM odds
        betmgm_games = self.odds_api.get_odds(odds_sport_key)

        if not betmgm_games:
            print(f"⚠️  No BetMGM odds available for {sport}")
            return []

        # Get our Elo ratings
        elo_ratings = self.get_elo_ratings(sport)

        if not elo_ratings:
            print(f"⚠️  No Elo ratings available for {sport}")
            return []

        print(f"✓ Loaded Elo ratings for {len(elo_ratings)} teams\n")

        opportunities = []

        for game in betmgm_games:
            home_team_odds = game.get("home_team")
            away_team_odds = game.get("away_team")

            if not home_team_odds or not away_team_odds:
                continue

            # Match team names
            elo_teams = list(elo_ratings.keys())
            home_team_elo = self.mapper.find_match(home_team_odds, elo_teams, sport)
            away_team_elo = self.mapper.find_match(away_team_odds, elo_teams, sport)

            if not home_team_elo or not away_team_elo:
                print(f"⚠️  Could not match: {home_team_odds} vs {away_team_odds}")
                continue

            # Get BetMGM odds
            bookmaker_data = None
            for bookmaker in game.get("bookmakers", []):
                if bookmaker.get("key") == "betmgm":
                    bookmaker_data = bookmaker
                    break

            if not bookmaker_data:
                continue

            # Extract moneyline odds
            h2h_market = None
            for market in bookmaker_data.get("markets", []):
                if market.get("key") == "h2h":
                    h2h_market = market
                    break

            if not h2h_market:
                continue

            outcomes = h2h_market.get("outcomes", [])
            home_odds = None
            away_odds = None

            for outcome in outcomes:
                if outcome.get("name") == home_team_odds:
                    home_odds = outcome.get("price")
                elif outcome.get("name") == away_team_odds:
                    away_odds = outcome.get("price")

            if home_odds is None or away_odds is None:
                continue

            # Calculate BetMGM implied probabilities
            home_prob_betmgm = self.odds_api.american_to_probability(home_odds)
            away_prob_betmgm = self.odds_api.american_to_probability(away_odds)

            # Calculate Elo probabilities
            home_prob_elo, away_prob_elo = self.calculate_elo_prediction(
                home_team_elo, away_team_elo, elo_ratings, home_advantage
            )

            # Calculate edges
            home_edge = home_prob_elo - home_prob_betmgm
            away_edge = away_prob_elo - away_prob_betmgm

            # Determine best opportunity
            if abs(home_edge) > abs(away_edge):
                best_bet = "home"
                edge = home_edge
                elo_prob = home_prob_elo
                betmgm_prob = home_prob_betmgm
                odds = home_odds
                bet_team = home_team_elo
            else:
                best_bet = "away"
                edge = away_edge
                elo_prob = away_prob_elo
                betmgm_prob = away_prob_betmgm
                odds = away_odds
                bet_team = away_team_elo

            opportunity = {
                "sport": sport,
                "home_team": home_team_elo,
                "away_team": away_team_elo,
                "commence_time": game.get("commence_time"),
                "best_bet": best_bet,
                "bet_team": bet_team,
                "elo_prob": elo_prob,
                "betmgm_prob": betmgm_prob,
                "edge": edge,
                "betmgm_odds": odds,
                "home_odds": home_odds,
                "away_odds": away_odds,
            }

            opportunities.append(opportunity)

        return opportunities

    def print_opportunities(self, opportunities: List[Dict], min_edge: float = 0.05):
        """Print betting opportunities with edge >= min_edge."""
        # Filter by edge
        filtered = [opp for opp in opportunities if opp["edge"] >= min_edge]

        if not filtered:
            print(f"\n⚠️  No opportunities with edge >= {min_edge:.1%}")
            return

        # Sort by edge
        filtered.sort(key=lambda x: x["edge"], reverse=True)

        print(f"\n{'='*80}")
        print(f"🎯 BETTING OPPORTUNITIES (Edge >= {min_edge:.1%})")
        print(f"{'='*80}\n")

        for opp in filtered:
            print(f"🏀 {opp['away_team']} @ {opp['home_team']}")
            print(f"   Bet: {opp['bet_team'].upper()} ({opp['best_bet']})")
            print(f"   Edge: {opp['edge']:.1%} | Elo: {opp['elo_prob']:.1%} | BetMGM: {opp['betmgm_prob']:.1%}")
            print(f"   BetMGM Odds: {opp['betmgm_odds']:+d}")
            print(f"   Time: {opp['commence_time']}")
            print()

        print(f"Total opportunities: {len(filtered)}")


def main():
    """Main function to check BetMGM opportunities."""
    comparison = BetMGMComparison()

    # Sport configurations
    sports = [
        ("nba", "basketball_nba", 100),
        ("ncaab", "basketball_ncaab", 60),
        ("wncaab", "basketball_wncaab", 60),
        # Tennis handled separately (no home advantage)
        # ("tennis", "tennis_atp", 0),
    ]

    all_opportunities = []

    for sport, odds_key, home_adv in sports:
        opportunities = comparison.compare_sport(sport, odds_key, home_adv)
        all_opportunities.extend(opportunities)

    # Print all opportunities
    if all_opportunities:
        comparison.print_opportunities(all_opportunities, min_edge=0.05)

        # Save to file
        output_file = Path(f"data/betmgm_opportunities_{datetime.now().strftime('%Y-%m-%d')}.json")
        with open(output_file, "w") as f:
            json.dump(all_opportunities, f, indent=2, default=str)
        print(f"\n✓ Saved {len(all_opportunities)} opportunities to {output_file}")
    else:
        print("\n⚠️  No opportunities found")


if __name__ == "__main__":
    main()
