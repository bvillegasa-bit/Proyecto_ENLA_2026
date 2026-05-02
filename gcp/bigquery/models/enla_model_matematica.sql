-- BigQuery ML Logistic Regression Model: Matematica
--
-- Trains a model to predict ENLA 2026 success/failure for Matematica area.
-- Uses temporal split: 2021-2022 as train, 2023 as eval.
--
-- Features (normalized [-1, 1]):
--   avg_score_2023, avg_score_2022, avg_score_2021, trend, variance
--
-- Usage: Replace {project_id} and {dataset_id} placeholders before running.

CREATE OR REPLACE MODEL `{project_id}.{dataset_id}.enla_model_matematica_v1`
OPTIONS(
    model_type='logistic_reg',
    input_label_cols=['target'],
    data_split_method='CUSTOM',
    data_split_col='split',
    l2_reg=0.1,
    max_iterations=20,
    learn_rate=0.1,
    early_stop=True
) AS
SELECT
    avg_score_2023,
    avg_score_2022,
    avg_score_2021,
    trend,
    variance,
    target,
    CASE
        WHEN year_in_train THEN 'train'
        ELSE 'eval'
    END AS split
FROM `{project_id}.{dataset_id}.enla_callao_features`
WHERE area = 'matematica';
