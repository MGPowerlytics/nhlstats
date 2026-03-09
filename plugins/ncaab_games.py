import pandas as pd
import requests
from plugins.base_games import MasseyGamesFetcher


class NCAABGames(MasseyGamesFetcher):
    """Download and manage NCAAB game data from Massey Ratings."""

    def __init__(self, data_dir="data/ncaab"):
        # NCAA D1 Men's Basketball sub-ID usually 11590
        super().__init__(sport="ncaab", sub_id="11590", data_dir=data_dir)

    def load_games(self):
        """Load and merge all games with team names."""
        self.download_games()

        all_games = []

        for season in self.seasons:
            team_map, games_df = self._load_raw_data(season)
            if team_map is None or games_df is None:
                continue

            try:
                if games_df.shape[1] < 8:
                    continue

                for _, row in games_df.iterrows():
                    game = self._parse_game_row(row, team_map)
                    if game:
                        game["season"] = season
                        all_games.append(game)

            except Exception as e:
                print(f"Error loading NCAAB season {season}: {e}")

        return pd.DataFrame(all_games)


if __name__ == "__main__":
    ncaab = NCAABGames()
    df = ncaab.load_games()
    print(f"Loaded {len(df)} NCAAB games.")
    print(df.tail())
