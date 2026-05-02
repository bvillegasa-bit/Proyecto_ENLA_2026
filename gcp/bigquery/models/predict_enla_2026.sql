-- Stored Procedure: Generate ENLA 2026 Predictions for All Areas
--
-- Uses trained BigQuery ML models to generate predictions for all 4 areas
-- and stores results in enla_callao_predictions_2026 table.
--
-- Risk classification:
--   ALTO:  confidence < 0.55 (model nearly guessing)
--   MEDIO: confidence 0.55 - 0.75 (moderate confidence)
--   BAJO:  confidence > 0.75 (high confidence)
--
-- Usage: Replace {project_id} and {dataset_id} placeholders before running.

CREATE OR REPLACE PROCEDURE `{project_id}.{dataset_id}.predict_enla_2026`()
BEGIN
    -- ==========================================
    -- Comunicacion
    -- ==========================================
    CREATE OR REPLACE TABLE `{project_id}.{dataset_id}._tmp_predictions_comunicacion` AS
    SELECT
        area,
        institution_id,
        nom_ie,
        predicted_target AS predicted_success,
        predicted_target_probability AS confidence,
        CASE
            WHEN predicted_target_probability < 0.55 THEN 'ALTO'
            WHEN predicted_target_probability < 0.75 THEN 'MEDIO'
            ELSE 'BAJO'
        END AS risk_level,
        'v1' AS model_version,
        CURRENT_TIMESTAMP() AS prediction_ts,
        CURRENT_TIMESTAMP() AS created_at
    FROM ML.PREDICT(
        MODEL `{project_id}.{dataset_id}.enla_model_comunicacion_v1`,
        (SELECT * FROM `{project_id}.{dataset_id}.enla_callao_features` WHERE area = 'comunicacion')
    );

    -- ==========================================
    -- Matematica
    -- ==========================================
    CREATE OR REPLACE TABLE `{project_id}.{dataset_id}._tmp_predictions_matematica` AS
    SELECT
        area,
        institution_id,
        nom_ie,
        predicted_target AS predicted_success,
        predicted_target_probability AS confidence,
        CASE
            WHEN predicted_target_probability < 0.55 THEN 'ALTO'
            WHEN predicted_target_probability < 0.75 THEN 'MEDIO'
            ELSE 'BAJO'
        END AS risk_level,
        'v1' AS model_version,
        CURRENT_TIMESTAMP() AS prediction_ts,
        CURRENT_TIMESTAMP() AS created_at
    FROM ML.PREDICT(
        MODEL `{project_id}.{dataset_id}.enla_model_matematica_v1`,
        (SELECT * FROM `{project_id}.{dataset_id}.enla_callao_features` WHERE area = 'matematica')
    );

    -- ==========================================
    -- CCSS
    -- ==========================================
    CREATE OR REPLACE TABLE `{project_id}.{dataset_id}._tmp_predictions_ccss` AS
    SELECT
        area,
        institution_id,
        nom_ie,
        predicted_target AS predicted_success,
        predicted_target_probability AS confidence,
        CASE
            WHEN predicted_target_probability < 0.55 THEN 'ALTO'
            WHEN predicted_target_probability < 0.75 THEN 'MEDIO'
            ELSE 'BAJO'
        END AS risk_level,
        'v1' AS model_version,
        CURRENT_TIMESTAMP() AS prediction_ts,
        CURRENT_TIMESTAMP() AS created_at
    FROM ML.PREDICT(
        MODEL `{project_id}.{dataset_id}.enla_model_ccss_v1`,
        (SELECT * FROM `{project_id}.{dataset_id}.enla_callao_features` WHERE area = 'ccss')
    );

    -- ==========================================
    -- CYT
    -- ==========================================
    CREATE OR REPLACE TABLE `{project_id}.{dataset_id}._tmp_predictions_cyt` AS
    SELECT
        area,
        institution_id,
        nom_ie,
        predicted_target AS predicted_success,
        predicted_target_probability AS confidence,
        CASE
            WHEN predicted_target_probability < 0.55 THEN 'ALTO'
            WHEN predicted_target_probability < 0.75 THEN 'MEDIO'
            ELSE 'BAJO'
        END AS risk_level,
        'v1' AS model_version,
        CURRENT_TIMESTAMP() AS prediction_ts,
        CURRENT_TIMESTAMP() AS created_at
    FROM ML.PREDICT(
        MODEL `{project_id}.{dataset_id}.enla_model_cyt_v1`,
        (SELECT * FROM `{project_id}.{dataset_id}.enla_callao_features` WHERE area = 'cyt')
    );

    -- ==========================================
    -- Combine all predictions into final table
    -- ==========================================
    CREATE OR REPLACE TABLE `{project_id}.{dataset_id}.enla_callao_predictions_2026` AS
    SELECT
        GENERATE_UUID() AS prediction_id,
        area,
        institution_id,
        nom_ie,
        predicted_success,
        confidence,
        risk_level,
        model_version,
        prediction_ts,
        created_at
    FROM (
        SELECT * FROM `{project_id}.{dataset_id}._tmp_predictions_comunicacion`
        UNION ALL
        SELECT * FROM `{project_id}.{dataset_id}._tmp_predictions_matematica`
        UNION ALL
        SELECT * FROM `{project_id}.{dataset_id}._tmp_predictions_ccss`
        UNION ALL
        SELECT * FROM `{project_id}.{dataset_id}._tmp_predictions_cyt`
    );

    -- Clean up temporary tables
    DROP TABLE IF EXISTS `{project_id}.{dataset_id}._tmp_predictions_comunicacion`;
    DROP TABLE IF EXISTS `{project_id}.{dataset_id}._tmp_predictions_matematica`;
    DROP TABLE IF EXISTS `{project_id}.{dataset_id}._tmp_predictions_ccss`;
    DROP TABLE IF EXISTS `{project_id}.{dataset_id}._tmp_predictions_cyt`;

END;
