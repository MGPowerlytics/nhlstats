"""Provider contract tests for the calibrated Elo boundary.

These tests exercise the real :class:`ProbabilityCalibrator` with stubbed
training data and verify the contractual invariants that consumers
(``BettingOutcome``, ``GameContext``) depend on:

1.  Calibrated probability is always in **[0, 1]** (type ``float``).
2.  Monotonicity is preserved (higher raw Elo → >= higher calibrated).
3.  Falls back cleanly (raw Elo used) when calibrator is not fitted.
4.  Per-sport models are independent.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from plugins.probability_calibration import (
    CalibratorNotFittedError,
    ProbabilityCalibrator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_stub_db(rows: list[dict]) -> MagicMock:
    """Build a stub DBManager with the given training rows."""
    import pandas as pd
    stub = MagicMock()
    stub.fetch_df.return_value = pd.DataFrame(rows)
    return stub


@pytest.fixture(scope="module")
def trained_calibrator() -> tuple[ProbabilityCalibrator, dict[str, MagicMock]]:
    """A ProbabilityCalibrator fitted for MLB and EPL with distinct biases.

    Returns:
        Tuple of (calibrator, {sport: stub_db}) so tests can inspect data.
    """
    rng = np.random.default_rng(42)

    # MLB: overestimates by ~25pp
    mlb_rows = []
    for _ in range(200):
        raw = float(rng.uniform(0.50, 0.85))
        true_rate = raw - 0.25
        outcome = 1.0 if rng.random() < true_rate else 0.0
        mlb_rows.append({"elo_prob": raw, "outcome": outcome})

    # EPL: underestimates slightly
    epl_rows = []
    for _ in range(200):
        raw = float(rng.uniform(0.30, 0.65))
        true_rate = raw + 0.05
        outcome = 1.0 if rng.random() < true_rate else 0.0
        epl_rows.append({"elo_prob": raw, "outcome": outcome})

    mlb_db = _make_stub_db(mlb_rows)
    epl_db = _make_stub_db(epl_rows)

    calibrator = ProbabilityCalibrator(db=mlb_db)
    calibrator.fit("MLB")

    calibrator.db = epl_db
    calibrator.fit("EPL")

    return calibrator, {"MLB": mlb_db, "EPL": epl_db}


@pytest.fixture
def unfitted_calibrator() -> ProbabilityCalibrator:
    """A fresh calibrator with no fitted models."""
    stub = _make_stub_db([{"elo_prob": 0.5, "outcome": 0}])
    return ProbabilityCalibrator(db=stub)


# ===========================================================================
# Contract tests
# ===========================================================================


class TestCalibratedEloProviderContract:
    """Provider-side guarantees for the calibrated Elo boundary."""

    # --- Contract 1: Range ------------------------------------------------

    @pytest.mark.parametrize("raw", [0.01, 0.25, 0.50, 0.75, 0.99])
    def test_contract_range(self, trained_calibrator, raw: float) -> None:
        """Calibrated probability must be in [0.0, 1.0] for all valid inputs."""
        calibrator, _ = trained_calibrator
        cal = calibrator.calibrate("MLB", raw)
        assert isinstance(cal, float), f"Expected float, got {type(cal)}"
        assert 0.0 <= cal <= 1.0, f"Calibrated prob {cal} out of [0, 1]"

    # --- Contract 2: Monotonicity -----------------------------------------

    def test_contract_monotonicity(self, trained_calibrator) -> None:
        """Higher raw Elo → >= higher calibrated probability."""
        calibrator, _ = trained_calibrator
        inputs = [0.1, 0.3, 0.5, 0.7, 0.9]
        outputs = [calibrator.calibrate("MLB", p) for p in inputs]

        for i in range(len(outputs) - 1):
            assert outputs[i] <= outputs[i + 1], (
                f"Monotonicity broken at {inputs[i]}→{outputs[i]:.4f} vs "
                f"{inputs[i+1]}→{outputs[i+1]:.4f}"
            )

    # --- Contract 3: Raw fallback on not-fitted ---------------------------

    def test_contract_raw_fallback_on_not_fitted(self) -> None:
        """When calibrator is not fitted for a sport, calibrate() raises
        CalibratorNotFittedError — the consumer MUST catch this and use
        raw Elo."""
        calibrator = ProbabilityCalibrator(db=MagicMock())
        # No fit() called
        with pytest.raises(CalibratorNotFittedError):
            calibrator.calibrate("CBA", 0.5)

    # --- Contract 4: Per-sport independence --------------------------------

    def test_contract_per_sport_models_are_independent(
        self, trained_calibrator,
    ) -> None:
        """Same raw input → different calibrated outputs for different sports."""
        calibrator, _ = trained_calibrator
        mlb_cal = calibrator.calibrate("MLB", 0.6)
        epl_cal = calibrator.calibrate("EPL", 0.6)

        assert mlb_cal != pytest.approx(epl_cal, abs=0.01), (
            f"MLB {mlb_cal:.4f} == EPL {epl_cal:.4f} — models not independent"
        )

    # --- Contract 5: Unfitted raises --------------------------------------

    def test_contract_unfitted_sport_raises(self, trained_calibrator) -> None:
        """Calling calibrate() for an unfitted sport raises appropriately."""
        calibrator, _ = trained_calibrator
        with pytest.raises(CalibratorNotFittedError):
            calibrator.calibrate("CBA", 0.5)

    # --- Contract 6: Edge saturation does not overflow --------------------

    @pytest.mark.parametrize("raw", [1e-6, 0.999999])
    def test_contract_edge_saturation_no_overflow(
        self, trained_calibrator, raw: float,
    ) -> None:
        """Extreme probabilities produce finite values without nan/inf."""
        calibrator, _ = trained_calibrator
        cal = calibrator.calibrate("MLB", raw)
        assert 0.0 <= cal <= 1.0
        assert not (cal != cal), f"Got nan for raw={raw}"  # NaN check
