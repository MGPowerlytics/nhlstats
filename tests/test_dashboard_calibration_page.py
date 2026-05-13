"""Focused tests for the governed calibration dashboard page."""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard import data_layer
from dashboard.pages import calibration


class FakeStreamlit:
    """Minimal Streamlit test double for calibration page rendering."""

    def __init__(self, selected_option: str = "All") -> None:
        self.dataframes: list[pd.DataFrame] = []
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.captions: list[str] = []
        self.plot_count = 0
        self.selected_option = selected_option

    def title(self, _text: str) -> None:
        pass

    def selectbox(self, _label: str, options: list[str]) -> str:
        assert self.selected_option in options
        return self.selected_option

    def subheader(self, _text: str) -> None:
        pass

    def dataframe(self, data: pd.DataFrame, **_kwargs: object) -> None:
        self.dataframes.append(data)

    def plotly_chart(self, _figure: object, **_kwargs: object) -> None:
        self.plot_count += 1

    def info(self, text: str) -> None:
        self.infos.append(text)

    def warning(self, text: str) -> None:
        self.warnings.append(text)

    def error(self, text: str) -> None:
        self.errors.append(text)

    def caption(self, text: str) -> None:
        self.captions.append(text)


def _seeded_buckets() -> list[dict]:
    return [
        {
            "label": "50%-60%",
            "bucket_start": 0.5,
            "bucket_end": 0.6,
            "prediction_count": 12,
            "avg_elo_prob": 0.55,
            "avg_market_prob": 0.51,
            "observed_win_rate": 0.5,
            "avg_edge": 0.04,
            "avg_expected_value": 0.021,
            "settled_count": 10,
            "unsettled_count": 2,
        }
    ]


def _render_with(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict | data_layer.DashboardDataError,
    *,
    selected_option: str = "All",
) -> FakeStreamlit:
    fake_st = FakeStreamlit(selected_option=selected_option)
    monkeypatch.setattr(calibration, "st", fake_st)

    def fake_get_calibration_data(_sport: str | None = None) -> dict:
        if isinstance(payload, data_layer.DashboardDataError):
            raise payload
        return payload

    monkeypatch.setattr(calibration, "get_calibration_data", fake_get_calibration_data)
    calibration.render()
    return fake_st


def test_calibration_page_renders_seeded_probability_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seeded calibration rows render all governed bucket fields."""

    fake_st = _render_with(
        monkeypatch,
        {
            "buckets": _seeded_buckets(),
            "empty_state": None,
            "sport_validation_state": None,
            "settled_empty_state": None,
        },
    )

    assert fake_st.errors == []
    assert fake_st.infos == []
    assert fake_st.plot_count == 1
    display = fake_st.dataframes[0]
    assert list(display.columns) == [
        "Probability bucket",
        "Predictions",
        "Avg Elo Prob",
        "Avg Market Prob",
        "Observed Win Rate",
        "Avg Edge",
        "Avg Expected Value",
        "Settled",
        "Unsettled",
    ]
    assert display.iloc[0].to_dict() == {
        "Probability bucket": "50%-60%",
        "Predictions": 12,
        "Avg Elo Prob": "55.0%",
        "Avg Market Prob": "51.0%",
        "Observed Win Rate": "50.0%",
        "Avg Edge": "4.0%",
        "Avg Expected Value": "0.021",
        "Settled": 10,
        "Unsettled": 2,
    }


def test_calibration_page_renders_no_predictions_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No calibration rows render no_calibration_predictions only."""

    fake_st = _render_with(
        monkeypatch,
        {
            "buckets": [],
            "empty_state": {
                "kind": "no_calibration_predictions",
                "title": "No calibration predictions",
                "message": "No governed calibration prediction rows are available yet.",
                "action": "Run recommendation ingestion before reviewing calibration.",
                "severity": "info",
            },
            "sport_validation_state": None,
            "settled_empty_state": None,
        },
    )

    assert fake_st.dataframes == []
    assert fake_st.plot_count == 0
    assert fake_st.infos == [
        "No calibration predictions: No governed calibration prediction rows are available yet."
    ]
    assert fake_st.captions == [
        "Run recommendation ingestion before reviewing calibration."
    ]


def test_calibration_page_distinguishes_no_settled_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Predictions without settled outcomes still render buckets and skip curve."""

    bucket = _seeded_buckets()[0] | {
        "observed_win_rate": None,
        "settled_count": 0,
        "unsettled_count": 12,
    }
    fake_st = _render_with(
        monkeypatch,
        {
            "buckets": [bucket],
            "empty_state": None,
            "sport_validation_state": None,
            "settled_empty_state": {
                "kind": "no_settled_calibration_outcomes",
                "title": "No settled calibration outcomes",
                "message": "Calibration predictions exist, but no governed settled outcomes are available yet.",
                "action": "Wait for recommended bets to settle before evaluating observed win rates.",
                "severity": "info",
            },
        },
    )

    assert len(fake_st.dataframes) == 1
    assert fake_st.dataframes[0].iloc[0]["Observed Win Rate"] == "—"
    assert fake_st.plot_count == 0
    assert fake_st.infos == [
        "No settled calibration outcomes: Calibration predictions exist, but no governed settled outcomes are available yet."
    ]


def test_calibration_page_renders_blocked_sport_validation_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blocked sports must render governed state instead of generic buckets."""

    fake_st = _render_with(
        monkeypatch,
        {
            "buckets": _seeded_buckets(),
            "empty_state": None,
            "sport_validation_state": {
                "sport": "NBA",
                "evidence_state": "blocked",
                "evidence_state_reason": (
                    "NBA remains blocked because no repeatable approval-grade "
                    "validation path is currently governed."
                ),
                "contamination_reason": None,
                "evidence_state_source_artifact": "docs/plan/example.md",
                "runtime_consumer": None,
            },
            "settled_empty_state": None,
        },
        selected_option="NBA",
    )

    assert fake_st.dataframes == []
    assert fake_st.plot_count == 0
    assert fake_st.warnings == [
        "NBA is blocked: NBA remains blocked because no repeatable approval-grade validation path is currently governed."
    ]
    assert "Contamination: none" in fake_st.captions


def test_calibration_page_renders_shadow_only_contamination_cues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shadow-only sports must expose contamination and provenance cues."""

    fake_st = _render_with(
        monkeypatch,
        {
            "buckets": _seeded_buckets(),
            "empty_state": None,
            "sport_validation_state": {
                "sport": "TENNIS",
                "evidence_state": "shadow_only",
                "evidence_state_reason": (
                    "TENNIS remains shadow-only because descriptive evidence exists "
                    "but approval-grade runtime provenance is incomplete."
                ),
                "contamination_reason": (
                    "binary_result_clv_contamination;" "synthetic_ticker_contamination"
                ),
                "evidence_state_source_artifact": "docs/plan/example.md",
                "runtime_consumer": "multi_sport_betting_workflow",
            },
            "settled_empty_state": None,
        },
        selected_option="TENNIS",
    )

    assert fake_st.dataframes == []
    assert fake_st.plot_count == 0
    assert fake_st.warnings == [
        "TENNIS is shadow-only: TENNIS remains shadow-only because descriptive evidence exists but approval-grade runtime provenance is incomplete."
    ]
    assert (
        "Contamination: binary_result_clv_contamination;synthetic_ticker_contamination"
        in fake_st.captions
    )
    assert "Runtime consumer: multi_sport_betting_workflow" in fake_st.captions


def test_calibration_page_renders_sanitized_data_layer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Data-layer failures render the sanitized payload, not raw exception details."""

    raw_secret = "SELECT password FROM accounts postgresql://user:secret@host/db"
    error = data_layer.DashboardDataError(
        data_layer.DashboardStatePayload(
            kind="dashboard_query_failed",
            title="Dashboard query failed",
            message="The governed read model dashboard_calibration_v1 could not be read.",
            action="Check dashboard data-layer logs and read-model migrations.",
            severity="error",
        )
    )
    fake_st = _render_with(monkeypatch, error)

    assert fake_st.dataframes == []
    assert fake_st.plot_count == 0
    assert fake_st.errors == [
        "Dashboard query failed: The governed read model dashboard_calibration_v1 could not be read."
    ]
    rendered = " ".join(fake_st.errors + fake_st.captions)
    assert raw_secret not in rendered
    assert "SELECT password" not in rendered
    assert "postgresql://" not in rendered


def test_calibration_page_has_no_direct_sql_or_source_table_references() -> None:
    """Calibration page must stay behind dashboard.data_layer APIs."""

    page_text = calibration.__loader__.get_source(calibration.__name__)
    forbidden_tokens = (
        "SELECT ",
        " FROM ",
        " JOIN ",
        "bet_recommendations",
        "placed_bets",
        "dashboard_calibration_v1",
    )

    assert page_text is not None
    for token in forbidden_tokens:
        assert token not in page_text
