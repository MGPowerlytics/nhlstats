import unittest
import pandas as pd
from unittest.mock import patch
from plugins.portfolio_optimizer import (
    DatabaseRowParser,
    JsonFileParser,
    PortfolioOptimizer,
    PortfolioConfig,
    BetOpportunity,
)


class TestPortfolioOptimizerRefactored(unittest.TestCase):
    def setUp(self):
        self.db_parser = DatabaseRowParser()
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

    def test_database_row_parser_handles_home_away_bet_on_values(self):
        row = pd.Series(
            {
                "sport": "MLB",
                "ticker": "KXMLBGAME-26APR21CHCSTL-CHC",
                "bet_on": "home",
                "home_team": "Chicago Cubs",
                "away_team": "St. Louis Cardinals",
                "home_rating": 1512.0,
                "away_rating": 1497.0,
                "elo_prob": 0.61,
                "market_prob": 0.55,
                "edge": 0.06,
                "confidence": "MEDIUM",
                "yes_ask": 55,
                "no_ask": 45,
                "bet_id": "MLB_2026-04-21_KXMLBGAME-26APR21CHCSTL-CHC_home",
            }
        )

        opp = self.db_parser.parse(row, "mlb")

        self.assertIsNotNone(opp)
        self.assertEqual(opp.bet_on, "home")
        self.assertEqual(opp.team, "Chicago Cubs")
        self.assertEqual(opp.opponent, "St. Louis Cardinals")

    def test_load_opportunities_from_database_normalizes_sport_filter(self):
        rows = pd.DataFrame(
            [
                {
                    "sport": "MLB",
                    "ticker": "KXMLBGAME-26APR21CHCSTL-CHC",
                    "bet_on": "home",
                    "home_team": "Chicago Cubs",
                    "away_team": "St. Louis Cardinals",
                    "home_rating": 1512.0,
                    "away_rating": 1497.0,
                    "elo_prob": 0.61,
                    "market_prob": 0.55,
                    "edge": 0.06,
                    "confidence": "MEDIUM",
                    "yes_ask": 55,
                    "no_ask": 45,
                    "bet_id": "MLB_2026-04-21_KXMLBGAME-26APR21CHCSTL-CHC_home",
                }
            ]
        )

        with patch(
            "plugins.db_manager.default_db.fetch_df", return_value=rows
        ) as mock_fetch:
            opportunities = self.optimizer.load_opportunities_from_database(
                "2026-04-21", sports=["mlb"]
            )

        query = mock_fetch.call_args[0][0]
        self.assertIn("'MLB'", query)
        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].sport, "MLB")
        self.assertEqual(opportunities[0].bet_on, "home")
        self.assertEqual(opportunities[0].team, "Chicago Cubs")

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

    def test_filter_opportunities_keeps_edge_based_high_confidence_soccer_and_mlb(self):
        optimizer = PortfolioOptimizer(
            PortfolioConfig(
                bankroll=1000.0,
                min_confidence=0.65,
                excluded_segments=[("EPL", "LOW"), ("MLB", "LOW")],
            )
        )

        opportunities = [
            BetOpportunity(
                sport="EPL",
                ticker="KXEPLGAME-TEST-ARSNEW-NEW",
                bet_on="home",
                team="Arsenal",
                opponent="Newcastle",
                elo_prob=0.5279,
                market_prob=0.15,
                edge=0.3779,
                confidence="HIGH",
                yes_ask=15,
                no_ask=85,
            ),
            BetOpportunity(
                sport="MLB",
                ticker="KXMLBGAME-TEST-ATHSEA-ATH",
                bet_on="away",
                team="Athletics",
                opponent="Mariners",
                elo_prob=0.4887,
                market_prob=0.39,
                edge=0.0987,
                confidence="MEDIUM",
                yes_ask=39,
                no_ask=61,
            ),
        ]

        filtered = optimizer.filter_opportunities(opportunities)

        self.assertEqual(len(filtered), 2)
        self.assertEqual({opp.sport for opp in filtered}, {"EPL", "MLB"})

    def test_calculate_portfolio_allocation_preserves_multi_sport_exposure(self):
        optimizer = PortfolioOptimizer(
            PortfolioConfig(
                bankroll=100.0,
                max_daily_risk_pct=0.04,
                max_single_bet_pct=0.02,
                min_bet_size=2.0,
                max_bet_size=10.0,
            )
        )

        opportunities = [
            BetOpportunity(
                sport="EPL",
                ticker="EPL-1",
                bet_on="home",
                team="Arsenal",
                opponent="Chelsea",
                elo_prob=0.52,
                market_prob=0.10,
                edge=0.42,
                confidence="HIGH",
                yes_ask=10,
                no_ask=90,
            ),
            BetOpportunity(
                sport="EPL",
                ticker="EPL-2",
                bet_on="home",
                team="Liverpool",
                opponent="Crystal Palace",
                elo_prob=0.51,
                market_prob=0.12,
                edge=0.39,
                confidence="HIGH",
                yes_ask=12,
                no_ask=88,
            ),
            BetOpportunity(
                sport="MLB",
                ticker="MLB-1",
                bet_on="away",
                team="Twins",
                opponent="Mets",
                elo_prob=0.58,
                market_prob=0.41,
                edge=0.17,
                confidence="HIGH",
                yes_ask=41,
                no_ask=59,
            ),
        ]

        allocations = optimizer.calculate_portfolio_allocation(opportunities)

        self.assertEqual(len(allocations), 2)
        self.assertEqual(
            {alloc.opportunity.sport for alloc in allocations}, {"EPL", "MLB"}
        )


if __name__ == "__main__":
    unittest.main()
