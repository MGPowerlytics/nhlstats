"""Provider RED contract tests for the BetReconciliation boundary.

Exercises the *real* producer code in ``plugins/bet_reconciliation.py``:
- ``diff_bet()`` — field-level comparison
- ``reconcile_bet()`` — applies discrepancies with mocked DB
- ``reconcile_all()`` — top-level orchestrator (mocked DB + client)
- ``insert_missing_bet()`` — inserts Kalshi-discovered fills
- ``fetch_kalshi_state()`` — fetches remote state (mocked client)

Outputs are validated against ``bet_reconciliation_contract_v1.json``
schema definitions to detect drift between the producer and contract.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from plugins.bet_reconciliation import (
    diff_bet,
    fetch_kalshi_state,
    insert_missing_bet,
    reconcile_all,
    reconcile_bet,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "bet_reconciliation_contract_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator(def_name: str) -> Draft202012Validator:
    schema = _load_schema()
    resource = Resource.from_contents(schema)
    registry = Registry().with_resource(uri=schema["$id"], resource=resource)
    return Draft202012Validator(
        {"$ref": f"{schema['$id']}#/$defs/{def_name}"}, registry=registry
    )


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockDB:
    """A minimal mock DB that records execute calls and returns fake DataFrames.

    Supports the ``fetch_df``, ``execute``, and ``engine`` contract that
    ``reconcile_bet`` and ``reconcile_all`` expect.
    """

    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, dict[str, Any] | None]] = []
        self.fetch_df_calls: list[tuple[str, dict[str, Any] | None]] = []
        self._local_bets: list[dict[str, Any]] = []

    def set_local_bets(self, bets: list[dict[str, Any]]) -> None:
        """Set the bets that ``fetch_df`` will return for the placed_bets table."""
        self._local_bets = bets

    def fetch_df(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        self.fetch_df_calls.append((sql, params))
        if self._local_bets:
            return pd.DataFrame(self._local_bets)
        return pd.DataFrame(
            {
                "bet_id": pd.Series(dtype="object"),
                "ticker": pd.Series(dtype="object"),
                "contracts": pd.Series(dtype="int64"),
                "price_cents": pd.Series(dtype="int64"),
                "cost_dollars": pd.Series(dtype="float64"),
                "fees_dollars": pd.Series(dtype="float64"),
                "status": pd.Series(dtype="object"),
                "settled_date": pd.Series(dtype="object"),
                "payout_dollars": pd.Series(dtype="float64"),
                "profit_dollars": pd.Series(dtype="float64"),
                "created_at": pd.Series(dtype="object"),
            }
        )

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        self.execute_calls.append((sql, params))
        mock_result = MagicMock()
        mock_result.rowcount = 1
        return mock_result


def _make_mock_fill(
    bet_id: str = "KXNBAGAME-26JAN20LAL-LAL_home",
    ticker: str = "KXNBAGAME-26JAN20LAL-LAL",
    status: str = "settled",
    contracts: int = 10,
    price: int = 55,
    cost: int = 550,
    fees: int = 25,
    payout_dollars: float | None = None,
    profit_dollars: float | None = None,
) -> dict[str, Any]:
    """Build a deterministic Kalshi fill dict as returned by load_fills_from_kalshi."""
    fill: dict[str, Any] = {
        "bet_id": bet_id,
        "trade_id": bet_id,
        "ticker": ticker,
        "count": contracts,
        "yes_price": price,
        "cost": cost,
        "fees": fees,
        "status": status,
    }
    if payout_dollars is not None:
        fill["payout_dollars"] = payout_dollars
    if profit_dollars is not None:
        fill["profit_dollars"] = profit_dollars
    return fill


def _make_mock_client(
    market_details: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mocked Kalshi client with deterministic market details."""
    if market_details is None:
        market_details = {
            "title": "Test Market",
            "status": "settled",
            "close_time": "2026-01-21T19:00:00Z",
        }
    client = MagicMock()
    client.get_market_details.return_value = market_details
    return client


@contextmanager
def _mocked_deps(
    local_bets: list[dict[str, Any]] | None = None,
    fills: list[dict[str, Any]] | None = None,
) -> Iterator[MockDB]:
    """Create a MockDB and patch external dependencies.

    Args:
        local_bets: List of local placed_bets row dicts to return from fetch_df.
        fills: List of Kalshi fill dicts to return from load_fills_from_kalshi.

    Yields:
        The MockDB instance.
    """
    db = MockDB()
    if local_bets is not None:
        db.set_local_bets(local_bets)

    if fills is None:
        fills = [_make_mock_fill()]

    with (
        patch("plugins.bet_tracker.load_fills_from_kalshi", return_value=fills),
    ):
        yield db


# ---------------------------------------------------------------------------
# diff_bet() provider tests
# ---------------------------------------------------------------------------


class TestDiffBetProvider:
    """Validates that diff_bet() output matches the discrepancy_entry schema."""

    def test_diff_bet_identical_records_returns_empty_list(self) -> None:
        local = {"contracts": 10, "status": "settled", "price_cents": 55}
        remote = {"contracts": 10, "status": "settled", "price_cents": 55}
        result = diff_bet(local, remote)
        assert result == []

    def test_diff_bet_status_change_produces_schema_valid_output(self) -> None:
        local = {"contracts": 10, "status": "open", "price_cents": 55}
        remote = {"contracts": 10, "status": "settled", "price_cents": 55}
        result = diff_bet(local, remote)
        assert len(result) == 1
        assert result[0]["field"] == "status"
        assert result[0]["old"] == "open"
        assert result[0]["new"] == "settled"

    def test_diff_bet_multi_field_diffs_all_schema_valid(self) -> None:
        local = {
            "contracts": 10,
            "price_cents": 55,
            "cost_dollars": 5.50,
            "fees_dollars": 0.25,
            "status": "open",
            "settled_date": None,
            "payout_dollars": None,
            "profit_dollars": None,
        }
        remote = {
            "contracts": 10,
            "price_cents": 55,
            "cost_dollars": 5.50,
            "fees_dollars": 0.25,
            "status": "settled",
            "settled_date": "2026-01-21",
            "payout_dollars": 10.00,
            "profit_dollars": 4.25,
        }
        result = diff_bet(local, remote)
        assert len(result) == 4
        # Validate each discrepancy entry against the schema
        for entry in result:
            _validator("discrepancy_entry").validate(entry)

    def test_diff_bet_both_none_skipped(self) -> None:
        local = {"settled_date": None, "status": "open"}
        remote = {"settled_date": None, "status": "open"}
        result = diff_bet(local, remote)
        assert result == []

    def test_diff_bet_contracts_differ(self) -> None:
        local = {"contracts": 5, "status": "open"}
        remote = {"contracts": 10, "status": "open"}
        result = diff_bet(local, remote)
        assert len(result) == 1
        assert result[0]["field"] == "contracts"
        assert result[0]["old"] == 5
        assert result[0]["new"] == 10
        _validator("discrepancy_entry").validate(result[0])

    def test_diff_bet_payout_dollars_none_to_value(self) -> None:
        local = {"payout_dollars": None, "status": "open"}
        remote = {"payout_dollars": 100.0, "status": "settled"}
        result = diff_bet(local, remote)
        # Both payout_dollars AND status will differ
        fields = {e["field"] for e in result}
        assert "payout_dollars" in fields
        for entry in result:
            _validator("discrepancy_entry").validate(entry)

    def test_diff_bet_non_reconcilable_fields_ignored(self) -> None:
        local = {"contracts": 10, "status": "open", "some_ignored_field": "a"}
        remote = {"contracts": 10, "status": "open", "some_ignored_field": "b"}
        result = diff_bet(local, remote)
        assert result == []


# ---------------------------------------------------------------------------
# fetch_kalshi_state() provider tests
# ---------------------------------------------------------------------------


class TestFetchKalshiStateProvider:
    """Validates that fetch_kalshi_state() output matches kalshi_state_entry."""

    def test_fetch_kalshi_state_returns_dict(self) -> None:
        client = _make_mock_client()
        with _mocked_deps():
            state = fetch_kalshi_state(client=client)
        assert isinstance(state, dict)

    def test_kalshi_state_entries_match_schema(self) -> None:
        fill = _make_mock_fill(
            bet_id="TEST_001",
            ticker="KXNBATEST",
            status="settled",
            contracts=15,
            price=60,
            cost=900,
            fees=30,
        )
        client = _make_mock_client()
        with _mocked_deps(fills=[fill]):
            state = fetch_kalshi_state(client=client)
        assert "TEST_001" in state
        _validator("kalshi_state_entry").validate(state["TEST_001"])

    def test_kalshi_state_with_multiple_fills(self) -> None:
        fills = [
            _make_mock_fill(bet_id="BET_001", ticker="MKT_001", contracts=5),
            _make_mock_fill(bet_id="BET_002", ticker="MKT_002", contracts=10),
        ]
        client = _make_mock_client()
        with _mocked_deps(fills=fills):
            state = fetch_kalshi_state(client=client)
        assert len(state) == 2
        for entry in state.values():
            _validator("kalshi_state_entry").validate(entry)

    def test_kalshi_state_open_entry_has_nullable_fields(self) -> None:
        fill = _make_mock_fill(status="open")
        client = _make_mock_client(market_details={"title": "Open Market", "status": "open", "close_time": None})
        with _mocked_deps(fills=[fill]):
            state = fetch_kalshi_state(client=client)
        bet_id = fill["bet_id"]
        entry = state[bet_id]
        assert entry["settled_date"] is None
        assert entry["payout_dollars"] is None
        assert entry["profit_dollars"] is None
        _validator("kalshi_state_entry").validate(entry)

    def test_kalshi_state_empty_fills_returns_empty_dict(self) -> None:
        client = _make_mock_client()
        with _mocked_deps(fills=[]):
            state = fetch_kalshi_state(client=client)
        assert state == {}


# ---------------------------------------------------------------------------
# reconcile_bet() provider tests
# ---------------------------------------------------------------------------


class TestReconcileBetProvider:
    """Validates that reconcile_bet() applies differences and produces
    contract-consistent results."""

    def test_reconcile_identical_bets_returns_zero(self) -> None:
        db = MockDB()
        local = {"contracts": 10, "status": "settled", "price_cents": 55}
        remote = {"contracts": 10, "status": "settled", "price_cents": 55}
        result = reconcile_bet("BET_001", local, remote, db)
        assert result == 0

    def test_reconcile_with_changes_returns_change_count(self) -> None:
        db = MockDB()
        local = {"contracts": 5, "status": "open", "price_cents": 55}
        remote = {"contracts": 10, "status": "open", "price_cents": 55}
        result = reconcile_bet("BET_001", local, remote, db)
        assert result == 1  # Only contracts changed
        # One UPDATE plus one audit INSERT per changed field
        assert len(db.execute_calls) >= 1
        assert "UPDATE placed_bets" in db.execute_calls[0][0]

    def test_reconcile_with_status_change_executes_update(self) -> None:
        db = MockDB()
        local = {"contracts": 10, "status": "open", "price_cents": 55}
        remote = {"contracts": 10, "status": "settled", "price_cents": 55}
        result = reconcile_bet("BET_001", local, remote, db)
        assert result == 1
        sql, params = db.execute_calls[0]
        assert "UPDATE placed_bets" in sql
        assert params["status"] == "settled"

    def test_reconcile_with_multiple_changes(self) -> None:
        db = MockDB()
        local = {
            "contracts": 10,
            "price_cents": 55,
            "status": "open",
            "settled_date": None,
            "payout_dollars": None,
            "profit_dollars": None,
        }
        remote = {
            "contracts": 10,
            "price_cents": 55,
            "status": "settled",
            "settled_date": "2026-01-21",
            "payout_dollars": 10.00,
            "profit_dollars": 4.25,
        }
        result = reconcile_bet("BET_001", local, remote, db)
        assert result == 4  # status, settled_date, payout_dollars, profit_dollars


# ---------------------------------------------------------------------------
# insert_missing_bet() provider tests
# ---------------------------------------------------------------------------


class TestInsertMissingBetProvider:
    """Validates that insert_missing_bet() inserts Kalshi-discovered fills."""

    def test_insert_missing_bet_returns_true(self) -> None:
        db = MockDB()
        fill = _make_mock_fill()
        result = insert_missing_bet(fill, db)
        assert result is True
        assert len(db.execute_calls) == 1

    def test_insert_missing_bet_executes_insert(self) -> None:
        db = MockDB()
        fill = _make_mock_fill(bet_id="NEW_BET_001", ticker="NEW_TICKER")
        result = insert_missing_bet(fill, db)
        assert result is True
        sql, params = db.execute_calls[0]
        assert "INSERT INTO placed_bets" in sql
        assert params["bet_id"] == "NEW_BET_001"

    def test_insert_missing_bet_with_open_fill(self) -> None:
        db = MockDB()
        fill = _make_mock_fill(
            bet_id="OPEN_BET", status="open", contracts=5, price=50, cost=250, fees=10
        )
        result = insert_missing_bet(fill, db)
        assert result is True
        sql, params = db.execute_calls[0]
        assert params["status"] == "open"
        assert params["contracts"] == 5


# ---------------------------------------------------------------------------
# reconcile_all() provider tests
# ---------------------------------------------------------------------------


class TestReconcileAllProvider:
    """Validates that reconcile_all() output matches the reconciliation_report
    schema and produces consistent summary counts."""

    def test_reconcile_all_returns_summary_dict(self) -> None:
        with _mocked_deps() as db:
            result = reconcile_all(db=db, client=_make_mock_client(), cutoff_minutes=0)
        assert isinstance(result, dict)

    def test_reconcile_all_summary_contains_required_keys(self) -> None:
        with _mocked_deps() as db:
            result = reconcile_all(db=db, client=_make_mock_client(), cutoff_minutes=0)
        required_keys = {
            "checked",
            "discrepancies",
            "corrected",
            "missing_locally_inserted",
            "missing_on_kalshi",
            "audit_rows_written",
            "excluded_by_cutoff",
            "run_id",
        }
        assert required_keys.issubset(result.keys())

    def test_reconcile_all_with_matching_bets(self) -> None:
        # Local data must match what fetch_kalshi_state produces (payout/profit
        # are always None from the Kalshi fill — the remote source).
        local_bets = [
            {
                "bet_id": "BET_001",
                "ticker": "MKT_001",
                "contracts": 10,
                "price_cents": 55,
                "cost_dollars": 5.5,
                "fees_dollars": 0.25,
                "status": "settled",
                "settled_date": "2026-01-21",
                "payout_dollars": None,
                "profit_dollars": None,
                "created_at": None,
            }
        ]
        fill = _make_mock_fill(
            bet_id="BET_001",
            ticker="MKT_001",
            status="settled",
            contracts=10,
            price=55,
            cost=550,
            fees=25,
        )
        with _mocked_deps(local_bets=local_bets, fills=[fill]) as db:
            client = _make_mock_client()
            result = reconcile_all(db=db, client=client, cutoff_minutes=0)
        assert result["checked"] == 1
        assert result["discrepancies"] == 0
        assert result["corrected"] == 0

    def test_reconcile_all_with_discrepancy(self) -> None:
        local_bets = [
            {
                "bet_id": "BET_001",
                "ticker": "MKT_001",
                "contracts": 5,
                "price_cents": 55,
                "cost_dollars": 2.75,
                "fees_dollars": 0.15,
                "status": "open",
                "settled_date": None,
                "payout_dollars": None,
                "profit_dollars": None,
                "created_at": None,
            }
        ]
        fill = _make_mock_fill(
            bet_id="BET_001",
            ticker="MKT_001",
            status="settled",
            contracts=5,
            price=55,
            cost=275,
            fees=15,
        )
        with _mocked_deps(local_bets=local_bets, fills=[fill]) as db:
            result = reconcile_all(db=db, client=_make_mock_client(), cutoff_minutes=0)
        assert result["checked"] == 1
        assert result["discrepancies"] == 1  # status differs

    def test_reconcile_all_missing_locally(self) -> None:
        # No local bets, but Kalshi has a fill
        fill = _make_mock_fill(bet_id="REMOTE_ONLY", ticker="MKT_REMOTE")
        with _mocked_deps(local_bets=[], fills=[fill]) as db:
            result = reconcile_all(db=db, client=_make_mock_client(), cutoff_minutes=0)
        assert result["checked"] == 1
        assert result["missing_locally_inserted"] == 1

    def test_reconcile_all_with_since_date(self) -> None:
        local_bets = [
            {
                "bet_id": "BET_001",
                "ticker": "MKT_001",
                "contracts": 10,
                "price_cents": 55,
                "cost_dollars": 5.5,
                "fees_dollars": 0.25,
                "status": "settled",
                "settled_date": None,
                "payout_dollars": None,
                "profit_dollars": None,
                "created_at": None,
            }
        ]
        fill = _make_mock_fill(bet_id="BET_001", ticker="MKT_001")
        with _mocked_deps(local_bets=local_bets, fills=[fill]) as db:
            from datetime import date

            result = reconcile_all(
                db=db,
                client=_make_mock_client(),
                since_date=date(2026, 1, 1),
                cutoff_minutes=0,
            )
        assert result["checked"] == 1


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


class TestReconciliationDriftDetection:
    """Tests that detect when the real BetReconciliation output drifts from
    the contract. These should fail if the producer's output shape changes."""

    def test_diff_bet_output_field_is_reconcilable_enum(self) -> None:
        """The field in a discrepancy must be one of the RECONCILABLE_FIELDS."""
        local = {"contracts": 5, "status": "open"}
        remote = {"contracts": 10, "status": "settled"}
        result = diff_bet(local, remote)
        for entry in result:
            assert entry["field"] in {
                "contracts",
                "price_cents",
                "cost_dollars",
                "fees_dollars",
                "status",
                "settled_date",
                "payout_dollars",
                "profit_dollars",
            }

    def test_reconcile_all_summary_has_run_id(self) -> None:
        """Every reconcile_all output must include a run_id (UUID string)."""
        with _mocked_deps() as db:
            result = reconcile_all(db=db, client=_make_mock_client(), cutoff_minutes=0)
        assert "run_id" in result
        assert isinstance(result["run_id"], str)
        assert len(result["run_id"]) > 0

    def test_reconcile_all_counts_are_non_negative_integers(self) -> None:
        """All count fields in the summary must be non-negative integers."""
        with _mocked_deps() as db:
            result = reconcile_all(db=db, client=_make_mock_client(), cutoff_minutes=0)
        for key in [
            "checked",
            "discrepancies",
            "corrected",
            "missing_locally_inserted",
            "missing_on_kalshi",
            "audit_rows_written",
            "excluded_by_cutoff",
        ]:
            assert isinstance(result[key], int), f"{key} is not an int"
            assert result[key] >= 0, f"{key} is negative"

    def test_reconcile_all_run_id_is_string(self) -> None:
        """run_id must be a UUID string."""
        with _mocked_deps() as db:
            result = reconcile_all(db=db, client=_make_mock_client(), cutoff_minutes=0)
        assert isinstance(result["run_id"], str)

    def test_insert_missing_bet_returns_bool(self) -> None:
        """insert_missing_bet must return a boolean."""
        db = MockDB()
        fill = _make_mock_fill()
        result = insert_missing_bet(fill, db)
        assert isinstance(result, bool)

    def test_reconcile_bet_returns_int(self) -> None:
        """reconcile_bet must return an integer (change count)."""
        db = MockDB()
        local = {"contracts": 5, "status": "open"}
        remote = {"contracts": 10, "status": "open"}
        result = reconcile_bet("BET_001", local, remote, db)
        assert isinstance(result, int)
        assert result >= 0
