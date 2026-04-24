"""Wave-3 MLB persisted-row provider coverage marker.

Coverage for ``mlb_mlb_games_row_v1`` and ``mlb_unified_game_row_v1`` is
folded into :mod:`tests.contracts.test_mlb_ingestion_provider` because the
real producer (``NHLDatabaseLoader._load_mlb_schedule``) writes both rows in
the same call from a single MLB Stats API schedule record. Splitting the
provider tests across two modules would require duplicating the loader
fixture and re-running the same producer code path twice.

This file exists so the Wave-3 deliverable matches the plan's named test
modules; the real assertions live next to the schedule ingestion tests.
"""

from __future__ import annotations


def test_mlb_db_row_provider_coverage_is_in_ingestion_module() -> None:
    """Sentinel: the real persistence assertions live in the ingestion module."""
    from tests.contracts import test_mlb_ingestion_provider

    assert hasattr(
        test_mlb_ingestion_provider,
        "test_load_mlb_schedule_emits_contract_valid_mlb_games_row",
    )
    assert hasattr(
        test_mlb_ingestion_provider,
        "test_load_mlb_schedule_emits_contract_valid_unified_games_row",
    )
