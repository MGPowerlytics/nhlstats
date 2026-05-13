"""Calibration — governed model accuracy and probability bucket analysis."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from dashboard.data_layer import DashboardDataError, get_calibration_data


def _format_validation_state(state: str | None) -> str:
    """Format a governed evidence-state code for operator display."""

    if not state:
        return "unknown"
    return state.replace("_", "-")


def _render_state(payload: dict[str, str | None]) -> None:
    """Render a governed empty/error state without exposing raw exceptions."""

    title = payload["title"] or "Dashboard state"
    message = payload["message"]
    action = payload["action"]
    body = title if message is None else f"{title}: {message}"
    severity = payload.get("severity")

    if severity == "error":
        st.error(body)
    elif severity == "warning":
        st.warning(body)
    else:
        st.info(body)

    if action:
        st.caption(action)


def _format_percent(value: float | None) -> str:
    """Format a nullable probability/percentage value for display."""

    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.1%}"


def _format_number(value: float | None) -> str:
    """Format a nullable numeric value for display."""

    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.3f}"


def _bucket_table(buckets: list[dict]) -> pd.DataFrame:
    """Return display-ready calibration bucket rows."""

    return pd.DataFrame(
        [
            {
                "Probability bucket": bucket["label"],
                "Predictions": bucket["prediction_count"],
                "Avg Elo Prob": _format_percent(bucket["avg_elo_prob"]),
                "Avg Market Prob": _format_percent(bucket["avg_market_prob"]),
                "Observed Win Rate": _format_percent(bucket["observed_win_rate"]),
                "Avg Edge": _format_percent(bucket["avg_edge"]),
                "Avg Expected Value": _format_number(bucket["avg_expected_value"]),
                "Settled": bucket["settled_count"],
                "Unsettled": bucket["unsettled_count"],
            }
            for bucket in buckets
        ]
    )


def _render_sport_validation(payload: dict[str, str | None]) -> None:
    """Render governed sport-validation cues for a selected sport."""

    sport = payload.get("sport") or "Selected sport"
    evidence_state = _format_validation_state(payload.get("evidence_state"))
    reason = payload.get("evidence_state_reason") or "No governed reason published."
    contamination = payload.get("contamination_reason") or "none"
    source_artifact = (
        payload.get("evidence_state_source_artifact") or "approval artifact unavailable"
    )
    runtime_consumer = payload.get("runtime_consumer") or "not published"

    st.subheader("Governed Sport Validation")
    st.warning(f"{sport} is {evidence_state}: {reason}")
    st.caption(f"Contamination: {contamination}")
    st.caption(f"Source artifact: {source_artifact}")
    st.caption(f"Runtime consumer: {runtime_consumer}")


def render():
    st.title("Model Calibration")

    sport_filter = st.selectbox(
        "Sport",
        [
            "All",
            "NBA",
            "NHL",
            "MLB",
            "NFL",
            "NCAAB",
            "WNCAAB",
            "TENNIS",
            "EPL",
            "Ligue1",
            "CBA",
            "Unrivaled",
        ],
    )
    sport = None if sport_filter == "All" else sport_filter

    try:
        data = get_calibration_data(sport)
    except DashboardDataError as exc:
        _render_state(exc.payload)
        return

    sport_validation_state = data.get("sport_validation_state")
    if sport and sport_validation_state:
        _render_sport_validation(sport_validation_state)
        if sport_validation_state.get("evidence_state") in {"blocked", "shadow_only"}:
            return

    empty_state = data.get("empty_state")
    if empty_state:
        _render_state(empty_state)
        return

    buckets = data.get("buckets", [])

    st.subheader("Probability Buckets")
    if buckets:
        st.dataframe(
            _bucket_table(buckets),
            use_container_width=True,
            hide_index=True,
        )

    settled_empty_state = data.get("settled_empty_state")
    if settled_empty_state:
        _render_state(settled_empty_state)
        return

    st.subheader("Calibration Curve")
    if buckets:
        settled_buckets = [
            bucket for bucket in buckets if bucket["observed_win_rate"] is not None
        ]
        if not settled_buckets:
            return

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=[
                    (bucket["bucket_start"] + bucket["bucket_end"]) / 2
                    for bucket in settled_buckets
                ],
                y=[bucket["observed_win_rate"] for bucket in settled_buckets],
                mode="lines+markers",
                name="Observed Win Rate",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[0, 1],
                y=[0, 1],
                mode="lines",
                line=dict(dash="dash", color="gray"),
                name="Perfect Calibration",
            )
        )
        fig.update_layout(
            xaxis_title="Predicted Probability",
            yaxis_title="Actual Win Rate",
            xaxis=dict(range=[0, 1]),
            yaxis=dict(range=[0, 1]),
        )
        st.plotly_chart(fig, use_container_width=True)
