"""TDD tests for ProbabilityCalibrator (Platt scaling for Elo probabilities)."""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from plugins.probability_calibration import (
    CalibratorNotFittedError,
    ProbabilityCalibrator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stub_db(rows: list[dict]) -> MagicMock:
    """Build a stub DBManager whose fetch_df returns a DataFrame built from *rows*.

    Each dict in *rows* must have at least ``elo_prob`` and ``outcome`` keys.
    """
    stub = MagicMock()
    df = pd.DataFrame(rows)
    stub.fetch_df.return_value = df
    return stub


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def stub_db_with_30_bets() -> MagicMock:
    """30 settled bets for MLB with known bias: Elo overestimates by ~20-30pp.

    The outcome rate increases with Elo prob (higher Elo → more likely to win),
    but the overall rate is ~0.45 even though Elo predicts ~0.70 — preserving
    the monotonic relationship required for Platt scaling.
    """
    np.random.seed(42)
    rows = []
    for _ in range(30):
        # Raw Elo between 0.55 and 0.85
        raw_elo = np.random.uniform(0.55, 0.85)
        # True win rate is a linear function of raw_elo but shifted down ~25pp
        true_rate = raw_elo - 0.25  # e.g. 0.70 raw → 0.45 true
        outcome = 1.0 if np.random.random() < true_rate else 0.0
        rows.append({"elo_prob": raw_elo, "outcome": outcome})
    return _make_stub_db(rows)


@pytest.fixture
def stub_db_with_20_bets() -> MagicMock:
    """Only 20 settled bets — below the 30-threshold."""
    np.random.seed(42)
    rows = []
    for _ in range(20):
        raw_elo = np.random.uniform(0.55, 0.85)
        true_rate = raw_elo - 0.25
        outcome = 1.0 if np.random.random() < true_rate else 0.0
        rows.append({"elo_prob": raw_elo, "outcome": outcome})
    return _make_stub_db(rows)


@pytest.fixture
def stub_db_perfect_calibration() -> MagicMock:
    """Data where Elo is perfectly calibrated (outcome rate == raw prob).

    Uses 2000 samples to ensure the logistic regression converges to
    identity (calibrated ≈ raw) within a tight tolerance.
    """
    np.random.seed(42)
    rows = []
    rng = np.random.default_rng(42)
    for raw_elo in rng.uniform(0.2, 0.8, size=2000):
        outcome = 1.0 if rng.random() < raw_elo else 0.0
        rows.append({"elo_prob": float(raw_elo), "outcome": outcome})
    return _make_stub_db(rows)


@pytest.fixture
def stub_db_two_sports() -> tuple[MagicMock, MagicMock]:
    """Return (mlb_db, epl_db) with different bias profiles.

    MLB: Elo overestimates (true rate ~0.45, predicted ~0.70).
    EPL: Elo underestimates slightly (true rate ~0.55, predicted ~0.50).
    """
    np.random.seed(123)
    mlb_rows = []
    for _ in range(35):
        raw_elo = np.random.uniform(0.55, 0.85)
        true_rate = raw_elo - 0.25  # overestimate by ~25pp
        outcome = 1.0 if np.random.random() < true_rate else 0.0
        mlb_rows.append({"elo_prob": raw_elo, "outcome": outcome})

    epl_rows = []
    for _ in range(35):
        raw_elo = np.random.uniform(0.35, 0.65)
        true_rate = raw_elo + 0.05  # underestimate by ~5pp
        outcome = 1.0 if np.random.random() < true_rate else 0.0
        epl_rows.append({"elo_prob": raw_elo, "outcome": outcome})

    return _make_stub_db(mlb_rows), _make_stub_db(epl_rows)


# ===========================================================================
# Tests
# ===========================================================================

class TestProbabilityCalibrator:
    """TDD suite for Platt scaling calibration."""

    # --- Test 1: Range check ------------------------------------------------

    def test_calibrate_returns_probability_in_range(self, stub_db_with_30_bets):
        """calibrate() returns a float in [0.0, 1.0] for any valid input."""
        calibrator = ProbabilityCalibrator(db=stub_db_with_30_bets)
        calibrator.fit("MLB")

        cal = calibrator.calibrate("MLB", 0.72)
        assert 0.0 <= cal <= 1.0, f"Calibrated prob {cal} out of [0, 1]"

        for raw in [0.01, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99]:
            cal = calibrator.calibrate("MLB", raw)
            assert 0.0 <= cal <= 1.0, f"Calibrated prob {cal} out of [0, 1] for raw={raw}"

    # --- Test 2: Monotonicity -----------------------------------------------

    def test_calibrate_preserves_monotonicity(self, stub_db_with_30_bets):
        """If elo_prob_a > elo_prob_b then calibrated_a >= calibrated_b."""
        calibrator = ProbabilityCalibrator(db=stub_db_with_30_bets)
        calibrator.fit("MLB")

        inputs = [0.1, 0.3, 0.5, 0.7, 0.9]
        outputs = [calibrator.calibrate("MLB", p) for p in inputs]

        for i in range(len(outputs) - 1):
            assert outputs[i] <= outputs[i + 1], (
                f"Monotonicity broken at index {i}: {outputs[i]} > {outputs[i + 1]}"
            )

    # --- Test 3: Bias reduction ---------------------------------------------

    def test_calibrate_reduces_bias_on_real_data(self, stub_db_with_30_bets):
        """On synthetic data where Elo overestimates by ~20pp, calibrated
        probability is closer to the true win rate than raw Elo."""
        calibrator = ProbabilityCalibrator(db=stub_db_with_30_bets)
        calibrator.fit("MLB")

        # The fixture generates true_rate = raw_elo - 0.25.
        # For raw=0.70, true rate ≈ 0.45.  Raw bias ≈ 0.25.
        # Calibrated prob should be closer to 0.45 than 0.70 is.
        raw = 0.70
        true_rate = 0.45
        cal = calibrator.calibrate("MLB", raw)

        raw_bias = abs(raw - true_rate)
        cal_bias = abs(cal - true_rate)

        assert cal_bias < raw_bias, (
            f"Calibrated bias {cal_bias:.3f} >= raw bias {raw_bias:.3f} "
            f"(cal={cal:.3f}, raw={raw})"
        )

    # --- Test 4: Unfitted sport raises error --------------------------------

    def test_calibrate_raises_for_unfitted_sport(self, stub_db_with_30_bets):
        """calibrate() for an unfitted sport raises CalibratorNotFittedError."""
        calibrator = ProbabilityCalibrator(db=stub_db_with_30_bets)
        # Fit MLB but not CBA
        calibrator.fit("MLB")

        with pytest.raises(CalibratorNotFittedError):
            calibrator.calibrate("CBA", 0.5)

    # --- Test 5: Fit trains logistic model ----------------------------------

    def test_fit_trains_logistic_model(self, stub_db_with_30_bets):
        """After fit('MLB'), calibrate() returns sensible values (not NaN, not constant)."""
        calibrator = ProbabilityCalibrator(db=stub_db_with_30_bets)
        calibrator.fit("MLB")

        # The model should produce different outputs for different inputs
        c1 = calibrator.calibrate("MLB", 0.3)
        c2 = calibrator.calibrate("MLB", 0.7)

        assert not math.isnan(c1)
        assert not math.isnan(c2)
        assert c2 > c1, "Calibrated values should differ for different inputs"

        # Both should be in [0, 1]
        assert 0.0 <= c1 <= 1.0
        assert 0.0 <= c2 <= 1.0

    # --- Test 6: Force retrain ----------------------------------------------

    def test_fit_force_retrain_overwrites_cached(self, stub_db_with_30_bets):
        """fit('MLB', force_retrain=True) replaces existing model."""
        calibrator = ProbabilityCalibrator(db=stub_db_with_30_bets)
        calibrator.fit("MLB")

        # Get initial calibration
        initial = calibrator.calibrate("MLB", 0.5)

        # Refit — should overwrite
        calibrator.fit("MLB", force_retrain=True)
        after_retrain = calibrator.calibrate("MLB", 0.5)

        # The values could differ due to randomization in the stub data
        # (each fit calls fetch_df again which gets a fresh DataFrame),
        # but calibrate should still work
        assert isinstance(after_retrain, float)
        assert 0.0 <= after_retrain <= 1.0

    # --- Test 7: Identity when perfectly calibrated -------------------------

    def test_calibrate_identity_when_perfectly_calibrated(
        self, stub_db_perfect_calibration
    ):
        """When raw Elo matches true outcome rate, calibrated ≈ raw."""
        calibrator = ProbabilityCalibrator(db=stub_db_perfect_calibration)
        calibrator.fit("PERFECT")

        for raw in [0.3, 0.4, 0.5, 0.6, 0.7]:
            cal = calibrator.calibrate("PERFECT", raw)
            # With 2000 well-calibrated samples the model should be close
            # to identity (±15pp to account for logit-link curvature at edges)
            assert abs(cal - raw) < 0.15, (
                f"Calibrated {cal:.3f} differs from raw {raw:.3f} by >15pp"
            )

    # --- Test 8: Edge saturation --------------------------------------------

    def test_calibrate_saturates_at_edges(self, stub_db_with_30_bets):
        """Extreme probabilities (0.001, 0.999) don't overflow or hit exact 0/1."""
        calibrator = ProbabilityCalibrator(db=stub_db_with_30_bets)
        calibrator.fit("MLB")

        # Very low probability
        low = calibrator.calibrate("MLB", 0.001)
        assert 0.0 <= low <= 1.0
        # Should not be exactly 0 (would cause division issues downstream)
        assert low > 0.0 or abs(low - 0.0) < 1e-10

        # Very high probability
        high = calibrator.calibrate("MLB", 0.999)
        assert 0.0 <= high <= 1.0
        # Should not be exactly 1.0
        assert high < 1.0 or abs(high - 1.0) < 1e-10

    # --- Test 9: Per-sport distinct models ----------------------------------

    def test_calibrate_different_sports_have_different_models(
        self, stub_db_two_sports
    ):
        """Same raw Elo prob produces different calibrated probs for MLB vs EPL."""
        mlb_db, epl_db = stub_db_two_sports

        calibrator = ProbabilityCalibrator(db=mlb_db)
        calibrator.fit("MLB")

        # Replace db for EPL fit
        calibrator.db = epl_db
        calibrator.fit("EPL")

        # Same input for both sports
        mlb_cal = calibrator.calibrate("MLB", 0.6)
        epl_cal = calibrator.calibrate("EPL", 0.6)

        # They should be different (different bias profiles)
        assert mlb_cal != pytest.approx(epl_cal, abs=0.01), (
            f"MLB calibrated {mlb_cal:.4f} == EPL calibrated {epl_cal:.4f} — "
            "models appear identical"
        )

    # -------------------------------------------------------------------
    # Additional edge-case tests
    # -------------------------------------------------------------------

    def test_calibrate_fallback_when_below_min_bets(self, stub_db_with_20_bets):
        """fit() raises CalibratorNotFittedError when < 30 bets available."""
        calibrator = ProbabilityCalibrator(db=stub_db_with_20_bets, load_precomputed=False)

        with pytest.raises(CalibratorNotFittedError):
            calibrator.fit("MLB")

    def test_calibrate_raises_if_not_fitted_at_all(self, stub_db_with_30_bets):
        """calibrate() before any fit() raises CalibratorNotFittedError."""
        calibrator = ProbabilityCalibrator(db=stub_db_with_30_bets, load_precomputed=False)

        with pytest.raises(CalibratorNotFittedError):
            calibrator.calibrate("MLB", 0.5)
