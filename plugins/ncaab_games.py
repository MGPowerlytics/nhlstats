import pandas as pd
from pathlib import Path
import requests
import time


class NCAABGames:
    """Download and manage NCAAB game data from Massey Ratings."""

    def __init__(self, data_dir="data/ncaab"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Seasons to fetch (e.g., 2022 corresponds to 2021-22 season)
        self.seasons = [2021, 2022, 2023, 2024, 2025, 2026]
        # NCAA D1 sub-ID usually 11590.
        self.sub_id = "11590"

    def download_games(self):
        """Download historical and current NCAAB data using numeric format + team mapping."""
        success = True

        for season in self.seasons:
            # 1. Download Team Mapping (Format 2)
            # Use 'cb{season}' style for archive, 'cb' for current if season==2026?
            # Actually cb2026 works usually.

            teams_url = f"https://masseyratings.com/scores.php?s=cb{season}&sub={self.sub_id}&all=1&mode=3&format=2"
            teams_file = self.data_dir / f"teams_{season}.csv"

            # Re-download if current season or missing
            if not teams_file.exists() or season == 2026:
                print(f"📥 Downloading NCAAB teams ({season})...")
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
                print(f"📥 Downloading NCAAB games ({season})...")
                try:
                    resp = requests.get(games_url)
                    resp.raise_for_status()
                    with open(games_file, "wb") as f:
                        f.write(resp.content)
                    print(f"✓ Saved NCAAB data for {season}")
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
                # Format: "   1, Abilene_Chr"
                teams_df = pd.read_csv(
                    teams_file, header=None, names=["team_id", "team_name"]
                )
                teams_df["team_name"] = teams_df["team_name"].str.strip()
                team_map = dict(zip(teams_df["team_id"], teams_df["team_name"]))

                # Load Games (Format 1)
                # Cols: Time, Date, Team1, @1, Score1, Team2, @2, Score2
                # Use engine='python' for robust parsing if delimiter varies, but CSV is standard
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
                print(f"Error loading NCAAB season {season}: {e}")

        return pd.DataFrame(all_games)


if __name__ == "__main__":
    ncaab = NCAABGames()
    df = ncaab.load_games()
    print(f"Loaded {len(df)} NCAAB games.")
    print(df.tail())
