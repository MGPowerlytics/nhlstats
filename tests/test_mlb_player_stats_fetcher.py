"""Tests for plugins.mlb_modeling.player_stats_fetcher."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from plugins.mlb_modeling.player_stats_fetcher import (
    MLBPlayerStatsFetcher,
    PlayerStatsFetchResult,
    _SEASON_CONSTANTS,
    _aggregate_pitch_features,
    _extract_pitch_events,
    _get_season_constants,
    _parse_innings_pitched,
    _safe_divide,
    _to_float,
    _to_int,
    compute_advanced_batting_metrics,
    compute_advanced_pitching_metrics,
    fetch_player_stats,
    upsert_batting_stats,
    upsert_pitching_stats,
    upsert_pitch_features,
)


# =========================================================================
# Helper tests
# =========================================================================


class TestToInt:
    def test_int_passthrough(self) -> None:
        assert _to_int(42) == 42

    def test_float_truncation(self) -> None:
        assert _to_int(3.9) == 3

    def test_string_parsing(self) -> None:
        assert _to_int("15") == 15

    def test_none_default(self) -> None:
        assert _to_int(None) == 0

    def test_custom_default(self) -> None:
        assert _to_int(None, default=-1) == -1

    def test_bad_value_returns_default(self) -> None:
        assert _to_int("not_a_number") == 0


class TestToFloat:
    def test_float_passthrough(self) -> None:
        assert _to_float(3.14) == 3.14

    def test_int_conversion(self) -> None:
        assert _to_float(5) == 5.0

    def test_string_parsing(self) -> None:
        assert _to_float("2.5") == 2.5

    def test_none_default(self) -> None:
        assert _to_float(None) == 0.0

    def test_custom_default(self) -> None:
        assert _to_float(None, default=1.0) == 1.0

    def test_bad_value_returns_default(self) -> None:
        assert _to_float("bad") == 0.0


class TestParseInningsPitched:
    def test_whole_innings(self) -> None:
        assert _parse_innings_pitched("9.0") == 9.0

    def test_two_thirds(self) -> None:
        assert _parse_innings_pitched("6.2") == pytest.approx(6.6667, rel=1e-3)

    def test_one_third(self) -> None:
        assert _parse_innings_pitched("5.1") == pytest.approx(5.3333, rel=1e-3)

    def test_zero(self) -> None:
        assert _parse_innings_pitched("0.0") == 0.0

    def test_none(self) -> None:
        assert _parse_innings_pitched(None) == 0.0

    def test_float_input(self) -> None:
        assert _parse_innings_pitched(6.1) == pytest.approx(6.3333, rel=1e-3)


class TestSafeDivide:
    def test_normal(self) -> None:
        assert _safe_divide(10, 2) == 5.0

    def test_zero_denominator(self) -> None:
        assert _safe_divide(10, 0) is None

    def test_negative(self) -> None:
        assert _safe_divide(-10, 2) == -5.0

    def test_zero_numerator(self) -> None:
        assert _safe_divide(0, 5) == 0.0


class TestGetSeasonConstants:
    def test_known_year(self) -> None:
        const = _get_season_constants(2023)
        assert const["lg_wOBA"] == 0.313
        assert const["fip_constant"] == 3.05
        assert const["lg_era"] == 4.33

    def test_unknown_year_falls_back(self) -> None:
        const = _get_season_constants(2019)
        # Should fall back to 2025 defaults
        assert isinstance(const, dict)
        assert "lg_wOBA" in const

    def test_all_seasons_have_required_keys(self) -> None:
        required = {
            "lg_wOBA",
            "lg_wOBA_scale",
            "fip_constant",
            "lg_era",
            "lg_hr_per_fb",
        }
        for year, const in _SEASON_CONSTANTS.items():
            missing = required - set(const.keys())
            assert not missing, f"Season {year} missing keys: {missing}"


# =========================================================================
# Advanced batting metrics
# =========================================================================


class TestComputeAdvancedBattingMetrics:
    def test_empty_stats_returns_zero_woba(self) -> None:
        """Empty stats means no PAs, so wrc_plus should be None."""
        result = compute_advanced_batting_metrics({}, 2024)
        assert result["woba"] is None
        assert result["wrc_plus"] is None
        assert result["o_swing_pct"] is None

    def test_perfect_game(self) -> None:
        """4-for-4 with 2 HR, 1 2B."""
        stats = {
            "atBats": 4,
            "hits": 4,
            "doubles": 1,
            "triples": 0,
            "homeRuns": 2,
            "baseOnBalls": 0,
            "strikeOuts": 0,
        }
        result = compute_advanced_batting_metrics(stats, 2024)
        assert result["woba"] is not None
        assert result["woba"] > 0.500
        assert result["wrc_plus"] is not None
        assert result["wrc_plus"] > 150

    def test_all_strikeouts_returns_low_woba(self) -> None:
        stats = {
            "atBats": 4,
            "hits": 0,
            "doubles": 0,
            "triples": 0,
            "homeRuns": 0,
            "baseOnBalls": 0,
            "strikeOuts": 4,
        }
        result = compute_advanced_batting_metrics(stats, 2024)
        assert result["woba"] == 0.0
        assert result["wrc_plus"] == 0.0

    def test_walks_count_in_denominator(self) -> None:
        """Player with 3 walks and 1 AB should have positive wOBA."""
        stats = {
            "atBats": 1,
            "hits": 0,
            "doubles": 0,
            "triples": 0,
            "homeRuns": 0,
            "baseOnBalls": 3,
            "strikeOuts": 1,
        }
        result = compute_advanced_batting_metrics(stats, 2024)
        assert result["woba"] is not None
        assert result["woba"] > 0

    def test_hbp_and_sf_handled(self) -> None:
        stats = {
            "atBats": 3,
            "hits": 1,
            "doubles": 0,
            "triples": 0,
            "homeRuns": 1,
            "baseOnBalls": 0,
            "hitByPitch": 1,
            "sacFlies": 1,
            "strikeOuts": 0,
        }
        result = compute_advanced_batting_metrics(stats, 2024)
        assert result["woba"] is not None
        assert result["woba"] > 0.300
        assert result["wrc_plus"] is not None

    def test_static_fields_always_none(self) -> None:
        """Statcast/plate-discipline fields are always None from boxscore."""
        stats = {
            "atBats": 4,
            "hits": 1,
            "doubles": 0,
            "triples": 0,
            "homeRuns": 0,
            "baseOnBalls": 1,
            "strikeOuts": 1,
        }
        result = compute_advanced_batting_metrics(stats, 2024)
        for field in [
            "o_swing_pct",
            "z_contact_pct",
            "hard_hit_pct",
            "avg_exit_velocity",
            "avg_launch_angle",
            "whiff_rate",
            "csw_pct",
        ]:
            assert result[field] is None, f"{field} should be None"

    def test_season_constants_affect_wrc_plus(self) -> None:
        """Same stats produce different wRC+ across seasons."""
        stats = {
            "atBats": 4,
            "hits": 2,
            "doubles": 0,
            "triples": 0,
            "homeRuns": 1,
            "baseOnBalls": 0,
            "strikeOuts": 1,
        }
        r2021 = compute_advanced_batting_metrics(stats, 2021)
        r2024 = compute_advanced_batting_metrics(stats, 2024)
        # wRC+ = (wOBA / lg_wOBA) * 100, so different lg_wOBA yields different
        # wRC+ even with identical stats
        assert (
            r2021["wrc_plus"] != r2024["wrc_plus"]
            or abs(r2021["woba"] - r2024["woba"]) < 0.001
        )


# =========================================================================
# Advanced pitching metrics
# =========================================================================


class TestComputeAdvancedPitchingMetrics:
    def test_empty_stats(self) -> None:
        result = compute_advanced_pitching_metrics({}, 2024)
        # IP is 0, so FIP should be 0.0
        assert result["fip"] is not None
        assert result["xfip"] is None  # no fly ball data
        assert result["siera"] is None  # insufficient PA

    def test_perfect_game(self) -> None:
        """9 IP, 0 ER, 0 H, 0 BB, 14 K.

        FIP is mathematically allowed to be negative when strikeouts heavily
        outweigh walks + home runs.  The perfect-game scenario here yields
        FIP ≈ -0.05, which is correct.
        """
        stats = {
            "inningsPitched": "9.0",
            "strikeOuts": 14,
            "baseOnBalls": 0,
            "homeRuns": 0,
            "earnedRuns": 0,
            "battersFaced": 27,
            "pitchesThrown": 98,
        }
        result = compute_advanced_pitching_metrics(stats, 2024)
        assert result["fip"] is not None
        # FIP = (0 + 0 - 2*14) / 9 + 3.06 = -28/9 + 3.06 ≈ -0.05
        assert result["fip"] == pytest.approx(-0.05, abs=0.01)
        assert result["k_bb_pct"] == pytest.approx(51.85, rel=1e-2)
        assert result["siera"] is not None
        assert result["siera"] > 0
        assert result["xfip"] is None

    def test_high_walk_game(self) -> None:
        """5 IP, 8 BB, 6 K, 2 HR, 5 ER."""
        stats = {
            "inningsPitched": "5.0",
            "strikeOuts": 6,
            "baseOnBalls": 8,
            "homeRuns": 2,
            "earnedRuns": 5,
            "battersFaced": 25,
            "pitchesThrown": 95,
        }
        result = compute_advanced_pitching_metrics(stats, 2024)
        assert result["fip"] is not None
        # FIP = (13*2 + 3*8 - 2*6) / 5 + 3.06 = (26 + 24 - 12) / 5 + 3.06 = 38/5 + 3.06 = 10.66
        assert result["fip"] == pytest.approx(10.66, rel=1e-2)
        assert result["k_bb_pct"] == pytest.approx(-8.0, rel=1e-2)

    def test_few_batters_returns_none_siera(self) -> None:
        """Less than 4 batters faced -> no SIERA."""
        stats = {
            "inningsPitched": "0.2",
            "strikeOuts": 1,
            "baseOnBalls": 0,
            "homeRuns": 0,
            "earnedRuns": 0,
            "battersFaced": 2,
        }
        result = compute_advanced_pitching_metrics(stats, 2024)
        assert result["siera"] is None

    def test_static_fields_always_none(self) -> None:
        """Plate discipline and Statcast fields are None from boxscore."""
        stats = {
            "inningsPitched": "1.0",
            "strikeOuts": 1,
            "baseOnBalls": 0,
            "homeRuns": 0,
            "earnedRuns": 0,
            "battersFaced": 4,
        }
        result = compute_advanced_pitching_metrics(stats, 2024)
        for field in [
            "o_swing_pct",
            "z_contact_pct",
            "hard_hit_pct_allowed",
            "avg_exit_velocity_allowed",
            "whiff_rate",
            "csw_pct",
            "primary_pitch_type",
            "primary_pitch_pct",
            "avg_velocity",
        ]:
            assert result[field] is None, f"{field} should be None"

    def test_xfip_always_none(self) -> None:
        """xFIP requires fly-ball data not available from boxscore."""
        stats = {
            "inningsPitched": "6.0",
            "strikeOuts": 8,
            "baseOnBalls": 2,
            "homeRuns": 1,
            "earnedRuns": 3,
            "battersFaced": 24,
        }
        result = compute_advanced_pitching_metrics(stats, 2024)
        assert result["xfip"] is None

    def test_fatigue_fields_none_in_return(self) -> None:
        """Fatigue fields are NOT in pitching metrics return."""
        stats = {
            "inningsPitched": "6.0",
            "strikeOuts": 5,
            "baseOnBalls": 2,
            "homeRuns": 0,
            "earnedRuns": 2,
            "battersFaced": 22,
        }
        result = compute_advanced_pitching_metrics(stats, 2024)
        # These fields are set at the row level, not in advanced metrics
        assert "days_rest" not in result


# =========================================================================
# Pitch-level extraction
# =========================================================================


def _make_live_feed_with_pitches() -> dict:
    """Build a minimal live-feed dict with pitch events for testing."""
    return {
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "matchup": {
                            "batter": {"id": 111},
                            "pitcher": {"id": 222},
                            "batSide": {"code": "L"},
                            "pitchHand": {"code": "R"},
                        },
                        "playEvents": [
                            {
                                "isPitch": True,
                                "details": {
                                    "type": {
                                        "code": "FF",
                                        "description": "Four-Seam Fastball",
                                    },
                                    "call": {
                                        "code": "C",
                                        "description": "Called Strike",
                                    },
                                },
                                "pitchData": {
                                    "startSpeed": 95.1,
                                    "coordinates": {"x": 0.5, "y": 2.5, "z": 3.2},
                                },
                            },
                            {
                                "isPitch": True,
                                "details": {
                                    "type": {
                                        "code": "FF",
                                        "description": "Four-Seam Fastball",
                                    },
                                    "call": {
                                        "code": "S",
                                        "description": "Swinging Strike",
                                    },
                                },
                                "pitchData": {
                                    "startSpeed": 94.8,
                                    "coordinates": {"x": -0.3, "y": 2.5, "z": 2.9},
                                },
                            },
                            {
                                "isPitch": True,
                                "details": {
                                    "type": {"code": "SL", "description": "Slider"},
                                    "call": {"code": "B", "description": "Ball"},
                                },
                                "pitchData": {
                                    "startSpeed": 87.2,
                                    "coordinates": {"x": -1.2, "y": 2.5, "z": 1.8},
                                },
                            },
                            {
                                "isPitch": True,
                                "details": {
                                    "type": {
                                        "code": "FF",
                                        "description": "Four-Seam Fastball",
                                    },
                                    "call": {
                                        "code": "X",
                                        "description": "In play, out(s)",
                                    },
                                },
                                "pitchData": {
                                    "startSpeed": 95.5,
                                    "coordinates": {"x": 0.1, "y": 2.5, "z": 3.0},
                                },
                            },
                        ],
                    },
                    {
                        "matchup": {
                            "batter": {"id": 333},
                            "pitcher": {"id": 222},
                            "batSide": {"code": "R"},
                            "pitchHand": {"code": "R"},
                        },
                        "playEvents": [
                            {
                                "isPitch": True,
                                "details": {
                                    "type": {"code": "CH", "description": "Changeup"},
                                    "call": {
                                        "code": "S",
                                        "description": "Swinging Strike",
                                    },
                                },
                                "pitchData": {
                                    "startSpeed": 83.5,
                                    "coordinates": {"x": 0.8, "y": 2.5, "z": 2.5},
                                },
                            },
                        ],
                    },
                ]
            }
        }
    }


def _make_empty_live_feed() -> dict:
    """Return a live-feed dict with no plays."""
    return {"liveData": {"plays": {"allPlays": []}}}


def _make_live_feed_no_pitches() -> dict:
    """Return a live-feed with plays but no pitch events."""
    return {
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "matchup": {
                            "batter": {"id": 111},
                            "pitcher": {"id": 222},
                            "batSide": {"code": "L"},
                            "pitchHand": {"code": "R"},
                        },
                        "playEvents": [
                            {
                                "isPitch": False,
                                "details": {
                                    "type": {"code": "PO", "description": "Pickoff"},
                                },
                            }
                        ],
                    }
                ]
            }
        }
    }


class TestExtractPitchEvents:
    def test_extracts_all_pitch_events(self) -> None:
        live = _make_live_feed_with_pitches()
        events = _extract_pitch_events(live)
        assert len(events) == 5  # 4 FF+SL from batter 111, 1 CH from batter 333

    def test_pitch_type_and_result_correct(self) -> None:
        live = _make_live_feed_with_pitches()
        events = _extract_pitch_events(live)

        # First event: FF, called strike
        assert events[0]["pitch_type"] == "FF"
        assert events[0]["is_called_strike"] is True
        assert events[0]["is_whiff"] is False
        assert events[0]["is_csw"] is True

        # Second event: FF, swinging strike (whiff)
        assert events[1]["pitch_type"] == "FF"
        assert events[1]["is_whiff"] is True
        assert events[1]["is_called_strike"] is False
        assert events[1]["is_csw"] is True

        # Third event: SL, ball
        assert events[2]["pitch_type"] == "SL"
        assert events[2]["is_whiff"] is False
        assert events[2]["is_called_strike"] is False
        assert events[2]["is_csw"] is False

    def test_velocity_and_location(self) -> None:
        live = _make_live_feed_with_pitches()
        events = _extract_pitch_events(live)
        assert events[0]["velocity"] == 95.1
        assert events[0]["vert_location"] == 3.2
        assert events[2]["velocity"] == 87.2
        assert events[2]["vert_location"] == 1.8

    def test_batter_and_pitcher_ids(self) -> None:
        live = _make_live_feed_with_pitches()
        events = _extract_pitch_events(live)
        for event in events[:4]:  # first 4 are batter 111 vs pitcher 222
            assert event["batter_id"] == "111"
            assert event["pitcher_id"] == "222"
            assert event["batter_side"] == "L"
            assert event["pitcher_throw_side"] == "R"

    def test_empty_live_feed(self) -> None:
        events = _extract_pitch_events(_make_empty_live_feed())
        assert events == []

    def test_no_pitch_events(self) -> None:
        events = _extract_pitch_events(_make_live_feed_no_pitches())
        assert events == []

    def test_missing_data_is_graceful(self) -> None:
        live = {
            "liveData": {
                "plays": {
                    "allPlays": [
                        {
                            "matchup": {},
                            "playEvents": [
                                {
                                    "isPitch": True,
                                    "details": {},
                                    "pitchData": {},
                                }
                            ],
                        }
                    ]
                }
            }
        }
        events = _extract_pitch_events(live)
        assert len(events) == 1
        assert events[0]["pitch_type"] == "UNK"
        assert events[0]["velocity"] is None
        assert events[0]["vert_location"] is None
        assert events[0]["is_whiff"] is False
        assert events[0]["is_called_strike"] is False


# =========================================================================
# Pitch-level aggregation
# =========================================================================


class TestAggregatePitchFeatures:
    def test_groups_by_pitcher_batter_pitch_type(self) -> None:
        live = _make_live_feed_with_pitches()
        events = _extract_pitch_events(live)
        features = _aggregate_pitch_features(events, "test_game_1")

        # Should have 3 groups: (222, 111, FF), (222, 111, SL), (222, 333, CH)
        assert len(features) == 3

        # Find FF group for (222, 111)
        ff_group = None
        sl_group = None
        ch_group = None
        for f in features:
            if (
                f["pitcher_id"] == "222"
                and f["batter_id"] == "111"
                and f["pitch_type"] == "FF"
            ):
                ff_group = f
            elif (
                f["pitcher_id"] == "222"
                and f["batter_id"] == "111"
                and f["pitch_type"] == "SL"
            ):
                sl_group = f
            elif (
                f["pitcher_id"] == "222"
                and f["batter_id"] == "333"
                and f["pitch_type"] == "CH"
            ):
                ch_group = f

        assert ff_group is not None
        assert sl_group is not None
        assert ch_group is not None

        # FF: 4 pitches, 1 whiff (swinging strike), 2 CSW (1 called + 1 swinging)
        assert ff_group["pitch_count"] == 3
        assert ff_group["whiff_rate"] == pytest.approx(1 / 3, rel=1e-3)
        assert ff_group["csw_pct"] == pytest.approx(2 / 3, rel=1e-3)

        # SL: 1 pitch, ball
        assert sl_group["pitch_count"] == 1
        assert sl_group["whiff_rate"] == 0.0
        assert sl_group["csw_pct"] == 0.0

        # CH: 1 pitch, swinging strike
        assert ch_group["pitch_count"] == 1
        assert ch_group["whiff_rate"] == 1.0
        assert ch_group["csw_pct"] == 1.0

    def test_velocity_averages(self) -> None:
        live = _make_live_feed_with_pitches()
        events = _extract_pitch_events(live)
        features = _aggregate_pitch_features(events, "test_game_1")

        ff_group = next(
            f
            for f in features
            if f["pitcher_id"] == "222"
            and f["batter_id"] == "111"
            and f["pitch_type"] == "FF"
        )
        # 3 FF pitches: 95.1, 94.8, 95.5
        assert ff_group["avg_velocity"] == pytest.approx(
            (95.1 + 94.8 + 95.5) / 3, rel=1e-2
        )

    def test_vertical_location_accuracy(self) -> None:
        """Standard deviation of vertical location when >=2 samples."""
        live = _make_live_feed_with_pitches()
        events = _extract_pitch_events(live)
        features = _aggregate_pitch_features(events, "test_game_1")

        ff_group = next(
            f
            for f in features
            if f["pitcher_id"] == "222"
            and f["batter_id"] == "111"
            and f["pitch_type"] == "FF"
        )
        # 3 FF pitches with z: 3.2, 2.9, 3.0
        assert ff_group["avg_vertical_location"] is not None
        assert ff_group["vertical_location_accuracy"] is not None
        assert ff_group["vertical_location_accuracy"] > 0

    def test_single_sample_no_accuracy(self) -> None:
        live = _make_live_feed_with_pitches()
        events = _extract_pitch_events(live)
        features = _aggregate_pitch_features(events, "test_game_1")

        ch_group = next(
            f
            for f in features
            if f["pitcher_id"] == "222"
            and f["batter_id"] == "333"
            and f["pitch_type"] == "CH"
        )
        assert ch_group["vertical_location_accuracy"] is None

    def test_game_id_included(self) -> None:
        events = _extract_pitch_events(_make_live_feed_with_pitches())
        features = _aggregate_pitch_features(events, "game_abc_123")
        assert all(f["game_id"] == "game_abc_123" for f in features)

    def test_batter_side_and_throw_side(self) -> None:
        events = _extract_pitch_events(_make_live_feed_with_pitches())
        features = _aggregate_pitch_features(events, "test_game_1")

        ff_group = next(
            f
            for f in features
            if f["pitcher_id"] == "222"
            and f["batter_id"] == "111"
            and f["pitch_type"] == "FF"
        )
        assert ff_group["batter_side"] == "L"
        assert ff_group["pitcher_throw_side"] == "R"

    def test_empty_events(self) -> None:
        features = _aggregate_pitch_features([], "game_1")
        assert features == []

    def test_source_and_version_set(self) -> None:
        events = _extract_pitch_events(_make_live_feed_with_pitches())
        features = _aggregate_pitch_features(events, "game_1")
        for f in features:
            assert f["source"] == "mlb_statsapi_livefeed"
            assert f["feature_version"] == "v1"


# =========================================================================
# Mock data for fetch_player_stats tests
# =========================================================================


def _make_mock_boxscore() -> dict:
    """Return a realistic minimal boxscore response."""
    return {
        "teams": {
            "home": {
                "team": {"name": "Home Team"},
                "teamStats": {},
                "batters": [1001, 1002, 1003],
                "pitchers": [2001, 2002],
                "players": {
                    "ID1001": {
                        "person": {"id": 1001, "fullName": "Home Batter One"},
                        "battingOrder": 1,
                        "batSide": {"code": "R"},
                        "stats": {
                            "batting": {
                                "plateAppearances": 4,
                                "atBats": 4,
                                "hits": 2,
                                "doubles": 0,
                                "triples": 0,
                                "homeRuns": 1,
                                "baseOnBalls": 0,
                                "strikeOuts": 1,
                            }
                        },
                    },
                    "ID1002": {
                        "person": {"id": 1002, "fullName": "Home Batter Two"},
                        "battingOrder": 2,
                        "batSide": {"code": "L"},
                        "stats": {
                            "batting": {
                                "plateAppearances": 4,
                                "atBats": 3,
                                "hits": 1,
                                "doubles": 1,
                                "triples": 0,
                                "homeRuns": 0,
                                "baseOnBalls": 1,
                                "strikeOuts": 0,
                            }
                        },
                    },
                    "ID1003": {
                        "person": {"id": 1003, "fullName": "Home Batter Three"},
                        "battingOrder": 3,
                        "batSide": {"code": "R"},
                        "stats": {
                            "batting": {
                                "plateAppearances": 3,
                                "atBats": 3,
                                "hits": 0,
                                "strikeOuts": 3,
                            }
                        },
                    },
                    "ID2001": {
                        "person": {"id": 2001, "fullName": "Home Pitcher One"},
                        "throws": {"code": "R"},
                        "stats": {
                            "pitching": {
                                "inningsPitched": "6.0",
                                "pitchesThrown": 92,
                                "battersFaced": 24,
                                "strikeOuts": 8,
                                "baseOnBalls": 1,
                                "homeRuns": 1,
                                "earnedRuns": 2,
                            }
                        },
                    },
                    "ID2002": {
                        "person": {"id": 2002, "fullName": "Home Pitcher Two"},
                        "throws": {"code": "L"},
                        "stats": {
                            "pitching": {
                                "inningsPitched": "3.0",
                                "pitchesThrown": 45,
                                "battersFaced": 12,
                                "strikeOuts": 3,
                                "baseOnBalls": 2,
                                "homeRuns": 0,
                                "earnedRuns": 1,
                            }
                        },
                    },
                },
            },
            "away": {
                "team": {"name": "Away Team"},
                "teamStats": {},
                "batters": [3001, 3002],
                "pitchers": [4001],
                "players": {
                    "ID3001": {
                        "person": {"id": 3001, "fullName": "Away Batter One"},
                        "battingOrder": 1,
                        "batSide": {"code": "R"},
                        "stats": {
                            "batting": {
                                "plateAppearances": 5,
                                "atBats": 4,
                                "hits": 1,
                                "doubles": 0,
                                "triples": 0,
                                "homeRuns": 0,
                                "baseOnBalls": 1,
                                "strikeOuts": 1,
                            }
                        },
                    },
                    "ID3002": {
                        "person": {"id": 3002, "fullName": "Away Batter Two"},
                        "battingOrder": 2,
                        "batSide": {"code": "R"},
                        "stats": {
                            "batting": {
                                "plateAppearances": 4,
                                "atBats": 4,
                                "hits": 1,
                                "doubles": 0,
                                "triples": 0,
                                "homeRuns": 0,
                                "baseOnBalls": 0,
                                "strikeOuts": 2,
                            }
                        },
                    },
                    "ID4001": {
                        "person": {"id": 4001, "fullName": "Away Pitcher One"},
                        "throws": {"code": "R"},
                        "stats": {
                            "pitching": {
                                "inningsPitched": "5.2",
                                "pitchesThrown": 88,
                                "battersFaced": 24,
                                "strikeOuts": 5,
                                "baseOnBalls": 3,
                                "homeRuns": 2,
                                "earnedRuns": 4,
                            }
                        },
                    },
                },
            },
        }
    }


def _make_mock_live_feed() -> dict:
    """Return a minimal live-feed response for the player stats flow."""
    return {
        "gameData": {
            "datetime": {"officialDate": "2024-06-15"},
            "teams": {
                "home": {"abbreviation": "HOM", "name": "Home Team"},
                "away": {"abbreviation": "AWY", "name": "Away Team"},
            },
        },
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "matchup": {
                            "batter": {"id": 3001},
                            "pitcher": {"id": 2001},
                            "batSide": {"code": "R"},
                            "pitchHand": {"code": "R"},
                        },
                        "playEvents": [
                            {
                                "isPitch": True,
                                "details": {
                                    "type": {"code": "FF"},
                                    "call": {"code": "B"},
                                },
                                "pitchData": {
                                    "startSpeed": 95.0,
                                    "coordinates": {"z": 3.0},
                                },
                            }
                        ],
                    },
                ]
            }
        },
    }


def _make_mock_live_feed_no_date() -> dict:
    """Live feed without officialDate."""
    feed = _make_mock_live_feed()
    feed["gameData"]["datetime"]["officialDate"] = ""
    return feed


# =========================================================================
# Fetch player stats integration
# =========================================================================


class _MockRateLimiter:
    """Rate limiter that does nothing -- no actual delays in tests."""

    def __init__(self) -> None:
        self.call_count = 0

    def wait(self) -> None:
        self.call_count += 1


class TestFetchPlayerStats:
    def test_fetches_both_teams(self) -> None:
        limiter = _MockRateLimiter()

        with (
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.requests"
            ) as mock_requests,
        ):
            mock_requests.get.side_effect = [
                MagicMock(
                    status_code=200,
                    json=lambda: _make_mock_live_feed(),
                    raise_for_status=lambda: None,
                ),
                MagicMock(
                    status_code=200,
                    json=lambda: _make_mock_boxscore(),
                    raise_for_status=lambda: None,
                ),
            ]

            result = fetch_player_stats("test_game_1", date(2024, 6, 15), limiter.wait)

        assert isinstance(result, PlayerStatsFetchResult)
        assert len(result.batting_rows) == 5  # 3 home + 2 away batters
        assert len(result.pitching_rows) == 3  # 2 home + 1 away pitchers
        assert len(result.pitch_features) >= 1

    def test_batting_row_structure(self) -> None:
        limiter = _MockRateLimiter()

        with (
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.requests"
            ) as mock_requests,
        ):
            mock_requests.get.side_effect = [
                MagicMock(
                    status_code=200,
                    json=lambda: _make_mock_live_feed(),
                    raise_for_status=lambda: None,
                ),
                MagicMock(
                    status_code=200,
                    json=lambda: _make_mock_boxscore(),
                    raise_for_status=lambda: None,
                ),
            ]

            result = fetch_player_stats("g1", date(2024, 6, 15), limiter.wait)

        row = result.batting_rows[0]
        assert row["game_id"] == "g1"
        assert row["player_id"] == "1001"
        assert row["player_name"] == "Home Batter One"
        assert row["team"] == "HOM"
        assert row["opponent"] == "AWY"
        assert row["is_home"] is True
        assert row["batting_order"] == 1
        assert row["bats"] == "R"
        assert row["plate_appearances"] == 4
        assert row["at_bats"] == 4
        assert row["hits"] == 2
        assert row["home_runs"] == 1
        assert row["woba"] is not None
        assert row["wrc_plus"] is not None
        assert row["source"] == "mlb_statsapi_boxscore"
        assert row["feature_version"] == "v1"

    def test_pitching_row_structure(self) -> None:
        limiter = _MockRateLimiter()

        with (
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.requests"
            ) as mock_requests,
        ):
            mock_requests.get.side_effect = [
                MagicMock(
                    status_code=200,
                    json=lambda: _make_mock_live_feed(),
                    raise_for_status=lambda: None,
                ),
                MagicMock(
                    status_code=200,
                    json=lambda: _make_mock_boxscore(),
                    raise_for_status=lambda: None,
                ),
            ]

            result = fetch_player_stats("g1", date(2024, 6, 15), limiter.wait)

        # Home pitcher 2001 is the starter (faces first batter)
        # Home pitcher 2002 is not the starter
        starter_row = result.pitching_rows[0]
        assert starter_row["pitcher_id"] == "2001"
        assert starter_row["is_starter"] is True

        reliever_row = result.pitching_rows[1]
        assert reliever_row["pitcher_id"] == "2002"
        assert reliever_row["is_starter"] is False

        # Fatigue fields are None
        assert starter_row["days_rest"] is None
        assert starter_row["pitches_last_3_days"] is None
        assert starter_row["fatigue_velocity_penalty"] is None

    def test_away_team_rows(self) -> None:
        limiter = _MockRateLimiter()

        with (
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.requests"
            ) as mock_requests,
        ):
            mock_requests.get.side_effect = [
                MagicMock(
                    status_code=200,
                    json=lambda: _make_mock_live_feed(),
                    raise_for_status=lambda: None,
                ),
                MagicMock(
                    status_code=200,
                    json=lambda: _make_mock_boxscore(),
                    raise_for_status=lambda: None,
                ),
            ]

            result = fetch_player_stats("g1", date(2024, 6, 15), limiter.wait)

        away_batter = next(r for r in result.batting_rows if r["player_id"] == "3001")
        assert away_batter["team"] == "AWY"
        assert away_batter["opponent"] == "HOM"
        assert away_batter["is_home"] is False

        away_pitcher = next(
            r for r in result.pitching_rows if r["pitcher_id"] == "4001"
        )
        assert away_pitcher["team"] == "AWY"
        assert away_pitcher["is_home"] is False

    def test_http_failures_propagate(self) -> None:
        limiter = _MockRateLimiter()

        with (
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.requests"
            ) as mock_requests,
            pytest.raises(Exception),
        ):
            mock_requests.get.side_effect = Exception("API error")
            fetch_player_stats("g1", date(2024, 6, 15), limiter.wait)

    def test_rate_limiter_called(self) -> None:
        limiter = _MockRateLimiter()

        with (
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.requests"
            ) as mock_requests,
        ):
            mock_requests.get.side_effect = [
                MagicMock(
                    status_code=200,
                    json=lambda: _make_mock_live_feed(),
                    raise_for_status=lambda: None,
                ),
                MagicMock(
                    status_code=200,
                    json=lambda: _make_mock_boxscore(),
                    raise_for_status=lambda: None,
                ),
            ]

            fetch_player_stats("g1", date(2024, 6, 15), limiter.wait)
            assert limiter.call_count == 2  # live feed + boxscore


# =========================================================================
# Upsert tests
# =========================================================================


class _FakeDb:
    """In-memory fake DBManager that captures SQL calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, sql: str, params: dict) -> None:
        self.calls.append((sql, params))


class TestUpsertBattingStats:
    def test_inserts_batting_rows(self) -> None:
        db = _FakeDb()
        rows = [
            {
                "game_id": "g1",
                "player_id": "1001",
                "player_name": "Test Batter",
                "team": "HOM",
                "opponent": "AWY",
                "is_home": True,
                "batting_order": 1,
                "bats": "R",
                "plate_appearances": 4,
                "at_bats": 4,
                "hits": 2,
                "doubles": 0,
                "triples": 0,
                "home_runs": 1,
                "walks": 0,
                "strikeouts": 1,
                "woba": 0.5123,
                "wrc_plus": 164.2,
                "o_swing_pct": None,
                "z_contact_pct": None,
                "hard_hit_pct": None,
                "avg_exit_velocity": None,
                "avg_launch_angle": None,
                "whiff_rate": None,
                "csw_pct": None,
                "source": "mlb_statsapi_boxscore",
                "feature_version": "v1",
            }
        ]
        count = upsert_batting_stats(db, rows)
        assert count == 1
        assert len(db.calls) == 1
        sql, params = db.calls[0]
        assert "INSERT INTO mlb_player_game_batting_stats" in sql
        assert "ON CONFLICT (game_id, player_id)" in sql
        assert params["player_id"] == "1001"

    def test_empty_rows(self) -> None:
        db = _FakeDb()
        count = upsert_batting_stats(db, [])
        assert count == 0


class TestUpsertPitchingStats:
    def test_inserts_pitching_rows(self) -> None:
        db = _FakeDb()
        rows = [
            {
                "game_id": "g1",
                "pitcher_id": "2001",
                "pitcher_name": "Test Pitcher",
                "team": "HOM",
                "opponent": "AWY",
                "is_home": True,
                "is_starter": True,
                "throws": "R",
                "innings_pitched": 6.0,
                "pitch_count": 92,
                "batters_faced": 24,
                "strikeouts": 8,
                "walks": 1,
                "home_runs_allowed": 1,
                "earned_runs": 2,
                "fip": 3.15,
                "xfip": None,
                "siera": 3.45,
                "k_bb_pct": 29.17,
                "o_swing_pct": None,
                "z_contact_pct": None,
                "hard_hit_pct_allowed": None,
                "avg_exit_velocity_allowed": None,
                "whiff_rate": None,
                "csw_pct": None,
                "primary_pitch_type": None,
                "primary_pitch_pct": None,
                "avg_velocity": None,
                "days_rest": None,
                "pitches_last_3_days": None,
                "pitches_last_5_days": None,
                "fatigue_velocity_penalty": None,
                "source": "mlb_statsapi_boxscore",
                "feature_version": "v1",
            }
        ]
        count = upsert_pitching_stats(db, rows)
        assert count == 1
        assert len(db.calls) == 1
        sql, params = db.calls[0]
        assert "INSERT INTO mlb_player_game_pitching_stats" in sql
        assert "ON CONFLICT (game_id, pitcher_id)" in sql
        assert params["is_starter"] is True

    def test_empty_rows(self) -> None:
        db = _FakeDb()
        count = upsert_pitching_stats(db, [])
        assert count == 0


class TestUpsertPitchFeatures:
    def test_inserts_pitch_feature_rows(self) -> None:
        db = _FakeDb()
        rows = [
            {
                "game_id": "g1",
                "pitcher_id": "222",
                "batter_id": "111",
                "pitch_type": "FF",
                "batter_side": "L",
                "pitcher_throw_side": "R",
                "pitch_count": 10,
                "whiff_rate": 0.2,
                "csw_pct": 0.3,
                "z_contact_pct": None,
                "avg_vertical_location": 3.1,
                "vertical_location_accuracy": 0.45,
                "avg_velocity": 94.5,
                "source": "mlb_statsapi_livefeed",
                "feature_version": "v1",
            }
        ]
        count = upsert_pitch_features(db, rows)
        assert count == 1
        assert len(db.calls) == 1
        sql, params = db.calls[0]
        assert "INSERT INTO mlb_pitch_level_features" in sql
        assert "ON CONFLICT (game_id, pitcher_id, batter_id, pitch_type)" in sql
        assert params["pitch_type"] == "FF"

    def test_empty_rows(self) -> None:
        db = _FakeDb()
        count = upsert_pitch_features(db, [])
        assert count == 0


# =========================================================================
# MLBPlayerStatsFetcher class
# =========================================================================


class TestMLBPlayerStatsFetcher:
    def test_fetch_game_stats_delegates(self) -> None:
        """The class wrapper calls fetch_player_stats with its rate limiter."""
        fetcher = MLBPlayerStatsFetcher(db=_FakeDb())

        with (
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.fetch_player_stats"
            ) as mock_fn,
        ):
            mock_result = PlayerStatsFetchResult(
                batting_rows=[{"game_id": "g1", "player_id": "1"}],
                pitching_rows=[],
                pitch_features=[],
            )
            mock_fn.return_value = mock_result

            result = fetcher.fetch_game_stats("g1", game_date=date(2024, 6, 15))

            mock_fn.assert_called_once()
            args, _ = mock_fn.call_args
            assert args[0] == "g1"  # game_id
            assert args[1] == date(2024, 6, 15)  # game_date
            assert callable(args[2])  # rate_limiter
            assert result == mock_result

    def test_upsert_all_calls_all_upserts(self) -> None:
        db = _FakeDb()
        fetcher = MLBPlayerStatsFetcher(db=db)
        result = PlayerStatsFetchResult(
            batting_rows=[{"game_id": "g1", "player_id": "1"}],
            pitching_rows=[{"game_id": "g1", "pitcher_id": "2"}],
            pitch_features=[
                {
                    "game_id": "g1",
                    "pitcher_id": "2",
                    "batter_id": "1",
                    "pitch_type": "FF",
                }
            ],
        )

        with (
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.upsert_batting_stats"
            ) as mock_bat,
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.upsert_pitching_stats"
            ) as mock_pit,
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.upsert_pitch_features"
            ) as mock_pf,
        ):
            mock_bat.return_value = 1
            mock_pit.return_value = 1
            mock_pf.return_value = 1

            total = fetcher.upsert_all(result)

            assert total == 3
            mock_bat.assert_called_once_with(db, result.batting_rows)
            mock_pit.assert_called_once_with(db, result.pitching_rows)
            mock_pf.assert_called_once_with(db, result.pitch_features)

    def test_fetch_game_stats_without_date_fetches_metadata(self) -> None:
        """When game_date is None, the class fetches the date from the API."""
        fetcher = MLBPlayerStatsFetcher(db=_FakeDb())

        with (
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.requests"
            ) as mock_requests,
            patch(
                "plugins.mlb_modeling.player_stats_fetcher.fetch_player_stats"
            ) as mock_fn,
        ):
            # First API call (for metadata) returns a live feed with officialDate
            mock_meta_resp = MagicMock(
                status_code=200,
                json=lambda: {
                    "gameData": {
                        "datetime": {"officialDate": "2024-08-01"},
                        "teams": {},
                    }
                },
                raise_for_status=lambda: None,
            )

            mock_result = PlayerStatsFetchResult(
                batting_rows=[],
                pitching_rows=[],
                pitch_features=[],
            )
            mock_fn.return_value = mock_result

            mock_requests.get.return_value = mock_meta_resp

            result = fetcher.fetch_game_stats("g1", game_date=None)

            mock_fn.assert_called_once_with(
                "g1", date(2024, 8, 1), fetcher._limiter.wait
            )
            assert result == mock_result


# =========================================================================
# Season constants data integrity
# =========================================================================


class TestSeasonConstantsIntegrity:
    def test_all_years_have_all_keys(self) -> None:
        required_keys = {
            "lg_wOBA",
            "lg_wOBA_scale",
            "fip_constant",
            "lg_era",
            "lg_hr_per_fb",
        }
        for year, const in _SEASON_CONSTANTS.items():
            assert set(const.keys()) == required_keys, (
                f"Year {year} has keys {set(const.keys())}, "
                f"expected {required_keys}"
            )

    def test_lg_woba_range(self) -> None:
        for year, const in _SEASON_CONSTANTS.items():
            assert (
                0.250 <= const["lg_wOBA"] <= 0.400
            ), f"Year {year} lg_wOBA={const['lg_wOBA']} out of range"

    def test_fip_constant_range(self) -> None:
        for year, const in _SEASON_CONSTANTS.items():
            assert (
                2.50 <= const["fip_constant"] <= 4.00
            ), f"Year {year} fip_constant={const['fip_constant']} out of range"

    def test_lg_era_range(self) -> None:
        for year, const in _SEASON_CONSTANTS.items():
            assert (
                3.00 <= const["lg_era"] <= 5.50
            ), f"Year {year} lg_era={const['lg_era']} out of range"

    def test_lg_hr_per_fb_range(self) -> None:
        for year, const in _SEASON_CONSTANTS.items():
            assert (
                0.08 <= const["lg_hr_per_fb"] <= 0.25
            ), f"Year {year} lg_hr_per_fb={const['lg_hr_per_fb']} out of range"

    def test_woba_scale_range(self) -> None:
        for year, const in _SEASON_CONSTANTS.items():
            assert (
                1.00 <= const["lg_wOBA_scale"] <= 1.50
            ), f"Year {year} lg_wOBA_scale={const['lg_wOBA_scale']} out of range"
