"""Focused unit tests for the Tennis Model Health dashboard page."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from dashboard import data_layer
from dashboard.pages import tennis_model_health


class FakeStreamlit:
    """Capture Streamlit calls made by the Tennis Model Health page."""

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


def _seeded_health() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "run_date": "2026-05-11",
                "model_version": "tennis_probability_model_v2",
                "data_source": "postgres_tennis_games",
                "rows": 960,
                "holdout_rows": 192,
                "betmgm_holdout_rows": 144,
                "enabled": True,
                "beats_betmgm": True,
                "baseline_log_loss": 0.6221,
                "ensemble_log_loss": 0.5982,
                "ensemble_market_log_loss": 0.6034,
                "betmgm_log_loss": 0.6178,
                "baseline_brier": 0.2174,
                "ensemble_brier": 0.2091,
                "ensemble_market_brier": 0.2108,
                "betmgm_brier": 0.2156,
                "baseline_accuracy": 0.6771,
                "ensemble_accuracy": 0.6979,
                "ensemble_market_accuracy": 0.6944,
                "betmgm_accuracy": 0.6875,
                "baseline_actionable_count": 81,
                "ensemble_actionable_count": 104,
                "log_loss_delta": -0.0239,
                "brier_delta": -0.0083,
                "accuracy_delta": 0.0208,
                "ensemble_vs_betmgm_log_loss_delta": -0.0144,
                "ensemble_vs_betmgm_brier_delta": -0.0048,
                "ensemble_vs_betmgm_accuracy_delta": 0.0069,
                "created_at": "2026-05-11T19:45:00Z",
            }
        ],
        columns=data_layer.TENNIS_MODEL_HEALTH_COLUMNS,
    )


def _empty_health() -> pd.DataFrame:
    df = pd.DataFrame(columns=data_layer.TENNIS_MODEL_HEALTH_COLUMNS)
    df.attrs["empty_state"] = {
        "kind": "no_tennis_model_health",
        "title": "No production tennis model health snapshots",
        "message": "No production PostgreSQL tennis model-vs-BetMGM evaluation rows are available yet.",
        "action": (
            "Ingest tennis BetMGM odds and player-match stats, then run "
            "scripts/train_tennis_probability_model.py without --evaluate-only "
            "to publish production evidence to PostgreSQL."
        ),
        "severity": "info",
    }
    return df


def _flatten_calls(fake_st: FakeStreamlit) -> str:
    return "\n".join(str(item) for call in fake_st.calls for item in call)


def test_tennis_model_health_page_renders_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seeded rows expose the latest BetMGM comparison metrics."""
    fake_st = FakeStreamlit()
    monkeypatch.setattr(tennis_model_health, "st", fake_st)
    monkeypatch.setattr(
        tennis_model_health.data_layer,
        "get_tennis_model_health",
        _seeded_health,
    )

    tennis_model_health.render()

    dataframe_calls = [call for call in fake_st.calls if call[0] == "dataframe"]
    assert len(dataframe_calls) == 1
    rendered = dataframe_calls[0][1].data
    row = rendered.iloc[0]
    assert bool(row["Beats BetMGM"]) is True
    assert row["Log Loss Delta"] == -0.0144
    assert row["Accuracy Delta"] == 0.0069
    rendered_text = _flatten_calls(fake_st)
    assert (
        "Calibration metrics (log loss and Brier) are the primary quality bar"
        in rendered_text
    )


def test_tennis_model_health_page_renders_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero governed rows render the tennis model-health empty state."""
    fake_st = FakeStreamlit()
    monkeypatch.setattr(tennis_model_health, "st", fake_st)
    monkeypatch.setattr(
        tennis_model_health.data_layer,
        "get_tennis_model_health",
        _empty_health,
    )

    tennis_model_health.render()

    rendered_text = _flatten_calls(fake_st)
    assert "no_tennis_model_health" in rendered_text
    assert "No production tennis model health snapshots" in rendered_text
    assert not [call for call in fake_st.calls if call[0] == "dataframe"]


def test_tennis_model_health_page_renders_sanitized_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Data-layer failures show sanitized payloads without raw SQL details."""
    fake_st = FakeStreamlit()
    monkeypatch.setattr(tennis_model_health, "st", fake_st)

    def raise_error() -> pd.DataFrame:
        raise data_layer.DashboardDataError(
            data_layer.DashboardStatePayload(
                kind="dashboard_query_failed",
                title="Dashboard query failed",
                message="The governed read model dashboard_tennis_model_health_v1 could not be read.",
                action="Check dashboard data-layer logs and read-model migrations.",
                severity="error",
            )
        )

    monkeypatch.setattr(
        tennis_model_health.data_layer, "get_tennis_model_health", raise_error
    )

    tennis_model_health.render()

    rendered_text = _flatten_calls(fake_st)
    assert "dashboard_query_failed" in rendered_text
    assert "dashboard_tennis_model_health_v1" in rendered_text
    assert "SELECT" not in rendered_text
    assert "password" not in rendered_text
