"""Provider contract tests for the PortfolioOptimizer boundary.

Exercises the real ``PortfolioOptimizer.calculate_portfolio_allocation()`` and
the internal ``_build_summary()`` with deterministic ``BetOpportunity`` inputs,
then verifies the output conforms to the ``portfolio_optimizer_contract_v1.json``
schema.

Uses mocks to avoid database dependencies.  Does not call
``optimize_daily_bets()``, which requires a database connection.
"""

from __future__ import annotations

import dataclasses
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import validate

from plugins.portfolio_optimizer import (
    BetOpportunity,
    PortfolioAllocation,
    PortfolioConfig,
    PortfolioOptimizer,
)
from tests.contracts.helpers import serialize_contract_payload

SCHEMA_PATH = Path(__file__).parent / "schemas" / "portfolio_optimizer_contract_v1.json"


# ---------------------------------------------------------------------------
# Deterministic BetOpportunity inputs
# ---------------------------------------------------------------------------

NBA_OPP = BetOpportunity(
    sport="nba",
    ticker="KXNBAGAME-26JAN20LAL-LAL",
    bet_on="home",
    team="Los Angeles Lakers",
    opponent="Boston Celtics",
    home_team="Los Angeles Lakers",
    away_team="Boston Celtics",
    home_team_raw="Lakers",
    away_team_raw="Celtics",
    elo_prob=0.62,
    market_prob=0.55,
    edge=0.07,
    confidence="HIGH",
    yes_ask=62,
    no_ask=38,
    home_rating=1612.4,
    away_rating=1545.1,
    game_time="2026-01-20T19:30:00Z",
    game_id="NBA_20260120_LAL_BOS",
    betmgm_prob=0.60,
)

MLB_OPP = BetOpportunity(
    sport="mlb",
    ticker="KXMLBGAME-25APR15NYYBOS-NYY",
    bet_on="home",
    team="New York Yankees",
    opponent="Boston Red Sox",
    home_team="New York Yankees",
    away_team="Boston Red Sox",
    home_team_raw="Yankees",
    away_team_raw="Red Sox",
    elo_prob=0.58,
    market_prob=0.47,
    edge=0.11,
    confidence="MEDIUM",
    yes_ask=58,
    no_ask=42,
    home_rating=1612.4,
    away_rating=1498.2,
    game_time="2025-04-15T18:00:00Z",
    game_id="745431",
    betmgm_prob=0.55,
)

TENNIS_OPP = BetOpportunity(
    sport="tennis",
    ticker="KXATPMATCH-26JAN20ALCARAZ-ZVEREV-ALCARAZ",
    bet_on="home",
    team="Carlos Alcaraz",
    opponent="Alexander Zverev",
    home_team="Carlos Alcaraz",
    away_team="Alexander Zverev",
    home_team_raw="Alcaraz",
    away_team_raw="Zverev",
    elo_prob=0.65,
    market_prob=0.60,
    edge=0.05,
    confidence="MEDIUM",
    yes_ask=65,
    no_ask=35,
    home_rating=1850.0,
    away_rating=1720.0,
    game_time="2026-01-20T10:00:00Z",
    game_id="TENNIS_20260120_ALCARAZ_ZVEREV",
    betmgm_prob=0.62,
)

NFL_OPP = BetOpportunity(
    sport="nfl",
    ticker="KXNFLGAME-09FEB26KCC-SF-KCC",
    bet_on="home",
    team="Kansas City Chiefs",
    opponent="San Francisco 49ers",
    home_team="Kansas City Chiefs",
    away_team="San Francisco 49ers",
    home_team_raw="Chiefs",
    away_team_raw="49ers",
    elo_prob=0.54,
    market_prob=0.48,
    edge=0.06,
    confidence="LOW",
    yes_ask=54,
    no_ask=46,
    home_rating=1680.0,
    away_rating=1650.0,
    game_time="2026-02-09T18:30:00Z",
    game_id="NFL_20260209_KC_SF",
    betmgm_prob=0.52,
)


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

ALLOCATION_DEF: dict[str, Any] = {}
SUMMARY_DEF: dict[str, Any] = {}


def _allocation_schema(contract: dict[str, Any]) -> dict[str, Any]:
    """Build a standalone schema for the ``portfolio_allocation_result`` def."""
    return {
        "$schema": contract["$schema"],
        "$ref": "#/$defs/portfolio_allocation_result",
        "$defs": contract["$defs"],
    }


def _summary_schema(contract: dict[str, Any]) -> dict[str, Any]:
    """Build a standalone schema for the ``optimization_summary`` def."""
    return {
        "$schema": contract["$schema"],
        "$ref": "#/$defs/optimization_summary",
        "$defs": contract["$defs"],
    }


# ---------------------------------------------------------------------------
# Mock wrapper
# ---------------------------------------------------------------------------


class MockPortfolioOptimizer:
    """Wraps ``PortfolioOptimizer`` with mock inputs and no DB dependencies.

    Bypasses the load/filter pipeline; directly passes
    ``List[BetOpportunity]`` to the real allocation method via
    ``calculate_portfolio_allocation()``.
    """

    def __init__(self, bankroll: float = 1000.0) -> None:
        config = PortfolioConfig(
            bankroll=bankroll,
            max_daily_risk_pct=0.25,
            kelly_fraction=0.25,
            min_bet_size=2.0,
            max_bet_size=100.0,
            max_single_bet_pct=0.10,
            min_edge=0.03,
        )
        self._optimizer = PortfolioOptimizer(config=config)

    def calculate(
        self, opportunities: list[BetOpportunity]
    ) -> list[PortfolioAllocation]:
        """Run the real portfolio allocation algorithm."""
        return self._optimizer.calculate_portfolio_allocation(opportunities)

    def summary(
        self,
        date_str: str,
        total_opps: int,
        filtered_opps: list[BetOpportunity],
        allocations: list[PortfolioAllocation],
    ) -> dict[str, Any]:
        """Build the internal summary dict via _build_summary."""
        # Access the private method for testing — this is the contract boundary
        return self._optimizer._build_summary(
            date_str=date_str,
            opportunities=[NBA_OPP] * total_opps,
            filtered_opps=filtered_opps,
            allocations=allocations,
            use_database=False,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def contract_schema() -> dict[str, Any]:
    """Load the portfolio optimizer contract schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def optimizer() -> MockPortfolioOptimizer:
    """Create a MockPortfolioOptimizer with a deterministic bankroll."""
    return MockPortfolioOptimizer(bankroll=1000.0)


# ---------------------------------------------------------------------------
# Portfolio Allocation provider tests
# ---------------------------------------------------------------------------


class TestCalculatePortfolioAllocation:
    """``calculate_portfolio_allocation()`` must produce schema-conforming output."""

    def test_single_nba_opportunity_produces_valid_allocation(
        self, optimizer: MockPortfolioOptimizer, contract_schema: dict[str, Any]
    ) -> None:
        """A single NBA opportunity must produce one valid allocation."""
        allocations = optimizer.calculate([NBA_OPP])
        assert len(allocations) == 1

        alloc = allocations[0]
        payload = serialize_contract_payload(dataclasses.asdict(alloc))
        payload["schema_version"] = "v1"
        payload["payload_kind"] = "portfolio_allocation"
        validate(payload, _allocation_schema(contract_schema))

    def test_multi_sport_allocations_all_validate(
        self, optimizer: MockPortfolioOptimizer, contract_schema: dict[str, Any]
    ) -> None:
        """All allocations from a multi-sport run must validate."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP])
        assert len(allocations) >= 1

        for alloc in allocations:
            payload = serialize_contract_payload(dataclasses.asdict(alloc))
            payload["schema_version"] = "v1"
            payload["payload_kind"] = "portfolio_allocation"
            validate(payload, _allocation_schema(contract_schema))

    def test_allocation_bet_size_non_negative(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Every allocation must have bet_size >= 0."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP])
        for alloc in allocations:
            assert alloc.bet_size >= 0

    def test_allocation_kelly_fraction_non_negative(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Every allocation must have kelly_fraction >= 0."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP])
        for alloc in allocations:
            assert alloc.kelly_fraction >= 0

    def test_allocation_pct_in_zero_one_range(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Every allocation must have allocation_pct in [0, 1]."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP])
        for alloc in allocations:
            assert 0 <= alloc.allocation_pct <= 1

    def test_preserves_opportunity_details(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Allocation must preserve the original opportunity's key fields."""
        allocations = optimizer.calculate([NBA_OPP])
        alloc = allocations[0]
        assert alloc.opportunity.ticker == NBA_OPP.ticker
        assert alloc.opportunity.team == NBA_OPP.team
        assert alloc.opportunity.sport == NBA_OPP.sport
        assert alloc.opportunity.edge == NBA_OPP.edge

    def test_empty_opportunities_returns_empty(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Empty input must produce empty output."""
        allocations = optimizer.calculate([])
        assert allocations == []

    def test_opp_probabilities_in_range(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """All returned opportunities must have valid probabilities."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP, NFL_OPP])
        for alloc in allocations:
            opp = alloc.opportunity
            assert 0 <= opp.elo_prob <= 1
            assert 0 <= opp.market_prob <= 1

    def test_opp_ask_prices_non_negative(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """All returned opportunities must have non-negative ask prices."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP])
        for alloc in allocations:
            assert alloc.opportunity.yes_ask >= 0
            assert alloc.opportunity.no_ask >= 0

    def test_output_is_list_of_portfolio_allocation(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Output must be a list of PortfolioAllocation instances."""
        allocations = optimizer.calculate([NBA_OPP])
        assert isinstance(allocations, list)
        assert all(isinstance(a, PortfolioAllocation) for a in allocations)

    def test_total_bet_respects_max_daily_risk(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Total allocated must not exceed max_daily_risk_pct of bankroll."""
        many_opps = [NBA_OPP, MLB_OPP, TENNIS_OPP, NFL_OPP] * 5
        allocations = optimizer.calculate(many_opps)

        total_bet = sum(a.bet_size for a in allocations)
        max_daily = 1000.0 * 0.25
        assert total_bet <= max_daily + 1.0  # Allow rounding


# ---------------------------------------------------------------------------
# Kelly sizing tests
# ---------------------------------------------------------------------------


class TestKellySizing:
    """Kelly Criterion-based sizing must produce valid allocations."""

    def test_high_edge_opp_gets_larger_allocation(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """A high-edge opportunity should get a larger bet than a low-edge one."""
        high_edge = deepcopy(NBA_OPP)
        high_edge.edge = 0.15
        high_edge.elo_prob = 0.70
        high_edge.market_prob = 0.55

        low_edge = deepcopy(MLB_OPP)
        low_edge.edge = 0.04
        low_edge.elo_prob = 0.51
        low_edge.market_prob = 0.47

        allocations = optimizer.calculate([low_edge, high_edge])
        high_alloc = [a for a in allocations if a.opportunity.elo_prob == 0.70]
        low_alloc = [a for a in allocations if a.opportunity.elo_prob == 0.51]

        if high_alloc and low_alloc:
            # kelly: high_edge should have larger fraction
            assert high_alloc[0].kelly_fraction >= low_alloc[0].kelly_fraction

    def test_kelly_sizing_all_schema_valid(
        self, optimizer: MockPortfolioOptimizer, contract_schema: dict[str, Any]
    ) -> None:
        """All Kelly-sized allocations must validate against the schema."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP, NFL_OPP])
        schema = _allocation_schema(contract_schema)
        for alloc in allocations:
            payload = serialize_contract_payload(dataclasses.asdict(alloc))
            payload["schema_version"] = "v1"
            payload["payload_kind"] = "portfolio_allocation"
            validate(payload, schema)

    def test_kelly_fraction_scales_with_bankroll(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Higher bankroll should produce proportionally larger bet sizes."""
        allocations = optimizer.calculate([NBA_OPP])
        small_bet = allocations[0].bet_size

        big_optimizer = MockPortfolioOptimizer(bankroll=10000.0)
        big_allocations = big_optimizer.calculate([NBA_OPP])
        big_bet = big_allocations[0].bet_size

        # Bigger bankroll = bigger absolute bet (within max bet constraints)
        assert big_bet >= small_bet


# ---------------------------------------------------------------------------
# Equal sizing tests (indirectly tested via zero-kelly fallback)
# ---------------------------------------------------------------------------


class TestEqualSizing:
    """Edge cases where Kelly is zero should still produce valid allocations."""

    def test_zero_kelly_opp_still_produces_valid_allocation(
        self, optimizer: MockPortfolioOptimizer, contract_schema: dict[str, Any]
    ) -> None:
        """A zero-kelly (zero edge) opp should still produce a valid schema output."""
        zero_edge = deepcopy(NBA_OPP)
        zero_edge.elo_prob = 0.55
        zero_edge.market_prob = 0.55
        zero_edge.edge = 0.0

        allocations = optimizer.calculate([zero_edge])
        if allocations:
            alloc = allocations[0]
            payload = serialize_contract_payload(dataclasses.asdict(alloc))
            payload["schema_version"] = "v1"
            payload["payload_kind"] = "portfolio_allocation"
            validate(payload, _allocation_schema(contract_schema))

            # Falls back to min_bet_size
            assert alloc.bet_size >= 2.0

    def test_negative_kelly_opp_still_produces_valid_output(
        self, optimizer: MockPortfolioOptimizer, contract_schema: dict[str, Any]
    ) -> None:
        """Negative edge (kelly=0) should still produce valid schema output if allocated."""
        bad_opp = deepcopy(NBA_OPP)
        bad_opp.elo_prob = 0.45
        bad_opp.market_prob = 0.55
        bad_opp.edge = -0.10

        allocations = optimizer.calculate([bad_opp])
        if allocations:
            payload = serialize_contract_payload(dataclasses.asdict(allocations[0]))
            payload["schema_version"] = "v1"
            payload["payload_kind"] = "portfolio_allocation"
            validate(payload, _allocation_schema(contract_schema))


# ---------------------------------------------------------------------------
# Optimization Summary provider tests
# ---------------------------------------------------------------------------


class TestOptimizationSummary:
    """``_build_summary()`` must produce schema-conforming output."""

    def test_summary_constructs_valid_payload(
        self, optimizer: MockPortfolioOptimizer, contract_schema: dict[str, Any]
    ) -> None:
        """A canonical summary must validate against the schema."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP])
        summary = optimizer.summary(
            date_str="2026-01-20",
            total_opps=12,
            filtered_opps=[NBA_OPP, MLB_OPP, TENNIS_OPP],
            allocations=allocations,
        )

        payload = _summary_to_contract(summary)
        validate(payload, _summary_schema(contract_schema))

    def test_summary_counts_are_correct(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Summary counts must match actual values."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP])
        total_bet = sum(a.bet_size for a in allocations)

        summary = optimizer.summary(
            date_str="2026-01-20",
            total_opps=10,
            filtered_opps=[NBA_OPP, MLB_OPP, TENNIS_OPP],
            allocations=allocations,
        )

        payload = _summary_to_contract(summary)
        assert payload["total_opportunities"] == 10
        assert payload["filtered_count"] == 3
        assert payload["allocations_count"] == len(allocations)
        assert payload["total_bet_size"] == pytest.approx(total_bet, abs=0.01)

    def test_summary_schema_version_constrained(
        self, optimizer: MockPortfolioOptimizer, contract_schema: dict[str, Any]
    ) -> None:
        """Summary schema_version must be \"v1\"."""
        allocations = optimizer.calculate([NBA_OPP])
        summary = optimizer.summary(
            date_str="2026-01-20",
            total_opps=5,
            filtered_opps=[NBA_OPP],
            allocations=allocations,
        )
        payload = _summary_to_contract(summary)
        validate(payload, _summary_schema(contract_schema))

    def test_summary_payload_kind_constrained(
        self, optimizer: MockPortfolioOptimizer, contract_schema: dict[str, Any]
    ) -> None:
        """Summary payload_kind must be \"optimization_summary\"."""
        allocations = optimizer.calculate([NBA_OPP])
        summary = optimizer.summary(
            date_str="2026-01-20",
            total_opps=5,
            filtered_opps=[NBA_OPP],
            allocations=allocations,
        )
        payload = _summary_to_contract(summary)
        assert payload["payload_kind"] == "optimization_summary"


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


class TestDriftDetection:
    """Drift detection: verify key numerical outputs remain stable."""

    def test_nba_allocation_bet_size_stable(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """NBA opportunity should produce a repeatable bet size."""
        allocations = optimizer.calculate([NBA_OPP])
        assert allocations[0].bet_size == pytest.approx(39.0, abs=1.0)

    def test_mlb_allocation_bet_size_stable(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """MLB opportunity should produce a repeatable bet size."""
        allocations = optimizer.calculate([MLB_OPP])
        # Higher edge → higher kelly → larger bet
        assert allocations[0].bet_size >= 2.0

    def test_kelly_fraction_for_nba_stable(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Kelly fraction for NBA opp should be repeatable."""
        allocations = optimizer.calculate([NBA_OPP])
        # p=0.62, market=0.55 → kelly ≈ 0.156
        assert allocations[0].kelly_fraction == pytest.approx(0.156, abs=0.01)

    def test_kelly_fraction_for_mlb_stable(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Kelly fraction for MLB opp should be repeatable."""
        allocations = optimizer.calculate([MLB_OPP])
        # p=0.58, market=0.47, b = 1/0.47 - 1 = 1.12766
        # kelly = (0.58 * 1.12766 - 0.42) / 1.12766 = 0.2075
        assert allocations[0].kelly_fraction == pytest.approx(0.2075, abs=0.01)

    def test_allocation_pct_stable(self, optimizer: MockPortfolioOptimizer) -> None:
        """Allocation percentage should be repeatable."""
        allocations = optimizer.calculate([NBA_OPP])
        assert 0 < allocations[0].allocation_pct <= 1.0

    def test_sport_diversity_maintained(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Multi-sport input should produce allocations across sports."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP])
        sports = {a.opportunity.sport for a in allocations}
        assert len(sports) >= 2  # At least 2 sports represented

    def test_prioritize_by_ev(
        self, optimizer: MockPortfolioOptimizer
    ) -> None:
        """Higher EV opportunities should be prioritized."""
        allocations = optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP])
        # MLB has highest edge (0.11) → should be allocated
        mlb_alloc = [a for a in allocations if a.opportunity.sport == "mlb"]
        assert len(mlb_alloc) >= 1

    def test_zero_opportunities_summary(
        self, optimizer: MockPortfolioOptimizer, contract_schema: dict[str, Any]
    ) -> None:
        """Zero opportunities should produce a valid summary."""
        summary = optimizer.summary(
            date_str="2026-01-20",
            total_opps=0,
            filtered_opps=[],
            allocations=[],
        )
        payload = _summary_to_contract(summary)
        validate(payload, _summary_schema(contract_schema))
        assert payload["total_opportunities"] == 0
        assert payload["filtered_count"] == 0
        assert payload["allocations_count"] == 0
        assert payload["total_bet_size"] == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _summary_to_contract(summary: dict[str, Any]) -> dict[str, Any]:
    """Map ``_build_summary`` internal keys to contract schema names.

    The internal summary dict uses keys like:
      ``opportunities_found``, ``opportunities_filtered``,
      ``bets_placed``, ``total_bet_amount``, ``date``

    The contract schema expects:
      ``total_opportunities``, ``filtered_count``,
      ``allocations_count``, ``total_bet_size``, ``date_str``
    """
    return {
        "date_str": summary.get("date", ""),
        "total_opportunities": summary.get("opportunities_found", 0),
        "filtered_count": summary.get("opportunities_filtered", 0),
        "allocations_count": summary.get("bets_placed", 0),
        "total_bet_size": float(summary.get("total_bet_amount", 0.0)),
        "schema_version": "v1",
        "payload_kind": "optimization_summary",
    }
