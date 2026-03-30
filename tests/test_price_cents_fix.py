"""Tests for the price_cents=0 bug fix in bet_tracker.py.

Root cause: Kalshi fills API (v2) returns fills with a single ``price`` field,
not separate ``yes_price``/``no_price`` fields (those exist on *orders*, not fills).
The old code called ``fill.get("yes_price", 0)`` which always returned 0 because
that key is absent from fill payloads, causing every ``price_cents`` to be stored
as 0 in the ``placed_bets`` table.

Fix: fall back to the ``price`` field that the fills API actually returns.
"""

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


# ---------------------------------------------------------------------------
# Helper – import the private helper under test
# ---------------------------------------------------------------------------


def _import_extract():
    """Import _extract_basic_fill_data from bet_tracker (lazy to allow patching)."""
    from bet_tracker import _extract_basic_fill_data

    return _extract_basic_fill_data


# ---------------------------------------------------------------------------
# Fixtures – representative Kalshi fills API payloads
# ---------------------------------------------------------------------------


def _kalshi_v2_fill(
    ticker: str = "KXNBAGAME-26MAR30PHIMIA-MIA",
    side: str = "yes",
    count: int = 5,
    price: int = 45,
    fill_id: str = "fill_abc123",
    order_id: str = "order_xyz",
    fee_cost: int = 1,
    created_time: str = "2026-03-30T18:00:00Z",
) -> Dict[str, Any]:
    """Return a fill payload matching the current Kalshi v2 fills API schema.

    The v2 API returns a single ``price`` field; it does **not** contain
    ``yes_price`` or ``no_price``.
    """
    return {
        "fill_id": fill_id,
        "order_id": order_id,
        "ticker": ticker,
        "side": side,
        "action": "buy",
        "count": count,
        "price": price,
        "is_taker": True,
        "created_time": created_time,
        "fee_cost": fee_cost,
    }


def _legacy_fill(
    ticker: str = "KXNBAGAME-26MAR30PHIMIA-MIA",
    side: str = "yes",
    count: int = 5,
    yes_price: int = 45,
    no_price: int = 55,
) -> Dict[str, Any]:
    """Return a fill payload that uses the old ``yes_price``/``no_price`` schema."""
    return {
        "trade_id": "trade_old001",
        "ticker": ticker,
        "side": side,
        "count": count,
        "yes_price": yes_price,
        "no_price": no_price,
        "fee_cost": 0,
        "created_time": "2026-03-01T12:00:00Z",
    }


# ---------------------------------------------------------------------------
# Tests – price extraction with current (v2) fills API
# ---------------------------------------------------------------------------


class TestExtractBasicFillData:
    """Tests for _extract_basic_fill_data using the Kalshi v2 fills API schema."""

    def test_yes_side_price_extracted_from_price_field(self) -> None:
        """YES-side fill: price_cents must equal fill['price'], not zero."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(side="yes", price=45)
        result = _extract_basic_fill_data(fill)

        assert result.price == 45, "price should be 45¢ from the 'price' field, not 0"

    def test_no_side_price_extracted_from_price_field(self) -> None:
        """NO-side fill: price_cents must equal fill['price'], not zero."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(side="no", price=55)
        result = _extract_basic_fill_data(fill)

        assert result.price == 55, "price should be 55¢ from the 'price' field, not 0"

    def test_price_zero_only_when_fill_price_is_zero(self) -> None:
        """price should only be 0 when the fill itself has price=0 (edge case)."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(side="yes", price=0)
        result = _extract_basic_fill_data(fill)

        assert result.price == 0

    def test_cost_computed_correctly_from_price(self) -> None:
        """cost_dollars must equal count * price / 100."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(side="yes", count=5, price=45)
        result = _extract_basic_fill_data(fill)

        expected_cost = 5 * 45 / 100  # $2.25
        assert result.cost == pytest.approx(expected_cost, abs=1e-6)

    def test_cost_is_nonzero_when_price_is_nonzero(self) -> None:
        """cost must not be 0 when price and count are positive."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(side="yes", count=3, price=60)
        result = _extract_basic_fill_data(fill)

        assert result.cost > 0

    def test_nba_ticker_sport_detected(self) -> None:
        """Sport should be detected as nba for NBA tickers."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(ticker="KXNBAGAME-26MAR30PHIMIA-MIA", price=45)
        result = _extract_basic_fill_data(fill)

        assert result.sport.lower() == "nba"

    # ------------------------------------------------------------------
    # Backward-compatibility: old ``yes_price``/``no_price`` payloads
    # ------------------------------------------------------------------

    def test_yes_side_legacy_yes_price_still_works(self) -> None:
        """Legacy fills with yes_price/no_price should still extract correctly."""
        _extract_basic_fill_data = _import_extract()
        fill = _legacy_fill(side="yes", yes_price=42)
        result = _extract_basic_fill_data(fill)

        assert result.price == 42

    def test_no_side_legacy_no_price_still_works(self) -> None:
        """Legacy fills with no_price should still extract correctly."""
        _extract_basic_fill_data = _import_extract()
        fill = _legacy_fill(side="no", no_price=58)
        result = _extract_basic_fill_data(fill)

        assert result.price == 58

    # ------------------------------------------------------------------
    # Fill ID extraction (fill_id vs trade_id)
    # ------------------------------------------------------------------

    def test_fill_id_used_when_present(self) -> None:
        """bet_id should use fill_id when the v2 payload provides it."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(
            ticker="KXNBAGAME-26MAR30PHIMIA-MIA",
            fill_id="fill_abc123",
            price=45,
        )
        result = _extract_basic_fill_data(fill)

        assert "fill_abc123" in result.bet_id

    def test_trade_id_fallback_when_fill_id_absent(self) -> None:
        """bet_id should fall back to trade_id for legacy payloads."""
        _extract_basic_fill_data = _import_extract()
        fill = _legacy_fill(side="yes")
        # legacy fill has trade_id but not fill_id
        assert "fill_id" not in fill

        result = _extract_basic_fill_data(fill)
        assert "trade_old001" in result.bet_id

    # ------------------------------------------------------------------
    # Other fields
    # ------------------------------------------------------------------

    def test_ticker_extracted(self) -> None:
        """ticker field is forwarded verbatim."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(ticker="KXNBAGAME-26MAR30PHIMIA-MIA", price=45)
        result = _extract_basic_fill_data(fill)

        assert result.ticker == "KXNBAGAME-26MAR30PHIMIA-MIA"

    def test_count_extracted(self) -> None:
        """count (contracts) is forwarded correctly."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(count=7, price=45)
        result = _extract_basic_fill_data(fill)

        assert result.count == 7

    def test_side_extracted(self) -> None:
        """side is forwarded correctly."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(side="no", price=55)
        result = _extract_basic_fill_data(fill)

        assert result.side == "no"

    def test_placed_date_parsed_from_created_time(self) -> None:
        """placed_date is parsed from created_time ISO string."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(created_time="2026-03-30T18:00:00Z", price=45)
        result = _extract_basic_fill_data(fill)

        assert result.placed_date == "2026-03-30"

    def test_placed_date_none_on_missing_created_time(self) -> None:
        """placed_date is None when created_time is missing."""
        _extract_basic_fill_data = _import_extract()
        fill = _kalshi_v2_fill(price=45)
        fill["created_time"] = ""
        result = _extract_basic_fill_data(fill)

        assert result.placed_date is None
