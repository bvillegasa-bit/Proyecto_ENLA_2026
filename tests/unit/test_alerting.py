"""Unit tests for the alerting module (Sprint 5).

Tests the AlertManager class including:
- Querying high-risk institutions
- Generating summaries and HTML reports
- Sending emails via SendGrid
- Logging alerts to BigQuery
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import pandas as pd
from datetime import datetime, timezone
from typing import List, Dict, Any

from src.alerting.email_alert import (
    AlertManager,
    AlertResult,
    AlertError,
    EmailSendError,
)
from src.alerting.schemas import ALERT_LOG_SCHEMA, ALERT_SCHEMA_REGISTRY


class TestAlertManagerInitialization(unittest.TestCase):
    """Test AlertManager initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        with patch('src.alerting.email_alert.settings') as mock_settings:
            mock_settings.GCP_PROJECT_ID = 'test-project'
            mock_settings.GCP_DATASET_ID = 'BI_ENLA'
            mock_settings.SENDGRID_API_KEY = ''
            mock_settings.ALERT_EMAIL_FROM = 'test@example.com'
            mock_settings.ALERT_EMAIL_TO = []

            manager = AlertManager()

            self.assertEqual(manager.project_id, 'test-project')
            self.assertEqual(manager.dataset_id, 'BI_ENLA')
            self.assertEqual(manager.email_from, 'test@example.com')
            self.assertEqual(manager.email_to, [])

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        manager = AlertManager(
            project_id='custom-project',
            dataset_id='CUSTOM_DS',
            sendgrid_api_key='SG.test-key',
            email_from='custom@example.com',
            email_to=['admin@example.com']
        )

        self.assertEqual(manager.project_id, 'custom-project')
        self.assertEqual(manager.dataset_id, 'CUSTOM_DS')
        self.assertEqual(manager.sendgrid_api_key, 'SG.test-key')
        self.assertEqual(manager.email_from, 'custom@example.com')
        self.assertEqual(manager.email_to, ['admin@example.com'])

    def test_area_recommendations_exist(self):
        """Test that all areas have recommendations."""
        manager = AlertManager()

        expected_areas = ['comunicacion', 'matematica', 'ccss', 'cyt']
        for area in expected_areas:
            self.assertIn(area, manager.AREA_RECOMMENDATIONS)
            self.assertIsInstance(manager.AREA_RECOMMENDATIONS[area], list)
            self.assertGreater(len(manager.AREA_RECOMMENDATIONS[area]), 0)

    def test_area_display_names_exist(self):
        """Test that all areas have display names."""
        manager = AlertManager()

        expected_areas = ['comunicacion', 'matematica', 'ccss', 'cyt']
        for area in expected_areas:
            self.assertIn(area, manager.AREA_DISPLAY_NAMES)
            self.assertIsInstance(manager.AREA_DISPLAY_NAMES[area], str)
            self.assertGreater(len(manager.AREA_DISPLAY_NAMES[area]), 0)


class TestGetHighRiskInstitutions(unittest.TestCase):
    """Test get_high_risk_institutions method."""

    @patch('src.alerting.email_alert.AlertManager._get_bq_manager')
    def test_get_high_risk_with_data(self, mock_get_manager):
        """Test querying high-risk institutions returns data."""
        # Setup mock
        mock_manager = Mock()
        mock_client = Mock()
        mock_manager.connect = Mock(return_value=None)
        mock_manager.query = Mock(return_value=pd.DataFrame({
            'prediction_id': ['id1', 'id2'],
            'area': ['comunicacion', 'matematica'],
            'institution_id': ['INST001', 'INST002'],
            'nom_ie': ['IE San Martín', 'IE Bolivar'],
            'predicted_success': [0, 0],
            'confidence': [0.45, 0.50],
            'risk_level': ['ALTO', 'ALTO'],
            'model_version': ['v1', 'v1'],
            'prediction_ts': [datetime.now(timezone.utc), datetime.now(timezone.utc)]
        }))
        mock_get_manager.return_value = mock_manager

        manager = AlertManager(project_id='test-project', dataset_id='BI_ENLA')
        result = manager.get_high_risk_institutions()

        self.assertEqual(len(result), 2)
        self.assertIn('nom_ie', result.columns)
        mock_manager.query.assert_called_once()

    @patch('src.alerting.email_alert.AlertManager._get_bq_manager')
    def test_get_high_risk_empty(self, mock_get_manager):
        """Test querying when no high-risk institutions."""
        mock_manager = Mock()
        mock_manager.connect = Mock(return_value=None)
        mock_manager.query = Mock(return_value=pd.DataFrame())
        mock_get_manager.return_value = mock_manager

        manager = AlertManager(project_id='test-project', dataset_id='BI_ENLA')
        result = manager.get_high_risk_institutions()

        self.assertTrue(result.empty)

    @patch('src.alerting.email_alert.AlertManager._get_bq_manager')
    def test_get_high_risk_with_area_filter(self, mock_get_manager):
        """Test querying with area filter."""
        mock_manager = Mock()
        mock_manager.connect = Mock(return_value=None)
        mock_manager.query = Mock(return_value=pd.DataFrame({
            'prediction_id': ['id1'],
            'area': ['comunicacion'],
            'institution_id': ['INST001'],
            'nom_ie': ['IE San Martín'],
            'predicted_success': [0],
            'confidence': [0.45],
            'risk_level': ['ALTO'],
            'model_version': ['v1'],
            'prediction_ts': [datetime.now(timezone.utc)]
        }))
        mock_get_manager.return_value = mock_manager

        manager = AlertManager(project_id='test-project', dataset_id='BI_ENLA')
        result = manager.get_high_risk_institutions(area='comunicacion')

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['area'], 'comunicacion')

        # Verify query contains area filter
        call_args = mock_manager.query.call_args[0][0]
        self.assertIn('comunicacion', call_args)

    @patch('src.alerting.email_alert.AlertManager._get_bq_manager')
    def test_get_high_risk_bigquery_error(self, mock_get_manager):
        """Test handling BigQuery connection error."""
        mock_manager = Mock()
        mock_manager.connect = Mock(side_effect=Exception("Connection failed"))
        mock_get_manager.return_value = mock_manager

        manager = AlertManager(project_id='test-project', dataset_id='BI_ENLA')

        with self.assertRaises(AlertError):
            manager.get_high_risk_institutions()


class TestGenerateSummary(unittest.TestCase):
    """Test generate_summary method."""

    def test_generate_summary_with_data(self):
        """Test summary generation with high-risk data."""
        manager = AlertManager()

        df = pd.DataFrame({
            'prediction_id': ['id1', 'id2', 'id3'],
            'area': ['comunicacion', 'comunicacion', 'matematica'],
            'nom_ie': ['IE 1', 'IE 2', 'IE 3'],
            'confidence': [0.45, 0.50, 0.55],
            'risk_level': ['ALTO', 'ALTO', 'ALTO'],
            'model_version': ['v1', 'v1', 'v1'],
        })

        summary = manager.generate_summary(df)

        self.assertEqual(summary['total_high_risk'], 3)
        self.assertIn('comunicacion', summary['by_area'])
        self.assertIn('matematica', summary['by_area'])
        self.assertEqual(summary['by_area']['comunicacion']['count'], 2)
        self.assertEqual(summary['by_area']['matematica']['count'], 1)

    def test_generate_summary_empty(self):
        """Test summary generation with empty DataFrame."""
        manager = AlertManager()

        summary = manager.generate_summary(pd.DataFrame())

        self.assertEqual(summary['total_high_risk'], 0)
        self.assertEqual(summary['by_area'], {})
        self.assertIsNone(summary['avg_confidence'])

    def test_generate_summary_with_confidence(self):
        """Test summary includes average confidence."""
        manager = AlertManager()

        df = pd.DataFrame({
            'prediction_id': ['id1', 'id2'],
            'area': ['comunicacion', 'matematica'],
            'confidence': [0.45, 0.55],
        })

        summary = manager.generate_summary(df)

        self.assertIsNotNone(summary['avg_confidence'])
        self.assertAlmostEqual(summary['avg_confidence'], 0.50, places=2)


class TestGenerateHtmlReport(unittest.TestCase):
    """Test generate_html_report method."""

    def test_generate_html_report_with_data(self):
        """Test HTML report generation with data."""
        manager = AlertManager()

        df = pd.DataFrame({
            'prediction_id': ['id1'],
            'area': ['comunicacion'],
            'institution_id': ['INST001'],
            'nom_ie': ['IE San Martín'],
            'confidence': [0.45],
            'risk_level': ['ALTO'],
            'model_version': ['v1'],
        })

        summary = {
            'total_high_risk': 1,
            'by_area': {
                'comunicacion': {
                    'display_name': 'Comunicación',
                    'count': 1
                }
            },
            'avg_confidence': 0.45,
            'model_version': 'v1',
        }

        html = manager.generate_html_report(df, summary)

        self.assertIn('ALERTA ENLA 2026', html)
        self.assertIn('IE San Martín', html)
        self.assertIn('Comunicación', html)
        self.assertIn('45.0%', html)

    def test_generate_html_report_empty(self):
        """Test HTML report generation with no data."""
        manager = AlertManager()

        summary = {
            'total_high_risk': 0,
            'by_area': {},
            'avg_confidence': None,
            'model_version': None,
        }

        html = manager.generate_html_report(pd.DataFrame(), summary)

        self.assertIn('ALERTA ENLA 2026', html)
        self.assertIn('No se encontraron', html)

    def test_generate_html_report_contains_recommendations(self):
        """Test HTML report includes pedagogical recommendations."""
        manager = AlertManager()

        df = pd.DataFrame({
            'prediction_id': ['id1'],
            'area': ['comunicacion'],
            'nom_ie': ['IE Test'],
            'confidence': [0.45],
        })

        summary = {
            'total_high_risk': 1,
            'by_area': {'comunicacion': {'display_name': 'Comunicación', 'count': 1}},
            'avg_confidence': 0.45,
            'model_version': 'v1',
        }

        html = manager.generate_html_report(df, summary)

        # Check recommendations are present
        self.assertIn('Recomendaciones Pedagógicas', html)
        self.assertIn('Comunicación', html)
        self.assertIn('comprensión lectora', html.lower())

    def test_generate_html_report_valid_html(self):
        """Test generated HTML is well-formed."""
        manager = AlertManager()

        df = pd.DataFrame({
            'prediction_id': ['id1'],
            'area': ['comunicacion'],
            'nom_ie': ['IE Test'],
            'confidence': [0.45],
        })

        summary = {
            'total_high_risk': 1,
            'by_area': {},
            'avg_confidence': 0.45,
            'model_version': 'v1',
        }

        html = manager.generate_html_report(df, summary)

        # Basic HTML validation
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('<html>', html)
        self.assertIn('</html>', html)
        self.assertIn('<head>', html)
        self.assertIn('</head>', html)
        self.assertIn('<body>', html)
        self.assertIn('</body>', html)


class TestSendEmail(unittest.TestCase):
    """Test send_email method."""

    @patch('src.alerting.email_alert.SendGridAPIClient')
    def test_send_email_success(self, mock_sg_class):
        """Test successful email sending."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.headers = {'X-Message-Id': 'test-message-id'}
        mock_client.send = Mock(return_value=mock_response)
        mock_sg_class.return_value = mock_client

        manager = AlertManager(
            sendgrid_api_key='SG.test-key',
            email_from='test@example.com'
        )

        result = manager.send_email(
            to_emails=['recipient@example.com'],
            subject='Test Alert',
            html_content='<html>Test</html>'
        )

        self.assertEqual(result['status'], 'sent')
        self.assertEqual(result['status_code'], 202)
        mock_client.send.assert_called_once()

    def test_send_email_no_api_key(self):
        """Test email sending fails without API key."""
        manager = AlertManager(sendgrid_api_key='')

        with self.assertRaises(EmailSendError) as context:
            manager.send_email(
                to_emails=['recipient@example.com'],
                subject='Test',
                html_content='<html>Test</html>'
            )

        self.assertIn('not configured', str(context.exception))

    def test_send_email_no_recipients(self):
        """Test email sending fails without recipients."""
        manager = AlertManager(sendgrid_api_key='SG.test-key')

        with self.assertRaises(EmailSendError) as context:
            manager.send_email(
                to_emails=[],
                subject='Test',
                html_content='<html>Test</html>'
            )

        self.assertIn('No recipients', str(context.exception))

    @patch('src.alerting.email_alert.SendGridAPIClient')
    def test_send_email_sendgrid_error(self, mock_sg_class):
        """Test handling SendGrid API error."""
        mock_client = Mock()
        mock_client.send = Mock(side_effect=Exception("SendGrid error"))
        mock_sg_class.return_value = mock_client

        manager = AlertManager(
            sendgrid_api_key='SG.test-key',
            email_from='test@example.com'
        )

        with self.assertRaises(EmailSendError):
            manager.send_email(
                to_emails=['recipient@example.com'],
                subject='Test',
                html_content='<html>Test</html>'
            )


class TestLogAlert(unittest.TestCase):
    """Test log_alert method."""

    @patch('src.alerting.email_alert.AlertManager._get_bq_manager')
    def test_log_alert_success(self, mock_get_manager):
        """Test successful alert logging."""
        mock_manager = Mock()
        mock_manager.connect = Mock(return_value=None)
        mock_manager.create_dataset = Mock()
        mock_manager.create_table = Mock()
        mock_manager.load_table_from_dataframe = Mock(return_value={'rows_loaded': 1})
        mock_get_manager.return_value = mock_manager

        manager = AlertManager(project_id='test-project', dataset_id='BI_ENLA')

        manager.log_alert(
            alert_type='high_risk',
            area=None,
            recipients=['test@example.com'],
            subject='Test Alert',
            status='sent',
        )

        mock_manager.load_table_from_dataframe.assert_called_once()

    @patch('src.alerting.email_alert.AlertManager._get_bq_manager')
    def test_log_alert_with_error(self, mock_get_manager):
        """Test logging alert with error message."""
        mock_manager = Mock()
        mock_manager.connect = Mock(return_value=None)
        mock_manager.create_dataset = Mock()
        mock_manager.create_table = Mock()
        mock_manager.load_table_from_dataframe = Mock(return_value={'rows_loaded': 1})
        mock_get_manager.return_value = mock_manager

        manager = AlertManager(project_id='test-project', dataset_id='BI_ENLA')

        manager.log_alert(
            alert_type='system_error',
            area='comunicacion',
            recipients=[],
            subject='Error Alert',
            status='failed',
            error_message='Connection timeout'
        )

        # Verify the call was made
        mock_manager.load_table_from_dataframe.assert_called_once()


class TestTriggerAlerts(unittest.TestCase):
    """Test trigger_alerts method."""

    @patch('src.alerting.email_alert.AlertManager.get_high_risk_institutions')
    @patch('src.alerting.email_alert.AlertManager.send_email')
    @patch('src.alerting.email_alert.AlertManager.log_alert')
    def test_trigger_alerts_with_data(self, mock_log, mock_send, mock_get_high_risk):
        """Test complete alert pipeline with high-risk data."""
        # Setup mocks
        mock_get_high_risk.return_value = pd.DataFrame({
            'prediction_id': ['id1'],
            'area': ['comunicacion'],
            'nom_ie': ['IE Test'],
            'confidence': [0.45],
        })

        mock_send.return_value = {
            'status': 'sent',
            'status_code': 202,
            'message_id': 'test-id',
            'error': None
        }

        manager = AlertManager(
            sendgrid_api_key='SG.test-key',
            email_from='test@example.com',
            email_to=['recipient@example.com']
        )

        result = manager.trigger_alerts()

        self.assertTrue(result.email_sent)
        self.assertEqual(result.total_high_risk, 1)
        self.assertEqual(result.status, 'success')
        mock_send.assert_called_once()
        mock_log.assert_called_once()

    @patch('src.alerting.email_alert.AlertManager.get_high_risk_institutions')
    def test_trigger_alerts_no_data(self, mock_get_high_risk):
        """Test alert pipeline with no high-risk institutions."""
        mock_get_high_risk.return_value = pd.DataFrame()

        manager = AlertManager(email_to=['recipient@example.com'])

        result = manager.trigger_alerts()

        self.assertEqual(result.total_high_risk, 0)
        self.assertEqual(result.status, 'no_data')
        self.assertFalse(result.email_sent)

    @patch('src.alerting.email_alert.AlertManager.get_high_risk_institutions')
    def test_trigger_alerts_no_recipients(self, mock_get_high_risk):
        """Test alert pipeline with no recipients configured."""
        mock_get_high_risk.return_value = pd.DataFrame({
            'prediction_id': ['id1'],
            'area': ['comunicacion'],
            'nom_ie': ['IE Test'],
        })

        manager = AlertManager(email_to=[])

        result = manager.trigger_alerts()

        self.assertEqual(result.status, 'skipped')
        self.assertFalse(result.email_sent)


class TestAlertResult(unittest.TestCase):
    """Test AlertResult dataclass."""

    def test_alert_result_defaults(self):
        """Test AlertResult default values."""
        result = AlertResult()

        self.assertEqual(result.alert_id, "")
        self.assertEqual(result.total_high_risk, 0)
        self.assertEqual(result.areas_affected, [])
        self.assertFalse(result.email_sent)
        self.assertEqual(result.status, "pending")

    def test_alert_result_is_success(self):
        """Test AlertResult is_success property."""
        result = AlertResult(email_sent=True, status='success')
        self.assertTrue(result.is_success)

        result.email_sent = False
        self.assertFalse(result.is_success)

        result.email_sent = True
        result.status = 'failed'
        self.assertFalse(result.is_success)


class TestAlertSchemas(unittest.TestCase):
    """Test alert schema definitions."""

    def test_alert_log_schema_exists(self):
        """Test ALERT_LOG_SCHEMA is defined."""
        self.assertIsNotNone(ALERT_LOG_SCHEMA)
        self.assertIsInstance(ALERT_LOG_SCHEMA, list)
        self.assertGreater(len(ALERT_LOG_SCHEMA), 0)

    def test_alert_log_schema_fields(self):
        """Test ALERT_LOG_SCHEMA has required fields."""
        field_names = [field.name for field in ALERT_LOG_SCHEMA]

        required_fields = [
            'alert_id', 'alert_type', 'area', 'recipients',
            'subject', 'send_timestamp', 'status', 'error_message', 'created_at'
        ]

        for field in required_fields:
            self.assertIn(field, field_names)

    def test_alert_schema_registry(self):
        """Test ALERT_SCHEMA_REGISTRY contains expected tables."""
        self.assertIn('enla_alert_log', ALERT_SCHEMA_REGISTRY)

    def test_get_alert_schema(self):
        """Test get_alert_schema function."""
        from src.alerting.schemas import get_alert_schema

        schema = get_alert_schema('enla_alert_log')
        self.assertIsInstance(schema, list)
        self.assertGreater(len(schema), 0)

    def test_get_alert_schema_invalid(self):
        """Test get_alert_schema with invalid table name."""
        from src.alerting.schemas import get_alert_schema

        with self.assertRaises(KeyError):
            get_alert_schema('invalid_table')


if __name__ == '__main__':
    unittest.main()
