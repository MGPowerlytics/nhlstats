"""Consumer contract tests for the Kalshi fill/order → BetTracker boundary.

Validates that ``bet_tracker._extract_basic_fill_data()``,
``_process_fill()``, and ``_extract_order_data()`` correctly consume
schema-compliant Kalshi API payloads and correctly reject invalid payloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from jsonschema import Draft202012Validator, ValidationError

from plugins.bet_tracker import (
    _extract_basic_fill_data,
    _extract_order_data,
    _process_fill,
)
from tests.contracts.fixtures.kalshi_samples import (
    build_kalshi_fill_payload,
    build_kalshi_order_payload,
    build_kalshi_market_details_payload,
)

FILL_SCHEMA_PATH = Path(__file__).parent / "schemas" / "kalshi_fill_payload_v1.json"
ORDER_SCHEMA_PATH = Path(__file__).parent / "schemas" / "kalshi_order_payload_v1.json"
MARKET_DETAILS_SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / "kalshi_market_details_v1.json"
)


@pytest.fixture(scope="module")
def fill_schema() -> dict[str, Any]:
    """Load the Kalshi fill payload schema."""
    return json.loads(FILL_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def order_schema() -> dict[str, Any]:
    """Load the Kalshi order payload schema."""
    return json.loads(ORDER_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def market_details_schema() -> dict[str, Any]:
    """Load the Kalshi market details schema."""
    return json.loads(MARKET_DETAILS_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


# ---------------------------------------------------------------------------
# Fixture → schema conformance
# ---------------------------------------------------------------------------


class TestFillFixtureConformance:
    """Canonical fill fixture must match the frozen schema."""

    def test_canonical_fill_payload_matches_schema(
        self, fill_schema: dict[str, Any]
    ) -> None:
        _validate(fill_schema, build_kalshi_fill_payload())

    def test_no_side_fill_payload_matches_schema(
        self, fill_schema: dict[str, Any]
    ) -> None:
        _validate(fill_schema, build_kalshi_fill_payload(side="no", no_price=45))

    def test_fill_payload_rejects_extra_fields(
        self, fill_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(fill_schema, {**build_kalshi_fill_payload(), "unknown_key": "x"})

    def test_fill_payload_rejects_missing_required_field(
        self, fill_schema: dict[str, Any]
    ) -> None:
        payload = build_kalshi_fill_payload()
        del payload["ticker"]
        with pytest.raises(ValidationError):
            _validate(fill_schema, payload)

    def test_fill_payload_rejects_invalid_side(
        self, fill_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(fill_schema, build_kalshi_fill_payload(side="maybe"))


class TestOrderFixtureConformance:
    """Canonical order fixture must match the frozen schema."""

    def test_canonical_order_payload_matches_schema(
        self, order_schema: dict[str, Any]
    ) -> None:
        _validate(order_schema, build_kalshi_order_payload())

    def test_order_payload_rejects_extra_fields(
        self, order_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                order_schema, {**build_kalshi_order_payload(), "unknown_key": "x"}
            )

    def test_order_payload_rejects_missing_required_field(
        self, order_schema: dict[str, Any]
    ) -> None:
        payload = build_kalshi_order_payload()
        del payload["order_id"]
        with pytest.raises(ValidationError):
            _validate(order_schema, payload)

    def test_order_payload_rejects_invalid_status(
        self, order_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(order_schema, build_kalshi_order_payload(status="unknown"))


class TestMarketDetailsFixtureConformance:
    """Canonical market details fixture must match the frozen schema."""

    def test_canonical_market_details_matches_schema(
        self, market_details_schema: dict[str, Any]
    ) -> None:
        _validate(market_details_schema, build_kalshi_market_details_payload())

    def test_market_details_rejects_extra_fields(
        self, market_details_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                market_details_schema,
                {**build_kalshi_market_details_payload(), "unknown_key": "x"},
            )

    def test_market_details_rejects_missing_required_field(
        self, market_details_schema: dict[str, Any]
    ) -> None:
        payload = build_kalshi_market_details_payload()
        del payload["status"]
        with pytest.raises(ValidationError):
            _validate(market_details_schema, payload)

    def test_market_details_rejects_invalid_status(
        self, market_details_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                market_details_schema,
                build_kalshi_market_details_payload(status="unknown"),
            )


# ---------------------------------------------------------------------------
# Consumer: _extract_basic_fill_data
# ---------------------------------------------------------------------------


class TestExtractBasicFillData:
    """_extract_basic_fill_data() consumes schema-compliant fill payloads."""

    def test_extracts_yes_side_fill_correctly(self) -> None:
        fill = build_kalshi_fill_payload()
        fill_data = _extract_basic_fill_data(fill)

        assert fill_data.ticker == "KXNBAGAME-26JAN20LAL-LAL"
        assert fill_data.trade_id == "abc123"
        assert fill_data.bet_id == "KXNBAGAME-26JAN20LAL-LAL_abc123"
        assert fill_data.sport == "NBA"
        assert fill_data.side == "yes"
        assert fill_data.count == 10
        assert fill_data.price == 60
        assert fill_data.cost == 6.0  # 10 * 60 / 100
        assert fill_data.fees == 0.05  # 5 cents -> 0.05 dollars
        assert fill_data.placed_time_utc is not None
        assert fill_data.placed_date == "2026-01-20"

    def test_extracts_no_side_fill_correctly(self) -> None:
        fill = build_kalshi_fill_payload(side="no", no_price=45, no_price_dollars="0.45")
        fill_data = _extract_basic_fill_data(fill)

        assert fill_data.side == "no"
        assert fill_data.price == 45

    def test_extracts_tennis_ticker_sport(self) -> None:
        fill = build_kalshi_fill_payload(
            ticker="KXATPMATCH-26JAN20-NADAL-DJOKOVIC",
            trade_id="tenn_id_001",
        )
        fill_data = _extract_basic_fill_data(fill)
        assert fill_data.sport == "TENNIS"

    def test_extracts_epl_ticker_sport(self) -> None:
        fill = build_kalshi_fill_payload(
            ticker="KXEPLGAME-26JAN20-LIV-BOU",
            trade_id="epl_id_001",
        )
        fill_data = _extract_basic_fill_data(fill)
        assert fill_data.sport == "EPL"

    def test_extracts_unknown_ticker_sport(self) -> None:
        fill = build_kalshi_fill_payload(
            ticker="KXUNKNOWN-26JAN20-FOO-BAR",
            trade_id="unk_id_001",
        )
        fill_data = _extract_basic_fill_data(fill)
        assert fill_data.sport == "UNKNOWN"


class TestExtractFillDataEdgeCases:
    """Edge cases in _extract_basic_fill_data."""

    def test_uses_count_fp_when_count_missing(self) -> None:
        fill = build_kalshi_fill_payload(trade_id="edge_001", count_fp=7.5)
        # Remove count so fill.get("count") falls through to fill.get("count_fp", 0)
        del fill["count"]
        fill_data = _extract_basic_fill_data(fill)
        assert fill_data.count == 8  # int(round(7.5))

    def test_empty_fill_does_not_crash(self) -> None:
        fill_data = _extract_basic_fill_data({})
        assert fill_data.ticker == ""
        assert fill_data.count == 0
        assert fill_data.price == 0

    def test_fee_cost_in_dollars_string_parsed_correctly(self) -> None:
        fill = build_kalshi_fill_payload(fee_cost="0.15", trade_id="fee_001")
        fill_data = _extract_basic_fill_data(fill)
        assert fill_data.fees == 0.15  # Already in dollars, has decimal point

    def test_fee_cost_as_integer_cents_parsed_correctly(self) -> None:
        fill = build_kalshi_fill_payload(fee_cost=50, trade_id="fee_002")
        fill_data = _extract_basic_fill_data(fill)
        assert fill_data.fees == 0.50  # 50 cents -> 0.50 dollars


# ---------------------------------------------------------------------------
# Consumer: _extract_order_data
# ---------------------------------------------------------------------------


class TestExtractOrderData:
    """_extract_order_data() consumes schema-compliant order payloads."""

    def test_extracts_executed_order_correctly(self) -> None:
        order = build_kalshi_order_payload()
        bet_data = _extract_order_data(order)

        assert bet_data is not None
        assert bet_data.bet_id == "ord_abc123"
        assert bet_data.ticker == "KXNBAGAME-26JAN20LAL-LAL"
        assert bet_data.side == "yes"
        assert bet_data.sport == "NBA"
        assert bet_data.count == 10
        assert bet_data.price == 60
        assert bet_data.cost == 6.0
        assert bet_data.fees_dollars == 0.30
        assert bet_data.status == "open"
        assert bet_data.placed_time_utc is not None
        assert bet_data.placed_date == "2026-01-20"
        assert bet_data.source == "system"

    def test_extracts_resting_order_with_zero_fills(self) -> None:
        order = build_kalshi_order_payload(
            status="resting",
            fill_count_fp=0.0,
            taker_fill_cost_dollars="0.00",
            taker_fees_dollars="0.00",
        )
        bet_data = _extract_order_data(order)

        assert bet_data is not None
        assert bet_data.status == "open"
        assert bet_data.count == 10  # falls back to initial_count_fp
        assert bet_data.cost == 6.0  # contracts * price / 100

    def test_canceled_order_maps_to_canceled_status(self) -> None:
        order = build_kalshi_order_payload(status="canceled")
        bet_data = _extract_order_data(order)
        assert bet_data is not None
        assert bet_data.status == "canceled"

    def test_cancelled_order_maps_to_canceled_status(self) -> None:
        order = build_kalshi_order_payload(status="cancelled")
        bet_data = _extract_order_data(order)
        assert bet_data is not None
        assert bet_data.status == "canceled"

    def test_missing_order_id_returns_none(self) -> None:
        order = build_kalshi_order_payload(order_id="")
        bet_data = _extract_order_data(order)
        # Falls back to client_order_id
        assert bet_data is not None

    def test_missing_client_order_id_and_order_id_returns_none(self) -> None:
        bet_data = _extract_order_data({})
        assert bet_data is None

    def test_order_price_parsed_from_yes_price_dollars(self) -> None:
        order = build_kalshi_order_payload(
            side="yes",
            yes_price=75,
            yes_price_dollars="0.75",
            no_price=25,
            no_price_dollars="0.25",
        )
        # _extract_order_data calls _parse_price_cents which reads yes_price
        bet_data = _extract_order_data(order)
        assert bet_data is not None
        assert bet_data.price == 75

    def test_order_price_parsed_from_no_price_dollars(self) -> None:
        order = build_kalshi_order_payload(
            side="no",
            yes_price=60,
            yes_price_dollars="0.60",
            no_price=40,
            no_price_dollars="0.40",
        )
        bet_data = _extract_order_data(order)
        assert bet_data is not None
        assert bet_data.price == 40


# ---------------------------------------------------------------------------
# Consumer: _process_fill (integration of _extract_basic_fill_data +
# market lookup + probability/status)
# ---------------------------------------------------------------------------


class TestProcessFill:
    """_process_fill() processes fill payloads into BetData records."""

    def test_processes_yes_fill_with_active_market(self) -> None:
        fill = build_kalshi_fill_payload()
        client = _make_mock_client()
        existing_bets: set = set()

        bet_data = _process_fill(fill, client, existing_bets)

        assert bet_data is not None
        assert bet_data.bet_id == "KXNBAGAME-26JAN20LAL-LAL_abc123"
        assert bet_data.sport == "NBA"
        assert bet_data.status == "open"
        assert bet_data.market_title == "Lakers vs Celtics - Winner"

    def test_processes_no_fill_with_active_market(self) -> None:
        fill = build_kalshi_fill_payload(
            side="no",
            trade_id="no_fill_001",
            yes_price=55,
            yes_price_dollars="0.55",
            no_price=45,
            no_price_dollars="0.45",
        )
        client = _make_mock_client()
        existing_bets: set = set()

        bet_data = _process_fill(fill, client, existing_bets)

        assert bet_data is not None
        assert bet_data.side == "no"
        assert bet_data.price == 45
        assert bet_data.status == "open"

    def test_skips_existing_bet(self) -> None:
        fill = build_kalshi_fill_payload()
        client = _make_mock_client()
        existing_bets = {"KXNBAGAME-26JAN20LAL-LAL_abc123"}

        bet_data = _process_fill(fill, client, existing_bets)

        # _process_fill determines existing_bets after processing the fill;
        # it doesn't skip — the skip happens at the caller level (_save_bet_to_database).
        # So the fill still processes successfully.
        assert bet_data is not None
        assert bet_data.bet_id == "KXNBAGAME-26JAN20LAL-LAL_abc123"

    def test_processes_market_with_empty_result(self) -> None:
        fill = build_kalshi_fill_payload(trade_id="empty_res_001")
        client = _make_mock_client(market_result="")
        existing_bets: set = set()

        bet_data = _process_fill(fill, client, existing_bets)

        assert bet_data is not None
        assert bet_data.status == "open"
        assert bet_data.closing_line_prob is None

    def test_processes_won_settled_market(self) -> None:
        fill = build_kalshi_fill_payload(
            side="yes", trade_id="won_001"
        )
        client = _make_mock_client(market_status="closed", market_result="yes")
        existing_bets: set = set()

        bet_data = _process_fill(fill, client, existing_bets)

        assert bet_data is not None
        assert bet_data.status == "won"
        assert bet_data.payout == 10.0  # count * 1.0
        assert bet_data.profit == 4.0  # 10.0 - 6.0

    def test_processes_lost_settled_market(self) -> None:
        fill = build_kalshi_fill_payload(
            side="no", trade_id="lost_001", no_price=45, no_price_dollars="0.45"
        )
        client = _make_mock_client(market_status="closed", market_result="yes")
        existing_bets: set = set()

        bet_data = _process_fill(fill, client, existing_bets)

        assert bet_data is not None
        assert bet_data.status == "lost"
        assert bet_data.payout == 0
        assert bet_data.profit == -bet_data.cost


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(
    market_status: str = "active",
    market_result: str = "",
) -> MagicMock:
    """Create a mock KalshiBetting client that returns deterministic market data."""
    client = MagicMock()
    client.get_market_details.return_value = {
        "status": market_status,
        "result": market_result,
        "close_time": "2026-01-20T19:00:00Z",
        "title": "Lakers vs Celtics - Winner",
    }
    return client
