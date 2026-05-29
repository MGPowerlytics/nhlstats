"""Tests for canonical PostgreSQL Elo ratings persistence semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pandas as pd

from plugins.elo.elo_update_helpers import (
    persist_elo_ratings,
    save_elo_ratings,
    seed_active_nhl_elo_ratings,
)
from tests.contracts.fixtures.dashboard_elo_samples import (
    seed_dashboard_rankings_nhl_rows,
)


class InMemoryEloRatingsDB:
    """Small DBManager-compatible test double for elo_ratings writes."""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.executed: list[tuple[str, dict]] = []

    def fetch_df(self, query: str, params: dict | None = None) -> pd.DataFrame:
        params = params or {}
        sport = params["sport"]
        entity_type = params["entity_type"]
        # Extract entity_ids from individual eid_0, eid_1, ... keys
        entity_ids = {
            v for k, v in params.items() if k.startswith("eid_")
        }
        if not entity_ids:
            entity_ids = set(params.get("entity_ids", []))
        active_rows = [
            row.copy()
            for row in self.rows
            if row["sport"] == sport
            and row["entity_type"] == entity_type
            and row["entity_id"] in entity_ids
            and row["valid_to"] is None
        ]
        return pd.DataFrame(active_rows)

    def execute(self, query: str, params: dict | None = None):
        params = params or {}
        self.executed.append((query, params.copy()))
        if query.lstrip().upper().startswith("UPDATE"):
            for row in self.rows:
                if (
                    row["sport"] == params["sport"]
                    and row["entity_type"] == params["entity_type"]
                    and row["entity_id"] == params["entity_id"]
                    and row["valid_to"] is None
                ):
                    row["valid_to"] = params["valid_to"]
            return None
        if query.lstrip().upper().startswith("INSERT"):
            self.rows.append(
                {
                    "sport": params["sport"],
                    "entity_type": params["entity_type"],
                    "entity_id": params["entity_id"],
                    "entity_name": params["entity_name"],
                    "rating": Decimal(str(params["rating"])),
                    "valid_from": params["valid_from"],
                    "valid_to": None,
                    "games_played": params["games_played"],
                    "created_at": params["created_at"],
                }
            )
            return None
        raise AssertionError(f"Unexpected SQL in test double: {query}")


def active_rows(db: InMemoryEloRatingsDB) -> list[dict]:
    return [row for row in db.rows if row["valid_to"] is None]


def test_persist_elo_ratings_inserts_canonical_active_rows() -> None:
    db = InMemoryEloRatingsDB()
    valid_from = datetime(2026, 1, 1, tzinfo=timezone.utc)

    result = persist_elo_ratings(
        "nhl",
        {"BOS": 1550.0, "NYR": 1512.25},
        db=db,
        valid_from=valid_from,
    )

    assert result == {"inserted": 2, "updated": 0, "unchanged": 0}
    assert active_rows(db) == [
        {
            "sport": "NHL",
            "entity_type": "team",
            "entity_id": "BOS",
            "entity_name": "BOS",
            "rating": Decimal("1550.0"),
            "valid_from": valid_from,
            "valid_to": None,
            "games_played": 0,
            "created_at": valid_from,
        },
        {
            "sport": "NHL",
            "entity_type": "team",
            "entity_id": "NYR",
            "entity_name": "NYR",
            "rating": Decimal("1512.25"),
            "valid_from": valid_from,
            "valid_to": None,
            "games_played": 0,
            "created_at": valid_from,
        },
    ]


def test_persist_elo_ratings_is_idempotent_for_unchanged_active_rows() -> None:
    db = InMemoryEloRatingsDB()
    valid_from = datetime(2026, 1, 1, tzinfo=timezone.utc)

    persist_elo_ratings("nhl", {"BOS": 1550.0}, db=db, valid_from=valid_from)
    result = persist_elo_ratings("NHL", {"BOS": 1550.0}, db=db, valid_from=valid_from)

    assert result == {"inserted": 0, "updated": 0, "unchanged": 1}
    assert len(db.rows) == 1
    assert len(active_rows(db)) == 1


def test_persist_elo_ratings_closes_previous_active_row_when_rating_changes() -> None:
    db = InMemoryEloRatingsDB()
    first_valid_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second_valid_from = datetime(2026, 1, 2, tzinfo=timezone.utc)

    persist_elo_ratings("nhl", {"BOS": 1550.0}, db=db, valid_from=first_valid_from)
    result = persist_elo_ratings(
        "nhl",
        {"BOS": 1560.0},
        db=db,
        valid_from=second_valid_from,
    )

    assert result == {"inserted": 1, "updated": 1, "unchanged": 0}
    assert len(db.rows) == 2
    assert db.rows[0]["valid_to"] == second_valid_from
    assert active_rows(db)[0]["rating"] == Decimal("1560.0")


def test_seed_active_nhl_elo_ratings_populates_dashboard_rankings_fixture_rows() -> (
    None
):
    db = InMemoryEloRatingsDB()
    valid_from = datetime(2026, 1, 1, tzinfo=timezone.utc)

    result = seed_active_nhl_elo_ratings(db=db, valid_from=valid_from)

    assert result["inserted"] >= 2
    assert {row["sport"] for row in active_rows(db)} == {"NHL"}
    assert {row["entity_type"] for row in active_rows(db)} == {"team"}
    assert all(row["rating"] > 0 for row in active_rows(db))


def test_dashboard_rankings_fixture_helper_seeds_active_nhl_rows() -> None:
    db = InMemoryEloRatingsDB()

    result = seed_dashboard_rankings_nhl_rows(db)

    assert result["inserted"] >= 2
    assert all(row["sport"] == "NHL" for row in active_rows(db))


def test_save_elo_ratings_preserves_csv_and_xcom_while_persisting_postgres(
    tmp_path,
    monkeypatch,
) -> None:
    db = InMemoryEloRatingsDB()
    elo_instance = Mock()
    elo_instance.ratings = {"BOS": 1550.0, "NYR": 1512.25}
    task_instance = Mock()

    monkeypatch.chdir(tmp_path)

    save_elo_ratings(
        "nhl",
        elo_instance,
        previous_ratings={},
        context={"task_instance": task_instance},
        db=db,
    )

    assert (tmp_path / "data" / "nhl_current_elo_ratings.csv").read_text() == (
        "team,rating\nBOS,1550.00\nNYR,1512.25\n"
    )
    task_instance.xcom_push.assert_called_once_with(
        key="nhl_elo_ratings",
        value={"BOS": 1550.0, "NYR": 1512.25},
    )
    assert {row["entity_id"] for row in active_rows(db)} == {"BOS", "NYR"}
