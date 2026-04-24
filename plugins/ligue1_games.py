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
            # Canonical: PSG
            "Paris Saint-Germain": "PSG",
            "Paris Saint Germain": "PSG",
            "Paris SG": "PSG",
            "PSG": "PSG",

            # Canonical: Marseille
            "Olympique de Marseille": "Marseille",
            "Olympique Marseille": "Marseille",
            "Marseille": "Marseille",
            "MAR": "Marseille",

            # Canonical: Lyon
            "Olympique Lyonnais": "Lyon",
            "Lyon": "Lyon",
            "LYO": "Lyon",

            # Canonical: Monaco
            "AS Monaco FC": "Monaco",
            "AS Monaco": "Monaco",
            "Monaco": "Monaco",
            "ASM": "Monaco",

            # Canonical: Lille
            "Lille OSC": "Lille",
            "Lille": "Lille",
            "LIL": "Lille",

            # Canonical: Nice
            "OGC Nice": "Nice",
            "Nice": "Nice",
            "NIC": "Nice",

            # Canonical: Rennes
            "Stade Rennais FC": "Rennes",
            "Stade Rennais": "Rennes",
            "Rennes": "Rennes",
            "REN": "Rennes",

            # Canonical: Lens
            "RC Lens": "Lens",
            "Lens": "Lens",
            "RCL": "Lens",

            # Canonical: Reims
            "Stade de Reims": "Reims",
            "Reims": "Reims",
            "REI": "Reims",

            # Canonical: Montpellier
            "Montpellier HSC": "Montpellier",
            "Montpellier": "Montpellier",
            "MPL": "Montpellier",

            # Canonical: Nantes
            "FC Nantes": "Nantes",
            "Nantes": "Nantes",
            "FCN": "Nantes",

            # Canonical: Strasbourg
            "RC Strasbourg": "Strasbourg",
            "Strasbourg": "Strasbourg",
            "RCS": "Strasbourg",

            # Canonical: Toulouse
            "Toulouse FC": "Toulouse",
            "Toulouse": "Toulouse",
            "TFC": "Toulouse",

            # Canonical: Lorient
            "FC Lorient": "Lorient",
            "Lorient": "Lorient",
            "FCL": "Lorient",

            # Canonical: Le Havre
            "Le Havre AC": "Le Havre",
            "Le Havre": "Le Havre",
            "HAC": "Le Havre",

            # Canonical: Metz
            "FC Metz": "Metz",
            "Metz": "Metz",
            "FCM": "Metz",

            # Canonical: Angers
            "Angers SCO": "Angers",
            "Angers": "Angers",
            "ANG": "Angers",

            # Canonical: Brest
            "Brest": "Brest",
            "Stade Brestois": "Brest",
            "STB": "Brest",

            # Canonical: Auxerre
            "AJ Auxerre": "Auxerre",
            "Auxerre": "Auxerre",
            "AUX": "Auxerre",

            # Canonical: Saint-Etienne
            "St Etienne": "Saint-Etienne",
            "Saint-Etienne": "Saint-Etienne",
            "STE": "Saint-Etienne",

            # Canonical: Troyes
            "Troyes": "Troyes",
            "ESTAC Troyes": "Troyes",
            "TRO": "Troyes",

            # Canonical: Clermont
            "Clermont": "Clermont",
            "Clermont Foot": "Clermont",
            "CLE": "Clermont",

            # Canonical: Ajaccio
            "Ajaccio": "Ajaccio",
            "AC Ajaccio": "Ajaccio",
            "AJA": "Ajaccio",

            # Canonical: Paris FC
            "Paris FC": "Paris FC",
            "PAR": "Paris FC",

            # Canonical: Bordeaux
            "Bordeaux": "Bordeaux",
            "FC Bordeaux": "Bordeaux",
            "BOR": "Bordeaux",
        }


if __name__ == "__main__":
    ligue1 = Ligue1Games()
    ligue1.download_games()
    df = ligue1.load_games()
    print(f"Loaded {len(df)} finished games.")
    print(df.tail())
