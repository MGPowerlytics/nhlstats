from __future__ import annotations

import csv
from copy import deepcopy
from io import StringIO
from typing import Any


_BASE_EPL_CSV_ROW: dict[str, Any] = {
    "Date": "16/08/2025",
    "HomeTeam": "Liverpool",
    "AwayTeam": "Bournemouth",
    "FTHG": 2,
    "FTAG": 0,
    "FTR": "H",
}

_EPL_CANONICAL_TEAM_NAME_CASES: tuple[tuple[str, str], ...] = (
    ("Liverpool", "Liverpool"),
    ("Manchester City", "Man City"),
    ("Manchester United", "Man United"),
    ("Nottingham Forest", "Nott'm Forest"),
    ("Tottenham Hotspur", "Tottenham"),
    ("West Ham United", "West Ham"),
    ("Wolverhampton Wanderers", "Wolves"),
)


def build_epl_csv_row(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic EPL CSV row sample for contract validation."""
    row = deepcopy(_BASE_EPL_CSV_ROW)
    row.update(overrides)
    return row


def build_epl_csv_text(*rows: dict[str, Any]) -> str:
    """Build deterministic EPL CSV file contents for provider-side contract tests."""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(_BASE_EPL_CSV_ROW.keys()))
    writer.writeheader()
    writer.writerows(rows or [build_epl_csv_row()])
    return output.getvalue()


def build_epl_canonical_team_name_cases() -> tuple[tuple[str, str], ...]:
    """Return deterministic EPL-only raw-to-canonical team-name cases."""
    return tuple(_EPL_CANONICAL_TEAM_NAME_CASES)
