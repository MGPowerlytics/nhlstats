"""Deterministic Sackmann / tennis-data.co.uk CSV row builders for tennis contracts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_CSV_ROW: dict[str, Any] = {
    "Date": "2026-04-07",
    "Winner": "Cobolli F.",
    "Loser": "Blockx A.",
    "Tournament": "Monte Carlo Masters",
    "Surface": "Clay",
    "Score": "6-4 7-5",
    "Round": "1st Round",
    "Series": "Masters 1000",
    "Best of": 3,
    "WRank": 32,
    "LRank": 134,
}


def build_tennis_csv_row(**overrides: Any) -> dict[str, Any]:
    """Return a deterministic Sackmann/tennis-data.co.uk CSV row sample."""
    row = deepcopy(_BASE_CSV_ROW)
    row.update(overrides)
    return row


def build_tennis_csv_minimal_row() -> dict[str, Any]:
    """Return the minimal CSV row with only required fields populated."""
    return {
        "Date": "2026-04-08",
        "Winner": "Sinner J.",
        "Loser": "Alcaraz C.",
    }
