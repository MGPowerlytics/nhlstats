"""
Download and manage Women's NCAA Basketball (D1 only) game data from Massey Ratings.

This module provides functionality to download historical game data for Women's NCAA Basketball
Division I teams from the Massey Ratings service.
"""

import pandas as pd
from typing import List
from plugins.base_games import MasseyGamesFetcher

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


class WNCAABGames(MasseyGamesFetcher):
    """Download and manage Women's NCAAB game data from Massey Ratings."""

    def __init__(self, data_dir="data/wncaab"):
        # Women's NCAA D1 sub-ID is usually 11591
        super().__init__(sport="wncaab", sub_id="11591", data_dir=data_dir)

    def _is_d1_matchup(self, game: dict) -> bool:
        """Checks if a game is between two D1 programs."""
        return game["home_team"] in D1_PROGRAMS and game["away_team"] in D1_PROGRAMS

    def _load_season_games(self, season: str) -> List[dict]:
        """Loads and parses all games for a specific season."""
        team_map, games_df = self._load_raw_data(season)
        if team_map is None or games_df is None:
            return []

        season_games = []
        try:
            if games_df.shape[1] < 8:
                return []

            for _, row in games_df.iterrows():
                game = self._parse_game_row(row, team_map)
                if game and self._is_d1_matchup(game):
                    game["season"] = season
                    season_games.append(game)

        except Exception as e:
            print(f"Error loading WNCAAB season {season}: {e}")

        return season_games

    def load_games(self):
        """Load and merge all games with team names."""
        self.download_games()

        all_games = []
        for season in self.seasons:
            all_games.extend(self._load_season_games(season))

        df = pd.DataFrame(all_games)
        if len(df) > 0:
            print(f"✓ Loaded {len(df):,} D1 vs D1 games")
        return df


if __name__ == "__main__":
    wncaab = WNCAABGames()
    df = wncaab.load_games()
    print(f"Loaded {len(df)} WNCAAB games.")
    print(df.tail())
