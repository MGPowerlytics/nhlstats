"""Unit tests for portfolio betting module.

Following TDD to fix betting errors:
1. None tickers causing 404 errors
2. Already locked markets (duplicate bet attempts)
3. Finalized markets being attempted
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import sys

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from portfolio_betting import PortfolioBettingManager
from portfolio_optimizer import BetOpportunity, PortfolioAllocation


class TestPortfolioBettingErrorHandling:
    """Test error handling in portfolio betting (TDD for production bugs)."""

    @pytest.fixture
    def mock_kalshi_client(self):
        """Create a mocked KalshiBetting client."""
        from kalshi_betting import KalshiBetting

        # Mock the initialization requirements
        with patch("kalshi_betting.serialization.load_pem_private_key"):
            with patch("builtins.open", mock_open(read_data=b"fake_key")):
                client = KalshiBetting(api_key_id="test", private_key_path="test.pem")

                # Mock methods we'll use
                client.get_balance = Mock(return_value=(1000.0, 0.0))
                client.get_market_details = Mock()
                client.place_bet = Mock()

                return client

    def test_none_ticker_returns_error(self, mock_kalshi_client):
        """Should return error for None ticker without crashing."""
        mock_kalshi_client.get_market_details.return_value = None

        manager = PortfolioBettingManager(
            kalshi_client=mock_kalshi_client, initial_bankroll=1000.0, dry_run=True
        )

        # Create allocation with None ticker
        opp = BetOpportunity(
            sport="tennis",
            ticker=None,
            bet_on="home",
            team="Player A",
            opponent="Player B",
            elo_prob=0.75,
            market_prob=0.50,
            edge=0.25,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
        )

        allocations = [
            PortfolioAllocation(
                opportunity=opp, bet_size=10.0, kelly_fraction=0.25, allocation_pct=0.01
            )
        ]

        results = manager._place_optimized_bets(allocations, "2026-01-22")

        # Should record an error, not crash
        assert results["errors"]
        assert len(results["errors"]) == 1
        assert results["errors"][0]["ticker"] is None
        assert "Cannot fetch market details" in results["errors"][0]["error"]
        assert len(results["placed_bets"]) == 0

    def test_finalized_market_is_skipped(self, mock_kalshi_client):
        """Should skip finalized markets and not attempt to place bet."""
        # Mock market details returning finalized status
        mock_kalshi_client.get_market_details.return_value = {
            "status": "finalized",
            "ticker": "KXWTAMATCH-26JAN20TJEPLI-TJE",
        }

        manager = PortfolioBettingManager(
            kalshi_client=mock_kalshi_client, initial_bankroll=1000.0, dry_run=True
        )

        opp = BetOpportunity(
            sport="tennis",
            ticker="KXWTAMATCH-26JAN20TJEPLI-TJE",
            bet_on="home",
            team="Tjen J.",
            opponent="Player B",
            elo_prob=0.72,
            market_prob=0.55,
            edge=0.17,
            confidence="HIGH",
            yes_ask=55,
            no_ask=45,
        )

        allocations = [
            PortfolioAllocation(
                opportunity=opp, bet_size=10.0, kelly_fraction=0.25, allocation_pct=0.01
            )
        ]

        results = manager._place_optimized_bets(allocations, "2026-01-22")

        # Should be skipped, not errored
        assert len(results["skipped_bets"]) == 1
        assert results["skipped_bets"][0]["ticker"] == "KXWTAMATCH-26JAN20TJEPLI-TJE"
        assert "finalized" in results["skipped_bets"][0]["reason"]
        assert len(results["errors"]) == 0
        assert len(results["placed_bets"]) == 0

    def test_closed_market_is_skipped(self, mock_kalshi_client):
        """Should skip markets that are past close_time."""
        # Mock market with close time in the past
        past_time = "2026-01-20T00:00:00Z"
        mock_kalshi_client.get_market_details.return_value = {
            "status": "active",
            "ticker": "TEST-TICKER",
            "close_time": past_time,
        }

        manager = PortfolioBettingManager(
            kalshi_client=mock_kalshi_client, initial_bankroll=1000.0, dry_run=True
        )

        opp = BetOpportunity(
            sport="tennis",
            ticker="TEST-TICKER",
            bet_on="home",
            team="Player A",
            opponent="Player B",
            elo_prob=0.70,
            market_prob=0.50,
            edge=0.20,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
        )

        allocations = [
            PortfolioAllocation(
                opportunity=opp, bet_size=10.0, kelly_fraction=0.25, allocation_pct=0.01
            )
        ]

        results = manager._place_optimized_bets(allocations, "2026-01-22")

        # Should be skipped as market is closed
        assert len(results["skipped_bets"]) == 1
        assert results["skipped_bets"][0]["ticker"] == "TEST-TICKER"
        assert "closed" in results["skipped_bets"][0]["reason"].lower()

    def test_already_locked_ticker_handled_gracefully(self, mock_kalshi_client):
        """Should handle locally locked tickers (duplicate bet prevention)."""
        # Simulate the place_bet returning None due to local lock
        mock_kalshi_client.get_market_details.return_value = {
            "status": "active",
            "ticker": "KXWTAMATCH-26JAN22JOVPAO-PAO",
            "close_time": "2026-12-31T00:00:00Z",
        }

        # Mock place_bet to return None (which happens when ticker is locked)
        mock_kalshi_client.place_bet.return_value = None

        manager = PortfolioBettingManager(
            kalshi_client=mock_kalshi_client,
            initial_bankroll=1000.0,
            dry_run=False,  # Test actual placement path
        )

        opp = BetOpportunity(
            sport="tennis",
            ticker="KXWTAMATCH-26JAN22JOVPAO-PAO",
            bet_on="home",
            team="Paolini J.",
            opponent="Player B",
            elo_prob=0.75,
            market_prob=0.50,
            edge=0.25,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
        )

        allocations = [
            PortfolioAllocation(
                opportunity=opp, bet_size=10.0, kelly_fraction=0.25, allocation_pct=0.01
            )
        ]

        results = manager._place_optimized_bets(allocations, "2026-01-22")

        # Should record as error when place_bet returns None
        assert len(results["errors"]) == 1
        assert results["errors"][0]["ticker"] == "KXWTAMATCH-26JAN22JOVPAO-PAO"
        assert "Failed to place bet" in results["errors"][0]["error"]

    def test_multiple_issues_tracked_separately(self, mock_kalshi_client):
        """Should track different error types correctly in one batch."""

        # Set up different responses for different tickers
        def mock_get_market(ticker):
            if ticker is None:
                return None
            elif ticker == "FINALIZED-TICKER":
                return {"status": "finalized"}
            elif ticker == "VALID-TICKER":
                return {"status": "active", "close_time": "2026-12-31T00:00:00Z"}
            return None

        mock_kalshi_client.get_market_details.side_effect = mock_get_market

        manager = PortfolioBettingManager(
            kalshi_client=mock_kalshi_client, initial_bankroll=1000.0, dry_run=True
        )

        allocations = [
            PortfolioAllocation(
                opportunity=BetOpportunity(
                    sport="tennis",
                    ticker=None,
                    bet_on="home",
                    team="A",
                    opponent="B",
                    elo_prob=0.75,
                    market_prob=0.50,
                    edge=0.25,
                    confidence="HIGH",
                    yes_ask=50,
                    no_ask=50,
                ),
                bet_size=10.0,
                kelly_fraction=0.25,
                allocation_pct=0.01,
            ),
            PortfolioAllocation(
                opportunity=BetOpportunity(
                    sport="tennis",
                    ticker="FINALIZED-TICKER",
                    bet_on="home",
                    team="C",
                    opponent="D",
                    elo_prob=0.70,
                    market_prob=0.45,
                    edge=0.25,
                    confidence="HIGH",
                    yes_ask=45,
                    no_ask=55,
                ),
                bet_size=10.0,
                kelly_fraction=0.25,
                allocation_pct=0.01,
            ),
            PortfolioAllocation(
                opportunity=BetOpportunity(
                    sport="tennis",
                    ticker="VALID-TICKER",
                    bet_on="home",
                    team="E",
                    opponent="F",
                    elo_prob=0.72,
                    market_prob=0.47,
                    edge=0.25,
                    confidence="HIGH",
                    yes_ask=47,
                    no_ask=53,
                ),
                bet_size=10.0,
                kelly_fraction=0.25,
                allocation_pct=0.01,
            ),
        ]

        results = manager._place_optimized_bets(allocations, "2026-01-22")

        # Should have 1 error (None ticker), 1 skipped (finalized), 1 placed (valid)
        assert len(results["errors"]) == 1
        assert len(results["skipped_bets"]) == 1
        assert len(results["placed_bets"]) == 1

        # Verify correct classification
        assert results["errors"][0]["ticker"] is None
        assert results["skipped_bets"][0]["ticker"] == "FINALIZED-TICKER"
        assert results["placed_bets"][0]["ticker"] == "VALID-TICKER"


class TestKalshiBettingNoneTicker:
    """Test KalshiBetting handles None ticker gracefully."""

    @patch("kalshi_betting.serialization.load_pem_private_key")
    @patch("builtins.open", mock_open(read_data=b"fake_key"))
    def test_get_market_details_none_ticker(self, mock_load_key):
        """get_market_details should handle None ticker without API call."""
        from kalshi_betting import KalshiBetting

        mock_load_key.return_value = MagicMock()

        betting = KalshiBetting(api_key_id="test", private_key_path="test.pem")

        # Mock _get to ensure it's not called
        betting._get = Mock()

        result = betting.get_market_details(None)

        # Should return None and not make API call
        assert result is None
        betting._get.assert_not_called()

    @patch("kalshi_betting.serialization.load_pem_private_key")
    @patch("builtins.open", mock_open(read_data=b"fake_key"))
    def test_get_market_details_empty_ticker(self, mock_load_key):
        """get_market_details should handle empty string ticker."""
        from kalshi_betting import KalshiBetting

        mock_load_key.return_value = MagicMock()

        betting = KalshiBetting(api_key_id="test", private_key_path="test.pem")

        # Mock _get to ensure it's not called
        betting._get = Mock()

        result = betting.get_market_details("")

        # Should return None and not make API call
        assert result is None
        betting._get.assert_not_called()

    @patch("kalshi_betting.serialization.load_pem_private_key")
    @patch("builtins.open", mock_open(read_data=b"fake_key"))
    def test_place_bet_none_ticker(self, mock_load_key):
        """place_bet should handle None ticker gracefully."""
        from kalshi_betting import KalshiBetting

        mock_load_key.return_value = MagicMock()

        betting = KalshiBetting(api_key_id="test", private_key_path="test.pem")

        result = betting.place_bet(ticker=None, side="yes", amount=10.0)

        # Should return None without attempting reservation or API call
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
