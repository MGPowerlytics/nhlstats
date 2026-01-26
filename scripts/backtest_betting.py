#!/usr/bin/env python3
"""
Backtest betting performance by comparing Elo/Glicko-2 predictions
against actual outcomes from The Odds API.
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

# Add plugins to path
sys.path.insert(0, "/mnt/data2/nhlstats/plugins")

from plugins.elo import NBAEloRating
from plugins.elo import NHLEloRating
from plugins.elo import MLBEloRating
from plugins.elo import NFLEloRating
from plugins.elo import EPLEloRating
from plugins.elo import NCAABEloRating


class BettingBacktest:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4/sports"
        self.db_path = "/mnt/data2/nhlstats/data/nhlstats.duckdb"

        # Sport mappings for The Odds API
        self.sport_keys = {
            "NBA": "basketball_nba",
            "NHL": "icehockey_nhl",
            "NFL": "americanfootball_nfl",
            "MLB": "baseball_mlb",
            "NCAAB": "basketball_ncaab",
            "EPL": "soccer_epl",
        }

        # Initialize rating systems with current ratings
        self.elo_systems = {}
        self.glicko2_systems = {}
        self._load_rating_systems()

        self.api_calls_made = 0

    def _load_rating_systems(self):
        """Load current Elo and Glicko-2 ratings from CSV files."""
        print("📥 Loading rating systems...")

        # NBA
        try:
            elo_nba = NBAEloRating(k_factor=20, home_advantage=100)
            df = pd.read_csv("/mnt/data2/nhlstats/data/nba_current_elo_ratings.csv")
            for _, row in df.iterrows():
                elo_nba.ratings[row["team"]] = row["rating"]
            self.elo_systems["NBA"] = elo_nba
            print(f"  ✓ NBA Elo: {len(elo_nba.ratings)} teams")
        except Exception as e:
            print(f"  ⚠️ NBA Elo: {e}")

        # NHL
        try:
            elo_nhl = NHLEloRating(k_factor=20, home_advantage=50)  # Tuned from 100
            df = pd.read_csv("/mnt/data2/nhlstats/data/nhl_current_elo_ratings.csv")
            for _, row in df.iterrows():
                elo_nhl.ratings[row["team"]] = row["rating"]
            self.elo_systems["NHL"] = elo_nhl
            print(f"  ✓ NHL Elo: {len(elo_nhl.ratings)} teams (tuned: K=20, HA=50)")
        except Exception as e:
            print(f"  ⚠️ NHL Elo: {e}")

        # NFL
        try:
            elo_nfl = NFLEloRating(k_factor=20, home_advantage=65)
            df = pd.read_csv("/mnt/data2/nhlstats/data/nfl_current_elo_ratings.csv")
            for _, row in df.iterrows():
                elo_nfl.ratings[row["team"]] = row["rating"]
            self.elo_systems["NFL"] = elo_nfl
            print(f"  ✓ NFL Elo: {len(elo_nfl.ratings)} teams")
        except Exception as e:
            print(f"  ⚠️ NFL Elo: {e}")

        # MLB
        try:
            elo_mlb = MLBEloRating(k_factor=20, home_advantage=50)
            df = pd.read_csv("/mnt/data2/nhlstats/data/mlb_current_elo_ratings.csv")
            for _, row in df.iterrows():
                elo_mlb.ratings[row["team"]] = row["rating"]
            self.elo_systems["MLB"] = elo_mlb
            print(f"  ✓ MLB Elo: {len(elo_mlb.ratings)} teams")
        except Exception as e:
            print(f"  ⚠️ MLB Elo: {e}")

        # NCAAB
        try:
            elo_ncaab = NCAABEloRating(k_factor=20, home_advantage=100)
            df = pd.read_csv("/mnt/data2/nhlstats/data/ncaab_current_elo_ratings.csv")
            for _, row in df.iterrows():
                elo_ncaab.ratings[row["team"]] = row["rating"]
            self.elo_systems["NCAAB"] = elo_ncaab
            print(f"  ✓ NCAAB Elo: {len(elo_ncaab.ratings)} teams")
        except Exception as e:
            print(f"  ⚠️ NCAAB Elo: {e}")

        # EPL
        try:
            elo_epl = EPLEloRating(k_factor=20, home_advantage=60)
            df = pd.read_csv("/mnt/data2/nhlstats/data/epl_current_elo_ratings.csv")
            for _, row in df.iterrows():
                elo_epl.ratings[row["team"]] = row["rating"]
            self.elo_systems["EPL"] = elo_epl
            print(f"  ✓ EPL Elo: {len(elo_epl.ratings)} teams")
        except Exception as e:
            print(f"  ⚠️ EPL Elo: {e}")

    def normalize_team_name(self, team: str, sport: str) -> str:
        """Normalize team names to match our database format."""
        # NHL uses abbreviations
        if sport == "NHL":
            nhl_map = {
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
                "Vancouver Canucks": "VAN",
                "Vegas Golden Knights": "VGK",
                "Washington Capitals": "WSH",
                "Winnipeg Jets": "WPG",
                "Utah Hockey Club": "ATL",  # Relocated team
            }
            return nhl_map.get(team, team)

        # NBA uses just team name (no city)
        if sport == "NBA":
            # Extract team name from full name
            nba_map = {
                "Atlanta Hawks": "Hawks",
                "Boston Celtics": "Celtics",
                "Brooklyn Nets": "Nets",
                "Charlotte Hornets": "Hornets",
                "Chicago Bulls": "Bulls",
                "Cleveland Cavaliers": "Cavaliers",
                "Dallas Mavericks": "Mavericks",
                "Denver Nuggets": "Nuggets",
                "Detroit Pistons": "Pistons",
                "Golden State Warriors": "Warriors",
                "Houston Rockets": "Rockets",
                "Indiana Pacers": "Pacers",
                "LA Clippers": "Clippers",
                "Los Angeles Clippers": "Clippers",
                "Los Angeles Lakers": "Lakers",
                "Memphis Grizzlies": "Grizzlies",
                "Miami Heat": "Heat",
                "Milwaukee Bucks": "Bucks",
                "Minnesota Timberwolves": "Timberwolves",
                "New Orleans Pelicans": "Pelicans",
                "New York Knicks": "Knicks",
                "Oklahoma City Thunder": "Thunder",
                "Orlando Magic": "Magic",
                "Philadelphia 76ers": "76ers",
                "Phoenix Suns": "Suns",
                "Portland Trail Blazers": "Trail Blazers",
                "Sacramento Kings": "Kings",
                "San Antonio Spurs": "Spurs",
                "Toronto Raptors": "Raptors",
                "Utah Jazz": "Jazz",
                "Washington Wizards": "Wizards",
            }
            return nba_map.get(team, team)

        # NFL uses full names
        if sport == "NFL":
            nfl_map = {
                "Arizona Cardinals": "Arizona Cardinals",
                "Atlanta Falcons": "Atlanta Falcons",
                "Baltimore Ravens": "Baltimore Ravens",
                "Buffalo Bills": "Buffalo Bills",
                "Carolina Panthers": "Carolina Panthers",
                "Chicago Bears": "Chicago Bears",
                "Cincinnati Bengals": "Cincinnati Bengals",
                "Cleveland Browns": "Cleveland Browns",
                "Dallas Cowboys": "Dallas Cowboys",
                "Denver Broncos": "Denver Broncos",
                "Detroit Lions": "Detroit Lions",
                "Green Bay Packers": "Green Bay Packers",
                "Houston Texans": "Houston Texans",
                "Indianapolis Colts": "Indianapolis Colts",
                "Jacksonville Jaguars": "Jacksonville Jaguars",
                "Kansas City Chiefs": "Kansas City Chiefs",
                "Las Vegas Raiders": "Las Vegas Raiders",
                "Los Angeles Chargers": "Los Angeles Chargers",
                "Los Angeles Rams": "Los Angeles Rams",
                "Miami Dolphins": "Miami Dolphins",
                "Minnesota Vikings": "Minnesota Vikings",
                "New England Patriots": "New England Patriots",
                "New Orleans Saints": "New Orleans Saints",
                "New York Giants": "New York Giants",
                "New York Jets": "New York Jets",
                "Philadelphia Eagles": "Philadelphia Eagles",
                "Pittsburgh Steelers": "Pittsburgh Steelers",
                "San Francisco 49ers": "San Francisco 49ers",
                "Seattle Seahawks": "Seattle Seahawks",
                "Tampa Bay Buccaneers": "Tampa Bay Buccaneers",
                "Tennessee Titans": "Tennessee Titans",
                "Washington Commanders": "Washington Commanders",
            }
            return nfl_map.get(team, team)

        # MLB uses team names or abbreviations
        if sport == "MLB":
            # Check database format
            mlb_map = {
                "Arizona Diamondbacks": "Diamondbacks",
                "Atlanta Braves": "Braves",
                "Baltimore Orioles": "Orioles",
                "Boston Red Sox": "Red Sox",
                "Chicago Cubs": "Cubs",
                "Chicago White Sox": "White Sox",
                "Cincinnati Reds": "Reds",
                "Cleveland Guardians": "Guardians",
                "Colorado Rockies": "Rockies",
                "Detroit Tigers": "Tigers",
                "Houston Astros": "Astros",
                "Kansas City Royals": "Royals",
                "Los Angeles Angels": "Angels",
                "Los Angeles Dodgers": "Dodgers",
                "Miami Marlins": "Marlins",
                "Milwaukee Brewers": "Brewers",
                "Minnesota Twins": "Twins",
                "New York Mets": "Mets",
                "New York Yankees": "Yankees",
                "Oakland Athletics": "Athletics",
                "Philadelphia Phillies": "Phillies",
                "Pittsburgh Pirates": "Pirates",
                "San Diego Padres": "Padres",
                "San Francisco Giants": "Giants",
                "Seattle Mariners": "Mariners",
                "St. Louis Cardinals": "Cardinals",
                "Tampa Bay Rays": "Rays",
                "Texas Rangers": "Rangers",
                "Toronto Blue Jays": "Blue Jays",
                "Washington Nationals": "Nationals",
            }
            return mlb_map.get(team, team)

        # EPL uses full club names
        if sport == "EPL":
            return team

        # NCAAB uses school names - complex mapping needed
        if sport == "NCAAB":
            # Load mapping if exists
            import json
            from pathlib import Path

            mapping_file = Path("/mnt/data2/nhlstats/data/ncaab_team_mapping.json")
            if mapping_file.exists():
                with open(mapping_file, "r") as f:
                    ncaab_map = json.load(f)
                if team in ncaab_map:
                    return ncaab_map[team]

            # Fallback: try common patterns
            # Replace spaces with underscores
            normalized = team.replace(" ", "_")
            # Handle State/St
            normalized = normalized.replace(" State", "_St")
            normalized = normalized.replace("St. ", "St_")

            return normalized

        return team

    def fetch_scores(self, sport: str, days_ago: int = 3) -> List[Dict]:
        """Fetch completed games with scores from The Odds API."""
        sport_key = self.sport_keys.get(sport)
        if not sport_key:
            return []

        # Calculate date range
        end_date = datetime.now()
        end_date - timedelta(days=days_ago)

        url = f"{self.base_url}/{sport_key}/scores"
        params = {"apiKey": self.api_key, "daysFrom": days_ago, "dateFormat": "iso"}

        print(f"\n📡 Fetching {sport} scores (last {days_ago} days)...")
        response = requests.get(url, params=params)
        self.api_calls_made += 1

        if response.status_code != 200:
            print(f"  ❌ Error: {response.status_code}")
            return []

        data = response.json()
        completed_games = [g for g in data if g.get("completed", False)]
        print(f"  ✓ Found {len(completed_games)} completed games")

        return completed_games

    def analyze_game(self, game: Dict, sport: str) -> Optional[Dict]:
        """Analyze a single game and return prediction vs actual."""
        try:
            home_team_name = game["home_team"]
            away_team_name = game["away_team"]

            # Normalize team names
            home_team = self.normalize_team_name(home_team_name, sport)
            away_team = self.normalize_team_name(away_team_name, sport)

            # Get scores
            scores = game.get("scores", [])
            if len(scores) < 2:
                return None

            home_score = next(
                (s["score"] for s in scores if s["name"] == home_team_name), None
            )
            away_score = next(
                (s["score"] for s in scores if s["name"] == away_team_name), None
            )

            if home_score is None or away_score is None:
                return None

            home_won = int(home_score) > int(away_score)
            is_draw = int(home_score) == int(away_score)

            # Get Elo prediction
            elo_prob = None
            if sport in self.elo_systems:
                elo_system = self.elo_systems[sport]
                if home_team in elo_system.ratings and away_team in elo_system.ratings:
                    # EPL uses 3-way predictions
                    if sport == "EPL" and hasattr(elo_system, "predict_3way"):
                        probs = elo_system.predict_3way(home_team, away_team)
                        elo_prob = probs["home"]  # Store home win prob
                        # For EPL, prediction is correct if we pick highest probability outcome
                        max_outcome = max(probs, key=probs.get)
                        if is_draw:
                            elo_correct_3way = max_outcome == "draw"
                        elif home_won:
                            elo_correct_3way = max_outcome == "home"
                        else:
                            elo_correct_3way = max_outcome == "away"
                    else:
                        elo_prob = elo_system.predict(home_team, away_team)
                        elo_correct_3way = None

            # Glicko-2 disabled for now (needs proper initialization)
            glicko2_prob = None

            if elo_prob is None and glicko2_prob is None:
                return None

            result = {
                "sport": sport,
                "date": game.get("commence_time", ""),
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "home_won": home_won,
                "is_draw": is_draw,
                "elo_prob": elo_prob,
                "glicko2_prob": glicko2_prob,
                "elo_correct": (elo_prob > 0.5) == home_won
                if elo_prob and not is_draw
                else None,
                "glicko2_correct": (glicko2_prob > 0.5) == home_won
                if glicko2_prob
                else None,
            }

            # Add 3-way correctness for EPL
            if sport == "EPL" and elo_correct_3way is not None:
                result["elo_correct_3way"] = elo_correct_3way

            return result

        except Exception as e:
            print(f"  ⚠️ Error analyzing game: {e}")
            return None

    def run_backtest(self, sports: List[str], days: int = 3):
        """Run backtest across multiple sports."""
        print(f"\n{'=' * 80}")
        print(f"🎯 BETTING BACKTEST - Last {days} Days")
        print(f"{'=' * 80}")

        all_results = []

        for sport in sports:
            games = self.fetch_scores(sport, days)

            for game in games:
                result = self.analyze_game(game, sport)
                if result:
                    all_results.append(result)

        if not all_results:
            print("\n❌ No results to analyze")
            return

        # Convert to DataFrame for analysis
        df = pd.DataFrame(all_results)

        # Overall statistics
        print(f"\n{'=' * 80}")
        print("📊 OVERALL PERFORMANCE")
        print(f"{'=' * 80}")
        print(f"Total Games Analyzed: {len(df)}")
        print(f"API Calls Used: {self.api_calls_made}/500")

        # Elo performance
        elo_df = df[df["elo_prob"].notna()]
        if len(elo_df) > 0:
            elo_accuracy = elo_df["elo_correct"].mean()
            elo_brier = (
                (elo_df["elo_prob"] - elo_df["home_won"].astype(float)) ** 2
            ).mean()
            print("\n🎲 ELO RATING SYSTEM:")
            print(f"  Games Predicted: {len(elo_df)}")
            print(f"  Accuracy: {elo_accuracy:.1%}")
            print(f"  Brier Score: {elo_brier:.4f}")

            # High confidence bets (>70%)
            high_conf = elo_df[elo_df["elo_prob"] > 0.70]
            if len(high_conf) > 0:
                high_accuracy = high_conf["elo_correct"].mean()
                print(
                    f"  High Confidence (>70%): {len(high_conf)} games, {high_accuracy:.1%} accuracy"
                )

        # Glicko-2 performance
        glicko2_df = df[df["glicko2_prob"].notna()]
        if len(glicko2_df) > 0:
            glicko2_accuracy = glicko2_df["glicko2_correct"].mean()
            glicko2_brier = (
                (glicko2_df["glicko2_prob"] - glicko2_df["home_won"].astype(float)) ** 2
            ).mean()
            print("\n🎯 GLICKO-2 RATING SYSTEM:")
            print(f"  Games Predicted: {len(glicko2_df)}")
            print(f"  Accuracy: {glicko2_accuracy:.1%}")
            print(f"  Brier Score: {glicko2_brier:.4f}")

            # High confidence bets
            high_conf = glicko2_df[glicko2_df["glicko2_prob"] > 0.70]
            if len(high_conf) > 0:
                high_accuracy = high_conf["glicko2_correct"].mean()
                print(
                    f"  High Confidence (>70%): {len(high_conf)} games, {high_accuracy:.1%} accuracy"
                )

        # Per-sport breakdown
        print(f"\n{'=' * 80}")
        print("📈 PER-SPORT BREAKDOWN")
        print(f"{'=' * 80}")

        for sport in df["sport"].unique():
            sport_df = df[df["sport"] == sport]
            print(f"\n{sport}:")
            print(f"  Games: {len(sport_df)}")

            sport_elo = sport_df[sport_df["elo_prob"].notna()]
            if len(sport_elo) > 0:
                print(f"  Elo Accuracy: {sport_elo['elo_correct'].mean():.1%}")

            sport_glicko2 = sport_df[sport_df["glicko2_prob"].notna()]
            if len(sport_glicko2) > 0:
                print(
                    f"  Glicko-2 Accuracy: {sport_glicko2['glicko2_correct'].mean():.1%}"
                )

        # Show some examples
        print(f"\n{'=' * 80}")
        print("🎮 RECENT PREDICTIONS (Sample)")
        print(f"{'=' * 80}")

        sample_df = df.head(10)
        for _, row in sample_df.iterrows():
            winner = row["home_team"] if row["home_won"] else row["away_team"]
            elo_str = (
                f"Elo:{row['elo_prob']:.1%}" if pd.notna(row["elo_prob"]) else "Elo:N/A"
            )
            g2_str = (
                f"G2:{row['glicko2_prob']:.1%}"
                if pd.notna(row["glicko2_prob"])
                else "G2:N/A"
            )

            elo_mark = (
                "✓"
                if row["elo_correct"]
                else "✗"
                if pd.notna(row["elo_correct"])
                else "-"
            )
            g2_mark = (
                "✓"
                if row["glicko2_correct"]
                else "✗"
                if pd.notna(row["glicko2_correct"])
                else "-"
            )

            print(
                f"{row['sport']:6} | {row['home_team'][:15]:15} vs {row['away_team'][:15]:15} | "
                f"Winner: {winner[:15]:15} | {elo_str} {elo_mark} | {g2_str} {g2_mark}"
            )

        # Save results
        output_file = f"/mnt/data2/nhlstats/data/backtest_results_{datetime.now().strftime('%Y%m%d')}.csv"
        df.to_csv(output_file, index=False)
        print(f"\n💾 Results saved to: {output_file}")

        print(f"\n{'=' * 80}")
        print("✅ BACKTEST COMPLETE")
        print(f"{'=' * 80}\n")


def main():
    api_key = os.environ.get("ODDS_API_KEY")
    if not api_key:
        print("❌ Error: ODDS_API_KEY environment variable not set")
        return

    backtest = BettingBacktest(api_key)

    # Analyze NCAAB specifically (203 games in 3 days)
    print("\n⚠️  WARNING: NCAAB has 203 games - this will use significant API calls")
    print("📊 Testing NCAAB only to conserve API budget\n")

    active_sports = ["NCAAB"]

    backtest.run_backtest(active_sports, days=3)


if __name__ == "__main__":
    main()
