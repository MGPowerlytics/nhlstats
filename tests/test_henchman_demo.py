"""
Simple test file for NBAEloRating class demonstration.
Contains 2 test cases as requested: test_init and test_predict_returns_probability.
"""

import sys
import os

# Add parent directory to path to import from plugins
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.elo import NBAEloRating


def test_init():
    """Test initialization of NBAEloRating class with default parameters."""
    # Create an instance of NBAEloRating
    elo = NBAEloRating()

    # Verify default parameters
    assert elo.k_factor == 20.0, f"Expected k_factor=20.0, got {elo.k_factor}"
    assert elo.home_advantage == 100.0, (
        f"Expected home_advantage=100.0, got {elo.home_advantage}"
    )
    assert elo.initial_rating == 1500.0, (
        f"Expected initial_rating=1500.0, got {elo.initial_rating}"
    )

    # Verify ratings dictionary is empty initially
    assert elo.ratings == {}, f"Expected empty ratings dict, got {elo.ratings}"

    print("✓ test_init passed: NBAEloRating initialized with correct defaults")


def test_predict_returns_probability():
    """Test that predict method returns a valid probability between 0 and 1."""
    # Create an instance of NBAEloRating
    elo = NBAEloRating()

    # Set up some test ratings
    elo.ratings["Lakers"] = 1600.0
    elo.ratings["Celtics"] = 1400.0

    # Test 1: Predict with home advantage (Lakers at home)
    probability = elo.predict("Lakers", "Celtics", is_neutral=False)

    # Verify it's a float
    assert isinstance(probability, float), f"Expected float, got {type(probability)}"

    # Verify it's between 0 and 1 (inclusive)
    assert 0.0 <= probability <= 1.0, (
        f"Expected probability between 0 and 1, got {probability}"
    )

    # Lakers should have higher probability since they're higher rated and at home
    assert probability > 0.5, (
        f"Expected probability > 0.5 for higher rated home team, got {probability}"
    )

    print(
        f"✓ Test 1 passed: predict returns probability {probability:.3f} (Lakers at home)"
    )

    # Test 2: Predict without home advantage (neutral court)
    probability_neutral = elo.predict("Lakers", "Celtics", is_neutral=True)

    # Verify it's a float between 0 and 1
    assert isinstance(probability_neutral, float), (
        f"Expected float, got {type(probability_neutral)}"
    )
    assert 0.0 <= probability_neutral <= 1.0, (
        f"Expected probability between 0 and 1, got {probability_neutral}"
    )

    # Without home advantage, probability should be lower but still > 0.5
    assert probability_neutral > 0.5, (
        f"Expected probability > 0.5 for higher rated team, got {probability_neutral}"
    )

    # Home advantage should increase probability
    assert probability > probability_neutral, (
        f"Expected home advantage to increase probability ({probability:.3f} > {probability_neutral:.3f})"
    )

    print(
        f"✓ Test 2 passed: predict returns probability {probability_neutral:.3f} (neutral court)"
    )

    # Test 3: Predict with equal ratings
    elo.ratings["TeamA"] = 1500.0
    elo.ratings["TeamB"] = 1500.0

    probability_equal = elo.predict("TeamA", "TeamB", is_neutral=False)

    # With equal ratings and home advantage, home team should have slight edge
    assert 0.5 < probability_equal < 0.7, (
        f"Expected probability ~0.64 for equal teams with home advantage, got {probability_equal}"
    )

    print(
        f"✓ Test 3 passed: predict returns probability {probability_equal:.3f} (equal ratings, home advantage)"
    )


if __name__ == "__main__":
    """Run the tests when executed directly."""
    print("Running NBAEloRating demo tests...")
    print("=" * 50)

    try:
        test_init()
        print("-" * 50)
        test_predict_returns_probability()
        print("=" * 50)
        print("✅ All tests passed!")
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
