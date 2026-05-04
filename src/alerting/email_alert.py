"""Email alerting module for ENLA 2026 Callao prediction pipeline.

Manages alerts based on prediction results. Queries high-risk institutions
from BigQuery, generates HTML email reports with pedagogical recommendations,
sends notifications via SendGrid, and logs all alert activity.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import pandas as pd

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent

from src.logging.setup import get_logger
from src.database.bigquery_client import BigQueryClientManager, BigQueryConnectionError
from src.alerting.schemas import ALERT_LOG_SCHEMA
from src.ingestion.config import settings

logger = get_logger('alerting')


# ==========================================
# Custom Exceptions
# ==========================================

class AlertError(Exception):
    """Exception for general alerting errors."""
    pass


class EmailSendError(Exception):
    """Exception for email sending errors."""
    pass


# ==========================================
# Data Classes
# ==========================================

@dataclass
class AlertResult:
    """Result of the alert triggering pipeline."""
    alert_id: str = ""
    total_high_risk: int = 0
    areas_affected: List[str] = field(default_factory=list)
    email_sent: bool = False
    recipients: List[str] = field(default_factory=list)
    alert_type: str = "high_risk"
    status: str = "pending"
    error_message: Optional[str] = None
    send_timestamp: Optional[datetime] = None

    @property
    def is_success(self) -> bool:
        """Check if alert was sent successfully."""
        return self.email_sent and self.status == "success"


# ==========================================
# AlertManager Class
# ==========================================

class AlertManager:
    """
    Manages ENLA prediction alerts.

    Responsibilities:
    1. Query high-risk predictions from BigQuery
    2. Generate HTML email reports
    3. Send emails via SendGrid
    4. Log alerts to BigQuery
    """

    AREA_RECOMMENDATIONS = {
        'comunicación': [
            "Implementar talleres de comprensión lectora intensivos",
            "Reforzar habilidades de escritura y producción de textos",
            "Promover lectura diaria con materiales contextualizados"
        ],
        'matemática': [
            "Fortalecer resolución de problemas con situaciones reales",
            "Implementar material concreto para conceptos abstractos",
            "Practicar razonamiento lógico-matemático semanalmente"
        ],
        'ccss': [
            "Integrar proyectos interdisciplinarios con contexto local",
            "Usar metodologías activas (ABP, estudio de casos)",
            "Fomentar pensamiento crítico con debates guiados"
        ],
        'cyt': [
            "Incorporar experimentación práctica en laboratorio",
            "Vincular contenidos científicos con problemas ambientales locales",
            "Promover indagación científica con metodología de proyectos"
        ]
    }

    AREA_DISPLAY_NAMES = {
        'comunicación': 'Comunicación',
        'matemática': 'Matemática',
        'ccss': 'Ciencias Sociales',
        'cyt': 'Ciencia y Tecnología'
    }
    # NOTE: Keys now use accents to match user's data: 'comunicación', 'matemática'

    # Risk level thresholds from Sprint 4
    RISK_THRESHOLDS = {
        'ALTO': 0.55,
        'MEDIO': 0.75,
    }

    def __init__(self, bigquery_client: Optional[BigQueryClientManager] = None,
                 project_id: Optional[str] = None,
                 dataset_id: Optional[str] = None,
                 sendgrid_api_key: Optional[str] = None,
                 email_from: Optional[str] = None,
                 email_to: Optional[List[str]] = None):
        """
        Initialize AlertManager.

        Args:
            bigquery_client: BigQueryClientManager instance. If None, uses global manager.
            project_id: GCP project ID. If None, reads from settings.
            dataset_id: BigQuery dataset ID. If None, reads from settings.
            sendgrid_api_key: SendGrid API key. If None, reads from settings.
            email_from: Sender email address. If None, reads from settings.
            email_to: List of recipient email addresses. If None, reads from settings.
        """
        self.bq_manager = bigquery_client
        self.project_id = project_id or settings.GCP_PROJECT_ID
        self.dataset_id = dataset_id or settings.GCP_DATASET_ID
        self.sendgrid_api_key = sendgrid_api_key or settings.SENDGRID_API_KEY
        self.email_from = email_from or settings.ALERT_EMAIL_FROM
        self.email_to = email_to or settings.ALERT_EMAIL_TO

        logger.info(f"AlertManager initialized | project_id={self.project_id} dataset_id={self.dataset_id} email_from={self.email_from} recipients_count={len(self.email_to) if self.email_to else 0}")

    def _get_bq_manager(self) -> BigQueryClientManager:
        """Get or create BigQuery manager."""
        if self.bq_manager is None:
            from src.database.bigquery_client import get_bq_manager
            self.bq_manager = get_bq_manager(project_id=self.project_id)
        return self.bq_manager

    def get_high_risk_institutions(self, area: Optional[str] = None) -> pd.DataFrame:
        """
        Query predictions WHERE risk_level = 'ALTO'.

        Args:
            area: Optional area filter (comunicación, matemática, ccss, cyt).
                  If None, return for all areas.

        Returns:
            DataFrame with high-risk institutions and their prediction details.

        Raises:
            AlertError: If query fails
        """
        logger.info(f"Querying high-risk institutions | area={area or 'all'}")

        try:
            bq_manager = self._get_bq_manager()
            bq_manager.connect()

            # Build query
            area_filter = f"AND area = '{area}'" if area else ""
            query = f"""
            SELECT
                prediction_id,
                area,
                institution_id,
                nom_ie,
                predicted_success,
                confidence,
                risk_level,
                model_version,
                prediction_ts
            FROM `{self.project_id}.{self.dataset_id}.enla_callao_predictions_2026`
            WHERE risk_level = 'ALTO'
            {area_filter}
            ORDER BY area, confidence ASC
            """

            df = bq_manager.query(query)

            if df.empty:
                logger.info(f"No high-risk institutions found | area={area or 'all'}")
                return pd.DataFrame()

            logger.info(f"High-risk institutions found | count={len(df)} area={area or 'all'}")

            return df

        except BigQueryConnectionError as e:
            error_msg = f"BigQuery error querying high-risk institutions: {str(e)}"
            logger.error(error_msg)
            raise AlertError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error querying high-risk institutions: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AlertError(error_msg)

    def generate_summary(self, high_risk_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate executive summary from high-risk institutions DataFrame.

        Args:
            high_risk_df: DataFrame with high-risk institutions

        Returns:
            Dict with summary statistics:
                - total_high_risk: Total count
                - by_area: Dict with counts per area
                - avg_confidence: Average confidence across all
                - model_version: Model version used
        """
        logger.info("Generating alert summary")

        if high_risk_df.empty:
            return {
                'total_high_risk': 0,
                'by_area': {},
                'avg_confidence': None,
                'model_version': None,
            }

        # Count by area
        by_area = {}
        for area in high_risk_df['area'].unique():
            area_count = int((high_risk_df['area'] == area).sum())
            display_name = self.AREA_DISPLAY_NAMES.get(area, area)
            by_area[area] = {
                'display_name': display_name,
                'count': area_count
            }

        # Calculate average confidence
        avg_confidence = None
        if 'confidence' in high_risk_df.columns and not high_risk_df['confidence'].isna().all():
            avg_confidence = float(high_risk_df['confidence'].mean())

        # Get model version (use the most recent one)
        model_version = None
        if 'model_version' in high_risk_df.columns:
            model_version = high_risk_df['model_version'].iloc[0]

        summary = {
            'total_high_risk': len(high_risk_df),
            'by_area': by_area,
            'avg_confidence': avg_confidence,
            'model_version': model_version,
        }

        logger.info(f"Alert summary generated | total_high_risk={summary['total_high_risk']} areas_count={len(by_area)}")

        return summary

    def generate_html_report(self, high_risk_df: pd.DataFrame, summary: Dict[str, Any]) -> str:
        """
        Generate professional HTML email report.

        Args:
            high_risk_df: DataFrame with high-risk institutions
            summary: Summary dict from generate_summary()

        Returns:
            HTML string with formatted email report
        """
        logger.info("Generating HTML email report")

        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        total_count = summary.get('total_high_risk', 0)

        # Build HTML
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALERTA ENLA 2026 - Instituciones en Riesgo</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #d32f2f 0%, #f44336 100%);
            color: white;
            padding: 30px;
            border-radius: 8px 8px 0 0;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 0 0 8px 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary {{
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 15px 20px;
            margin-bottom: 25px;
        }}
        .summary h2 {{
            margin-top: 0;
            color: #e65100;
        }}
        .area-breakdown {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .area-card {{
            background: #fafafa;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 15px;
            text-align: center;
        }}
        .area-card h3 {{
            margin: 0 0 10px 0;
            color: #1976d2;
        }}
        .area-card .count {{
            font-size: 32px;
            font-weight: bold;
            color: #d32f2f;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background: #1976d2;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .risk-high {{
            color: #d32f2f;
            font-weight: bold;
        }}
        .recommendations {{
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px 20px;
            margin: 25px 0;
        }}
        .recommendations h2 {{
            margin-top: 0;
            color: #2e7d32;
        }}
        .recommendations ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .recommendations li {{
            margin: 8px 0;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            font-size: 12px;
            color: #666;
        }}
        .footer a {{
            color: #1976d2;
            text-decoration: none;
        }}
        .no-data {{
            text-align: center;
            padding: 40px;
            color: #666;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚨 ALERTA ENLA 2026</h1>
        <p>{total_count} instituciones en RIESGO ALTO</p>
    </div>
    <div class="content">
        <div class="summary">
            <h2>📊 Resumen Ejecutivo</h2>
            <p><strong>Total instituciones en riesgo ALTO:</strong> {total_count}</p>
"""

        # Add area breakdown
        if summary.get('by_area'):
            html += """            <div class="area-breakdown">
"""
            for area, info in summary['by_area'].items():
                html += f"""                <div class="area-card">
                    <h3>{info['display_name']}</h3>
                    <div class="count">{info['count']}</div>
                </div>
"""
            html += """            </div>
"""

        html += """        </div>
"""

        # High-risk institutions table
        if not high_risk_df.empty:
            html += """        <h2>🏫 Instituciones en Riesgo</h2>
        <table>
            <thead>
                <tr>
                    <th>Institución</th>
                    <th>Área</th>
                    <th>Score Actual</th>
                    <th>Confianza</th>
                    <th>Modelo</th>
                </tr>
            </thead>
            <tbody>
"""
            for _, row in high_risk_df.iterrows():
                nom_ie = row.get('nom_ie', 'N/A')
                area = row.get('area', '')
                area_display = self.AREA_DISPLAY_NAMES.get(area, area)
                confidence = row.get('confidence', 0)
                confidence_pct = f"{confidence * 100:.1f}%" if pd.notna(confidence) else "N/A"
                model_version = row.get('model_version', 'N/A')

                html += f"""                <tr>
                    <td>{nom_ie}</td>
                    <td>{area_display}</td>
                    <td class="risk-high">-</td>
                    <td>{confidence_pct}</td>
                    <td>{model_version}</td>
                </tr>
"""

            html += """            </tbody>
        </table>
"""
        else:
            html += """        <div class="no-data">
            <p>No se encontraron instituciones en riesgo ALTO.</p>
        </div>
"""

        # Pedagogical recommendations
        html += """        <div class="recommendations">
            <h2>💡 Recomendaciones Pedagógicas</h2>
"""
        for area, recommendations in self.AREA_RECOMMENDATIONS.items():
            display_name = self.AREA_DISPLAY_NAMES.get(area, area)
            html += f"""            <h3>{display_name}:</h3>
            <ul>
"""
            for rec in recommendations:
                html += f"""                <li>{rec}</li>
"""
            html += """            </ul>
"""

        html += """        </div>
        <div class="footer">
            <p><strong>Dashboard:</strong> <a href="https://lookerstudio.google.com/">Ver Dashboard ENLA 2026</a></p>
"""

        if summary.get('model_version'):
            html += f"""            <p><strong>Modelo:</strong> enla_model_{{area}}_{summary['model_version']}</p>
"""

        html += f"""            <p><strong>Generado:</strong> {timestamp}</p>
            <p><em>Este es un mensaje automático del sistema ENLA 2026 Callao. Por favor no responder a este correo.</em></p>
        </div>
    </div>
</body>
</html>
"""

        logger.info(f"HTML email report generated | length={len(html)}")
        return html

    def send_email(self, to_emails: List[str], subject: str, html_content: str) -> Dict[str, Any]:
        """
        Send email via SendGrid API.

        Args:
            to_emails: List of recipient email addresses
            subject: Email subject line
            html_content: HTML email body

        Returns:
            Dict with status, message_id, and any errors

        Raises:
            EmailSendError: If SendGrid is not configured or send fails
        """
        logger.info(f"Sending alert email | recipients_count={len(to_emails)} subject={subject}")

        if not self.sendgrid_api_key:
            error_msg = "SendGrid API key not configured"
            logger.error(error_msg)
            raise EmailSendError(error_msg)

        if not to_emails:
            error_msg = "No recipients specified"
            logger.error(error_msg)
            raise EmailSendError(error_msg)

        try:
            sg = SendGridAPIClient(api_key=self.sendgrid_api_key)

            from_email = Email(self.email_from)
            to_emails_list = [To(email) for email in to_emails]
            content = HtmlContent(html_content)

            mail = Mail(
                from_email=from_email,
                to_emails=to_emails_list,
                subject=subject,
                html_content=content
            )

            response = sg.send(mail)

            result = {
                'status': 'sent' if response.status_code == 202 else 'failed',
                'status_code': response.status_code,
                'message_id': response.headers.get('X-Message-Id', ''),
                'error': None
            }

            if result['status'] == 'sent':
                logger.info(f"Email sent successfully | status_code={response.status_code} message_id={result['message_id']}")
            else:
                logger.error(f"Email send failed | status_code={response.status_code}")
                result['error'] = f"SendGrid returned status {response.status_code}"

            return result

        except EmailSendError:
            raise

        except Exception as e:
            error_msg = f"SendGrid error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise EmailSendError(error_msg)

    def log_alert(self, alert_type: str, area: Optional[str], recipients: List[str],
                  subject: str, status: str, error_message: Optional[str] = None) -> None:
        """
        Insert alert record into enla_alert_log table.

        Args:
            alert_type: Type of alert ('high_risk', 'system_error', 'pipeline_complete')
            area: Subject area (None for cross-area alerts)
            recipients: List of recipient email addresses
            subject: Email subject line
            status: Send status ('sent', 'failed', 'pending')
            error_message: Error message if send failed

        Raises:
            AlertError: If logging fails
        """
        logger.info("Logging alert to BigQuery", alert_type=alert_type, status=status)

        try:
            bq_manager = self._get_bq_manager()
            bq_manager.connect()

            # Ensure alert log table exists
            bq_manager.create_dataset(self.dataset_id, location=settings.GCP_LOCATION)
            bq_manager.create_table(
                self.dataset_id,
                'enla_alert_log',
                ALERT_LOG_SCHEMA,
                exists_ok=True
            )

            # Create alert record
            import json
            alert_record = {
                'alert_id': str(uuid.uuid4()),
                'alert_type': alert_type,
                'area': area,
                'recipients': json.dumps(recipients),
                'subject': subject,
                'send_timestamp': datetime.now(timezone.utc),
                'status': status,
                'error_message': error_message,
                'created_at': datetime.now(timezone.utc),
            }

            # Convert to DataFrame and load
            alert_df = pd.DataFrame([alert_record])

            stats = bq_manager.load_table_from_dataframe(
                self.dataset_id,
                'enla_alert_log',
                alert_df,
                write_disposition='WRITE_APPEND',
                schema=ALERT_LOG_SCHEMA,
            )

            logger.info(f"Alert logged successfully | alert_id={alert_record['alert_id']} rows_loaded={stats.get('rows_loaded')}")

        except BigQueryConnectionError as e:
            error_msg = f"BigQuery error logging alert: {str(e)}"
            logger.error(error_msg)
            raise AlertError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error logging alert: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AlertError(error_msg)

    def trigger_alerts(self, email_recipients: Optional[List[str]] = None) -> AlertResult:
        """
        Complete alert pipeline:
        1. Query high-risk institutions
        2. Generate summary
        3. Create HTML report
        4. Send email
        5. Log alert
        6. Return result

        Args:
            email_recipients: List of recipient emails. If None, uses configured recipients.

        Returns:
            AlertResult with execution summary
        """
        result = AlertResult(status="running")

        logger.info("=" * 60)
        logger.info("Starting Alert Pipeline")
        logger.info("=" * 60)

        try:
            recipients = email_recipients or self.email_to

            if not recipients:
                logger.warning("No email recipients configured")
                result.status = "skipped"
                result.error_message = "No email recipients configured"
                return result

            # Step 1: Query high-risk institutions
            logger.info("Step 1: Querying high-risk institutions")
            high_risk_df = self.get_high_risk_institutions()

            if high_risk_df.empty:
                logger.info("No high-risk institutions found. Alert not sent.")
                result.status = "no_data"
                return result

            result.total_high_risk = len(high_risk_df)
            result.areas_affected = list(high_risk_df['area'].unique())

            # Step 2: Generate summary
            logger.info("Step 2: Generating summary")
            summary = self.generate_summary(high_risk_df)

            # Step 3: Create HTML report
            logger.info("Step 3: Generating HTML report")
            html_report = self.generate_html_report(high_risk_df, summary)

            # Step 4: Send email
            logger.info("Step 4: Sending email alert")
            subject = f"🚨 ALERTA ENLA 2026 - {result.total_high_risk} instituciones en RIESGO ALTO"

            send_result = self.send_email(recipients, subject, html_report)

            result.email_sent = send_result['status'] == 'sent'
            result.recipients = recipients
            result.alert_type = "high_risk"
            result.send_timestamp = datetime.now(timezone.utc)

            # Step 5: Log alert
            logger.info("Step 5: Logging alert")
            self.log_alert(
                alert_type=result.alert_type,
                area=None,  # Cross-area alert
                recipients=recipients,
                subject=subject,
                status=send_result['status'],
                error_message=send_result.get('error'),
            )

            result.alert_id = "logged"  # Actual ID is in BigQuery
            result.status = "success" if result.email_sent else "failed"

            logger.info(f"Alert Pipeline completed | email_sent={result.email_sent} recipients_count={len(recipients)} status={result.status}")

        except (AlertError, EmailSendError) as e:
            error_msg = f"Alert pipeline error: {str(e)}"
            result.error_message = error_msg
            result.status = "failed"
            logger.error(error_msg)

            # Try to log the failure
            try:
                self.log_alert(
                    alert_type="high_risk",
                    area=None,
                    recipients=email_recipients or [],
                    subject="ALERTA ENLA 2026 - FAILED",
                    status="failed",
                    error_message=error_msg,
                )
            except Exception as log_error:
                logger.error(f"Failed to log alert error: {str(log_error)}")

        except Exception as e:
            error_msg = f"Unexpected pipeline error: {str(e)}"
            result.error_message = error_msg
            result.status = "failed"
            logger.error(error_msg, exc_info=True)

        return result


# ==========================================
# Convenience Function
# ==========================================

def trigger_high_risk_alert(bigquery_client: Optional[BigQueryClientManager] = None,
                            email_recipients: Optional[List[str]] = None,
                            sendgrid_api_key: Optional[str] = None) -> AlertResult:
    """
    Trigger alerts for high-risk institutions.

    Args:
        bigquery_client: BigQueryClientManager instance (optional)
        email_recipients: List of recipient emails (optional)
        sendgrid_api_key: SendGrid API key (optional)

    Returns:
        AlertResult with execution summary
    """
    manager = AlertManager(
        bigquery_client=bigquery_client,
        sendgrid_api_key=sendgrid_api_key,
    )
    return manager.trigger_alerts(email_recipients=email_recipients)
