"""BigQuery schema definitions for ENLA 2026 Callao pipeline."""

from google.cloud import bigquery
from google.cloud.bigquery import SchemaField
from typing import List


# ==========================================
# fact_enla schema
# Core fact table: one row per student per academic area per year
# ==========================================
FACT_ENLA_SCHEMA: List[SchemaField] = [
    SchemaField("fact_id", "STRING", mode="REQUIRED", description="Unique UUID for this fact record"),
    SchemaField("id_ie", "STRING", mode="REQUIRED", description="Institution ID"),
    SchemaField("id_seccion", "STRING", mode="REQUIRED", description="Section ID"),
    SchemaField("nom_ie", "STRING", mode="NULLABLE", description="Institution name"),
    SchemaField("year", "INTEGER", mode="REQUIRED", description="Evaluation year"),
    SchemaField("area_academica", "STRING", mode="REQUIRED", description="Academic area: comunicacion, matematica, ccss (from EMA 2023)"),
    SchemaField("cor_est", "STRING", mode="REQUIRED", description="Student identifier"),
    SchemaField("score", "FLOAT64", mode="NULLABLE", description="Student score [0, 100], NULL if not available"),
    SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", description="Record creation timestamp"),
]


# ==========================================
# enla_callao_cleaned schema
# Cleaned staging table for ML feature engineering
# NOTE: "area" = geographic zone (Rural/Urban), NOT academic area
# ==========================================
ENLA_CALLAO_CLEANED_SCHEMA: List[SchemaField] = [
    SchemaField("id_ie", "STRING", mode="REQUIRED", description="Institution ID"),
    SchemaField("id_seccion", "STRING", mode="REQUIRED", description="Section ID"),
    SchemaField("nom_ie", "STRING", mode="NULLABLE", description="Institution name"),
    SchemaField("nom_dre", "STRING", mode="NULLABLE", description="DRE (regional education directorate) name"),
    SchemaField("year", "INTEGER", mode="REQUIRED", description="Evaluation year"),
    SchemaField("area", "STRING", mode="REQUIRED", description="Geographic zone: Rural or Urban"),
    SchemaField("cor_est", "STRING", mode="REQUIRED", description="Student identifier"),
    SchemaField("area_academica", "STRING", mode="REQUIRED", description="Academic area: comunicacion, matematica, ccss (from EMA 2023)"),
    SchemaField("score", "FLOAT64", mode="NULLABLE", description="Student score [0, 100], NULL if not available"),
    SchemaField("grupo", "STRING", mode="NULLABLE", description="Performance group (from EMA 2023 grupo column)"),
    SchemaField("peso", "FLOAT64", mode="NULLABLE", description="Weight factor (from EMA 2023 peso column)"),
    SchemaField("is_null_score", "BOOLEAN", mode="REQUIRED", description="Flag indicating if score was NULL"),
    SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", description="Record creation timestamp"),
]


# ==========================================
# dim_meta schema
# Institution metadata with performance targets per academic area per year
# NOTE: "area_academica" = academic area (comunicacion/matematica/ccss), NOT geographic zone
# ==========================================
DIM_META_SCHEMA: List[SchemaField] = [
    SchemaField("meta_id", "STRING", mode="REQUIRED", description="Unique UUID for this meta record"),
    SchemaField("id_ie", "STRING", mode="REQUIRED", description="Institution ID"),
    SchemaField("nom_ie", "STRING", mode="NULLABLE", description="Institution name"),
    SchemaField("year", "INTEGER", mode="REQUIRED", description="Target year"),
    SchemaField("area_academica", "STRING", mode="REQUIRED", description="Academic area: comunicacion, matematica, ccss (NOT geographic zone)"),
    SchemaField("target_score", "FLOAT64", mode="REQUIRED", description="Target score threshold (default 60.0)"),
    SchemaField("region", "STRING", mode="REQUIRED", description="Region name (CALLAO)"),
    SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", description="Record creation timestamp"),
]


# ==========================================
# dim_calendario schema
# Calendar/date dimension for time-based analysis
# ==========================================
DIM_CALENDARIO_SCHEMA: List[SchemaField] = [
    SchemaField("date_id", "STRING", mode="REQUIRED", description="Date in YYYYMMDD format"),
    SchemaField("date", "DATE", mode="REQUIRED", description="Full date"),
    SchemaField("year", "INTEGER", mode="REQUIRED", description="Year"),
    SchemaField("month", "INTEGER", mode="REQUIRED", description="Month (1-12)"),
    SchemaField("day", "INTEGER", mode="REQUIRED", description="Day (1-31)"),
    SchemaField("quarter", "INTEGER", mode="REQUIRED", description="Quarter (1-4)"),
    SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", description="Record creation timestamp"),
]


# ==========================================
# Schema registry for programmatic access
# ==========================================
SCHEMA_REGISTRY = {
    "fact_enla": FACT_ENLA_SCHEMA,
    "enla_callao_cleaned": ENLA_CALLAO_CLEANED_SCHEMA,
    "dim_meta": DIM_META_SCHEMA,
    "dim_calendario": DIM_CALENDARIO_SCHEMA,
}


def get_schema(table_name: str) -> List[SchemaField]:
    """
    Get schema definition for a table by name.
    
    Args:
        table_name: Table name key from SCHEMA_REGISTRY
    
    Returns:
        List of SchemaField objects
    
    Raises:
        KeyError: If table_name is not in registry
    """
    if table_name not in SCHEMA_REGISTRY:
        available = ", ".join(SCHEMA_REGISTRY.keys())
        raise KeyError(f"Unknown table '{table_name}'. Available: {available}")
    return SCHEMA_REGISTRY[table_name]
