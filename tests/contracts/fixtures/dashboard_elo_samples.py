"""Fixture helpers for dashboard Elo read-model provider tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from plugins.elo.elo_update_helpers import seed_active_nhl_elo_ratings


def seed_dashboard_rankings_nhl_rows(
    db: Any,
    *,
    valid_from: datetime | None = None,
) -> dict[str, int]:
    """Populate non-empty active NHL Elo rows for dashboard_rankings_v1 tests."""
    return seed_active_nhl_elo_ratings(
        db=db,
        valid_from=valid_from or datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
