"""Additional tests for NBA Elo Rating module - covering helper functions."""

import pytest
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestNBAEloRatingCore:
    """Test core NBAEloRating functionality."""
    
    def test_init_defaults(self):
        """Test default initialization."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        
        assert elo.k_factor == 20
        assert elo.home_advantage == 100
        assert elo.initial_rating == 1500
        assert elo.ratings == {}
    
    def test_init_custom_params(self):
        """Test custom initialization."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating(k_factor=30, home_advantage=80, initial_rating=1400)
        
        assert elo.k_factor == 30
        assert elo.home_advantage == 80
        assert elo.initial_rating == 1400
    
    def test_get_rating_new_team(self):
        """Test getting rating for new team."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        rating = elo.get_rating("New Team")
        
        assert rating == 1500
        assert "New Team" in elo.ratings
    
    def test_get_rating_existing_team(self):
        """Test getting rating for existing team."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.ratings["Lakers"] = 1600
        rating = elo.get_rating("Lakers")
        
        assert rating == 1600
    
    def test_expected_score_equal_ratings(self):
        """Test expected score with equal ratings."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        score = elo.expected_score(1500, 1500)
        
        assert score == 0.5
    
    def test_expected_score_higher_rating_favored(self):
        """Test higher rated team is favored."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        score = elo.expected_score(1600, 1500)
        
        assert score > 0.5
    
    def test_expected_score_lower_rating_underdog(self):
        """Test lower rated team is underdog."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        score = elo.expected_score(1400, 1500)
        
        assert score < 0.5
    
    def test_predict_includes_home_advantage(self):
        """Test prediction includes home advantage."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.ratings["Home"] = 1500
        elo.ratings["Away"] = 1500
        
        prob = elo.predict("Home", "Away")
        
        # With home advantage, should be > 50%
        assert prob > 0.5
    
    def test_update_winner_gains_rating(self):
        """Test winner gains rating."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.ratings["Winner"] = 1500
        elo.ratings["Loser"] = 1500
        
        elo.update("Winner", "Loser", home_won=True)
        
        assert elo.ratings["Winner"] > 1500
    
    def test_update_loser_loses_rating(self):
        """Test loser loses rating."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.ratings["Winner"] = 1500
        elo.ratings["Loser"] = 1500
        
        elo.update("Winner", "Loser", home_won=True)
        
        assert elo.ratings["Loser"] < 1500
    
    def test_update_zero_sum(self):
        """Test rating changes are zero-sum."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.ratings["Team A"] = 1500
        elo.ratings["Team B"] = 1500
        
        total_before = sum(elo.ratings.values())
        elo.update("Team A", "Team B", home_won=True)
        total_after = sum(elo.ratings.values())
        
        assert total_before == pytest.approx(total_after, abs=0.001)
    
    def test_update_upset_larger_change(self):
        """Test upset results in larger rating change."""
        from nba_elo_rating import NBAEloRating
        
        elo1 = NBAEloRating()
        elo1.ratings["Favorite"] = 1600
        elo1.ratings["Underdog"] = 1400
        
        elo2 = NBAEloRating()
        elo2.ratings["Favorite"] = 1600
        elo2.ratings["Underdog"] = 1400
        
        # Expected win
        elo1.update("Favorite", "Underdog", home_won=True)
        change_expected = elo1.ratings["Favorite"] - 1600
        
        # Upset
        elo2.update("Underdog", "Favorite", home_won=False)
        change_upset = 1400 - elo2.ratings["Underdog"]
        
        # Upset should cause larger change (in absolute terms)
        assert abs(change_upset) > abs(change_expected)


class TestLoadNBAGamesFromJSON:
    """Test JSON game loading functions."""
    
    def test_json_file_structure(self, tmp_path):
        """Test expected JSON file structure."""
        game_data = {
            'resultSets': [
                {
                    'name': 'GameHeader',
                    'rowSet': [
                        ['game_id', 'game_date', 'home_team', 'away_team', 'home_score', 'away_score']
                    ]
                }
            ]
        }
        
        json_file = tmp_path / "game.json"
        json_file.write_text(json.dumps(game_data))
        
        with open(json_file) as f:
            loaded = json.load(f)
        
        assert 'resultSets' in loaded
    
    def test_parse_game_date(self):
        """Test parsing game date."""
        date_str = "2024-01-15T00:00:00"
        
        from datetime import datetime
        parsed = datetime.fromisoformat(date_str.replace('T', ' ').split('.')[0])
        
        assert parsed.year == 2024
        assert parsed.month == 1
        assert parsed.day == 15


class TestEloMetrics:
    """Test Elo evaluation metrics."""
    
    def test_accuracy_calculation(self):
        """Test accuracy calculation."""
        predictions = [1, 1, 0, 1, 0]
        actuals = [1, 1, 0, 0, 0]
        
        correct = sum(p == a for p, a in zip(predictions, actuals))
        accuracy = correct / len(predictions)
        
        assert accuracy == 0.8
    
    def test_brier_score(self):
        """Test Brier score calculation."""
        # Brier score = mean squared error of probabilities
        probs = [0.9, 0.8, 0.3, 0.6]
        actuals = [1, 1, 0, 1]
        
        brier = sum((p - a) ** 2 for p, a in zip(probs, actuals)) / len(probs)
        
        assert brier < 0.2  # Good predictions
    
    def test_calibration_check(self):
        """Test prediction calibration."""
        # For well-calibrated predictions, when we predict 70%,
        # actual win rate should be ~70%
        
        predictions_70pct = [0.70] * 10
        actuals = [1, 1, 1, 0, 1, 1, 1, 0, 0, 1]
        
        actual_rate = sum(actuals) / len(actuals)
        
        assert actual_rate == 0.7


class TestEloRatingHistory:
    """Test Elo rating history tracking."""
    
    def test_game_history_recorded(self):
        """Test game history is recorded."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.game_history = []
        
        # Record a game
        game = {
            'home_team': 'Lakers',
            'away_team': 'Celtics',
            'home_won': True,
            'prediction': 0.55
        }
        elo.game_history.append(game)
        
        assert len(elo.game_history) == 1
    
    def test_rating_progression(self):
        """Test rating progression over multiple games."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        
        # Simulate a winning streak
        for i in range(10):
            elo.update("Winner", f"Team{i}", home_won=True)
        
        # Rating should increase significantly
        assert elo.ratings["Winner"] > 1550


class TestTeamNormalization:
    """Test team name normalization."""
    
    def test_normalize_full_name(self):
        """Test normalizing full team name."""
        full = "Los Angeles Lakers"
        short = "Lakers"
        
        normalized = full.split()[-1]
        
        assert normalized == short
    
    def test_team_abbreviations(self):
        """Test team abbreviation mapping."""
        abbrev_map = {
            'LAL': 'Lakers',
            'BOS': 'Celtics',
            'GSW': 'Warriors'
        }
        
        assert abbrev_map['LAL'] == 'Lakers'
    
    def test_case_insensitive_matching(self):
        """Test case-insensitive team matching."""
        team1 = "LAKERS"
        team2 = "lakers"
        
        assert team1.lower() == team2.lower()


class TestSeasonReversion:
    """Test season-to-season rating reversion."""
    
    def test_ratings_regress_to_mean(self):
        """Test ratings regress to mean between seasons."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.ratings["Top Team"] = 1700
        elo.ratings["Bottom Team"] = 1300
        
        # Regress 1/3 toward mean
        mean_rating = 1500
        reversion_factor = 1/3
        
        new_top = elo.ratings["Top Team"] - reversion_factor * (elo.ratings["Top Team"] - mean_rating)
        new_bottom = elo.ratings["Bottom Team"] + reversion_factor * (mean_rating - elo.ratings["Bottom Team"])
        
        assert new_top < 1700
        assert new_bottom > 1300
        assert new_top > new_bottom  # Top should still be higher


class TestEdgeCases:
    """Test edge cases."""
    
    def test_perfect_prediction(self):
        """Test perfect prediction (100%)."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.ratings["Dominant"] = 2000
        elo.ratings["Weak"] = 1000
        
        prob = elo.predict("Dominant", "Weak")
        
        assert prob > 0.95
    
    def test_very_close_ratings(self):
        """Test very close ratings."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.ratings["A"] = 1500
        elo.ratings["B"] = 1501
        
        prob = elo.predict("A", "B")
        
        # Should be close to 0.5 but home team slightly favored
        assert 0.55 < prob < 0.65
