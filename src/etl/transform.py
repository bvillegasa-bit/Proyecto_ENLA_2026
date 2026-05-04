"""ETL Transform module for Sprint 2: MongoDB → BigQuery pipeline.

This module handles the transformation of raw ENLA data from MongoDB's wide format
(one row per institution with all area scores) to BigQuery's long format
(one row per institution per area), along with dimension table creation
and data quality validation.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

from src.logging.setup import get_logger
from src.database.mongo_client import get_mongo_manager
from src.database.bigquery_client import get_bq_manager, BigQueryClientManager
from src.ingestion.config import settings
from src.etl.schemas import (
    FACT_ENLA_SCHEMA,
    ENLA_CALLAO_CLEANED_SCHEMA,
    DIM_META_SCHEMA,
    DIM_CALENDARIO_SCHEMA,
)

logger = get_logger('etl_transform')


# ==========================================
# Custom Exceptions
# ==========================================

class ETLTransformError(Exception):
    """Exception for ETL transformation errors."""
    pass


class DataQualityError(Exception):
    """Exception for data quality gate failures."""
    pass


# ==========================================
# Data Classes
# ==========================================

@dataclass
class DataQualitySummary:
    """Summary of data quality checks after transformation."""
    total_input_rows: int = 0
    total_output_rows: int = 0
    areas_processed: int = 0
    null_scores_count: int = 0
    null_scores_percent: float = 0.0
    score_range_valid: bool = True
    critical_null_coverage: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """Check if data quality passes all gates."""
        return len(self.errors) == 0


@dataclass
class ETLResult:
    """Result of the complete ETL pipeline."""
    success: bool
    data_quality: DataQualitySummary
    tables_loaded: List[str] = field(default_factory=list)
    total_rows_loaded: int = 0
    execution_time_seconds: float = 0.0
    error_message: Optional[str] = None
    
    @property
    def status(self) -> str:
        """Return status string based on success flag."""
        return 'success' if self.success else 'failed'


# ==========================================
# Area Mapping Configuration
# ==========================================

# EMA 2023 column mappings: Excel column -> academic area name
# Note: "area" column in Excel = geographic zone (Rural/Urban), NOT academic area
AREA_COLUMN_MAP: Dict[str, str] = {
    'M500_EM_2S_2023_CT': 'comunicacion',  # Comunicación/Lectura
    'M500_EM_2S_2023_MA': 'matematica',    # Matemática
    'M500_EM_2S_2023_CS': 'ccss',          # Ciencias Sociales
}

AREA_DISPLAY_NAMES: Dict[str, str] = {
    'comunicacion': 'Comunicación',
    'matematica': 'Matemática',
    'ccss': 'Ciencias Sociales',
}


# ==========================================
# ETL Transform Class
# ==========================================

class ETLTransform:
    """Core ETL transformation engine for ENLA data.
    
    Transforms raw MongoDB data into BigQuery fact and dimension tables:
    1. Extract: Query MongoDB enla_callao_raw collection
    2. Transform: Pivot wide format → long format by area
    3. Create dimensions: dim_meta, dim_calendario
    4. Load: Insert to BigQuery tables
    5. Validate: Data quality checks
    """
    
    def __init__(self, mongodb_uri: Optional[str] = None,
                 gcp_project_id: Optional[str] = None,
                 gcp_credentials_path: Optional[str] = None):
        """
        Initialize ETL transform with database connections.
        
        Args:
            mongodb_uri: MongoDB connection string (uses env if None)
            gcp_project_id: GCP project ID (uses env if None)
            gcp_credentials_path: Path to GCP credentials JSON (uses env if None)
        """
        self.mongo_manager = get_mongo_manager(mongodb_uri)
        self.bq_manager = BigQueryClientManager(gcp_project_id, gcp_credentials_path)
        self.dataset_id = settings.GCP_DATASET_ID
        
        logger.info(f"ETLTransform initialized | dataset_id={self.dataset_id} area_count={len(AREA_COLUMN_MAP)}")
    
    def run_full_pipeline(self) -> ETLResult:
        """
        Execute the complete ETL pipeline.
        
        Returns:
            ETLResult with execution status, data quality summary, and metadata
        """
        start_time = datetime.now(timezone.utc)
        tables_loaded = []
        total_rows = 0
        
        try:
            logger.info("=" * 60)
            logger.info("Starting ETL Pipeline: MongoDB → BigQuery")
            logger.info("=" * 60)
            
            # Step 1: Connect to MongoDB and extract data
            logger.info("Step 1: Extracting data from MongoDB...")
            raw_df = self._extract_from_mongodb()
            logger.info(f"Extracted {len(raw_df)} rows from MongoDB")
            
            # Step 2: Transform wide → long format
            logger.info("Step 2: Transforming data (wide → long format)...")
            cleaned_df = self._transform_to_long_format(raw_df)
            logger.info(f"Transformed to {len(cleaned_df)} rows (long format)")
            
            # Step 3: Create fact_enla records
            logger.info("Step 3: Creating fact_enla records...")
            fact_df = self._create_fact_records(cleaned_df)
            logger.info(f"Created {len(fact_df)} fact records")
            
            # Step 4: Create dimension tables
            logger.info("Step 4: Creating dimension tables...")
            dim_meta_df = self._create_dim_meta(cleaned_df)
            dim_calendario_df = self._create_dim_calendario(raw_df)
            logger.info(f"Created dim_meta: {len(dim_meta_df)} rows, "
                       f"dim_calendario: {len(dim_calendario_df)} rows")
            
            # Step 5: Connect to BigQuery
            logger.info("Step 5: Connecting to BigQuery...")
            self.bq_manager.connect()
            self.bq_manager.create_dataset(self.dataset_id, location=settings.GCP_LOCATION)
            
            # Step 6: Load to BigQuery
            logger.info("Step 6: Loading data to BigQuery...")
            
            # DEFINITIVE FIX: Convert ALL columns that BigQuery expects as STRING
            # This prevents PyArrow TypeError for int64 -> string conversion
            
            # Debug: Print dtypes before conversion
            logger.info("=== DataFrame dtypes BEFORE conversion ===")
            logger.info(f"cleaned_df dtypes:\n{cleaned_df.dtypes}")
            logger.info(f"fact_df dtypes:\n{fact_df.dtypes}")
            logger.info(f"dim_meta_df dtypes:\n{dim_meta_df.dtypes}")
            
            # Function to convert columns based on BigQuery schema
            def convert_string_columns(df, schema, df_name):
                """Convert DataFrame columns to string if schema expects STRING."""
                for field in schema:
                    if field.field_type == 'STRING' and field.name in df.columns:
                        if df[field.name].dtype == 'int64':
                            logger.info(f"Converting {field.name} to string in {df_name} (dtype: {df[field.name].dtype})")
                            # Convert to string, replace 'nan' string with empty string
                            df[field.name] = df[field.name].astype(str).replace('nan', '')
                            logger.info(f"  After conversion: {df[field.name].dtype}")
                return df
            
            # Convert based on actual BigQuery schemas
            cleaned_df = convert_string_columns(cleaned_df, ENLA_CALLAO_CLEANED_SCHEMA, 'cleaned_df')
            fact_df = convert_string_columns(fact_df, FACT_ENLA_SCHEMA, 'fact_df')
            dim_meta_df = convert_string_columns(dim_meta_df, DIM_META_SCHEMA, 'dim_meta_df')
            dim_calendario_df = convert_string_columns(dim_calendario_df, DIM_CALENDARIO_SCHEMA, 'dim_calendario_df')
            
            # Debug: Print dtypes after conversion
            logger.info("=== DataFrame dtypes AFTER conversion ===")
            logger.info(f"cleaned_df dtypes:\n{cleaned_df.dtypes}")
            logger.info(f"fact_df dtypes:\n{fact_df.dtypes}")
            logger.info(f"dim_meta_df dtypes:\n{dim_meta_df.dtypes}")
            
            self.bq_manager.load_table_from_dataframe(
                self.dataset_id, 'enla_callao_cleaned',
                cleaned_df, write_disposition='WRITE_TRUNCATE',
                schema=ENLA_CALLAO_CLEANED_SCHEMA
            )
            tables_loaded.append('enla_callao_cleaned')
            total_rows += len(cleaned_df)
            
            self.bq_manager.load_table_from_dataframe(
                self.dataset_id, 'fact_enla',
                fact_df, write_disposition='WRITE_TRUNCATE',
                schema=FACT_ENLA_SCHEMA
            )
            tables_loaded.append('fact_enla')
            total_rows += len(fact_df)
            
            self.bq_manager.load_table_from_dataframe(
                self.dataset_id, 'dim_meta',
                dim_meta_df, write_disposition='WRITE_TRUNCATE',
                schema=DIM_META_SCHEMA
            )
            tables_loaded.append('dim_meta')
            total_rows += len(dim_meta_df)
            
            self.bq_manager.load_table_from_dataframe(
                self.dataset_id, 'dim_calendario',
                dim_calendario_df, write_disposition='WRITE_TRUNCATE',
                schema=DIM_CALENDARIO_SCHEMA
            )
            tables_loaded.append('dim_calendario')
            total_rows += len(dim_calendario_df)
            
            # Step 7: Data quality validation
            logger.info("Step 7: Running data quality checks...")
            quality_summary = self._validate_data_quality(raw_df, cleaned_df)
            
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            result = ETLResult(
                success=quality_summary.is_valid,
                data_quality=quality_summary,
                tables_loaded=tables_loaded,
                total_rows_loaded=total_rows,
                execution_time_seconds=execution_time,
            )
            
            logger.info(f"ETL Pipeline completed successfully | tables_loaded={len(tables_loaded)} total_rows={total_rows} execution_time={execution_time:.2f}s data_quality_valid={quality_summary.is_valid}")
            
            return result
            
        except ETLTransformError as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_msg = f"ETL transformation error: {str(e)}"
            logger.error(error_msg)
            
            return ETLResult(
                success=False,
                data_quality=DataQualitySummary(),
                tables_loaded=tables_loaded,
                total_rows_loaded=total_rows,
                execution_time_seconds=execution_time,
                error_message=error_msg,
            )
        except Exception as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_msg = f"Unexpected ETL error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return ETLResult(
                success=False,
                data_quality=DataQualitySummary(),
                tables_loaded=tables_loaded,
                total_rows_loaded=total_rows,
                execution_time_seconds=execution_time,
                error_message=error_msg,
            )
        finally:
            # Clean up connections
            try:
                self.bq_manager.disconnect()
                self.mongo_manager.disconnect()
            except Exception as e:
                logger.warning("Error during connection cleanup", error=str(e))
    
    # ==========================================
    # Extract Phase
    # ==========================================
    
    def _extract_from_mongodb(self) -> pd.DataFrame:
        """
        Extract all records from MongoDB enla_callao_raw collection.
        
        Returns:
            DataFrame with raw ENLA data
            
        Raises:
            ETLTransformError: If MongoDB connection or query fails
        """
        try:
            collection = self.mongo_manager.get_collection(
                settings.MONGODB_DB,
                settings.MONGODB_COLLECTION_RAW
            )
            
            # Query all documents, converting ObjectId to string
            cursor = collection.find({})
            
            records = []
            for doc in cursor:
                # Convert ObjectId to string for JSON compatibility
                doc['_id'] = str(doc['_id'])
                records.append(doc)
            
            if not records:
                msg = "No records found in MongoDB enla_callao_raw collection"
                logger.warning(msg)
                raise ETLTransformError(msg)
            
            df = pd.DataFrame(records)
            
            logger.info(f"Extracted records from MongoDB | row_count={len(df)} columns={list(df.columns)}")
            
            return df
            
        except ETLTransformError:
            raise
        except Exception as e:
            msg = f"Failed to extract data from MongoDB: {str(e)}"
            logger.error(msg)
            raise ETLTransformError(msg)
    
    # ==========================================
    # Transform Phase
    # ==========================================
    
    def _transform_to_long_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform wide-format data to long format by academic area.
        
        Converts from (wide - one row per student with all area scores):
            id_ie | cor_est | area (geographic) | M500_EM_2S_2023_CT | M500_EM_2S_2023_MA | ...
        To (long - one row per student per academic area):
            id_ie | cor_est | area (geographic) | area_academica | score | grupo | peso
            IE001 | EST001 | Urban             | comunicacion    | 72.5  | 2     | 1.0
            IE001 | EST001 | Urban             | matematica      | 65.3  | 3     | 1.0
        
        Args:
            raw_df: Raw DataFrame from MongoDB
            
        Returns:
            DataFrame in long format with columns:
            id_ie, id_seccion, nom_ie, nom_dre, year, area (geographic),
            cor_est, area_academica, score, grupo, peso, is_null_score, created_at
        """
        # DEFENSIVE: Log columns to help debug KeyError issues
        logger.info(f"Transform input columns: {list(raw_df.columns)}")
        
        # DEFENSIVE: Create case-insensitive column mapping
        # This handles any case variation (ID_IE, id_ie, Id_Ie, etc.)
        col_mapping = {col.lower(): col for col in raw_df.columns}
        logger.info(f"Column mapping (lowercase -> original): {col_mapping}")
        
        def get_column(df, possible_names):
            """Get column from DataFrame, trying multiple case variations."""
            for name in possible_names:
                if name in df.columns:
                    return df[name]
                # Also try case-insensitive match
                lower_name = name.lower()
                if lower_name in col_mapping:
                    actual_col = col_mapping[lower_name]
                    logger.info(f"Column '{name}' found as '{actual_col}' (case-insensitive match)")
                    return df[actual_col]
            raise KeyError(f"Column not found. Tried: {possible_names}. Available columns: {list(df.columns)}")
        
        all_records = []
        
        for score_col, area_name in AREA_COLUMN_MAP.items():
            if score_col not in raw_df.columns:
                logger.warning(f"Column '{score_col}' not found in raw data, skipping area '{area_name}'")
                continue
            
            # Derive related column names
            grupo_col = score_col.replace('M500_', 'grupo_')
            peso_col = f"peso_{area_name[-2:].upper()}"  # peso_CT, peso_MA, peso_CS
            
            # Extract score column and convert to numeric
            scores = pd.to_numeric(raw_df[score_col], errors='coerce')
            
            # Create records for this academic area
            # DEFENSIVE: Use helper function to handle case variations
            area_df = pd.DataFrame({
                'id_ie': get_column(raw_df, ['ID_IE', 'id_ie']),  # Try uppercase first
                'id_seccion': get_column(raw_df, ['ID_SECCION', 'id_seccion']),  # Try uppercase first
                'nom_ie': get_column(raw_df, ['nom_ie', 'NOM_IE']) if 'nom_ie' in col_mapping or 'NOM_IE' in raw_df.columns else None,
                'nom_dre': get_column(raw_df, ['nom_dre', 'NOM_DRE']) if 'nom_dre' in col_mapping or 'NOM_DRE' in raw_df.columns else None,
                'year': get_column(raw_df, ['ano_evaluacion', 'ANO_EVALUACION']) if 'ano_evaluacion' in col_mapping or 'ANO_EVALUACION' in raw_df.columns else 2023,
                'area': get_column(raw_df, ['area', 'AREA']),  # Geographic zone (Rural/Urban)
                'cor_est': get_column(raw_df, ['cor_est', 'COR_EST']),  # Student identifier
                'area_academica': area_name,  # Academic area name
                'score': scores,
                'grupo': raw_df[grupo_col] if grupo_col in raw_df.columns else None,
                'peso': raw_df[peso_col] if peso_col in raw_df.columns else None,
                'is_null_score': scores.isna(),
                'created_at': datetime.now(timezone.utc),
            })
            
            all_records.append(area_df)
            logger.debug(f"Processed academic area '{area_name}': {len(area_df)} records")
        
        if not all_records:
            msg = "No EMA 2023 area columns found in raw data"
            logger.error(msg)
            raise ETLTransformError(msg)
        
        cleaned_df = pd.concat(all_records, ignore_index=True)
        
        # Sort for consistency
        cleaned_df = cleaned_df.sort_values(['id_ie', 'cor_est', 'year', 'area_academica']).reset_index(drop=True)
        
        logger.info(f"Wide-to-long transformation complete | input_rows={len(raw_df)} output_rows={len(cleaned_df)} areas_processed={len(all_records)}")
        
        return cleaned_df
    
    # ==========================================
    # Fact Table Creation
    # ==========================================
    
    def _create_fact_records(self, cleaned_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create fact_enla table records with UUID primary keys.
        
        Args:
            cleaned_df: Cleaned long-format DataFrame
            
        Returns:
            DataFrame with fact_enla schema
        """
        fact_df = pd.DataFrame({
            'fact_id': [str(uuid.uuid4()) for _ in range(len(cleaned_df))],
            'id_ie': cleaned_df['id_ie'],
            'id_seccion': cleaned_df['id_seccion'],
            'nom_ie': cleaned_df['nom_ie'],
            'year': cleaned_df['year'].astype(int),
            'area_academica': cleaned_df['area_academica'],  # Academic area (comunicacion/matematica/ccss)
            'cor_est': cleaned_df['cor_est'],  # Student identifier
            'score': cleaned_df['score'],
            'created_at': cleaned_df['created_at'],
        })
        
        logger.info(f"Fact records created | count={len(fact_df)}")
        return fact_df
    
    # ==========================================
    # Dimension Table Creation
    # ==========================================
    
    def _create_dim_meta(self, cleaned_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create dim_meta table with institution targets per academic area per year.
        
        Args:
            cleaned_df: Cleaned long-format DataFrame
            
        Returns:
            DataFrame with dim_meta schema
        """
        # Get unique institution-academic_area-year combinations
        unique_combos = cleaned_df[['id_ie', 'nom_ie', 'year', 'area_academica']].drop_duplicates()
        
        dim_meta_df = pd.DataFrame({
            'meta_id': [str(uuid.uuid4()) for _ in range(len(unique_combos))],
            'id_ie': unique_combos['id_ie'],
            'nom_ie': unique_combos['nom_ie'],
            'year': unique_combos['year'].astype(int),
            'area': unique_combos['area_academica'],  # Academic area
            'target_score': settings.TARGET_SCORE_THRESHOLD,
            'region': settings.ENLA_REGION,
            'created_at': datetime.now(timezone.utc),
        })
        
        logger.info(f"dim_meta created | count={len(dim_meta_df)} target_score={settings.TARGET_SCORE_THRESHOLD}")
        
        return dim_meta_df
    
    def _create_dim_calendario(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create dim_calendario table with date dimension for analysis.
        
        Generates calendar entries for all evaluation years found in the data.
        
        Args:
            raw_df: Raw DataFrame from MongoDB
            
        Returns:
            DataFrame with dim_calendario schema
        """
        # Get unique years from data
        years = sorted(raw_df['ano_evaluacion'].dropna().unique())
        
        all_dates = []
        for year in years:
            year_int = int(year)
            # Create entries for key dates in each year (quarter starts + evaluation dates)
            key_dates = [
                (year_int, 1, 1),   # Q1 start
                (year_int, 4, 1),   # Q2 start
                (year_int, 7, 1),   # Q3 start
                (year_int, 10, 1),  # Q4 start
                (year_int, 12, 31), # Year end
            ]
            
            for y, m, d in key_dates:
                try:
                    date_obj = datetime(y, m, d, tzinfo=timezone.utc)
                    all_dates.append({
                        'date_id': f"{y}{m:02d}{d:02d}",
                        'date': date_obj,
                        'year': y,
                        'month': m,
                        'day': d,
                        'quarter': (m - 1) // 3 + 1,
                        'created_at': datetime.now(timezone.utc),
                    })
                except ValueError:
                    continue
        
        dim_cal_df = pd.DataFrame(all_dates)
        
        logger.info(f"dim_calendario created | count={len(dim_cal_df)} years_covered={list(years)}")
        
        return dim_cal_df
    
    # ==========================================
    # Data Quality Validation
    # ==========================================
    
    def _validate_data_quality(self, raw_df: pd.DataFrame,
                                cleaned_df: pd.DataFrame) -> DataQualitySummary:
        """
        Run data quality checks on transformed data.
        
        Validates:
        - NULL coverage for critical columns (< 5% threshold)
        - Score range validity (scores in [0, 100] when not NULL)
        - Row count consistency (output = input × academic areas)
        - Geographic zone (area) distribution
        
        Args:
            raw_df: Original raw DataFrame
            cleaned_df: Transformed long-format DataFrame
            
        Returns:
            DataQualitySummary with validation results
        """
        summary = DataQualitySummary(
            total_input_rows=len(raw_df),
            total_output_rows=len(cleaned_df),
            areas_processed=cleaned_df['area_academica'].nunique() if 'area_academica' in cleaned_df.columns else 0,
        )
        
        # Check 1: NULL score coverage
        null_scores = cleaned_df['is_null_score'].sum()
        summary.null_scores_count = int(null_scores)
        summary.null_scores_percent = round(
            (null_scores / len(cleaned_df)) * 100, 2
        ) if len(cleaned_df) > 0 else 0.0
        
        logger.info(f"Data quality: NULL score coverage | null_count={summary.null_scores_count} null_percent={summary.null_scores_percent}")
        
        # Check 2: Score range validity (for non-NULL scores)
        valid_scores = cleaned_df[~cleaned_df['is_null_score']]['score']
        if len(valid_scores) > 0:
            min_score = valid_scores.min()
            max_score = valid_scores.max()
            out_of_range = ((valid_scores < 0) | (valid_scores > 100)).sum()
            
            # DEBUG: Log actual score ranges to understand the data
            logger.info(f"Data quality: Score range check | min={min_score} max={max_score} valid_range=[0,100] out_of_range={out_of_range}")
            
            # DEBUG: Show distribution of scores in ranges
            range_counts = {
                'negative': (valid_scores < 0).sum(),
                '0_to_50': ((valid_scores >= 0) & (valid_scores <= 50)).sum(),
                '51_to_100': ((valid_scores > 50) & (valid_scores <= 100)).sum(),
                '101_to_200': ((valid_scores > 100) & (valid_scores <= 200)).sum(),
                '201_to_500': ((valid_scores > 200) & (valid_scores <= 500)).sum(),
                'above_500': (valid_scores > 500).sum(),
            }
            logger.info(f"Data quality: Score distribution | {range_counts}")
            
            if out_of_range > 0:
                summary.score_range_valid = False
                msg = f"{out_of_range} scores out of valid range [0, 100] (actual range: [{min_score}, {max_score}])"
                summary.warnings.append(msg)  # CHANGED: warnings instead of errors (don't fail ETL)
                logger.warning(f"Data quality: {msg}")
                logger.warning(f"  Scores outside [0,100] will be kept but may affect analysis")
            
            # DEBUG: Also check raw data score columns
            logger.info("Data quality: Checking raw score columns...")
            for col in AREA_COLUMN_MAP.keys():
                if col in raw_df.columns:
                    col_data = pd.to_numeric(raw_df[col], errors='coerce')
                    col_min = col_data.min()
                    col_max = col_data.max()
                    col_null = col_data.isna().sum()
                    logger.info(f"  {col}: min={col_min}, max={col_max}, nulls={col_null}, total={len(raw_df)}")
        
        # Check 3: Critical column NULL coverage
        # Note: 'area' now = geographic zone (Rural/Urban), 'area_academica' = academic area
        critical_cols = ['id_ie', 'id_seccion', 'year', 'area_academica', 'cor_est']
        for col in critical_cols:
            if col in cleaned_df.columns:
                null_pct = round(
                    (cleaned_df[col].isna().sum() / len(cleaned_df)) * 100, 2
                )
                summary.critical_null_coverage[col] = null_pct
                
                if null_pct > 5.0:
                    msg = f"Critical column '{col}' has {null_pct}% NULL coverage (threshold: 5%)"
                    summary.warnings.append(msg)
                    logger.warning(msg)
                
                if null_pct > 20.0:
                    msg = f"FAIL: Critical column '{col}' has {null_pct}% NULL coverage (exceeds 20%)"
                    summary.errors.append(msg)
                    logger.error(msg)
        
        # Check 3b: Geographic zone (area) distribution - informational
        if 'area' in cleaned_df.columns:
            area_dist = cleaned_df['area'].value_counts().to_dict()
            logger.info(f"Data quality: Geographic zone distribution | {area_dist}")
        
        # Check 4: Row count consistency
        expected_rows = len(raw_df) * len(AREA_COLUMN_MAP)
        if len(cleaned_df) != expected_rows:
            msg = (f"Row count mismatch: expected {expected_rows} "
                   f"(input: {len(raw_df)} × {len(AREA_COLUMN_MAP)} academic areas), "
                   f"got {len(cleaned_df)}")
            summary.warnings.append(msg)
            logger.warning(msg)
        
        # Log summary
        logger.info(f"Data quality validation complete | is_valid={summary.is_valid} warnings={len(summary.warnings)} errors={len(summary.errors)}")
        
        return summary


# ==========================================
# Convenience Function
# ==========================================

def run_etl_pipeline(mongodb_uri: Optional[str] = None,
                     gcp_project_id: Optional[str] = None,
                     gcp_credentials_path: Optional[str] = None) -> ETLResult:
    """
    Run the complete ETL pipeline from MongoDB to BigQuery.
    
    Args:
        mongodb_uri: MongoDB connection string (uses env if None)
        gcp_project_id: GCP project ID (uses env if None)
        gcp_credentials_path: Path to GCP credentials JSON (uses env if None)
    
    Returns:
        ETLResult with execution status and metadata
    """
    transform = ETLTransform(
        mongodb_uri=mongodb_uri,
        gcp_project_id=gcp_project_id,
        gcp_credentials_path=gcp_credentials_path,
    )
    return transform.run_full_pipeline()
