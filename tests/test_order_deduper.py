from __future__ import annotations

from pathlib import Path

from order_deduper import OrderDeduper


def test_cannot_reserve_same_ticker_twice(tmp_path: Path) -> None:
    deduper = OrderDeduper(tmp_path)

    r1 = deduper.reserve(trade_date="2026-01-19", ticker="KXTEST-AAA", side="yes")
    assert r1.reserved is True

    r2 = deduper.reserve(trade_date="2026-01-19", ticker="KXTEST-AAA", side="yes")
    assert r2.reserved is False
    assert "Already reserved" in r2.reason


def test_cannot_reserve_same_ticker_across_dates(tmp_path: Path) -> None:
    deduper = OrderDeduper(tmp_path)

    r1 = deduper.reserve(trade_date="2026-01-19", ticker="KXTEST-CCC", side="yes")
    assert r1.reserved is True

    # Even on a different date, the same ticker must not be reservable again.
    r2 = deduper.reserve(trade_date="2026-01-20", ticker="KXTEST-CCC", side="yes")
    assert r2.reserved is False
    assert "Already reserved" in r2.reason


def test_cannot_reserve_both_sides_same_ticker(tmp_path: Path) -> None:
    deduper = OrderDeduper(tmp_path)

    r1 = deduper.reserve(trade_date="2026-01-19", ticker="KXTEST-BBB", side="yes")
    assert r1.reserved is True

    r2 = deduper.reserve(trade_date="2026-01-19", ticker="KXTEST-BBB", side="no")
    assert r2.reserved is False
    assert "Already reserved" in r2.reason
