-- ==========================================
-- ENLA 2026 Callao - CyT Dashboard View
-- Sprint 6: Materialized View for Looker Studio
-- ==========================================
-- Purpose: Materialized view for Ciencia y Tecnología area dashboard
-- Refresh: Daily at 03:00 UTC via BigQuery scheduled query
-- Connected to: Looker Studio CyT Dashboard
--
-- WARNING: CyT (Ciencia y Tecnología) data does NOT exist in the current Excel file.
-- The source data only has: M500_EM_2S_2023_CT, M500_EM_2S_2023_MA, M500_EM_2S_2023_CS
-- (NO M500_EM_2S_2023_CYT column exists).
-- This view will return 0 rows until CyT data becomes available.

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
WHERE f.area = 'cyt'  -- No data for this area - view will be empty
