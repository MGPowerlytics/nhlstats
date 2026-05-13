"""Focused unit tests for the governed Bet Detail Streamlit page."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from dashboard import data_layer
from dashboard.pages import bet_detail


@dataclass
class _FakeColumn:
    """Small Streamlit column test double."""

    parent: "_FakeStreamlit"

    def metric(self, label: str, value: Any, **kwargs: Any) -> None:
        self.parent.calls.append(("metric", (label, value), kwargs))


@dataclass
class _FakeStreamlit:
    """Capture Streamlit calls made by the Bet Detail page."""

    button_values: dict[str, bool] = field(default_factory=dict)
    session_state: dict[str, Any] = field(default_factory=dict)
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(
        default_factory=list
    )
    rerun_count: int = 0

    def header(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("header", args, kwargs))

    def subheader(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("subheader", args, kwargs))

    def metric(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("metric", args, kwargs))

    def write(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("write", args, kwargs))

    def caption(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("caption", args, kwargs))

    def info(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("info", args, kwargs))

    def warning(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("warning", args, kwargs))

    def error(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("error", args, kwargs))

    def divider(self) -> None:
        self.calls.append(("divider", (), {}))

    def columns(self, spec: int | list[int]) -> list[_FakeColumn]:
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeColumn(self) for _ in range(count)]

    def button(self, label: str) -> bool:
        self.calls.append(("button", (label,), {}))
        return self.button_values.get(label, False)

    def rerun(self) -> None:
        self.rerun_count += 1


def _seeded_detail(status: str | None = "placed") -> dict[str, Any]:
    return {
        "bet": {
            "bet_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
            "recommendation_date": datetime(2026, 5, 3, 12, tzinfo=timezone.utc),
            "placed_time_utc": datetime(2026, 5, 3, 12, 5, tzinfo=timezone.utc),
            "home_team": "New York Rangers",
            "away_team": "Boston Bruins",
            "bet_on": "New York Rangers",
            "ticker": "KXNHL-26MAY03NYRBOS-NYR",
            "elo_prob": 0.62,
            "market_prob": 0.54,
            "edge": 0.08,
            "expected_value": 0.14,
            "kelly_fraction": 0.05,
            "confidence": "HIGH",
            "yes_ask": 57,
            "no_ask": 45,
            "status": status,
            "cost_dollars": 10.0,
            "payout_dollars": 17.5,
            "profit_dollars": 7.5,
            "created_at": datetime(2026, 5, 3, 12, 1, tzinfo=timezone.utc),
        },
        "execution_link": {
            "linkage_status": "linked",
            "linkage_basis": "market_ticker_selection_key_canonical_game_id",
            "entry_quote_role": "executable",
            "entry_price_source": "dashboard_seed",
            "entry_quote_source_system": "kalshi_market_details",
            "entry_quote_bookmaker": "Kalshi",
        },
        "clv_evidence": {
            "clv_source_type": "market_close",
            "closing_quote_source": "dashboard_seed",
            "close_price_role": "close",
            "selected_close_rule": "latest_admissible_pregame_quote",
            "clv_evidence_tier": "partially_evidenced",
        },
        "empty_state": None,
    }


def _state(kind: str, severity: str = "info") -> dict[str, str]:
    return {
        "kind": kind,
        "title": "Bet not found" if kind == "bet_not_found" else "No bet details",
        "message": (
            "The selected bet is unavailable."
            if kind == "bet_not_found"
            else "No governed bet detail rows are available yet."
        ),
        "action": "Return to recent activity and choose an available bet.",
        "severity": severity,
    }


def _rendered_text(fake_st: _FakeStreamlit) -> str:
    return "\n".join(
        str(arg)
        for _, args, kwargs in fake_st.calls
        for arg in (*args, *kwargs.values())
    )


def test_bet_detail_page_renders_seeded_recommendation_and_placed_bet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seeded detail shows recommendation, odds, pricing, and placed-bet values."""

    fake_st = _FakeStreamlit()
    monkeypatch.setattr(bet_detail, "st", fake_st)
    monkeypatch.setattr(bet_detail, "get_bet_detail", lambda bet_id: _seeded_detail())

    bet_detail.render_bet_detail("DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME")

    rendered = _rendered_text(fake_st)
    assert "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME" in rendered
    assert "New York Rangers vs Boston Bruins" in rendered
    assert "New York Rangers" in rendered
    assert "KXNHL-26MAY03NYRBOS-NYR" in rendered
    assert "62.0%" in rendered
    assert "54.0%" in rendered
    assert "8.0%" in rendered
    assert "$0.14" in rendered
    assert "5.0%" in rendered
    assert "HIGH" in rendered
    assert "57" in rendered
    assert "45" in rendered
    assert "$10.00" in rendered
    assert "$17.50" in rendered
    assert "$7.50" in rendered
    assert "Linkage status: linked" in rendered
    assert "Entry quote role: executable" in rendered
    assert "Close-line source type: market_close" in rendered
    assert "Closing quote source: dashboard_seed" in rendered
    assert "Selected close rule: latest_admissible_pregame_quote" in rendered


def test_bet_detail_page_handles_lowercase_placed_bet_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lowercase placed-bet statuses render without uppercase-only assumptions."""

    fake_st = _FakeStreamlit()
    monkeypatch.setattr(bet_detail, "st", fake_st)
    monkeypatch.setattr(
        bet_detail, "get_bet_detail", lambda bet_id: _seeded_detail("won")
    )

    bet_detail.render_bet_detail("lowercase-status")

    metric_calls = [call for call in fake_st.calls if call[0] == "metric"]
    assert ("metric", ("Status", "won"), {}) in metric_calls
    assert any(
        call[1][0] == "Profit" and call[2].get("delta_color") == "normal"
        for call in metric_calls
    )


def test_bet_detail_page_renders_explicit_no_bet_details_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No governed detail rows render the explicit no_bet_details state."""

    fake_st = _FakeStreamlit()
    monkeypatch.setattr(bet_detail, "st", fake_st)
    monkeypatch.setattr(
        bet_detail,
        "get_bet_detail",
        lambda bet_id: {"bet": {}, "empty_state": _state("no_bet_details")},
    )

    bet_detail.render_bet_detail("any-bet")

    rendered = _rendered_text(fake_st)
    assert "no_bet_details" in rendered
    assert "No bet details" in rendered
    assert not [call for call in fake_st.calls if call[0] == "metric"]


def test_bet_detail_page_renders_explicit_bet_not_found_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown bet IDs render the explicit bet_not_found empty state."""

    fake_st = _FakeStreamlit()
    monkeypatch.setattr(bet_detail, "st", fake_st)
    error = data_layer.DashboardEmptyState(
        data_layer.DashboardStatePayload(
            kind="bet_not_found",
            title="Bet not found",
            message="The selected bet is not available in the governed dashboard detail view.",
            action="Return to recent activity and choose an available bet.",
            severity="info",
        )
    )
    monkeypatch.setattr(
        bet_detail, "get_bet_detail", lambda bet_id: (_ for _ in ()).throw(error)
    )

    bet_detail.render_bet_detail("missing-bet")

    rendered = _rendered_text(fake_st)
    assert "bet_not_found" in rendered
    assert "Bet not found" in rendered
    assert "missing-bet" in rendered


def test_bet_detail_page_renders_sanitized_data_layer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Data-layer failures show sanitized payloads without raw SQL details."""

    fake_st = _FakeStreamlit()
    monkeypatch.setattr(bet_detail, "st", fake_st)
    error = data_layer.DashboardDataError(
        data_layer.DashboardStatePayload(
            kind="dashboard_query_failed",
            title="Dashboard query failed",
            message="The governed bet detail read model could not be read.",
            action="Check dashboard data-layer logs and read-model migrations.",
            severity="error",
        )
    )
    monkeypatch.setattr(
        bet_detail, "get_bet_detail", lambda bet_id: (_ for _ in ()).throw(error)
    )

    bet_detail.render_bet_detail("failing-bet")

    rendered = _rendered_text(fake_st)
    assert "dashboard_query_failed" in rendered
    assert "Dashboard query failed" in rendered
    assert "SELECT" not in rendered
    assert "password" not in rendered
    assert "postgresql://" not in rendered
    assert "Traceback" not in rendered


def test_bet_detail_page_has_no_direct_sql_or_source_table_references() -> None:
    """Bet Detail page must stay behind dashboard.data_layer APIs."""

    source = Path(bet_detail.__file__).read_text(encoding="utf-8")
    forbidden = (
        "SELECT ",
        " FROM ",
        " JOIN ",
        "bet_recommendations",
        "placed_bets",
        "unified_games",
        "game_odds",
        "dashboard_bet_detail_v1",
    )
    for token in forbidden:
        assert token not in source
