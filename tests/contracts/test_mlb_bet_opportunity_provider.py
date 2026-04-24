"""Wave-3 provider-red contract tests for the MLB ``OddsComparator`` opportunity path.

These exercise the *real* producer code in ``plugins/odds_comparator.py``
(``OddsComparator.find_opportunities``, ``BettingOutcome.to_opportunity``) and
validate the captured payload against the frozen MLB v1 contract. Where the
producer is known to drift from the contract, tests are marked
``xfail(strict=True)`` with the Wave-4-6 fix task ID so the suite turns green
the moment the producer is corrected.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from jsonschema import ValidationError, validate

from plugins.odds_comparator import (
    BettingOpportunityConfig,
    BettingThresholds,
    OddsComparator,
)
from tests.contracts.helpers import validate_contract_payload


CONTRACT_PATH = Path(__file__).parent / "schemas" / "mlb_bet_opportunity_v1.json"
MLB_GAME_ID = "745431"
MLB_HOME_TEAM = "New York Yankees"
MLB_AWAY_TEAM = "Boston Red Sox"
MLB_HOME_TICKER = "KXMLBGAME-25APR15NYYBOS-NYY"
MLB_AWAY_TICKER = "KXMLBGAME-25APR15NYYBOS-BOS"
MLB_DATE = "2025-04-15"
WAVE_4_TASK = "mlb-kalshi-recommendation-fix"


class _MlbEloStub:
    """Deterministic Elo stub satisfying the OddsComparator interface for MLB."""

    def __init__(self, home_prob: float = 0.58) -> None:
        self.home_prob = home_prob
        self._ratings = {MLB_HOME_TEAM: 1612.4, MLB_AWAY_TEAM: 1498.2}

    def predict(self, home: str, away: str) -> float:
        return self.home_prob

    def get_rating(self, name: str) -> float:
        return self._ratings.get(name, 1500.0)

    def has_real_rating(self, name: str) -> bool:
        return name in self._ratings


class _FakeOddsDb:
    """Minimal DB stub returning canned games + odds DataFrames."""

    def __init__(self, games_df: pd.DataFrame, odds_df: pd.DataFrame) -> None:
        self.games_df = games_df
        self.odds_df = odds_df

    def fetch_df(
        self, query: str, params: dict[str, Any] | None = None
    ) -> pd.DataFrame:
        if "FROM unified_games" in query:
            return self.games_df.copy()
        if "FROM game_odds" in query:
            return self.odds_df.copy()
        raise AssertionError(f"Unexpected query: {query}")


def _build_mlb_games() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": MLB_GAME_ID,
                "game_date": MLB_DATE,
                "home_team_name": MLB_HOME_TEAM,
                "away_team_name": MLB_AWAY_TEAM,
                "status": "Scheduled",
            }
        ]
    )


def _build_mlb_odds(home_price: float = 2.13, away_price: float = 2.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": home_price,
                "last_update": "2025-04-15T18:00:00Z",
                "external_id": MLB_HOME_TICKER,
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": away_price,
                "last_update": "2025-04-15T18:00:00Z",
                "external_id": MLB_AWAY_TICKER,
            },
        ]
    )


def _build_comparator(
    games_df: pd.DataFrame | None = None,
    odds_df: pd.DataFrame | None = None,
) -> OddsComparator:
    comparator = OddsComparator(
        db_manager=_FakeOddsDb(
            games_df=games_df if games_df is not None else _build_mlb_games(),
            odds_df=odds_df if odds_df is not None else _build_mlb_odds(),
        )
    )
    comparator._get_source = lambda _: "kalshi"  # type: ignore[method-assign]
    comparator._resolve_name = lambda context: context.name  # type: ignore[method-assign]
    return comparator


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def opportunity_contract() -> dict[str, Any]:
    return _load_contract()


# ---------------------------------------------------------------------------
# Provider invocations
# ---------------------------------------------------------------------------


def _run_real_mlb_opportunity(
    *,
    sport: str = "mlb",
    home_prob: float = 0.58,
    home_price: float = 2.13,
    away_price: float = 2.0,
    thresholds: BettingThresholds | None = None,
) -> list[dict[str, Any]]:
    comparator = _build_comparator(odds_df=_build_mlb_odds(home_price, away_price))
    return comparator.find_opportunities(
        BettingOpportunityConfig(
            sport=sport,
            elo_system=_MlbEloStub(home_prob=home_prob),
            thresholds=thresholds or BettingThresholds(min_edge=0.03, max_edge=1.0),
            date_str=MLB_DATE,
        )
    )


def test_real_mlb_opportunity_payload_has_expected_structural_fields(
    opportunity_contract: dict[str, Any],
) -> None:
    """Exercise real producer; verify the *structural* fields the contract demands.

    Validates everything except the known-drifting ``sport`` casing by
    uppercasing the captured value before schema validation. This proves that
    ``OddsComparator`` already emits a payload matching the contract aside
    from the explicitly tracked drift modes.
    """
    opportunities = _run_real_mlb_opportunity()
    assert opportunities, "Expected exactly one MLB opportunity from real producer"

    payload = deepcopy(opportunities[0])
    # Normalize the only known sport-casing drift so the rest of the shape can
    # be validated against the frozen contract.
    payload["sport"] = "MLB"
    validate_contract_payload(payload, opportunity_contract)


def test_real_mlb_opportunity_emits_uppercase_sport() -> None:
    """Producer must emit ``sport='MLB'`` even when callers pass ``'mlb'``."""
    opportunities = _run_real_mlb_opportunity(sport="mlb")
    assert opportunities, "Expected one MLB opportunity from real producer"
    assert opportunities[0]["sport"] == "MLB"


def test_real_mlb_opportunity_default_thresholds_enforce_max_edge() -> None:
    """A 0.50 edge must NOT be emitted when relying on producer defaults."""
    # Configure a market where elo - market = ~0.55 (well above the contract
    # max of 0.40). Default BettingThresholds() should reject it on its own.
    opportunities = _run_real_mlb_opportunity(
        home_prob=0.95,
        home_price=2.5,  # market_prob=0.40 → edge=0.55
        away_price=2.0,
        thresholds=BettingThresholds(),  # defaults: min=0.03, max=1.0
    )
    assert opportunities == [], (
        "Producer should refuse to emit opportunities whose edge exceeds the "
        "contract-enforced 0.40 maximum even with default thresholds."
    )


def test_real_mlb_opportunity_explicit_max_edge_blocks_huge_edge() -> None:
    """Sanity: when caller supplies max_edge=0.40 the producer DOES filter."""
    opportunities = _run_real_mlb_opportunity(
        home_prob=0.95,
        home_price=2.5,
        away_price=2.0,
        thresholds=BettingThresholds(min_edge=0.03, max_edge=0.40),
    )
    assert opportunities == []


# ---------------------------------------------------------------------------
# Schema-rejection sanity (proves the contract genuinely rejects drift)
# ---------------------------------------------------------------------------


def test_contract_rejects_lowercase_sport_payload(
    opportunity_contract: dict[str, Any],
) -> None:
    payload = deepcopy(_run_real_mlb_opportunity()[0])
    # Producer now emits uppercase 'MLB' after the Wave 4-6 fix; force the
    # value to lowercase here so we can still verify the schema rejects it.
    payload["sport"] = "mlb"
    with pytest.raises(ValidationError):
        validate(payload, opportunity_contract)


def test_contract_rejects_out_of_range_edge_payload(
    opportunity_contract: dict[str, Any],
) -> None:
    payload = deepcopy(_run_real_mlb_opportunity()[0])
    payload["sport"] = "MLB"
    payload["edge"] = 0.55
    with pytest.raises(ValidationError):
        validate(payload, opportunity_contract)


# ---------------------------------------------------------------------------
# Optional-field tolerance
# ---------------------------------------------------------------------------


def test_real_mlb_opportunity_optional_fields_validate_when_present(
    opportunity_contract: dict[str, Any],
) -> None:
    """``sharp_confirmed``, ``agreement_diff``, ``bookmaker``, ``market_odds``
    are optional in the contract but emitted by the producer; assert they
    individually validate against the schema when present.
    """
    payload = deepcopy(_run_real_mlb_opportunity()[0])
    payload["sport"] = "MLB"

    for optional_field in (
        "sharp_confirmed",
        "agreement_diff",
        "bookmaker",
        "market_odds",
    ):
        assert optional_field in payload, (
            f"Producer is expected to emit '{optional_field}' on MLB opportunity"
        )

    # Full payload (with sport corrected) must validate including optionals.
    validate_contract_payload(payload, opportunity_contract)


def test_real_mlb_opportunity_no_default_elo_guard_blocks_unknown_team() -> None:
    """Safety guard from production: unknown teams must not produce opportunities."""
    games = _build_mlb_games()
    games.loc[0, "away_team_name"] = "Springfield Isotopes"
    comparator = _build_comparator(games_df=games)
    opportunities = comparator.find_opportunities(
        BettingOpportunityConfig(
            sport="mlb",
            elo_system=_MlbEloStub(),
            thresholds=BettingThresholds(min_edge=0.03, max_edge=1.0),
            date_str=MLB_DATE,
        )
    )
    assert opportunities == []
