from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for relative_path in ("plugins", "dags"):
    candidate = str(REPO_ROOT / relative_path)
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import multi_sport_betting_workflow as workflow
from plugins.bet_loader import BetContext, BetLoader, BetRecommendation
from plugins.odds_comparator import BettingOutcome, BettingThresholds, GameContext
from tests.contracts.fixtures.epl_bet_recommendations import (
    build_epl_recommendation_contract_expectations,
)
from tests.contracts.helpers import validate_contract_definition

CONTRACT_PATH = Path(__file__).parent / "schemas" / "epl_bet_recommendation_row_v1.json"


class _RatingStub:
    def get_rating(self, team: str) -> float:
        ratings = {
            "Liverpool": 1612.4,
            "Bournemouth": 1498.2,
        }
        return ratings[team]


@pytest.fixture(scope="module")
def recommendation_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def recommendation_expectations() -> dict[str, Any]:
    return build_epl_recommendation_contract_expectations()


def _build_real_provider_payload(
    *, side: str = "home", team_name: str = "Liverpool", ticker: str | None = "KXHEPL-LIVBOU-20250816"
) -> dict[str, Any]:
    odds_by_side = {
        "home": {"home": 2.13},
        "draw": {"draw": 5.25},
        "away": {"away": 4.5},
    }
    tickers_by_side = {
        "home": {"home": ticker},
        "draw": {"draw": ticker},
        "away": {"away": ticker},
    }
    probabilities = {
        "home": (0.58, 0.47, 0.11),
        "draw": (0.24, 0.19, 0.05),
        "away": (0.18, 0.14, 0.04),
    }
    elo_prob, market_prob, edge = probabilities[side]
    context = GameContext(
        sport="epl",
        game_id="EPL-2025-08-16-LIV-BOU",
        home_team_name="Liverpool",
        away_team_name="Bournemouth",
        source="kalshi",
        canon_home="Liverpool",
        canon_away="Bournemouth",
        elo_home="Liverpool",
        elo_away="Bournemouth",
        odds_by_bm={"Kalshi": odds_by_side[side]},
        tickers_by_bm={"Kalshi": tickers_by_side[side]},
        elo_system=_RatingStub(),
    )
    return BettingOutcome(
        side=side,
        team_name=team_name,
        elo_prob=elo_prob,
        market_prob=market_prob,
        market_odds=next(iter(odds_by_side[side].values())),
        edge=edge,
    ).to_opportunity(context, BettingThresholds())


@pytest.fixture
def saved_payload_via_identify_good_bets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    provider_payload = _build_real_provider_payload()
    task_instance = SimpleNamespace(
        xcom_pull=lambda **_: {"Liverpool": 1612.4, "Bournemouth": 1498.2}
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(workflow, "_load_elo_system", lambda sport, ratings: object())
    monkeypatch.setattr(
        workflow,
        "_find_betting_opportunities",
        lambda sport, elo_system, elo_ratings, config, date_str=None: [provider_payload],
    )

    workflow.identify_good_bets("epl", task_instance=task_instance, ds="2025-08-16")

    saved_path = tmp_path / "data" / "epl" / "bets_2025-08-16.json"
    return json.loads(saved_path.read_text(encoding="utf-8"))[0]


def test_identify_good_bets_saves_uppercase_epl_sport(
    saved_payload_via_identify_good_bets: dict[str, Any],
    recommendation_expectations: dict[str, Any],
) -> None:
    assert saved_payload_via_identify_good_bets["sport"] == recommendation_expectations["sport"]


def test_identify_good_bets_saves_contract_bet_on_semantics(
    saved_payload_via_identify_good_bets: dict[str, Any],
    recommendation_expectations: dict[str, Any],
) -> None:
    assert (
        saved_payload_via_identify_good_bets["bet_on"]
        in recommendation_expectations["allowed_bet_on"]
    )


def test_save_bets_to_file_round_trips_contract_saved_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recommendation_contract: dict[str, Any],
) -> None:
    payload = _build_real_provider_payload()
    monkeypatch.chdir(tmp_path)

    workflow._save_bets_to_file("epl", [payload], {"ds": "2025-08-16"})

    saved_path = tmp_path / "data" / "epl" / "bets_2025-08-16.json"
    saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))[0]

    validate_contract_definition(saved_payload, recommendation_contract, "saved_payload")


def test_bet_loader_persistence_params_match_persisted_row_contract(
    monkeypatch: pytest.MonkeyPatch,
    recommendation_contract: dict[str, Any],
) -> None:
    captured_params: list[dict[str, Any]] = []
    loader = BetLoader()
    loader._upsert_bet = lambda db, params: captured_params.append(dict(params))
    monkeypatch.setattr(loader, "_lazy_initialize_table", lambda: None)
    monkeypatch.setattr(
        loader,
        "_load_bets_from_file",
        lambda sport, date_str: [_build_real_provider_payload()],
    )

    loaded = loader.load_bets_for_date("epl", "2025-08-16")

    assert loaded == 1
    validate_contract_definition(captured_params[0], recommendation_contract, "persisted_row")


def test_bet_loader_fallback_ids_stay_stable_without_ticker() -> None:
    payload = _build_real_provider_payload(side="draw", team_name="Draw", ticker=None)

    first = BetRecommendation.from_dict(
        payload,
        BetContext(sport="EPL", date_str="2025-08-16", index=0),
    )
    second = BetRecommendation.from_dict(
        payload,
        BetContext(sport="EPL", date_str="2025-08-16", index=7),
    )

    assert first.bet_id == second.bet_id
