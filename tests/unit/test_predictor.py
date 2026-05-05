"""Unit tests for model prediction module (Sprint 4).

Tests cover:
- Risk classification thresholds (ALTO, MEDIO, BAJO)
- Prediction query building (SQL structure)
- Prediction flow for single area (mocked)
- Save predictions flow (mocked)
- Predictions summary generation
- Risk distribution calculation
- Full prediction pipeline
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from src.models.predictor import (
    ENLAPredictor,
    PredictionError,
    PredictionResult,
    run_prediction_pipeline,
)
from src.database.bigquery_client import BigQueryConnectionError


# ==========================================
# Test Fixtures
# ==========================================

@pytest.fixture
def mock_bq_manager():
    """Create a mocked BigQueryClientManager."""
    manager = MagicMock()
    manager.project_id = 'test-project'
    manager.dataset_id = 'BI_ENLA'
    return manager


@pytest.fixture
def predictor(mock_bq_manager) -> ENLAPredictor:
    """Create an ENLAPredictor with mocked BQ client."""
    predictor = ENLAPredictor.__new__(ENLAPredictor)
    predictor.bq_manager = mock_bq_manager
    predictor.project_id = 'test-project'
    predictor.dataset_id = 'BI_ENLA'
    predictor.model_version = 'v1'
    predictor.RISK_THRESHOLDS = {
        'ALTO': 0.55,
        'MEDIO': 0.75,
    }
    return predictor


# ==========================================
# Test: Risk Classification
# ==========================================

class TestClassifyRisk:
    """Tests for risk level classification from confidence."""

    def test_alto_risk_below_055(self, predictor: ENLAPredictor):
        """Verify confidence < 0.55 returns ALTO."""
        assert predictor.classify_risk(0.10) == 'ALTO'
        assert predictor.classify_risk(0.30) == 'ALTO'
        assert predictor.classify_risk(0.54) == 'ALTO'

    def test_alto_risk_at_boundary(self, predictor: ENLAPredictor):
        """Verify confidence at exactly 0.55 is NOT ALTO."""
        # At 0.55, should be MEDIO (>= ALTO threshold, < MEDIO threshold)
        assert predictor.classify_risk(0.55) == 'MEDIO'

    def test_medio_risk_range(self, predictor: ENLAPredictor):
        """Verify confidence 0.55-0.75 returns MEDIO."""
        assert predictor.classify_risk(0.55) == 'MEDIO'
        assert predictor.classify_risk(0.60) == 'MEDIO'
        assert predictor.classify_risk(0.70) == 'MEDIO'
        assert predictor.classify_risk(0.74) == 'MEDIO'

    def test_medio_risk_at_boundary(self, predictor: ENLAPredictor):
        """Verify confidence at exactly 0.75 is NOT MEDIO."""
        # At 0.75, should be BAJO (>= MEDIO threshold)
        assert predictor.classify_risk(0.75) == 'BAJO'

    def test_bajo_risk_above_075(self, predictor: ENLAPredictor):
        """Verify confidence > 0.75 returns BAJO."""
        assert predictor.classify_risk(0.76) == 'BAJO'
        assert predictor.classify_risk(0.85) == 'BAJO'
        assert predictor.classify_risk(0.99) == 'BAJO'
        assert predictor.classify_risk(1.0) == 'BAJO'

    def test_risk_threshold_values(self, predictor: ENLAPredictor):
        """Verify RISK_THRESHOLDS constants are correct."""
        assert predictor.RISK_THRESHOLDS['ALTO'] == 0.55
        assert predictor.RISK_THRESHOLDS['MEDIO'] == 0.75


# ==========================================
# Test: Prediction Query Building
# ==========================================

class TestBuildPredictionQuery:
    """Tests for SQL prediction query construction."""

    def test_build_prediction_query_comunicacion(self, predictor: ENLAPredictor):
        """Verify SQL structure for comunicación area (general, no year)."""
        # User said: "comunicación y matemática" (WITH accents!)
        query = predictor._build_prediction_query('comunicación')

        assert 'ML.PREDICT' in query
        assert 'enla_model_comunicación_v1' in query
        assert 'enla_callao_features' in query
        assert "WHERE area = 'comunicación'" in query
        # For general query, should NOT have year filter
        assert 'AND year' not in query

    def test_build_prediction_query_comunicacion_year_specific(self, predictor: ENLAPredictor):
        """Verify SQL structure for comunicación area with year filter."""
        # User said: "comunicación y matemática" (WITH accents!)
        query = predictor._build_prediction_query('comunicación', year=2022)

        assert 'enla_model_comunicación_v1_2022' in query
        assert "WHERE area = 'comunicación'" in query
        assert 'AND year = 2022' in query

    def test_build_prediction_query_matematica(self, predictor: ENLAPredictor):
        """Verify SQL structure for matemática area (general, no year)."""
        # User said: "comunicación y matemática" (WITH accents!)
        query = predictor._build_prediction_query('matemática')

        assert 'enla_model_matemática_v1' in query
        assert "WHERE area = 'matemática'" in query

    def test_build_prediction_query_matematica_year_specific(self, predictor: ENLAPredictor):
        """Verify SQL structure for matemática area with year filter."""
        # User said: "comunicación y matemática" (WITH accents!)
        query = predictor._build_prediction_query('matemática', year=2023)

        assert 'enla_model_matemática_v1_2023' in query
        assert "WHERE area = 'matemática'" in query
        assert 'AND year = 2023' in query

    def test_build_prediction_query_ccss(self, predictor: ENLAPredictor):
        """Verify SQL structure for ccss area (general, all years)."""
        query = predictor._build_prediction_query('ccss')

        assert 'enla_model_ccss_v1' in query
        assert "WHERE area = 'ccss'" in query
        # ccss is general area, should NOT have year filter
        assert 'AND year' not in query

    def test_build_prediction_query_cyt(self, predictor: ENLAPredictor):
        """Verify SQL structure for cyt area (general, all years)."""
        query = predictor._build_prediction_query('cyt')

        assert 'enla_model_cyt_v1' in query
        assert "WHERE area = 'cyt'" in query
        # cyt is general area, should NOT have year filter
        assert 'AND year' not in query

    def test_build_prediction_query_uses_correct_project(self, predictor: ENLAPredictor):
        """Verify fully qualified names use correct project/dataset."""
        query = predictor._build_prediction_query('comunicacion')

        assert 'test-project.BI_ENLA.enla_model_comunicacion_v1' in query
        assert 'test-project.BI_ENLA.enla_callao_features' in query


# ==========================================
# Test: Predict For Area (Mocked)
# ==========================================

class TestPredictForArea:
    """Tests for single area prediction generation."""

    def test_predict_for_area_success(self, predictor: ENLAPredictor):
        """Verify predictions are generated correctly."""
        mock_predictions = pd.DataFrame({
            'predicted_target': [1, 0, 1],
            'predicted_target_probability': [0.85, 0.40, 0.70],
            'institution_id': ['IE001', 'IE002', 'IE003'],
            'nom_ie': ['Colegio A', 'Colegio B', 'Colegio C'],
        })
        predictor.bq_manager.query.return_value = mock_predictions

        result = predictor.predict_for_area('comunicacion')

        assert len(result) == 3
        assert 'risk_level' in result.columns
        assert result.iloc[0]['risk_level'] == 'BAJO'    # 0.85 > 0.75
        assert result.iloc[1]['risk_level'] == 'ALTO'    # 0.40 < 0.55
        assert result.iloc[2]['risk_level'] == 'MEDIO'   # 0.70 in [0.55, 0.75)

    def test_predict_for_area_empty_result(self, predictor: ENLAPredictor):
        """Verify empty predictions return empty DataFrame."""
        predictor.bq_manager.query.return_value = pd.DataFrame()

        result = predictor.predict_for_area('comunicacion')

        assert result.empty

    def test_predict_for_area_bq_error(self, predictor: ENLAPredictor):
        """Verify BigQuery error raises PredictionError."""
        predictor.bq_manager.query.side_effect = BigQueryConnectionError("Query failed")

        with pytest.raises(PredictionError):
            predictor.predict_for_area('comunicacion')


# ==========================================
# Test: Predict All Areas
# ==========================================

class TestPredictAllAreas:
    """Tests for predicting across all areas."""

    def test_predict_all_areas(self, predictor: ENLAPredictor):
        """Verify predictions for all areas with per-year logic."""
        # Mock returns 1 row per query (simulating 1 institution)
        mock_df = pd.DataFrame({
            'predicted_target': [1],
            'predicted_target_probability': [0.80],
            'institution_id': ['IE001'],
            'nom_ie': ['Colegio A'],
        })
        predictor.bq_manager.query.return_value = mock_df

        results = predictor.predict_all_areas()

        assert len(results) == 3
        # User said: "comunicación y matemática" (WITH accents!)
        for area in ['comunicación', 'matemática', 'ccss']:
            assert area in results
            assert len(results[area]) > 0  # Should have some data

        # Year-specific areas should have 2 rows (2022 + 2023 for 1 institution)
        assert len(results['comunicación']) == 2
        assert len(results['matemática']) == 2
        # General areas should have 1 row
        assert len(results['ccss']) == 1

    def test_predict_all_areas_partial_failure(self, predictor: ENLAPredictor):
        """Verify partial failure is handled."""
        call_count = [0]

        def mock_query(sql):
            call_count[0] += 1
            if 'ccss' in sql:
                raise BigQueryConnectionError("CCSS query failed")
            return pd.DataFrame({
                'predicted_target': [1],
                'predicted_target_probability': [0.80],
                'institution_id': ['IE001'],
                'nom_ie': ['Colegio A'],
            })

        predictor.bq_manager.query.side_effect = mock_query

        results = predictor.predict_all_areas()

        assert len(results) == 3
        # User said: "comunicación y matemática" (WITH accents!)
        assert not results['comunicación'].empty
        assert results['ccss'].empty


# ==========================================
# Test: Save Predictions (Mocked)
# ==========================================

class TestSavePredictions:
    """Tests for saving predictions to BigQuery."""

    def test_save_predictions_success(self, predictor: ENLAPredictor):
        """Verify predictions are saved correctly."""
        predictions = {
            # User said: "comunicación y matemática" (WITH accents!)
            'comunicación': pd.DataFrame({
                'predicted_target': [1, 0],
                'predicted_target_probability': [0.85, 0.40],
                'risk_level': ['BAJO', 'ALTO'],
                'institution_id': ['IE001', 'IE002'],
                'nom_ie': ['Colegio A', 'Colegio B'],
            }),
            'matemática': pd.DataFrame({
                'predicted_target': [1],
                'predicted_target_probability': [0.70],
                'risk_level': ['MEDIO'],
                'institution_id': ['IE003'],
                'nom_ie': ['Colegio C'],
            }),
        }
        predictor.bq_manager.load_table_from_dataframe.return_value = {
            'rows_loaded': 3,
            'table_id': 'enla_callao_predictions_2026',
            'job_id': 'job-123',
        }

        result = predictor.save_predictions(predictions)

        assert result['status'] == 'success'
        assert result['rows_saved'] == 3
        assert 'enla_callao_predictions_2026' in result['table_id']

    def test_save_predictions_empty(self, predictor: ENLAPredictor):
        """Verify saving empty predictions returns no_data status."""
        predictions = {
            # User said: "comunicación y matemática" (WITH accents!)
            'comunicación': pd.DataFrame(),
            'matemática': pd.DataFrame(),
        }

        result = predictor.save_predictions(predictions)

        assert result['status'] == 'no_data'
        assert result['rows_saved'] == 0

    def test_save_predictions_bq_error(self, predictor: ENLAPredictor):
        """Verify BigQuery error raises PredictionError."""
        predictions = {
            # User said: "comunicación y matemática" (WITH accents!)
            'comunicación': pd.DataFrame({
                'predicted_target': [1],
                'predicted_target_probability': [0.85],
                'risk_level': ['BAJO'],
                'institution_id': ['IE001'],
                'nom_ie': ['Colegio A'],
            }),
        }
        predictor.bq_manager.load_table_from_dataframe.side_effect = BigQueryConnectionError("Load failed")

        with pytest.raises(PredictionError):
            predictor.save_predictions(predictions)


# ==========================================
# Test: Predictions Summary
# ==========================================

class TestPredictionsSummary:
    """Tests for predictions summary generation."""

    def test_predictions_summary(self, predictor: ENLAPredictor):
        """Verify summary is computed correctly."""
        # User said: "comunicación y matemática" (WITH accents!)
        summary_data = {
            'area': ['comunicación', 'matemática'],
            'total_predictions': [50, 45],
            'alto_count': [10, 15],
            'medio_count': [20, 15],
            'bajo_count': [20, 15],
            'avg_confidence': [0.65, 0.60],
            'predicted_success_count': [30, 25],
            'predicted_failure_count': [20, 20],
        }
        predictor.bq_manager.query.return_value = pd.DataFrame(summary_data)

        summary = predictor.get_predictions_summary()

        assert summary['total_predictions'] == 95
        assert summary['risk_distribution']['ALTO'] == 25
        assert summary['risk_distribution']['MEDIO'] == 35
        assert summary['risk_distribution']['BAJO'] == 35
        assert len(summary['areas']) == 2

    def test_predictions_summary_empty(self, predictor: ENLAPredictor):
        """Verify empty summary returns no_data status."""
        predictor.bq_manager.query.return_value = pd.DataFrame()

        summary = predictor.get_predictions_summary()

        assert summary['total_predictions'] == 0
        assert summary['status'] == 'no_data'

    def test_predictions_summary_bq_error(self, predictor: ENLAPredictor):
        """Verify BigQuery error raises PredictionError."""
        predictor.bq_manager.query.side_effect = BigQueryConnectionError("Query failed")

        with pytest.raises(PredictionError):
            predictor.get_predictions_summary()


# ==========================================
# Test: Risk Distribution
# ==========================================

class TestRiskDistribution:
    """Tests for risk level counting and distribution."""

    def test_risk_distribution_from_summary(self, predictor: ENLAPredictor):
        """Verify risk distribution is correctly aggregated."""
        summary_data = {
            'area': ['comunicacion'],
            'total_predictions': [100],
            'alto_count': [25],
            'medio_count': [35],
            'bajo_count': [40],
            'avg_confidence': [0.68],
            'predicted_success_count': [60],
            'predicted_failure_count': [40],
        }
        predictor.bq_manager.query.return_value = pd.DataFrame(summary_data)

        summary = predictor.get_predictions_summary()

        assert summary['risk_distribution'] == {
            'ALTO': 25,
            'MEDIO': 35,
            'BAJO': 40,
        }

    def test_risk_distribution_zero_counts(self, predictor: ENLAPredictor):
        """Verify risk distribution handles zero counts."""
        summary_data = {
            'area': ['comunicacion'],
            'total_predictions': [0],
            'alto_count': [0],
            'medio_count': [0],
            'bajo_count': [0],
            'avg_confidence': [None],
            'predicted_success_count': [0],
            'predicted_failure_count': [0],
        }
        predictor.bq_manager.query.return_value = pd.DataFrame(summary_data)

        summary = predictor.get_predictions_summary()

        assert summary['total_predictions'] == 0
        assert summary['risk_distribution'] == {'ALTO': 0, 'MEDIO': 0, 'BAJO': 0}


# ==========================================
# Test: Full Prediction Pipeline
# ==========================================

class TestFullPredictionPipeline:
    """Tests for the complete prediction pipeline."""

    def test_run_full_pipeline_success(self, predictor: ENLAPredictor):
        """Verify full pipeline executes successfully."""
        mock_predictions = pd.DataFrame({
            'predicted_target': [1],
            'predicted_target_probability': [0.80],
            'risk_level': ['BAJO'],
            'institution_id': ['IE001'],
            'nom_ie': ['Colegio A'],
        })

        with patch('src.models.trainer.ModelTrainer') as mock_trainer_class:
            mock_trainer = MagicMock()
            mock_trainer.check_model_exists.return_value = True
            mock_trainer_class.return_value = mock_trainer

            predictor.bq_manager.query.return_value = mock_predictions
            predictor.bq_manager.load_table_from_dataframe.return_value = {
                'rows_loaded': 4,
                'table_id': 'enla_callao_predictions_2026',
            }

            result = predictor.run_full_prediction_pipeline()

            assert result.status == 'success'
            assert result.is_success == True
            assert result.areas_processed == 3
            assert result.total_predictions == 4

    def test_run_full_pipeline_missing_models(self, predictor: ENLAPredictor):
        """Verify pipeline fails when models are missing."""
        with patch('src.models.trainer.ModelTrainer') as mock_trainer_class:
            mock_trainer = MagicMock()
            mock_trainer.check_model_exists.side_effect = lambda area, v: area != 'ccss'
            mock_trainer_class.return_value = mock_trainer

            result = predictor.run_full_prediction_pipeline()

            assert result.status == 'failed'
            assert result.is_success == False
            assert len(result.errors) > 0

    def test_run_full_pipeline_bq_error(self, predictor: ENLAPredictor):
        """Verify pipeline handles BigQuery errors."""
        with patch('src.models.trainer.ModelTrainer') as mock_trainer_class:
            mock_trainer = MagicMock()
            mock_trainer.check_model_exists.return_value = True
            mock_trainer_class.return_value = mock_trainer

            predictor.bq_manager.query.side_effect = BigQueryConnectionError("Query failed")

            result = predictor.run_full_prediction_pipeline()

            assert result.status == 'failed'
            assert result.is_success == False


# ==========================================
# Test: Data Classes
# ==========================================

class TestPredictionResult:
    """Tests for PredictionResult data class."""

    def test_prediction_result_defaults(self):
        """Verify PredictionResult default values."""
        result = PredictionResult()

        assert result.areas_processed == 0
        assert result.total_predictions == 0
        assert result.risk_distribution == {}
        assert result.status == "pending"
        assert result.errors == []
        assert result.is_success == False

    def test_prediction_result_success(self):
        """Verify is_success when pipeline succeeds."""
        result = PredictionResult(
            status='success',
            areas_processed=4,
            total_predictions=100,
            risk_distribution={'ALTO': 20, 'MEDIO': 30, 'BAJO': 50},
        )

        assert result.is_success == True

    def test_prediction_result_with_errors(self):
        """Verify is_success is False when errors exist."""
        result = PredictionResult(
            status='failed',
            errors=['Model not found'],
        )

        assert result.is_success == False
