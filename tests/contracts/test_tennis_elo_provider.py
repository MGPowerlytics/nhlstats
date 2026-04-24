"""Provider RED tests for TennisEloRating.predict_with_payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from plugins.elo.tennis_elo_rating import TennisEloRating


SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "tennis_elo_prediction_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def elo() -> TennisEloRating:
    rating = TennisEloRating()
    rating.atp_ratings["Djokovic N."] = 1700.0
    rating.atp_ratings["Alcaraz C."] = 1620.0
    rating.wta_ratings["Swiatek I."] = 1850.0
    rating.wta_ratings["Gauff C."] = 1730.0
    return rating


def test_predict_with_payload_satisfies_atp_contract(elo: TennisEloRating) -> None:
    payload = elo.predict_with_payload("Djokovic N.", "Alcaraz C.", tour="ATP")
    Draft202012Validator(_load_schema()).validate(payload)

    assert payload["tour"] == "ATP"
    assert payload["sport"] == "TENNIS"
    assert payload["payload_kind"] == "elo_prediction"
    assert payload["k_factor"] == elo.config.k_factor
    assert payload["home_advantage"] == 0.0
    assert payload["rating_a"] == 1700.0
    assert payload["rating_b"] == 1620.0


def test_predict_with_payload_satisfies_wta_contract(elo: TennisEloRating) -> None:
    payload = elo.predict_with_payload("Swiatek I.", "Gauff C.", tour="WTA")
    Draft202012Validator(_load_schema()).validate(payload)

    assert payload["tour"] == "WTA"
    assert payload["rating_a"] == 1850.0


def test_predict_with_payload_emits_calibrated_in_unit_interval(
    elo: TennisEloRating,
) -> None:
    payload = elo.predict_with_payload("Djokovic N.", "Alcaraz C.", tour="ATP")
    assert 0.0 <= payload["raw_prob_a"] <= 1.0
    assert 0.0 <= payload["calibrated_prob_a"] <= 1.0


def test_predict_with_payload_rejects_unknown_tour(elo: TennisEloRating) -> None:
    with pytest.raises(ValueError):
        elo.predict_with_payload("Djokovic N.", "Alcaraz C.", tour="DAVIS")
