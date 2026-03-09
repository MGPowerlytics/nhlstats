import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from data_validation import GamesSummary


def test_games_summary_from_row_all_values():
    row = (100, 90, "2023-10-01", "2024-04-15", 32, 32, 0, 0, 80, 20)
    summary = GamesSummary.from_row(row, sport="NBA")

    assert summary.total == 100
    assert summary.unique == 90
    assert summary.min_date == "2023-10-01"
    assert summary.max_date == "2024-04-15"
    assert summary.home_teams == 32
    assert summary.away_teams == 32
    assert summary.null_home_scores == 0
    assert summary.null_away_scores == 0
    assert summary.completed_games == 80
    assert summary.future_games == 20


def test_games_summary_from_row_with_nones():
    # Test that None values are coalesced correctly
    row = (None, None, None, None, None, None, None, None, None, None)
    summary = GamesSummary.from_row(row, sport="NBA")

    assert summary.total == 0
    assert summary.unique == 0
    assert summary.min_date is None
    assert summary.max_date is None
    assert summary.home_teams == 0
    assert summary.away_teams == 0
    assert summary.null_home_scores == 0
    assert summary.null_away_scores == 0
    assert summary.completed_games == 0
    assert summary.future_games == 0


def test_games_summary_from_row_mixed_values():
    row = (100, None, "2023-10-01", None, 32, None, 5, None, 80, None)
    summary = GamesSummary.from_row(row, sport="NBA")

    assert summary.total == 100
    assert summary.unique == 0
    assert summary.min_date == "2023-10-01"
    assert summary.max_date is None
    assert summary.home_teams == 32
    assert summary.away_teams == 0
    assert summary.null_home_scores == 5
    assert summary.null_away_scores == 0
    assert summary.completed_games == 80
    assert summary.future_games == 0
