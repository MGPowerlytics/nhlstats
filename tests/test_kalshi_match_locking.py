import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))
from kalshi_betting import KalshiBetting


class TestKalshiMatchLocking(unittest.TestCase):
    """
    Ensures that we cannot bet on a match if we already have an open
    position on EITHER ticker associated with that match.
    """

    def setUp(self):
        # Mock the private key loading to avoid needing a real PEM file
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data=b"-----BEGIN RSA PRIVATE KEY-----\n...\n"
            ),
        ):
            with patch(
                "cryptography.hazmat.primitives.serialization.load_pem_private_key"
            ):
                self.client = KalshiBetting(
                    api_key_id="test_key", private_key_path="fake.pem", production=True
                )

    def test_get_match_prefix(self):
        """Test extraction of the unique match identifier."""
        # Standard Tennis Match
        t1 = "KXATPMATCH-26JAN20ALCHAN-ALC"
        t2 = "KXATPMATCH-26JAN20ALCHAN-HAN"
        self.assertEqual(self.client.get_match_prefix(t1), "KXATPMATCH-26JAN20ALCHAN")
        self.assertEqual(
            self.client.get_match_prefix(t1), self.client.get_match_prefix(t2)
        )

        # Challenger Match
        c1 = "KXATPCHALLENGERMATCH-26JAN20RIBBLA-RIB"
        c2 = "KXATPCHALLENGERMATCH-26JAN20RIBBLA-BLA"
        self.assertEqual(
            self.client.get_match_prefix(c1), "KXATPCHALLENGERMATCH-26JAN20RIBBLA"
        )
        self.assertEqual(
            self.client.get_match_prefix(c1), self.client.get_match_prefix(c2)
        )

    @patch("kalshi_betting.KalshiBetting.get_open_positions")
    @patch("kalshi_betting.OrderDeduper.reserve")
    def test_place_bet_blocks_if_match_open(self, mock_reserve, mock_get_positions):
        """
        Verify that place_bet skips if any ticker with the same match prefix
        is already in open positions.
        """
        # Mock local reservation success
        mock_res = MagicMock()
        mock_res.reserved = True
        mock_reserve.return_value = mock_res

        # Scenario: We have an open position on ALCARAZ (ALC)
        mock_get_positions.return_value = [
            {"ticker": "KXATPMATCH-26JAN20ALCHAN-ALC", "count": 10}
        ]

        # Attempt to bet on HANFMANN (HAN) in the SAME match
        new_ticker = "KXATPMATCH-26JAN20ALCHAN-HAN"

        # This should return None (skipping)
        result = self.client.place_bet(new_ticker, "yes", 5.0)

        self.assertIsNone(result)
        # Verify it attempted to check open positions
        mock_get_positions.assert_called_once()
        # Verify local lock was released
        mock_res.lock_path.unlink.assert_called_once()

    @patch("kalshi_betting.KalshiBetting.get_open_positions")
    @patch("kalshi_betting.OrderDeduper.reserve")
    @patch("kalshi_betting.KalshiBetting.get_market_details")
    @patch("kalshi_betting.KalshiBetting._post")
    def test_place_bet_allows_if_match_different(
        self, mock_post, mock_market, mock_reserve, mock_get_positions
    ):
        """
        Verify that place_bet allows betting on a different match.
        """
        mock_res = MagicMock()
        mock_res.reserved = True
        mock_reserve.return_value = mock_res

        # Scenario: We have an open position on ALCARAZ
        mock_get_positions.return_value = [
            {"ticker": "KXATPMATCH-26JAN20ALCHAN-ALC", "count": 10}
        ]

        # Attempt to bet on a DIFFERENT match (Djokovic)
        new_ticker = "KXATPMATCH-26JAN20MAEDJO-DJO"

        mock_market.return_value = {"yes_ask": 50}
        mock_post.return_value = {"order_id": "123"}

        result = self.client.place_bet(new_ticker, "yes", 1.0)

        self.assertIsNotNone(result)
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
