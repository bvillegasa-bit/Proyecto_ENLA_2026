"""Cloud Function orchestrator for ENLA 2026 Callao prediction pipeline.

Orchestrates the complete ML pipeline when triggered by Pub/Sub:
1. Ingest (Sprint 1): Excel → MongoDB
2. ETL (Sprint 2): MongoDB → BigQuery
3. Features (Sprint 3): Engineer features
4. Models (Sprint 4): Train + Predict
5. Alerts (Sprint 5): Generate + Send emails

Triggers:
- Pub/Sub topic `enla_predictions_ready` for full pipeline
- HTTP endpoint `/health` for health checks
"""

import json
import base64
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import functions_framework
from google.cloud import bigquery

# Import project modules
from src.ingestion.ingest_enla import ingest_enla_xlsx
from src.etl.transform import run_etl_pipeline
from src.features.engineer import run_feature_pipeline
from src.models.trainer import ModelTrainer
from src.models.predictor import ENLAPredictor, PredictionResult
from src.alerting.email_alert import AlertManager, AlertResult
from src.logging.setup import get_logger, setup_logging
from src.ingestion.config import settings

# Setup logging for Cloud Functions
setup_logging(
    log_level=settings.LOG_LEVEL,
    log_file='/tmp/enla_orchestrator.log',
    use_json=True
)

logger = get_logger('enla_orchestrator')


# ==========================================
# Pipeline Orchestration
# ==========================================

def run_full_pipeline(gcs_file_path: Optional[str] = None,
                      model_version: str = 'v1') -> Dict[str, Any]:
    """
    Execute the complete ENLA ML pipeline.

    Args:
        gcs_file_path: Optional GCS path to input Excel file
        model_version: Model version to use for training/prediction

    Returns:
        Dict with execution summary for each phase
    """
    pipeline_start = datetime.utcnow()
    results = {
        'pipeline_status': 'running',
        'start_time': pipeline_start.isoformat(),
        'phases': {},
        'errors': [],
    }

    logger.info("=" * 60)
    logger.info("ENLA 2026 Callao - Full Pipeline Started")
    logger.info(f"Model version: {model_version}")
    logger.info("=" * 60)

    try:
        # Phase 1: Ingestion (Excel → MongoDB)
        logger.info("Phase 1: Starting Ingestion...")
        try:
            if gcs_file_path:
                # TODO: Download from GCS first
                logger.info(f"Processing file: {gcs_file_path}")

            ingestion_result = ingest_enla_xlsx()
            results['phases']['ingestion'] = {
                'status': 'success',
                'records_ingested': ingestion_result.get('records_ingested', 0),
                'message': 'Ingestion completed successfully'
            }
            logger.info(f"Phase 1: Ingestion completed - Status: {results['phases']['ingestion']['status']}, Records: {results['phases']['ingestion']['records_ingested']}")

        except Exception as e:
            error_msg = f"Ingestion failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['phases']['ingestion'] = {
                'status': 'failed',
                'error': str(e)
            }
            results['errors'].append(error_msg)
            raise

        # Phase 2: ETL (MongoDB → BigQuery)
        logger.info("Phase 2: Starting ETL...")
        try:
            etl_result = run_etl_pipeline()
            results['phases']['etl'] = {
                'status': 'success',
                'rows_loaded': etl_result.get('total_rows_loaded', 0),
                'message': 'ETL completed successfully'
            }
            logger.info(f"Phase 2: ETL completed - Status: {results['phases']['etl']['status']}, Rows: {results['phases']['etl']['rows_loaded']}")

        except Exception as e:
            error_msg = f"ETL failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['phases']['etl'] = {
                'status': 'failed',
                'error': str(e)
            }
            results['errors'].append(error_msg)
            raise

        # Phase 3: Feature Engineering
        logger.info("Phase 3: Starting Feature Engineering...")
        try:
            feature_result = run_feature_pipeline()
            results['phases']['features'] = {
                'status': 'success',
                'features_created': feature_result.get('total_features', 0),
                'message': 'Feature engineering completed successfully'
            }
            logger.info(f"Phase 3: Feature Engineering completed - Status: {results['phases']['features']['status']}, Features: {results['phases']['features']['features_created']}")

        except Exception as e:
            error_msg = f"Feature engineering failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['phases']['features'] = {
                'status': 'failed',
                'error': str(e)
            }
            results['errors'].append(error_msg)
            raise

        # Phase 4: Model Training & Prediction
        logger.info("Phase 4: Starting Model Training & Prediction...")
        try:
            # Train models
            trainer = ModelTrainer()
            training_result = trainer.run_full_training_pipeline(model_version=model_version)

            # Generate predictions
            predictor = ENLAPredictor(model_version=model_version)
            prediction_result = predictor.run_full_prediction_pipeline(model_version=model_version)

            results['phases']['models'] = {
                'status': 'success' if prediction_result.is_success else 'partial',
                'areas_trained': training_result.areas_trained,
                'areas_predicted': prediction_result.areas_processed,
                'total_predictions': prediction_result.total_predictions,
                'risk_distribution': prediction_result.risk_distribution,
                'message': 'Model training and prediction completed'
            }
            logger.info(f"Phase 4: Model & Prediction completed - Status: {results['phases']['models']['status']}")

        except Exception as e:
            error_msg = f"Model training/prediction failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['phases']['models'] = {
                'status': 'failed',
                'error': str(e)
            }
            results['errors'].append(error_msg)
            raise

        # Phase 5: Alerting
        logger.info("Phase 5: Starting Alerting...")
        try:
            alert_manager = AlertManager()
            alert_result = alert_manager.trigger_alerts()

            results['phases']['alerts'] = {
                'status': 'success' if alert_result.is_success else 'failed',
                'alert_sent': alert_result.email_sent,
                'high_risk_count': alert_result.total_high_risk,
                'recipients': alert_result.recipients,
                'message': 'Alerting completed'
            }
            logger.info(f"Phase 5: Alerting completed - Status: {results['phases']['alerts']['status']}")

        except Exception as e:
            error_msg = f"Alerting failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['phases']['alerts'] = {
                'status': 'failed',
                'error': str(e)
            }
            results['errors'].append(error_msg)
            # Don't raise - alerting failure shouldn't fail entire pipeline

        # Final status
        pipeline_end = datetime.utcnow()
        duration = (pipeline_end - pipeline_start).total_seconds()

        if results['errors']:
            results['pipeline_status'] = 'completed_with_errors'
        else:
            results['pipeline_status'] = 'success'

        results['end_time'] = pipeline_end.isoformat()
        results['duration_seconds'] = duration

        logger.info("=" * 60)
        logger.info(f"ENLA Pipeline Completed - Status: {results['pipeline_status']}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info("=" * 60)

    except Exception as e:
        pipeline_end = datetime.utcnow()
        duration = (pipeline_end - pipeline_start).total_seconds()

        results['pipeline_status'] = 'failed'
        results['end_time'] = pipeline_end.isoformat()
        results['duration_seconds'] = duration

        logger.error("Pipeline failed", exc_info=True)
        logger.info("=" * 60)

    return results


# ==========================================
# Cloud Function Entry Points
# ==========================================

@functions_framework.cloud_event
def enla_pipeline_orchestrator(cloud_event: functions_framework.CloudEvent) -> Dict[str, Any]:
    """
    Main Cloud Function orchestrator for ENLA prediction pipeline.

    Triggered by Pub/Sub message when new data arrives in GCS.
    Executes: Ingest → ETL → Features → Train → Predict → Alert

    Args:
        cloud_event: CloudEvent with GCS file metadata or Pub/Sub message

    Returns:
        Dict with execution summary
    """
    logger.info(f"Cloud Function triggered - Event ID: {cloud_event.get('id')}")

    # Parse event data
    gcs_file_path = None
    model_version = 'v1'
    
    try:
        # Handle both CloudEvent objects and plain dicts (for testing)
        event_data = cloud_event.data if hasattr(cloud_event, 'data') else cloud_event.get('data', {})
        
        if event_data:
            # Decode Pub/Sub message if present
            if 'message' in event_data:
                message_data = event_data['message']
                if 'data' in message_data:
                    decoded_data = base64.b64decode(message_data['data']).decode('utf-8')
                    event_payload = json.loads(decoded_data)
                    
                    gcs_file_path = event_payload.get('gcs_file_path')
                    model_version = event_payload.get('model_version', 'v1')
                    
                    logger.info(f"Event payload parsed - GCS path: {gcs_file_path}, Version: {model_version}")

    except Exception as e:
        logger.warning(f"Failed to parse event data: {str(e)}")

    # Run the full pipeline
    results = run_full_pipeline(
        gcs_file_path=gcs_file_path,
        model_version=model_version
    )

    return results


@functions_framework.http
def enla_health_check(request) -> (Dict[str, Any], int):
    """
    Health check endpoint for the Cloud Function.

    Args:
        request: HTTP request object

    Returns:
        Tuple of (response JSON, HTTP status code)
    """
    logger.info("Health check requested")

    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'pipeline_phases': [
            'ingestion',
            'etl',
            'features',
            'models',
            'alerts'
        ]
    }

    return health_status, 200
