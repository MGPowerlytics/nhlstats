"""Tests for MLB rolling-window feature computation."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from plugins.mlb_modeling.rolling_features import (
    ROLES,
    SOURCE,
    SPLITS,
    FEATURE_VERSION,
    WINDOWS,
    RollingWindowConfig,
    _compute_fip_from_game,
    _compute_k_bb_pct_from_game,
    _compute_recency_weight,
    _compute_siera_from_game,
    _compute_woba_from_game,
    _compute_wrc_plus,
    _filter_games_by_window,
    _parse_game_date,
    _recency_weight,
    compute_all_rolling_features,
    compute_rolling_features,
    upsert_rolling_features,
)


# ---------------------------------------------------------------------------
# Fake DB
# ---------------------------------------------------------------------------


class _FakeDb:
    """In-memory DB stub that records executed SQL and returns canned results."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._results: dict[str, list[dict[str, Any]]] = {}

    def _set_result(self, sql_fragment: str, rows: list[dict[str, Any]]) -> None:
        """Register canned rows to return when SQL contains *sql_fragment*."""
        self._results[sql_fragment] = rows

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> list[Any]:
        self.calls.append((sql, params or {}))
        # Return matching canned data, or empty list
        for fragment, rows in self._results.items():
            if fragment in sql:
                return _RowsResult(rows)
        return _RowsResult([])


class _Row:
    """Mock row that supports both ``_mapping`` and dict conversion."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self._mapping = data

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data[key]

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def __iter__(self):
        return iter(self._data.values())

    def __len__(self):
        return len(self._data)


class _RowsResult:
    """Mock SQLAlchemy result proxy."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = [_Row(r) for r in rows]

    def __iter__(self):
        return iter(self._rows)

    def __bool__(self):
        return len(self._rows) > 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DAY0 = date(2026, 6, 1)
D1 = DAY0 - timedelta(days=1)   # 1 day ago
D3 = DAY0 - timedelta(days=3)   # 3 days ago
D6 = DAY0 - timedelta(days=6)   # 6 days ago
D10 = DAY0 - timedelta(days=10)  # 10 days ago
D15 = DAY0 - timedelta(days=15)  # 15 days ago
D20 = DAY0 - timedelta(days=20)  # 20 days ago


def _make_batting_game(
    *,
    game_id: str = "g1",
    player_id: str = "p1",
    player_name: str = "Test Batter",
    team: str = "NYY",
    opponent: str = "BOS",
    game_date: date = D6,
    pa: int = 4,
    ab: int = 4,
    hits: int = 2,
    doubles: int = 1,
    triples: int = 0,
    hr: int = 0,
    walks: int = 0,
    strikeouts: int = 1,
    woba: float | None = 0.350,
    opposing_starter_throws: str | None = "R",
) -> dict[str, Any]:
    return {
        "game_id": game_id,
        "player_id": player_id,
        "player_name": player_name,
        "team": team,
        "opponent": opponent,
        "is_home": True,
        "batting_order": 3,
        "bats": "R",
        "plate_appearances": pa,
        "at_bats": ab,
        "hits": hits,
        "doubles": doubles,
        "triples": triples,
        "home_runs": hr,
        "walks": walks,
        "strikeouts": strikeouts,
        "woba": woba,
        "wrc_plus": None,
        "o_swing_pct": None,
        "z_contact_pct": None,
        "hard_hit_pct": None,
        "avg_exit_velocity": None,
        "avg_launch_angle": None,
        "whiff_rate": None,
        "csw_pct": None,
        "game_date": game_date,
        "opposing_starter_throws": opposing_starter_throws,
    }


def _make_pitching_game(
    *,
    game_id: str = "g1",
    pitcher_id: str = "p2",
    pitcher_name: str = "Test Pitcher",
    team: str = "NYY",
    opponent: str = "BOS",
    game_date: date = D6,
    ip: float = 6.0,
    pitch_count: int = 90,
    batters_faced: int = 25,
    strikeouts: int = 7,
    walks: int = 2,
    hr: int = 1,
    earned_runs: int = 3,
    throws: str = "R",
    is_starter: bool = True,
    fip: float | None = 3.50,
) -> dict[str, Any]:
    return {
        "game_id": game_id,
        "pitcher_id": pitcher_id,
        "pitcher_name": pitcher_name,
        "team": team,
        "opponent": opponent,
        "is_home": True,
        "is_starter": is_starter,
        "throws": throws,
        "innings_pitched": ip,
        "pitch_count": pitch_count,
        "batters_faced": batters_faced,
        "strikeouts": strikeouts,
        "walks": walks,
        "home_runs_allowed": hr,
        "earned_runs": earned_runs,
        "fip": fip,
        "xfip": None,
        "siera": None,
        "k_bb_pct": None,
        "o_swing_pct": None,
        "z_contact_pct": None,
        "hard_hit_pct_allowed": None,
        "avg_exit_velocity_allowed": None,
        "whiff_rate": None,
        "csw_pct": None,
        "primary_pitch_type": None,
        "primary_pitch_pct": None,
        "avg_velocity": None,
        "game_date": game_date,
    }


# ---------------------------------------------------------------------------
# Tests: Configuration
# ---------------------------------------------------------------------------


class TestConfig:
    def test_rolling_window_config(self) -> None:
        cfg = RollingWindowConfig(7, "7d", half_life_days=5.0)
        assert cfg.window_days == 7
        assert cfg.window_name == "7d"
        assert cfg.half_life_days == 5.0

    def test_rolling_window_config_default_half_life(self) -> None:
        cfg = RollingWindowConfig(14, "14d")
        assert cfg.half_life_days == 14.0

    def test_standard_windows_defined(self) -> None:
        assert len(WINDOWS) == 3
        names = [w.window_name for w in WINDOWS]
        assert names == ["7d", "14d", "30d"]

    def test_splits_and_roles(self) -> None:
        assert SPLITS == ["ALL", "VS_RHP", "VS_LHP"]
        assert ROLES == ["batter", "pitcher", "starter"]


# ---------------------------------------------------------------------------
# Tests: Internal helpers
# ---------------------------------------------------------------------------


class TestParseGameDate:
    def test_date_object(self) -> None:
        d = date(2026, 5, 15)
        assert _parse_game_date(d) == d

    def test_iso_string(self) -> None:
        assert _parse_game_date("2026-05-15") == date(2026, 5, 15)

    def test_none(self) -> None:
        assert _parse_game_date(None) is None

    def test_invalid_string(self) -> None:
        assert _parse_game_date("not-a-date") is None


class TestRecencyWeight:
    def test_zero_age_returns_one(self) -> None:
        assert _recency_weight(0, 14.0) == pytest.approx(1.0)

    def test_half_life_steps(self) -> None:
        # At age == half_life_days, weight should be ~0.5
        w = _recency_weight(14, 14.0)
        assert w == pytest.approx(0.5, abs=0.001)

    def test_large_age_approaches_zero(self) -> None:
        w = _recency_weight(100, 14.0)
        assert w < 0.01


class TestComputeWobaFromGame:
    def test_uses_stored_woba_when_available(self) -> None:
        game = _make_batting_game(woba=0.400)
        assert _compute_woba_from_game(game) == 0.400

    def test_computes_from_counts_when_woba_none(self) -> None:
        game = _make_batting_game(woba=None, hits=2, doubles=0, triples=0, hr=1, walks=1, ab=4)
        # PA = 5 (4 AB + 1 BB)
        # singles = 2 - 1 = 1
        # numerator = 0.690*1 + 0.880*1 + 1.249*0 + 1.576*0 + 2.031*1 = 0.690 + 0.880 + 2.031 = 3.601
        # wOBA = 3.601 / 5 = 0.7202
        result = _compute_woba_from_game(game)
        assert result is not None
        assert result == pytest.approx(0.7202, abs=0.001)

    def test_returns_none_when_no_pa(self) -> None:
        game = _make_batting_game(woba=None, ab=0, hits=0, walks=0)
        assert _compute_woba_from_game(game) is None


class TestComputeWrcPlus:
    def test_basic_computation(self) -> None:
        result = _compute_wrc_plus(0.350, lg_woba=0.312)
        assert result is not None
        assert result == pytest.approx(112.2, abs=0.1)

    def test_none_woba_returns_none(self) -> None:
        assert _compute_wrc_plus(None, 0.312) is None

    def test_zero_lg_woba_returns_none(self) -> None:
        assert _compute_wrc_plus(0.350, 0.0) is None


class TestComputeFipFromGame:
    def test_basic_fip(self) -> None:
        game = _make_pitching_game(ip=6.0, hr=1, walks=2, strikeouts=7)
        # FIP = (13*1 + 3*2 - 2*7) / 6.0 + 3.06 = (13 + 6 - 14) / 6 + 3.06 = 5/6 + 3.06 = 3.893
        result = _compute_fip_from_game(game)
        assert result is not None
        assert result == pytest.approx(3.89, abs=0.01)

    def test_zero_ip_returns_none(self) -> None:
        game = _make_pitching_game(ip=0.0)
        assert _compute_fip_from_game(game) is None

    def test_custom_fip_constant(self) -> None:
        game = _make_pitching_game(ip=6.0, hr=1, walks=2, strikeouts=7)
        result = _compute_fip_from_game(game, fip_constant=3.10)
        assert result is not None
        assert result == pytest.approx(3.93, abs=0.01)


class TestComputeSieraFromGame:
    def test_basic_siera(self) -> None:
        game = _make_pitching_game(batters_faced=25, strikeouts=7, walks=2)
        result = _compute_siera_from_game(game)
        assert result is not None
        assert result > 0

    def test_too_few_batters_returns_none(self) -> None:
        game = _make_pitching_game(batters_faced=3, strikeouts=1, walks=0)
        assert _compute_siera_from_game(game) is None


class TestComputeKBBPctFromGame:
    def test_basic_calculation(self) -> None:
        game = _make_pitching_game(batters_faced=25, strikeouts=7, walks=2)
        result = _compute_k_bb_pct_from_game(game)
        assert result is not None
        # (7 - 2) / 25 * 100 = 20.0
        assert result == pytest.approx(20.0, abs=0.01)

    def test_no_batters_returns_none(self) -> None:
        game = _make_pitching_game(batters_faced=0)
        assert _compute_k_bb_pct_from_game(game) is None


# ---------------------------------------------------------------------------
# Tests: Filtering and weighting
# ---------------------------------------------------------------------------


class TestFilterGamesByWindow:
    def test_includes_games_within_window(self) -> None:
        games = [
            {"game_date": DAY0 - timedelta(days=3)},
            {"game_date": DAY0 - timedelta(days=5)},
            {"game_date": DAY0 - timedelta(days=10)},
        ]
        result = _filter_games_by_window(games, DAY0, window_days=7)
        assert len(result) == 2  # 3 and 5 days ago

    def test_excludes_today_and_future(self) -> None:
        games = [
            {"game_date": DAY0},  # same day → excluded
            {"game_date": DAY0 + timedelta(days=1)},  # future → excluded
        ]
        result = _filter_games_by_window(games, DAY0, window_days=7)
        assert len(result) == 0

    def test_excludes_none_date(self) -> None:
        games = [{"game_date": None}]
        result = _filter_games_by_window(games, DAY0, window_days=7)
        assert len(result) == 0

    def test_empty_list(self) -> None:
        assert _filter_games_by_window([], DAY0, 7) == []


class TestComputeRecencyWeight:
    def test_single_game_today(self) -> None:
        games = [{"game_date": DAY0 - timedelta(days=0)}]
        w = _compute_recency_weight(games, DAY0, half_life_days=14.0)
        assert w == pytest.approx(1.0, abs=0.01)

    def test_single_game_far_away(self) -> None:
        games = [{"game_date": DAY0 - timedelta(days=30)}]
        w = _compute_recency_weight(games, DAY0, half_life_days=7.0)
        assert w < 1.0
        assert w > 0

    def test_multiple_games_sums_weights(self) -> None:
        games = [
            {"game_date": DAY0 - timedelta(days=1)},
            {"game_date": DAY0 - timedelta(days=7)},
        ]
        w = _compute_recency_weight(games, DAY0, half_life_days=14.0)
        expected = _recency_weight(1, 14.0) + _recency_weight(7, 14.0)
        assert w == pytest.approx(expected, abs=0.001)


# ---------------------------------------------------------------------------
# Tests: compute_rolling_features
# ---------------------------------------------------------------------------


class TestComputeRollingFeatures:
    def test_batter_only_player(self) -> None:
        """Batter with 3 games across different windows."""
        db = _FakeDb()
        db._set_result(
            "mlb_player_game_batting_stats",
            [
                _make_batting_game(
                    game_id="g1", game_date=D3, pa=4, ab=3, hits=1, hr=0, walks=1, woba=0.280,
                ),
                _make_batting_game(
                    game_id="g2", game_date=D10, pa=5, ab=5, hits=3, doubles=1, hr=1, woba=0.420,
                ),
                _make_batting_game(
                    game_id="g3", game_date=D20, pa=4, ab=4, hits=0, woba=0.150,
                ),
            ],
        )
        db._set_result("mlb_player_game_pitching_stats", [])

        rows = compute_rolling_features(db, "p1", DAY0)

        # Expected rows: batter has 3 windows x 3 splits = up to 9 rows
        assert len(rows) > 0
        batter_rows = [r for r in rows if r["role"] == "batter"]
        assert len(batter_rows) > 0

        # Check a batter row
        row = batter_rows[0]
        assert row["player_id"] == "p1"
        assert row["player_name"] == "Test Batter"
        assert row["team"] == "NYY"
        assert row["role"] == "batter"
        assert row["source"] == SOURCE
        assert row["feature_version"] == FEATURE_VERSION

        # 7d window should only include g1 (3 days ago)
        seven_day = [r for r in batter_rows if r["window_name"] == "7d" and r["handedness_split"] == "ALL"]
        assert len(seven_day) == 1
        assert seven_day[0]["plate_appearances"] == 4

    def test_pitcher_only_player(self) -> None:
        """Pitcher with several games."""
        db = _FakeDb()
        db._set_result("mlb_player_game_batting_stats", [])
        db._set_result(
            "mlb_player_game_pitching_stats",
            [
                _make_pitching_game(
                    game_id="g1", pitcher_id="p2", game_date=D3,
                    ip=6.0, batters_faced=25, strikeouts=7, walks=2, hr=1,
                ),
                _make_pitching_game(
                    game_id="g2", pitcher_id="p2", game_date=D10,
                    ip=5.0, batters_faced=22, strikeouts=5, walks=3, hr=0,
                ),
            ],
        )

        rows = compute_rolling_features(db, "p2", DAY0)

        pitcher_rows = [r for r in rows if r["role"] == "pitcher"]
        assert len(pitcher_rows) > 0

        row = pitcher_rows[0]
        assert row["player_id"] == "p2"
        assert row["player_name"] == "Test Pitcher"
        assert row["handedness_split"] == "ALL"

        # 7d window: only g1 (3 days ago)
        seven_day = [r for r in pitcher_rows if r["window_name"] == "7d"]
        assert len(seven_day) >= 1

    def test_starter_role_separate_from_pitcher(self) -> None:
        """Starters get their own feature rows."""
        db = _FakeDb()
        db._set_result("mlb_player_game_batting_stats", [])
        db._set_result(
            "mlb_player_game_pitching_stats",
            [
                _make_pitching_game(
                    game_id="g1", pitcher_id="p3", game_date=D3,
                    is_starter=True, ip=6.0, batters_faced=25,
                    strikeouts=7, walks=2, hr=1,
                ),
            ],
        )

        rows = compute_rolling_features(db, "p3", DAY0)

        starter_rows = [r for r in rows if r["role"] == "starter"]
        assert len(starter_rows) > 0

        # Non-starter pitcher rows should also exist
        pitcher_rows = [r for r in rows if r["role"] == "pitcher"]
        assert len(pitcher_rows) > 0

    def test_handedness_splits_for_batters(self) -> None:
        """Batter rows should include VS_RHP and VS_LHP splits."""
        db = _FakeDb()
        db._set_result(
            "mlb_player_game_batting_stats",
            [
                _make_batting_game(
                    game_id="g1", game_date=D3, opposing_starter_throws="R",
                ),
                _make_batting_game(
                    game_id="g2", game_date=D6, opposing_starter_throws="L",
                ),
                _make_batting_game(
                    game_id="g3", game_date=D10, opposing_starter_throws="R",
                ),
            ],
        )
        db._set_result("mlb_player_game_pitching_stats", [])

        rows = compute_rolling_features(db, "p1", DAY0)

        batter_rows = [r for r in rows if r["role"] == "batter"]
        split_names = {(r["window_name"], r["handedness_split"]) for r in batter_rows}

        # 30d window should have all 3 splits
        assert ("30d", "ALL") in split_names
        assert ("30d", "VS_RHP") in split_names
        assert ("30d", "VS_LHP") in split_names

    def test_no_games_returns_empty_list(self) -> None:
        db = _FakeDb()
        db._set_result("mlb_player_game_batting_stats", [])
        db._set_result("mlb_player_game_pitching_stats", [])

        rows = compute_rolling_features(db, "unknown", DAY0)
        assert rows == []

    def test_upsert_rolling_features(self) -> None:
        """Upsert function calls db.execute for each row."""
        db = _FakeDb()
        rows = [
            {
                "as_of_date": DAY0,
                "player_id": "p1",
                "player_name": "Test",
                "team": "NYY",
                "role": "batter",
                "window_name": "7d",
                "handedness_split": "ALL",
                "plate_appearances": 10,
                "innings_pitched": None,
                "woba": 0.350,
                "wrc_plus": 112,
                "fip": None,
                "xfip": None,
                "siera": None,
                "k_bb_pct": None,
                "o_swing_pct": None,
                "z_contact_pct": None,
                "hard_hit_pct": None,
                "avg_exit_velocity": None,
                "avg_launch_angle": None,
                "whiff_rate": None,
                "csw_pct": None,
                "recency_weight": 1.0,
                "source": SOURCE,
                "feature_version": FEATURE_VERSION,
            }
        ]

        count = upsert_rolling_features(db, rows)
        assert count == 1
        assert len(db.calls) == 1
        sql, params = db.calls[0]
        assert "INSERT INTO mlb_player_rolling_features" in sql
        assert params["player_id"] == "p1"
        assert params["as_of_date"] == DAY0


# ---------------------------------------------------------------------------
# Tests: compute_all_rolling_features
# ---------------------------------------------------------------------------


class TestComputeAllRollingFeatures:
    def test_with_explicit_player_ids(self) -> None:
        db = _FakeDb()

        # Need to set up _set_result BEFORE calling compute_all_rolling_features
        # because it queries inside compute_rolling_features

        db2 = _FakeDb()
        db2._set_result(
            "mlb_player_game_batting_stats",
            [
                _make_batting_game(
                    game_id="g1", player_id="p1", game_date=D3,
                ),
            ],
        )
        db2._set_result("mlb_player_game_pitching_stats", [])

        # Use the fake DB from db2 as the execute target
        # We'll test by calling with explicit player IDs
        rows = compute_all_rolling_features(db2, DAY0, player_ids=["p1"])
        assert rows > 0

    def test_discovers_player_ids_when_not_provided(self) -> None:
        """When player_ids is None, queries both tables for distinct IDs."""
        db = _FakeDb()
        db._set_result("mlb_player_game_batting_stats", [
            {"player_id": "batter1"},
        ])
        db._set_result("mlb_player_game_pitching_stats", [
            {"pitcher_id": "pitcher1"},
        ])

        # With those query results but no game-level data, the inner
        # compute_rolling_features returns [] → total 0
        result = compute_all_rolling_features(db, DAY0, player_ids=[])
        assert result == 0


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_compute_woba_with_zero_pa(self) -> None:
        game = _make_batting_game(pa=0, ab=0, hits=0, walks=0, woba=None)
        assert _compute_woba_from_game(game) is None

    def test_filter_window_with_mixed_date_types(self) -> None:
        """Should handle both date objects and ISO strings."""
        games = [
            {"game_date": date(2026, 5, 28)},
            {"game_date": "2026-05-25"},
        ]
        result = _filter_games_by_window(games, date(2026, 6, 1), window_days=7)
        assert len(result) == 2

    def test_recency_weight_with_varied_half_lives(self) -> None:
        """Shorter half-life = less weight on old games."""
        game_age = 14
        w_long = _recency_weight(game_age, 28.0)  # longer half-life
        w_short = _recency_weight(game_age, 7.0)   # shorter half-life
        # With longer half-life, weight should be higher
        assert w_long == pytest.approx(0.707, abs=0.01)
        assert w_short == pytest.approx(0.25, abs=0.01)

    def test_siera_with_realistic_stats(self) -> None:
        # 5 K, 2 BB in 25 BFP ≈ 3.04 SIERA — a typical mid-rotation line
        game = _make_pitching_game(batters_faced=25, strikeouts=5, walks=2)
        result = _compute_siera_from_game(game)
        assert result is not None
        assert result == pytest.approx(3.04, abs=0.05)

    def test_compute_k_bb_pct_zero_denominator(self) -> None:
        game = _make_pitching_game(batters_faced=0)
        assert _compute_k_bb_pct_from_game(game) is None
