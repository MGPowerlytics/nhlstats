import numpy as np


def test_fit_and_apply_platt_scaler_shapes_and_range():
    from probability_calibration import apply_platt_scaler, fit_platt_scaler

    rng = np.random.default_rng(0)
    # Synthetic probabilities and labels with both classes present
    p = rng.uniform(0.05, 0.95, size=2000)
    y = (rng.random(2000) < p).astype(int)

    model = fit_platt_scaler(y=y, probs=p, c=1.0, max_iter=2000)
    assert model is not None

    out = apply_platt_scaler(model, p)
    assert out.shape == p.shape
    assert np.all(out > 0.0)
    assert np.all(out < 1.0)


def test_bucketed_platt_scaler_falls_back_to_global():
    from probability_calibration import (
        apply_bucketed_platt_scaler,
        fit_bucketed_platt_scaler,
    )

    rng = np.random.default_rng(1)
    p = rng.uniform(0.05, 0.95, size=2000)
    y = (rng.random(2000) < p).astype(int)
    # One large bucket and one tiny bucket; tiny should fall back
    buckets = np.array(["big"] * 1990 + ["tiny"] * 10)

    bm = fit_bucketed_platt_scaler(y=y, probs=p, buckets=buckets, min_samples=1000)
    out, used_bucket = apply_bucketed_platt_scaler(bm, probs=p, buckets=buckets)

    assert out.shape == p.shape
    assert used_bucket.shape == p.shape
    # We should have a bucket model for 'big', but not 'tiny'
    assert "big" in bm.bucket_models
    assert "tiny" not in bm.bucket_models
    assert used_bucket[buckets == "big"].any()
    assert not used_bucket[buckets == "tiny"].any()
