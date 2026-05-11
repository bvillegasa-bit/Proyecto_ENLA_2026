"""ETL Transform module for Sprint 2: MongoDB → BigQuery pipeline.

This module handles the transformation of raw ENLA data from MongoDB's wide format
(one row per institution with all area scores) to BigQuery's long format
(one row per institution per area), along with dimension table creation
and data quality validation.

DYNAMIC COLUMN SUPPORT:
- Column names CHANGE per year (2021, 2022, 2023 have different formats)
- Year is extracted from FILENAME (not in Excel data)
- Pattern matching used to discover actual column names in each year's data
"""

import uuid
import re
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
# Accent Normalization (Display Only)
# ==========================================

# For display purposes only - column names are now standardized without accents
ACCENT_NORMALIZATION_DISPLAY = {
    'comunicacion': 'comunicación',
    'matematica': 'matemática',
}

def normalize_area_name(area_name: str) -> str:
    """Normalize area name for display (add accents).
    
    Args:
        area_name: Area key (without accents)
        
    Returns:
        Display name with correct accents
    """
    return ACCENT_NORMALIZATION_DISPLAY.get(area_name.lower(), area_name)


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
# Standardized Area Configuration (Module Level)
# ==========================================

# After column standardization (SDD standardize-columns), all column names are now
# in snake_case format. We use the standardized names directly.
# Keys use UNACCENTED names to match UNIFIED_SCHEMA from column_mapping.py
STANDARDIZED_AREAS = {
    'comunicacion': {
        'display_name': 'Comunicación',
        'measure': 'medida_lectura',
        'group': 'grupo_lectura',
        'weight': 'peso_lectura',
        'required': True,  # OBLIGATORY area
    },
    'matematica': {
        'display_name': 'Matemática',
        'measure': 'medida_matematica',
        'group': 'grupo_matematica',
        'weight': 'peso_matematica',
        'required': True,  # OBLIGATORY area
    },
    'ccss': {
        'display_name': 'Ciencias Sociales',
        'measure': 'medida_ciencias',
        'group': 'grupo_ciencias',
        'weight': 'peso_ciencias',
        'required': False,  # OPTIONAL area
    },
}

# Accent normalization for display purposes (not for column matching)
ACCENT_NORMALIZATION_DISPLAY = {
    'comunicacion': 'comunicación',
    'matematica': 'matemática',
}


# ==========================================
# ETL Transform Class
# ==========================================

class ETLTransform:
    """Core ETL transformation engine for ENLA data.
    
    Transforms raw MongoDB data into BigQuery fact and dimension tables:
    1. Extract: Query MongoDB from configurable collection (default: enla_all_peru_raw)
    2. Filter: Apply nom_dre == 'CALLAO' filter in MongoDB query
    3. Transform: Pivot wide format → long format by area (DYNAMIC column discovery)
    4. Create dimensions: dim_meta, dim_calendario
    5. Load: Insert to BigQuery tables
    6. Validate: Data quality checks
    
    KEY CHANGES (2026-05-03):
    - Column names discovered DYNAMICALLY (vary by year: 2021/2022/2023)
    - Year extracted from FILENAME (not in Excel data)
    - Optional areas (ccss, cyt) handled gracefully
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
        
        logger.info(f"ETLTransform initialized | dataset_id={self.dataset_id}")
    
    def run_full_pipeline(self, year: Optional[int] = None) -> ETLResult:
        """
        Execute the complete ETL pipeline.
        
        Args:
            year: Optional year filter (if None, processes all years from data)
        
        Returns:
            ETLResult with execution status, data quality summary, and metadata
        """
        start_time = datetime.now(timezone.utc)
        tables_loaded = []
        total_rows = 0
        
        try:
            logger.info("=" * 60)
            logger.info("Starting ETL Pipeline: MongoDB → BigQuery")
            if year:
                logger.info(f"Filtering to year: {year}")
            logger.info("=" * 60)
            
            # Step 1: Connect to MongoDB and extract data
            logger.info("Step 1: Extracting data from MongoDB...")
            raw_df = self._extract_from_mongodb(year=year)
            
            if len(raw_df) == 0:
                msg = f"No data found for year={year}" if year else "No data found in MongoDB"
                logger.warning(msg)
                return ETLResult(
                    success=True,
                    data_quality=DataQualitySummary(),
                    tables_loaded=[],
                    total_rows_loaded=0,
                    execution_time_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
                    error_message=msg,
                )
            
            logger.info(f"Extracted {len(raw_df)} rows from MongoDB")
            
            # Step 2: Transform wide → long format (DYNAMIC column discovery)
            logger.info("Step 2: Transforming data (wide → long format)...")
            cleaned_df = self._transform_to_long_format(raw_df, year=year)
            logger.info(f"Transformed to {len(cleaned_df)} rows (long format)")
            
            # Step 3: Create fact_enla records
            logger.info("Step 3: Creating fact_enla records...")
            fact_df = self._create_fact_records(cleaned_df)
            logger.info(f"Created {len(fact_df)} fact records")
            
            # Step 4: Create dimension tables
            logger.info("Step 4: Creating dimension tables...")
            dim_meta_df = self._create_dim_meta(cleaned_df)
            dim_calendario_df = self._create_dim_calendario(cleaned_df)
            logger.info(f"Created dim_meta: {len(dim_meta_df)} rows, "
                       f"dim_calendario: {len(dim_calendario_df)} rows")
            
            # Step 5: Connect to BigQuery
            logger.info("Step 5: Connecting to BigQuery...")
            self.bq_manager.connect()
            self.bq_manager.create_dataset(self.dataset_id, location=settings.GCP_LOCATION)
            
            # Step 6: Load to BigQuery
            logger.info("Step 6: Loading data to BigQuery...")
            
            # Convert ALL columns that BigQuery expects as STRING
            def convert_string_columns(df, schema, df_name):
                """Convert DataFrame columns to string if schema expects STRING."""
                for field in schema:
                    if field.field_type == 'STRING' and field.name in df.columns:
                        # Convert any numeric type (int64, float64) to string
                        if df[field.name].dtype in ['int64', 'float64']:
                            logger.info(f"Converting {field.name} ({df[field.name].dtype}) to string in {df_name}")
                            df[field.name] = df[field.name].fillna('').astype(str).replace('nan', '').replace('<NA>', '')
                return df
            
            cleaned_df = convert_string_columns(cleaned_df, ENLA_CALLAO_CLEANED_SCHEMA, 'cleaned_df')
            fact_df = convert_string_columns(fact_df, FACT_ENLA_SCHEMA, 'fact_df')
            dim_meta_df = convert_string_columns(dim_meta_df, DIM_META_SCHEMA, 'dim_meta_df')
            dim_calendario_df = convert_string_columns(dim_calendario_df, DIM_CALENDARIO_SCHEMA, 'dim_calendario_df')
            
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
            
            logger.info(f"ETL Pipeline completed | tables={len(tables_loaded)} rows={total_rows} time={execution_time:.2f}s")
            
            return result
            
        except ETLTransformError as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_msg = f"ETL transformation error: {str(e)}"
            logger.error(error_msg)
            return ETLResult(success=False, data_quality=DataQualitySummary(),
                           tables_loaded=tables_loaded, total_rows_loaded=total_rows,
                           execution_time_seconds=execution_time, error_message=error_msg)
        except Exception as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_msg = f"Unexpected ETL error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ETLResult(success=False, data_quality=DataQualitySummary(),
                           tables_loaded=tables_loaded, total_rows_loaded=total_rows,
                           execution_time_seconds=execution_time, error_message=error_msg)
        finally:
            try:
                self.bq_manager.disconnect()
                self.mongo_manager.disconnect()
            except Exception as e:
                logger.warning("Error during connection cleanup", error=str(e))
    
    # ==========================================
    # Extract Phase
    # ==========================================
    
    def _extract_from_mongodb(self, year: Optional[int] = None) -> pd.DataFrame:
        """
        Extract records from MongoDB ETL source collection (default: enla_all_peru_raw).
        
        Applies region filter (nom_dre == 'CALLAO') to ensure only Callao data
        reaches BigQuery, even when the source collection contains all-Peru data.
        
        Args:
            year: Optional year filter
            
        Returns:
            DataFrame with raw ENLA data (Callao only)
        """
        try:
            collection = self.mongo_manager.get_collection(
                settings.MONGODB_DB,
                settings.MONGODB_ETL_SOURCE_COLLECTION
            )
            
            # Build query with Callao region filter (RF-007)
            query = {'nom_dre': 'CALLAO'}
            if year:
                query['ano_evaluacion'] = year
            
            cursor = collection.find(query)
            
            records = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                records.append(doc)
            
            if not records:
                msg = f"No records found in MongoDB" + (f" for year={year}" if year else "")
                logger.warning(msg)
                return pd.DataFrame()
            
            df = pd.DataFrame(records)
            
            logger.info(f"Extracted from MongoDB | rows={len(df)} columns={list(df.columns)[:10]}")
            
            return df
            
        except Exception as e:
            msg = f"Failed to extract data from MongoDB: {str(e)}"
            logger.error(msg)
            raise ETLTransformError(msg)
    
    # ==========================================
    # Transform Phase
    # ==========================================
    
    def _transform_to_long_format(self, raw_df: pd.DataFrame, year: Optional[int] = None) -> pd.DataFrame:
        """
        Transform wide-format data to long format by academic area.
        
        Uses DYNAMIC column discovery via regex patterns to handle different years
        with DIFFERENT column naming conventions.
        
        Args:
            raw_df: Raw DataFrame from MongoDB
            year: Year extracted from FILENAME
        
        Returns:
            DataFrame in long format
        """
        import sys
        print("DEBUG: Starting _transform_to_long_format", file=sys.stderr)
        logger.info(f"Transform input columns ({len(raw_df.columns)}): {list(raw_df.columns)[:20]}...")
        logger.info(f"Year parameter: {year}")
        
        # Determine year
        # NOTE: Data comes from MongoDB with already-standardized column names
        # (ENLA column_mapping.py is applied during ingestion), so we access
        # 'ano_evaluacion' directly from the DataFrame (no col_mapping needed)
        if year is None:
            try:
                if 'ano_evaluacion' in raw_df.columns:
                    year_values = raw_df['ano_evaluacion'].dropna()
                    if len(year_values) > 0:
                        year = int(float(year_values.iloc[0]))
                        logger.info(f"Year from 'ano_evaluacion' column: {year}")
            except Exception as e:
                logger.warning(f"Could not extract year from data: {e}")
        
        if year is None:
            logger.warning("Year not determined! Using 2023 as default")
            year = 2023
        
        logger.info(f"Processing data for year: {year}")
        
        # ==========================================
        # STANDARDIZED COLUMN MAPPING
        # ==========================================
        # After column standardization, we use standardized names directly
        # Columns are already renamed in MongoDB (by ingest_enla.py using column_mapping.py)
        area_columns = {}  # {area_name: {'measure': col, 'group': col, 'weight': col}}
        
        for area_key, config in STANDARDIZED_AREAS.items():
            measure_col = config['measure']
            group_col = config['group']
            weight_col = config['weight']
            
            # Check if the standardized columns exist in the DataFrame
            if measure_col in raw_df.columns and group_col in raw_df.columns:
                area_columns[area_key] = {
                    'measure': measure_col,
                    'group': group_col,
                    'weight': weight_col if weight_col in raw_df.columns else None
                }
                logger.info(f"✓ Found '{area_key}': measure={measure_col}, group={group_col}, weight={weight_col}")
            else:
                if config['required']:
                    logger.error(f"✗ REQUIRED area '{area_key}' NOT FOUND! measure_exists={measure_col in raw_df.columns}, group_exists={group_col in raw_df.columns}")
                    raise ETLTransformError(f"REQUIRED area '{area_key}' not found. Expected columns: {measure_col}, {group_col}. Available: {list(raw_df.columns)[:15]}")
                else:
                    logger.info(f"- Optional area '{area_key}' not present (OK)")
        
        if not area_columns:
            msg = f"No academic area columns found! Expected standardized columns. Available: {list(raw_df.columns)[:20]}"
            logger.error(msg)
            raise ETLTransformError(msg)
        
        # ==========================================
        # TRANSFORM TO LONG FORMAT
        # ==========================================
        all_records = []
        
        # DEBUG: Print area_columns to understand what was discovered
        logger.info(f"area_columns to process: {area_columns}")
        
        for area_key, cols in area_columns.items():
            try:
                # Normalize area name for display (add accents)
                area_display = ACCENT_NORMALIZATION_DISPLAY.get(area_key, area_key)
                
                # Handle comma as decimal separator (common in Latin American Excel files)
                measure_raw = raw_df[cols['measure']].astype(str)
                measure_clean = measure_raw.str.replace(',', '.', regex=False)
                scores = pd.to_numeric(measure_clean, errors='coerce')
                
                # DEBUG: Print what column we're using
                logger.info(f"Processing '{area_display}', using score column: {cols['measure']}")
                logger.info(f"  Sample raw values: {list(measure_raw[:3])}")
                logger.info(f"  Sample cleaned scores: {list(scores[:3])}")
                
                # Use per-record ano_evaluacion instead of global year variable
                per_record_year = pd.to_numeric(raw_df['ano_evaluacion'], errors='coerce')

                area_df = pd.DataFrame({
                    'id_ie': raw_df['id_ie'],
                    'id_seccion': raw_df['id_seccion'],
                    'nom_ie': raw_df['nom_ie'] if 'nom_ie' in raw_df.columns else None,
                    'nom_dre': raw_df['nom_dre'] if 'nom_dre' in raw_df.columns else None,
                    'year': per_record_year,
                    'area': raw_df['area'] if 'area' in raw_df.columns else None,
                    'cor_est': raw_df['cor_est'],
                    'area_academica': area_display,  # Use accent-normalized name for display
                    'score': scores,
                    'grupo': raw_df[cols['group']] if cols['group'] in raw_df.columns else None,
                    'peso': raw_df[cols['weight']] if cols['weight'] and cols['weight'] in raw_df.columns else None,
                    'is_null_score': scores.isna(),
                    'created_at': datetime.now(timezone.utc),
                })
                
                all_records.append(area_df)
                logger.info(f"Processed '{area_key}': {len(area_df)} records (null: {scores.isna().sum()})")
                
            except KeyError as e:
                if STANDARDIZED_AREAS[area_key]['required']:
                    logger.error(f"Failed to process REQUIRED area '{area_key}': {e}")
                    raise
                else:
                    logger.warning(f"Failed to process optional area '{area_key}': {e} (skipping)")
        
        if not all_records:
            msg = "No records created during transformation"
            logger.error(msg)
            raise ETLTransformError(msg)
        
        cleaned_df = pd.concat(all_records, ignore_index=True)
        cleaned_df = cleaned_df.sort_values(['id_ie', 'cor_est', 'year', 'area_academica']).reset_index(drop=True)
        
        logger.info(f"Transformation complete | input={len(raw_df)} output={len(cleaned_df)} areas={len(all_records)} year={year}")
        
        return cleaned_df
    
    # ==========================================
    # Fact Table Creation
    # ==========================================
    
    def _create_fact_records(self, cleaned_df: pd.DataFrame) -> pd.DataFrame:
        """Create fact_enla table records with UUID primary keys."""
        fact_df = pd.DataFrame({
            'fact_id': [str(uuid.uuid4()) for _ in range(len(cleaned_df))],
            'id_ie': cleaned_df['id_ie'],
            'id_seccion': cleaned_df['id_seccion'],
            'nom_ie': cleaned_df['nom_ie'],
            'year': cleaned_df['year'].astype(int),
            'area_academica': cleaned_df['area_academica'],
            'cor_est': cleaned_df['cor_est'],
            'score': cleaned_df['score'],
            'created_at': cleaned_df['created_at'],
        })
        
        logger.info(f"Fact records created | count={len(fact_df)}")
        return fact_df
    
    # ==========================================
    # Dimension Table Creation
    # ==========================================
    
    def _create_dim_meta(self, cleaned_df: pd.DataFrame) -> pd.DataFrame:
        """Create dim_meta table with institution targets per academic area per year."""
        # Select columns and drop duplicates (use double brackets for multiple columns in pandas)
        cols_to_select = ['id_ie', 'nom_ie', 'year', 'area_academica']
        unique_combos = cleaned_df[cols_to_select].drop_duplicates()
        
        # Normalize area names (defensive coding)
        unique_combos['area_academica'] = unique_combos['area_academica'].apply(normalize_area_name)
        
        dim_meta_df = pd.DataFrame({
            'meta_id': [str(uuid.uuid4()) for _ in range(len(unique_combos))],
            'id_ie': unique_combos['id_ie'].values,
            'nom_ie': unique_combos['nom_ie'].values,
            'year': unique_combos['year'].astype(int).values,
            'area_academica': unique_combos['area_academica'].values,  # Academic area, NOT geographic zone
            'target_score': settings.TARGET_SCORE_THRESHOLD,
            'region': settings.ENLA_REGION,
            'created_at': datetime.now(timezone.utc),
        })
        
        logger.info(f"dim_meta created | count={len(dim_meta_df)}")
        return dim_meta_df
        
        logger.info(f"dim_meta created | count={len(dim_meta_df)}")
        return dim_meta_df
    
    def _create_dim_calendario(self, cleaned_df: pd.DataFrame) -> pd.DataFrame:
        """Create dim_calendario table with date dimension for analysis."""
        # Get unique years from cleaned data (has 'year' column from filename)
        years = sorted(cleaned_df['year'].dropna().unique())
        
        all_dates = []
        for year in years:
            year_int = int(year)
            key_dates = [
                (year_int, 1, 1),
                (year_int, 4, 1),
                (year_int, 7, 1),
                (year_int, 10, 1),
                (year_int, 12, 31),
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
        logger.info(f"dim_calendario created | count={len(dim_cal_df)} years={list(years)}")
        return dim_cal_df
    
    # ==========================================
    # Data Quality Validation
    # ==========================================
    
    def _validate_data_quality(self, raw_df: pd.DataFrame,
                                cleaned_df: pd.DataFrame) -> DataQualitySummary:
        """Run data quality checks on transformed data."""
        summary = DataQualitySummary(
            total_input_rows=len(raw_df),
            total_output_rows=len(cleaned_df),
            areas_processed=cleaned_df['area_academica'].nunique() if 'area_academica' in cleaned_df.columns else 0,
        )
        
        # Check 1: NULL score coverage
        null_scores = cleaned_df['is_null_score'].sum() if 'is_null_score' in cleaned_df.columns else 0
        summary.null_scores_count = int(null_scores)
        summary.null_scores_percent = round((null_scores / len(cleaned_df)) * 100, 2) if len(cleaned_df) > 0 else 0.0
        
        logger.info(f"Data quality: NULL score coverage | null={summary.null_scores_count} pct={summary.null_scores_percent}%")
        
        # Check 2: Score range validity
        if 'is_null_score' in cleaned_df.columns:
            valid_scores = cleaned_df[~cleaned_df['is_null_score']]['score']
            if len(valid_scores) > 0:
                min_score = valid_scores.min()
                max_score = valid_scores.max()
                # ENLA scores are 0-1000 scale, not percentage
                out_of_range = ((valid_scores < 0) | (valid_scores > 1000)).sum()
                
                logger.info(f"Score range | min={min_score} max={max_score} out_of_range={out_of_range}")
                
                if out_of_range > 0:
                    summary.score_range_valid = False
                    summary.warnings.append(f"{out_of_range} scores out of valid range [0,1000]")
        
        # Check 3: Critical column NULL coverage
        critical_cols = ['id_ie', 'id_seccion', 'year', 'area_academica', 'cor_est']
        for col in critical_cols:
            if col in cleaned_df.columns:
                null_pct = round((cleaned_df[col].isna().sum() / len(cleaned_df)) * 100, 2)
                summary.critical_null_coverage[col] = null_pct
                
                if null_pct > 5.0:
                    summary.warnings.append(f"Column '{col}' has {null_pct}% NULL")
                if null_pct > 20.0:
                    summary.errors.append(f"FAIL: Column '{col}' has {null_pct}% NULL")
        
        # Check 4: Geographic zone distribution
        if 'area' in cleaned_df.columns:
            area_dist = cleaned_df['area'].value_counts().to_dict()
            logger.info(f"Geographic zone distribution | {area_dist}")
        
        logger.info(f"Data quality complete | valid={summary.is_valid} warnings={len(summary.warnings)} errors={len(summary.errors)}")
        
        return summary


# ==========================================
# Convenience Function
# ==========================================

def run_etl_pipeline(mongodb_uri: Optional[str] = None,
                      gcp_project_id: Optional[str] = None,
                      gcp_credentials_path: Optional[str] = None,
                      year: Optional[int] = None) -> ETLResult:
    """
    Run the complete ETL pipeline from MongoDB to BigQuery.
    
    Args:
        mongodb_uri: MongoDB connection string (uses env if None)
        gcp_project_id: GCP project ID (uses env if None)
        gcp_credentials_path: Path to GCP credentials JSON (uses env if None)
        year: Year extracted from FILENAME (e.g., 2021, 2022, 2023).
    
    Returns:
        ETLResult with execution status and metadata
    """
    transform = ETLTransform(
        mongodb_uri=mongodb_uri,
        gcp_project_id=gcp_project_id,
        gcp_credentials_path=gcp_credentials_path,
    )
    return transform.run_full_pipeline(year=year)
