import pandas as pd
import streamlit as st

from dashboard.data_layer import DashboardDataError, get_data_quality_report


DISPLAY_COLUMNS = {
    "status": "Status",
    "check_name": "Check",
    "relation_name": "Relation",
    "relation_type": "Type",
    "row_count": "Rows",
    "freshness_timestamp": "Freshness Timestamp",
    "actual_lag_minutes": "Lag (min)",
    "max_allowed_lag_minutes": "Max Lag (min)",
    "message": "Message",
    "checked_at_utc": "Checked At",
}


def _state_text(payload: dict[str, str | None]) -> str:
    """Build a compact, sanitized state message from a data-layer payload."""

    parts = [
        payload.get("kind"),
        payload.get("title"),
        payload.get("message"),
        payload.get("action"),
    ]
    return " — ".join(str(part) for part in parts if part)


def _render_state(payload: dict[str, str | None]) -> None:
    """Render an explicit governed error state."""

    message = _state_text(payload)
    if payload.get("severity") == "error":
        st.error(message)
    else:
        st.info(message)


def _fallback_zero_check_error() -> dict[str, str]:
    """Return the hard error shown when the report has no checks."""

    return {
        "kind": "dashboard_contract_mismatch",
        "title": "Dashboard contract mismatch",
        "message": "The governed data-quality report returned zero checks.",
        "action": "Apply dashboard read-model migrations and rerun checks.",
        "severity": "error",
    }


def _format_cell(value: object) -> object:
    """Return a display-safe value without fabricating missing data."""

    if value is None or pd.isna(value):
        return "—"
    return str(value) if not isinstance(value, (int, float)) else value


def _display_checks(checks: list[dict[str, object]]) -> pd.DataFrame:
    """Return the governed checks in a page-friendly display shape."""

    display = pd.DataFrame(checks)
    display = display[
        [column for column in DISPLAY_COLUMNS if column in display.columns]
    ]
    display = display.rename(columns=DISPLAY_COLUMNS)
    for column in display.columns:
        display[column] = display[column].map(_format_cell)
    if "Status" in display.columns:
        display["Status"] = display["Status"].map(lambda value: str(value).upper())
    return display


def _degraded_summary(checks: list[dict[str, object]]) -> str:
    """Return a concise warning/failure summary."""

    warn_count = sum(1 for check in checks if check.get("status") == "warn")
    fail_count = sum(1 for check in checks if check.get("status") == "fail")
    warning_label = "warning" if warn_count == 1 else "warnings"
    failure_label = "failure" if fail_count == 1 else "failures"
    return (
        f"Degraded checks: {warn_count} {warning_label}, {fail_count} {failure_label}."
    )


def render():
    st.title("Data Quality")

    try:
        report = get_data_quality_report()
    except DashboardDataError as exc:
        _render_state(exc.payload)
        return

    overall = report.get("overall_health", 0)
    checks = report.get("checks", [])

    st.metric("Overall Health Score", f"{overall}/100")

    if not checks:
        _render_state(_fallback_zero_check_error())
        return

    st.subheader("Governed Data Quality Checks")
    if all(check.get("status") == "pass" for check in checks):
        st.success("All governed data-quality checks are passing.")
    else:
        st.warning(_degraded_summary(checks))

    st.dataframe(_display_checks(checks), use_container_width=True, hide_index=True)
