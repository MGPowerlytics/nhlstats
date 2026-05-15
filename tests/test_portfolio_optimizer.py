import unittest
import pandas as pd
from unittest.mock import patch
from plugins.constants import MIN_ELO_PROB_FOR_BET
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

    def test_portfolio_config_min_elo_prob_uses_shared_constant(self):
        self.assertEqual(self.config.min_elo_prob, MIN_ELO_PROB_FOR_BET)

    @staticmethod
    def _apply_approval_grade_evidence(opportunity: BetOpportunity) -> BetOpportunity:
        opportunity.clv_evidence_tier = "approval_grade"
        opportunity.calibration_evidence_tier = "approval_grade"
        opportunity.walk_forward_evidence_tier = "approval_grade"
        return opportunity

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
                    "clv_evidence_tier": "approval_grade",
                    "calibration_evidence_tier": "approval_grade",
                    "walk_forward_evidence_tier": "approval_grade",
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
        self.assertEqual(opportunities[0].clv_evidence_tier, "approval_grade")
        self.assertEqual(
            opportunities[0].calibration_evidence_tier, "approval_grade"
        )
        self.assertEqual(
            opportunities[0].walk_forward_evidence_tier, "approval_grade"
        )

    def test_database_row_parser_fail_closes_missing_governance_fields(self):
        row = pd.Series(
            {
                "sport": "MLB",
                "ticker": "KXMLBGAME-26APR21CHCSTL-CHC",
                "bet_on": "home",
                "home_team": "Chicago Cubs",
                "away_team": "St. Louis Cardinals",
                "elo_prob": 0.61,
                "market_prob": 0.55,
                "edge": 0.06,
                "confidence": "MEDIUM",
                "yes_ask": 55,
                "no_ask": 45,
                "evidence_state": "shadow_only",
                "governance_status": "descriptive_only",
            }
        )

        opp = self.db_parser.parse(row, "mlb")

        self.assertIsNotNone(opp)
        self.assertFalse(opp.sizing_eligible)
        self.assertTrue(opp.abstain)
        self.assertIn("missing_governance_metadata", opp.abstention_reason)

    def test_database_row_parser_fail_closes_null_governance_fields(self):
        row = pd.Series(
            {
                "sport": "MLB",
                "ticker": "KXMLBGAME-26APR21CHCSTL-CHC",
                "bet_on": "home",
                "home_team": "Chicago Cubs",
                "away_team": "St. Louis Cardinals",
                "elo_prob": 0.61,
                "market_prob": 0.55,
                "edge": 0.06,
                "confidence": "MEDIUM",
                "yes_ask": 55,
                "no_ask": 45,
                "evidence_state": "shadow_only",
                "governance_status": "descriptive_only",
                "sizing_eligible": float("nan"),
                "abstain": None,
            }
        )

        opp = self.db_parser.parse(row, "mlb")

        self.assertIsNotNone(opp)
        self.assertFalse(opp.sizing_eligible)
        self.assertTrue(opp.abstain)
        self.assertIn("missing_governance_metadata", opp.abstention_reason)

    def test_json_parser_fail_closes_missing_governance_fields(self):
        data = {
            "sport": "MLB",
            "ticker": "KXMLBGAME-26APR21CHCSTL-CHC",
            "bet_on": "Chicago Cubs",
            "side": "home",
            "home_team": "Chicago Cubs",
            "away_team": "St. Louis Cardinals",
            "elo_prob": 0.61,
            "market_prob": 0.55,
            "edge": 0.06,
            "confidence": "MEDIUM",
            "yes_ask": 55,
            "no_ask": 45,
            "evidence_state": "shadow_only",
            "governance_status": "descriptive_only",
        }

        opp = self.json_parser.parse(data, "mlb")

        self.assertIsNotNone(opp)
        self.assertFalse(opp.sizing_eligible)
        self.assertTrue(opp.abstain)
        self.assertIn("missing_governance_metadata", opp.abstention_reason)

    def test_optimize_daily_bets_blocks_when_governed_recommendations_unavailable(self):
        legacy_shadow_payload = {
            "sport": "MLB",
            "game_id": "mlb-1",
            "home_team": "Dodgers",
            "away_team": "Padres",
            "bet_on": "Dodgers",
            "side": "home",
            "ticker": "KXMLBGAME-26MAY10LADSD-LAD",
            "elo_prob": 0.68,
            "market_prob": 0.5,
            "edge": 0.18,
            "confidence": "HIGH",
            "probability_source": "mlb_model_predictions",
            "evidence_state": "shadow_only",
            "evidence_state_reason": "MLB remains shadow-only pending approval-grade evidence.",
            "evidence_state_source_artifact": "mlb_model_predictions:mlb_moneyline_public_v3@2026-05-10",
            "governance_status": "descriptive_only",
        }

        with patch.object(self.optimizer, "load_opportunities_from_database", return_value=[]):
            with patch.object(
                self.optimizer, "load_opportunities_from_files"
            ) as mock_files:
                mock_files.return_value = [
                    self.json_parser.parse(legacy_shadow_payload, "mlb")
                ]

                allocations, summary = self.optimizer.optimize_daily_bets(
                    "2026-05-10", sports=["mlb"]
                )

        self.assertEqual(allocations, [])
        mock_files.assert_not_called()
        self.assertEqual(summary["data_source"], "database")
        self.assertEqual(
            summary["approval_blocked_reason"],
            "governed_recommendations_unavailable",
        )
        self.assertEqual(summary["opportunities_found"], 0)
        self.assertEqual(summary["opportunities_filtered"], 0)
        self.assertEqual(summary["bets_placed"], 0)

    def test_build_runtime_risk_context_raises_when_exposure_query_fails(self):
        with patch(
            "plugins.db_manager.default_db.fetch_df",
            side_effect=Exception("view unavailable"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "governed portfolio risk state"
            ):
                self.optimizer._build_runtime_risk_context(250.0)

    def test_build_runtime_risk_context_raises_when_open_positions_query_fails(self):
        with patch(
            "plugins.db_manager.default_db.fetch_df",
            side_effect=[
                pd.DataFrame(
                    [
                        {
                            "sport": "NBA",
                            "open_exposure_amount": 10.0,
                            "resting_order_exposure_amount": 4.0,
                            "executed_unsettled_exposure_amount": 6.0,
                        }
                    ]
                ),
                Exception("placed_bets unavailable"),
            ],
        ):
            with self.assertRaisesRegex(RuntimeError, "open positions"):
                self.optimizer._build_runtime_risk_context(250.0)

    def test_optimize_daily_bets_blocks_when_runtime_risk_context_unavailable(self):
        opportunity = BetOpportunity(
            sport="NBA",
            ticker="KXNBAGAME-TEST-LALBOS-LAL",
            bet_on="home",
            team="Lakers",
            opponent="Celtics",
            elo_prob=0.66,
            market_prob=0.5,
            edge=0.16,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
            sizing_eligible=True,
            abstain=False,
        )
        self._apply_approval_grade_evidence(opportunity)

        with patch.object(
            self.optimizer, "load_opportunities_from_database", return_value=[opportunity]
        ):
            with patch.object(
                self.optimizer,
                "_build_runtime_risk_context",
                side_effect=RuntimeError("governed open positions unavailable"),
            ):
                with patch.object(
                    self.optimizer, "load_opportunities_from_files"
                ) as mock_files:
                    allocations, summary = self.optimizer.optimize_daily_bets(
                        "2026-05-10", sports=["nba"]
                    )

        self.assertEqual(allocations, [])
        mock_files.assert_not_called()
        self.assertEqual(summary["data_source"], "database")
        self.assertEqual(
            summary["approval_blocked_reason"],
            "governed_risk_context_unavailable",
        )
        self.assertEqual(summary["opportunities_found"], 1)
        self.assertEqual(summary["opportunities_filtered"], 0)
        self.assertEqual(summary["bets_placed"], 0)

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

    def test_live_risk_mode_rejects_missing_and_contaminated_evidence(self):
        missing = BetOpportunity(
            sport="MLB",
            ticker="KXMLBGAME-TEST-LADSD-LAD",
            bet_on="home",
            team="Dodgers",
            opponent="Padres",
            elo_prob=0.61,
            market_prob=0.5,
            edge=0.11,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
            sizing_eligible=True,
            abstain=False,
        )
        contaminated = BetOpportunity(
            sport="MLB",
            ticker="KXMLBGAME-TEST-NYYBOS-NYY",
            bet_on="home",
            team="Yankees",
            opponent="Red Sox",
            elo_prob=0.6,
            market_prob=0.5,
            edge=0.1,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
            sizing_eligible=True,
            abstain=False,
        )
        contaminated.clv_contaminated_flag = True
        contaminated.contamination_reason = "binary_result_placeholder"

        risk_context = self.optimizer._empty_risk_context(250.0)
        filtered = self.optimizer.filter_opportunities(
            [missing, contaminated],
            risk_context=risk_context,
            enforce_governed_risk=True,
        )

        self.assertEqual(filtered, [])
        audit = self.optimizer.get_last_risk_audit()
        self.assertEqual(
            [row["rejection_reason_code"] for row in audit],
            ["missing_evidence", "contaminated_evidence"],
        )

    def test_live_risk_mode_blocks_same_match_conflicts_before_sizing(self):
        opportunity = BetOpportunity(
            sport="NHL",
            ticker="KXNHL-26MAY03NYRBOS-NYR",
            bet_on="home",
            team="Rangers",
            opponent="Bruins",
            elo_prob=0.58,
            market_prob=0.5,
            edge=0.08,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
            sizing_eligible=True,
            abstain=False,
            game_id="NHL_20260503_NYR_BOS",
        )
        self._apply_approval_grade_evidence(opportunity)

        risk_context = self.optimizer._empty_risk_context(250.0)
        risk_context["open_positions"] = [
            {
                "sport": "NHL",
                "canonical_match_key": "NHL_20260503_NYR_BOS",
                "selection_key": "bruins",
                "position_status": "filled",
                "exposure_amount": 12.0,
            }
        ]

        filtered = self.optimizer.filter_opportunities(
            [opportunity],
            risk_context=risk_context,
            enforce_governed_risk=True,
        )

        self.assertEqual(filtered, [])
        audit = self.optimizer.get_last_risk_audit()
        self.assertEqual(audit[0]["rejection_reason_code"], "existing_position_conflict")
        self.assertTrue(audit[0]["same_match_conflict"])

    def test_live_sizing_subtracts_governed_open_exposure(self):
        opportunity = BetOpportunity(
            sport="NBA",
            ticker="KXNBAGAME-TEST-LALBOS-LAL",
            bet_on="home",
            team="Lakers",
            opponent="Celtics",
            elo_prob=0.66,
            market_prob=0.5,
            edge=0.16,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
            sizing_eligible=True,
            abstain=False,
        )
        self._apply_approval_grade_evidence(opportunity)

        risk_context = self.optimizer._empty_risk_context(100.0)
        risk_context["remaining_daily_risk_budget_dollars"] = 6.0
        risk_context["governed_open_exposure_dollars"] = 94.0

        allocations = self.optimizer.calculate_portfolio_allocation(
            [opportunity],
            risk_context=risk_context,
        )

        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations[0].bet_size, 6.0)
        audit = self.optimizer.get_last_risk_audit()
        self.assertEqual(audit[-1]["rejection_reason_code"], "remaining_budget_downgrade")
        self.assertEqual(audit[-1]["approved_bet_size_dollars"], 6.0)

    def test_live_sizing_rejects_governed_concentration_breach(self):
        opportunity = BetOpportunity(
            sport="NBA",
            ticker="KXNBAGAME-TEST-NYKCHI-NYK",
            bet_on="home",
            team="Knicks",
            opponent="Bulls",
            elo_prob=0.62,
            market_prob=0.5,
            edge=0.12,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
            sizing_eligible=True,
            abstain=False,
        )
        self._apply_approval_grade_evidence(opportunity)
        filtered = self.optimizer.filter_opportunities(
            [opportunity],
            risk_context=self.optimizer._empty_risk_context(250.0),
            enforce_governed_risk=True,
        )

        risk_context = self.optimizer._empty_risk_context(250.0)
        risk_context["sport_exposure_amounts"] = {"NBA": 38.0}
        risk_context["sport_concentration_limit_dollars"] = 40.0

        allocations = self.optimizer.calculate_portfolio_allocation(
            filtered,
            risk_context=risk_context,
        )

        self.assertEqual(allocations, [])
        audit = self.optimizer.get_last_risk_audit()
        self.assertEqual(audit[-1]["rejection_reason_code"], "concentration_breach")

    def test_live_sizing_emits_drawdown_reporting_without_zero_drawdown_block(
        self,
    ):
        opportunity = BetOpportunity(
            sport="NBA",
            ticker="KXNBAGAME-TEST-DALPHX-DAL",
            bet_on="home",
            team="Mavericks",
            opponent="Suns",
            elo_prob=0.69,
            market_prob=0.5,
            edge=0.19,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
            sizing_eligible=True,
            abstain=False,
        )
        self._apply_approval_grade_evidence(opportunity)

        filtered = self.optimizer.filter_opportunities(
            [opportunity],
            risk_context=self.optimizer._empty_risk_context(250.0),
            enforce_governed_risk=True,
        )

        risk_context = self.optimizer._empty_risk_context(250.0)
        risk_context.update(
            {
                "current_portfolio_value_dollars": 1475.75,
                "peak_portfolio_value_dollars": 1600.0,
                "drawdown_amount_dollars": 124.25,
                "drawdown_ratio": 0.07765625,
                "drawdown_state": "drawdown_active",
                "risk_of_ruin_state": "capital_available",
                "portfolio_guardrail_state": "eligible",
                "portfolio_guardrail_reason_code": None,
                "portfolio_guardrail_reason_detail": None,
            }
        )

        allocations = self.optimizer.calculate_portfolio_allocation(
            filtered,
            risk_context=risk_context,
        )

        self.assertEqual(len(allocations), 1)
        audit = self.optimizer.get_last_risk_audit()
        self.assertEqual(audit[-1]["drawdown_state"], "drawdown_active")
        self.assertEqual(audit[-1]["portfolio_guardrail_state"], "eligible")
        self.assertIsNone(audit[-1]["rejection_reason_code"])
        self.assertGreater(audit[-1]["approved_bet_size_dollars"], 0.0)

    def test_live_sizing_rejects_explicit_drawdown_guardrail_before_strong_single_sport_approval(
        self,
    ):
        opportunity = BetOpportunity(
            sport="NBA",
            ticker="KXNBAGAME-TEST-DENOKC-DEN",
            bet_on="home",
            team="Nuggets",
            opponent="Thunder",
            elo_prob=0.71,
            market_prob=0.5,
            edge=0.21,
            confidence="HIGH",
            yes_ask=50,
            no_ask=50,
            sizing_eligible=True,
            abstain=False,
        )
        self._apply_approval_grade_evidence(opportunity)

        filtered = self.optimizer.filter_opportunities(
            [opportunity],
            risk_context=self.optimizer._empty_risk_context(250.0),
            enforce_governed_risk=True,
        )

        risk_context = self.optimizer._empty_risk_context(250.0)
        risk_context.update(
            {
                "current_portfolio_value_dollars": 1475.75,
                "peak_portfolio_value_dollars": 1600.0,
                "drawdown_amount_dollars": 124.25,
                "drawdown_ratio": 0.07765625,
                "drawdown_state": "drawdown_active",
                "risk_of_ruin_state": "capital_available",
                "portfolio_guardrail_state": "blocked_drawdown",
                "portfolio_guardrail_reason_code": "drawdown_gate_blocked",
                "portfolio_guardrail_reason_detail": (
                    "Explicit governed drawdown regime is active for new approvals."
                ),
            }
        )

        allocations = self.optimizer.calculate_portfolio_allocation(
            filtered,
            risk_context=risk_context,
        )

        self.assertEqual(allocations, [])
        audit = self.optimizer.get_last_risk_audit()
        self.assertEqual(audit[-1]["rejection_reason_code"], "drawdown_gate_blocked")
        self.assertEqual(audit[-1]["portfolio_guardrail_state"], "blocked_drawdown")
        self.assertEqual(audit[-1]["drawdown_state"], "drawdown_active")

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
                elo_prob=0.62,
                market_prob=0.24,
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
                elo_prob=0.61,
                market_prob=0.48,
                edge=0.13,
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
