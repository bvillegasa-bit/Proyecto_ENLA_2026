"""BigQuery schema definitions for alerting tables.

Defines schemas for:
- enla_alert_log: Audit trail for sent alerts and notifications
"""

from google.cloud.bigquery import SchemaField
from typing import List, Dict


# ==========================================
# enla_alert_log schema
# Audit trail for alert notifications
# ==========================================
ALERT_LOG_SCHEMA: List[SchemaField] = [
    SchemaField("alert_id", "STRING", mode="REQUIRED",
                description="Unique UUID for this alert record"),
    SchemaField("alert_type", "STRING", mode="REQUIRED",
                description="Alert type: 'high_risk', 'system_error', 'pipeline_complete'"),
    SchemaField("area", "STRING", mode="NULLABLE",
                description="Subject area (NULL for cross-area alerts)"),
    SchemaField("recipients", "STRING", mode="NULLABLE",
                description="JSON array of recipient email addresses"),
    SchemaField("subject", "STRING", mode="NULLABLE",
                description="Email subject line"),
    SchemaField("send_timestamp", "TIMESTAMP", mode="NULLABLE",
                description="Timestamp when email was sent"),
    SchemaField("status", "STRING", mode="REQUIRED",
                description="Send status: 'sent', 'failed', 'pending'"),
    SchemaField("error_message", "STRING", mode="NULLABLE",
                description="Error message if send failed"),
    SchemaField("created_at", "TIMESTAMP", mode="REQUIRED",
                description="Record creation timestamp"),
]

# ==========================================
# Schema registry for programmatic access
# ==========================================
ALERT_SCHEMA_REGISTRY: Dict[str, List[SchemaField]] = {
    "enla_alert_log": ALERT_LOG_SCHEMA,
}


def get_alert_schema(table_name: str) -> List[SchemaField]:
    """
    Get schema definition for an alert-related table by name.

    Args:
        table_name: Table name key from ALERT_SCHEMA_REGISTRY

    Returns:
        List of SchemaField objects

    Raises:
        KeyError: If table_name is not in registry
    """
    if table_name not in ALERT_SCHEMA_REGISTRY:
        available = ", ".join(ALERT_SCHEMA_REGISTRY.keys())
        raise KeyError(f"Unknown alert table '{table_name}'. Available: {available}")
    return ALERT_SCHEMA_REGISTRY[table_name]
