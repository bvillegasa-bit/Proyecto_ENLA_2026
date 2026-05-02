"""BigQuery schema definitions for feature engineering tables.

Defines schemas for:
- enla_callao_features: Engineered features per institution per area
- enla_feature_normalization_params: Normalization parameters for reproducibility
"""

from google.cloud.bigquery import SchemaField
from typing import List, Dict


# ==========================================
# enla_callao_features schema
# Engineered features for ML model training
# ==========================================
FEATURES_SCHEMA: List[SchemaField] = [
    SchemaField("feature_id", "STRING", mode="REQUIRED",
                description="Unique UUID for this feature record"),
    SchemaField("area", "STRING", mode="REQUIRED",
                description="Subject area: comunicacion, matematica, ccss, cyt"),
    SchemaField("institution_id", "STRING", mode="REQUIRED",
                description="Institution ID (id_ie)"),
    SchemaField("nom_ie", "STRING", mode="NULLABLE",
                description="Institution name"),

    # Normalized features [-1, 1]
    SchemaField("avg_score_2023", "FLOAT64", mode="NULLABLE",
                description="Normalized average score for 2023"),
    SchemaField("avg_score_2022", "FLOAT64", mode="NULLABLE",
                description="Normalized average score for 2022"),
    SchemaField("avg_score_2021", "FLOAT64", mode="NULLABLE",
                description="Normalized average score for 2021"),
    SchemaField("trend", "FLOAT64", mode="NULLABLE",
                description="Normalized year-over-year trend (2023 vs 2022)"),
    SchemaField("variance", "FLOAT64", mode="NULLABLE",
                description="Normalized standard deviation across years"),

    # Target
    SchemaField("target", "INTEGER", mode="NULLABLE",
                description="Binary target: 1 if avg_score_2023 > meta_threshold, else 0"),

    # Raw values (for reference/debugging)
    SchemaField("raw_avg_score_2023", "FLOAT64", mode="NULLABLE",
                description="Raw average score for 2023"),
    SchemaField("raw_avg_score_2022", "FLOAT64", mode="NULLABLE",
                description="Raw average score for 2022"),
    SchemaField("raw_avg_score_2021", "FLOAT64", mode="NULLABLE",
                description="Raw average score for 2021"),
    SchemaField("raw_trend", "FLOAT64", mode="NULLABLE",
                description="Raw year-over-year trend"),
    SchemaField("raw_variance", "FLOAT64", mode="NULLABLE",
                description="Raw standard deviation across years"),

    # Metadata
    SchemaField("meta_threshold", "FLOAT64", mode="NULLABLE",
                description="Threshold used for target generation"),
    SchemaField("created_at", "TIMESTAMP", mode="REQUIRED",
                description="Record creation timestamp"),
]


# ==========================================
# enla_feature_normalization_params schema
# Parameters for reproducing normalization at inference time
# ==========================================
NORM_PARAMS_SCHEMA: List[SchemaField] = [
    SchemaField("param_id", "STRING", mode="REQUIRED",
                description="Unique UUID for this normalization parameter"),
    SchemaField("area", "STRING", mode="REQUIRED",
                description="Subject area: comunicacion, matematica, ccss, cyt"),
    SchemaField("feature_name", "STRING", mode="REQUIRED",
                description="Feature name: avg_score_2023, avg_score_2022, avg_score_2021, trend, variance"),
    SchemaField("min_value", "FLOAT64", mode="NULLABLE",
                description="Minimum raw value used for normalization"),
    SchemaField("max_value", "FLOAT64", mode="NULLABLE",
                description="Maximum raw value used for normalization"),
    SchemaField("created_at", "TIMESTAMP", mode="REQUIRED",
                description="Record creation timestamp"),
]


# ==========================================
# Schema registry for programmatic access
# ==========================================
FEATURE_SCHEMA_REGISTRY: Dict[str, List[SchemaField]] = {
    "enla_callao_features": FEATURES_SCHEMA,
    "enla_feature_normalization_params": NORM_PARAMS_SCHEMA,
}


def get_feature_schema(table_name: str) -> List[SchemaField]:
    """
    Get schema definition for a feature table by name.

    Args:
        table_name: Table name key from FEATURE_SCHEMA_REGISTRY

    Returns:
        List of SchemaField objects

    Raises:
        KeyError: If table_name is not in registry
    """
    if table_name not in FEATURE_SCHEMA_REGISTRY:
        available = ", ".join(FEATURE_SCHEMA_REGISTRY.keys())
        raise KeyError(f"Unknown feature table '{table_name}'. Available: {available}")
    return FEATURE_SCHEMA_REGISTRY[table_name]
