"""TDD tests for the 2026-04-18 MLB Elo accuracy-improvement pass.

Verifies the four production changes that together yield +3.01% relative
accuracy on the 2021-2024 backtest:

1. K-factor default is 4 (down from 10).
2. Home advantage default is 20 Elo points (down from 75).
3. Spring-training games (pre-Mar 20) are filtered by
   :func:`is_regular_season_date`.
4. Margin-of-victory multiplier is OFF by default (``use_mov=False``).
"""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from elo.mlb_elo_rating import MLBEloRating, is_regular_season_date


def test_default_k_factor_is_four():
    """K=4 minimizes overfitting to MLB's high game-to-game variance."""
    assert MLBEloRating().k_factor == 4.0


def test_default_home_advantage_is_twenty():
    """HA=20 matches the empirical 53.2% home win rate."""
    assert MLBEloRating().home_advantage == 20.0


def test_mov_disabled_by_default():
    """MOV multiplier hurts MLB accuracy and is off by default."""
    assert MLBEloRating().use_mov is False


def test_mov_can_be_enabled_via_kwarg():
    """Callers may opt in to MOV explicitly."""
    assert MLBEloRating(use_mov=True).use_mov is True


def test_score_blowout_does_not_change_rating_when_mov_off():
    """With MOV off, a 10-1 win moves ratings the same as a 2-1 win."""
    elo_blowout = MLBEloRating()
    elo_blowout.update("A", "B", home_won=True, home_score=10, away_score=1)

    elo_close = MLBEloRating()
    elo_close.update("A", "B", home_won=True, home_score=2, away_score=1)

    assert elo_blowout.get_rating("A") == pytest.approx(elo_close.get_rating("A"))


def test_score_blowout_amplifies_change_when_mov_on():
    """Re-enabling MOV restores the blowout amplification (regression guard)."""
    elo_blowout = MLBEloRating(use_mov=True)
    elo_blowout.update("A", "B", home_won=True, home_score=10, away_score=1)

    elo_close = MLBEloRating(use_mov=True)
    elo_close.update("A", "B", home_won=True, home_score=2, away_score=1)

    assert elo_blowout.get_rating("A") > elo_close.get_rating("A")


@pytest.mark.parametrize(
    "game_date,expected",
    [
        ("2024-02-25", False),  # spring training
        ("2024-03-15", False),  # spring training
        ("2024-03-19", False),  # day before cutoff
        ("2024-03-20", True),  # earliest opener (Seoul series)
        ("2024-04-01", True),  # standard opening week
        ("2024-10-30", True),  # World Series
        (date(2023, 3, 1), False),
        (date(2023, 4, 5), True),
    ],
)
def test_is_regular_season_date(game_date, expected):
    """Spring training (pre-Mar 20) must be filterable."""
    assert is_regular_season_date(game_date) is expected


def test_apply_season_carryover_regresses_to_mean():
    """Season carryover regresses ratings toward 1500 by the given weight."""
    elo = MLBEloRating()
    elo.set_rating("Hot Team", 1600.0)
    elo.set_rating("Cold Team", 1400.0)

    elo.apply_season_carryover(regression_weight=0.25)

    assert elo.get_rating("Hot Team") == pytest.approx(1575.0)
    assert elo.get_rating("Cold Team") == pytest.approx(1425.0)


def test_apply_season_carryover_zero_is_noop():
    """Default 0.0 weight leaves ratings untouched (matches grid optimum)."""
    elo = MLBEloRating()
    elo.set_rating("Team", 1623.4)
    elo.apply_season_carryover(regression_weight=0.0)
    assert elo.get_rating("Team") == 1623.4
