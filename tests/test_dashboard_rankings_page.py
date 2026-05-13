"""Focused tests for the governed rankings dashboard page."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from dashboard import data_layer
from dashboard.pages import rankings


@dataclass
class _FakeColumn:
    """Small Streamlit column test double."""

    parent: "_FakeStreamlit"

    def selectbox(
        self,
        label: str,
        options: list[str],
        key: str | None = None,
        index: int = 0,
    ) -> str:
        return self.parent.selectbox(label, options, key=key, index=index)

    def metric(self, label: str, value: Any, **kwargs: Any) -> None:
        self.parent.metrics.append((label, value, kwargs))


@dataclass
class _FakeStreamlit:
    """Record the Streamlit calls the rankings page makes."""

    selectbox_values: dict[str, str] = field(default_factory=dict)
    titles: list[str] = field(default_factory=list)
    subheaders: list[str] = field(default_factory=list)
    captions: list[str] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dataframes: list[Any] = field(default_factory=list)
    charts: list[Any] = field(default_factory=list)
    metrics: list[tuple[str, Any, dict[str, Any]]] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)

    def title(self, text: str) -> None:
        self.titles.append(text)

    def subheader(self, text: str) -> None:
        self.subheaders.append(text)

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def info(self, text: str) -> None:
        self.infos.append(text)

    def error(self, text: str) -> None:
        self.errors.append(text)

    def dataframe(self, data: Any, **kwargs: Any) -> None:
        self.dataframes.append(data)

    def plotly_chart(self, figure: Any, **kwargs: Any) -> None:
        self.charts.append(figure)

    def divider(self) -> None:
        return None

    def write(self, text: str) -> None:
        self.writes.append(text)

    def columns(self, spec: int | list[int]) -> list[_FakeColumn]:
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeColumn(self) for _ in range(count)]

    def selectbox(
        self,
        label: str,
        options: list[str],
        key: str | None = None,
        index: int = 0,
    ) -> str:
        lookup_key = key or label
        return self.selectbox_values.get(lookup_key, options[index])


def _rankings_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sport": "NHL",
                "entity_type": "team",
                "entity_id": "bos",
                "entity_name": "Boston Bruins",
                "rating": 1612.4,
                "rank": 1,
                "games_played": 82,
                "valid_from": datetime(2026, 5, 3, 12, tzinfo=timezone.utc),
                "valid_to": None,
                "created_at": datetime(2026, 5, 3, 12, 5, tzinfo=timezone.utc),
                "team": "Boston Bruins",
                "last_updated": "2026-05-03T12:00:00+00:00",
            },
            {
                "sport": "NHL",
                "entity_type": "team",
                "entity_id": "tor",
                "entity_name": "Toronto Maple Leafs",
                "rating": 1588.0,
                "rank": 2,
                "games_played": 82,
                "valid_from": datetime(2026, 5, 3, 12, tzinfo=timezone.utc),
                "valid_to": None,
                "created_at": datetime(2026, 5, 3, 12, 5, tzinfo=timezone.utc),
                "team": "Toronto Maple Leafs",
                "last_updated": "2026-05-03T12:00:00+00:00",
            },
        ]
    )


def test_rankings_page_renders_seeded_governed_rankings(
    monkeypatch,
) -> None:
    """Seeded read-model rows render ranking, entity, rating, games, and validity."""

    fake_st = _FakeStreamlit(
        selectbox_values={
            "Sport": "NHL",
            "team_a": "Boston Bruins",
            "team_b": "Toronto Maple Leafs",
        }
    )
    monkeypatch.setattr(rankings, "st", fake_st)
    monkeypatch.setattr(
        rankings, "get_current_elo_ratings", lambda sport: _rankings_frame()
    )
    monkeypatch.setattr(
        rankings, "get_elo_history", lambda *args, **kwargs: pd.DataFrame()
    )

    rankings.render()

    assert "NHL Ratings (2 active rows)" in fake_st.subheaders
    assert fake_st.dataframes
    displayed = fake_st.dataframes[0].data
    assert list(displayed.columns) == [
        "rank",
        "sport",
        "entity_type",
        "entity_name",
        "rating",
        "games_played",
        "valid_from",
        "valid_to",
        "created_at",
    ]
    assert displayed.iloc[0]["entity_name"] == "Boston Bruins"
    assert displayed.iloc[0]["games_played"] == 82


def test_rankings_page_renders_explicit_no_rankings_empty_state(monkeypatch) -> None:
    """Zero read-model rows render the governed no_rankings empty state."""

    empty = pd.DataFrame()
    empty.attrs["empty_state"] = {
        "kind": "no_rankings",
        "title": "No rankings",
        "message": "No governed active ranking rows are available for the selected sport.",
        "action": "Run rating ingestion before comparing teams.",
        "severity": "info",
    }
    fake_st = _FakeStreamlit(selectbox_values={"Sport": "NHL"})
    monkeypatch.setattr(rankings, "st", fake_st)
    monkeypatch.setattr(rankings, "get_current_elo_ratings", lambda sport: empty)

    rankings.render()

    rendered_text = " ".join(fake_st.infos + fake_st.captions)
    assert "no_rankings" in rendered_text
    assert "No rankings" in rendered_text
    assert "Run rating ingestion" in rendered_text


def test_rankings_page_renders_sanitized_data_layer_error(monkeypatch) -> None:
    """Typed data-layer failures render only their sanitized payload."""

    fake_st = _FakeStreamlit(selectbox_values={"Sport": "NHL"})
    monkeypatch.setattr(rankings, "st", fake_st)
    error = data_layer.DashboardDataError(
        data_layer.DashboardStatePayload(
            kind="dashboard_query_failed",
            title="Dashboard query failed",
            message="The governed read model dashboard_rankings_v1 could not be read.",
            action="Check dashboard data-layer logs and read-model migrations.",
            severity="error",
        )
    )
    monkeypatch.setattr(
        rankings,
        "get_current_elo_ratings",
        lambda sport: (_ for _ in ()).throw(error),
    )

    rankings.render()

    rendered_text = " ".join(fake_st.errors + fake_st.captions)
    assert "dashboard_query_failed" in rendered_text
    assert "dashboard_rankings_v1" in rendered_text
    assert "SELECT" not in rendered_text
    assert "password" not in rendered_text
    assert "Traceback" not in rendered_text
