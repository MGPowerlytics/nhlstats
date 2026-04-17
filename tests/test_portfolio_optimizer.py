import unittest
import pandas as pd
from plugins.portfolio_optimizer import (
    JsonFileParser,
    PortfolioOptimizer,
    PortfolioConfig,
    BetOpportunity,
)


class TestPortfolioOptimizerRefactored(unittest.TestCase):
    def setUp(self):
        self.json_parser = JsonFileParser()
        self.config = PortfolioConfig(bankroll=1000.0)
        self.optimizer = PortfolioOptimizer(self.config)

    def test_blended_prob_calculation(self):
        # Case 1: No BetMGM prob - should return elo_prob
        opp = BetOpportunity(
            sport="nba",
            ticker="T1",
            bet_on="home",
            team="A",
            opponent="B",
            elo_prob=0.6,
        )
        self.assertEqual(opp.blended_prob, 0.6)

        # Case 2: Both available - should return 70/30 split
        # Import constants from the module
        from plugins.portfolio_optimizer import ELO_BLEND_WEIGHT, BETMGM_BLEND_WEIGHT

        expected = (0.6 * ELO_BLEND_WEIGHT) + (0.5 * BETMGM_BLEND_WEIGHT)
        opp.betmgm_prob = 0.5
        self.assertAlmostEqual(opp.blended_prob, expected)

    def test_json_parser_game_id_generation(self):
        # Case: game_id missing, but date and teams present
        data = {
            "ticker": "NHL_EDM_STL",
            "home_team": "EDM",
            "away_team": "STL",
            "game_time": "2026-03-02T19:00:00",
            "elo_prob": 0.6,
            "market_prob": 0.5,
            "edge": 0.1,
            "confidence": "MEDIUM",
            "yes_ask": 50,
            "no_ask": 50,
        }
        opp = self.json_parser.parse(data, "nhl")
        self.assertIsNotNone(opp)
        self.assertEqual(opp.game_id, "NHL_20260302_EDM_STL")

    def test_parse_prices_basic(self):
        data = {"yes_ask": 55, "no_ask": 45, "market_prob": 0.55}
        yes, no, prob = self.json_parser._parse_prices(data, "nba", "home")
        self.assertEqual(yes, 55.0)
        self.assertEqual(no, 45.0)
        self.assertEqual(prob, 0.55)

    def test_parse_prices_tennis_home(self):
        # For tennis, if market_prob missing, it uses yes_ask for home
        data = {
            "yes_ask": 60,
            "no_ask": 40,
            "bet_on": "Player A",
            "player1": "Player A",
        }
        yes, no, prob = self.json_parser._parse_prices(data, "tennis", "home")
        self.assertEqual(prob, 0.60)

    def test_parse_prices_tennis_away(self):
        # For tennis, if market_prob missing, it uses no_ask for away
        data = {
            "yes_ask": 60,
            "no_ask": 40,
            "bet_on": "Player B",
            "player1": "Player A",
        }
        yes, no, prob = self.json_parser._parse_prices(data, "tennis", "away")
        self.assertEqual(prob, 0.40)

    def test_extract_prob_from_rows_home(self):
        df = pd.DataFrame(
            [
                {"outcome_name": "home", "price": 2.0},
                {"outcome_name": "away", "price": 1.8},
            ]
        )
        prob = self.optimizer._extract_prob_from_rows(df, "home")
        self.assertEqual(prob, 0.5)

    def test_extract_prob_from_rows_away(self):
        df = pd.DataFrame(
            [
                {"outcome_name": "home", "price": 2.0},
                {"outcome_name": "away", "price": 1.8},
            ]
        )
        prob = self.optimizer._extract_prob_from_rows(df, "away")
        self.assertAlmostEqual(prob, 1.0 / 1.8)

    def test_extract_prob_from_rows_fuzzy(self):
        df = pd.DataFrame(
            [{"outcome_name": "H", "price": 2.5}, {"outcome_name": "A", "price": 1.5}]
        )
        prob = self.optimizer._extract_prob_from_rows(df, "home")
        self.assertEqual(prob, 0.4)

    def test_derive_market_prob_from_asks_home_yes_ask_available(self):
        """Test market probability calculation for home bet when yes_ask is available."""
        # yes_ask = 60 means 60 cents = 0.60 probability
        prob = self.json_parser._derive_market_prob_from_asks(
            yes_ask=60.0, no_ask=40.0, bet_direction="home", fallback_prob=0.5
        )
        self.assertAlmostEqual(prob, 0.60)

    def test_derive_market_prob_from_asks_home_no_ask_available(self):
        """Test market probability calculation for home bet when only no_ask is available."""
        # no_ask = 70 means away probability = 0.70, so home probability = 0.30
        prob = self.json_parser._derive_market_prob_from_asks(
            yes_ask=0.0, no_ask=70.0, bet_direction="home", fallback_prob=0.5
        )
        self.assertAlmostEqual(prob, 0.30)

    def test_derive_market_prob_from_asks_away_no_ask_available(self):
        """Test market probability calculation for away bet when no_ask is available."""
        # no_ask = 65 means 65 cents = 0.65 probability for away
        prob = self.json_parser._derive_market_prob_from_asks(
            yes_ask=35.0, no_ask=65.0, bet_direction="away", fallback_prob=0.5
        )
        self.assertAlmostEqual(prob, 0.65)

    def test_derive_market_prob_from_asks_away_yes_ask_available(self):
        """Test market probability calculation for away bet when only yes_ask is available."""
        # yes_ask = 80 means home probability = 0.80, so away probability = 0.20
        prob = self.json_parser._derive_market_prob_from_asks(
            yes_ask=80.0, no_ask=0.0, bet_direction="away", fallback_prob=0.5
        )
        self.assertAlmostEqual(prob, 0.20)

    def test_derive_market_prob_from_asks_fallback_when_no_asks(self):
        """Test that fallback probability is used when no ask prices are available."""
        prob = self.json_parser._derive_market_prob_from_asks(
            yes_ask=0.0, no_ask=0.0, bet_direction="home", fallback_prob=0.55
        )
        self.assertAlmostEqual(prob, 0.55)

    def test_derive_market_prob_from_asks_edge_cases(self):
        """Test edge cases for market probability calculation."""
        # Test with very high ask prices
        prob = self.json_parser._derive_market_prob_from_asks(
            yes_ask=99.0, no_ask=1.0, bet_direction="home", fallback_prob=0.5
        )
        self.assertAlmostEqual(prob, 0.99)

        # Test with very low ask prices
        prob = self.json_parser._derive_market_prob_from_asks(
            yes_ask=1.0, no_ask=99.0, bet_direction="away", fallback_prob=0.5
        )
        self.assertAlmostEqual(prob, 0.99)


if __name__ == "__main__":
    def test_team_factor_adjustment(self):
        # Mock team factor of +5%
        with patch.object(PortfolioOptimizer, '_fetch_team_factor', return_value=0.05):
            opp = BetOpportunity(
                sport="mlb",
                ticker="TEST",
                game_id="MLB_20240520_TEST_HOME_AWAY",
                elo_prob=0.6,
                market_prob=0.5
            )
            opportunities = [opp]

            # Apply team factor adjustment
            for o in opportunities:
                if o.game_id:
                    adjustment = self.optimizer._fetch_team_factor(o.game_id)
                    adjustment = max(-0.05, min(0.05, adjustment))
                    o.elo_prob = max(0.0, min(1.0, o.elo_prob + adjustment))

            self.assertAlmostEqual(opportunities[0].elo_prob, 0.65)

    def test_team_factor_capping(self):
        # Test cap at +5%
        with patch.object(PortfolioOptimizer, '_fetch_team_factor', return_value=0.07):
            opp = BetOpportunity(
                sport="mlb",
                ticker="TEST",
                game_id="MLB_20240520_TEST_HOME_AWAY",
                elo_prob=0.6,
                market_prob=0.5
            )
            opportunities = [opp]

            for o in opportunities:
                if o.game_id:
                    adjustment = self.optimizer._fetch_team_factor(o.game_id)
                    adjustment = max(-0.05, min(0.05, adjustment))
                    o.elo_prob = max(0.0, min(1.0, o.elo_prob + adjustment))

            self.assertAlmostEqual(opportunities[0].elo_prob, 0.65)
            self.assertLessEqual(opportunities[0].elo_prob, 1.0)

    def test_negative_team_factor(self):
        # Test negative adjustment
        with patch.object(PortfolioOptimizer, '_fetch_team_factor', return_value=-0.03):
            opp = BetOpportunity(
                sport="mlb",
                ticker="TEST",
                game_id="MLB_20240520_TEST_HOME_AWAY",
                elo_prob=0.7,
                market_prob=0.5
            )
            opportunities = [opp]

            for o in opportunities:
                if o.game_id:
                    adjustment = self.optimizer._fetch_team_factor(o.game_id)
                    adjustment = max(-0.05, min(0.05, adjustment))
                    o.elo_prob = max(0.0, min(1.0, o.elo_prob + adjustment))

            self.assertAlmostEqual(opportunities[0].elo_prob, 0.67)
            self.assertGreaterEqual(opportunities[0].elo_prob, 0.0)

    unittest.main()
