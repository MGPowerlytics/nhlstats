"""Focused unit tests for the governed Live Markets Streamlit page."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import pytest

from dashboard import data_layer
from dashboard.pages import live_markets


class FakeStreamlit:
    """Capture Streamlit calls made by the Live Markets page."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def title(self, value: str) -> None:
        self.calls.append(("title", value))

    def subheader(self, value: str) -> None:
        self.calls.append(("subheader", value))

    def dataframe(self, value: Any, **kwargs: Any) -> None:
        self.calls.append(("dataframe", value))
        self.calls.append(("dataframe_kwargs", kwargs))

    def info(self, value: str) -> None:
        self.calls.append(("info", value))

    def error(self, value: str) -> None:
        self.calls.append(("error", value))

    def caption(self, value: str) -> None:
        self.calls.append(("caption", value))


def _seeded_live_markets_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "market_external_id": "KXNHL-26MAY03NYRBOS-NYR",
                "game_date": "2026-05-03",
                "commence_time": datetime(2026, 5, 3, 23, tzinfo=timezone.utc),
                "home_team_name": "New York Rangers",
                "away_team_name": "Boston Bruins",
                "bookmaker": "Kalshi",
                "market_name": "moneyline",
                "outcome_name": "New York Rangers",
                "price": 0.57,
                "last_update": datetime(2026, 5, 3, 13, 55, tzinfo=timezone.utc),
                "recommendation_bet_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
                "edge": 0.08,
                "expected_value": 0.14,
                "confidence": "HIGH",
                "ticker": "KXNHL-26MAY03NYRBOS-NYR",
            }
        ]
    )


def _empty_live_markets_frame() -> pd.DataFrame:
    df = pd.DataFrame(columns=data_layer.LIVE_MARKET_COLUMNS)
    df.attrs["empty_state"] = {
        "kind": "no_live_markets",
        "title": "No live markets",
        "message": "No governed live market rows are available right now.",
        "action": "Wait for market ingestion to complete or refresh later.",
        "severity": "info",
    }
    return df


def _flatten_calls(fake_st: FakeStreamlit) -> str:
    return "\n".join(str(item) for call in fake_st.calls for item in call)


def test_live_markets_page_renders_seeded_market_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seeded governed rows show game, market, odds, and recommendation context."""

    fake_st = FakeStreamlit()
    monkeypatch.setattr(live_markets, "st", fake_st)
    monkeypatch.setattr(
        live_markets.data_layer, "get_live_markets", _seeded_live_markets_frame
    )

    live_markets.render()

    dataframe_calls = [call for call in fake_st.calls if call[0] == "dataframe"]
    assert len(dataframe_calls) == 1
    rendered = dataframe_calls[0][1]
    assert list(rendered.columns) == [
        "game_date",
        "commence_time",
        "home_team_name",
        "away_team_name",
        "market_external_id",
        "ticker",
        "bookmaker",
        "market_name",
        "outcome_name",
        "price",
        "last_update",
        "edge",
        "expected_value",
        "confidence",
        "recommendation_bet_id",
    ]
    row = rendered.iloc[0]
    assert row["home_team_name"] == "New York Rangers"
    assert row["away_team_name"] == "Boston Bruins"
    assert row["market_external_id"] == "KXNHL-26MAY03NYRBOS-NYR"
    assert row["ticker"] == "KXNHL-26MAY03NYRBOS-NYR"
    assert row["bookmaker"] == "Kalshi"
    assert row["market_name"] == "moneyline"
    assert row["outcome_name"] == "New York Rangers"
    assert row["price"] == 0.57
    assert row["edge"] == 0.08
    assert row["expected_value"] == 0.14
    assert row["confidence"] == "HIGH"


def test_live_markets_page_renders_explicit_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero governed rows render the no_live_markets empty state."""

    fake_st = FakeStreamlit()
    monkeypatch.setattr(live_markets, "st", fake_st)
    monkeypatch.setattr(
        live_markets.data_layer, "get_live_markets", _empty_live_markets_frame
    )

    live_markets.render()

    rendered_text = _flatten_calls(fake_st)
    assert "no_live_markets" in rendered_text
    assert "No live markets" in rendered_text
    assert "No governed live market rows are available right now." in rendered_text
    assert not [call for call in fake_st.calls if call[0] == "dataframe"]


def test_live_markets_page_renders_sanitized_data_layer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Data-layer failures show sanitized payloads without raw SQL details."""

    fake_st = FakeStreamlit()
    monkeypatch.setattr(live_markets, "st", fake_st)

    def raise_error() -> pd.DataFrame:
        raise data_layer.DashboardDataError(
            data_layer.DashboardStatePayload(
                kind="dashboard_query_failed",
                title="Dashboard query failed",
                message=(
                    "The governed read model dashboard_live_markets_v1 could not be read."
                ),
                action="Check dashboard data-layer logs and read-model migrations.",
                severity="error",
            )
        )

    monkeypatch.setattr(live_markets.data_layer, "get_live_markets", raise_error)

    live_markets.render()

    rendered_text = _flatten_calls(fake_st)
    assert "dashboard_query_failed" in rendered_text
    assert "Dashboard query failed" in rendered_text
    assert "dashboard_live_markets_v1" in rendered_text
    assert "SELECT" not in rendered_text
    assert "password" not in rendered_text
    assert "postgresql://" not in rendered_text
