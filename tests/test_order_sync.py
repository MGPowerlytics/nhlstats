"""TDD coverage for order-aware sync of Kalshi orders into placed_bets.

The existing fill-driven sync (``sync_bets_to_database``) only persists
trades after Kalshi reports them on the fills endpoint. Orders that are
``resting`` on the book and orders whose fills have not yet propagated to
``/portfolio/fills`` would not appear in ``placed_bets`` until much later,
which is exactly the persistence gap that left today's MLB and EPL live
orders missing from Postgres.

These tests pin the behaviour of the new order-driven sync path:
* ``load_orders_from_kalshi`` paginates the orders endpoint.
* ``sync_orders_to_database`` upserts each order into ``placed_bets``
  keyed by ``order_id`` so the row exists immediately after placement,
  regardless of whether the order is ``executed`` or ``resting``.
"""

from __future__ import annotations

from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def sample_orders() -> List[Dict]:
    """Return a representative pair of MLB + EPL orders.

    Mirrors the live response observed on 2026-04-22:
    one ``executed`` MLB order and one ``resting`` EPL order.
    """
    return [
        {
            "order_id": "678eb389-22c1-4aa3-aa9b-f477c87c1458",
            "client_order_id": "92d80c20-65f6-4d75-b59b-79284280f99d",
            "ticker": "KXMLBGAME-26APR231910MINNYM-MIN",
            "side": "yes",
            "action": "buy",
            "status": "executed",
            "yes_price_dollars": "0.4900",
            "no_price_dollars": "0.5100",
            "initial_count_fp": "4.00",
            "fill_count_fp": "4.00",
            "remaining_count_fp": "0.00",
            "taker_fill_cost_dollars": "1.880000",
            "taker_fees_dollars": "0.070000",
            "created_time": "2026-04-22T11:09:52.761837Z",
        },
        {
            "order_id": "f3ef09d8-a003-4602-ad34-99495a311b67",
            "client_order_id": "8a1f1bd2-b50a-4405-a699-d60526608aff",
            "ticker": "KXEPLGAME-26MAY04CFCNFO-NFO",
            "side": "yes",
            "action": "buy",
            "status": "resting",
            "yes_price_dollars": "0.2300",
            "no_price_dollars": "0.7700",
            "initial_count_fp": "9.00",
            "fill_count_fp": "0.00",
            "remaining_count_fp": "9.00",
            "taker_fill_cost_dollars": "0.000000",
            "taker_fees_dollars": "0.000000",
            "created_time": "2026-04-22T11:00:51.234504Z",
        },
    ]


def test_load_orders_from_kalshi_paginates_until_empty_cursor(sample_orders):
    """``load_orders_from_kalshi`` must follow Kalshi's cursor pagination."""
    from plugins.bet_tracker import load_orders_from_kalshi

    page_one, page_two = sample_orders[:1], sample_orders[1:]
    responses = [
        {"orders": page_one, "cursor": "next-page"},
        {"orders": page_two, "cursor": ""},
    ]
    client = MagicMock()
    client._get.side_effect = responses

    orders = load_orders_from_kalshi(client)

    assert orders == page_one + page_two
    assert client._get.call_count == 2
    # Second call must include the cursor we received from page one.
    second_call_path = client._get.call_args_list[1].args[0]
    assert "cursor=next-page" in second_call_path


def test_load_orders_from_kalshi_breaks_on_repeated_cursor():
    """Pagination must guard against Kalshi returning the same cursor twice."""
    from plugins.bet_tracker import load_orders_from_kalshi

    client = MagicMock()
    client._get.side_effect = [
        {"orders": [{"order_id": "a"}], "cursor": "loop"},
        {"orders": [{"order_id": "b"}], "cursor": "loop"},
    ]

    with pytest.raises(RuntimeError, match="repeated cursor"):
        load_orders_from_kalshi(client)


def test_sync_orders_to_database_upserts_one_row_per_order(sample_orders):
    """Each Kalshi order must produce exactly one upsert keyed by order_id."""
    from plugins.bet_tracker import sync_orders_to_database

    client = MagicMock()
    db = MagicMock()
    db.fetch_df.return_value = MagicMock(empty=True)

    with patch(
        "plugins.bet_tracker.load_orders_from_kalshi",
        return_value=sample_orders,
    ):
        with patch("plugins.bet_tracker.get_market_status", return_value={}):
            with patch("plugins.bet_tracker.backfill_bet_metrics"):
                with patch(
                    "plugins.bet_tracker._ensure_bets_table_exists"
                ):
                    added, updated = sync_orders_to_database(
                        db=db, client=client
                    )

    assert added == 2
    assert updated == 0

    # Every execute() must use the order_id as bet_id and tag rows with source='system'.
    insert_calls = [
        call for call in db.execute.call_args_list
        if "INSERT INTO placed_bets" in str(call.args[0])
    ]
    assert len(insert_calls) == 2

    bet_ids = sorted(call.args[1]["bet_id"] for call in insert_calls)
    assert bet_ids == sorted(o["order_id"] for o in sample_orders)

    for call in insert_calls:
        params = call.args[1]
        assert params["source"] == "system"
        assert params["status"] == "open"


def test_sync_orders_maps_resting_executed_canceled_to_local_status(sample_orders):
    """Status mapping must collapse Kalshi states into the local ``status`` enum."""
    from plugins.bet_tracker import _order_status_to_local

    assert _order_status_to_local("executed") == "open"
    assert _order_status_to_local("resting") == "open"
    assert _order_status_to_local("canceled") == "canceled"
    assert _order_status_to_local("cancelled") == "canceled"
    # Unknown statuses fall through as-is so reconciliation can pick them up.
    assert _order_status_to_local("partially_filled") == "open"


def test_sync_orders_extracts_sport_from_ticker(sample_orders):
    """Order rows must populate ``sport`` from the ticker prefix."""
    from plugins.bet_tracker import sync_orders_to_database

    client = MagicMock()
    db = MagicMock()
    db.fetch_df.return_value = MagicMock(empty=True)

    captured_params: List[Dict] = []
    db.execute.side_effect = lambda sql, params=None: captured_params.append(
        params or {}
    )

    with patch(
        "plugins.bet_tracker.load_orders_from_kalshi",
        return_value=sample_orders,
    ):
        with patch("plugins.bet_tracker.get_market_status", return_value={}):
            with patch("plugins.bet_tracker.backfill_bet_metrics"):
                with patch(
                    "plugins.bet_tracker._ensure_bets_table_exists"
                ):
                    sync_orders_to_database(db=db, client=client)

    sport_by_bet_id = {
        p["bet_id"]: p["sport"] for p in captured_params if "bet_id" in p
    }
    assert (
        sport_by_bet_id["678eb389-22c1-4aa3-aa9b-f477c87c1458"] == "MLB"
    )
    assert (
        sport_by_bet_id["f3ef09d8-a003-4602-ad34-99495a311b67"] == "EPL"
    )


def test_sync_orders_uses_initial_count_for_resting_and_fill_count_for_executed(
    sample_orders,
):
    """Resting orders must record intended size; executed orders use filled size."""
    from plugins.bet_tracker import sync_orders_to_database

    client = MagicMock()
    db = MagicMock()
    db.fetch_df.return_value = MagicMock(empty=True)

    captured_params: List[Dict] = []
    db.execute.side_effect = lambda sql, params=None: captured_params.append(
        params or {}
    )

    with patch(
        "plugins.bet_tracker.load_orders_from_kalshi",
        return_value=sample_orders,
    ):
        with patch("plugins.bet_tracker.get_market_status", return_value={}):
            with patch("plugins.bet_tracker.backfill_bet_metrics"):
                with patch(
                    "plugins.bet_tracker._ensure_bets_table_exists"
                ):
                    sync_orders_to_database(db=db, client=client)

    by_bet_id = {p["bet_id"]: p for p in captured_params if "bet_id" in p}
    executed = by_bet_id["678eb389-22c1-4aa3-aa9b-f477c87c1458"]
    resting = by_bet_id["f3ef09d8-a003-4602-ad34-99495a311b67"]

    # Executed: 4 contracts at 49c
    assert executed["count"] == 4
    assert executed["price"] == 49
    # Resting: 9 contracts at 23c — intended size, no fills yet
    assert resting["count"] == 9
    assert resting["price"] == 23


def test_sync_orders_calls_backfill_metrics_after_inserts(sample_orders):
    """After upserting, the sync must enrich rows from bet_recommendations."""
    from plugins.bet_tracker import sync_orders_to_database

    client = MagicMock()
    db = MagicMock()
    db.fetch_df.return_value = MagicMock(empty=True)

    with patch(
        "plugins.bet_tracker.load_orders_from_kalshi",
        return_value=sample_orders,
    ):
        with patch("plugins.bet_tracker.get_market_status", return_value={}):
            with patch(
                "plugins.bet_tracker.backfill_bet_metrics"
            ) as mock_backfill:
                with patch(
                    "plugins.bet_tracker._ensure_bets_table_exists"
                ):
                    sync_orders_to_database(db=db, client=client)

    mock_backfill.assert_called_once_with(db)
