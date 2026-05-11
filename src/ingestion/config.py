"""Configuration module for ENLA 2026 Callao pipeline."""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    model_config = SettingsConfigDict(env_file='config/.env', case_sensitive=True)
    
    # MongoDB Configuration
    MONGODB_URI: str = os.getenv('MONGODB_URI', '')
    MONGODB_DB: str = 'enla_db'
    MONGODB_COLLECTION_RAW: str = 'enla_callao_raw'  # Existing: Callao-only collection (legacy ETL source)
    MONGODB_COLLECTION_LOG: str = 'enla_ingestion_log'

    # Data Lake Configuration (MongoDB as raw data lake for ALL Peru data)
    MONGODB_COLLECTION_ALL_PERU: str = 'enla_all_peru_raw'  # New: all-Peru raw data lake (no region filter)
    MONGODB_DATALAKE_ENABLED: bool = False  # Toggle: when True, ingest() also populates enla_all_peru_raw
    MONGODB_ETL_SOURCE_COLLECTION: str = 'enla_all_peru_raw'  # Source collection for ETL extraction
    
    # GCP Configuration
    GCP_PROJECT_ID: str = os.getenv('GCP_PROJECT_ID', '')
    GCP_DATASET_ID: str = 'BI_ENLA'
    GCP_LOCATION: str = 'US'
    GCP_CREDENTIALS_PATH: Optional[str] = os.getenv('GCP_CREDENTIALS_PATH', None)
    
    # ENLA Data Configuration
    ENLA_REGION: str = 'CALLAO'
    ENLA_GRADO: int = 2
    ENLA_YEARS: list = [2021, 2022, 2023]
    # Standardized area columns (after column_mapping.py rename)
    # NOTE: "area" column = geographic zone (Rural/Urban), NOT academic area
    # These are the standardized names from src/ingestion/column_mapping.py
    ENLA_AREA_COLUMNS: dict = {
        'medida_lectura': 'Comunicación/Lectura',
        'medida_matematica': 'Matemática',
        'medida_ciencias': 'Ciencias Naturales',
    }
    # Student identifier column (standardized name)
    ENLA_STUDENT_ID_COL: str = 'cor_est'
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: str = 'logs/enla_ingestion.log'
    LOG_FORMAT: str = 'json'  # json or text
    
    # Feature Engineering Configuration
    TARGET_SCORE_THRESHOLD: float = 576.0  # Minimum score to pass (scale 0-1000). Calculated as rounded median of real scores (N=24910, all areas, 2022-2023)
    FEATURE_NORMALIZATION_MIN: float = -1.0
    FEATURE_NORMALIZATION_MAX: float = 1.0
    
    # Model Configuration
    MODEL_RANDOM_STATE: int = 42
    MODEL_TEST_SIZE: float = 0.2
    MODEL_TRAIN_YEARS: list = [2021, 2022]
    MODEL_TEST_YEARS: list = [2023]
    
    # Alert Configuration
    ALERT_RISK_THRESHOLD_HIGH: float = 0.7  # Probability threshold for high risk
    ALERT_RISK_THRESHOLD_MEDIUM: float = 0.5  # Probability threshold for medium risk
    ALERT_EMAIL_FROM: str = os.getenv('ALERT_EMAIL_FROM', 'enla-alerts@dre-callao.gob.pe')
    ALERT_EMAIL_TO: List[str] = []  # Will be populated from environment
    SENDGRID_API_KEY: str = os.getenv('SENDGRID_API_KEY', '')


settings = Settings()
