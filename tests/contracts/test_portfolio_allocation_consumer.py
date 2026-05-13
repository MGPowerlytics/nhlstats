"""Consumer contract tests for the PortfolioOptimizer → PortfolioBettingManager boundary.

Validates that the ``PortfolioAllocation`` dataclass serializes to match the
frozen portfolio allocation schema, and that the ``BetOpportunity`` computed
properties (``kelly_fraction``, ``expected_value``) produce correct values.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from plugins.portfolio_optimizer import BetOpportunity, PortfolioAllocation
from tests.contracts.fixtures.portfolio_samples import (
    build_portfolio_allocation,
)
from tests.contracts.helpers import (
    serialize_contract_payload,
    validate_contract_payload,
)

SCHEMA_PATH = Path(__file__).parent / "schemas" / "portfolio_allocation_v1.json"


@pytest.fixture(scope="module")
def allocation_schema() -> dict[str, Any]:
    """Load the portfolio allocation schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Dataclass → dict serialization conformance
# ---------------------------------------------------------------------------


class TestPortfolioAllocationSerialization:
    """``PortfolioAllocation`` dataclass must serialize to match the schema."""

    def test_portfolio_allocation_dataclass_serializes_to_schema(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        """Build a real PortfolioAllocation from a BetOpportunity and verify
        the serialized dict matches the frozen schema."""
        opp = BetOpportunity(
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
        alloc = PortfolioAllocation(
            opportunity=opp,
            bet_size=25.0,
            kelly_fraction=0.1139,
            allocation_pct=0.025,
        )

        payload = serialize_contract_payload(dataclasses.asdict(alloc))
        # Validate the full shape
        validate_contract_payload(payload, allocation_schema)

        # Assert specific field values
        assert payload["bet_size"] == 25.0
        assert payload["kelly_fraction"] == pytest.approx(0.1139, abs=0.0001)
        assert payload["allocation_pct"] == 0.025
        assert payload["opportunity"]["sport"] == "nba"
        assert payload["opportunity"]["ticker"] == "KXNBAGAME-26JAN20LAL-LAL"
        assert payload["opportunity"]["edge"] == 0.07

    def test_serialized_allocation_includes_all_required_fields(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        """The serialized dict must contain all schema-required fields."""
        opp = BetOpportunity(
            sport="mlb",
            ticker="KXMLBGAME-25APR15NYYBOS-NYY",
            bet_on="home",
            team="New York Yankees",
            opponent="Boston Red Sox",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
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
        alloc = PortfolioAllocation(
            opportunity=opp, bet_size=20.0, kelly_fraction=0.1038, allocation_pct=0.02
        )

        payload = serialize_contract_payload(dataclasses.asdict(alloc))

        # Every required top-level field must be present
        for field in ("bet_size", "kelly_fraction", "allocation_pct", "opportunity"):
            assert field in payload, f"Missing required field: {field}"

        # Every required opportunity field must be present
        required_opp_fields = [
            "sport",
            "ticker",
            "bet_on",
            "team",
            "opponent",
            "home_team",
            "away_team",
            "elo_prob",
            "market_prob",
            "edge",
            "confidence",
            "yes_ask",
            "no_ask",
            "home_rating",
            "away_rating",
        ]
        for field in required_opp_fields:
            assert field in payload["opportunity"], (
                f"Missing required opportunity field: {field}"
            )

    def test_canonical_portfolio_allocation_fixture_matches_schema(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        """The canonical fixture dict must validate against the schema."""
        validate_contract_payload(build_portfolio_allocation(), allocation_schema)

    def test_portfolio_allocation_rejects_extra_top_level_field(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        """additionalProperties: false must block unknown top-level fields."""
        payload = build_portfolio_allocation()
        payload["unknown_field"] = "x"
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)

    def test_portfolio_allocation_rejects_missing_bet_size(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_allocation()
        del payload["bet_size"]
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)

    def test_portfolio_allocation_rejects_missing_opportunity(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_allocation()
        del payload["opportunity"]
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)

    def test_portfolio_allocation_rejects_negative_bet_size(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_allocation(bet_size=-5.0)
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)

    def test_portfolio_allocation_rejects_negative_kelly_fraction(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_allocation(kelly_fraction=-0.1)
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)

    def test_portfolio_allocation_rejects_allocation_pct_gt_one(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_allocation(allocation_pct=1.5)
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)

    def test_opportunity_rejects_extra_field(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_allocation()
        payload["opportunity"]["unknown_opp_field"] = "y"
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)

    def test_opportunity_rejects_missing_required_field(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_allocation()
        del payload["opportunity"]["sport"]
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)

    def test_opportunity_rejects_missing_ticker(
        self, allocation_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_allocation()
        del payload["opportunity"]["ticker"]
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)

    @pytest.mark.parametrize("bad_confidence", ["High", "medium", "low", "", "UNKNOWN"])
    def test_opportunity_rejects_invalid_confidence(
        self, allocation_schema: dict[str, Any], bad_confidence: str
    ) -> None:
        payload = build_portfolio_allocation(opportunity__confidence=bad_confidence)
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)

    @pytest.mark.parametrize("bad_prob", [-0.1, 1.1, 2.0])
    def test_opportunity_rejects_out_of_range_elo_prob(
        self, allocation_schema: dict[str, Any], bad_prob: float
    ) -> None:
        payload = build_portfolio_allocation(opportunity__elo_prob=bad_prob)
        with pytest.raises(ValidationError):
            validate_contract_payload(payload, allocation_schema)


# ---------------------------------------------------------------------------
# BetOpportunity computed property correctness
# ---------------------------------------------------------------------------


class TestBetOpportunityKellyFraction:
    """``BetOpportunity.kelly_fraction`` must compute correctly."""

    def test_kelly_fraction_zero_when_market_prob_zero(self) -> None:
        """No edge means no bet — market_prob=0 yields kelly_fraction=0."""
        opp = BetOpportunity(
            sport="nba",
            ticker="TEST",
            bet_on="home",
            team="A",
            opponent="B",
            market_prob=0.0,
            elo_prob=0.5,
        )
        assert opp.kelly_fraction == 0.0

    def test_kelly_fraction_zero_when_market_prob_one(self) -> None:
        """Certain market (prob=1) yields no bet."""
        opp = BetOpportunity(
            sport="nba",
            ticker="TEST",
            bet_on="home",
            team="A",
            opponent="B",
            market_prob=1.0,
            elo_prob=0.99,
        )
        assert opp.kelly_fraction == 0.0

    def test_kelly_fraction_positive_on_edge(self) -> None:
        """Positive edge yields a positive Kelly fraction."""
        opp = BetOpportunity(
            sport="nba",
            ticker="TEST",
            bet_on="home",
            team="A",
            opponent="B",
            elo_prob=0.62,
            market_prob=0.55,
        )
        # p=0.62, market=0.55, b = 1/0.55 - 1 = 0.818...
        # kelly = (0.62 * 0.818 - 0.38) / 0.818 = 0.6207... - 0.4646... = 0.1561... ~ 0.156
        kelly = opp.kelly_fraction
        assert kelly > 0
        assert pytest.approx(kelly, 0.01) == 0.156

    def test_kelly_fraction_clamped_at_zero(self) -> None:
        """Negative edge (p < market) yields kelly_fraction=0."""
        opp = BetOpportunity(
            sport="nba",
            ticker="TEST",
            bet_on="home",
            team="A",
            opponent="B",
            elo_prob=0.45,
            market_prob=0.55,
        )
        assert opp.kelly_fraction == 0.0

    def test_kelly_fraction_zero_on_equal_probs(self) -> None:
        """Equal probabilities yield no edge → kelly≈0 (floating point)."""
        opp = BetOpportunity(
            sport="nba",
            ticker="TEST",
            bet_on="home",
            team="A",
            opponent="B",
            elo_prob=0.55,
            market_prob=0.55,
        )
        assert opp.kelly_fraction == pytest.approx(0.0, abs=1e-15)

    def test_kelly_fraction_reproducible_from_fixture_values(self) -> None:
        """Verify the fixture's kelly_fraction matches the computed value."""
        opp = BetOpportunity(
            sport="nba",
            ticker="KXNBAGAME-26JAN20LAL-LAL",
            bet_on="home",
            team="Los Angeles Lakers",
            opponent="Boston Celtics",
            home_team="Los Angeles Lakers",
            away_team="Boston Celtics",
            elo_prob=0.62,
            market_prob=0.55,
            edge=0.07,
            confidence="HIGH",
            yes_ask=62,
            no_ask=38,
            home_rating=1612.4,
            away_rating=1545.1,
        )
        # p=0.62, b = 1/0.55 - 1 = 0.81818...
        # kelly = (0.62 * 0.81818 - 0.38) / 0.81818
        # kelly = (0.50727 - 0.38) / 0.81818 = 0.12727 / 0.81818 = 0.15555...
        assert opp.kelly_fraction > 0
        assert opp.kelly_fraction == pytest.approx(0.15556, abs=0.001)


class TestBetOpportunityExpectedValue:
    """``BetOpportunity.expected_value`` must compute correctly."""

    def test_expected_value_positive_on_edge(self) -> None:
        """Positive edge yields positive expected value."""
        opp = BetOpportunity(
            sport="nba",
            ticker="TEST",
            bet_on="home",
            team="A",
            opponent="B",
            elo_prob=0.62,
            market_prob=0.55,
            edge=0.07,
        )
        # EV = edge / market_prob = 0.07 / 0.55 = 0.12727...
        assert opp.expected_value == pytest.approx(0.12727, abs=0.001)

    def test_expected_value_zero_when_edge_zero(self) -> None:
        """Zero edge yields zero expected value."""
        opp = BetOpportunity(
            sport="nba",
            ticker="TEST",
            bet_on="home",
            team="A",
            opponent="B",
            elo_prob=0.55,
            market_prob=0.55,
            edge=0.0,
        )
        assert opp.expected_value == 0.0

    def test_expected_value_negative_on_negative_edge(self) -> None:
        """Negative edge yields negative expected value."""
        opp = BetOpportunity(
            sport="nba",
            ticker="TEST",
            bet_on="home",
            team="A",
            opponent="B",
            elo_prob=0.50,
            market_prob=0.55,
            edge=-0.05,
        )
        assert opp.expected_value < 0
        assert opp.expected_value == pytest.approx(-0.09091, abs=0.001)

    def test_expected_value_reproducible_from_fixture_values(self) -> None:
        """Verify the fixture's implied EV matches the computed value."""
        opp = BetOpportunity(
            sport="nba",
            ticker="KXNBAGAME-26JAN20LAL-LAL",
            bet_on="home",
            team="Los Angeles Lakers",
            opponent="Boston Celtics",
            home_team="Los Angeles Lakers",
            away_team="Boston Celtics",
            elo_prob=0.62,
            market_prob=0.55,
            edge=0.07,
            confidence="HIGH",
            yes_ask=62,
            no_ask=38,
            home_rating=1612.4,
            away_rating=1545.1,
        )
        expected = opp.expected_value
        assert expected > 0
        assert expected == pytest.approx(0.12727, abs=0.001)
