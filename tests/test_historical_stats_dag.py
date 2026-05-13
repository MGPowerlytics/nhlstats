"""Smoke tests for the historical_stats_daily DAG.

Tests:
    (a) DAG parses without import errors.
    (b) All 9 sport tasks are present with correct task IDs.
    (c) Each sport task has the correct pool assigned.
    (d) Schedule and basic DAG properties are correct.
    (e) Retry / backoff config is applied to each sport task.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from airflow.models import DagBag

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DAG_ID = "historical_stats_daily"
DAG_FOLDER = "dags"

_SPORT_TASKS = [
    "fetch_stats_nba",
    "fetch_stats_nhl",
    "fetch_stats_mlb",
    "fetch_stats_nfl",
    "fetch_stats_epl",
    "fetch_stats_ligue1",
    "fetch_stats_ncaab",
    "fetch_stats_wncaab",
    "fetch_stats_tennis",
]

_EXPECTED_POOLS = {
    "fetch_stats_nba": "stats_nba_pool",
    "fetch_stats_nhl": "stats_nhl_pool",
    "fetch_stats_mlb": "stats_mlb_pool",
    "fetch_stats_nfl": "stats_nfl_pool",
    "fetch_stats_epl": "stats_fbref_pool",
    "fetch_stats_ligue1": "stats_fbref_pool",
    "fetch_stats_ncaab": "stats_cbb_pool",
    "fetch_stats_wncaab": "stats_cbb_pool",
    "fetch_stats_tennis": "stats_tennis_pool",
}


@pytest.fixture(scope="module")
def dag_bag() -> DagBag:
    """Load DAGs from the dags/ folder."""
    return DagBag(dag_folder=DAG_FOLDER, include_examples=False)


@pytest.fixture(scope="module")
def dag(dag_bag: DagBag):
    """Return the historical_stats_daily DAG object."""
    return dag_bag.dags.get(DAG_ID)


# ---------------------------------------------------------------------------
# (a) DAG parses without errors
# ---------------------------------------------------------------------------


def test_dag_parses_without_errors(dag_bag: DagBag) -> None:
    """The DagBag must report zero import errors for historical_stats_daily."""
    errors = dag_bag.import_errors
    assert DAG_ID not in {
        k.replace("dags/", "").replace(".py", "") for k in errors
    }, f"Import errors detected: {errors}"
    assert len(errors) == 0 or all(
        DAG_ID not in str(k) for k in errors
    ), f"historical_stats_daily has import errors: {errors}"


def test_dag_loaded(dag) -> None:
    """The DAG object must be present in the DagBag."""
    assert dag is not None, f"DAG '{DAG_ID}' not found in DagBag"


# ---------------------------------------------------------------------------
# (b) All 9 sport tasks present with correct task_ids
# ---------------------------------------------------------------------------


def test_all_sport_task_ids_present(dag) -> None:
    """All 9 sport fetch tasks must be present in the DAG."""
    assert dag is not None
    task_ids = set(dag.task_ids)
    for task_id in _SPORT_TASKS:
        assert (
            task_id in task_ids
        ), f"Expected task '{task_id}' not found. Present: {sorted(task_ids)}"


def test_validate_task_present(dag) -> None:
    """The downstream validate_stats_ingestion task must exist."""
    assert dag is not None
    assert "validate_stats_ingestion" in dag.task_ids


def test_total_task_count(dag) -> None:
    """DAG must have exactly 10 tasks (9 sport + 1 validation)."""
    assert dag is not None
    assert (
        len(dag.task_ids) == 10
    ), f"Expected 10 tasks, got {len(dag.task_ids)}: {sorted(dag.task_ids)}"


# ---------------------------------------------------------------------------
# (c) Each sport task has the correct pool assigned
# ---------------------------------------------------------------------------


def test_sport_task_pools(dag) -> None:
    """Each sport task must be assigned to its designated pool."""
    assert dag is not None
    for task_id, expected_pool in _EXPECTED_POOLS.items():
        task = dag.get_task(task_id)
        assert task.pool == expected_pool, (
            f"Task '{task_id}': expected pool '{expected_pool}', " f"got '{task.pool}'"
        )


# ---------------------------------------------------------------------------
# (d) Schedule and basic DAG properties
# ---------------------------------------------------------------------------


def test_dag_schedule(dag) -> None:
    """DAG schedule must be '0 8 * * *' (08:00 UTC daily).

    Airflow 3.x exposes the schedule via ``dag.timetable.summary``; Airflow 2.x
    uses ``dag.schedule_interval``.  We check both for compatibility.
    """
    assert dag is not None
    # Airflow 3.x: timetable.summary returns the canonical cron expression.
    schedule = getattr(dag.timetable, "summary", None) or getattr(
        dag, "schedule_interval", getattr(dag, "schedule", None)
    )
    assert schedule == "0 8 * * *", f"Expected schedule '0 8 * * *', got '{schedule}'"


def test_dag_catchup_disabled(dag) -> None:
    """Catchup must be False to avoid backfilling historical runs."""
    assert dag is not None
    assert dag.catchup is False


def test_dag_max_active_runs(dag) -> None:
    """max_active_runs must be 1 to prevent parallel ingestion races."""
    assert dag is not None
    assert dag.max_active_runs == 1


# ---------------------------------------------------------------------------
# (e) Retry / backoff config on each sport task
# ---------------------------------------------------------------------------


def test_sport_tasks_retry_config(dag) -> None:
    """Each sport task must have retries=2 and exponential backoff enabled."""
    assert dag is not None
    for task_id in _SPORT_TASKS:
        task = dag.get_task(task_id)
        assert (
            task.retries == 2
        ), f"Task '{task_id}': expected retries=2, got {task.retries}"
        assert (
            task.retry_exponential_backoff is True
        ), f"Task '{task_id}': expected retry_exponential_backoff=True"
        assert task.retry_delay == timedelta(
            minutes=5
        ), f"Task '{task_id}': expected retry_delay=5min, got {task.retry_delay}"
        assert task.max_retry_delay == timedelta(minutes=30), (
            f"Task '{task_id}': expected max_retry_delay=30min, "
            f"got {task.max_retry_delay}"
        )


# ---------------------------------------------------------------------------
# (f) DAG import sanity — direct module import
# ---------------------------------------------------------------------------


def test_direct_module_import() -> None:
    """``from dags import historical_stats_daily`` must succeed with no errors."""
    import importlib

    mod = importlib.import_module("dags.historical_stats_daily")
    assert hasattr(mod, "dag"), "Module must expose a 'dag' object"


# ---------------------------------------------------------------------------
# (g) _run_sport_fetch_by_date remap logic — unit tests
# ---------------------------------------------------------------------------


class _FakeFetcher:
    """Minimal fetcher stub for remap unit tests."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.upserted: list[dict] = []

    def fetch_date_range(self, start, end):  # noqa: D401
        return list(self._rows)

    def upsert_rows(self, rows: list[dict]) -> int:
        self.upserted = rows
        return len(rows)


def test_remap_replaces_native_ids(monkeypatch) -> None:
    """_run_sport_fetch_by_date must remap native game IDs to unified IDs."""
    import importlib
    from datetime import date

    mod = importlib.import_module("dags.historical_stats_daily")

    unified_rows = [
        {
            "game_id": "NHL_20260423_BOS_BUF",
            "home_team_id": "BOS",
            "away_team_id": "BUF",
        }
    ]

    import pandas as pd

    fake_df = pd.DataFrame(unified_rows)

    class _FakeDB:
        def fetch_df(self, query, params):
            return fake_df

    monkeypatch.setattr("plugins.db_manager.DBManager", _FakeDB)

    native_rows = [
        {
            "game_id": "2026030101",
            "sport": "NHL",
            "team": "BOS",
            "opponent": "BUF",
            "is_home": True,
            "game_date": "2026-04-23",
            "season": "2026",
            "points_for": 4,
            "points_against": 2,
            "won": True,
            "margin": 2,
            "ext": {"game_id": "2026030101", "team": "BOS"},
        },
        {
            "game_id": "2026030101",
            "sport": "NHL",
            "team": "BUF",
            "opponent": "BOS",
            "is_home": False,
            "game_date": "2026-04-23",
            "season": "2026",
            "points_for": 2,
            "points_against": 4,
            "won": False,
            "margin": -2,
            "ext": {"game_id": "2026030101", "team": "BUF"},
        },
    ]
    fetcher = _FakeFetcher(native_rows)

    mod._run_sport_fetch_by_date(fetcher, "NHL", date(2026, 4, 23))

    assert len(fetcher.upserted) == 2
    for row in fetcher.upserted:
        assert (
            row["game_id"] == "NHL_20260423_BOS_BUF"
        ), f"Expected unified ID, got {row['game_id']!r}"
        assert row["ext"]["game_id"] == "NHL_20260423_BOS_BUF"


def test_remap_no_unified_games_skips_gracefully(monkeypatch) -> None:
    """_run_sport_fetch_by_date must return early when unified_games is empty."""
    import importlib
    from datetime import date

    import pandas as pd

    mod = importlib.import_module("dags.historical_stats_daily")

    class _FakeDB:
        def fetch_df(self, query, params):
            return pd.DataFrame()

    monkeypatch.setattr("plugins.db_manager.DBManager", _FakeDB)

    fetcher = _FakeFetcher(
        [{"game_id": "2026030101", "team": "BOS", "opponent": "BUF", "is_home": True}]
    )
    mod._run_sport_fetch_by_date(fetcher, "NHL", date(2026, 4, 23))
    # upsert_rows should never be called
    assert fetcher.upserted == []


def test_remap_raises_when_all_unmapped(monkeypatch) -> None:
    """_run_sport_fetch_by_date must raise RuntimeError when 0 rows can be mapped."""
    import importlib
    from datetime import date

    import pandas as pd

    mod = importlib.import_module("dags.historical_stats_daily")

    unified_rows = [
        {
            "game_id": "NHL_20260423_BOS_BUF",
            "home_team_id": "BOS",
            "away_team_id": "BUF",
        }
    ]

    class _FakeDB:
        def fetch_df(self, query, params):
            return pd.DataFrame(unified_rows)

    monkeypatch.setattr("plugins.db_manager.DBManager", _FakeDB)

    # Row has wrong team abbreviations — won't match lookup
    bad_rows = [
        {
            "game_id": "2026030101",
            "team": "MTL",
            "opponent": "TOR",
            "is_home": True,
            "ext": {},
        }
    ]
    fetcher = _FakeFetcher(bad_rows)

    with pytest.raises(RuntimeError, match="none matched unified_games"):
        mod._run_sport_fetch_by_date(fetcher, "NHL", date(2026, 4, 23))


# ---------------------------------------------------------------------------
# (h) _run_tennis_fetch_by_date remap logic — unit tests
# ---------------------------------------------------------------------------


class _FakeTennisFetcher:
    """Minimal tennis fetcher stub."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.upserted: list[dict] = []

    def fetch_date_range(self, start, end):  # noqa: D401
        return list(self._rows)

    def upsert_rows(self, rows: list[dict]) -> int:
        self.upserted = rows
        return len(rows)


def test_tennis_remap_replaces_sackmann_ids(monkeypatch) -> None:
    """_run_tennis_fetch_by_date must remap Sackmann IDs to unified TENNIS_ IDs."""
    import importlib
    from datetime import date

    import pandas as pd

    mod = importlib.import_module("dags.historical_stats_daily")

    unified_rows = pd.DataFrame(
        [{"game_id": "TENNIS_WTA_2026-04-23_ElenaRybakina_ElenaGabrielaRuse"}]
    )

    class _FakeDB:
        def fetch_df(self, query, params):
            return unified_rows

    monkeypatch.setattr("plugins.db_manager.DBManager", _FakeDB)

    sackmann_rows = [
        {
            "game_id": "wta_2026-560_R64_0001",
            "player_name": "Elena Rybakina",
            "won": True,
        },
        {
            "game_id": "wta_2026-560_R64_0001",
            "player_name": "Elena Gabriela Ruse",
            "won": False,
        },
    ]
    fetcher = _FakeTennisFetcher(sackmann_rows)

    mod._run_tennis_fetch_by_date(fetcher, date(2026, 4, 23))

    assert len(fetcher.upserted) == 2
    for row in fetcher.upserted:
        assert row["game_id"] == "TENNIS_WTA_2026-04-23_ElenaRybakina_ElenaGabrielaRuse"


def test_tennis_remap_no_unified_games_returns_early(monkeypatch) -> None:
    """_run_tennis_fetch_by_date returns without error when unified_games is empty."""
    import importlib
    from datetime import date

    import pandas as pd

    mod = importlib.import_module("dags.historical_stats_daily")

    class _FakeDB:
        def fetch_df(self, query, params):
            return pd.DataFrame()

    monkeypatch.setattr("plugins.db_manager.DBManager", _FakeDB)

    fetcher = _FakeTennisFetcher(
        [{"game_id": "wta_2026-560_R64_0001", "player_name": "A", "won": True}]
    )
    mod._run_tennis_fetch_by_date(fetcher, date(2026, 4, 23))
    assert fetcher.upserted == []


def test_tennis_remap_no_sackmann_rows_returns_early(monkeypatch) -> None:
    """_run_tennis_fetch_by_date returns without error when Sackmann returns 0 rows."""
    import importlib
    from datetime import date

    import pandas as pd

    mod = importlib.import_module("dags.historical_stats_daily")

    unified_rows = pd.DataFrame(
        [{"game_id": "TENNIS_WTA_2026-04-23_ElenaRybakina_ElenaGabrielaRuse"}]
    )

    class _FakeDB:
        def fetch_df(self, query, params):
            return unified_rows

    monkeypatch.setattr("plugins.db_manager.DBManager", _FakeDB)

    fetcher = _FakeTennisFetcher([])  # Sackmann returns nothing
    mod._run_tennis_fetch_by_date(fetcher, date(2026, 4, 23))
    assert fetcher.upserted == []


def test_tennis_remap_unmatched_names_warns_but_does_not_raise(monkeypatch) -> None:
    """_run_tennis_fetch_by_date logs a warning but does NOT raise when slugs don't match."""
    import importlib
    from datetime import date

    import pandas as pd

    mod = importlib.import_module("dags.historical_stats_daily")

    unified_rows = pd.DataFrame(
        [{"game_id": "TENNIS_WTA_2026-04-23_ElenaRybakina_ElenaGabrielaRuse"}]
    )

    class _FakeDB:
        def fetch_df(self, query, params):
            return unified_rows

    monkeypatch.setattr("plugins.db_manager.DBManager", _FakeDB)

    # Sackmann returns rows with completely different player names
    sackmann_rows = [
        {"game_id": "wta_2026-560_R64_0002", "player_name": "Iga Swiatek", "won": True},
        {
            "game_id": "wta_2026-560_R64_0002",
            "player_name": "Aryna Sabalenka",
            "won": False,
        },
    ]
    fetcher = _FakeTennisFetcher(sackmann_rows)

    # Must NOT raise — graceful degradation
    mod._run_tennis_fetch_by_date(fetcher, date(2026, 4, 23))
    assert fetcher.upserted == []


def test_fetch_stats_tennis_runs_both_tours(monkeypatch) -> None:
    """The scheduled tennis task must ingest both ATP and WTA stats."""
    import importlib
    from datetime import date

    mod = importlib.import_module("dags.historical_stats_daily")
    calls: list[tuple[str, date]] = []

    class _FakeTennisFetcher:
        def __init__(self, tour: str = "atp") -> None:
            self.tour = tour

    def _fake_run(fetcher, game_date):
        calls.append((fetcher.tour, game_date))

    monkeypatch.setattr(
        "plugins.stats.tennis_box_score.TennisBoxScoreFetcher", _FakeTennisFetcher
    )
    monkeypatch.setattr(mod, "_run_tennis_fetch_by_date", _fake_run)

    mod._fetch_stats_tennis(ds="2026-04-23")

    assert calls == [("atp", date(2026, 4, 23)), ("wta", date(2026, 4, 23))]
