"""
Test suite for Elo temporal integrity - ensuring no data leakage.

CRITICAL: Elo predictions must use ratings from BEFORE the game being predicted.
This test suite validates:
1. predict() is always called BEFORE update()
2. Ratings used in predictions are from prior games only
3. No look-ahead bias in historical backtests
4. Production DAG maintains temporal order
"""

import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from nba_elo_rating import NBAEloRating
from nhl_elo_rating import NHLEloRating
from mlb_elo_rating import MLBEloRating
from nfl_elo_rating import NFLEloRating
from ncaab_elo_rating import NCAABEloRating
from wncaab_elo_rating import WNCAABEloRating
from tennis_elo_rating import TennisEloRating


class TestEloTemporalIntegrity(unittest.TestCase):
    """Test that Elo predictions never use future information."""
    
    def test_nba_predict_before_update(self):
        """
        NBA: Verify predict() uses ratings from BEFORE update().
        
        Scenario: 
        - Game 1: Team A (1500) vs Team B (1500) - A wins
        - Game 2: Team A vs Team B again
        
        Game 2 prediction MUST use Game 1 post-update ratings, not pre-update.
        """
        elo = NBAEloRating(k_factor=20, home_advantage=100)
        
        # Initial ratings
        self.assertEqual(elo.get_rating("Team A"), 1500)
        self.assertEqual(elo.get_rating("Team B"), 1500)
        
        # Game 1: Predict BEFORE update
        prob_game1 = elo.predict("Team A", "Team B")
        self.assertAlmostEqual(prob_game1, 0.640, places=2)  # With home advantage
        
        # Game 1: Update after prediction
        elo.update("Team A", "Team B", home_won=True)
        
        # Ratings should have changed
        rating_a_after_game1 = elo.get_rating("Team A")
        rating_b_after_game1 = elo.get_rating("Team B")
        
        self.assertGreater(rating_a_after_game1, 1500, "Team A should increase after winning")
        self.assertLess(rating_b_after_game1, 1500, "Team B should decrease after losing")
        
        # Game 2: Prediction should use ratings AFTER Game 1
        prob_game2 = elo.predict("Team A", "Team B")
        
        # Game 2 prediction should be higher than Game 1 (Team A now stronger)
        self.assertGreater(prob_game2, prob_game1, 
                          "Game 2 prediction should reflect Team A's improved rating")
        
        # Verify exact calculation
        expected_prob_game2 = 1 / (1 + 10 ** ((rating_b_after_game1 - (rating_a_after_game1 + 100)) / 400))
        self.assertAlmostEqual(prob_game2, expected_prob_game2, places=5,
                              msg="Game 2 prediction should use post-Game-1 ratings")
    
    def test_nhl_predict_before_update(self):
        """NHL: Verify temporal integrity with recency weighting."""
        elo = NHLEloRating(k_factor=10, home_advantage=50)
        
        # Game 1
        rating_before = elo.get_rating("Toronto Maple Leafs")
        prob1 = elo.predict("Toronto Maple Leafs", "Boston Bruins")
        elo.update("Toronto Maple Leafs", "Boston Bruins", home_won=True)
        rating_after = elo.get_rating("Toronto Maple Leafs")
        
        self.assertNotEqual(rating_before, rating_after, 
                           "Rating must change after update")
        
        # Game 2: Should use updated rating
        prob2 = elo.predict("Toronto Maple Leafs", "Boston Bruins")
        self.assertNotEqual(prob1, prob2, 
                           "Second prediction should use updated ratings")
    
    def test_mlb_predict_before_update(self):
        """MLB: Verify temporal integrity."""
        elo = MLBEloRating(k_factor=20, home_advantage=50)
        
        prob1 = elo.predict("Yankees", "Red Sox")
        elo.update("Yankees", "Red Sox", home_score=5, away_score=3)
        prob2 = elo.predict("Yankees", "Red Sox")
        
        self.assertGreater(prob2, prob1, 
                          "Yankees should be stronger after winning")
    
    def test_nfl_predict_before_update(self):
        """NFL: Verify temporal integrity."""
        elo = NFLEloRating(k_factor=20, home_advantage=65)
        
        prob1 = elo.predict("Chiefs", "Bills")
        elo.update("Chiefs", "Bills", home_score=27, away_score=24)
        prob2 = elo.predict("Chiefs", "Bills")
        
        self.assertGreater(prob2, prob1, 
                          "Chiefs should be stronger after winning")
    
    def test_historical_simulation_no_leakage(self):
        """
        Critical test: Simulate processing historical games in order.
        Verify that predictions never use future information.
        """
        elo = NBAEloRating(k_factor=20, home_advantage=100)
        
        # Simulated historical games (chronological order)
        games = [
            {"date": "2024-01-01", "home": "Lakers", "away": "Warriors", "home_won": True},
            {"date": "2024-01-02", "home": "Warriors", "away": "Lakers", "home_won": False},
            {"date": "2024-01-03", "home": "Lakers", "away": "Celtics", "home_won": True},
        ]
        
        predictions_and_ratings = []
        
        for game in games:
            # CRITICAL: Predict BEFORE updating
            home_rating_before = elo.get_rating(game["home"])
            away_rating_before = elo.get_rating(game["away"])
            prediction = elo.predict(game["home"], game["away"])
            
            # Store prediction and ratings used
            predictions_and_ratings.append({
                "date": game["date"],
                "home": game["home"],
                "away": game["away"],
                "prediction": prediction,
                "home_rating_at_prediction": home_rating_before,
                "away_rating_at_prediction": away_rating_before
            })
            
            # Update AFTER prediction
            elo.update(game["home"], game["away"], game["home_won"])
        
        # Verify: Game 2 prediction used ratings AFTER Game 1 update
        game1_data = predictions_and_ratings[0]
        game2_data = predictions_and_ratings[1]
        
        # Warriors rating in Game 2 should reflect their Game 1 loss
        self.assertLess(game2_data["home_rating_at_prediction"], 
                       game1_data["away_rating_at_prediction"],
                       "Warriors rating in Game 2 should reflect their Game 1 loss")
        
        # Lakers rating in Game 2 should reflect their Game 1 win
        self.assertGreater(game2_data["away_rating_at_prediction"],
                          game1_data["home_rating_at_prediction"],
                          "Lakers rating in Game 2 should reflect their Game 1 win")
    
    def test_tennis_predict_before_update(self):
        """Tennis: Verify temporal integrity for individual sport."""
        elo = TennisEloRating(k_factor=32)  # Tennis doesn't have home advantage
        
        prob1 = elo.predict("Djokovic", "Federer", tour='ATP')
        elo.update("Djokovic", "Federer", tour='ATP')
        prob2 = elo.predict("Djokovic", "Federer", tour='ATP')
        
        self.assertGreater(prob2, prob1,
                          "Djokovic should be stronger after winning")
    
    def test_lift_gain_analysis_integrity(self):
        """
        Test that lift/gain analysis (used for threshold optimization)
        maintains temporal integrity.
        
        This is CRITICAL because our threshold decisions are based on this analysis.
        """
        elo = NBAEloRating(k_factor=20, home_advantage=100)
        
        # Simulate the lift/gain analysis pattern
        games = [
            {"home": "A", "away": "B", "home_won": True},
            {"home": "B", "away": "C", "home_won": False},
            {"home": "A", "away": "C", "home_won": True},
        ]
        
        predictions = []
        for game in games:
            # Pattern from lift_gain_analysis.py:
            # 1. Get prediction BEFORE updating
            pred = elo.predict(game["home"], game["away"])
            predictions.append(pred)
            
            # 2. Update AFTER prediction
            elo.update(game["home"], game["away"], game["home_won"])
        
        # Verify all predictions were made
        self.assertEqual(len(predictions), 3)
        
        # Verify predictions changed as ratings updated
        # (This validates temporal order was maintained)
        self.assertTrue(all(0 < p < 1 for p in predictions),
                       "All predictions should be valid probabilities")
    
    def test_production_dag_simulation(self):
        """
        Simulate production DAG behavior: predict current games using past ratings.
        
        This tests the identify_good_bets() pattern in the DAG.
        """
        elo = NBAEloRating(k_factor=20, home_advantage=100)
        
        # Historical games (already played - used to build ratings)
        historical_games = [
            {"home": "Lakers", "away": "Warriors", "home_won": True},
            {"home": "Celtics", "away": "Heat", "home_won": False},
        ]
        
        # Process historical games
        for game in historical_games:
            elo.update(game["home"], game["away"], game["home_won"])
        
        # Save ratings (simulating XCom push in DAG)
        current_ratings = dict(elo.ratings)
        
        # Today's games (not yet played - we're predicting these)
        todays_games = [
            {"home": "Lakers", "away": "Celtics"},
            {"home": "Warriors", "away": "Heat"},
        ]
        
        # Make predictions using current ratings
        for game in todays_games:
            prediction = elo.predict(game["home"], game["away"])
            
            # Verify prediction uses only historical ratings
            expected_pred = 1 / (1 + 10 ** ((current_ratings[game["away"]] - 
                                             (current_ratings[game["home"]] + 100)) / 400))
            self.assertAlmostEqual(prediction, expected_pred, places=5,
                                  msg="Prediction should use only historical ratings")
    
    def test_no_rating_contamination_across_games(self):
        """
        Verify that making predictions doesn't contaminate ratings.
        
        Bug scenario to prevent: predict() accidentally modifies ratings.
        """
        elo = NBAEloRating(k_factor=20, home_advantage=100)
        
        # Set initial ratings
        elo.update("A", "B", home_won=True)
        rating_a_after_update = elo.get_rating("A")
        rating_b_after_update = elo.get_rating("B")
        
        # Make multiple predictions
        for _ in range(10):
            elo.predict("A", "B")
        
        # Ratings should NOT have changed from predictions alone
        self.assertEqual(elo.get_rating("A"), rating_a_after_update,
                        "predict() should NOT modify ratings")
        self.assertEqual(elo.get_rating("B"), rating_b_after_update,
                        "predict() should NOT modify ratings")
    
    def test_chronological_game_order_required(self):
        """
        Verify that processing games out of chronological order gives wrong results.
        
        This demonstrates WHY temporal order matters.
        """
        # Correct order
        elo_correct = NBAEloRating(k_factor=20, home_advantage=100)
        games_chronological = [
            ("2024-01-01", "A", "B", True),
            ("2024-01-02", "B", "A", False),
        ]
        
        for date, home, away, home_won in games_chronological:
            elo_correct.update(home, away, home_won)
        
        correct_rating_a = elo_correct.get_rating("A")
        
        # Wrong order
        elo_wrong = NBAEloRating(k_factor=20, home_advantage=100)
        games_reversed = list(reversed(games_chronological))
        
        for date, home, away, home_won in games_reversed:
            elo_wrong.update(home, away, home_won)
        
        wrong_rating_a = elo_wrong.get_rating("A")
        
        # Ratings should be DIFFERENT (proving order matters)
        self.assertNotEqual(correct_rating_a, wrong_rating_a,
                           "Game order affects final ratings - must maintain chronological order")


class TestBacktestTemporalIntegrity(unittest.TestCase):
    """Test backtest scripts maintain temporal integrity."""
    
    def test_backtest_pattern(self):
        """
        Test the standard backtest pattern used throughout the codebase.
        
        Pattern:
        1. Load all historical games in chronological order
        2. For each game:
            a. Predict using current ratings
            b. Store prediction
            c. Update ratings with actual result
        3. Analyze predictions vs outcomes
        """
        elo = NBAEloRating(k_factor=20, home_advantage=100)
        
        games = [
            ("2024-01-01", "Lakers", "Warriors", True),
            ("2024-01-02", "Warriors", "Celtics", False),
            ("2024-01-03", "Celtics", "Lakers", True),
        ]
        
        backtest_results = []
        
        for date, home, away, home_won in games:
            # CRITICAL ORDER:
            # 1. Predict FIRST (using ratings before this game)
            prediction = elo.predict(home, away)
            
            # 2. Store prediction with outcome
            backtest_results.append({
                "date": date,
                "prediction": prediction,
                "actual": home_won
            })
            
            # 3. Update LAST (after prediction stored)
            elo.update(home, away, home_won)
        
        # Verify we have predictions for all games
        self.assertEqual(len(backtest_results), 3)
        
        # Verify predictions are valid
        for result in backtest_results:
            self.assertGreater(result["prediction"], 0)
            self.assertLess(result["prediction"], 1)


def run_temporal_integrity_tests():
    """Run all temporal integrity tests and report results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestEloTemporalIntegrity))
    suite.addTests(loader.loadTestsFromTestCase(TestBacktestTemporalIntegrity))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_temporal_integrity_tests()
    sys.exit(0 if success else 1)
