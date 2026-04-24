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


class SoccerCSVProcessor(BaseCSVProcessor):
    """Base class for soccer-specific CSV processors (EPL, Ligue 1)."""

    def _resolve_soccer_team_name(self, sport: str, team_name: str, source: str) -> str:
        """Resolve a soccer team name for a specific downstream consumer."""
        from naming_resolver import NamingResolver, NamingContext

        return NamingResolver.resolve(
            NamingContext(sport=sport.lower(), source=source, name=team_name)
        )

    def _build_soccer_game_id(
        self, sport: str, game_date: str, home_team: str, away_team: str
    ) -> str:
        """Build the deterministic soccer game identifier."""
        date_id = game_date.replace("-", "")
        home_slug = "".join(filter(str.isalnum, home_team)).upper()
        away_slug = "".join(filter(str.isalnum, away_team)).upper()
        return f"{sport.upper()}_{date_id}_{home_slug}_{away_slug}"

    def _process_soccer_row(self, row: pd.Series, sport: str, table_name: str, **kwargs) -> None:
        """Common logic for processing a soccer game row."""
        season_code = kwargs.get("season_code", "")

        # Check for required column
        if pd.isna(row.get("FTHG")):
            return

        try:
            params = self._extract_soccer_params(row, sport, season_code)

            # 1. Insert into sport-specific table
            self.db.execute(
                f"""
                INSERT INTO {table_name} (
                    game_id, game_date, season, home_team, away_team, home_score, away_score, result
                ) VALUES (:game_id, :game_date, :season, :home_team, :away_team, :home_score, :away_score, :result)
                ON CONFLICT (game_id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    result = EXCLUDED.result
            """,
                params,
            )

            # 2. Insert into unified_games
            self.db.execute(
                """
                INSERT INTO unified_games (
                    game_id, sport, game_date, season, status,
                    home_team_name, away_team_name, home_score, away_score
                ) VALUES (
                    :game_id, :sport_upper, :game_date, :season_year, 'Final',
                    :home_team_name, :away_team_name, :home_score, :away_score
                )
                ON CONFLICT (game_id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    status = EXCLUDED.status
            """,
                {
                    **params,
                    "sport_upper": sport.upper(),
                    "season_year": int("20" + season_code[:2]) if season_code and season_code[:2].isdigit() else 2024,
                    "home_team_name": params["home_team_full"],
                    "away_team_name": params["away_team_full"],
                },
            )

            # 3. Insert into team_game_stats and soccer_team_game_stats_ext
            self._insert_soccer_stats(params, row, sport.upper())

        except Exception as e:
            print(f"Error processing {sport} row: {e}")
            pass

    def _extract_soccer_params(self, row: pd.Series, sport: str, season_code: str) -> Dict[str, Any]:
        """Common parameter extraction for soccer with name resolution."""
        game_date = row["Date"]
        if hasattr(game_date, "strftime"):
            date_str = game_date.strftime("%Y-%m-%d")
        else:
            date_str = str(game_date)[:10]

        raw_home = str(row["HomeTeam"])
        raw_away = str(row["AwayTeam"])

        home_team = self._resolve_soccer_team_name(sport, raw_home, "elo")
        away_team = self._resolve_soccer_team_name(sport, raw_away, "elo")

        if sport.lower() == "epl":
            home_team_full = self._resolve_soccer_team_name(sport, raw_home, "kalshi")
            away_team_full = self._resolve_soccer_team_name(sport, raw_away, "kalshi")
            game_id = self._build_soccer_game_id(sport, date_str, raw_home, raw_away)
        else:
            home_team_full = home_team
            away_team_full = away_team
            game_id = self._build_soccer_game_id(sport, date_str, home_team, away_team)

        return {
            "game_id": game_id,
            "game_date": date_str,
            "season": season_code,
            "home_team": home_team,
            "away_team": away_team,
            "home_team_full": home_team_full,
            "away_team_full": away_team_full,
            "home_score": int(row["FTHG"]),
            "away_score": int(row["FTAG"]),
            "result": row["FTR"],
        }

    def _insert_soccer_stats(self, params: Dict[str, Any], row: pd.Series, sport: str) -> None:
        """Insert data into team_game_stats and soccer_team_game_stats_ext."""
        game_id = params["game_id"]
        game_date = params["game_date"]
        season = params["season"]
        home_team = params["home_team"]
        away_team = params["away_team"]
        home_score = params["home_score"]
        away_score = params["away_score"]

        # Home team stats
        self._upsert_team_stats(
            game_id, sport, home_team, away_team, True, game_date, season,
            home_score, away_score, home_score > away_score, row, "H"
        )

        # Away team stats
        self._upsert_team_stats(
            game_id, sport, away_team, home_team, False, game_date, season,
            away_score, home_score, away_score > home_score, row, "A"
        )

    def _upsert_team_stats(
        self, game_id, sport, team, opponent, is_home, game_date, season,
        pts_for, pts_against, won, row, side
    ):
        # Insert into team_game_stats
        self.db.execute(
            """
            INSERT INTO team_game_stats (
                game_id, sport, team, opponent, is_home, game_date, season,
                points_for, points_against, won, margin
            ) VALUES (
                :game_id, :sport, :team, :opponent, :is_home, :game_date, :season,
                :points_for, :points_against, :won, :margin
            )
            ON CONFLICT (game_id, team) DO UPDATE SET
                points_for = EXCLUDED.points_for,
                points_against = EXCLUDED.points_against,
                won = EXCLUDED.won,
                margin = EXCLUDED.margin
        """,
            {
                "game_id": game_id, "sport": sport, "team": team, "opponent": opponent,
                "is_home": is_home, "game_date": game_date, "season": season,
                "points_for": pts_for, "points_against": pts_against, "won": won,
                "margin": pts_for - pts_against
            }
        )

        # Insert into soccer_team_game_stats_ext
        prefix = "H" if side == "H" else "A"
        self.db.execute(
            """
            INSERT INTO soccer_team_game_stats_ext (
                game_id, team, shots, shots_on_target, fouls, yellow_cards, red_cards, corners
            ) VALUES (
                :game_id, :team, :shots, :shots_on_target, :fouls, :yellow_cards, :red_cards, :corners
            )
            ON CONFLICT (game_id, team) DO UPDATE SET
                shots = EXCLUDED.shots,
                shots_on_target = EXCLUDED.shots_on_target,
                fouls = EXCLUDED.fouls,
                yellow_cards = EXCLUDED.yellow_cards,
                red_cards = EXCLUDED.red_cards,
                corners = EXCLUDED.corners
        """,
            {
                "game_id": game_id,
                "team": team,
                "shots": int(row[f"{prefix}S"]) if pd.notna(row.get(f"{prefix}S")) else None,
                "shots_on_target": int(row[f"{prefix}ST"]) if pd.notna(row.get(f"{prefix}ST")) else None,
                "fouls": int(row[f"{prefix}F"]) if pd.notna(row.get(f"{prefix}F")) else None,
                "yellow_cards": int(row[f"{prefix}Y"]) if pd.notna(row.get(f"{prefix}Y")) else None,
                "red_cards": int(row[f"{prefix}R"]) if pd.notna(row.get(f"{prefix}R")) else None,
                "corners": int(row[f"{prefix}C"]) if pd.notna(row.get(f"{prefix}C")) else None,
            }
        )


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

            # 1. Insert into sport-specific table
            self.db.execute(
                """
                INSERT INTO tennis_games (
                    game_id, game_date, season, tour, tournament, surface, winner, loser, score
                ) VALUES (:game_id, :game_date, :season, :tour, :tournament, :surface, :winner, :loser, :score)
                ON CONFLICT (game_id) DO NOTHING
            """,
                params,
            )

            # 2. Insert into unified_games
            self.db.execute(
                """
                INSERT INTO unified_games (
                    game_id, sport, game_date, season, status,
                    home_team_name, away_team_name, home_score, away_score
                ) VALUES (
                    :game_id, 'TENNIS', :game_date, :season_year, 'Final',
                    :winner, :loser, 1, 0
                )
                ON CONFLICT (game_id) DO UPDATE SET
                    home_team_name = EXCLUDED.home_team_name,
                    away_team_name = EXCLUDED.away_team_name,
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    status = EXCLUDED.status
            """,
                {
                    **params,
                    "season_year": int(season) if str(season).isdigit() else 2024
                },
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


class EPLCSVProcessor(SoccerCSVProcessor):
    """CSV processor for EPL (English Premier League) games."""

    def process_row(self, row: pd.Series, **kwargs) -> None:
        """Process a single EPL game row."""
        self._process_soccer_row(row, "EPL", "epl_games", **kwargs)

    def get_table_name(self) -> str:
        """Get the database table name for EPL games.

        Returns:
            Table name "epl_games"
        """
        return "epl_games"


class Ligue1CSVProcessor(SoccerCSVProcessor):
    """CSV processor for Ligue 1 (French Soccer) games."""

    def process_row(self, row: pd.Series, **kwargs) -> None:
        """Process a single Ligue 1 game row."""
        season_code = kwargs.get("season_code", "")

        if pd.isna(row.get("FTHG")):
            return

        try:
            params = self._extract_ligue1_game_data(row, season_code)
            self.db.execute(
                """
                INSERT INTO ligue1_games (
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
            pass

    def _extract_ligue1_game_data(
        self, row: pd.Series, season_code: str
    ) -> Dict[str, Any]:
        """Extract and transform Ligue 1 game data without EPL-specific rewiring."""
        game_date = row["Date"].strftime("%Y-%m-%d")
        home_team = row["HomeTeam"]
        away_team = row["AwayTeam"]
        game_id = (
            f"LIGUE1_{game_date}_{home_team.replace(' ', '')}_{away_team.replace(' ', '')}"
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
        """Get the database table name for Ligue 1 games.

        Returns:
            Table name "ligue1_games"
        """
        return "ligue1_games"


class WNCAABCSVProcessor(BaseCSVProcessor):
    """CSV processor for WNCAAB games."""

    def process_row(self, row: pd.Series, **kwargs) -> None:
        """Process a single WNCAAB game row and upsert into database.

        Args:
            row: Pandas Series with WNCAAB game data
            **kwargs: Not used for WNCAAB
        """
        try:
            params = self._extract_wncaab_game_data(row)
            self.db.execute(
                """
                INSERT INTO wncaab_games (
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
            # Silently skip rows with errors
            pass

    def _extract_wncaab_game_data(self, row: pd.Series) -> Dict[str, Any]:
        """Extract and transform WNCAAB game data from CSV row.

        Args:
            row: Pandas Series with WNCAAB game data

        Returns:
            Dictionary of parameters for database insertion
        """
        game_date = row["date"].strftime("%Y-%m-%d")
        h_slug = "".join(x for x in str(row["home_team"]) if x.isalnum())
        a_slug = "".join(x for x in str(row["away_team"]) if x.isalnum())
        game_id = f"WNCAAB_{game_date}_{h_slug}_{a_slug}"

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
        """Get the database table name for WNCAAB games.

        Returns:
            Table name "wncaab_games"
        """
        return "wncaab_games"


class UnrivaledCSVProcessor(BaseCSVProcessor):
    """CSV processor for Unrivaled Basketball games."""

    def process_row(self, row: pd.Series, **kwargs) -> None:
        """Process a single Unrivaled game row and upsert into database."""
        try:
            params = self._extract_unrivaled_game_data(row)
            self.db.execute(
                """
                INSERT INTO unrivaled_games (
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
            pass

    def _extract_unrivaled_game_data(self, row: pd.Series) -> Dict[str, Any]:
        """Extract and transform Unrivaled game data."""
        game_date = row["date"].strftime("%Y-%m-%d")
        h_slug = "".join(x for x in str(row["home_team"]) if x.isalnum())
        a_slug = "".join(x for x in str(row["away_team"]) if x.isalnum())
        game_id = f"UNRIVALED_{game_date}_{h_slug}_{a_slug}"

        return {
            "game_id": game_id,
            "game_date": game_date,
            "season": int(row["season"]),
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "home_score": int(row["home_score"]) if not pd.isna(row["home_score"]) else 0,
            "away_score": int(row["away_score"]) if not pd.isna(row["away_score"]) else 0,
            "is_neutral": bool(row.get("neutral", True)),
        }

    def get_table_name(self) -> str:
        """Get the database table name for Unrivaled games."""
        return "unrivaled_games"


class CBACSVProcessor(BaseCSVProcessor):
    """CSV processor for CBA (Chinese Basketball Association) games."""

    def process_row(self, row: pd.Series, **kwargs) -> None:
        """Process a single CBA game row and upsert into database."""
        try:
            params = self._extract_cba_game_data(row)
            self.db.execute(
                """
                INSERT INTO cba_games (
                    game_id, game_date, season, home_team, away_team,
                    home_score, away_score, is_neutral, status
                ) VALUES (:game_id, :game_date, :season, :home_team, :away_team, :home_score, :away_score, :is_neutral, :status)
                ON CONFLICT (game_id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    status = EXCLUDED.status
            """,
                params,
            )
        except Exception:
            pass

    def _extract_cba_game_data(self, row: pd.Series) -> Dict[str, Any]:
        """Extract and transform CBA game data."""
        game_date = row["date"].strftime("%Y-%m-%d")
        h_slug = "".join(x for x in str(row["home_team"]) if x.isalnum())
        a_slug = "".join(x for x in str(row["away_team"]) if x.isalnum())
        game_id = f"CBA_{game_date}_{h_slug}_{a_slug}"

        return {
            "game_id": game_id,
            "game_date": game_date,
            "season": int(row["season"]),
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "home_score": int(row["home_score"]) if not pd.isna(row["home_score"]) else None,
            "away_score": int(row["away_score"]) if not pd.isna(row["away_score"]) else None,
            "is_neutral": bool(row.get("neutral", False)),
            "status": str(row.get("status", "Final")),
        }

    def get_table_name(self) -> str:
        """Get the database table name for CBA games."""
        return "cba_games"


# Factory function to get appropriate CSV processor
def get_csv_processor(sport: str, db_manager: DBManager) -> Optional[BaseCSVProcessor]:
    """Get CSV processor for a specific sport.

    Args:
        sport: Sport name (e.g., "ncaab", "wncaab", "unrivaled", "cba", "tennis", "epl", "ligue1")
        db_manager: Database manager for executing SQL queries

    Returns:
        CSV processor instance or None if sport not supported
    """
    processors = {
        "ncaab": NCAABCSVProcessor,
        "wncaab": WNCAABCSVProcessor,
        "unrivaled": UnrivaledCSVProcessor,
        "cba": CBACSVProcessor,
        "tennis": TennisCSVProcessor,
        "epl": EPLCSVProcessor,
        "ligue1": Ligue1CSVProcessor,
    }

    processor_class = processors.get(sport.lower())
    if processor_class:
        return processor_class(db_manager)
    return None
