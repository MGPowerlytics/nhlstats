"""Shared dashboard rendering utilities used by all pages."""

from __future__ import annotations

from typing import Any

import streamlit as st

SPORT_OPTIONS = [
    "NBA",
    "NHL",
    "MLB",
    "NFL",
    "NCAAB",
    "WNCAAB",
    "TENNIS",
    "EPL",
    "LIGUE1",
    "CBA",
    "UNRIVALED",
]


def render_state(
    payload: dict[str, Any] | None,
    *,
    context: str | None = None,
) -> None:
    """Render a governed dashboard empty, error, or warning state.

    Args:
        payload: Sanitized data-layer state dict with ``kind``, ``title``,
            ``message``, ``action``, and ``severity`` keys.
        context: Optional extra context appended to the message body (used
            by bet-detail to show the selected bet ID).
    """
    if not payload:
        return

    title = payload.get("title") or "Dashboard state"
    message = payload.get("message")
    action = payload.get("action")
    kind = payload.get("kind")
    severity = payload.get("severity")

    body: str
    if message:
        body = f"{title} — {message}"
    else:
        body = str(title)

    if context:
        body = f"{body} — {context}"

    if severity == "error":
        st.error(body)
    elif severity == "warning":
        st.warning(body)
    else:
        st.info(body)

    if action:
        st.caption(action)
    if kind:
        st.caption(f"State: {kind}")
