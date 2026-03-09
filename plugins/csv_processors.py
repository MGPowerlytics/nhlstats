"""
CSV Processors for different sports.

Extracted from NHLDatabaseLoader to reduce class size and improve maintainability.
"""

import pandas as pd
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from plugins.db_manager import DBManager


class BaseCSVProcessor(ABC):
    """Base class for CSV processors."""

    def __init__(self, db_manager: DBManager):
        """Initialize CSV processor with database manager.

        Args:
            db_manager: Database manager for executing SQL queries
        """
        self.db = db_manager

    @abstractmethod
    def process_row(self, row: pd.Series, **kwargs) -> None:
        """Process a single CSV row and upsert into database.

        Args:
            row: Pandas Series representing a single row of CSV data
            **kwargs: Additional sport-specific parameters
        """
        pass

    @abstractmethod
    def get_table_name(self) -> str:
        """Get the database table name for this sport.

        Returns:
            Table name as string
        """
        pass


class NCAABCSVProcessor(BaseCSVProcessor):
    """CSV processor for NCAAB games."""

    def process_row(self, row: pd.Series, **kwargs) -> None:
        """Process a single NCAAB game row and upsert into database.

        Args:
            row: Pandas Series with NCAAB game data
            **kwargs: Not used for NCAAB
        """
        try:
            params = self._extract_ncaab_game_data(row)
            self.db.execute(
                """
                INSERT INTO ncaab_games (
                    game_id, game_date, season, home_team, away_team,
                    home_score, away_score, is_neutral
                ) VALUES (:game_id, :game_date, :season, :home_team, :away_team, :home_score, :away_score, :is_neutral)
                ON CONFLICT (game_id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score
            """,
                params,
            )
        except Exception:
            # Silently skip rows with errors (matching original behavior)
            pass

    def _extract_ncaab_game_data(self, row: pd.Series) -> Dict[str, Any]:
        """Extract and transform NCAAB game data from CSV row.

        Args:
            row: Pandas Series with NCAAB game data

        Returns:
            Dictionary of parameters for database insertion
        """
        game_date = row["date"].strftime("%Y-%m-%d")
        h_slug = "".join(x for x in str(row["home_team"]) if x.isalnum())
        a_slug = "".join(x for x in str(row["away_team"]) if x.isalnum())
        game_id = f"NCAAB_{game_date}_{h_slug}_{a_slug}"

        return {
            "game_id": game_id,
            "game_date": game_date,
            "season": int(row["season"]),
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "home_score": int(row["home_score"]),
            "away_score": int(row["away_score"]),
            "is_neutral": bool(row["neutral"]),
        }

    def get_table_name(self) -> str:
        """Get the database table name for NCAAB games.

        Returns:
            Table name "ncaab_games"
        """
        return "ncaab_games"


class TennisCSVProcessor(BaseCSVProcessor):
    """CSV processor for Tennis games."""

    def process_row(self, row: pd.Series, **kwargs) -> None:
        """Process a single Tennis game row and upsert into database.

        Args:
            row: Pandas Series with Tennis game data
            **kwargs: Must contain 'tour' and 'season' parameters
        """
        tour = kwargs.get("tour", "")
        season = kwargs.get("season", "")

        # Check for required columns (matching original behavior)
        if (
            pd.isna(row.get("Date"))
            or pd.isna(row.get("Winner"))
            or pd.isna(row.get("Loser"))
        ):
            return

        try:
            params = self._extract_tennis_game_data(row, tour, season)
            self.db.execute(
                """
                INSERT INTO tennis_games (
                    game_id, game_date, season, tour, tournament, surface, winner, loser, score
                ) VALUES (:game_id, :game_date, :season, :tour, :tournament, :surface, :winner, :loser, :score)
                ON CONFLICT (game_id) DO NOTHING
            """,
                params,
            )
        except Exception:
            # Silently skip rows with errors (matching original behavior)
            pass

    def _extract_tennis_game_data(
        self, row: pd.Series, tour: str, season: str
    ) -> Dict[str, Any]:
        """Extract and transform Tennis game data from CSV row.

        Args:
            row: Pandas Series with Tennis game data
            tour: Tennis tour (e.g., "ATP", "WTA")
            season: Season year

        Returns:
            Dictionary of parameters for database insertion
        """
        game_date = row["Date"].strftime("%Y-%m-%d")
        w_slug = "".join(x for x in str(row["Winner"]) if x.isalnum())
        l_slug = "".join(x for x in str(row["Loser"]) if x.isalnum())
        game_id = f"TENNIS_{tour}_{game_date}_{w_slug}_{l_slug}"

        return {
            "game_id": game_id,
            "game_date": game_date,
            "season": str(season),
            "tour": tour,
            "tournament": str(row.get("Tournament", "")),
            "surface": str(row.get("Surface", "Unknown")),
            "winner": str(row["Winner"]),
            "loser": str(row["Loser"]),
            "score": str(row.get("Score", "")),
        }

    def get_table_name(self) -> str:
        """Get the database table name for Tennis games.

        Returns:
            Table name "tennis_games"
        """
        return "tennis_games"


class EPLCSVProcessor(BaseCSVProcessor):
    """CSV processor for EPL (English Premier League) games."""

    def process_row(self, row: pd.Series, **kwargs) -> None:
        """Process a single EPL game row and upsert into database.

        Args:
            row: Pandas Series with EPL game data
            **kwargs: Must contain 'season_code' parameter
        """
        season_code = kwargs.get("season_code", "")

        # Check for required column (matching original behavior)
        if pd.isna(row.get("FTHG")):
            return

        try:
            params = self._extract_epl_game_data(row, season_code)
            self.db.execute(
                """
                INSERT INTO epl_games (
                    game_id, game_date, season, home_team, away_team, home_score, away_score, result
                ) VALUES (:game_id, :game_date, :season, :home_team, :away_team, :home_score, :away_score, :result)
                ON CONFLICT (game_id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    result = EXCLUDED.result
            """,
                params,
            )
        except Exception:
            # Silently skip rows with errors (matching original behavior)
            pass

    def _extract_epl_game_data(
        self, row: pd.Series, season_code: str
    ) -> Dict[str, Any]:
        """Extract and transform EPL game data from CSV row.

        Args:
            row: Pandas Series with EPL game data
            season_code: Season code (e.g., "2023-2024")

        Returns:
            Dictionary of parameters for database insertion
        """
        game_date = row["Date"].strftime("%Y-%m-%d")
        home_team = row["HomeTeam"]
        away_team = row["AwayTeam"]
        game_id = (
            f"EPL_{game_date}_{home_team.replace(' ', '')}_{away_team.replace(' ', '')}"
        )

        return {
            "game_id": game_id,
            "game_date": game_date,
            "season": season_code,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": int(row["FTHG"]),
            "away_score": int(row["FTAG"]),
            "result": row["FTR"],
        }

    def get_table_name(self) -> str:
        """Get the database table name for EPL games.

        Returns:
            Table name "epl_games"
        """
        return "epl_games"


# Factory function to get appropriate CSV processor
def get_csv_processor(sport: str, db_manager: DBManager) -> Optional[BaseCSVProcessor]:
    """Get CSV processor for a specific sport.

    Args:
        sport: Sport name (e.g., "ncaab", "tennis", "epl")
        db_manager: Database manager for executing SQL queries

    Returns:
        CSV processor instance or None if sport not supported
    """
    processors = {
        "ncaab": NCAABCSVProcessor,
        "tennis": TennisCSVProcessor,
        "epl": EPLCSVProcessor,
    }

    processor_class = processors.get(sport.lower())
    if processor_class:
        return processor_class(db_manager)
    return None
