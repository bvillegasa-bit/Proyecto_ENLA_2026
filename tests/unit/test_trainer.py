"""Unit tests for model training module (Sprint 4).

Tests cover:
- Training query building (SQL structure for each area)
- Model naming conventions
- Model training flow (mocked)
- Model evaluation result parsing (mocked)
- Feature weights retrieval (mocked)
- Model existence check
- Model deletion
- Training pipeline result handling
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch, PropertyMock

from src.models.trainer import (
    ModelTrainer,
    ModelTrainingError,
    ModelEvaluationError,
    TrainingResult,
    ModelTrainingPipelineResult,
    run_model_training,
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
def mock_query_job():
    """Create a mocked BigQuery query job."""
    job = MagicMock()
    job.job_id = 'test-job-123'
    job.total_bytes_processed = 1024
    job.cache_hit = False
    job.result.return_value = None
    return job


@pytest.fixture
def trainer(mock_bq_manager) -> ModelTrainer:
    """Create a ModelTrainer with mocked BQ client."""
    trainer = ModelTrainer.__new__(ModelTrainer)
    trainer.bq_manager = mock_bq_manager
    trainer.project_id = 'test-project'
    trainer.dataset_id = 'BI_ENLA'
    trainer.l2_reg = 0.1
    trainer.max_iterations = 20
    trainer.ls_init_learn_rate = 0.1  # Match constructor parameter name
    return trainer


# ==========================================
# Test: Training Query Building
# ==========================================

class TestBuildTrainingQuery:
    """Tests for SQL training query construction."""

    def test_build_training_query_comunicacion_general(self, trainer: ModelTrainer):
        """Verify SQL structure for comunicación area (general, no year)."""
        # User said: "comunicación y matemática" (WITH accents!)
        query = trainer._build_training_query('comunicación')

        assert 'CREATE OR REPLACE MODEL' in query
        assert 'enla_model_comunicación_v1' in query
        assert "model_type='logistic_reg'" in query
        assert "input_label_cols=['target']" in query
        assert "data_split_method='CUSTOM'" in query
        assert "data_split_col='split'" in query
        assert "l2_reg=0.1" in query
        assert "max_iterations=20" in query
        assert "ls_init_learn_rate=0.1" in query
        assert "early_stop=True" in query
        assert "WHERE area = 'comunicación'" in query
        # General query should NOT have year filter
        assert 'AND year' not in query

    def test_build_training_query_comunicacion_year_specific(self, trainer: ModelTrainer):
        """Verify SQL structure for comunicación area with year filter (2022)."""
        query = trainer._build_training_query('comunicación', year=2022)

        assert 'enla_model_comunicación_v1_2022' in query
        assert "WHERE area = 'comunicación'" in query
        assert 'AND year = 2022' in query

    def test_build_training_query_matematica_year_specific(self, trainer: ModelTrainer):
        """Verify SQL structure for matemática area with year filter (2023)."""
        # User said: "comunicación y matemática" (WITH accents!)
        query = trainer._build_training_query('matemática', year=2023)

        assert 'enla_model_matemática_v1_2023' in query
        assert "WHERE area = 'matemática'" in query
        assert 'AND year = 2023' in query

    def test_build_training_query_ccss_general(self, trainer: ModelTrainer):
        """Verify SQL structure for ccss area (general, all years)."""
        query = trainer._build_training_query('ccss')

        assert 'enla_model_ccss_v1' in query
        assert "WHERE area = 'ccss'" in query
        # ccss is general area, should NOT have year filter
        assert 'AND year' not in query

    def test_build_training_query_cyt_general(self, trainer: ModelTrainer):
        """Verify SQL structure for cyt area (general, all years)."""
        query = trainer._build_training_query('cyt')

        assert 'enla_model_cyt_v1' in query
        assert "WHERE area = 'cyt'" in query
        # cyt is general area, should NOT have year filter
        assert 'AND year' not in query

    def test_build_training_query_includes_features(self, trainer: ModelTrainer):
        """Verify all feature columns are included in the query."""
        # User said: "comunicación y matemática" (WITH accents!)
        query = trainer._build_training_query('comunicación')

        for feature in trainer.FEATURE_COLUMNS:
            assert feature in query, f"Missing feature column: {feature}"

    def test_build_training_query_includes_split_logic(self, trainer: ModelTrainer):
        """Verify temporal split logic is in the query."""
        # User said: "comunicación y matemática" (WITH accents!)
        query = trainer._build_training_query('comunicación')

        assert 'year_in_train' in query
        assert "'train'" in query
        assert "'eval'" in query

    def test_build_training_query_uses_correct_project(self, trainer: ModelTrainer):
        """Verify fully qualified model name uses correct project/dataset."""
        # User said: "comunicación y matemática" (WITH accents!)
        query = trainer._build_training_query('comunicación')

        assert 'test-project.BI_ENLA.enla_model_comunicación_v1' in query
        assert 'test-project.BI_ENLA.enla_callao_features' in query


# ==========================================
# Test: Model Name Conventions
# ==========================================

class TestModelNameConvention:
    """Tests for model naming patterns."""

    def test_model_name_v1(self, trainer: ModelTrainer):
        """Verify v1 model name format."""
        # User said: "comunicación y matemática" (WITH accents!)
        name = trainer._get_model_name('comunicación', 'v1')
        assert name == 'test-project.BI_ENLA.enla_model_comunicación_v1'

    def test_model_name_v2(self, trainer: ModelTrainer):
        """Verify v2 model name format."""
        # User said: "comunicación y matemática" (WITH accents!)
        name = trainer._get_model_name('matemática', 'v2')
        assert name == 'test-project.BI_ENLA.enla_model_matemática_v2'

    def test_model_name_default_version(self, trainer: ModelTrainer):
        """Verify default version is v1."""
        name = trainer._get_model_name('ccss')
        assert name == 'test-project.BI_ENLA.enla_model_ccss_v1'


# ==========================================
# Test: Model Training (Mocked)
# ==========================================

class TestTrainModelForArea:
    """Tests for single area model training."""

    def test_train_model_success(self, trainer: ModelTrainer):
        """Verify successful training returns correct result for year-specific area."""
        # User said: "comunicación y matemática" (WITH accents!)
        # Train for a specific year (2022)
        result = trainer.train_model_for_area('comunicación', year=2022)

        # User said: "comunicación y matemática" (WITH accents!)
        assert result.area == 'comunicación'
        assert result.status == 'success'
        assert result.is_success == True
        assert len(result.errors) == 0
        assert 'comunicación' in result.model_name
        assert '2022' in result.model_name  # Year-specific model
        assert 'job_id' in result.training_stats

    def test_train_model_all_years(self, trainer: ModelTrainer):
        """Verify training all years for year-specific area."""
        result = trainer.train_model_for_area('comunicación')  # No year = train all years

        assert result.area == 'comunicación'
        assert result.status == 'success'
        assert result.is_success == True
        assert 'years_trained' in result.training_stats
        assert result.training_stats['years_trained'] == [2022, 2023]

    def test_train_model_invalid_area(self, trainer: ModelTrainer):
        """Verify invalid area raises ModelTrainingError."""
        result = trainer.train_model_for_area('invalid_area')

        assert result.status == 'failed'
        assert result.is_success == False
        assert len(result.errors) > 0

    def test_train_model_bq_error(self, trainer: ModelTrainer):
        """Verify BigQuery error is handled gracefully."""
        trainer.bq_manager.query.side_effect = BigQueryConnectionError("Connection failed")

        # User said: "comunicación y matemática" (WITH accents!)
        result = trainer.train_model_for_area('comunicación')

        assert result.status == 'failed'
        assert result.is_success == False
        assert len(result.errors) > 0


# ==========================================
# Test: Train All Models
# ==========================================

class TestTrainAllModels:
    """Tests for training all models.

    Year-specific areas (comunicación, matemática): 2 models each (2022, 2023) = 4 models
    General areas (ccss): 1 model = 1 model
    Total: 5 models for 3 areas
    """

    def test_train_all_models_success(self, trainer: ModelTrainer, mock_query_job):
        """Verify all models train successfully (5 models total)."""
        trainer.bq_manager.query.return_value = mock_query_job

        result = trainer.train_all_models()

        assert result.status == 'success'
        # 2 year-specific areas * 2 years + 1 general area = 5 models
        assert result.models_trained == 5
        assert result.models_failed == 0
        assert result.is_success == True
        assert len(result.results) == 3  # 3 areas

    def test_train_all_models_partial_failure(self, trainer: ModelTrainer, mock_query_job):
        """Verify partial failure is handled correctly."""
        call_count = [0]

        def mock_query(sql):
            call_count[0] += 1
            if 'ccss' in sql:
                raise BigQueryConnectionError("CCSS training failed")
            return mock_query_job

        trainer.bq_manager.query.side_effect = mock_query

        result = trainer.train_all_models()

        assert result.status == 'partial'
        # comunición (2) + matemática (2) = 4 trained, ccss (1) failed
        assert result.models_trained == 4
        assert result.models_failed == 1
        assert result.is_success == False

    def test_train_all_models_duration_recorded(self, trainer: ModelTrainer, mock_query_job):
        """Verify total duration is recorded."""
        # Make time pass between calls by tracking call count
        call_count = [0]
        original_time = __import__('time').time

        def mock_time():
            call_count[0] += 1
            return original_time() + call_count[0]  # Simulate 1 second per call

        trainer.bq_manager.query.return_value = mock_query_job

        with patch('time.time', side_effect=mock_time):
            result = trainer.train_all_models()

        assert result.total_duration_seconds > 0
        assert isinstance(result.total_duration_seconds, float)


# ==========================================
# Test: Model Evaluation (Mocked)
# ==========================================

class TestEvaluateModel:
    """Tests for model evaluation."""

    def test_evaluate_model_success(self, trainer: ModelTrainer):
        """Verify evaluation metrics are parsed correctly."""
        eval_data = {
            'precision': [0.80],
            'recall': [0.75],
            'accuracy': [0.78],
            'f1_score': [0.77],
            'roc_auc': [0.82],
            'log_loss': [0.45],
            'true_positives': [25],
            'true_negatives': [30],
            'false_positives': [5],
            'false_negatives': [8],
        }
        mock_job = MagicMock()
        mock_job.to_dataframe.return_value = pd.DataFrame(eval_data)
        trainer.bq_manager.query.return_value = mock_job

        result = trainer.evaluate_model('comunicacion')

        assert result['area'] == 'comunicacion'
        assert result['accuracy'] == 0.78
        assert result['precision'] == 0.80
        assert result['recall'] == 0.75
        assert result['f1_score'] == 0.77
        assert result['roc_auc'] == 0.82
        assert result['confusion_matrix']['true_pos'] == 25
        assert result['confusion_matrix']['true_neg'] == 30
        assert result['confusion_matrix']['false_pos'] == 5
        assert result['confusion_matrix']['false_neg'] == 8

    def test_evaluate_model_empty_result(self, trainer: ModelTrainer):
        """Verify empty evaluation result raises error."""
        mock_job = MagicMock()
        mock_job.to_dataframe.return_value = pd.DataFrame()
        trainer.bq_manager.query.return_value = mock_job

        with pytest.raises(ModelEvaluationError):
            trainer.evaluate_model('comunicacion')

    def test_evaluate_model_bq_error(self, trainer: ModelTrainer):
        """Verify BigQuery error raises ModelEvaluationError."""
        trainer.bq_manager.query.side_effect = BigQueryConnectionError("Query failed")

        with pytest.raises(ModelEvaluationError):
            trainer.evaluate_model('comunicacion')


# ==========================================
# Test: Feature Weights (Mocked)
# ==========================================

class TestFeatureWeights:
    """Tests for feature weights retrieval."""

    def test_feature_weights_success(self, trainer: ModelTrainer):
        """Verify feature weights are returned as DataFrame."""
        weights_data = {
            'input': ['avg_score_2023', 'avg_score_2022', 'avg_score_2021', 'trend', 'variance', '__INTERCEPT__'],
            'weight': [0.3, 0.25, 0.2, 0.15, 0.1, 0.0],
            'processing_method': ['none'] * 5 + [''],
        }
        mock_job = MagicMock()
        mock_job.to_dataframe.return_value = pd.DataFrame(weights_data)
        trainer.bq_manager.query.return_value = mock_job

        result = trainer.get_feature_weights('comunicacion')

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 6
        assert 'weight' in result.columns

    def test_feature_weights_bq_error(self, trainer: ModelTrainer):
        """Verify BigQuery error raises ModelTrainingError."""
        trainer.bq_manager.query.side_effect = BigQueryConnectionError("Weights query failed")

        with pytest.raises(ModelTrainingError):
            trainer.get_feature_weights('comunicacion')


# ==========================================
# Test: Model Existence Check
# ==========================================

class TestCheckModelExists:
    """Tests for model existence checking."""

    def test_model_exists_true(self, trainer: ModelTrainer):
        """Verify returns True when model exists."""
        mock_job = MagicMock()
        mock_job.to_dataframe.return_value = pd.DataFrame({'model_count': [1]})
        trainer.bq_manager.query.return_value = mock_job

        result = trainer.check_model_exists('comunicacion')

        assert result == True

    def test_model_exists_false(self, trainer: ModelTrainer):
        """Verify returns False when model does not exist."""
        mock_job = MagicMock()
        mock_job.to_dataframe.return_value = pd.DataFrame({'model_count': [0]})
        trainer.bq_manager.query.return_value = mock_job

        result = trainer.check_model_exists('comunicacion')

        assert result == False

    def test_model_exists_error_returns_false(self, trainer: ModelTrainer):
        """Verify returns False on error (graceful degradation)."""
        trainer.bq_manager.query.side_effect = BigQueryConnectionError("Connection failed")

        result = trainer.check_model_exists('comunicacion')

        assert result == False


# ==========================================
# Test: Model Deletion
# ==========================================

class TestDeleteModel:
    """Tests for model deletion."""

    def test_delete_model_success(self, trainer: ModelTrainer):
        """Verify model deletion succeeds."""
        trainer.bq_manager.delete_model.return_value = None

        result = trainer.delete_model('comunicacion')

        assert result == True
        trainer.bq_manager.delete_model.assert_called_once()

    def test_delete_model_not_found_ok(self, trainer: ModelTrainer):
        """Verify deletion with not_found_ok=True."""
        trainer.bq_manager.delete_model.return_value = None

        trainer.delete_model('comunicacion')

        call_args = trainer.bq_manager.delete_model.call_args
        assert call_args.kwargs.get('not_found_ok', call_args[1].get('not_found_ok')) == True

    def test_delete_model_error_returns_false(self, trainer: ModelTrainer):
        """Verify returns False on deletion error."""
        trainer.bq_manager.delete_model.side_effect = Exception("Delete failed")

        result = trainer.delete_model('comunicacion')

        assert result == False


# ==========================================
# Test: Data Classes
# ==========================================

class TestDataClasses:
    """Tests for result data classes."""

    def test_training_result_defaults(self):
        """Verify TrainingResult default values."""
        result = TrainingResult()

        assert result.area == ""
        assert result.model_name == ""
        assert result.status == "pending"
        assert result.training_stats == {}
        assert result.errors == []
        assert result.is_success == False

    def test_training_result_success(self):
        """Verify is_success is True when successful."""
        result = TrainingResult(
            area='comunicacion',
            model_name='test-model',
            status='success',
            training_stats={'accuracy': 0.80},
        )

        assert result.is_success == True

    def test_training_result_with_errors(self):
        """Verify is_success is False when errors exist."""
        result = TrainingResult(
            area='comunicacion',
            status='failed',
            errors=['Training failed'],
        )

        assert result.is_success == False

    def test_pipeline_result_defaults(self):
        """Verify ModelTrainingPipelineResult default values."""
        result = ModelTrainingPipelineResult()

        assert result.models_trained == 0
        assert result.models_failed == 0
        assert result.total_duration_seconds == 0.0
        assert result.status == "pending"
        assert result.results == {}
        assert result.errors == []

    def test_pipeline_result_success(self):
        """Verify is_success when all models trained."""
        result = ModelTrainingPipelineResult(
            status='success',
            models_trained=4,
            models_failed=0,
        )

        assert result.is_success == True

    def test_pipeline_result_failed(self):
        """Verify is_success is False when models failed."""
        result = ModelTrainingPipelineResult(
            status='failed',
            models_trained=0,
            models_failed=4,
            errors=['Error 1', 'Error 2'],
        )

        assert result.is_success == False
