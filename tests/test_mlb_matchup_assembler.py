"""Tests for MLB matchup feature assembly (matchup_assembler.py + features.py additions)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from plugins.mlb_modeling.features import (
    MLBFeatureRepository,
    RelieverAppearance,
    build_advanced_feature_payload,
    calculate_bullpen_fatigue,
    get_recent_bullpen_appearances,
)
from plugins.mlb_modeling.matchup_assembler import (
    MatchupAssemblyConfig,
    _build_feature_availability,
    _compute_matchup_dynamics,
    _compute_recency,
    _get_starter_data,
    _get_team_batting_features,
    _get_team_plate_discipline,
    _query_one,
    _zero_if_none,
    assemble_matchup_features,
)
from plugins.mlb_modeling.public_sources import AvailabilityStatus
from tests.contracts.helpers import validate_contract_payload
from tests.contracts.fixtures.mlb_predictive_modeling_samples import (
    build_mlb_advanced_features_payload,
)

SCHEMAS_ROOT = Path(__file__).resolve().parent / "contracts" / "schemas"


# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------


class _Row:
    """Mock DB row supporting both ``_mapping`` and dict conversion."""

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


class _FakeDb:
    """In-memory DB stub with canned result routing.

    Supports two registration modes:

    - :meth:`set_result` — matches rows to any SQL containing the fragment.
    - :meth:`set_param_result` — matches rows to SQL containing the fragment
      AND a specific parameter value (e.g. ``team=New York Yankees``).
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._results: dict[str, list[dict[str, Any]]] = {}
        self._param_results: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    def set_result(self, sql_fragment: str, rows: list[dict[str, Any]]) -> None:
        """Register canned rows for any SQL containing *sql_fragment*."""
        self._results[sql_fragment] = rows

    def set_param_result(
        self, sql_fragment: str, param_key: str, param_value: str, rows: list[dict[str, Any]]
    ) -> None:
        """Register canned rows for SQL containing *sql_fragment* when *param_key* == *param_value*."""
        self._param_results[(sql_fragment, param_key, param_value)] = rows

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> _RowsResult:
        resolved_params = params or {}
        self.calls.append((sql, resolved_params))

        # Check param-specific results first
        for (fragment, pkey, pval), rows in self._param_results.items():
            if fragment in sql and str(resolved_params.get(pkey, "")) == pval:
                return _RowsResult(rows)

        # Fall back to fragment-only results
        for fragment, rows in self._results.items():
            if fragment in sql:
                return _RowsResult(rows)
        return _RowsResult([])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GAME_DATE = date(2026, 5, 10)
AS_OF_TS = datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc)

HOME_TEAM = "New York Yankees"
AWAY_TEAM = "Boston Red Sox"
GAME_ID = "745431"

_STARTER_ROWS = [
    {
        "pitcher_id": "home_p1",
        "pitcher_name": "Home Starter",
        "throws": "R",
        "avg_velocity": 94.5,
        "primary_pitch_type": "FF",
        "primary_pitch_pct": 0.48,
    },
    {
        "pitcher_id": "away_p1",
        "pitcher_name": "Away Starter",
        "throws": "L",
        "avg_velocity": 92.3,
        "primary_pitch_type": "SL",
        "primary_pitch_pct": 0.35,
    },
]

_STARTER_ROLLING_ROWS = [
    {"player_id": "home_p1", "fip": 3.45, "xfip": 3.62, "siera": 3.50, "k_bb_pct": 0.214},
    {"player_id": "away_p1", "fip": 4.11, "xfip": 4.03, "siera": 4.05, "k_bb_pct": 0.143},
]

_HOME_BATTER_ROWS = [
    {
        "player_id": "b1",
        "team": HOME_TEAM,
        "role": "batter",
        "window_name": "30d",
        "handedness_split": "ALL",
        "plate_appearances": 80,
        "woba": 0.334,
        "wrc_plus": 112.0,
        "recency_weight": 8.5,
        "o_swing_pct": None,
        "z_contact_pct": None,
        "hard_hit_pct": None,
        "avg_exit_velocity": None,
        "avg_launch_angle": None,
        "whiff_rate": None,
        "csw_pct": None,
    },
    {
        "player_id": "b2",
        "team": HOME_TEAM,
        "role": "batter",
        "window_name": "30d",
        "handedness_split": "ALL",
        "plate_appearances": 60,
        "woba": 0.318,
        "wrc_plus": 98.0,
        "recency_weight": 7.2,
        "o_swing_pct": None,
        "z_contact_pct": None,
        "hard_hit_pct": None,
        "avg_exit_velocity": None,
        "avg_launch_angle": None,
        "whiff_rate": None,
        "csw_pct": None,
    },
]

_AWAY_BATTER_ROWS = [
    {
        "player_id": "b3",
        "team": AWAY_TEAM,
        "role": "batter",
        "window_name": "30d",
        "handedness_split": "ALL",
        "plate_appearances": 70,
        "woba": 0.302,
        "wrc_plus": 95.0,
        "recency_weight": 6.8,
        "o_swing_pct": None,
        "z_contact_pct": None,
        "hard_hit_pct": None,
        "avg_exit_velocity": None,
        "avg_launch_angle": None,
        "whiff_rate": None,
        "csw_pct": None,
    },
    {
        "player_id": "b4",
        "team": AWAY_TEAM,
        "role": "batter",
        "window_name": "30d",
        "handedness_split": "ALL",
        "plate_appearances": 50,
        "woba": 0.311,
        "wrc_plus": 101.0,
        "recency_weight": 5.5,
        "o_swing_pct": None,
        "z_contact_pct": None,
        "hard_hit_pct": None,
        "avg_exit_velocity": None,
        "avg_launch_angle": None,
        "whiff_rate": None,
        "csw_pct": None,
    },
]

_BULLPEN_ROWS = [
    {"pitcher_id": "rp1", "game_date": "2026-05-08", "pitch_count": 18, "avg_velocity": 93.0},
    {"pitcher_id": "rp2", "game_date": "2026-05-09", "pitch_count": 22, "avg_velocity": 94.1},
    {"pitcher_id": "rp3", "game_date": "2026-05-07", "pitch_count": 12, "avg_velocity": 95.2},
]


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tests for _zero_if_none
# ---------------------------------------------------------------------------


class TestZeroIfNone:
    def test_converts_none_to_zero(self) -> None:
        assert _zero_if_none(None) == 0.0

    def test_passes_float_through(self) -> None:
        assert _zero_if_none(3.14) == 3.14

    def test_passes_int_through(self) -> None:
        assert _zero_if_none(42) == 42.0


# ---------------------------------------------------------------------------
# Tests for get_recent_bullpen_appearances (features.py)
# ---------------------------------------------------------------------------


class TestGetRecentBullpenAppearances:
    def test_returns_reliever_appearances(self) -> None:
        db = _FakeDb()
        db.set_result("mlb_player_game_pitching_stats", _BULLPEN_ROWS)

        result = get_recent_bullpen_appearances(db, HOME_TEAM, GAME_DATE, days_back=5)

        assert len(result) == 3
        assert all(isinstance(a, RelieverAppearance) for a in result)
        assert result[0].pitcher_id == "rp1"
        assert result[0].pitch_count == 18
        assert result[1].appearance_date == date(2026, 5, 9)

    def test_returns_empty_when_no_relievers(self) -> None:
        db = _FakeDb()
        db.set_result("mlb_player_game_pitching_stats", [])

        result = get_recent_bullpen_appearances(db, HOME_TEAM, GAME_DATE, days_back=5)

        assert result == []

    def test_filters_by_team(self) -> None:
        db = _FakeDb()
        # No bullpen results registered for "Other Team" — returns empty list
        result = get_recent_bullpen_appearances(db, "Other Team", GAME_DATE, days_back=5)

        assert result == []

    def test_records_sql_calls(self) -> None:
        db = _FakeDb()
        db.set_result("mlb_player_game_pitching_stats", _BULLPEN_ROWS)

        get_recent_bullpen_appearances(db, HOME_TEAM, GAME_DATE, days_back=5)

        assert len(db.calls) == 1
        sql, params = db.calls[0]
        assert "mlb_player_game_pitching_stats" in sql
        assert "is_starter = FALSE" in sql
        assert params["team"] == HOME_TEAM


# ---------------------------------------------------------------------------
# Tests for _get_starter_data
# ---------------------------------------------------------------------------


class TestGetStarterData:
    def test_returns_starter_with_rolling_features(self) -> None:
        db = _FakeDb()
        db.set_result("mlb_player_game_pitching_stats", [_STARTER_ROWS[0]])
        db.set_result("mlb_player_rolling_features", [_STARTER_ROLLING_ROWS[0]])

        result = _get_starter_data(db, HOME_TEAM, GAME_DATE)

        assert result is not None
        assert result["pitcher_id"] == "home_p1"
        assert result["throws"] == "R"
        assert result["avg_velocity"] == 94.5
        # Rolling features merged in
        assert result["fip"] == 3.45
        assert result["k_bb_pct"] == 0.214

    def test_returns_starter_without_rolling_features(self) -> None:
        db = _FakeDb()
        db.set_result("mlb_player_game_pitching_stats", [_STARTER_ROWS[1]])
        db.set_result("mlb_player_rolling_features", [])

        result = _get_starter_data(db, AWAY_TEAM, GAME_DATE)

        assert result is not None
        assert result["pitcher_id"] == "away_p1"
        assert result["throws"] == "L"
        # Rolling features not merged
        assert result.get("fip") is None

    def test_returns_none_when_no_starter_found(self) -> None:
        db = _FakeDb()
        db.set_result("mlb_player_game_pitching_stats", [])

        result = _get_starter_data(db, "Unknown Team", GAME_DATE)

        assert result is None


# ---------------------------------------------------------------------------
# Tests for _get_team_batting_features
# ---------------------------------------------------------------------------


class TestGetTeamBattingFeatures:
    def test_returns_pa_weighted_woba_and_wrc_plus(self) -> None:
        db = _FakeDb()
        db.set_param_result("mlb_player_rolling_features", "team", HOME_TEAM, _HOME_BATTER_ROWS)

        result = _get_team_batting_features(db, HOME_TEAM, GAME_DATE)

        # PA-weighted: (0.334*80 + 0.318*60) / (80+60) = (26.72 + 19.08) / 140 = 45.80/140 = 0.3271
        assert result["woba"] == pytest.approx(0.3271, abs=0.001)
        assert result["wrc_plus"] == pytest.approx(106.0, abs=0.5)

    def test_returns_none_when_no_data(self) -> None:
        db = _FakeDb()
        db.set_result("mlb_player_rolling_features", [])

        result = _get_team_batting_features(db, "Unknown Team", GAME_DATE)

        assert result["woba"] is None
        assert result["wrc_plus"] is None


# ---------------------------------------------------------------------------
# Tests for _get_team_plate_discipline
# ---------------------------------------------------------------------------


class TestGetTeamPlateDiscipline:
    def test_returns_none_for_all_discipline_fields(self) -> None:
        """Plate discipline fields are None in boxscore-derived rolling features."""
        db = _FakeDb()
        db.set_param_result("mlb_player_rolling_features", "team", HOME_TEAM, _HOME_BATTER_ROWS)

        result = _get_team_plate_discipline(db, HOME_TEAM, GAME_DATE)

        assert result["o_swing_pct"] is None
        assert result["z_contact_pct"] is None
        assert result["hard_hit_pct"] is None
        assert result["avg_exit_velocity"] is None

    def test_returns_none_when_no_rows(self) -> None:
        db = _FakeDb()
        db.set_result("mlb_player_rolling_features", [])

        result = _get_team_plate_discipline(db, "Unknown Team", GAME_DATE)

        for val in result.values():
            assert val is None


# ---------------------------------------------------------------------------
# Tests for _compute_matchup_dynamics
# ---------------------------------------------------------------------------


class TestComputeMatchupDynamics:
    def test_computes_deltas_when_both_starters_present(self) -> None:
        home = {"k_bb_pct": 0.214, "primary_pitch_pct": 0.48}
        away = {"k_bb_pct": 0.143, "primary_pitch_pct": 0.35}

        result = _compute_matchup_dynamics(home, away)

        assert result["pitcher_batter_k_rate_delta"] == pytest.approx(0.071, abs=0.001)
        assert result["pitch_mix_mismatch"] == pytest.approx(0.13, abs=0.001)
        assert result["platoon_advantage"] == 0.0
        assert result["pitcher_batter_contact_rate_delta"] == 0.0
        assert result["catcher_framing_runs"] is None
        assert result["umpire_zone_runs"] is None
        assert result["pitch_accuracy"] is None
        assert result["vertical_location_score"] is None

    def test_defaults_to_zero_when_starters_missing(self) -> None:
        result = _compute_matchup_dynamics(None, None)

        assert result["pitcher_batter_k_rate_delta"] == 0.0
        assert result["pitch_mix_mismatch"] == 0.0
        assert result["platoon_advantage"] == 0.0

    def test_defaults_to_zero_when_data_missing(self) -> None:
        home = {"k_bb_pct": None, "primary_pitch_pct": None}
        away = {"k_bb_pct": None, "primary_pitch_pct": None}

        result = _compute_matchup_dynamics(home, away)

        assert result["pitcher_batter_k_rate_delta"] == 0.0
        assert result["pitch_mix_mismatch"] == 0.0

    def test_extra_keys_not_included(self) -> None:
        """Must match schema which has additionalProperties: false."""
        result = _compute_matchup_dynamics({}, {})
        expected_keys = {
            "pitcher_batter_k_rate_delta",
            "pitcher_batter_contact_rate_delta",
            "pitch_mix_mismatch",
            "platoon_advantage",
            "catcher_framing_runs",
            "umpire_zone_runs",
            "pitch_accuracy",
            "vertical_location_score",
        }
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Tests for _compute_recency
# ---------------------------------------------------------------------------


class TestComputeRecency:
    def test_averages_recency_across_both_teams(self) -> None:
        db = _FakeDb()
        db.set_param_result("mlb_player_rolling_features", "team", HOME_TEAM, _HOME_BATTER_ROWS)
        db.set_param_result("mlb_player_rolling_features", "team", AWAY_TEAM, _AWAY_BATTER_ROWS)

        result = _compute_recency(db, HOME_TEAM, AWAY_TEAM, GAME_DATE)

        assert result["window_days"] == 30
        # Home: 80+60=140, Away: 70+50=120, combined = 260
        assert result["plate_appearance_window"] == 260
        # per_batter_avg = (8.5+7.2+6.8+5.5)/4 = 7.0; normalised by /15.0 → 0.4667
        assert result["recency_weight"] == pytest.approx(0.4667, abs=0.01)

    def test_falls_back_to_schema_minimums_when_no_data(self) -> None:
        db = _FakeDb()

        result = _compute_recency(db, "Unknown A", "Unknown B", GAME_DATE)

        assert result["plate_appearance_window"] == 1
        assert result["recency_weight"] == 0.0

    def test_schema_compliant_keys(self) -> None:
        """Must match schema required keys."""
        db = _FakeDb()
        db.set_param_result("mlb_player_rolling_features", "team", HOME_TEAM, _HOME_BATTER_ROWS)
        db.set_param_result("mlb_player_rolling_features", "team", AWAY_TEAM, _AWAY_BATTER_ROWS)
        result = _compute_recency(db, HOME_TEAM, AWAY_TEAM, GAME_DATE)
        assert set(result.keys()) == {"window_days", "plate_appearance_window", "recency_weight"}


# ---------------------------------------------------------------------------
# Tests for _build_feature_availability
# ---------------------------------------------------------------------------


class TestBuildFeatureAvailability:
    def test_marks_all_available_when_data_present(self) -> None:
        availability = _build_feature_availability(
            home_starter={"pitcher_id": "p1"},
            away_starter={"pitcher_id": "p2"},
            home_batting={"woba": 0.334},
            away_batting={"woba": 0.318},
            home_pd={"o_swing_pct": 0.285},
            away_pd={"o_swing_pct": 0.293},
            home_bullpen_apps=[1],
            away_bullpen_apps=[2],
        )

        assert availability["rolling_batting"] == AvailabilityStatus.AVAILABLE
        assert availability["rolling_pitching"] == AvailabilityStatus.AVAILABLE
        assert availability["plate_discipline"] == AvailabilityStatus.AVAILABLE
        assert availability["matchup_dynamics"] == AvailabilityStatus.DERIVED
        assert availability["bullpen_fatigue"] == AvailabilityStatus.AVAILABLE

    def test_marks_unavailable_when_data_missing(self) -> None:
        availability = _build_feature_availability(
            home_starter=None,
            away_starter=None,
            home_batting={"woba": None},
            away_batting={"woba": None},
            home_pd={"o_swing_pct": None},
            away_pd={"o_swing_pct": None},
            home_bullpen_apps=[],
            away_bullpen_apps=[],
        )

        assert availability["rolling_batting"] == AvailabilityStatus.UNAVAILABLE
        assert availability["rolling_pitching"] == AvailabilityStatus.UNAVAILABLE
        assert availability["plate_discipline"] == AvailabilityStatus.UNAVAILABLE
        assert availability["bullpen_fatigue"] == AvailabilityStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# Integration tests for assemble_matchup_features
# ---------------------------------------------------------------------------


class TestAssembleMatchupFeatures:
    def _setup_db_with_all_data(self) -> _FakeDb:
        """Create a FakeDb with complete starter + home/away batter data."""
        db = _FakeDb()
        # Starter game stats: route by team param so each team gets the right starter
        db.set_param_result(
            "mlb_player_game_pitching_stats", "team", HOME_TEAM, [_STARTER_ROWS[0]],
        )
        db.set_param_result(
            "mlb_player_game_pitching_stats", "team", AWAY_TEAM, [_STARTER_ROWS[1]],
        )
        # Home team batter rolling features only (starters are queried by player_id)
        db.set_param_result(
            "mlb_player_rolling_features", "team", HOME_TEAM,
            _HOME_BATTER_ROWS,
        )
        db.set_param_result(
            "mlb_player_rolling_features", "team", AWAY_TEAM,
            _AWAY_BATTER_ROWS,
        )
        # Starter rolling features queried by player_id, not team
        db.set_param_result(
            "mlb_player_rolling_features", "player_id", "home_p1",
            [_STARTER_ROLLING_ROWS[0]],
        )
        db.set_param_result(
            "mlb_player_rolling_features", "player_id", "away_p1",
            [_STARTER_ROLLING_ROWS[1]],
        )
        return db

    def test_full_happy_path_builds_valid_payload(self) -> None:
        """End-to-end test with all data present produces a schema-compliant payload."""
        db = self._setup_db_with_all_data()

        payload = assemble_matchup_features(
            db,
            game_id=GAME_ID,
            home_team=HOME_TEAM,
            away_team=AWAY_TEAM,
            game_date=GAME_DATE,
            as_of_ts=AS_OF_TS,
        )

        assert payload is not None
        assert payload["game_id"] == GAME_ID
        assert payload["home_team"] == HOME_TEAM
        assert payload["away_team"] == AWAY_TEAM
        assert payload["feature_hash"] != "pending"
        assert payload["feature_hash"] != ""

        # Verify sabermetrics are populated
        assert payload["sabermetrics"]["home_woba"] > 0
        assert payload["sabermetrics"]["home_starter_fip"] > 0

        # Verify plate_discipline is all 0.0 (boxscore data doesn't populate these)
        assert payload["plate_discipline"]["home_o_swing_pct"] == 0.0

        # Verify matchup_dynamics
        assert isinstance(payload["matchup_dynamics"]["pitcher_batter_k_rate_delta"], float)

        # Verify bullpen fatigue exists
        assert payload["bullpen_fatigue"]["home_pitches_last_3_days"] >= 0

        # Verify recency is schema-compliant
        assert set(payload["recency"].keys()) == {
            "window_days", "plate_appearance_window", "recency_weight"
        }

    def test_missing_starter_still_produces_payload(self) -> None:
        """Graceful degradation: payload produced with UNAVAILABLE features."""
        db = _FakeDb()
        db.set_param_result("mlb_player_rolling_features", "team", HOME_TEAM, _HOME_BATTER_ROWS)
        db.set_param_result("mlb_player_rolling_features", "team", AWAY_TEAM, _AWAY_BATTER_ROWS)

        payload = assemble_matchup_features(
            db,
            game_id=GAME_ID,
            home_team=HOME_TEAM,
            away_team=AWAY_TEAM,
            game_date=GAME_DATE,
            as_of_ts=AS_OF_TS,
        )

        assert payload is not None
        # Starter sabermetrics should be 0.0
        assert payload["sabermetrics"]["home_starter_fip"] == 0.0
        assert payload["sabermetrics"]["away_starter_fip"] == 0.0
        # Matchup dynamics default to 0.0
        assert payload["matchup_dynamics"]["pitcher_batter_k_rate_delta"] == 0.0

    def test_payload_upserts_both_sides(self) -> None:
        """The assembler should persist for both home and away sides."""
        db = self._setup_db_with_all_data()

        assemble_matchup_features(
            db,
            game_id=GAME_ID,
            home_team=HOME_TEAM,
            away_team=AWAY_TEAM,
            game_date=GAME_DATE,
            as_of_ts=AS_OF_TS,
        )

        # Find INSERT / upsert calls
        upsert_calls = [
            (sql, params)
            for sql, params in db.calls
            if "INSERT INTO mlb_matchup_features" in sql
        ]
        assert len(upsert_calls) == 2

        sides = [p["side"] for _, p in upsert_calls]
        assert "home" in sides
        assert "away" in sides

    def test_payload_validates_against_contract_schema_when_complete(self) -> None:
        """Payload built by assemble_matchup_features with complete data should pass schema."""
        db = self._setup_db_with_all_data()

        payload = assemble_matchup_features(
            db,
            game_id=GAME_ID,
            home_team=HOME_TEAM,
            away_team=AWAY_TEAM,
            game_date=GAME_DATE,
            as_of_ts=AS_OF_TS,
        )

        validate_contract_payload(payload, _load_schema("mlb_advanced_features_v1.json"))


# ---------------------------------------------------------------------------
# Tests for features.py: calculate_bullpen_fatigue already has existing tests
# ---------------------------------------------------------------------------


class TestBuildAdvancedFeaturePayloadIntegration:
    """Verify that the existing contract test still passes."""

    def test_contract_fixture_still_validates(self) -> None:
        sample = build_mlb_advanced_features_payload()
        payload = build_advanced_feature_payload(
            game_id=sample["game_id"],
            home_team=sample["home_team"],
            away_team=sample["away_team"],
            as_of_ts=datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc),
            sabermetrics=sample["sabermetrics"],
            plate_discipline=sample["plate_discipline"],
            matchup_dynamics=sample["matchup_dynamics"],
            home_bullpen=calculate_bullpen_fatigue(
                [RelieverAppearance("h1", date(2026, 5, 9), 16)],
                as_of_date=date(2026, 5, 10),
            ),
            away_bullpen=calculate_bullpen_fatigue(
                [RelieverAppearance("a1", date(2026, 5, 8), 21)],
                as_of_date=date(2026, 5, 10),
            ),
            recency=sample["recency"],
            feature_availability={
                "woba": AvailabilityStatus.AVAILABLE,
                "catcher_framing": AvailabilityStatus.UNAVAILABLE,
            },
        )

        validate_contract_payload(payload, _load_schema("mlb_advanced_features_v1.json"))
        assert payload["feature_hash"] != "pending"
