"""Prediction module for ENLA 2026 Callao ML prediction pipeline.

Generates predictions using trained BigQuery ML models and stores
results in the predictions table.

Data flow:
    enla_callao_features (BigQuery) → ML.PREDICT() → enla_callao_predictions_2026
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import pandas as pd

from src.logging.setup import get_logger
from src.database.bigquery_client import BigQueryClientManager, BigQueryConnectionError
from src.features.engineer import AREAS
from src.models.schemas import PREDICTIONS_SCHEMA
from src.ingestion.config import settings

logger = get_logger('model_predictor')


# ==========================================
# Custom Exceptions
# ==========================================

class PredictionError(Exception):
    """Exception for prediction errors."""
    pass


# ==========================================
# Data Classes
# ==========================================

from dataclasses import dataclass, field


@dataclass
class PredictionResult:
    """Result of the complete prediction pipeline."""
    areas_processed: int = 0
    total_predictions: int = 0
    risk_distribution: Dict[str, int] = field(default_factory=dict)
    status: str = "pending"
    errors: List[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Check if pipeline completed without errors."""
        return len(self.errors) == 0 and self.status == "success"


# ==========================================
# ENLAPredictor Class
# ==========================================

class ENLAPredictor:
    """Generates predictions using trained BigQuery ML models.

    For each area:
    1. Query features from enla_callao_features
    2. Run ML.PREDICT()
    3. Extract confidence and classify risk level
    4. Store predictions in enla_callao_predictions_2026
    """

    RISK_THRESHOLDS = {
        'ALTO': 0.55,
        'MEDIO': 0.75,
    }

    def __init__(self, bigquery_client: Optional[BigQueryClientManager] = None,
                 project_id: Optional[str] = None,
                 dataset_id: Optional[str] = None,
                 model_version: str = 'v1'):
        """
        Initialize ENLAPredictor.

        Args:
            bigquery_client: BigQueryClientManager instance. If None, uses global manager.
            project_id: GCP project ID. If None, reads from settings.
            dataset_id: BigQuery dataset ID. If None, reads from settings.
            model_version: Model version string to use for predictions.
        """
        self.bq_manager = bigquery_client
        self.project_id = project_id or settings.GCP_PROJECT_ID
        self.dataset_id = dataset_id or settings.GCP_DATASET_ID
        self.model_version = model_version

        logger.info("ENLAPredictor initialized",
                    project_id=self.project_id,
                    dataset_id=self.dataset_id,
                    model_version=self.model_version,
                    risk_thresholds=self.RISK_THRESHOLDS)

    def _get_bq_manager(self) -> BigQueryClientManager:
        """Get or create BigQuery manager."""
        if self.bq_manager is None:
            from src.database.bigquery_client import get_bq_manager
            self.bq_manager = get_bq_manager(project_id=self.project_id)
        return self.bq_manager

    def _get_model_name(self, area: str) -> str:
        """Get fully qualified model name."""
        return f"{self.project_id}.{self.dataset_id}.enla_model_{area}_{self.model_version}"

    def _build_prediction_query(self, area: str) -> str:
        """
        Build ML.PREDICT() SQL query for an area.

        Args:
            area: Subject area (comunicacion, matematica, ccss, cyt)

        Returns:
            SQL string for ML.PREDICT() statement
        """
        model_name = self._get_model_name(area)

        query = f"""
        SELECT
            *
        FROM ML.PREDICT(
            MODEL `{model_name}`,
            (
                SELECT *
                FROM `{self.project_id}.{self.dataset_id}.enla_callao_features`
                WHERE area = '{area}'
            )
        )
        """

        logger.info("Prediction query built", area=area, model_name=model_name)
        return query

    def predict_for_area(self, area: str) -> pd.DataFrame:
        """
        Generate predictions for one area.

        Args:
            area: Subject area (comunicacion, matematica, ccss, cyt)

        Returns:
            DataFrame with predictions including predicted_success, confidence

        Raises:
            PredictionError: If prediction fails
        """
        logger.info(f"Generating predictions for area: {area}")

        try:
            bq_manager = self._get_bq_manager()
            bq_manager.connect()

            prediction_query = self._build_prediction_query(area)
            predictions_df = bq_manager.query(prediction_query)

            if predictions_df.empty:
                logger.warning(f"No predictions generated for area '{area}'")
                return pd.DataFrame()

            # Add risk classification
            predictions_df['risk_level'] = predictions_df['predicted_' + 'target_probability'].apply(
                lambda conf: self.classify_risk(float(conf)) if pd.notna(conf) else 'DESCONOCIDO'
            )

            # Add area column if not present
            if 'area' not in predictions_df.columns:
                predictions_df['area'] = area

            # Rename probability column for consistency
            prob_col = 'predicted_target_probability'
            if prob_col in predictions_df.columns:
                predictions_df['confidence'] = predictions_df[prob_col].astype(float)

            logger.info(f"Predictions generated for '{area}'",
                        count=len(predictions_df))

            return predictions_df

        except BigQueryConnectionError as e:
            error_msg = f"BigQuery error predicting for '{area}': {str(e)}"
            logger.error(error_msg)
            raise PredictionError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error predicting for '{area}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise PredictionError(error_msg)

    def classify_risk(self, confidence: float) -> str:
        """
        Classify risk level from confidence.

        Args:
            confidence: Prediction confidence/probability [0, 1]

        Returns:
            Risk level: 'ALTO' (<0.55), 'MEDIO' (0.55-0.75), 'BAJO' (>0.75)
        """
        if confidence < self.RISK_THRESHOLDS['ALTO']:
            return 'ALTO'
        elif confidence < self.RISK_THRESHOLDS['MEDIO']:
            return 'MEDIO'
        else:
            return 'BAJO'

    def predict_all_areas(self) -> Dict[str, pd.DataFrame]:
        """
        Generate predictions for all 4 areas.

        Returns:
            Dict mapping area name to DataFrame with predictions
        """
        results = {}
        errors = []

        logger.info("Starting predictions for all areas")

        for area in AREAS:
            try:
                predictions_df = self.predict_for_area(area)
                results[area] = predictions_df
                logger.info(f"Area '{area}' predictions: {len(predictions_df)} records")
            except PredictionError as e:
                error_msg = f"Prediction error for '{area}': {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                results[area] = pd.DataFrame()
            except Exception as e:
                error_msg = f"Unexpected error for '{area}': {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
                results[area] = pd.DataFrame()

        logger.info("All area predictions generated",
                    areas_with_data=sum(1 for df in results.values() if not df.empty),
                    errors=len(errors))

        return results

    def save_predictions(self, predictions: Dict[str, pd.DataFrame]) -> dict:
        """
        Save all predictions to enla_callao_predictions_2026 table.

        Args:
            predictions: Dict mapping area name to DataFrame with predictions

        Returns:
            Dict with save statistics (rows_saved, table_id)
        """
        logger.info("Saving predictions to BigQuery")

        try:
            bq_manager = self._get_bq_manager()
            bq_manager.connect()
            bq_manager.create_dataset(self.dataset_id, location=settings.GCP_LOCATION)

            all_records = []
            prediction_ts = datetime.now(timezone.utc)

            for area, df in predictions.items():
                if df.empty:
                    logger.warning(f"No predictions to save for area '{area}'")
                    continue

                for _, row in df.iterrows():
                    # Extract confidence - try multiple column names
                    confidence = None
                    for col_name in ['confidence', 'predicted_target_probability', 'predicted_target']:
                        if col_name in row.index:
                            val = row[col_name]
                            if pd.notna(val):
                                confidence = float(val)
                            break

                    predicted_success = None
                    if 'predicted_target' in row.index:
                        val = row['predicted_target']
                        if pd.notna(val):
                            predicted_success = int(val)

                    risk_level = row.get('risk_level', None)
                    if risk_level is None and confidence is not None:
                        risk_level = self.classify_risk(confidence)

                    institution_id = row.get('institution_id', row.get('id_ie', ''))
                    nom_ie = row.get('nom_ie', '')

                    record = {
                        'prediction_id': str(uuid.uuid4()),
                        'area': area,
                        'institution_id': institution_id,
                        'nom_ie': nom_ie,
                        'predicted_success': predicted_success,
                        'confidence': confidence,
                        'risk_level': risk_level,
                        'model_version': self.model_version,
                        'prediction_ts': prediction_ts,
                        'created_at': datetime.now(timezone.utc),
                    }
                    all_records.append(record)

            if not all_records:
                logger.warning("No prediction records to save")
                return {'rows_saved': 0, 'table_id': '', 'status': 'no_data'}

            predictions_df = pd.DataFrame(all_records)

            logger.info("Loading predictions to BigQuery", rows=len(predictions_df))

            stats = bq_manager.load_table_from_dataframe(
                self.dataset_id,
                'enla_callao_predictions_2026',
                predictions_df,
                write_disposition='WRITE_TRUNCATE',
                schema=PREDICTIONS_SCHEMA,
            )

            logger.info("Predictions saved successfully", rows_saved=stats.get('rows_loaded'))

            return {
                'rows_saved': stats.get('rows_loaded', len(all_records)),
                'table_id': stats.get('table_id', ''),
                'job_id': stats.get('job_id', ''),
                'status': 'success',
            }

        except BigQueryConnectionError as e:
            error_msg = f"BigQuery error saving predictions: {str(e)}"
            logger.error(error_msg)
            raise PredictionError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error saving predictions: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise PredictionError(error_msg)

    def get_predictions_summary(self) -> dict:
        """
        Get summary of saved predictions from BigQuery.

        Returns:
            Dict with count by area, count by risk_level, overall stats
        """
        logger.info("Getting predictions summary")

        try:
            bq_manager = self._get_bq_manager()
            bq_manager.connect()

            summary_query = f"""
            SELECT
                area,
                COUNT(*) as total_predictions,
                SUM(CASE WHEN risk_level = 'ALTO' THEN 1 ELSE 0 END) as alto_count,
                SUM(CASE WHEN risk_level = 'MEDIO' THEN 1 ELSE 0 END) as medio_count,
                SUM(CASE WHEN risk_level = 'BAJO' THEN 1 ELSE 0 END) as bajo_count,
                AVG(confidence) as avg_confidence,
                SUM(CASE WHEN predicted_success = 1 THEN 1 ELSE 0 END) as predicted_success_count,
                SUM(CASE WHEN predicted_success = 0 THEN 1 ELSE 0 END) as predicted_failure_count
            FROM `{self.project_id}.{self.dataset_id}.enla_callao_predictions_2026`
            GROUP BY area
            ORDER BY area
            """

            summary_df = bq_manager.query(summary_query)

            if summary_df.empty:
                return {'total_predictions': 0, 'areas': [], 'status': 'no_data'}

            overall_total = int(summary_df['total_predictions'].sum())
            overall_alto = int(summary_df['alto_count'].sum())
            overall_medio = int(summary_df['medio_count'].sum())
            overall_bajo = int(summary_df['bajo_count'].sum())

            summary = {
                'total_predictions': overall_total,
                'risk_distribution': {
                    'ALTO': overall_alto,
                    'MEDIO': overall_medio,
                    'BAJO': overall_bajo,
                },
                'areas': [],
                'model_version': self.model_version,
            }

            for _, row in summary_df.iterrows():
                area_info = {
                    'area': row['area'],
                    'total_predictions': int(row['total_predictions']),
                    'risk_distribution': {
                        'ALTO': int(row['alto_count']),
                        'MEDIO': int(row['medio_count']),
                        'BAJO': int(row['bajo_count']),
                    },
                    'avg_confidence': float(row['avg_confidence']) if pd.notna(row['avg_confidence']) else None,
                    'predicted_success': int(row['predicted_success_count']),
                    'predicted_failure': int(row['predicted_failure_count']),
                }
                summary['areas'].append(area_info)

            logger.info("Predictions summary retrieved",
                        total_predictions=overall_total,
                        risk_distribution=summary['risk_distribution'])

            return summary

        except BigQueryConnectionError as e:
            error_msg = f"BigQuery error getting predictions summary: {str(e)}"
            logger.error(error_msg)
            raise PredictionError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error getting predictions summary: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise PredictionError(error_msg)

    def run_full_prediction_pipeline(self, model_version: str = 'v1') -> PredictionResult:
        """
        Complete prediction pipeline:
        1. Verify all models exist
        2. Generate predictions for all areas
        3. Save to BigQuery
        4. Return summary

        Args:
            model_version: Model version to use

        Returns:
            PredictionResult with pipeline summary
        """
        result = PredictionResult(status="running")

        logger.info("=" * 60)
        logger.info("Starting Full Prediction Pipeline")
        logger.info(f"Model version: {model_version}")
        logger.info("=" * 60)

        try:
            # Update model version if different
            if model_version != self.model_version:
                self.model_version = model_version

            # Step 1: Verify all models exist
            from src.models.trainer import ModelTrainer
            trainer = ModelTrainer(
                bigquery_client=self.bq_manager,
                project_id=self.project_id,
                dataset_id=self.dataset_id,
            )

            missing_models = []
            for area in AREAS:
                if not trainer.check_model_exists(area, self.model_version):
                    missing_models.append(area)

            if missing_models:
                raise PredictionError(
                    f"Models not found for areas: {missing_models}. "
                    f"Run training first."
                )

            logger.info("All models verified")

            # Step 2: Generate predictions for all areas
            predictions = self.predict_all_areas()

            # Check for failed predictions
            failed_areas = [area for area, df in predictions.items() if df.empty]
            if failed_areas:
                result.errors.append(f"No predictions for areas: {failed_areas}")

            # Step 3: Save to BigQuery
            save_stats = self.save_predictions(predictions)

            if save_stats.get('status') != 'success':
                result.errors.append(f"Failed to save predictions: {save_stats}")

            # Step 4: Build summary
            result.areas_processed = sum(
                1 for df in predictions.values() if not df.empty
            )
            result.total_predictions = save_stats.get('rows_saved', 0)

            # Compute risk distribution from predictions
            risk_dist = {'ALTO': 0, 'MEDIO': 0, 'BAJO': 0}
            for area, df in predictions.items():
                if not df.empty and 'risk_level' in df.columns:
                    for level in risk_dist:
                        risk_dist[level] += int((df['risk_level'] == level).sum())
            result.risk_distribution = risk_dist

            if not result.errors:
                result.status = "success"
            elif result.areas_processed == 0:
                result.status = "failed"
            else:
                result.status = "partial"

            logger.info("Prediction Pipeline completed",
                        areas_processed=result.areas_processed,
                        total_predictions=result.total_predictions,
                        risk_distribution=result.risk_distribution,
                        status=result.status)

        except PredictionError as e:
            error_msg = f"Prediction pipeline error: {str(e)}"
            result.errors.append(error_msg)
            result.status = "failed"
            logger.error(error_msg)

        except Exception as e:
            error_msg = f"Unexpected pipeline error: {str(e)}"
            result.errors.append(error_msg)
            result.status = "failed"
            logger.error(error_msg, exc_info=True)

        return result


# ==========================================
# Convenience Function
# ==========================================

def run_prediction_pipeline(bigquery_client: Optional[BigQueryClientManager] = None,
                            model_version: str = 'v1') -> PredictionResult:
    """
    Run the complete prediction pipeline.

    Args:
        bigquery_client: BigQueryClientManager instance (optional)
        model_version: Model version to use

    Returns:
        PredictionResult with execution summary
    """
    predictor = ENLAPredictor(
        bigquery_client=bigquery_client,
        model_version=model_version,
    )
    return predictor.run_full_prediction_pipeline(model_version=model_version)
