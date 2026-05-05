-- ==========================================
-- ENLA 2026 Callao - Matemática Dashboard View
-- Sprint 6: Materialized View for Looker Studio
-- ==========================================
-- Purpose: Materialized view for Matemática area dashboard
-- Refresh: Daily at 03:00 UTC via BigQuery scheduled query
-- Connected to: Looker Studio Matemática Dashboard
--
-- Data source: 
--   - Raw column: M500_EM_2S_2023_MA → academic area 'matematica'
--   - Features: avg_score_2023, trend, variance from enla_callao_features
--   - Predictions: risk_level, confidence from enla_callao_predictions_2026

{{ config(materialized='view') }}

SELECT
  f.institution_id,
  f.nom_ie,
  f.avg_score_2023,
  f.avg_score_2022,
  f.avg_score_2021,
  f.trend,
  f.variance,
  f.target,
  p.predicted_success,
  p.confidence,
  p.risk_level,
  p.model_version,
  p.prediction_ts
FROM {{ source('enla_raw', 'enla_callao_features') }} f
LEFT JOIN {{ source('enla_raw', 'enla_callao_predictions_2026') }} p
  ON f.institution_id = p.institution_id
  AND f.area = p.area
WHERE f.area = 'matemática'
