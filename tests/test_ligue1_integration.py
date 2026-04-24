
import pytest
import os
import sys
import pandas as pd
from datetime import date

# Add plugins to path
sys.path.insert(0, os.path.join(os.getcwd(), "plugins"))
sys.path.insert(0, os.path.join(os.getcwd(), "plugins", "elo"))

from db_manager import DBManager
from ligue1_elo_rating import Ligue1EloRating
from ligue1_ensemble_adapter import Ligue1EnsembleAdapter
from ligue1_ensemble import Ligue1EnsembleModel

@pytest.fixture
def db():
    # Use a test database or mock if possible, but here we'll assume the real one
    # since we're in a controlled environment.
    # For safety, we can use an in-memory sqlite for some parts if needed.
    return DBManager()

def test_ligue1_variable_k():
    """Test that Ligue 1 Elo uses variable K-factor (30/20)."""
    elo = Ligue1EloRating()

    # Win update (K=30)
    # Expected change for equal teams: 30 * (1.0 - 0.5) = 15.0 (excluding HA)
    # HA=60 means home expected is ~0.585
    # Change = 30 * (1.0 - 0.585) = 12.45
    elo.update("TeamA", "TeamB", home_won=1.0)
    change_win = elo.get_rating("TeamA") - 1500

    # Reset
    elo.ratings = {"TeamA": 1500, "TeamB": 1500}

    # Draw update (K=20)
    # Change = 20 * (0.5 - 0.585) = -1.7
    elo.update("TeamA", "TeamB", home_won=0.5)
    change_draw = elo.get_rating("TeamA") - 1500

    # The win change magnitude should be larger than draw change
    # even accounting for the different distances from expectation.
    # 12.45 / 0.415 = 30
    # 1.7 / 0.085 = 20
    assert abs(change_win / (1.0 - elo.expected_score(1560, 1500)) - 30.0) < 0.1
    assert abs(change_draw / (0.5 - elo.expected_score(1560, 1500)) - 20.0) < 0.1

def test_ligue1_ensemble_adapter_predict():
    """Test that the ensemble adapter provides a 3-way prediction."""
    adapter = Ligue1EnsembleAdapter()

    # Mock some stats
    adapter.team_stats["PSG"] = SimpleNamespace(
        games_played=10, goals_for=25, goals_against=5, wins=8, recent_results=[1, 1, 1, 0.5, 1]
    )
    adapter.team_stats["Marseille"] = SimpleNamespace(
        games_played=10, goals_for=15, goals_against=10, wins=5, recent_results=[0.5, 1, 0, 1, 0.5]
    )

    p_h, p_d, p_a = adapter.predict_probs("PSG", "Marseille")

    assert 0 <= p_h <= 1
    assert 0 <= p_d <= 1
    assert 0 <= p_a <= 1
    assert abs(p_h + p_d + p_a - 1.0) < 0.001

class SimpleNamespace:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
