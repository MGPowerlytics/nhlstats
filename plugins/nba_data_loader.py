"""NBA-specific data loader for loading NBA scoreboard data into PostgreSQL."""

import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from plugins.db_manager import DBManager


class NBADataLoader:
    """NBA-specific data loader for loading NBA scoreboard data into PostgreSQL."""

    def __init__(self, db_manager: DBManager) -> None:
        """Initialize NBA data loader with database manager.

        Args:
            db_manager: Database manager instance for database operations
        """
        self.db = db_manager

    def load_nba_scoreboard(self, file_path: Path) -> None:
        """Load NBA scoreboard JSON into PostgreSQL (supports ESPN and legacy NBA Stats formats).

        Args:
            file_path: Path to the scoreboard JSON file
        """
        with open(file_path) as f:
            data = json.load(f)

        # Ensure table exists before processing any games
        self._ensure_nba_games_table_exists()

        # --- ESPN Format ---
        if "events" in data:
            self._process_espn_format(data["events"])
            return

        # --- Legacy NBA Stats Format ---
        if "resultSets" not in data:
            return

        self._process_nba_stats_format(data)

    def _ensure_nba_games_table_exists(self) -> None:
        """Create NBA games table if it doesn't exist."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS nba_games (
                game_id VARCHAR PRIMARY KEY,
                game_date DATE,
                season INTEGER,
                game_type VARCHAR,
                home_team VARCHAR,
                away_team VARCHAR,
                home_score INTEGER,
                away_score INTEGER,
                status VARCHAR
            )
        """)

    def _insert_or_update_nba_game(self, params: dict) -> None:
        """Insert or update NBA game record in database.

        Args:
            params: Dictionary containing game parameters
        """
        self.db.execute(
            """
            INSERT INTO nba_games (
                game_id, game_date, season, game_type,
                home_team, away_team, home_score, away_score, status
            ) VALUES (:game_id, :game_date, :season, :game_type, :home_team, :away_team, :home_score, :away_score, :status)
            ON CONFLICT (game_id) DO UPDATE SET
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score,
                status = EXCLUDED.status,
                game_date = EXCLUDED.game_date
        """,
            params,
        )

    def _process_espn_format(self, events: list) -> None:
        """Process ESPN format game events.

        Args:
            events: List of ESPN game events
        """
        for event in events:
            try:
                params = self._parse_espn_game_event(event)
                if params:
                    self._insert_or_update_nba_game(params)
            except Exception as e:
                print(f"    Error loading NBA game {event.get('id')}: {e}")

    def _parse_espn_game_event(self, event: dict) -> Optional[dict]:
        """Parse ESPN format game event and return parameters dict.

        Args:
            event: ESPN game event dictionary

        Returns:
            Dictionary of game parameters or None if parsing fails
        """
        game_id = event["id"]
        # ESPN date is ISO format e.g. "2026-02-04T00:00Z"
        game_date_str = event["date"].split("T")[0]
        season = event.get("season", {}).get("year")

        # Determine status
        status_desc = (
            event.get("status", {}).get("type", {}).get("description", "Scheduled")
        )
        status = self._normalize_game_status(status_desc)

        # Get competitors
        home_team, away_team, home_score, away_score = self._extract_espn_competitors(
            event
        )

        if not home_team or not away_team:
            return None

        return {
            "game_id": game_id,
            "game_date": game_date_str,
            "season": season,
            "game_type": "Regular",  # Simplification
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "status": status,
        }

    def _extract_espn_competitors(
        self, event: dict
    ) -> Tuple[Optional[str], Optional[str], int, int]:
        """Extract team information from ESPN event competitors.

        Args:
            event: ESPN game event dictionary

        Returns:
            Tuple of (home_team, away_team, home_score, away_score)
        """
        home_team = None
        away_team = None
        home_score = 0
        away_score = 0

        competitions = event.get("competitions", [])
        if competitions:
            competitors = competitions[0].get("competitors", [])
            for comp in competitors:
                team_info = comp.get("team", {})
                abbrev = team_info.get("abbreviation")
                score = int(comp.get("score", 0))

                if comp.get("homeAway") == "home":
                    home_team = abbrev
                    home_score = score
                else:
                    away_team = abbrev
                    away_score = score

        return home_team, away_team, home_score, away_score

    def _process_nba_stats_format(self, data: dict) -> None:
        """Process legacy NBA Stats format data.

        Args:
            data: NBA Stats format data dictionary
        """

        # Helper to get result set by name
        def get_result_set(name: str) -> Optional[Dict[str, Any]]:
            for rs in data["resultSets"]:
                if rs["name"] == name:
                    return rs
            return None

        header = get_result_set("GameHeader")
        line_score = get_result_set("LineScore")

        if not header:
            return

        # Map headers to indices
        h_cols = {col: i for i, col in enumerate(header["headers"])}
        l_cols = (
            {col: i for i, col in enumerate(line_score["headers"])}
            if line_score
            else {}
        )

        # Create a map of game_id -> {team_id: score}
        scores_map = self._build_scores_map(line_score, l_cols) if line_score else {}

        for row in header["rowSet"]:
            try:
                params = self._parse_nba_stats_game_row(
                    row, h_cols, line_score, l_cols, scores_map
                )
                if params:
                    self._insert_or_update_nba_game(params)
            except Exception as e:
                game_id = row[h_cols["GAME_ID"]] if "GAME_ID" in h_cols else "unknown"
                print(f"    Error loading NBA game {game_id}: {e}")

    def _build_scores_map(self, line_score: dict, l_cols: dict) -> dict:
        """Build map of game_id -> {team_id: score} from line score data.

        Args:
            line_score: Line score data dictionary
            l_cols: Column index mapping for line score

        Returns:
            Dictionary mapping game_id to team_id->score mapping
        """
        scores_map: dict[str, dict] = {}
        for row in line_score["rowSet"]:
            gid = row[l_cols["GAME_ID"]]
            tid = row[l_cols["TEAM_ID"]]
            pts = row[l_cols["PTS"]]
            if gid not in scores_map:
                scores_map[gid] = {}
            scores_map[gid][tid] = pts
        return scores_map

    def _parse_nba_stats_game_row(
        self,
        row: list,
        h_cols: dict,
        line_score: Optional[dict],
        l_cols: dict,
        scores_map: dict,
    ) -> Optional[dict]:
        """Parse NBA Stats format game row and return parameters dict.

        Args:
            row: Game row data
            h_cols: Column index mapping for header
            line_score: Line score data dictionary
            l_cols: Column index mapping for line score
            scores_map: Scores mapping dictionary

        Returns:
            Dictionary of game parameters or None if parsing fails
        """
        game_id = row[h_cols["GAME_ID"]]
        game_date_str = row[h_cols["GAME_DATE_EST"]].split("T")[0]
        home_id = row[h_cols["HOME_TEAM_ID"]]
        visitor_id = row[h_cols["VISITOR_TEAM_ID"]]

        # Fetch team abbreviations from LineScore if possible
        home_team, away_team = self._extract_team_abbreviations(
            home_id, visitor_id, line_score, l_cols
        )

        home_score = scores_map.get(game_id, {}).get(home_id)
        away_score = scores_map.get(game_id, {}).get(visitor_id)

        status_text = row[h_cols["GAME_STATUS_TEXT"]]
        status = self._normalize_game_status(status_text)

        return {
            "game_id": game_id,
            "game_date": game_date_str,
            "season": int(row[h_cols["SEASON"]]),
            "game_type": "Regular",  # Simplification
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "status": status,
        }

    def _extract_team_abbreviations(
        self, home_id: int, visitor_id: int, line_score: Optional[dict], l_cols: dict
    ) -> Tuple[str, str]:
        """Extract team abbreviations from line score data.

        Args:
            home_id: Home team ID
            visitor_id: Visitor team ID
            line_score: Line score data dictionary
            l_cols: Column index mapping for line score

        Returns:
            Tuple of (home_team_abbreviation, away_team_abbreviation)
        """
        home_team = str(home_id)
        away_team = str(visitor_id)

        if line_score:
            # Find abbreviations
            # This is inefficient but safe
            for ls_row in line_score["rowSet"]:
                if ls_row[l_cols["TEAM_ID"]] == home_id:
                    home_team = ls_row[l_cols["TEAM_ABBREVIATION"]]
                elif ls_row[l_cols["TEAM_ID"]] == visitor_id:
                    away_team = ls_row[l_cols["TEAM_ABBREVIATION"]]

        return home_team, away_team

    def _normalize_game_status(self, status_text: str) -> str:
        """Normalize game status string to standardized values.

        Args:
            status_text: Raw status text

        Returns:
            Normalized status string
        """
        if "Final" in status_text:
            return "Final"
        elif "In Progress" in status_text or "Live" in status_text:
            return "Live"
        elif "pm" in status_text or "am" in status_text or "ET" in status_text:
            return "Scheduled"
        else:
            return "Live"  # Default to Live for unknown statuses
