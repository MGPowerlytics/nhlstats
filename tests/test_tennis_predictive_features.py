"""Tests for advanced tennis predictive feature engineering."""

from __future__ import annotations

import math

import pandas as pd

from plugins.elo.tennis_features import TennisFeatureBuilder, TennisFeatureConfig


def test_time_decay_gives_one_year_old_match_configured_weight() -> None:
    """A one-year-old match should receive the configured recency weight."""
    builder = TennisFeatureBuilder(TennisFeatureConfig(one_year_weight=0.80))

    weight = builder.time_weight(age_days=365.25)

    assert weight == pytest_approx(0.80)


def test_surface_transfer_weights_hard_grass_more_than_clay_grass() -> None:
    """Surface transfer should respect tennis skill correlations."""
    builder = TennisFeatureBuilder()

    hard_to_grass = builder.surface_weight("Hard", "Grass")
    clay_to_grass = builder.surface_weight("Clay", "Grass")

    assert hard_to_grass > clay_to_grass
    assert builder.surface_weight("Hard", "Hard") == 1.0


def test_matchup_features_use_common_opponents_and_intransitivity() -> None:
    """Common-opponent records should drive matchup-relative features."""
    history = pd.DataFrame(
        [
            _match(
                "2026-01-01",
                "Player A",
                "Common C",
                surface="Hard",
                w_svpt=100,
                w_1st_won=45,
                w_2nd_won=25,
                l_svpt=90,
                l_1st_won=35,
                l_2nd_won=18,
            ),
            _match(
                "2026-01-02",
                "Common C",
                "Player B",
                surface="Hard",
                w_svpt=92,
                w_1st_won=44,
                w_2nd_won=18,
                l_svpt=96,
                l_1st_won=38,
                l_2nd_won=17,
            ),
            _match(
                "2026-01-03",
                "Player B",
                "Player A",
                surface="Hard",
                w_svpt=88,
                w_1st_won=42,
                w_2nd_won=20,
                l_svpt=84,
                l_1st_won=36,
                l_2nd_won=16,
            ),
        ]
    )
    builder = TennisFeatureBuilder()

    features = builder.build_matchup_features(
        history,
        player_a="Player A",
        player_b="Player B",
        as_of_date="2026-01-10",
        surface="Hard",
        tour="ATP",
    )

    assert features.common_opponent_count == 1
    assert features.common_opponent_win_rate_diff > 0
    assert features.intransitivity_complexity > 0
    assert features.serveadv_a == pytest_approx(
        features.serve_win_pct_a - features.return_win_pct_b
    )
    assert features.complete_a == pytest_approx(
        features.serve_win_pct_a * features.return_win_pct_a
    )


def test_fatigue_and_retired_features_track_recent_physical_state() -> None:
    """Recent games and retirement tags should be exposed as player-state features."""
    history = pd.DataFrame(
        [
            _match(
                "2026-01-09",
                "Opponent X",
                "Player A",
                score="6-4 2-1 RET",
                w_svpt=40,
                w_1st_won=20,
                w_2nd_won=8,
                l_svpt=35,
                l_1st_won=13,
                l_2nd_won=5,
            ),
            _match(
                "2025-12-01",
                "Player B",
                "Opponent Y",
                score="6-4 6-4",
                w_svpt=70,
                w_1st_won=34,
                w_2nd_won=15,
                l_svpt=66,
                l_1st_won=27,
                l_2nd_won=12,
            ),
        ]
    )
    builder = TennisFeatureBuilder()

    features = builder.build_matchup_features(
        history,
        player_a="Player A",
        player_b="Player B",
        as_of_date="2026-01-10",
        surface="Hard",
        tour="ATP",
    )

    assert features.fatigue_a > features.fatigue_b
    assert features.retired_a == 1
    assert features.retired_b == 0
    assert features.fatigue_diff == pytest_approx(
        features.fatigue_a - features.fatigue_b
    )


def test_age_30_uses_absolute_distance_from_optimal_age() -> None:
    """Age.30 should be encoded as distance from age 30."""
    history = pd.DataFrame(
        [
            _match("2026-01-01", "Player A", "Opponent X", winner_age=32.5),
            _match("2026-01-01", "Player B", "Opponent Y", winner_age=25.0),
        ]
    )
    builder = TennisFeatureBuilder()

    features = builder.build_matchup_features(
        history,
        player_a="Player A",
        player_b="Player B",
        as_of_date="2026-01-10",
        surface="Hard",
        tour="ATP",
    )

    assert features.age_30_a == pytest_approx(2.5)
    assert features.age_30_b == pytest_approx(5.0)


def _match(
    date: str,
    winner: str,
    loser: str,
    *,
    surface: str = "Hard",
    score: str = "6-4 6-4",
    tour: str = "ATP",
    winner_age: float | None = None,
    loser_age: float | None = None,
    w_svpt: int = 80,
    w_1st_won: int = 40,
    w_2nd_won: int = 16,
    l_svpt: int = 76,
    l_1st_won: int = 30,
    l_2nd_won: int = 12,
) -> dict[str, object]:
    return {
        "date": date,
        "winner": winner,
        "loser": loser,
        "surface": surface,
        "score": score,
        "tour": tour,
        "winner_age": winner_age,
        "loser_age": loser_age,
        "w_svpt": w_svpt,
        "w_1stWon": w_1st_won,
        "w_2ndWon": w_2nd_won,
        "l_svpt": l_svpt,
        "l_1stWon": l_1st_won,
        "l_2ndWon": l_2nd_won,
    }


def pytest_approx(value: float) -> object:
    """Local alias avoids importing pytest solely for approx in production examples."""
    import pytest

    if math.isnan(value):
        raise AssertionError("NaN is not a valid expected value")
    return pytest.approx(value, rel=1e-6, abs=1e-6)
