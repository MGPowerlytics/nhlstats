"""
Ligue 1 (French Soccer) game data downloader.

Downloads historical match results from football-data.co.uk (free CSV source).
"""

import pandas as pd
from pathlib import Path
import requests
from plugins.football_data_co_uk import FootballDataCoUkGames


class Ligue1Games(FootballDataCoUkGames):
    """Download and manage Ligue 1 game data."""

    def __init__(self, data_dir="data/ligue1"):
        super().__init__(sport_id="F1", data_dir=data_dir)

    def get_team_mapping(self):
        """Map between different team name formats used in CSV vs Kalshi.

        Returns:
            Dictionary mapping various name formats to canonical names
        """
        return {
            "Paris Saint-Germain": "PSG",
            "Paris Saint Germain": "PSG",
            "Olympique de Marseille": "Marseille",
            "Olympique Marseille": "Marseille",
            "Olympique Lyonnais": "Lyon",
            "AS Monaco FC": "Monaco",
            "AS Monaco": "Monaco",
            "Lille OSC": "Lille",
            "OGC Nice": "Nice",
            "Stade Rennais FC": "Rennes",
            "Stade Rennais": "Rennes",
            "RC Lens": "Lens",
            "Stade de Reims": "Reims",
            "Montpellier HSC": "Montpellier",
            "FC Nantes": "Nantes",
            "AJ Auxerre": "Auxerre",
            "Le Havre AC": "Le Havre",
            "FC Lorient": "Lorient",
            "Toulouse FC": "Toulouse",
            "Angers SCO": "Angers",
            "Brest": "Brest",
            "RC Strasbourg": "Strasbourg",
        }


if __name__ == "__main__":
    ligue1 = Ligue1Games()
    ligue1.download_games()
    df = ligue1.load_games()
    print(f"Loaded {len(df)} finished games.")
    print(df.tail())
