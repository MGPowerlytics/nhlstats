from __future__ import annotations

from datetime import datetime, timedelta

from plugins.pricing_governance import (
    CLVEvidenceTier,
    GovernedPriceQuote,
    PriceRole,
    build_clv_governance_snapshot,
    build_single_venue_price_decision,
    select_best_executable_quote,
    select_close_quote,
)


def _quote(
    *,
    role: PriceRole,
    price: float,
    bookmaker: str = "Kalshi",
    observed_at: datetime | None = None,
    loaded_at: datetime | None = None,
    payload_ref: str | None = None,
    ticker: str = "KX-TEST",
    side: str = "home",
    explicit_close: bool = False,
) -> GovernedPriceQuote:
    now = observed_at or datetime(2026, 5, 3, 14, 0, 0)
    return GovernedPriceQuote(
        role=role,
        decimal_price=price,
        bookmaker=bookmaker,
        market_ticker=ticker,
        selection_key=side,
        observed_at=now,
        loaded_at=loaded_at or now,
        payload_ref=payload_ref or f"{bookmaker}-{role.value}",
        explicit_close=explicit_close,
    )


def test_single_venue_recommendation_stays_executable_only() -> None:
    decision = build_single_venue_price_decision(
        executable_quote=_quote(role=PriceRole.EXECUTABLE, price=1.85),
        best_quote_candidates=[_quote(role=PriceRole.EXECUTABLE, price=1.85)],
    )

    assert decision.reference_quote is None
    assert decision.executable_quote.role is PriceRole.EXECUTABLE
    assert decision.best_quote is None
    assert decision.reference_context == "executable_market_comparison_only"


def test_best_price_requires_multi_bookmaker_eligibility() -> None:
    as_of = datetime(2026, 5, 3, 23, 0, 0)
    selected = select_best_executable_quote(
        [
            _quote(
                role=PriceRole.EXECUTABLE,
                price=1.91,
                bookmaker="Kalshi",
                observed_at=as_of - timedelta(minutes=10),
            ),
            _quote(
                role=PriceRole.EXECUTABLE,
                price=2.02,
                bookmaker="SBR",
                observed_at=as_of - timedelta(minutes=4),
            ),
        ],
        as_of=as_of,
        max_age=timedelta(hours=4),
    )

    assert selected is not None
    assert selected.role is PriceRole.BEST
    assert selected.bookmaker == "SBR"
    assert selected.decimal_price == 2.02
    assert selected.freshness_result == "fresh"


def test_close_selection_prefers_explicit_close_then_latest_quote() -> None:
    market_close = datetime(2026, 5, 3, 23, 0, 0)
    selected = select_close_quote(
        [
            _quote(
                role=PriceRole.CLOSE,
                price=1.96,
                bookmaker="Kalshi",
                observed_at=market_close - timedelta(minutes=1),
            ),
            _quote(
                role=PriceRole.CLOSE,
                price=1.94,
                bookmaker="SBR",
                observed_at=market_close - timedelta(minutes=5),
                explicit_close=True,
            ),
        ],
        market_close_time=market_close,
        source_priority=("Kalshi", "SBR"),
        max_age=timedelta(hours=4),
    )

    assert selected is not None
    assert selected.role is PriceRole.CLOSE
    assert selected.bookmaker == "SBR"
    assert selected.selection_rule == "explicit_close_snapshot"
    assert selected.selection_provenance == "SBR|home|2026-05-03T22:55:00"


def test_clv_governance_snapshot_marks_binary_placeholders_descriptive_only() -> None:
    entry_quote = _quote(role=PriceRole.EXECUTABLE, price=1.85)

    placeholder = build_clv_governance_snapshot(
        entry_quote=entry_quote,
        close_quote=None,
        clv_source_type="binary_result_placeholder",
    )
    partial = build_clv_governance_snapshot(
        entry_quote=entry_quote,
        close_quote=_quote(
            role=PriceRole.CLOSE,
            price=1.72,
            bookmaker="SBR",
            observed_at=datetime(2026, 5, 3, 22, 45, 0),
        ),
        clv_source_type="market_close",
    )

    assert placeholder.evidence_tier is CLVEvidenceTier.DESCRIPTIVE_ONLY
    assert placeholder.contaminated is True
    assert placeholder.contamination_reason == "binary_result_placeholder"
    assert partial.evidence_tier is CLVEvidenceTier.PARTIALLY_EVIDENCED
    assert partial.close_quote.role is PriceRole.CLOSE
    assert partial.close_freshness_result == "fresh"
