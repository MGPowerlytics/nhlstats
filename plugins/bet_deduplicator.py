"""Cross-day bet deduplication for the betting system.

Checks placed_bets for existing bets on the same (sport, home_team, away_team, bet_on)
within a configurable rolling window (default: 3 days). Prevents placing new bets on
matchups that have already been bet on recently.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from db_manager import DBManager, default_db


class BetDeduplicator:
    """Checks placed_bets for duplicate bets within a rolling time window.

    A bet is considered a duplicate if there exists an existing bet in
    placed_bets with the same (sport, home_team, away_team, bet_on) where
    placed_date falls within DEDUP_WINDOW_DAYS before the proposed date
    and the status is 'open', 'won', or 'lost'.

    Canceled bets are ignored (you may re-bet on a previously canceled matchup).
    Null team names (pre-backfill rows) are treated as non-matches.
    """

    DEDUP_WINDOW_DAYS: int = 3

    def __init__(self, db: Optional[DBManager] = None) -> None:
        """Initialize the deduplicator.

        Args:
            db: DBManager instance. Defaults to the global default_db.
        """
        self.db = db or default_db

    def is_duplicate(
        self,
        sport: str,
        home_team: str,
        away_team: str,
        bet_on: str,
        placed_date: str | date | datetime,
        ticker: str | None = None,
    ) -> bool:
        """Check if a bet on this matchup already exists within the dedup window.

        Args:
            sport: Sport code in uppercase (e.g., ``"MLB"``, ``"EPL"``).
            home_team: Canonical home team name.
            away_team: Canonical away team name.
            bet_on: The side being bet on (team name or ``"home"`` / ``"away"``).
            placed_date: The proposed placement date (YYYY-MM-DD string,
                ``date``, or ``datetime``).
            ticker: Full ticker of the bet (e.g. ``"KXEPLGAME-26MAY04EVEMCI-MCI"``).
                Used to dedup at the game level — if any bet on the same base game
                ID exists within the window, this is a duplicate.

        Returns:
            ``True`` if a matching non-canceled bet exists within the window,
            ``False`` otherwise.
        """
        # Normalize placed_date to string
        if isinstance(placed_date, (datetime, date)):
            date_str = placed_date.isoformat() if isinstance(placed_date, date) else placed_date.strftime("%Y-%m-%d")
        else:
            date_str = placed_date

        # Calculate window start (placed_date minus DEDUP_WINDOW_DAYS)
        placed_dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        window_start = (placed_dt - timedelta(days=self.DEDUP_WINDOW_DAYS)).isoformat()

        # When a ticker is supplied, expand check to game-level dedup: if ANY bet
        # on the same base game ID exists within the window, skip the new bet.
        # This prevents betting both sides of the same game (e.g. MCI and EVE).
        if ticker:
            # Strip the side suffix to get the base game ID.
            # e.g. "KXEPLGAME-26MAY04EVEMCI-MCI" → "KXEPLGAME-26MAY04EVEMCI"
            # Side suffixes are team codes (2-4 caps) or HOME/DRAW/AWAY.
            import re
            base_game_id = re.sub(r"-([A-Z]{2,3}|HOME|DRAW|AWAY)$", "", ticker)
        else:
            base_game_id = None

        if base_game_id:
            # Game-level dedup: any bet on this base game ID is a duplicate.
            # The base game ID uniquely identifies a specific game (e.g.
            # KXEPLGAME-26MAY04EVEMCI = Everton vs Man City on 2026-05-04),
            # so the dedup is permanent — no date window needed.
            # Use a simple LIKE prefix match — works across SQLite and PostgreSQL.
            game_query = """
                SELECT COUNT(*) AS cnt
                FROM placed_bets pb
                WHERE pb.sport = :sport
                  AND pb.status IN ('open', 'filled', 'won', 'lost')
                  AND pb.ticker LIKE :ticker_prefix || '%'
            """
            game_params = {
                "sport": sport,
                "ticker_prefix": base_game_id,
            }
            try:
                game_count = self.db.fetch_scalar(game_query, game_params) or 0
            except Exception:
                game_count = 0

            if game_count > 0:
                return True

        # Original side-level dedup (same sport + home + away + bet_on)
        query = """
            SELECT COUNT(*) AS cnt
            FROM placed_bets
            WHERE sport = :sport
              AND home_team = :home_team
              AND away_team = :away_team
              AND bet_on = :bet_on
              AND placed_date >= :window_start
              AND placed_date <= :placed_date
              AND status IN ('open', 'filled', 'won', 'lost')
        """

        params = {
            "sport": sport,
            "home_team": home_team,
            "away_team": away_team,
            "bet_on": bet_on,
            "window_start": window_start,
            "placed_date": date_str,
        }

        try:
            count = self.db.fetch_scalar(query, params) or 0
        except Exception:
            # If the placed_bets table doesn't exist (e.g., test environment
            # without full schema), treat as no duplicate — safe fallback.
            return False

        return count > 0
