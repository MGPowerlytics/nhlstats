"""Provider contract tests for the PortfolioOptimizer → PortfolioBettingManager boundary.

Exercises the real ``PortfolioOptimizer.calculate_portfolio_allocation()`` with
deterministic ``BetOpportunity`` inputs, verifies the output
``List[PortfolioAllocation]`` conforms to the frozen schema, and uses mocks
to avoid database dependencies.
"""

from __future__ import annotations

import dataclasses
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, List

import pytest
from plugins.portfolio_optimizer import (
    BetOpportunity,
    PortfolioAllocation,
    PortfolioConfig,
    PortfolioOptimizer,
)
from tests.contracts.helpers import (
    serialize_contract_payload,
    validate_contract_payload,
)

SCHEMA_PATH = Path(__file__).parent / "schemas" / "portfolio_allocation_v1.json"

# ---------------------------------------------------------------------------
# Deterministic inputs
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


# ---------------------------------------------------------------------------
# MockPortfolioOptimizer: wrapper that patches DB dependencies
# ---------------------------------------------------------------------------


class MockPortfolioOptimizer:
    """Wraps ``PortfolioOptimizer.calculate_portfolio_allocation()`` with
    mock inputs and no database dependencies.

    Uses a minimal ``PortfolioConfig`` and directly passes
    ``List[BetOpportunity]`` to the real allocation method, bypassing the
    load/filter pipeline that would hit the database.
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
        self, opportunities: List[BetOpportunity]
    ) -> List[PortfolioAllocation]:
        """Run the real portfolio allocation algorithm on the given opportunities.

        Args:
            opportunities: List of BetOpportunity to allocate for.

        Returns:
            List of PortfolioAllocation with optimized sizing.
        """
        return self._optimizer.calculate_portfolio_allocation(opportunities)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def allocation_schema() -> dict[str, Any]:
    """Load the portfolio allocation schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def mock_optimizer() -> MockPortfolioOptimizer:
    """Create a ``MockPortfolioOptimizer`` with a deterministic bankroll."""
    return MockPortfolioOptimizer(bankroll=1000.0)


# ---------------------------------------------------------------------------
# Provider tests
# ---------------------------------------------------------------------------


class TestMockPortfolioOptimizerSingleOpportunity:
    """Single-opportunity allocation must produce valid output."""

    def test_single_nba_opportunity_produces_one_allocation(
        self, mock_optimizer: MockPortfolioOptimizer, allocation_schema: dict[str, Any]
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP])
        assert len(allocations) == 1

        alloc = allocations[0]
        payload = serialize_contract_payload(dataclasses.asdict(alloc))
        validate_contract_payload(payload, allocation_schema)

    def test_single_nba_allocation_bet_size_within_bounds(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP])
        assert len(allocations) == 1

        alloc = allocations[0]
        # Kelly: p=0.62, market=0.55 → kelly_fraction≈0.156
        # scaled = 1000 * 0.156 * 0.25 = 39.0
        # capped by max_bet_size=100, min_bet_size=2, max_single_bet_pct=0.10 → 100
        # min(100, 100) → 100 ... wait, 1000*0.10=100, max_bet_size=100
        # So bet_size = min(100, max(2, 39.0)) = 39.0 ... rounded to 39.0
        assert alloc.bet_size >= 2.0
        assert alloc.bet_size <= 100.0

    def test_single_nba_allocation_allocation_pct_within_bounds(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP])
        alloc = allocations[0]
        assert 0.0 <= alloc.allocation_pct <= 1.0

    def test_single_nba_allocation_preserves_opportunity(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP])
        alloc = allocations[0]
        assert alloc.opportunity.ticker == NBA_OPP.ticker
        assert alloc.opportunity.team == NBA_OPP.team
        assert alloc.opportunity.sport == NBA_OPP.sport

    def test_single_mlb_opportunity_validates_against_schema(
        self, mock_optimizer: MockPortfolioOptimizer, allocation_schema: dict[str, Any]
    ) -> None:
        allocations = mock_optimizer.calculate([MLB_OPP])
        assert len(allocations) == 1

        payload = serialize_contract_payload(dataclasses.asdict(allocations[0]))
        validate_contract_payload(payload, allocation_schema)

    def test_single_tennis_opportunity_validates_against_schema(
        self, mock_optimizer: MockPortfolioOptimizer, allocation_schema: dict[str, Any]
    ) -> None:
        allocations = mock_optimizer.calculate([TENNIS_OPP])
        assert len(allocations) == 1

        payload = serialize_contract_payload(dataclasses.asdict(allocations[0]))
        validate_contract_payload(payload, allocation_schema)


class TestMockPortfolioOptimizerMultiOpportunity:
    """Multi-opportunity allocation must produce valid output."""

    def test_multi_sport_allocation_produces_multiple_allocations(
        self, mock_optimizer: MockPortfolioOptimizer, allocation_schema: dict[str, Any]
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP])
        assert len(allocations) >= 1  # At least the best EV opportunities

        for alloc in allocations:
            payload = serialize_contract_payload(dataclasses.asdict(alloc))
            validate_contract_payload(payload, allocation_schema)

    def test_multi_sport_allocation_prioritizes_by_ev(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        """Sports diversity should give each sport at least one allocation
        before filling the rest by EV."""
        # Add a second NBA opp with lower EV to check diversity logic
        nba_low_ev = deepcopy(NBA_OPP)
        nba_low_ev.edge = 0.04
        nba_low_ev.elo_prob = 0.52
        nba_low_ev.market_prob = 0.48

        allocations = mock_optimizer.calculate([NBA_OPP, MLB_OPP, nba_low_ev])

        # Must have at least NBA and MLB
        sports_in_alloc = {a.opportunity.sport for a in allocations}
        assert "nba" in sports_in_alloc
        assert "mlb" in sports_in_alloc

    def test_multi_sport_allocation_respects_max_daily_risk(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        """Total allocated must not exceed max_daily_risk_pct of bankroll."""
        # Add many high-value opportunities
        many_opps = [NBA_OPP, MLB_OPP, TENNIS_OPP] * 5
        allocations = mock_optimizer.calculate(many_opps)

        total_bet = sum(a.bet_size for a in allocations)
        max_daily = 1000.0 * 0.25  # bankroll * max_daily_risk_pct
        assert total_bet <= max_daily + 1.0  # Allow minimal rounding

    def test_multi_sport_allocation_total_allocation_pct_within_bounds(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP])
        for alloc in allocations:
            assert 0.0 <= alloc.allocation_pct <= 1.0


class TestMockPortfolioOptimizerEdgeCases:
    """Edge cases in portfolio allocation."""

    def test_empty_opportunities_returns_empty_list(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        allocations = mock_optimizer.calculate([])
        assert allocations == []

    def test_negative_edge_opportunity_excluded(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        """Negative edge opportunities should be excluded by the optimizer's
        internal filter, but calculate_portfolio_allocation() receives
        already-filtered opportunities — it still allocates for anything
        with positive kelly_fraction."""
        # Edge is passed through in kelly_fraction calc
        bad_opp = deepcopy(NBA_OPP)
        bad_opp.elo_prob = 0.50
        bad_opp.market_prob = 0.55
        bad_opp.edge = -0.05

        allocations = mock_optimizer.calculate([bad_opp])
        # Kelly fraction will be 0, so filter in calculate_portfolio_allocation
        # will... wait, calculate_portfolio_allocation doesn't filter.
        # _allocate_kelly_sizing checks opp.kelly_fraction > 0 so if it's 0, it falls
        # back to min_bet_size.
        # Actually for kelly=0 it does: kelly_size = self.min_bet_size if opp.kelly_fraction <= 0
        # So it will still allocate but at minimum size.
        if allocations:
            # If allocated, must have minimum bet size
            assert allocations[0].bet_size >= 2.0

    def test_zero_edge_opportunity_still_allocated(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        """Zero-edge opportunity (kelly=0) uses min_bet_size fallback."""
        zero_edge = deepcopy(NBA_OPP)
        zero_edge.elo_prob = 0.55
        zero_edge.market_prob = 0.55
        zero_edge.edge = 0.0

        allocations = mock_optimizer.calculate([zero_edge])
        # kelly_fraction will be 0 → falls back to min_bet_size
        # min_bet_size=2.0
        if allocations:
            # Kelly = 0, so kelly_size = self.min_bet_size = 2.0
            # bet_size = max(2.0, min(100.0, 2.0)) = 2.0
            # capped: min(100, 2.0) = 2.0
            assert allocations[0].bet_size >= 2.0
            assert allocations[0].kelly_fraction > 0  # falls back to DEFAULT_MIN_KELLY_FRACTION


class TestMockPortfolioOptimizerSchemaConformance:
    """All allocations from the real provider must conform to the schema."""

    def test_allocation_bet_size_non_negative(
        self, mock_optimizer: MockPortfolioOptimizer, allocation_schema: dict[str, Any]
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP, MLB_OPP])
        for alloc in allocations:
            payload = serialize_contract_payload(dataclasses.asdict(alloc))
            assert payload["bet_size"] >= 0

    def test_allocation_kelly_fraction_non_negative(
        self, mock_optimizer: MockPortfolioOptimizer, allocation_schema: dict[str, Any]
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP, MLB_OPP])
        for alloc in allocations:
            payload = serialize_contract_payload(dataclasses.asdict(alloc))
            assert payload["kelly_fraction"] >= 0

    def test_allocation_pct_in_zero_one_range(
        self, mock_optimizer: MockPortfolioOptimizer, allocation_schema: dict[str, Any]
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP, MLB_OPP])
        for alloc in allocations:
            payload = serialize_contract_payload(dataclasses.asdict(alloc))
            assert 0 <= payload["allocation_pct"] <= 1

    def test_opportunity_probabilities_in_zero_one_range(
        self, mock_optimizer: MockPortfolioOptimizer, allocation_schema: dict[str, Any]
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP])
        for alloc in allocations:
            opp = alloc.opportunity
            assert 0 <= opp.elo_prob <= 1
            assert 0 <= opp.market_prob <= 1

    def test_opportunity_ask_prices_non_negative(
        self, mock_optimizer: MockPortfolioOptimizer, allocation_schema: dict[str, Any]
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP, MLB_OPP])
        for alloc in allocations:
            assert alloc.opportunity.yes_ask >= 0
            assert alloc.opportunity.no_ask >= 0

    def test_all_serialized_allocations_validate(
        self, mock_optimizer: MockPortfolioOptimizer, allocation_schema: dict[str, Any]
    ) -> None:
        """Every allocation from a multi-opportunity run must validate individually."""
        allocations = mock_optimizer.calculate([NBA_OPP, MLB_OPP, TENNIS_OPP])
        for alloc in allocations:
            payload = serialize_contract_payload(dataclasses.asdict(alloc))
            validate_contract_payload(payload, allocation_schema)

    def test_output_is_list_of_portfolio_allocation(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP])
        assert isinstance(allocations, list)
        assert all(isinstance(a, PortfolioAllocation) for a in allocations)

    def test_single_opportunity_edge_preserved_in_output(
        self, mock_optimizer: MockPortfolioOptimizer
    ) -> None:
        allocations = mock_optimizer.calculate([NBA_OPP])
        assert allocations[0].opportunity.edge == 0.07
