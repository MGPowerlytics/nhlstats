"""
Abstract base class for all sport-specific box-score fetchers.

Each concrete sub-class fetches raw box-score data from an external source,
normalises it into the canonical ``team_game_stats`` schema, and persists
both the core row and any sport-specific extension rows via
:class:`~plugins.db_manager.DBManager`.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from plugins.db_manager import DBManager


class BoxScoreFetcher(ABC):
    """Abstract fetcher for team-level box-score data.

    Sub-classes **must** declare three class attributes and implement three
    abstract methods.

    Class Attributes:
        SPORT: Short sport identifier (e.g. ``"NBA"``, ``"NHL"``).
        RATE_LIMIT_SECONDS: Minimum pause (seconds) between successive API
            calls.  Enforced by :meth:`_rate_limit`.
        EXT_TABLE: Name of the sport-specific extension table in Postgres
            (e.g. ``"nba_team_game_stats_ext"``).

    Example:
        >>> class NBABoxScoreFetcher(BoxScoreFetcher):
        ...     SPORT = "NBA"
        ...     RATE_LIMIT_SECONDS = 0.34  # ~3 req/s
        ...     EXT_TABLE = "nba_team_game_stats_ext"
    """

    # ------------------------------------------------------------------
    # Sub-classes MUST override these three class attributes
    # ------------------------------------------------------------------
    SPORT: str = ""
    RATE_LIMIT_SECONDS: float = 1.0
    EXT_TABLE: str = ""

    def __init__(self, db: DBManager | None = None) -> None:
        """Initialise the fetcher with an optional shared DBManager.

        Args:
            db: An existing :class:`~plugins.db_manager.DBManager` instance.
                When ``None`` a new instance is created using the default
                environment-variable credentials.
        """
        self.db: DBManager = db or DBManager()
        self._last_request_ts: float = 0.0

    # ------------------------------------------------------------------
    # Abstract API — sub-classes implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def fetch_game_stats(self, game_id: str) -> list[dict[str, Any]]:
        """Fetch box-score rows for a single completed game.

        Returns one dict per *team* (home and away), normalised to the
        ``team_game_stats`` column contract.  Sport-specific fields are
        embedded under the ``"ext"`` key so that :meth:`upsert_rows` can
        split them across the core and extension tables.

        Args:
            game_id: The platform-native game identifier for this sport.

        Returns:
            A list of two dicts — one for each team.

        Raises:
            NotImplementedError: Concrete sub-class must implement this.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_date_range(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch box-score rows for every game within an inclusive date range.

        Args:
            start: First calendar date (inclusive).
            end: Last calendar date (inclusive).

        Returns:
            A flat list of normalised team-row dicts (same format as
            :meth:`fetch_game_stats`).

        Raises:
            NotImplementedError: Concrete sub-class must implement this.
        """
        raise NotImplementedError

    @abstractmethod
    def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        """Persist normalised rows to ``team_game_stats`` and the extension table.

        Rows whose ``"ext"`` sub-dict is non-empty are also written to
        :attr:`EXT_TABLE`.  Both writes use ON-CONFLICT-DO-UPDATE semantics
        (upsert) so that re-runs are idempotent.

        Args:
            rows: Normalised team-game dicts as returned by
                :meth:`fetch_game_stats` or :meth:`fetch_date_range`.

        Returns:
            Total number of rows upserted across both tables.

        Raises:
            NotImplementedError: Concrete sub-class must implement this.

        TODO (Wave 2):
            Implement shared upsert logic here once the Postgres schema is
            finalised.  Sub-classes should be able to call
            ``super().upsert_rows(rows)`` without overriding this method.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        """Block until at least :attr:`RATE_LIMIT_SECONDS` have elapsed since
        the last API call.

        Call this immediately before every outbound HTTP request.
        """
        elapsed = time.monotonic() - self._last_request_ts
        wait = self.RATE_LIMIT_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(sport={self.SPORT!r})"
