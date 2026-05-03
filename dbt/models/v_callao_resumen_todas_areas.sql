-- ==========================================
-- ENLA 2026 Callao - Executive Summary Dashboard View
-- Sprint 6: Materialized View for Looker Studio
-- ==========================================
-- Purpose: Executive summary across all areas
-- Refresh: Daily at 03:00 UTC via BigQuery scheduled query
-- Connected to: Looker Studio Executive Summary Dashboard
--
-- NOTE: Data covers 3 academic areas: comunicacion, matematica, ccss
-- (NO CyT/Ciencia y Tecnología data exists in the source Excel file)
-- The 'cyt' row will show 0 institutions until CyT data becomes available.

{{ config(materialized='view') }}

SELECT
  area,
  COUNT(*) as total_institutions,
  COUNTIF(risk_level = 'ALTO') as alto_risk_count,
  COUNTIF(risk_level = 'MEDIO') as medio_risk_count,
  COUNTIF(risk_level = 'BAJO') as bajo_risk_count,
  SAFE_DIVIDE(COUNTIF(risk_level = 'ALTO'), COUNT(*)) as alto_risk_pct,
  AVG(confidence) as avg_confidence,
  AVG(avg_score_2023) as avg_score_2023,
  AVG(trend) as avg_trend
FROM (
  SELECT f.*, p.risk_level, p.confidence, p.predicted_success
  FROM {{ ref('enla_callao_features') }} f
  JOIN {{ ref('enla_callao_predictions_2026') }} p
    ON f.institution_id = p.institution_id AND f.area = p.area
)
GROUP BY area
