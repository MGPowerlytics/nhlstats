"""Provider RED tests for the Tennis bet opportunity branch in OddsComparator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from plugins.odds_comparator import BettingThresholds, GameContext


SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "tennis_bet_opportunity_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class _StubEloSystem:
    def __init__(self, ratings: dict[str, float]) -> None:
        self._ratings = ratings

    def get_rating(self, name: str, tour: str | None = None) -> float:
        return self._ratings.get(name, 1500.0)


def _build_atp_context(
    *, home_prob: float = 0.28, away_prob: float = 0.72
) -> GameContext:
    elo = _StubEloSystem({"Alexander Blockx": 1620.0, "Flavio Cobolli": 1700.0})
    ctx = GameContext(
        sport="tennis",
        game_id="TENNIS_ATP_2026-04-07_AlexanderBlockx_FlavioCobolli",
        home_team_name="Alexander Blockx",
        away_team_name="Flavio Cobolli",
        source="kalshi",
        canon_home="Alexander Blockx",
        canon_away="Flavio Cobolli",
        elo_home="Alexander Blockx",
        elo_away="Flavio Cobolli",
        odds_by_bm={"Kalshi": {"home": 1.0 / 0.34, "away": 1.0 / 0.66}},
        tickers_by_bm={
            "Kalshi": {
                "home": "KXATPMATCH-26APR07COBBLO-BLO",
                "away": "KXATPMATCH-26APR07COBBLO-COB",
            }
        },
        elo_system=elo,
        tour="ATP",
        home_win_prob=home_prob,
        away_win_prob=away_prob,
    )
    return ctx


def test_evaluate_emits_contract_valid_tennis_opportunity() -> None:
    ctx = _build_atp_context()
    opportunities = ctx.evaluate(BettingThresholds(min_edge=0.03, max_edge=1.0))

    assert opportunities, "expected at least one opportunity for the away side"
    schema = _load_schema()
    for opp in opportunities:
        Draft202012Validator(schema).validate(opp)
        assert opp["sport"] == "TENNIS"
        assert opp["tour"] == "ATP"


def test_evaluate_clamps_edge_above_max_threshold() -> None:
    """Edges > 0.40 must be clamped out for tennis (data-error guard)."""
    # Push elo_prob ridiculously high vs market; edge >> 0.40 → must drop.
    ctx = _build_atp_context(home_prob=0.99, away_prob=0.99)
    ctx.odds_by_bm = {"Kalshi": {"home": 100.0, "away": 100.0}}

    opportunities = ctx.evaluate(BettingThresholds(min_edge=0.03, max_edge=1.0))
    for opp in opportunities:
        assert opp["edge"] <= 0.40


def test_recommendation_date_extracted_from_tennis_game_id() -> None:
    ctx = _build_atp_context()
    assert ctx.recommendation_date == "2026-04-07"


def test_normalized_sport_for_tennis_is_uppercase() -> None:
    ctx = _build_atp_context()
    assert ctx.normalized_sport == "TENNIS"
