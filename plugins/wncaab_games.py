"""
Download and manage Women's NCAA Basketball (D1 only) game data from Massey Ratings.

This module provides functionality to download historical game data for Women's NCAA Basketball
Division I teams from the Massey Ratings service.
"""

import pandas as pd
from pathlib import Path
import requests
import time

# D1 Women's Basketball Programs
D1_PROGRAMS = {
    "Duke",
    "Connecticut",
    "South_Carolina",
    "Stanford",
    "LSU",
    "Iowa",
    "Virginia_Tech",
    "Notre_Dame",
    "Louisville",
    "Tennessee",
    "UCLA",
    "USC",
    "Baylor",
    "Texas",
    "Maryland",
    "Indiana",
    "Ohio_St",
    "Michigan",
    "Nebraska",
    "Georgia",
    "Alabama",
    "Kentucky",
    "Florida",
    "Mississippi_St",
    "Arkansas",
    "Auburn",
    "Vanderbilt",
    "Missouri",
    "North_Carolina",
    "NC_State",
    "Florida_St",
    "Miami_FL",
    "Syracuse",
    "Boston_Col",
    "Wake_Forest",
    "Clemson",
    "Pittsburgh",
    "Georgia_Tech",
    "Villanova",
    "Creighton",
    "Marquette",
    "Butler",
    "Xavier",
    "Providence",
    "Seton_Hall",
    "DePaul",
    "St_John's",
    "Gonzaga",
    "BYU",
    "Washington",
    "Oregon",
    "Colorado",
    "Utah",
    "Arizona",
    "Arizona_St",
    "Oregon_St",
    "Washington_St",
    "Kansas",
    "Kansas_St",
    "Iowa_St",
    "Oklahoma",
    "Oklahoma_St",
    "Texas_Tech",
    "TCU",
    "West_Virginia",
    "Cincinnati",
    "Houston",
    "UCF",
    "Memphis",
    "Purdue",
    "Penn_St",
    "Northwestern",
    "Rutgers",
    "Wisconsin",
    "Minnesota",
    "Illinois",
    "Michigan_St",
    "Ole_Miss",
    "Texas_A&M",
    "Virginia",
    "California",
    "NC_Central",
    "Norfolk_St",
    "Howard",
    "Delaware_St",
    "Morgan_St",
    "Coppin_St",
    "UMES",
    "South_Carolina_St",
    "Bethune-Cookman",
    "FAMU",
    "Jackson_St",
    "Alabama_A&M",
    "Alabama_St",
    "Alcorn",
    "Grambling",
    "Prairie_View",
    "Southern",
    "Texas_Southern",
    "NC_A&T",
    "Hampton",
    "App_State",
    "Coastal_Carolina",
    "Georgia_St",
    "Georgia_Southern",
    "Old_Dominion",
    "JMU",
    "VCU",
    "George_Mason",
    "Richmond",
    "Davidson",
    "Dayton",
    "Fordham",
    "George_Washington",
    "La_Salle",
    "UMass",
    "Rhode_Island",
    "St_Bonaventure",
    "Saint_Louis",
    "Duquesne",
    "St_Joseph's",
    "Temple",
    "Charlotte",
    "UAB",
    "Rice",
    "Tulane",
    "Tulsa",
    "UTEP",
    "UTSA",
    "North_Texas",
    "East_Carolina",
    "FAU",
    "FIU",
    "Middle_Tennessee",
    "WKU",
    "Louisiana_Tech",
    "NMSU",
    "Liberty",
    "Jacksonville_St",
    "Sam_Houston",
    "Kennesaw",
    "Bellarmine",
    "Queens_NC",
    "Saint_Mary's",
    "San_Francisco",
    "Santa_Clara",
    "Pacific",
    "Loyola_Marymount",
    "Pepperdine",
    "Portland",
    "San_Diego",
    "Boise_St",
    "Colorado_St",
    "Fresno_St",
    "Nevada",
    "UNLV",
    "New_Mexico",
    "San_Diego_St",
    "San_Jose_St",
    "Wyoming",
    "Air_Force",
    "Utah_St",
}


class WNCAABGames:
    """Download and manage Women's NCAAB game data from Massey Ratings."""

    def __init__(self, data_dir="data/wncaab"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Seasons to fetch (e.g., 2022 corresponds to 2021-22 season)
        self.seasons = [2021, 2022, 2023, 2024, 2025, 2026]
        # Women's NCAA D1 sub-ID is usually 11591
        self.sub_id = "11591"

    def download_games(self):
        """Download historical and current WNCAAB data using numeric format + team mapping."""
        success = True

        for season in self.seasons:
            # 1. Download Team Mapping (Format 2)
            teams_url = f"https://masseyratings.com/scores.php?s=cb{season}&sub={self.sub_id}&all=1&mode=3&format=2"
            teams_file = self.data_dir / f"teams_{season}.csv"

            # Re-download if current season or missing
            if not teams_file.exists() or season == 2026:
                print(f"📥 Downloading WNCAAB teams ({season})...")
                try:
                    resp = requests.get(teams_url)
                    resp.raise_for_status()
                    with open(teams_file, "wb") as f:
                        f.write(resp.content)
                    time.sleep(1)
                except Exception as e:
                    print(f"✗ Failed to download teams for {season}: {e}")
                    success = False

            # 2. Download Games (Format 1 - Numeric)
            games_url = f"https://masseyratings.com/scores.php?s=cb{season}&sub={self.sub_id}&all=1&mode=3&format=1"
            games_file = self.data_dir / f"games_{season}.csv"

            if not games_file.exists() or season == 2026:
                print(f"📥 Downloading WNCAAB games ({season})...")
                try:
                    resp = requests.get(games_url)
                    resp.raise_for_status()
                    with open(games_file, "wb") as f:
                        f.write(resp.content)
                    print(f"✓ Saved WNCAAB data for {season}")
                    time.sleep(1)
                except Exception as e:
                    print(f"✗ Failed to download games for {season}: {e}")
                    success = False

        return success

    def load_games(self):
        """Load and merge all games with team names."""
        self.download_games()

        all_games = []

        for season in self.seasons:
            teams_file = self.data_dir / f"teams_{season}.csv"
            games_file = self.data_dir / f"games_{season}.csv"

            if not teams_file.exists() or not games_file.exists():
                continue

            try:
                # Load Teams
                teams_df = pd.read_csv(
                    teams_file, header=None, names=["team_id", "team_name"]
                )
                teams_df["team_name"] = teams_df["team_name"].str.strip()
                team_map = dict(zip(teams_df["team_id"], teams_df["team_name"]))

                # Load Games (Format 1)
                try:
                    games_df = pd.read_csv(games_file, header=None)
                except pd.errors.EmptyDataError:
                    continue

                if games_df.shape[1] < 8:
                    continue

                # Iterate rows
                for _, row in games_df.iterrows():
                    try:
                        date_int = row[1]
                        t1_id = row[2]
                        loc1 = row[3]  # 1=Home, -1=Away, 0=Neutral
                        s1 = row[4]
                        t2_id = row[5]
                        row[6]
                        s2 = row[7]

                        t1_name = team_map.get(t1_id, f"ID_{t1_id}")
                        t2_name = team_map.get(t2_id, f"ID_{t2_id}")

                        # Normalize to Home vs Away
                        if loc1 == 1:
                            home_team, away_team = t1_name, t2_name
                            home_score, away_score = s1, s2
                            neutral = False
                        elif loc1 == -1:  # T1 is Away
                            home_team, away_team = t2_name, t1_name
                            home_score, away_score = s2, s1
                            neutral = False
                        else:
                            # Neutral
                            home_team, away_team = t1_name, t2_name
                            home_score, away_score = s1, s2
                            neutral = True

                        # Parse date YYYYMMDD
                        date_str = str(date_int).strip()
                        game_date = pd.to_datetime(date_str, format="%Y%m%d")

                        # Only include D1 vs D1 games
                        if home_team in D1_PROGRAMS and away_team in D1_PROGRAMS:
                            all_games.append(
                                {
                                    "date": game_date,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "home_score": home_score,
                                    "away_score": away_score,
                                    "neutral": neutral,
                                    "season": season,
                                }
                            )
                    except Exception:
                        continue

            except Exception as e:
                print(f"Error loading WNCAAB season {season}: {e}")

        df = pd.DataFrame(all_games)
        if len(df) > 0:
            print(f"✓ Loaded {len(df):,} D1 vs D1 games")
        return df


if __name__ == "__main__":
    wncaab = WNCAABGames()
    df = wncaab.load_games()
    print(f"Loaded {len(df)} WNCAAB games.")
    print(df.tail())
