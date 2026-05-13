"""Historical stats daily ingestion DAG.

DAG ID: historical_stats_daily
Schedule: 0 8 * * * (08:00 UTC — after overnight games are final everywhere)
Start date: 2026-01-01
Catchup: False
Max active runs: 1

This DAG ingests team-level box-score and advanced stats from each sport's
public API into the PostgreSQL database on a daily basis.  One task is defined
per sport; a final validation task depends on all sport tasks.

Each task queries ``unified_games`` for yesterday's games (logical_date == ds),
calls the sport-specific fetcher, and upserts results into PostgreSQL.

Pool assignments
----------------
- stats_nba_pool    : 3 slots  (NBA Stats API, ~1 req/s)
- stats_nhl_pool    : 1 slot   (NHL API, ~0.5 req/s)
- stats_mlb_pool    : 2 slots  (MLB Stats API, ~1 req/s)
- stats_nfl_pool    : 2 slots  (nfl_data_py parquet download)
- stats_fbref_pool  : 1 slot   (FBRef / Sports-Reference, 1 req/4s)
- stats_cbb_pool    : 2 slots  (Sports-Reference CBB, 1 req/4s)
- stats_tennis_pool : 1 slot   (Tennis Abstract GitHub CSV)

Pools **must** be created before the DAG can run — see docs/AIRFLOW_SETUP.md.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from airflow import DAG

try:
    from airflow.providers.standard.operators.python import PythonOperator
except ImportError:
    from airflow.operators.python import PythonOperator  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_DEFAULT_TASK_KWARGS: dict[str, Any] = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}


def _yesterday_from_context(context: dict[str, Any]) -> date:
    """Return the UTC date for yesterday relative to the Airflow logical_date.

    In Airflow 3.x the ``ds`` context key is the data-interval-start date
    string (``YYYY-MM-DD``), which for a daily 08:00 UTC schedule equals the
    calendar day *before* the scheduled run fires.  We use it directly as
    "yesterday".

    Args:
        context: Airflow task context dictionary.

    Returns:
        The calendar date whose games we want to ingest.
    """
    ds: str | None = context.get("ds")
    if ds:
        return date.fromisoformat(ds)
    # Fallback for local / unit-test execution without a full Airflow context.
    logical = context.get("logical_date") or context.get("execution_date")
    if logical is not None:
        return logical.date()
    return date.today() - timedelta(days=1)


def _query_games_for_date(sport: str, game_date: date) -> list[str]:
    """Return game_ids for a given sport and date.

    Args:
        sport: Upper-case sport identifier (e.g. ``"NBA"``, ``"NHL"``).
        game_date: The calendar date to query.

    Returns:
        List of ``game_id`` strings.
    """
    from plugins.db_manager import DBManager

    db = DBManager()
    sport = sport.upper()
    if sport == "MLB":
        df = db.fetch_df(
            """
            SELECT CAST(game_id AS VARCHAR) AS game_id
            FROM mlb_games
            WHERE game_date = :gdate
            ORDER BY game_id
        """,
            {"gdate": str(game_date)},
        )
    else:
        df = db.fetch_df(
            "SELECT game_id FROM unified_games WHERE sport = :sport AND game_date = :gdate",
            {"sport": sport, "gdate": str(game_date)},
        )
    return [str(game_id) for game_id in df["game_id"].tolist()] if not df.empty else []


def _run_sport_fetch(
    fetcher: Any,
    sport: str,
    game_date: date,
) -> None:
    """Core ingestion loop shared by sports whose fetchers accept unified IDs.

    Iterates over games scheduled for *game_date* (queried from
    ``unified_games`` or the sport's own table), fetches box-score rows via
    the provided *fetcher*, upserts them to PostgreSQL, and logs a summary
    of processed / upserted / skipped / failed counts.

    Used by MLB, NFL, EPL, Ligue1, NCAAB, WNCAAB, and Tennis — sports whose
    fetchers are designed to accept the internal ``unified_games`` game IDs.
    For NHL and NBA (which need native numeric API IDs) see
    :func:`_run_sport_fetch_by_date`.

    Args:
        fetcher: A concrete :class:`~plugins.stats.base.BoxScoreFetcher`
            instance.
        sport: Upper-case sport identifier used for log messages and DB
            queries.
        game_date: Calendar date to process (typically yesterday in UTC).
    """
    game_ids = _query_games_for_date(sport, game_date)
    total = len(game_ids)
    upserted = 0
    skipped = 0
    failed = 0

    logger.info("📅 %s — processing %d game(s) for %s", sport, total, game_date)

    for game_id in game_ids:
        try:
            rows = fetcher.fetch_game_stats(game_id)
            if not rows:
                logger.debug(
                    "⏭️  %s game %s returned no rows — skipping", sport, game_id
                )
                skipped += 1
                continue
            count = fetcher.upsert_rows(rows)
            upserted += count
            logger.debug("✓ %s game %s → %d row(s) upserted", sport, game_id, count)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.error("❌ %s game %s failed: %s", sport, game_id, exc, exc_info=True)

    logger.info(
        "✅ %s %s summary — processed=%d upserted=%d skipped=%d failed=%d",
        sport,
        game_date,
        total,
        upserted,
        skipped,
        failed,
    )

    if failed and failed == total and total > 0:
        raise RuntimeError(
            f"{sport}: all {total} game(s) failed to ingest for {game_date}"
        )


def _run_sport_fetch_by_date(
    fetcher: Any,
    sport: str,
    game_date: date,
) -> None:
    """Fetch stats via native API schedule and remap game IDs to unified format.

    This helper is used for sports (NHL, NBA) where ``unified_games`` stores
    internal string IDs such as ``NHL_20260423_BOS_BUF`` or
    ``NBA_20260423_ATLANTAHAWKS_NEWYORKKNICKS``, but the sport's public API
    requires native numeric game IDs (e.g. ``2026030101``, ``0042500101``).
    Passing the internal string IDs directly to those APIs results in 404 or
    missing-key errors.

    Workflow:

    1. Build a ``{(home_abbrev, away_abbrev) -> unified_game_id}`` lookup from
       ``unified_games`` for the target sport and date.
    2. Call ``fetcher.fetch_date_range(game_date, game_date)``, which queries
       the sport's native API schedule for completed games, fetches each
       box-score, and returns rows keyed by the native numeric game ID.
    3. Remap ``row["game_id"]`` (and ``row["ext"]["game_id"]`` when present)
       to the matching ``unified_games`` ID using the lookup from step 1.
    4. Call ``fetcher.upsert_rows(remapped_rows)`` — the FK check inside
       ``upsert_rows`` will now pass because the IDs match ``unified_games``.

    Args:
        fetcher: A concrete :class:`~plugins.stats.base.BoxScoreFetcher`
            instance that implements ``fetch_date_range``.
        sport: Upper-case sport identifier used for log messages and DB
            queries.
        game_date: Calendar date to process (typically yesterday in UTC).

    Raises:
        RuntimeError: If rows were returned by the native API but none could
            be remapped to a ``unified_games`` ID, indicating a data sync
            problem that should trigger a task retry.
    """
    from plugins.db_manager import DBManager

    sport_upper = sport.upper()
    db = DBManager()

    # Step 1: Build home/away → unified_game_id lookup from unified_games.
    lu_df = db.fetch_df(
        "SELECT game_id, home_team_id, away_team_id FROM unified_games "
        "WHERE sport = :sport AND game_date = :gdate",
        {"sport": sport_upper, "gdate": str(game_date)},
    )

    if lu_df.empty:
        logger.info("📅 %s — no games in unified_games for %s", sport, game_date)
        return

    lookup: dict[tuple[str, str], str] = {}
    for _, lu_row in lu_df.iterrows():
        home = str(lu_row["home_team_id"]).upper() if lu_row["home_team_id"] else ""
        away = str(lu_row["away_team_id"]).upper() if lu_row["away_team_id"] else ""
        if home and away:
            lookup[(home, away)] = str(lu_row["game_id"])

    logger.info(
        "📅 %s — fetching via native API for %s (%d game(s) scheduled)",
        sport,
        game_date,
        len(lu_df),
    )

    # Step 2: Fetch rows using the native API schedule (returns numeric IDs).
    rows = fetcher.fetch_date_range(game_date, game_date)

    if not rows:
        logger.info(
            "✅ %s %s — native API returned 0 completed game rows", sport, game_date
        )
        return

    # Step 3: Remap native game IDs → unified_games IDs.
    remapped: list[dict[str, Any]] = []
    unmapped = 0
    for row in rows:
        is_home: bool = bool(row.get("is_home", False))
        home_abbrev = (row["team"] if is_home else row["opponent"]).upper()
        away_abbrev = (row["opponent"] if is_home else row["team"]).upper()
        unified_id = lookup.get((home_abbrev, away_abbrev))
        if unified_id is None:
            logger.warning(
                "⚠️ %s: no unified_games match for home=%s away=%s on %s — skipping",
                sport,
                home_abbrev,
                away_abbrev,
                game_date,
            )
            unmapped += 1
            continue
        remapped_row = dict(row)
        remapped_row["game_id"] = unified_id
        if isinstance(remapped_row.get("ext"), dict):
            remapped_row["ext"] = {**remapped_row["ext"], "game_id": unified_id}
        remapped.append(remapped_row)

    logger.info(
        "📊 %s %s — API returned %d row(s), remapped %d, unmapped %d",
        sport,
        game_date,
        len(rows),
        len(remapped),
        unmapped,
    )

    if not remapped:
        raise RuntimeError(
            f"{sport}: {len(rows)} row(s) fetched from native API but none matched "
            f"unified_games for {game_date} — team abbreviation mismatch?"
        )

    # Step 4: Upsert remapped rows; FK check in upsert_rows now passes.
    upserted = fetcher.upsert_rows(remapped)
    logger.info("✅ %s %s — %d row(s) upserted", sport, game_date, upserted)

    if len(remapped) > 0 and upserted == 0:
        raise RuntimeError(
            f"{sport}: {len(remapped)} row(s) remapped but 0 upserted for {game_date}"
        )


def _run_tennis_fetch_by_date(
    fetcher: Any,
    game_date: date,
) -> None:
    """Fetch tennis stats via Sackmann CSV and remap to unified game IDs.

    Tennis has a unique ID mismatch problem: ``unified_games`` stores IDs
    in the format ``TENNIS_{TOUR}_{DATE}_{WINNER_SLUG}_{LOSER_SLUG}`` (built
    from Kalshi market data), but :class:`~plugins.stats.tennis_box_score.TennisBoxScoreFetcher`
    uses Sackmann CSV IDs like ``wta_2026-560_R64_0001``.

    Additional complication: ``fetch_date_range`` filters by Sackmann's
    ``tourney_date`` (tournament *start* date), not the individual match
    date.  A match played on Apr 23 may belong to a tournament that started
    Apr 20, so a single-day query often returns 0 rows.  We widen the
    lookback window to 14 days to capture mid-tournament rounds.

    Workflow:

    1. Query ``unified_games`` for tennis games on *game_date*.  Build a
       player-slug lookup ``{frozenset([slug_p1, slug_p2]) -> unified_game_id}``.
    2. Call ``fetcher.fetch_date_range(game_date - 14d, game_date)`` to fetch
       all Sackmann rows whose tournament started within the past 14 days.
    3. Group returned rows by Sackmann-native ``game_id``.  For each group
       identify winner (``won=True``) and loser (``won=False``), then
       slugify their ``player_name`` and look up the unified ID.
    4. Remap matching rows and call ``fetcher.upsert_rows``.
    5. If 0 rows are returned from Sackmann, or none match ``unified_games``,
       log an info/warning but **do not raise** — this is expected when
       tournament start dates precede the game date by more than the lookback
       window, or when no Sackmann CSV is available yet for new matches.

    Args:
        fetcher: A :class:`~plugins.stats.tennis_box_score.TennisBoxScoreFetcher`
            instance.
        game_date: Calendar date to process (typically yesterday in UTC).
    """
    import re
    from collections import defaultdict

    from plugins.db_manager import DBManager

    db = DBManager()

    # Step 1: Build player-slug lookup from unified_games tennis entries.
    params: dict[str, str] = {"gdate": str(game_date)}
    query = "SELECT game_id FROM unified_games WHERE sport = 'TENNIS' AND game_date = :gdate"
    tour = str(getattr(fetcher, "tour", "")).upper()
    if tour in {"ATP", "WTA"}:
        query += " AND game_id LIKE :tour_prefix"
        params["tour_prefix"] = f"TENNIS_{tour}_%"
    lu_df = db.fetch_df(query, params)

    if lu_df.empty:
        logger.info("📅 Tennis — no games in unified_games for %s", game_date)
        return

    def _slugify(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    def _parse_player_slugs(gid: str) -> tuple[str, str] | None:
        """Extract (winner_slug, loser_slug) from a TENNIS_... game_id."""
        # Format: TENNIS_{TOUR}_{DATE}_{P1SLUG}_{P2SLUG}
        # Date uses hyphens, so split("_", 3) correctly isolates the player part.
        parts = gid.split("_", 3)
        if len(parts) < 4:
            return None
        remainder = parts[3]  # e.g. "ElenaRybakina_ElenaGabrielaRuse"
        idx = remainder.find("_")
        if idx < 0:
            return None
        return _slugify(remainder[:idx]), _slugify(remainder[idx + 1 :])

    lookup: dict[frozenset, str] = {}
    for gid in lu_df["game_id"].tolist():
        slugs = _parse_player_slugs(str(gid))
        if slugs:
            lookup[frozenset(slugs)] = str(gid)

    logger.info(
        "📅 Tennis — fetching via Sackmann CSV for %s (%d game(s) in unified_games)",
        game_date,
        len(lu_df),
    )

    # Step 2: Widen lookback to 14 days so mid-tournament rounds are included.
    window_start = game_date - timedelta(days=14)
    rows = fetcher.fetch_date_range(window_start, game_date)

    if not rows:
        logger.info(
            "✅ Tennis %s — Sackmann returned 0 rows (tournament may have started "
            "more than 14 days ago; skipping stats ingestion)",
            game_date,
        )
        return

    # Step 3: Group by native Sackmann game_id; identify winner/loser pair.
    by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_game[row["game_id"]].append(row)

    remapped: list[dict[str, Any]] = []
    unmapped = 0
    for native_gid, game_rows in by_game.items():
        winner_row = next((r for r in game_rows if r.get("won")), None)
        loser_row = next((r for r in game_rows if not r.get("won")), None)
        if not winner_row or not loser_row:
            unmapped += 1
            continue
        w_slug = _slugify(winner_row.get("player_name", ""))
        l_slug = _slugify(loser_row.get("player_name", ""))
        unified_id = lookup.get(frozenset([w_slug, l_slug]))
        if unified_id is None:
            logger.debug(
                "⚠️ Tennis: no unified_games match for %s vs %s (from Sackmann id %s)",
                w_slug,
                l_slug,
                native_gid,
            )
            unmapped += 1
            continue
        for row in game_rows:
            rr = dict(row)
            rr["game_id"] = unified_id
            remapped.append(rr)

    logger.info(
        "📊 Tennis %s — Sackmann: %d row(s) across %d match(es); "
        "remapped %d, unmapped %d",
        game_date,
        len(rows),
        len(by_game),
        len(remapped),
        unmapped,
    )

    if not remapped:
        logger.warning(
            "⚠️ Tennis %s — %d Sackmann match(es) found but none matched "
            "unified_games slugs (name format may differ between sources)",
            game_date,
            len(by_game),
        )
        return

    # Step 4: Upsert; FK check inside upsert_rows will now pass.
    upserted = fetcher.upsert_rows(remapped)
    logger.info("✅ Tennis %s — %d row(s) upserted", game_date, upserted)


# ---------------------------------------------------------------------------
# Sport task callables
# ---------------------------------------------------------------------------


def _fetch_stats_nba(**context: Any) -> None:
    """Fetch and store NBA team game stats for the execution date.

    Uses :func:`_run_sport_fetch_by_date` to query the native NBA Stats API
    schedule (via ``LeagueGameFinder``) for completed games, remap native
    numeric game IDs to unified internal IDs, then upsert to PostgreSQL.
    Gracefully skips if ``nba_api`` is not installed.

    Args:
        **context: Airflow task context dictionary.
    """
    try:
        from plugins.stats.nba_box_score import NBABoxScoreFetcher
    except ImportError as exc:
        logger.warning("⚠️  nba_api unavailable (%s) — skipping NBA stats fetch", exc)
        return

    yesterday = _yesterday_from_context(context)
    fetcher = NBABoxScoreFetcher()
    _run_sport_fetch_by_date(fetcher, "NBA", yesterday)


def _fetch_stats_nhl(**context: Any) -> None:
    """Fetch and store NHL team game stats for the execution date.

    Uses :func:`_run_sport_fetch_by_date` to query the native NHL API
    schedule for completed games, remap native numeric game IDs to unified
    internal IDs, then upsert to PostgreSQL.

    Args:
        **context: Airflow task context dictionary.
    """
    from plugins.stats.nhl_box_score import NHLBoxScoreFetcher

    yesterday = _yesterday_from_context(context)
    fetcher = NHLBoxScoreFetcher()
    _run_sport_fetch_by_date(fetcher, "NHL", yesterday)


def _fetch_stats_mlb(**context: Any) -> None:
    """Fetch and store MLB team game stats for the execution date.

    Args:
        **context: Airflow task context dictionary.
    """
    from plugins.stats.mlb_box_score import MLBBoxScoreFetcher

    yesterday = _yesterday_from_context(context)
    fetcher = MLBBoxScoreFetcher()
    _run_sport_fetch(fetcher, "MLB", yesterday)


def _fetch_stats_nfl(**context: Any) -> None:
    """Fetch and store NFL team game stats for the execution date.

    Gracefully skips if ``nfl_data_py`` is not installed.

    Args:
        **context: Airflow task context dictionary.
    """
    try:
        from plugins.stats.nfl_box_score import NFLBoxScoreFetcher, _NFL_DATA_AVAILABLE
    except ImportError as exc:
        logger.warning(
            "⚠️  nfl_data_py unavailable (%s) — skipping NFL stats fetch", exc
        )
        return

    if not _NFL_DATA_AVAILABLE:
        logger.warning("⚠️  nfl_data_py not installed — skipping NFL stats fetch")
        return

    yesterday = _yesterday_from_context(context)
    fetcher = NFLBoxScoreFetcher()
    _run_sport_fetch(fetcher, "NFL", yesterday)


def _fetch_stats_epl(**context: Any) -> None:
    """Fetch and store EPL team game stats for the execution date.

    Args:
        **context: Airflow task context dictionary.
    """
    from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

    yesterday = _yesterday_from_context(context)
    fetcher = SoccerBoxScoreFetcher(sport="EPL")
    _run_sport_fetch(fetcher, "EPL", yesterday)


def _fetch_stats_ligue1(**context: Any) -> None:
    """Fetch and store Ligue 1 team game stats for the execution date.

    Args:
        **context: Airflow task context dictionary.
    """
    from plugins.stats.soccer_box_score import SoccerBoxScoreFetcher

    yesterday = _yesterday_from_context(context)
    fetcher = SoccerBoxScoreFetcher(sport="Ligue1")
    _run_sport_fetch(fetcher, "Ligue1", yesterday)


def _fetch_stats_ncaab(**context: Any) -> None:
    """Fetch and store NCAAB team game stats for the execution date.

    Args:
        **context: Airflow task context dictionary.
    """
    from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

    yesterday = _yesterday_from_context(context)
    fetcher = CBBBoxScoreFetcher(sport="NCAAB")
    _run_sport_fetch(fetcher, "NCAAB", yesterday)


def _fetch_stats_wncaab(**context: Any) -> None:
    """Fetch and store WNCAAB team game stats for the execution date.

    Args:
        **context: Airflow task context dictionary.
    """
    from plugins.stats.cbb_box_score import CBBBoxScoreFetcher

    yesterday = _yesterday_from_context(context)
    fetcher = CBBBoxScoreFetcher(sport="WNCAAB")
    _run_sport_fetch(fetcher, "WNCAAB", yesterday)


def _fetch_stats_tennis(**context: Any) -> None:
    """Fetch and store tennis player-match stats for the execution date.

    Uses :func:`_run_tennis_fetch_by_date` to match Sackmann CSV rows against
    ``unified_games`` IDs (which use a slug-based format derived from Kalshi
    market data) rather than passing raw Sackmann IDs to ``fetch_game_stats``.
    Runs both ATP and WTA fetchers so production training can use stats coverage
    across both tours.

    Args:
        **context: Airflow task context dictionary.
    """
    from plugins.stats.tennis_box_score import TennisBoxScoreFetcher

    yesterday = _yesterday_from_context(context)
    for tour in ("atp", "wta"):
        fetcher = TennisBoxScoreFetcher(tour=tour)
        _run_tennis_fetch_by_date(fetcher, yesterday)


def _validate_stats_ingestion(**context: Any) -> None:
    """Log a summary of rows ingested across all sports for yesterday.

    Queries ``unified_games`` and ``team_game_stats`` to compare scheduled
    games against rows actually persisted.  Emits an INFO-level report;
    does **not** raise on coverage gaps (informational only).

    Args:
        **context: Airflow task context dictionary.
    """
    from plugins.db_manager import DBManager

    yesterday = _yesterday_from_context(context)
    db = DBManager()

    sports = ["NBA", "NHL", "MLB", "NFL", "EPL", "Ligue1", "NCAAB", "WNCAAB", "Tennis"]

    logger.info("📊 Stats ingestion validation for %s", yesterday)
    for sport in sports:
        scheduled_df = db.fetch_df(
            "SELECT COUNT(*) AS cnt FROM unified_games "
            "WHERE sport = :sport AND game_date = :gdate",
            {"sport": sport, "gdate": str(yesterday)},
        )
        scheduled = int(scheduled_df["cnt"].iloc[0]) if not scheduled_df.empty else 0
        logger.info("  %s — scheduled games: %d", sport, scheduled)

    logger.info("✅ Validation complete for %s", yesterday)


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

with DAG(
    dag_id="historical_stats_daily",
    description=(
        "Daily ingestion of team-level box-score and advanced stats "
        "from public sports APIs into PostgreSQL."
    ),
    schedule="0 8 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["stats", "historical", "multi-sport"],
) as dag:

    fetch_stats_nba = PythonOperator(
        task_id="fetch_stats_nba",
        python_callable=_fetch_stats_nba,
        pool="stats_nba_pool",
        **_DEFAULT_TASK_KWARGS,
    )

    fetch_stats_nhl = PythonOperator(
        task_id="fetch_stats_nhl",
        python_callable=_fetch_stats_nhl,
        pool="stats_nhl_pool",
        **_DEFAULT_TASK_KWARGS,
    )

    fetch_stats_mlb = PythonOperator(
        task_id="fetch_stats_mlb",
        python_callable=_fetch_stats_mlb,
        pool="stats_mlb_pool",
        **_DEFAULT_TASK_KWARGS,
    )

    fetch_stats_nfl = PythonOperator(
        task_id="fetch_stats_nfl",
        python_callable=_fetch_stats_nfl,
        pool="stats_nfl_pool",
        **_DEFAULT_TASK_KWARGS,
    )

    fetch_stats_epl = PythonOperator(
        task_id="fetch_stats_epl",
        python_callable=_fetch_stats_epl,
        pool="stats_fbref_pool",
        **_DEFAULT_TASK_KWARGS,
    )

    fetch_stats_ligue1 = PythonOperator(
        task_id="fetch_stats_ligue1",
        python_callable=_fetch_stats_ligue1,
        pool="stats_fbref_pool",
        **_DEFAULT_TASK_KWARGS,
    )

    fetch_stats_ncaab = PythonOperator(
        task_id="fetch_stats_ncaab",
        python_callable=_fetch_stats_ncaab,
        pool="stats_cbb_pool",
        **_DEFAULT_TASK_KWARGS,
    )

    fetch_stats_wncaab = PythonOperator(
        task_id="fetch_stats_wncaab",
        python_callable=_fetch_stats_wncaab,
        pool="stats_cbb_pool",
        **_DEFAULT_TASK_KWARGS,
    )

    fetch_stats_tennis = PythonOperator(
        task_id="fetch_stats_tennis",
        python_callable=_fetch_stats_tennis,
        pool="stats_tennis_pool",
        **_DEFAULT_TASK_KWARGS,
    )

    validate_stats_ingestion = PythonOperator(
        task_id="validate_stats_ingestion",
        python_callable=_validate_stats_ingestion,
    )

    # All sport tasks must complete before validation
    [
        fetch_stats_nba,
        fetch_stats_nhl,
        fetch_stats_mlb,
        fetch_stats_nfl,
        fetch_stats_epl,
        fetch_stats_ligue1,
        fetch_stats_ncaab,
        fetch_stats_wncaab,
        fetch_stats_tennis,
    ] >> validate_stats_ingestion
