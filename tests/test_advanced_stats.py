"""Tests for plugins/stats/advanced_stats.py — Wave 2 implementations."""

from __future__ import annotations

import pytest
import pandas as pd

from plugins.stats.advanced_stats import (
    compute_basketball_drtg,
    compute_basketball_efg,
    compute_basketball_ortg,
    compute_basketball_pace,
    compute_basketball_ts,
    compute_baseball_fip,
    compute_baseball_woba,
    compute_hockey_corsi,
    compute_nfl_epa_aggregate,
    compute_soccer_ppda,
    estimate_basketball_possessions,
)


# ---------------------------------------------------------------------------
# Basketball — eFG%
# ---------------------------------------------------------------------------


class TestComputeBasketballEfg:
    def test_typical_game(self) -> None:
        """Standard game: 40 FGM, 10 FG3M, 80 FGA → (40 + 5) / 80 = 0.5625."""
        result = compute_basketball_efg(fgm=40, fg3m=10, fga=80)
        assert abs(result - 0.5625) < 1e-6

    def test_no_three_pointers(self) -> None:
        """When no threes made eFG% equals FG% exactly."""
        result = compute_basketball_efg(fgm=30, fg3m=0, fga=60)
        assert abs(result - 0.5) < 1e-6

    def test_zero_fga_returns_zero(self) -> None:
        """Zero attempts must not raise and must return 0."""
        assert compute_basketball_efg(fgm=0, fg3m=0, fga=0) == 0.0

    def test_negative_fga_returns_zero(self) -> None:
        """Negative attempts are invalid; return 0."""
        assert compute_basketball_efg(fgm=5, fg3m=2, fga=-1) == 0.0


# ---------------------------------------------------------------------------
# Basketball — TS%
# ---------------------------------------------------------------------------


class TestComputeBasketballTs:
    def test_known_value(self) -> None:
        """PTS=100, FGA=80, FTA=20 → 100 / (2*(80+8.8)) = 100/177.6."""
        result = compute_basketball_ts(pts=100, fga=80, fta=20)
        expected = 100 / (2 * (80 + 0.44 * 20))
        assert abs(result - expected) < 1e-6

    def test_zero_attempts_returns_zero(self) -> None:
        """Both FGA and FTA = 0 must return 0."""
        assert compute_basketball_ts(pts=0, fga=0, fta=0) == 0.0

    def test_high_efficiency(self) -> None:
        """Free throw shooter only: PTS=10, FGA=0, FTA=10 → 10/(2*4.4)=~1.136."""
        result = compute_basketball_ts(pts=10, fga=0, fta=10)
        expected = 10 / (2 * 0.44 * 10)
        assert abs(result - expected) < 1e-6


# ---------------------------------------------------------------------------
# Basketball — Pace
# ---------------------------------------------------------------------------


class TestComputeBasketballPace:
    def test_typical_nba_game(self) -> None:
        """100 possessions in 240 minutes → 48 * 100 / 240 = 20."""
        result = compute_basketball_pace(possessions=100, minutes=240)
        assert abs(result - 20.0) < 1e-6

    def test_zero_minutes_returns_zero(self) -> None:
        assert compute_basketball_pace(possessions=50, minutes=0) == 0.0

    def test_high_pace_team(self) -> None:
        """120 possessions in 240 minutes → 24."""
        result = compute_basketball_pace(possessions=120, minutes=240)
        assert abs(result - 24.0) < 1e-6


# ---------------------------------------------------------------------------
# Basketball — estimate possessions
# ---------------------------------------------------------------------------


class TestEstimateBasketballPossessions:
    def test_dean_oliver_formula(self) -> None:
        """FGA=80, FTA=20, ORB=10, TOV=15 → 80 - 10 + 15 + 0.44*20 = 93.8."""
        result = estimate_basketball_possessions(fga=80, fta=20, orb=10, tov=15)
        assert abs(result - 93.8) < 1e-6

    def test_zero_inputs(self) -> None:
        assert estimate_basketball_possessions(fga=0, fta=0, orb=0, tov=0) == 0.0

    def test_no_offensive_boards(self) -> None:
        """ORB=0: Poss = FGA + TOV + 0.44*FTA."""
        result = estimate_basketball_possessions(fga=70, fta=10, orb=0, tov=12)
        expected = 70 + 12 + 0.44 * 10
        assert abs(result - expected) < 1e-6


# ---------------------------------------------------------------------------
# Basketball — ORtg / DRtg
# ---------------------------------------------------------------------------


class TestComputeBasketballOrtg:
    def test_typical(self) -> None:
        """110 pts on 100 possessions → 110."""
        assert abs(compute_basketball_ortg(pts=110, possessions=100) - 110.0) < 1e-6

    def test_zero_possessions_returns_zero(self) -> None:
        assert compute_basketball_ortg(pts=100, possessions=0) == 0.0


class TestComputeBasketballDrtg:
    def test_typical(self) -> None:
        """95 pts allowed on 100 possessions → 95."""
        assert (
            abs(compute_basketball_drtg(opp_pts=95, opp_possessions=100) - 95.0) < 1e-6
        )

    def test_zero_possessions_returns_zero(self) -> None:
        assert compute_basketball_drtg(opp_pts=80, opp_possessions=0) == 0.0


# ---------------------------------------------------------------------------
# Hockey — Corsi%
# ---------------------------------------------------------------------------


class TestComputeHockeyCorsi:
    def test_equal_shot_attempts(self) -> None:
        """Equal attempts on both sides → CF% = 0.5."""
        result = compute_hockey_corsi(
            shots_for=10,
            shots_against=10,
            blocks_for=5,
            blocks_against=5,
            missed_for=3,
            missed_against=3,
        )
        assert abs(result - 0.5) < 1e-6

    def test_dominant_team(self) -> None:
        """Team with all attempts → CF% = 1.0."""
        result = compute_hockey_corsi(
            shots_for=20,
            shots_against=0,
            blocks_for=0,
            blocks_against=5,
            missed_for=3,
            missed_against=0,
        )
        # CF = 20 + 5 + 3 = 28; CA = 0 + 0 + 0 = 0; total = 28 → 1.0
        assert abs(result - 1.0) < 1e-6

    def test_zero_attempts_returns_neutral(self) -> None:
        """No attempts at all → returns neutral 0.5."""
        result = compute_hockey_corsi(0, 0, 0, 0, 0, 0)
        assert result == 0.5


# ---------------------------------------------------------------------------
# Baseball — wOBA
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "bb": 0.69,
    "hbp": 0.72,
    "1b": 0.88,
    "2b": 1.247,
    "3b": 1.578,
    "hr": 2.031,
}


class TestComputeBaseballWoba:
    def test_typical_line(self) -> None:
        """Verify numeric result against manual calculation."""
        stats = {
            "ab": 400,
            "bb": 50,
            "sf": 5,
            "hbp": 3,
            "1b": 80,
            "2b": 30,
            "3b": 5,
            "hr": 20,
        }
        result = compute_baseball_woba(weights=DEFAULT_WEIGHTS, stats=stats)
        pa = 400 + 50 + 5 + 3  # 458
        num = 0.69 * 50 + 0.72 * 3 + 0.88 * 80 + 1.247 * 30 + 1.578 * 5 + 2.031 * 20
        expected = num / pa
        assert abs(result - expected) < 1e-6

    def test_empty_stats_returns_zero(self) -> None:
        """All-zero plate appearances → 0."""
        assert compute_baseball_woba(weights=DEFAULT_WEIGHTS, stats={}) == 0.0

    def test_only_home_runs(self) -> None:
        """Single event: 1 HR, 1 AB → 2.031 / 1."""
        stats = {"ab": 1, "hr": 1}
        result = compute_baseball_woba(weights=DEFAULT_WEIGHTS, stats=stats)
        assert abs(result - 2.031) < 1e-6


# ---------------------------------------------------------------------------
# Baseball — FIP
# ---------------------------------------------------------------------------


class TestComputeBaseballFip:
    def test_known_starter_line(self) -> None:
        """6 IP, 1 HR, 2 BB, 0 HBP, 7 K, constant=3.10."""
        result = compute_baseball_fip(hr=1, bb=2, hbp=0, k=7, ip=6.0, fip_constant=3.10)
        expected = (13 * 1 + 3 * (2 + 0) - 2 * 7) / 6.0 + 3.10
        assert abs(result - expected) < 1e-6

    def test_zero_ip_returns_zero(self) -> None:
        assert (
            compute_baseball_fip(hr=0, bb=0, hbp=0, k=0, ip=0, fip_constant=3.10) == 0.0
        )

    def test_dominant_outing(self) -> None:
        """0 HR, 0 BB, 0 HBP, 9 K in 9 IP → (−18)/9 + 3.10 = 1.10."""
        result = compute_baseball_fip(hr=0, bb=0, hbp=0, k=9, ip=9.0, fip_constant=3.10)
        assert abs(result - 1.10) < 1e-6


# ---------------------------------------------------------------------------
# Soccer — PPDA
# ---------------------------------------------------------------------------


class TestComputeSoccerPpda:
    def test_high_pressing(self) -> None:
        """40 passes / 10 actions = 4.0 (intense press)."""
        result = compute_soccer_ppda(opp_passes=40, defensive_actions=10)
        assert abs(result - 4.0) < 1e-6

    def test_no_defensive_actions_returns_zero(self) -> None:
        assert compute_soccer_ppda(opp_passes=50, defensive_actions=0) == 0.0

    def test_low_pressing(self) -> None:
        """100 passes / 5 actions = 20.0 (low press)."""
        result = compute_soccer_ppda(opp_passes=100, defensive_actions=5)
        assert abs(result - 20.0) < 1e-6


# ---------------------------------------------------------------------------
# NFL — EPA aggregate
# ---------------------------------------------------------------------------


class TestComputeNflEpaAggregate:
    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame()
        result = compute_nfl_epa_aggregate(df)
        assert result["epa_offense_mean"] == 0.0
        assert result["success_rate"] == 0.0

    def test_none_returns_empty(self) -> None:
        result = compute_nfl_epa_aggregate(None)
        assert result["epa_offense_mean"] == 0.0

    def test_typical_game(self) -> None:
        """Half positive EPA plays → success_rate = 0.5."""
        df = pd.DataFrame(
            {
                "epa": [1.0, -0.5, 2.0, -1.0],
                "posteam": ["KC", "KC", "KC", "KC"],
                "defteam": ["SF", "SF", "SF", "SF"],
            }
        )
        result = compute_nfl_epa_aggregate(df)
        assert abs(result["epa_offense_mean"] - 0.375) < 1e-6
        assert abs(result["success_rate"] - 0.5) < 1e-6

    def test_missing_epa_column(self) -> None:
        """DataFrame without 'epa' column returns zero metrics."""
        df = pd.DataFrame({"posteam": ["KC"], "defteam": ["SF"]})
        result = compute_nfl_epa_aggregate(df)
        assert result["epa_offense_mean"] == 0.0
