"""Model training module for ENLA 2026 Callao ML prediction pipeline.

Trains BigQuery ML Logistic Regression models for each subject area:
- comunicación, matemática, ccss, cyt

Uses temporal train/test split:
- Train: Years 2021, 2022 (historical data)
- Test: Year 2023 (holdout for validation)

Data flow:
    enla_callao_features (BigQuery) → BigQuery ML models → Model evaluation metrics
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import pandas as pd

from src.logging.setup import get_logger
from src.database.bigquery_client import BigQueryClientManager, BigQueryConnectionError
from src.features.engineer import AREAS, FEATURE_COLS
from src.ingestion.config import settings

logger = get_logger('model_trainer')


# ==========================================
# Custom Exceptions
# ==========================================

class ModelTrainingError(Exception):
    """Exception for model training errors."""
    pass


class ModelEvaluationError(Exception):
    """Exception for model evaluation errors."""
    pass


# ==========================================
# Data Classes
# ==========================================

from dataclasses import dataclass, field


@dataclass
class TrainingResult:
    """Result of training a single model."""
    area: str = ""
    model_name: str = ""
    status: str = "pending"
    training_stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Check if training completed without errors."""
        return len(self.errors) == 0 and self.status == "success"


@dataclass
class ModelTrainingPipelineResult:
    """Result of the complete model training pipeline."""
    models_trained: int = 0
    models_failed: int = 0
    total_duration_seconds: float = 0.0
    status: str = "pending"
    results: Dict[str, TrainingResult] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Check if all models trained successfully."""
        return len(self.errors) == 0 and self.models_failed == 0


# ==========================================
# ModelTrainer Class
# ==========================================

class ModelTrainer:
    """Trains BigQuery ML Logistic Regression models for ENLA prediction.

    Trains 4 independent models, one per area:
    - comunicación, matemática, ccss, cyt

    Uses temporal train/test split (2021-2022 train, 2023 test).
    """

    AREAS = AREAS  # ['comunicación', 'matemática', 'ccss', 'cyt']
    FEATURE_COLUMNS = FEATURE_COLS  # ['avg_score_2023', 'avg_score_2022', 'avg_score_2021', 'trend', 'variance']

    def __init__(self, bigquery_client: Optional[BigQueryClientManager] = None,
                 project_id: Optional[str] = None,
                 dataset_id: Optional[str] = None,
                 l2_reg: float = 0.1,
                 max_iterations: int = 20,
                 learn_rate: float = 0.1):
        """
        Initialize ModelTrainer.

        Args:
            bigquery_client: BigQueryClientManager instance. If None, uses global manager.
            project_id: GCP project ID. If None, reads from settings.
            dataset_id: BigQuery dataset ID. If None, reads from settings.
            l2_reg: L2 regularization parameter.
            max_iterations: Maximum training iterations.
            learn_rate: Learning rate for optimization.
        """
        self.bq_manager = bigquery_client
        self.project_id = project_id or settings.GCP_PROJECT_ID
        self.dataset_id = dataset_id or settings.GCP_DATASET_ID
        self.l2_reg = l2_reg
        self.max_iterations = max_iterations
        self.learn_rate = learn_rate

        logger.info(f"ModelTrainer initialized | project_id={self.project_id} dataset_id={self.dataset_id} areas={self.AREAS} l2_reg={self.l2_reg} max_iterations={self.max_iterations} learn_rate={self.learn_rate}")

    def _get_bq_manager(self) -> BigQueryClientManager:
        """Get or create BigQuery manager."""
        if self.bq_manager is None:
            from src.database.bigquery_client import get_bq_manager
            self.bq_manager = get_bq_manager(project_id=self.project_id)
        return self.bq_manager

    def _build_training_query(self, area: str) -> str:
        """
        Build the SQL query for training the model for a given area.

        Uses temporal split: 2021-2022 as train, 2023 as eval.

        Args:
            area: Subject area (comunicación, matemática, ccss, cyt)

        Returns:
            SQL string for CREATE MODEL statement
        """
        model_name = f"{self.project_id}.{self.dataset_id}.enla_model_{area}_v1"

        feature_cols = ", ".join(self.FEATURE_COLUMNS)

        query = f"""
        CREATE OR REPLACE MODEL `{model_name}`
        OPTIONS(
            model_type='logistic_reg',
            input_label_cols=['target'],
            data_split_method='CUSTOM',
            data_split_col='split',
            l2_reg={self.l2_reg},
            max_iterations={self.max_iterations},
            learn_rate={self.learn_rate},
            early_stop=True
        ) AS
        SELECT
            {feature_cols},
            target,
            CASE
                WHEN year_in_train THEN 'train'
                ELSE 'eval'
            END AS split
        FROM `{self.project_id}.{self.dataset_id}.enla_callao_features`
        WHERE area = '{area}'
        """

        logger.info(f"Training query built | area={area} model_name={model_name}")
        return query

    def _get_model_name(self, area: str, model_version: str = 'v1') -> str:
        """Get fully qualified model name."""
        return f"{self.project_id}.{self.dataset_id}.enla_model_{area}_{model_version}"

    def train_model_for_area(self, area: str) -> TrainingResult:
        """
        Train a single model for one area.

        Args:
            area: Subject area (comunicación, matemática, ccss, cyt)

        Returns:
            TrainingResult with training status and stats
        """
        result = TrainingResult(area=area, status="running")
        model_name = self._get_model_name(area)
        result.model_name = model_name

        logger.info(f"Starting model training for area: {area}")
        start_time = time.time()

        try:
            if area not in self.AREAS:
                raise ModelTrainingError(
                    f"Invalid area '{area}'. Must be one of {self.AREAS}"
                )

            bq_manager = self._get_bq_manager()

            # Build and execute training query
            training_query = self._build_training_query(area)
            logger.info(f"Executing training query | area={area}")

            job = bq_manager.query(training_query)
            job.result()  # Wait for training to complete

            duration = time.time() - start_time

            # Get training statistics from the job
            training_stats = {
                'job_id': job.job_id,
                'model_name': model_name,
                'duration_seconds': round(duration, 2),
                'total_bytes_processed': job.total_bytes_processed,
                'cache_hit': job.cache_hit,
            }

            result.status = "success"
            result.training_stats = training_stats

            logger.info(f"Model training completed for area '{area}' | duration={duration} job_id={job.job_id}")

        except BigQueryConnectionError as e:
            error_msg = f"BigQuery connection error training model for '{area}': {str(e)}"
            result.errors.append(error_msg)
            result.status = "failed"
            logger.error(error_msg, exc_info=True)

        except ModelTrainingError as e:
            error_msg = f"Training error for '{area}': {str(e)}"
            result.errors.append(error_msg)
            result.status = "failed"
            logger.error(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error training model for '{area}': {str(e)}"
            result.errors.append(error_msg)
            result.status = "failed"
            logger.error(error_msg, exc_info=True)

        return result

    def train_all_models(self) -> ModelTrainingPipelineResult:
        """
        Train all 4 models, one per area.

        Returns:
            ModelTrainingPipelineResult with per-area results
        """
        pipeline_result = ModelTrainingPipelineResult(status="running")
        pipeline_start = time.time()

        logger.info("=" * 60)
        logger.info("Starting Model Training Pipeline")
        logger.info(f"Areas: {self.AREAS}")
        logger.info("=" * 60)

        for area in self.AREAS:
            try:
                training_result = self.train_model_for_area(area)
                pipeline_result.results[area] = training_result

                if training_result.is_success:
                    pipeline_result.models_trained += 1
                else:
                    pipeline_result.models_failed += 1
                    pipeline_result.errors.extend(training_result.errors)

            except Exception as e:
                error_msg = f"Unexpected error training model for '{area}': {str(e)}"
                pipeline_result.errors.append(error_msg)
                pipeline_result.models_failed += 1
                pipeline_result.results[area] = TrainingResult(
                    area=area, status="failed", errors=[error_msg]
                )
                logger.error(error_msg, exc_info=True)

        pipeline_result.total_duration_seconds = round(time.time() - pipeline_start, 2)

        if pipeline_result.models_failed == 0:
            pipeline_result.status = "success"
        elif pipeline_result.models_trained > 0:
            pipeline_result.status = "partial"
        else:
            pipeline_result.status = "failed"

        logger.info(f"Model Training Pipeline completed | models_trained={pipeline_result.models_trained} models_failed={pipeline_result.models_failed} total_duration={pipeline_result.total_duration_seconds} status={pipeline_result.status}")

        return pipeline_result

    def evaluate_model(self, area: str, model_version: str = 'v1') -> dict:
        """
        Evaluate a trained model using ML.EVALUATE().

        Args:
            area: Subject area
            model_version: Model version string

        Returns:
            Dict with evaluation metrics: accuracy, precision, recall,
            f1_score, roc_auc, confusion_matrix
        """
        model_name = self._get_model_name(area, model_version)

        logger.info(f"Evaluating model: {model_name}")

        try:
            bq_manager = self._get_bq_manager()

            # Get evaluation metrics
            eval_query = f"""
            SELECT *
            FROM ML.EVALUATE(MODEL `{model_name}`)
            """

            eval_df = bq_manager.query(eval_query).to_dataframe()

            if eval_df.empty:
                raise ModelEvaluationError(f"No evaluation metrics returned for '{area}'")

            # Extract metrics from the first row
            row = eval_df.iloc[0]

            evaluation = {
                'area': area,
                'model_name': model_name,
                'accuracy': float(row.get('accuracy', 0.0)),
                'precision': float(row.get('precision', 0.0)),
                'recall': float(row.get('recall', 0.0)),
                'f1_score': float(row.get('f1_score', 0.0)),
                'roc_auc': float(row.get('roc_auc', 0.0)),
                'log_loss': float(row.get('log_loss', 0.0)),
                'confusion_matrix': {
                    'true_pos': int(row.get('true_positives', 0)),
                    'true_neg': int(row.get('true_negatives', 0)),
                    'false_pos': int(row.get('false_positives', 0)),
                    'false_neg': int(row.get('false_negatives', 0)),
                },
            }

            logger.info(f"Model evaluation for '{area}' complete | accuracy={evaluation['accuracy']} precision={evaluation['precision']} recall={evaluation['recall']} f1_score={evaluation['f1_score']}")

            return evaluation

        except BigQueryConnectionError as e:
            error_msg = f"BigQuery error evaluating model '{area}': {str(e)}"
            logger.error(error_msg)
            raise ModelEvaluationError(error_msg)

        except ModelEvaluationError:
            raise

        except Exception as e:
            error_msg = f"Unexpected error evaluating model '{area}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ModelEvaluationError(error_msg)

    def evaluate_all_models(self, model_version: str = 'v1') -> dict:
        """
        Evaluate all 4 models.

        Args:
            model_version: Model version string

        Returns:
            Dict mapping area name to evaluation metrics
        """
        results = {}

        logger.info("Evaluating all models")

        for area in self.AREAS:
            try:
                evaluation = self.evaluate_model(area, model_version)
                results[area] = evaluation
                logger.info(f"Area '{area}' evaluated | accuracy={evaluation['accuracy']}")
            except ModelEvaluationError as e:
                logger.error(f"Failed to evaluate '{area}': {str(e)}")
                results[area] = {'area': area, 'error': str(e)}

        return results

    def get_feature_weights(self, area: str, model_version: str = 'v1') -> pd.DataFrame:
        """
        Get feature coefficients using ML.WEIGHTS().

        Args:
            area: Subject area
            model_version: Model version string

        Returns:
            DataFrame with feature weights and processing methods
        """
        model_name = self._get_model_name(area, model_version)

        logger.info(f"Getting feature weights for model: {model_name}")

        try:
            bq_manager = self._get_bq_manager()

            weights_query = f"""
            SELECT *
            FROM ML.WEIGHTS(MODEL `{model_name}`)
            """

            weights_df = bq_manager.query(weights_query).to_dataframe()

            logger.info(f"Feature weights retrieved for '{area}' | features={len(weights_df)}")

            return weights_df

        except BigQueryConnectionError as e:
            error_msg = f"BigQuery error getting weights for '{area}': {str(e)}"
            logger.error(error_msg)
            raise ModelTrainingError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error getting weights for '{area}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ModelTrainingError(error_msg)

    def check_model_exists(self, area: str, model_version: str = 'v1') -> bool:
        """
        Check if a model exists in BigQuery.

        Args:
            area: Subject area
            model_version: Model version string

        Returns:
            True if model exists, False otherwise
        """
        model_name = self._get_model_name(area, model_version)

        logger.info(f"Checking if model exists: {model_name}")

        try:
            bq_manager = self._get_bq_manager()

            # Use INFORMATION_SCHEMA to check model existence
            check_query = f"""
            SELECT COUNT(*) as model_count
            FROM `{self.project_id}.{self.dataset_id}.INFORMATION_SCHEMA.MODELS`
            WHERE model_name = 'enla_model_{area}_{model_version}'
            """

            result_df = bq_manager.query(check_query).to_dataframe()

            exists = result_df.iloc[0]['model_count'] > 0

            logger.info(f"Model existence check for '{area}': {exists}")
            return exists

        except BigQueryConnectionError as e:
            logger.error(f"Error checking model existence for '{area}': {str(e)}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error checking model for '{area}': {str(e)}")
            return False

    def delete_model(self, area: str, model_version: str = 'v1') -> bool:
        """
        Delete a model from BigQuery.

        Args:
            area: Subject area
            model_version: Model version string

        Returns:
            True if model was deleted, False otherwise
        """
        model_name = self._get_model_name(area, model_version)

        logger.info(f"Deleting model: {model_name}")

        try:
            bq_manager = self._get_bq_manager()

            client = bq_manager
            client.delete_model(model_name, not_found_ok=True)

            logger.info(f"Model deleted: {model_name}")
            return True

        except BigQueryConnectionError as e:
            logger.error(f"Error deleting model '{area}': {str(e)}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error deleting model '{area}': {str(e)}")
            return False


# ==========================================
# Convenience Function
# ==========================================

def run_model_training(bigquery_client: Optional[BigQueryClientManager] = None,
                       l2_reg: float = 0.1,
                       max_iterations: int = 20,
                       learn_rate: float = 0.1) -> ModelTrainingPipelineResult:
    """
    Run the complete model training pipeline.

    Args:
        bigquery_client: BigQueryClientManager instance (optional)
        l2_reg: L2 regularization parameter
        max_iterations: Maximum training iterations
        learn_rate: Learning rate for optimization

    Returns:
        ModelTrainingPipelineResult with execution summary
    """
    trainer = ModelTrainer(
        bigquery_client=bigquery_client,
        l2_reg=l2_reg,
        max_iterations=max_iterations,
        learn_rate=learn_rate,
    )
    return trainer.train_all_models()
