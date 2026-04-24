from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import validate

from plugins.elo.elo_update_helpers import process_games_with_elo
from plugins.elo.epl_elo_rating import EPLEloRating
from tests.contracts.fixtures.epl_elo_samples import (
    EPL_AWAY_TEAM,
    EPL_HOME_TEAM,
    build_epl_prediction_payload,
    build_epl_training_games,
    build_training_config,
    build_trained_epl_elo,
)


CONTRACT_PATH = Path(__file__).parent / "schemas" / "epl_elo_prediction_v1.json"
SUM_TOLERANCE = 0.01


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _assert_probability_triplet(payload: dict[str, Any]) -> None:
    total = (
        payload["home_win_probability"]
        + payload["draw_probability"]
        + payload["away_win_probability"]
    )
    assert abs(total - 1.0) <= SUM_TOLERANCE


def test_process_games_with_elo_creates_real_ratings_for_epl_teams() -> None:
    elo = EPLEloRating()

    processed_games = process_games_with_elo(
        elo,
        build_epl_training_games(),
        build_training_config(),
    )

    assert processed_games == 4
    assert elo.has_real_rating(EPL_HOME_TEAM) is True
    assert elo.has_real_rating(EPL_AWAY_TEAM) is True
    assert elo.has_real_rating("Ipswich Town") is False


def test_real_epl_prediction_payload_matches_frozen_contract() -> None:
    payload = build_epl_prediction_payload()

    validate(payload, _load_contract())
    _assert_probability_triplet(payload)


def test_real_epl_prediction_payload_exposes_explicit_three_way_probabilities() -> None:
    elo = build_trained_epl_elo()

    probabilities = elo.predict_3way(EPL_HOME_TEAM, EPL_AWAY_TEAM)

    assert set(probabilities) == {"home", "draw", "away"}
    assert 0.0 <= probabilities["home"] <= 1.0
    assert 0.0 <= probabilities["draw"] <= 1.0
    assert 0.0 <= probabilities["away"] <= 1.0
