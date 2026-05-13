"""Focused unit tests for the Tennis Predictions dashboard page."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from dashboard import data_layer
from dashboard.pages import tennis_predictions


class FakeStreamlit:
    """Capture Streamlit calls made by the Tennis Predictions page."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def title(self, value: str) -> None:
        self.calls.append(("title", value))

    def caption(self, value: str) -> None:
        self.calls.append(("caption", value))

    def subheader(self, value: str) -> None:
        self.calls.append(("subheader", value))

    def dataframe(self, value: Any, **kwargs: Any) -> None:
        self.calls.append(("dataframe", value))
        self.calls.append(("dataframe_kwargs", kwargs))

    def info(self, value: str) -> None:
        self.calls.append(("info", value))

    def error(self, value: str) -> None:
        self.calls.append(("error", value))


def _seeded_predictions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "bet_id": "TENNIS_2026-05-04_KXATPMATCH-26MAY04ALPBRA-ALP_home",
                "sport": "TENNIS",
                "recommendation_date": "2026-05-04",
                "commence_time": "2026-05-04T16:00:00Z",
                "home_team": "Alpha A.",
                "away_team": "Bravo B.",
                "bet_on": "Alpha A.",
                "ticker": "KXATPMATCH-26MAY04ALPBRA-ALP",
                "model_prob": 0.64,
                "market_prob": 0.56,
                "edge": 0.08,
                "expected_value": 0.1429,
                "kelly_fraction": 0.18,
                "confidence": "HIGH",
                "yes_ask": 56,
                "no_ask": 44,
                "created_at": "2026-05-03T14:00:00Z",
            }
        ],
        columns=data_layer.TENNIS_PREDICTION_COLUMNS,
    )


def _empty_predictions() -> pd.DataFrame:
    df = pd.DataFrame(columns=data_layer.TENNIS_PREDICTION_COLUMNS)
    df.attrs["empty_state"] = {
        "kind": "no_tennis_predictions",
        "title": "No actionable tennis predictions",
        "message": "No governed actionable TENNIS predictions are available for the current run date.",
        "action": "Run tennis market ingestion and recommendation loading before placing bets.",
        "severity": "info",
    }
    return df


def _flatten_calls(fake_st: FakeStreamlit) -> str:
    return "\n".join(str(item) for call in fake_st.calls for item in call)


def test_tennis_predictions_page_renders_actionable_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seeded rows expose probabilities, edge, Kelly, confidence, ticker, and bet ID."""
    fake_st = FakeStreamlit()
    monkeypatch.setattr(tennis_predictions, "st", fake_st)
    monkeypatch.setattr(
        tennis_predictions.data_layer,
        "get_tomorrow_tennis_predictions",
        _seeded_predictions,
    )

    tennis_predictions.render()

    dataframe_calls = [call for call in fake_st.calls if call[0] == "dataframe"]
    assert len(dataframe_calls) == 1
    rendered = dataframe_calls[0][1].data
    assert list(rendered.columns) == [
        "Player A",
        "Player B",
        "Bet On",
        "Model Prob",
        "Market Prob",
        "Edge",
        "Expected Value",
        "Kelly Fraction",
        "Confidence",
        "Ticker",
        "Bet ID",
    ]
    row = rendered.iloc[0]
    assert row["Bet On"] == "Alpha A."
    assert row["Model Prob"] == 0.64
    assert row["Edge"] == 0.08
    assert row["Confidence"] == "HIGH"
    assert row["Ticker"] == "KXATPMATCH-26MAY04ALPBRA-ALP"


def test_tennis_predictions_page_renders_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero governed rows render the tennis predictions empty state."""
    fake_st = FakeStreamlit()
    monkeypatch.setattr(tennis_predictions, "st", fake_st)
    monkeypatch.setattr(
        tennis_predictions.data_layer,
        "get_tomorrow_tennis_predictions",
        _empty_predictions,
    )

    tennis_predictions.render()

    rendered_text = _flatten_calls(fake_st)
    assert "no_tennis_predictions" in rendered_text
    assert "No actionable tennis predictions" in rendered_text
    assert not [call for call in fake_st.calls if call[0] == "dataframe"]


def test_tennis_predictions_page_renders_sanitized_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Data-layer failures show sanitized payloads without raw SQL details."""
    fake_st = FakeStreamlit()
    monkeypatch.setattr(tennis_predictions, "st", fake_st)

    def raise_error() -> pd.DataFrame:
        raise data_layer.DashboardDataError(
            data_layer.DashboardStatePayload(
                kind="dashboard_query_failed",
                title="Dashboard query failed",
                message="The governed read model dashboard_tennis_predictions_v1 could not be read.",
                action="Check dashboard data-layer logs and read-model migrations.",
                severity="error",
            )
        )

    monkeypatch.setattr(
        tennis_predictions.data_layer, "get_tomorrow_tennis_predictions", raise_error
    )

    tennis_predictions.render()

    rendered_text = _flatten_calls(fake_st)
    assert "dashboard_query_failed" in rendered_text
    assert "dashboard_tennis_predictions_v1" in rendered_text
    assert "SELECT" not in rendered_text
    assert "password" not in rendered_text
