-- Governed tennis model-evaluation table and dashboard read model.

CREATE TABLE IF NOT EXISTS tennis_model_evaluations (
    run_date DATE NOT NULL,
    model_version VARCHAR NOT NULL,
    data_source VARCHAR NOT NULL,
    rows INTEGER NOT NULL,
    holdout_rows INTEGER NOT NULL,
    betmgm_holdout_rows INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    beats_betmgm BOOLEAN NOT NULL DEFAULT FALSE,
    baseline_log_loss DOUBLE PRECISION NOT NULL,
    ensemble_log_loss DOUBLE PRECISION NOT NULL,
    ensemble_market_log_loss DOUBLE PRECISION,
    betmgm_log_loss DOUBLE PRECISION,
    baseline_brier DOUBLE PRECISION NOT NULL,
    ensemble_brier DOUBLE PRECISION NOT NULL,
    ensemble_market_brier DOUBLE PRECISION,
    betmgm_brier DOUBLE PRECISION,
    baseline_accuracy DOUBLE PRECISION NOT NULL,
    ensemble_accuracy DOUBLE PRECISION NOT NULL,
    ensemble_market_accuracy DOUBLE PRECISION,
    betmgm_accuracy DOUBLE PRECISION,
    baseline_actionable_count INTEGER NOT NULL,
    ensemble_actionable_count INTEGER NOT NULL,
    log_loss_delta DOUBLE PRECISION NOT NULL,
    brier_delta DOUBLE PRECISION NOT NULL,
    accuracy_delta DOUBLE PRECISION NOT NULL,
    ensemble_vs_betmgm_log_loss_delta DOUBLE PRECISION,
    ensemble_vs_betmgm_brier_delta DOUBLE PRECISION,
    ensemble_vs_betmgm_accuracy_delta DOUBLE PRECISION,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_date, model_version, data_source)
);

CREATE INDEX IF NOT EXISTS idx_tennis_model_evaluations_created_at
    ON tennis_model_evaluations (created_at DESC);

DROP VIEW IF EXISTS dashboard_tennis_model_health_v1;

CREATE VIEW dashboard_tennis_model_health_v1 AS
SELECT
    run_date,
    model_version,
    data_source,
    rows,
    holdout_rows,
    betmgm_holdout_rows,
    enabled,
    beats_betmgm,
    baseline_log_loss,
    ensemble_log_loss,
    ensemble_market_log_loss,
    betmgm_log_loss,
    baseline_brier,
    ensemble_brier,
    ensemble_market_brier,
    betmgm_brier,
    baseline_accuracy,
    ensemble_accuracy,
    ensemble_market_accuracy,
    betmgm_accuracy,
    baseline_actionable_count,
    ensemble_actionable_count,
    log_loss_delta,
    brier_delta,
    accuracy_delta,
    ensemble_vs_betmgm_log_loss_delta,
    ensemble_vs_betmgm_brier_delta,
    ensemble_vs_betmgm_accuracy_delta,
    created_at
FROM tennis_model_evaluations;
