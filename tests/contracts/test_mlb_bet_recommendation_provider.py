"""Wave-3 provider-red contract tests for MLB bet recommendation persistence.

Exercise the *real* producer code in:
- ``plugins/bet_loader.py::BetLoader.load_bets_for_date``
- ``plugins/bet_loader.py::BetData.generate_id``
- ``dags/multi_sport_betting_workflow.py::identify_good_bets`` /
  ``_save_bets_to_file``

Captured payloads + persisted SQL params are validated against the frozen
``mlb_bet_recommendation_row_v1`` contract. Known producer drift modes are
``xfail(strict=True)`` with the Wave-4-6 fix task ID.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
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
from plugins.bet_loader import BetContext, BetData, BetLoader, BetRecommendation
from tests.contracts.fixtures.mlb_bet_recommendation_samples import (
    build_mlb_recommendation_contract_expectations,
    build_mlb_recommendation_payload,
)
from tests.contracts.helpers import validate_contract_definition


CONTRACT_PATH = Path(__file__).parent / "schemas" / "mlb_bet_recommendation_row_v1.json"
WAVE_4_TASK = "mlb-kalshi-recommendation-fix"
MLB_HOME_TEAM = "New York Yankees"
MLB_AWAY_TEAM = "Boston Red Sox"
MLB_TICKER = "KXMLBGAME-25APR15NYYBOS-NYY"
MLB_DATE = "2025-04-15"


@pytest.fixture(scope="module")
def recommendation_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def recommendation_expectations() -> dict[str, Any]:
    return build_mlb_recommendation_contract_expectations()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_saved_payload(*, ticker: str | None = MLB_TICKER) -> dict[str, Any]:
    """Build a realistic identify_good_bets-style saved-payload for MLB.

    Mirrors what ``OddsComparator.find_opportunities`` would emit *after* the
    Wave-4-6 fix (uppercase sport, contract bet_id) so we can isolate the
    BetLoader-side contract behavior.
    """
    payload = build_mlb_recommendation_payload()
    payload["ticker"] = ticker
    if ticker is None:
        # Drop bet_id so generate_id() takes the no-ticker fallback path.
        payload.pop("bet_id", None)
    return payload


def _make_loader_with_capture() -> tuple[BetLoader, list[dict[str, Any]]]:
    captured: list[dict[str, Any]] = []
    loader = BetLoader()
    loader._upsert_bet = lambda db, params: captured.append(dict(params))
    loader._table_initialized = True  # bypass DDL on the fake DB
    return loader, captured


# ---------------------------------------------------------------------------
# Real BetLoader.load_bets_for_date provider tests
# ---------------------------------------------------------------------------


def test_bet_loader_persists_contract_row_when_ticker_present(
    monkeypatch: pytest.MonkeyPatch,
    recommendation_contract: dict[str, Any],
    recommendation_expectations: dict[str, Any],
) -> None:
    """Real BetLoader path with a ticker present must produce a contract-valid row."""
    loader, captured = _make_loader_with_capture()
    monkeypatch.setattr(loader, "_lazy_initialize_table", lambda: None)
    monkeypatch.setattr(
        loader,
        "_load_bets_from_file",
        lambda sport, date_str: [_build_saved_payload(ticker=MLB_TICKER)],
    )

    loaded = loader.load_bets_for_date("mlb", MLB_DATE)

    assert loaded == 1
    assert len(captured) == 1
    row = captured[0]
    assert row["sport"] == recommendation_expectations["sport"]
    assert row["ticker"] == MLB_TICKER
    validate_contract_definition(row, recommendation_contract, "persisted_row")


def test_bet_loader_persists_contract_row_when_ticker_absent(
    monkeypatch: pytest.MonkeyPatch,
    recommendation_contract: dict[str, Any],
) -> None:
    """The no-ticker path currently writes a null ticker AND a bet_id whose
    pattern violates ``^MLB_..._(home|away)$`` (BetData.generate_id appends a
    trailing index). Both failures will validate-fail until the Wave-4-6 fix
    lands."""
    loader, captured = _make_loader_with_capture()
    monkeypatch.setattr(loader, "_lazy_initialize_table", lambda: None)
    monkeypatch.setattr(
        loader,
        "_load_bets_from_file",
        lambda sport, date_str: [_build_saved_payload(ticker=None)],
    )

    loaded = loader.load_bets_for_date("mlb", MLB_DATE)

    assert loaded == 1
    validate_contract_definition(captured[0], recommendation_contract, "persisted_row")


# ---------------------------------------------------------------------------
# BetData.generate_id stability for MLB without ticker
# ---------------------------------------------------------------------------


def test_bet_data_generate_id_is_stable_for_mlb_without_ticker() -> None:
    """Same logical bet must produce the same id across runs (and across
    BetContext.index values) so upserts collapse correctly."""
    bet = BetData(
        home_team=MLB_HOME_TEAM,
        away_team=MLB_AWAY_TEAM,
        ticker=None,
        side="home",
        bet_on="home",
        elo_prob=0.58,
        market_prob=0.47,
        edge=0.11,
    )

    first = bet.generate_id(BetContext(sport="MLB", date_str=MLB_DATE, index=0))
    second = bet.generate_id(BetContext(sport="MLB", date_str=MLB_DATE, index=7))

    assert first == second


def test_bet_data_generate_id_is_stable_for_mlb_with_ticker() -> None:
    """Sanity: the ticker-present id formula is already index-independent."""
    bet = BetData(
        home_team=MLB_HOME_TEAM,
        away_team=MLB_AWAY_TEAM,
        ticker=MLB_TICKER,
        side="home",
        bet_on="home",
        elo_prob=0.58,
        market_prob=0.47,
        edge=0.11,
    )

    first = bet.generate_id(BetContext(sport="MLB", date_str=MLB_DATE, index=0))
    second = bet.generate_id(BetContext(sport="MLB", date_str=MLB_DATE, index=42))

    assert first == second
    assert first == f"MLB_{MLB_DATE}_{MLB_TICKER}_home"


# ---------------------------------------------------------------------------
# DAG identify_good_bets / _save_bets_to_file provider tests
# ---------------------------------------------------------------------------


@pytest.fixture
def saved_payload_via_identify_good_bets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    # Use the post-fix producer shape (uppercase 'MLB'). After Wave 4-6 the
    # real ``BettingOutcome.to_opportunity`` emits uppercase for MLB, so the
    # mocked ``_find_betting_opportunities`` should mirror that contract.
    # ``market_odds`` is required by the DAG's print summary helper.
    provider_payload = build_mlb_recommendation_payload(market_odds=2.13)
    task_instance = SimpleNamespace(
        xcom_pull=lambda **_: {MLB_HOME_TEAM: 1612.4, MLB_AWAY_TEAM: 1498.2}
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(workflow, "_load_elo_system", lambda sport, ratings: object())
    monkeypatch.setattr(
        workflow,
        "_find_betting_opportunities",
        lambda sport, elo_system, elo_ratings, config, date_str=None: [
            deepcopy(provider_payload)
        ],
    )

    workflow.identify_good_bets("mlb", task_instance=task_instance, ds=MLB_DATE)

    saved_path = tmp_path / "data" / "mlb" / f"bets_{MLB_DATE}.json"
    return json.loads(saved_path.read_text(encoding="utf-8"))[0]


def test_identify_good_bets_saves_uppercase_mlb_sport(
    saved_payload_via_identify_good_bets: dict[str, Any],
    recommendation_expectations: dict[str, Any],
) -> None:
    assert (
        saved_payload_via_identify_good_bets["sport"]
        == recommendation_expectations["sport"]
    )


def test_save_bets_to_file_round_trips_contract_saved_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recommendation_contract: dict[str, Any],
) -> None:
    """A contract-shaped payload survives JSON round-trip via the real DAG helper."""
    payload = build_mlb_recommendation_payload()  # already contract-valid
    monkeypatch.chdir(tmp_path)

    workflow._save_bets_to_file("mlb", [payload], {"ds": MLB_DATE})

    saved_path = tmp_path / "data" / "mlb" / f"bets_{MLB_DATE}.json"
    saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))[0]

    validate_contract_definition(
        saved_payload, recommendation_contract, "saved_payload"
    )


# ---------------------------------------------------------------------------
# Schema-rejection sanity (proves the contract genuinely catches drift)
# ---------------------------------------------------------------------------


def test_contract_rejects_lowercase_sport_persisted_row(
    recommendation_contract: dict[str, Any],
) -> None:
    """Negative control: confirm the schema actually rejects ``sport='mlb'``."""
    from jsonschema import ValidationError

    row = build_mlb_recommendation_payload(sport="mlb")
    row.pop("side", None)
    with pytest.raises(ValidationError):
        validate_contract_definition(row, recommendation_contract, "persisted_row")


def test_contract_rejects_index_suffixed_bet_id(
    recommendation_contract: dict[str, Any],
) -> None:
    """Negative control: confirm the bet_id pattern rejects the index-suffixed
    form produced by ``BetData.generate_id`` when ticker is absent.
    """
    from jsonschema import ValidationError

    bad_id = f"MLB_{MLB_DATE}_{MLB_HOME_TEAM}_{MLB_AWAY_TEAM}_home_0"
    row = build_mlb_recommendation_payload(bet_id=bad_id)
    row.pop("side", None)
    with pytest.raises(ValidationError):
        validate_contract_definition(row, recommendation_contract, "persisted_row")


# ---------------------------------------------------------------------------
# BetRecommendation.from_dict end-to-end (real producer, contract-valid input)
# ---------------------------------------------------------------------------


def test_bet_recommendation_from_dict_emits_contract_row(
    recommendation_contract: dict[str, Any],
) -> None:
    """End-to-end: real BetRecommendation.from_dict over a contract-valid
    saved-payload yields contract-valid SQL params (after BetLoader's sport
    upper-casing)."""
    payload = _build_saved_payload(ticker=MLB_TICKER)
    context = BetContext(sport="MLB", date_str=MLB_DATE, index=0)

    recommendation = BetRecommendation.from_dict(payload, context)
    params = recommendation.to_sql_params()
    params.pop("date_str", None)

    validate_contract_definition(
        params, recommendation_contract, "persisted_row"
    )
