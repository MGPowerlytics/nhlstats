from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, Sequence


class PriceRole(str, Enum):
    REFERENCE = "reference"
    EXECUTABLE = "executable"
    BEST = "best"
    CLOSE = "close"


class CLVEvidenceTier(str, Enum):
    DESCRIPTIVE_ONLY = "descriptive_only"
    PARTIALLY_EVIDENCED = "partially_evidenced"
    APPROVAL_GRADE = "approval_grade"


@dataclass(frozen=True)
class GovernedPriceQuote:
    role: PriceRole
    decimal_price: float
    bookmaker: str
    market_ticker: str | None = None
    selection_key: str | None = None
    observed_at: datetime | None = None
    loaded_at: datetime | None = None
    payload_ref: str | None = None
    explicit_close: bool = False
    freshness_result: str = "missing_source_timestamp"
    selection_rule: str | None = None
    selection_provenance: str | None = None

    @property
    def implied_probability(self) -> float | None:
        if self.decimal_price <= 0:
            return None
        return min(max(1.0 / float(self.decimal_price), 0.0), 1.0)


@dataclass(frozen=True)
class PriceRoleDecision:
    executable_quote: GovernedPriceQuote
    reference_quote: GovernedPriceQuote | None = None
    best_quote: GovernedPriceQuote | None = None
    close_quote: GovernedPriceQuote | None = None
    reference_context: str = "reference_available"


@dataclass(frozen=True)
class CLVGovernanceSnapshot:
    evidence_tier: CLVEvidenceTier
    contaminated: bool
    contamination_reason: str | None
    clv_source_type: str
    close_quote: GovernedPriceQuote | None
    close_freshness_result: str


def _coerce_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def evaluate_freshness(
    observed_at: datetime | str | None,
    *,
    as_of: datetime | str | None,
    max_age: timedelta,
) -> str:
    observed = _coerce_datetime(observed_at)
    reference_time = _coerce_datetime(as_of)
    if observed is None:
        return "missing_source_timestamp"
    if reference_time is None:
        return "fresh"
    return "stale" if (reference_time - observed) > max_age else "fresh"


def build_single_venue_price_decision(
    *,
    executable_quote: GovernedPriceQuote,
    best_quote_candidates: Sequence[GovernedPriceQuote] | None = None,
    reference_quote: GovernedPriceQuote | None = None,
) -> PriceRoleDecision:
    best_quote = None
    if best_quote_candidates and len(best_quote_candidates) > 1:
        best_quote = select_best_executable_quote(best_quote_candidates)
    return PriceRoleDecision(
        executable_quote=replace(executable_quote, role=PriceRole.EXECUTABLE),
        reference_quote=reference_quote,
        best_quote=best_quote,
        reference_context=(
            "reference_available"
            if reference_quote is not None
            else "executable_market_comparison_only"
        ),
    )


def select_best_executable_quote(
    quotes: Iterable[GovernedPriceQuote],
    *,
    as_of: datetime | str | None = None,
    max_age: timedelta = timedelta(hours=4),
) -> GovernedPriceQuote | None:
    eligible: list[GovernedPriceQuote] = []
    for quote in quotes:
        freshness = evaluate_freshness(quote.observed_at, as_of=as_of, max_age=max_age)
        if freshness == "stale":
            continue
        eligible.append(replace(quote, freshness_result=freshness))
    unique_books = {quote.bookmaker for quote in eligible}
    if len(unique_books) < 2:
        return None
    selected = max(
        eligible,
        key=lambda quote: (quote.decimal_price, quote.observed_at or datetime.min),
    )
    return replace(selected, role=PriceRole.BEST)


def select_close_quote(
    quotes: Iterable[GovernedPriceQuote],
    *,
    market_close_time: datetime | str | None,
    source_priority: Sequence[str] = (),
    max_age: timedelta = timedelta(hours=4),
) -> GovernedPriceQuote | None:
    market_close = _coerce_datetime(market_close_time)
    eligible: list[GovernedPriceQuote] = []
    for quote in quotes:
        observed = _coerce_datetime(quote.observed_at)
        if market_close is not None and observed is not None and observed > market_close:
            continue
        freshness = evaluate_freshness(observed, as_of=market_close, max_age=max_age)
        eligible.append(replace(quote, freshness_result=freshness))
    if not eligible:
        return None

    explicit = [quote for quote in eligible if quote.explicit_close]
    priority_index = {source: index for index, source in enumerate(source_priority)}

    def _sort_key(quote: GovernedPriceQuote) -> tuple[datetime, int, float]:
        observed = _coerce_datetime(quote.observed_at) or datetime.min
        return (
            observed,
            -priority_index.get(quote.bookmaker, len(priority_index)),
            quote.decimal_price,
        )

    pool = explicit or eligible
    selected = max(pool, key=_sort_key)
    selection_rule = (
        "explicit_close_snapshot"
        if explicit
        else "latest_admissible_pregame_quote"
    )
    if (
        not explicit
        and sum(
            1
            for quote in pool
            if (_coerce_datetime(quote.observed_at) or datetime.min)
            == (_coerce_datetime(selected.observed_at) or datetime.min)
        )
        > 1
    ):
        selection_rule = "source_priority_tiebreak"
    provenance = None
    selected_observed = _coerce_datetime(selected.observed_at)
    if selected_observed is not None:
        provenance = (
            f"{selected.bookmaker}|{selected.selection_key}|"
            f"{selected_observed.isoformat()}"
        )
    return replace(
        selected,
        role=PriceRole.CLOSE,
        selection_rule=selection_rule,
        selection_provenance=provenance,
    )


def build_clv_governance_snapshot(
    *,
    entry_quote: GovernedPriceQuote,
    close_quote: GovernedPriceQuote | None,
    clv_source_type: str,
) -> CLVGovernanceSnapshot:
    if clv_source_type == "binary_result_placeholder":
        return CLVGovernanceSnapshot(
            evidence_tier=CLVEvidenceTier.DESCRIPTIVE_ONLY,
            contaminated=True,
            contamination_reason="binary_result_placeholder",
            clv_source_type=clv_source_type,
            close_quote=None,
            close_freshness_result="missing_close",
        )
    freshness = close_quote.freshness_result if close_quote is not None else "missing_close"
    if (
        close_quote is not None
        and freshness == "missing_source_timestamp"
        and close_quote.observed_at is not None
    ):
        freshness = "fresh"
        close_quote = replace(close_quote, freshness_result=freshness)
    tier = (
        CLVEvidenceTier.PARTIALLY_EVIDENCED
        if close_quote is not None
        else CLVEvidenceTier.DESCRIPTIVE_ONLY
    )
    contaminated = close_quote is None
    contamination_reason = None if close_quote is not None else "missing_close"
    if close_quote is not None and close_quote.freshness_result == "missing_source_timestamp":
        tier = CLVEvidenceTier.DESCRIPTIVE_ONLY
        contaminated = True
        contamination_reason = "missing_source_timestamp"
    return CLVGovernanceSnapshot(
        evidence_tier=tier,
        contaminated=contaminated,
        contamination_reason=contamination_reason,
        clv_source_type=clv_source_type,
        close_quote=close_quote,
        close_freshness_result=freshness,
    )
