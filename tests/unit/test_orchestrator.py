"""Unit tests for the Cloud Function orchestrator (Sprint 5).

Tests the enla_pipeline_orchestrator Cloud Function including:
- Health check endpoint
- Pipeline orchestration
- Error handling
- Pub/Sub event processing
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import base64
from datetime import datetime


class TestHealthCheck(unittest.TestCase):
    """Test health check endpoint."""

    def test_health_check_returns_healthy(self):
        """Test health check returns healthy status."""
        from gcp.functions.enla_orchestrator.main import enla_health_check

        response, status_code = enla_health_check(None)

        self.assertEqual(status_code, 200)
        self.assertEqual(response['status'], 'healthy')
        self.assertIn('timestamp', response)
        self.assertIn('version', response)
        self.assertIn('pipeline_phases', response)
        self.assertEqual(len(response['pipeline_phases']), 5)

    def test_health_check_timestamp_format(self):
        """Test health check timestamp is valid ISO format."""
        from gcp.functions.enla_orchestrator.main import enla_health_check

        response, _ = enla_health_check(None)

        # Should be valid ISO format
        timestamp = response['timestamp']
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        self.assertIsInstance(parsed, datetime)


class TestRunFullPipeline(unittest.TestCase):
    """Test run_full_pipeline function."""

    @patch('gcp.functions.enla_orchestrator.main.AlertManager')
    @patch('gcp.functions.enla_orchestrator.main.ENLAPredictor')
    @patch('gcp.functions.enla_orchestrator.main.ModelTrainer')
    @patch('gcp.functions.enla_orchestrator.main.run_feature_pipeline')
    @patch('gcp.functions.enla_orchestrator.main.run_etl_pipeline')
    @patch('gcp.functions.enla_orchestrator.main.ingest_enla_xlsx')
    def test_run_full_pipeline_success(
        self, mock_ingest, mock_etl, mock_features,
        mock_trainer, mock_predictor, mock_alert
    ):
        """Test successful full pipeline execution."""
        from gcp.functions.enla_orchestrator.main import run_full_pipeline

        # Setup mocks
        mock_ingest.return_value = {'records_ingested': 100}
        mock_etl.return_value = {'total_rows_loaded': 100}
        mock_features.return_value = {'total_features': 50}

        # Mock trainer
        mock_trainer_instance = Mock()
        mock_trainer_instance.run_full_training_pipeline.return_value = Mock(
            areas_trained=4,
            status='success'
        )
        mock_trainer.return_value = mock_trainer_instance

        # Mock predictor
        mock_predictor_instance = Mock()
        mock_predictor_instance.run_full_prediction_pipeline.return_value = Mock(
            areas_processed=4,
            total_predictions=200,
            risk_distribution={'ALTO': 20, 'MEDIO': 80, 'BAJO': 100},
            status='success',
            is_success=True
        )
        mock_predictor.return_value = mock_predictor_instance

        # Mock alert manager
        mock_alert_instance = Mock()
        mock_alert_instance.trigger_alerts.return_value = Mock(
            email_sent=True,
            total_high_risk=20,
            recipients=['test@example.com'],
            status='success',
            is_success=True
        )
        mock_alert.return_value = mock_alert_instance

        # Run pipeline
        results = run_full_pipeline()

        # Verify
        self.assertEqual(results['pipeline_status'], 'success')
        self.assertIn('ingestion', results['phases'])
        self.assertIn('etl', results['phases'])
        self.assertIn('features', results['phases'])
        self.assertIn('models', results['phases'])
        self.assertIn('alerts', results['phases'])
        self.assertEqual(len(results['errors']), 0)

    @patch('gcp.functions.enla_orchestrator.main.run_feature_pipeline')
    @patch('gcp.functions.enla_orchestrator.main.run_etl_pipeline')
    @patch('gcp.functions.enla_orchestrator.main.ingest_enla_xlsx')
    def test_run_full_pipeline_ingestion_failure(
        self, mock_ingest, mock_etl, mock_features
    ):
        """Test pipeline handles ingestion failure."""
        from gcp.functions.enla_orchestrator.main import run_full_pipeline

        # Setup mock to raise exception
        mock_ingest.side_effect = Exception("Ingestion failed")

        results = run_full_pipeline()

        self.assertEqual(results['pipeline_status'], 'failed')
        self.assertIn('ingestion', results['phases'])
        self.assertEqual(results['phases']['ingestion']['status'], 'failed')

    @patch('gcp.functions.enla_orchestrator.main.AlertManager')
    @patch('gcp.functions.enla_orchestrator.main.ENLAPredictor')
    @patch('gcp.functions.enla_orchestrator.main.ModelTrainer')
    @patch('gcp.functions.enla_orchestrator.main.run_feature_pipeline')
    @patch('gcp.functions.enla_orchestrator.main.run_etl_pipeline')
    @patch('gcp.functions.enla_orchestrator.main.ingest_enla_xlsx')
    def test_run_full_pipeline_partial_failure(
        self, mock_ingest, mock_etl, mock_features,
        mock_trainer, mock_predictor, mock_alert
    ):
        """Test pipeline continues after non-critical phase failure."""
        from gcp.functions.enla_orchestrator.main import run_full_pipeline

        # Setup mocks - all succeed except alerts
        mock_ingest.return_value = {'records_ingested': 100}
        mock_etl.return_value = {'total_rows_loaded': 100}
        mock_features.return_value = {'total_features': 50}

        mock_trainer_instance = Mock()
        mock_trainer_instance.run_full_training_pipeline.return_value = Mock(
            areas_trained=4, status='success'
        )
        mock_trainer.return_value = mock_trainer_instance

        mock_predictor_instance = Mock()
        mock_predictor_instance.run_full_prediction_pipeline.return_value = Mock(
            areas_processed=4,
            total_predictions=200,
            risk_distribution={'ALTO': 20},
            status='success',
            is_success=True
        )
        mock_predictor.return_value = mock_predictor_instance

        # Alert fails but shouldn't fail entire pipeline
        mock_alert_instance = Mock()
        mock_alert_instance.trigger_alerts.side_effect = Exception("Alert failed")
        mock_alert.return_value = mock_alert_instance

        results = run_full_pipeline()

        # Pipeline should complete with errors
        self.assertEqual(results['pipeline_status'], 'completed_with_errors')
        self.assertIn('alerts', results['phases'])
        self.assertEqual(results['phases']['alerts']['status'], 'failed')


class TestCloudFunctionEntryPoint(unittest.TestCase):
    """Test enla_pipeline_orchestrator Cloud Function entry point."""

    @patch('gcp.functions.enla_orchestrator.main.run_full_pipeline')
    def test_orchestrator_with_pubsub_event(self, mock_run_pipeline):
        """Test Cloud Function handles Pub/Sub event."""
        from gcp.functions.enla_orchestrator.main import enla_pipeline_orchestrator

        # Setup mock
        mock_run_pipeline.return_value = {
            'pipeline_status': 'success',
            'start_time': datetime.utcnow().isoformat(),
            'end_time': datetime.utcnow().isoformat(),
            'phases': {}
        }

        # Create mock CloudEvent
        payload = {
            'gcs_file_path': 'gs://bucket/file.xlsx',
            'model_version': 'v2'
        }
        encoded_payload = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')

        mock_event = {
            'id': 'test-event-id',
            'data': {
                'message': {
                    'data': encoded_payload
                }
            }
        }

        # Call function
        results = enla_pipeline_orchestrator(mock_event)

        # Verify
        self.assertEqual(results['pipeline_status'], 'success')
        mock_run_pipeline.assert_called_once_with(
            gcs_file_path='gs://bucket/file.xlsx',
            model_version='v2'
        )

    @patch('gcp.functions.enla_orchestrator.main.run_full_pipeline')
    def test_orchestrator_with_empty_event(self, mock_run_pipeline):
        """Test Cloud Function handles empty event data."""
        from gcp.functions.enla_orchestrator.main import enla_pipeline_orchestrator

        mock_run_pipeline.return_value = {
            'pipeline_status': 'success',
            'phases': {}
        }

        mock_event = {
            'id': 'test-event-id',
            'data': {}
        }

        results = enla_pipeline_orchestrator(mock_event)

        self.assertEqual(results['pipeline_status'], 'success')

    @patch('gcp.functions.enla_orchestrator.main.run_full_pipeline')
    def test_orchestrator_pipeline_failure(self, mock_run_pipeline):
        """Test Cloud Function handles pipeline failure."""
        from gcp.functions.enla_orchestrator.main import enla_pipeline_orchestrator

        mock_run_pipeline.return_value = {
            'pipeline_status': 'failed',
            'errors': ['Pipeline failed'],
            'phases': {'ingestion': {'status': 'failed'}}
        }

        mock_event = {
            'id': 'test-event-id',
            'data': {}
        }

        results = enla_pipeline_orchestrator(mock_event)

        self.assertEqual(results['pipeline_status'], 'failed')


class TestPipelineDuration(unittest.TestCase):
    """Test pipeline duration tracking."""

    @patch('gcp.functions.enla_orchestrator.main.AlertManager')
    @patch('gcp.functions.enla_orchestrator.main.ENLAPredictor')
    @patch('gcp.functions.enla_orchestrator.main.ModelTrainer')
    @patch('gcp.functions.enla_orchestrator.main.run_feature_pipeline')
    @patch('gcp.functions.enla_orchestrator.main.run_etl_pipeline')
    @patch('gcp.functions.enla_orchestrator.main.ingest_enla_xlsx')
    def test_pipeline_includes_duration(
        self, mock_ingest, mock_etl, mock_features,
        mock_trainer, mock_predictor, mock_alert
    ):
        """Test pipeline results include duration."""
        from gcp.functions.enla_orchestrator.main import run_full_pipeline

        # Setup all mocks to succeed
        mock_ingest.return_value = {'records_ingested': 10}
        mock_etl.return_value = {'total_rows_loaded': 10}
        mock_features.return_value = {'total_features': 5}

        mock_trainer_instance = Mock()
        mock_trainer_instance.run_full_training_pipeline.return_value = Mock(
            areas_trained=1, status='success'
        )
        mock_trainer.return_value = mock_trainer_instance

        mock_predictor_instance = Mock()
        mock_predictor_instance.run_full_prediction_pipeline.return_value = Mock(
            areas_processed=1, total_predictions=10,
            risk_distribution={}, status='success', is_success=True
        )
        mock_predictor.return_value = mock_predictor_instance

        mock_alert_instance = Mock()
        mock_alert_instance.trigger_alerts.return_value = Mock(
            email_sent=True, status='success', is_success=True
        )
        mock_alert.return_value = mock_alert_instance

        results = run_full_pipeline()

        self.assertIn('duration_seconds', results)
        self.assertGreater(results['duration_seconds'], 0)
        self.assertIn('start_time', results)
        self.assertIn('end_time', results)


class TestPipelinePhases(unittest.TestCase):
    """Test individual pipeline phases are tracked."""

    @patch('gcp.functions.enla_orchestrator.main.AlertManager')
    @patch('gcp.functions.enla_orchestrator.main.ENLAPredictor')
    @patch('gcp.functions.enla_orchestrator.main.ModelTrainer')
    @patch('gcp.functions.enla_orchestrator.main.run_feature_pipeline')
    @patch('gcp.functions.enla_orchestrator.main.run_etl_pipeline')
    @patch('gcp.functions.enla_orchestrator.main.ingest_enla_xlsx')
    def test_all_phases_tracked(
        self, mock_ingest, mock_etl, mock_features,
        mock_trainer, mock_predictor, mock_alert
    ):
        """Test all 5 phases are tracked in results."""
        from gcp.functions.enla_orchestrator.main import run_full_pipeline

        # Setup mocks
        mock_ingest.return_value = {'records_ingested': 10}
        mock_etl.return_value = {'total_rows_loaded': 10}
        mock_features.return_value = {'total_features': 5}

        mock_trainer_instance = Mock()
        mock_trainer_instance.run_full_training_pipeline.return_value = Mock(
            areas_trained=1, status='success'
        )
        mock_trainer.return_value = mock_trainer_instance

        mock_predictor_instance = Mock()
        mock_predictor_instance.run_full_prediction_pipeline.return_value = Mock(
            areas_processed=1, total_predictions=10,
            risk_distribution={}, status='success', is_success=True
        )
        mock_predictor.return_value = mock_predictor_instance

        mock_alert_instance = Mock()
        mock_alert_instance.trigger_alerts.return_value = Mock(
            email_sent=True, status='success', is_success=True
        )
        mock_alert.return_value = mock_alert_instance

        results = run_full_pipeline()

        expected_phases = ['ingestion', 'etl', 'features', 'models', 'alerts']
        for phase in expected_phases:
            self.assertIn(phase, results['phases'])
            self.assertEqual(results['phases'][phase]['status'], 'success')


if __name__ == '__main__':
    unittest.main()
