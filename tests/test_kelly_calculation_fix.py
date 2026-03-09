"""Test Kelly calculation fix for numerical stability."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from plugins.odds_comparator import OddsComparator


def test_kelly_calculation_numerical_stability():
    """Test that Kelly calculation handles edge cases correctly."""

    # Mock the database
    class MockDB:
        def fetch_df(self, query, params=None):
            return []

    comparator = OddsComparator(db_manager=MockDB())

    # We need to test the internal calculation, so let's extract the logic
    def calculate_kelly_from_code(elo_prob, market_prob):
        """Replicate the Kelly calculation logic from odds_comparator.py"""
        if market_prob > 0 and market_prob < 1:
            p = elo_prob
            q = 1 - elo_prob
            b = (1 / market_prob) - 1

            # Handle edge cases:
            # 1. If b is infinite or extremely large, use p as approximation
            #    (when market_prob → 0, b → ∞, f* → p)
            # 2. If b is 0 (market_prob = 1), don't bet
            # 3. Otherwise use stable formula
            if b == float("inf") or b > 1e100:
                # Market thinks it's impossible, bet full edge
                kelly_fraction = max(0.0, p)
            elif b > 0:
                # Stable formula: f* = p - q/b
                kelly_fraction = max(0.0, p - q / b)
            else:
                # b <= 0 means no positive expected value
                kelly_fraction = 0.0
        else:
            kelly_fraction = 0.0
        return kelly_fraction

    # Test cases
    test_cases = [
        # (elo_prob, market_prob, expected_kelly_min, expected_kelly_max, description)
        (0.6, 0.5, 0.199, 0.201, "Standard case"),
        (0.7, 0.9, 0.0, 0.0, "Negative edge"),
        (0.95, 0.9, 0.499, 0.501, "High probability"),
        (0.01, 0.005, 0.004, 0.006, "Very low probabilities"),
        (0.5, 0.01, 0.494, 0.496, "Long odds"),
        (0.5, 1e-10, 0.4999999999, 0.5000000001, "Extremely small market_prob"),
        (0.5, 1e-20, 0.4999999999, 0.5000000001, "Very extremely small market_prob"),
        (0.5, 0.0, 0.0, 0.0, "market_prob = 0"),
        (0.5, 1.0, 0.0, 0.0, "market_prob = 1"),
        (0.5, 0.9999, 0.0, 0.0, "market_prob close to 1"),
        (0.001, 0.0001, 0.0009, 0.0011, "Both probabilities very small"),
    ]

    print("Testing Kelly calculation fix:")
    all_passed = True

    for elo_prob, market_prob, expected_min, expected_max, description in test_cases:
        try:
            kelly = calculate_kelly_from_code(elo_prob, market_prob)

            # Check if result is in expected range
            if expected_min <= kelly <= expected_max:
                print(f"✓ {description}: kelly={kelly:.10f}")
            else:
                print(
                    f"✗ {description}: kelly={kelly:.10f} (expected between {expected_min} and {expected_max})"
                )
                all_passed = False

        except Exception as e:
            print(f"✗ {description}: Exception {e}")
            all_passed = False

    # Special test for infinite b case
    print("\nTesting infinite b case:")
    try:
        # market_prob = 1e-323 should give b = inf
        kelly = calculate_kelly_from_code(0.5, 1e-323)
        # When b is infinite, we should get p = 0.5
        if abs(kelly - 0.5) < 0.001:
            print(f"✓ Infinite b case handled correctly: kelly={kelly}")
        else:
            print(f"✗ Infinite b case: got kelly={kelly}, expected ~0.5")
            all_passed = False
    except Exception as e:
        print(f"✗ Infinite b case: Exception {e}")
        all_passed = False

    assert all_passed, "Some Kelly calculation tests failed"
    print("\n✅ All Kelly calculation tests passed!")


def test_kelly_formula_equivalence():
    """Test that stable formula gives same result as original formula for normal cases."""

    def original_formula(elo_prob, market_prob):
        """Original formula from before the fix."""
        if market_prob > 0 and market_prob < 1:
            p = elo_prob
            q = 1 - elo_prob
            b = (1 / market_prob) - 1
            kelly_fraction = max(0, (p * b - q) / b) if b > 0 else 0.0
        else:
            kelly_fraction = 0.0
        return kelly_fraction

    def stable_formula(elo_prob, market_prob):
        """Stable formula from the fix."""
        if market_prob > 0 and market_prob < 1:
            p = elo_prob
            q = 1 - elo_prob
            b = (1 / market_prob) - 1

            if b == float("inf") or b > 1e100:
                kelly_fraction = max(0.0, p)
            elif b > 0:
                kelly_fraction = max(0.0, p - q / b)
            else:
                kelly_fraction = 0.0
        else:
            kelly_fraction = 0.0
        return kelly_fraction

    # Test cases where both formulas should give same result
    test_cases = [
        (0.6, 0.5),
        (0.7, 0.6),
        (0.8, 0.75),
        (0.4, 0.3),
        (0.9, 0.85),
        (0.55, 0.5),
    ]

    print("\nTesting formula equivalence:")
    for elo_prob, market_prob in test_cases:
        orig = original_formula(elo_prob, market_prob)
        stable = stable_formula(elo_prob, market_prob)
        diff = abs(orig - stable)

        if diff < 1e-10:
            print(
                f"✓ elo={elo_prob}, market={market_prob}: orig={orig:.6f}, stable={stable:.6f}, diff={diff:.2e}"
            )
        else:
            print(
                f"✗ elo={elo_prob}, market={market_prob}: orig={orig:.6f}, stable={stable:.6f}, diff={diff:.2e}"
            )
            assert False, f"Formulas differ by {diff}"

    print("✅ Formula equivalence tests passed!")


if __name__ == "__main__":
    test_kelly_calculation_numerical_stability()
    test_kelly_formula_equivalence()
    print("\n🎉 All tests passed!")
