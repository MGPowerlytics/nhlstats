"""Deterministic CSVHistoryLoader contract fixtures.

Builders for CSV row samples and processor params that satisfy the
``csv_history_loader_contract_v1.json`` schema definitions.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# ---------------------------------------------------------------------------
# EPL CSV row samples
# ---------------------------------------------------------------------------

_BASE_EPL_CSV_ROW: dict[str, Any] = {
    "Date": "16/08/2025",
    "HomeTeam": "Liverpool",
    "AwayTeam": "Bournemouth",
    "FTHG": 2,
    "FTAG": 0,
    "FTR": "H",
}


def build_epl_csv_row(**overrides: Any) -> dict[str, Any]:
    """Build a canonical EPL CSV row sample.

    Represents a single row from a football-data.co.uk E0 CSV file
    as validated against the ``epl_csv_row`` contract definition.
    """
    payload = deepcopy(_BASE_EPL_CSV_ROW)
    payload.update(overrides)
    return payload


def build_epl_csv_text(*rows: dict[str, Any]) -> str:
    """Build deterministic EPL CSV file contents for provider-side tests."""
    from io import StringIO
    import csv

    output = StringIO()
    fieldnames = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows or [build_epl_csv_row()])
    return output.getvalue()


# ---------------------------------------------------------------------------
# Tennis CSV row samples
# ---------------------------------------------------------------------------

_BASE_TENNIS_CSV_ROW: dict[str, Any] = {
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
    """Build a canonical Tennis CSV row sample.

    Represents a single row from a Sackmann / tennis-data.co.uk CSV file
    as validated against the ``tennis_csv_row`` contract definition.
    """
    payload = deepcopy(_BASE_TENNIS_CSV_ROW)
    payload.update(overrides)
    return payload


def build_tennis_csv_text(*rows: dict[str, Any]) -> str:
    """Build deterministic Tennis CSV file contents for provider-side tests."""
    from io import StringIO
    import csv

    output = StringIO()
    fieldnames = [
        "Date", "Winner", "Loser", "Tournament", "Surface", "Score",
        "Round", "Series", "Best of", "WRank", "LRank",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows or [build_tennis_csv_row()])
    return output.getvalue()


# ---------------------------------------------------------------------------
# EPL processor params samples
# ---------------------------------------------------------------------------

_BASE_EPL_PROCESSOR_PARAMS: dict[str, Any] = {
    "game_id": "EPL_20250816_LIVERPOOL_BOURNEMOUTH",
    "game_date": "2025-08-16",
    "season": "2526",
    "home_team": "Liverpool",
    "away_team": "Bournemouth",
    "home_team_full": "Liverpool",
    "away_team_full": "Bournemouth",
    "home_score": 2,
    "away_score": 0,
    "result": "H",
}


def build_epl_processor_params(**overrides: Any) -> dict[str, Any]:
    """Build canonical EPL processor params.

    Represents the params dict produced by ``EPLCSVProcessor._extract_soccer_params``
    as validated against the ``epl_processor_params`` contract definition.
    """
    payload = deepcopy(_BASE_EPL_PROCESSOR_PARAMS)
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Tennis processor params samples
# ---------------------------------------------------------------------------

_BASE_TENNIS_PROCESSOR_PARAMS: dict[str, Any] = {
    "game_id": "TENNIS_ATP_2026-04-07_COBOLLIF_BLOCKXA",
    "game_date": "2026-04-07",
    "season": "2026",
    "tour": "ATP",
    "tournament": "Monte Carlo Masters",
    "surface": "Clay",
    "winner": "Cobolli F.",
    "loser": "Blockx A.",
    "score": "6-4 7-5",
}


def build_tennis_processor_params(**overrides: Any) -> dict[str, Any]:
    """Build canonical Tennis processor params.

    Represents the params dict produced by ``TennisCSVProcessor._extract_tennis_game_data``
    as validated against the ``tennis_processor_params`` contract definition.
    """
    payload = deepcopy(_BASE_TENNIS_PROCESSOR_PARAMS)
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Load CSV summary samples
# ---------------------------------------------------------------------------

_BASE_LOAD_CSV_SUMMARY: dict[str, Any] = {
    "sport": "epl",
    "file_name": "E0_2526.csv",
    "rows_loaded": 1,
}


def build_load_csv_summary(**overrides: Any) -> dict[str, Any]:
    """Build a canonical load_csv_summary payload.

    Represents the summary of a CSV file load operation.
    """
    payload = deepcopy(_BASE_LOAD_CSV_SUMMARY)
    payload.update(overrides)
    return payload
