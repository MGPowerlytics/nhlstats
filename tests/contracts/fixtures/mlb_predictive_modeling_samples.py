"""Deterministic MLB predictive-modeling contract fixtures."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


FEATURE_HASH = "abc123def4567890"
GAME_ID = "745431"
HOME_TEAM = "New York Yankees"
AWAY_TEAM = "Boston Red Sox"
MODEL_VERSION = "mlb_moneyline_public_v1"


_ADVANCED_FEATURES: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "advanced_feature_vector",
    "game_id": GAME_ID,
    "home_team": HOME_TEAM,
    "away_team": AWAY_TEAM,
    "as_of_ts": "2026-05-10T14:00:00Z",
    "feature_version": "v1",
    "feature_hash": FEATURE_HASH,
    "feature_availability": {
        "woba": "available",
        "wrc_plus": "derived",
        "catcher_framing": "unavailable",
        "umpire_zone": "unavailable",
        "ticket_money": "unavailable",
    },
    "sabermetrics": {
        "home_woba": 0.334,
        "away_woba": 0.318,
        "home_wrc_plus": 112.0,
        "away_wrc_plus": 98.0,
        "home_starter_fip": 3.42,
        "away_starter_fip": 4.11,
        "home_starter_xfip": 3.55,
        "away_starter_xfip": 4.03,
        "home_starter_siera": 3.50,
        "away_starter_siera": 4.05,
        "home_starter_k_bb_pct": 0.214,
        "away_starter_k_bb_pct": 0.143,
    },
    "plate_discipline": {
        "home_o_swing_pct": 0.303,
        "away_o_swing_pct": 0.322,
        "home_z_contact_pct": 0.865,
        "away_z_contact_pct": 0.844,
        "home_hard_hit_pct": 0.421,
        "away_hard_hit_pct": 0.389,
        "home_exit_velocity": 90.6,
        "away_exit_velocity": 88.9,
        "home_launch_angle": 12.4,
        "away_launch_angle": 10.1,
        "home_whiff_rate": 0.231,
        "away_whiff_rate": 0.257,
        "home_csw_pct": 0.287,
        "away_csw_pct": 0.301,
    },
    "matchup_dynamics": {
        "pitcher_batter_k_rate_delta": 0.036,
        "pitcher_batter_contact_rate_delta": -0.018,
        "pitch_mix_mismatch": 0.042,
        "platoon_advantage": 0.019,
        "catcher_framing_runs": None,
        "umpire_zone_runs": None,
        "pitch_accuracy": 0.63,
        "vertical_location_score": 0.68,
    },
    "bullpen_fatigue": {
        "home_pitches_last_3_days": 126,
        "away_pitches_last_3_days": 151,
        "home_pitches_last_5_days": 214,
        "away_pitches_last_5_days": 242,
        "home_relievers_over_15_pitches": 3,
        "away_relievers_over_15_pitches": 4,
        "home_relievers_over_20_pitches": 1,
        "away_relievers_over_20_pitches": 2,
        "home_velocity_penalty": -0.1,
        "away_velocity_penalty": -0.35,
    },
    "recency": {
        "window_days": 30,
        "plate_appearance_window": 500,
        "recency_weight": 0.65,
    },
}

_ENVIRONMENT_FEATURES: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "environment_features",
    "game_id": GAME_ID,
    "game_date": "2026-05-10",
    "venue": "Yankee Stadium",
    "park_factors": {
        "runs": 1.03,
        "home_runs": 1.12,
        "doubles_triples": 0.97,
        "singles": 1.01,
    },
    "weather": {
        "temperature_f": 72.0,
        "humidity_pct": 61.0,
        "wind_speed_mph": 8.5,
        "wind_direction_degrees": 225.0,
        "altitude_ft": 54.0,
    },
    "hit_distance_adjustment_ft": 5.4,
    "source": "public_weather",
    "observed_at": "2026-05-10T13:30:00Z",
    "feature_version": "v1",
    "availability": "available",
}

_TRAVEL_FATIGUE: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "travel_fatigue_features",
    "game_id": GAME_ID,
    "team": AWAY_TEAM,
    "is_home": False,
    "previous_game_id": "745430",
    "previous_game_date": "2026-05-09",
    "previous_venue": "Fenway Park",
    "time_zones_crossed": 0,
    "travel_direction": "none",
    "west_to_east_penalty": 0.0,
    "circadian_advantage_hours": -0.5,
    "local_start_time": "19:05:00",
    "days_rest": 0,
    "source": "schedule_derived",
    "feature_version": "v1",
}

_MARKET_SIGNALS: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "market_signals",
    "market_signal_id": "745431_KXMLBGAME-26MAY10NYYBOS-NYY_20260510T140000Z",
    "game_id": GAME_ID,
    "ticker": "KXMLBGAME-26MAY10NYYBOS-NYY",
    "outcome_name": "home",
    "snapshot_at": "2026-05-10T14:00:00Z",
    "market_prob": 0.541,
    "ticket_pct": None,
    "money_pct": None,
    "pro_edge": None,
    "line_move": 0.015,
    "reverse_line_movement": False,
    "source": "kalshi_public_market",
    "feature_version": "v1",
    "availability": "unavailable",
}

_PA_SIMULATION: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "pa_simulation",
    "game_id": GAME_ID,
    "batter_id": "592450",
    "pitcher_id": "543037",
    "method": "log5_empirical_bayes",
    "outcome_probs": {
        "strikeout": 0.231,
        "walk_hbp": 0.091,
        "single": 0.151,
        "double_triple": 0.052,
        "home_run": 0.041,
        "ball_in_play_out": 0.434,
    },
    "source_features_hash": FEATURE_HASH,
    "model_version": "mlb_pa_public_v1",
}

_GAME_SIMULATION: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "game_simulation",
    "game_id": GAME_ID,
    "simulation_count": 5000,
    "seed": 745431,
    "home_win_prob": 0.574,
    "away_win_prob": 0.426,
    "run_distribution": {
        "home_mean": 4.82,
        "away_mean": 4.21,
        "total_mean": 9.03,
        "home_p10": 2.0,
        "home_p90": 8.0,
        "away_p10": 1.0,
        "away_p90": 7.0,
    },
    "model_version": "mlb_sim_public_v1",
}

_MODEL_PREDICTION: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "model_prediction",
    "prediction_id": "mlb_moneyline_public_v1_745431_home_2026-05-10",
    "model_version": MODEL_VERSION,
    "game_id": GAME_ID,
    "market_name": "moneyline",
    "outcome_name": "home",
    "run_date": "2026-05-10",
    "model_prob": 0.574,
    "market_prob": 0.541,
    "edge": 0.033,
    "expected_value": 0.061,
    "calibration_method": "isotonic",
    "ece_at_train": 0.031,
    "feature_hash": FEATURE_HASH,
    "simulation_summary": {"simulation_count": 5000, "home_win_prob": 0.574},
    "abstain": False,
    "abstention_reason": None,
}

_PROP_PREDICTION: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "prop_prediction",
    "prediction_id": "mlb_prop_public_v1_745431_543037_strikeouts",
    "model_version": "mlb_prop_public_v1",
    "game_id": GAME_ID,
    "player_id": "543037",
    "player_name": "Gerrit Cole",
    "team": HOME_TEAM,
    "prop_type": "strikeouts",
    "line": 6.5,
    "over_prob": 0.548,
    "under_prob": 0.452,
    "market_prob": 0.515,
    "edge": 0.033,
    "expected_value": 0.064,
    "simulation_summary": {"mean": 6.9, "p10": 4.0, "p90": 10.0},
    "abstain": False,
    "abstention_reason": None,
}


def build_mlb_advanced_features_payload() -> Dict[str, Any]:
    """Return a fresh advanced feature-vector payload."""
    return deepcopy(_ADVANCED_FEATURES)


def build_mlb_environment_features_payload() -> Dict[str, Any]:
    """Return a fresh environment feature payload."""
    return deepcopy(_ENVIRONMENT_FEATURES)


def build_mlb_travel_fatigue_payload() -> Dict[str, Any]:
    """Return a fresh travel/fatigue feature payload."""
    return deepcopy(_TRAVEL_FATIGUE)


def build_mlb_market_signals_payload() -> Dict[str, Any]:
    """Return a fresh market-signal payload."""
    return deepcopy(_MARKET_SIGNALS)


def build_mlb_pa_simulation_payload() -> Dict[str, Any]:
    """Return a fresh plate-appearance simulation payload."""
    return deepcopy(_PA_SIMULATION)


def build_mlb_game_simulation_payload() -> Dict[str, Any]:
    """Return a fresh game-simulation payload."""
    return deepcopy(_GAME_SIMULATION)


def build_mlb_model_prediction_payload() -> Dict[str, Any]:
    """Return a fresh moneyline model prediction payload."""
    return deepcopy(_MODEL_PREDICTION)


def build_mlb_prop_prediction_payload() -> Dict[str, Any]:
    """Return a fresh prop prediction payload."""
    return deepcopy(_PROP_PREDICTION)
