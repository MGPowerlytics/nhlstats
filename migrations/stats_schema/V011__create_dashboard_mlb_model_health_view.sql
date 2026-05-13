-- Governed dashboard read model for MLB predictive-model health.

DROP VIEW IF EXISTS dashboard_mlb_model_health_v1;

CREATE VIEW dashboard_mlb_model_health_v1 AS
SELECT
    run_date,
    model_version,
    COUNT(*)::INTEGER AS prediction_count,
    COUNT(*) FILTER (WHERE abstain)::INTEGER AS abstention_count,
    CASE
        WHEN COUNT(*) = 0 THEN 0.0
        ELSE COUNT(*) FILTER (WHERE abstain)::DOUBLE PRECISION / COUNT(*)::DOUBLE PRECISION
    END::DOUBLE PRECISION AS abstention_rate,
    AVG(model_prob)::DOUBLE PRECISION AS avg_model_prob,
    AVG(market_prob)::DOUBLE PRECISION AS avg_market_prob,
    AVG(edge)::DOUBLE PRECISION AS avg_edge,
    AVG(expected_value)::DOUBLE PRECISION AS avg_expected_value,
    AVG(ece_at_train)::DOUBLE PRECISION AS ece_at_train,
    MAX(created_at)::TIMESTAMP AS latest_prediction_at
FROM mlb_model_predictions
GROUP BY run_date, model_version;
