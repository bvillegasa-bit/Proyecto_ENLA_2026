"""ENLA data ingestion module from Excel to MongoDB."""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import re
from pymongo.errors import PyMongoError, DuplicateKeyError

from src.logging.setup import get_logger
from src.ingestion.validators import ENLAValidator, ValidationReport
from src.ingestion.config import settings
from src.ingestion.column_mapping import (
    UNIFIED_SCHEMA, YEAR_RENAME_DICTS, detect_file_format,
    EXTRA_2022_FIELDS
)
from src.database.mongo_client import get_mongo_client, MongoConnectionError

logger = get_logger('ingestion')


class IngestionError(Exception):
    """Base exception for ingestion errors."""
    pass


def extract_year_from_filename(filename: str) -> Optional[int]:
    """
    Extract year from filename like: data_2022.xlsx, ENLA_2023.xlsx, enla_2021.xlsx
    
    Args:
        filename: Name of the Excel file
        
    Returns:
        Year as integer (e.g., 2022) or None if not found
    """
    # Match patterns like: 2022, 2023, 2021 in the filename
    match = re.search(r'20(\d{2})', filename)
    if match:
        year = 2000 + int(match.group(1))
        logger.info(f"Extracted year {year} from filename: {filename}")
        return year
    logger.warning(f"Could not extract year from filename: {filename}")
    return None


class ENLAIngestor:
    """
    Complete ENLA data ingestion pipeline.
    
    Responsibilities:
    1. Read Excel file with encoding handling
    2. Extract year from FILENAME (not from data)
    3. Filter by region and grade
    4. Validate data quality (with flexible column validation)
    5. Deduplicate using compound key
    6. UPSERT into MongoDB (with year added to each record)
    7. Log audit trail
    """
    
    # Core columns that should be present in ALL years (standardized snake_case names)
    CORE_COLUMNS = {
        'id_ie', 'id_seccion', 'nom_ie', 'nom_dre',
        'ano_evaluacion', 'grado_evaluacion',
        'cor_est', 'area',  # cor_est = student ID, area = geographic zone
    }

    # UPSERT_KEY uses standardized names
    UPSERT_KEY = ['id_ie', 'id_seccion', 'ano_evaluacion']
    
    def __init__(
        self,
        mongodb_uri: Optional[str] = None,
        db_name: str = 'enla_db',
        collection_raw: str = 'enla_callao_raw',
        collection_log: str = 'enla_ingestion_log'
    ):
        """
        Initialize ENLA ingestor.
        
        Args:
            mongodb_uri: MongoDB connection string
            db_name: Database name
            collection_raw: Raw data collection name
            collection_log: Ingestion log collection name
        """
        self.mongodb_uri = mongodb_uri or settings.MONGODB_URI
        self.db_name = db_name
        self.collection_raw = collection_raw
        self.collection_log = collection_log
        
        self.client = None
        self.db = None
        self.mongo_collection = None
        self.log_collection = None
        
        self.ingestion_id = str(uuid.uuid4())
        self.validator = ENLAValidator()
        
        logger.info(f"ENLAIngestor initialized | db_name={db_name} collection_raw={collection_raw} ingestion_id={self.ingestion_id}")
    
    def _connect(self):
        """Connect to MongoDB."""
        try:
            self.client = get_mongo_client(self.mongodb_uri)
            self.db = self.client[self.db_name]
            self.mongo_collection = self.db[self.collection_raw]
            self.log_collection = self.db[self.collection_log]
            logger.info("MongoDB connection successful")
        except MongoConnectionError as e:
            logger.error(f"Failed to connect to MongoDB | error={str(e)}")
            raise IngestionError(f"MongoDB connection failed: {e}")
    
    def _disconnect(self):
        """Disconnect from MongoDB.
        
        Note: We don't close the global singleton client here because
        it's shared across multiple operations. Just release the reference.
        """
        if self.client:
            # Don't close the global singleton client - it's managed by get_mongo_client()
            # Setting to None releases our reference, connection stays open for reuse
            self.client = None
            self.db = None
            self.mongo_collection = None
            self.log_collection = None
            logger.info("MongoDB reference released (connection pooled for reuse)")

    def _detect_year(self, df: pd.DataFrame, file_path: str) -> Optional[int]:
        """
        Detect the year/format of the Excel file.
        
        Uses detect_file_format() from column_mapping module:
        - Primary: Check distinctive columns (M500_EM_2S_2023_CT → 2023, M500_L → 2022)
        - Secondary: Extract year from filename
        
        Args:
            df: DataFrame with original column names (after stripping)
            file_path: Path to the Excel file (for filename extraction)
        
        Returns:
            Detected year as integer, or None if unknown
        """
        filename = Path(file_path).name if file_path else None
        format_key, detected_year = detect_file_format(df, filename)
        
        if format_key == 'unknown':
            logger.warning(f"Could not detect file format for {file_path}. "
                          f"Columns: {list(df.columns)[:10]}...")
            return None
        
        logger.info(f"Detected file format: {format_key} (year={detected_year})")
        return detected_year

    def _rename_columns(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Rename columns to standardized names and ensure all UNIFIED_SCHEMA columns exist.
        
        Args:
            df: DataFrame with original column names
            year: Detected year (2022, 2023, etc.)
        
        Returns:
            DataFrame with standardized column names
        """
        year_str = str(year)
        
        if year_str in YEAR_RENAME_DICTS:
            rename_dict = YEAR_RENAME_DICTS[year_str]
            # Only rename columns that exist in the DataFrame
            rename_dict_filtered = {k: v for k, v in rename_dict.items() if k in df.columns}
            df = df.rename(columns=rename_dict_filtered)
            logger.info(f"Applied {len(rename_dict_filtered)} column renames for year {year}")
            
            # Log unmapped columns
            unmapped = [col for col in df.columns if col not in UNIFIED_SCHEMA and col not in EXTRA_2022_FIELDS]
            if unmapped:
                logger.info(f"Found {len(unmapped)} unmapped columns (will preserve): {unmapped[:5]}...")
        
        # Add missing UNIFIED_SCHEMA columns with None
        missing_schema_cols = [col for col in UNIFIED_SCHEMA if col not in df.columns]
        for col in missing_schema_cols:
            df[col] = None
        
        if missing_schema_cols:
            logger.info(f"Added {len(missing_schema_cols)} missing UNIFIED_SCHEMA columns with None")
        
        # Ensure all 33 UNIFIED_SCHEMA columns exist
        final_cols = [col for col in UNIFIED_SCHEMA if col in df.columns]
        logger.info(f"Standardization complete: {len(final_cols)} UNIFIED_SCHEMA columns present")
        
        return df

    def read_excel(self, file_path: str, year: Optional[int] = None) -> pd.DataFrame:
        """
        Read Excel file.
        
        Args:
            file_path: Path to Excel file
            year: Year to add as 'ano_evaluacion' column (extracted from filename)
        
        Returns:
            DataFrame with 'ano_evaluacion' column added if year is provided
        """
        path = Path(file_path)
        
        if not path.exists():
            msg = f"Input file not found at {file_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)
        
        try:
            # Excel files are binary, no encoding needed
            df = pd.read_excel(path)
            logger.info(f"Excel file read successfully | file_path={str(path)} rows={len(df)}")
        except Exception as e:
            logger.warning(f"Failed to read Excel file, trying with openpyxl engine | file_path={str(path)} error={str(e)}")
            try:
                df = pd.read_excel(path, engine='openpyxl')
                logger.info(f"Excel file read with openpyxl | file_path={str(path)} rows={len(df)}")
            except Exception as e2:
                msg = f"Cannot read Excel file: {str(e2)}"
                logger.error(msg)
                raise IngestionError(msg)
        
        # NOTE: Preserve original column names (mixed case from Excel)
        df.columns = df.columns.str.strip()  # Only strip whitespace, preserve case

        # =================================================================
        # NEW: Column Standardization Pipeline
        # =================================================================

        # Step 1: Detect file format/year
        detected_year = self._detect_year(df, file_path)

        # Step 2: Rename columns to standardized names and add missing UNIFIED_SCHEMA columns
        if detected_year:
            df = self._rename_columns(df, detected_year)
        else:
            logger.warning(f"Could not detect year for {file_path}. "
                          f"Columns will remain in original format.")

        # =================================================================
        # Backward Compatibility: Handle cases where detection failed
        # =================================================================

        # Add missing required columns with defaults (if not already handled by _rename_columns)
        if 'nom_ie' not in df.columns:
            df['nom_ie'] = df.get('ID_IE', df.get('id_ie', '')).astype(str) + ' - Unknown'
            logger.info("Added missing 'nom_ie' column with default values")

        # Add grado_evaluacion if missing (all Excel files are 2do de secundaria)
        if 'grado_evaluacion' not in df.columns and 'Grado' not in df.columns:
            df['grado_evaluacion'] = 2
            logger.info("Added missing 'grado_evaluacion' column with default value 2 (all data is 2do)")

        # Add year column from filename if not present in data
        if year and 'ano_evaluacion' not in df.columns:
            df['ano_evaluacion'] = year
            logger.info(f"Added 'ano_evaluacion' column with year {year} from filename")
        elif 'ano_evaluacion' in df.columns:
            logger.info(f"Using 'ano_evaluacion' from Excel data (years: {df['ano_evaluacion'].unique()})")
        else:
            logger.warning("No 'ano_evaluacion' column and no year provided - data will use default")

        return df
    
    def filter_data(self, df: pd.DataFrame,
                   region: str = None,
                   grado: int = None,
                   year: int = None) -> pd.DataFrame:
        """
        Filter data by region, grade, and year.
        
        Args:
            df: DataFrame to filter
            region: Region name (default from settings)
            grado: Grade level (default from settings)
            year: Specific year to filter (if None, uses settings.ENLA_YEARS)
        
        Returns:
            Filtered DataFrame
        """
        region = region or settings.ENLA_REGION
        grado = grado or settings.ENLA_GRADO
        
        original_size = len(df)
        
        # Filter by region (columns are now standardized to 'nom_dre')
        if 'nom_dre' in df.columns:
            df['nom_dre'] = df['nom_dre'].str.upper().str.strip()
            df = df[df['nom_dre'] == region.upper()]
            logger.info(f"Filtered by region: {region}")
        else:
            logger.warning(f"No region column 'nom_dre' found, skipping region filter")
        
        # Filter by grade (columns are now standardized to 'grado_evaluacion')
        if 'grado_evaluacion' in df.columns:
            # Normalize grade values (handle string representations like '2do')
            grade_map = {
                '2do': 2, '3ro': 3, '4to': 4, '5to': 5,
                '2': 2, '3': 3, '4': 4, '5': 5
            }
            df['grado_evaluacion'] = df['grado_evaluacion'].map(lambda x: grade_map.get(str(x), x))
            df = df[df['grado_evaluacion'] == grado]
            logger.info(f"Filtered by grade: {grado}")
        else:
            logger.warning(f"No grade column 'grado_evaluacion' found, skipping grade filter")
        
        # Filter by year - if specific year provided, filter to that year only
        if 'ano_evaluacion' in df.columns:
            if year:
                df = df[df['ano_evaluacion'] == year]
                logger.info(f"Filtered to specific year: {year}")
            else:
                df = df[df['ano_evaluacion'].isin(settings.ENLA_YEARS)]
        
        filtered_size = len(df)
        
        logger.info(f"Data filtered | original_rows={original_size} filtered_rows={filtered_size} region={region} grado={grado}")
        
        return df
    
    def validate(self, df: pd.DataFrame) -> ValidationReport:
        """
        Validate DataFrame against ENLA requirements.
        
        Args:
            df: DataFrame to validate
        
        Returns:
            ValidationReport
        """
        report = self.validator.validate(df)
        
        logger.info(f"Validation completed | is_valid={report.is_valid} error_count={len(report.errors)} warning_count={len(report.warnings)}")
        
        return report
    
    def deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove duplicates based on UPSERT key.
        
        Args:
            df: DataFrame to deduplicate
        
        Returns:
            Deduplicated DataFrame
        """
        original_size = len(df)
        df = df.drop_duplicates(subset=self.UPSERT_KEY, keep='last')
        deduplicated_size = len(df)
        duplicates_removed = original_size - deduplicated_size
        
        logger.info(f"Deduplication completed | original_rows={original_size} deduplicated_rows={deduplicated_size} duplicates_removed={duplicates_removed}")
        
        return df
    
    def upsert_to_mongodb(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        UPSERT DataFrame rows to MongoDB.
        
        Args:
            df: DataFrame to insert
        
        Returns:
            Dict with insert/update counts
        """
        if self.mongo_collection is None:
            raise IngestionError("MongoDB collection not initialized")
        
        counts = {
            'inserted': 0,
            'updated': 0,
            'failed': 0,
            'errors': []
        }
        
        for idx, row in df.iterrows():
            try:
                filter_doc = {k: row[k] for k in self.UPSERT_KEY}
                update_doc = {'$set': row.to_dict()}
                
                result = self.mongo_collection.update_one(
                    filter_doc,
                    update_doc,
                    upsert=True
                )
                
                if result.upserted_id:
                    counts['inserted'] += 1
                elif result.modified_count > 0:
                    counts['updated'] += 1
                
            except PyMongoError as e:
                counts['failed'] += 1
                error_msg = f"Row {idx}: {str(e)}"
                counts['errors'].append(error_msg)
                logger.warning(f"Failed to upsert row | row_index={idx} error={str(e)}")
        
        logger.info(f"UPSERT completed | inserted={counts['inserted']} updated={counts['updated']} failed={counts['failed']}")
        
        return counts
    
    def log_ingestion(self, summary: Dict[str, Any]):
        """
        Log ingestion event to MongoDB audit trail.
        
        Args:
            summary: Ingestion summary to log
        """
        if self.log_collection is None:
            return
        
        log_entry = {
            'ingestion_id': self.ingestion_id,
            'timestamp': datetime.utcnow().isoformat(),
            'file_path': summary.get('file_path', ''),
            'rows_read': summary.get('rows_read', 0),
            'rows_filtered': summary.get('rows_filtered', 0),
            'rows_inserted': summary.get('rows_inserted', 0),
            'rows_updated': summary.get('rows_updated', 0),
            'rows_failed': summary.get('rows_failed', 0),
            'status': summary.get('status', 'unknown'),
            'error_count': len(summary.get('errors', [])),
            'validation_report': summary.get('validation_report', {})
        }
        
        try:
            self.log_collection.insert_one(log_entry)
            logger.info(f"Ingestion logged to MongoDB audit trail | ingestion_id={self.ingestion_id}")
        except PyMongoError as e:
            logger.error(f"Failed to log ingestion to MongoDB | error={str(e)}")
    
    def ingest(self, file_path: str,
               region: str = None,
               grado: int = None) -> Dict[str, Any]:
        """
        Execute full ingestion pipeline.
        
        Args:
            file_path: Path to Excel file (year will be extracted from filename)
            region: Region filter (default from settings)
            grado: Grade filter (default from settings)
        
        Returns:
            Summary dict with ingestion results including 'year_extracted'
        """
        summary = {
            'status': 'failed',
            'timestamp': datetime.utcnow().isoformat(),
            'ingestion_id': self.ingestion_id,
            'file_path': file_path,
            'year_extracted': None,
            'rows_read': 0,
            'rows_filtered': 0,
            'rows_inserted': 0,
            'rows_updated': 0,
            'rows_failed': 0,
            'validation_report': {},
            'errors': []
        }
        
        try:
            # Step 0: Extract year from FILENAME (NOT from data!)
            filename = Path(file_path).name
            year = extract_year_from_filename(filename)
            summary['year_extracted'] = year
            
            if year is None:
                logger.warning(f"Could not extract year from filename '{filename}', will try from data if available")
            
            # Step 1: Read Excel (pass year to add as column)
            logger.info(f"Starting ingestion pipeline | file_path={file_path} year={year}")
            df = self.read_excel(file_path, year=year)
            summary['rows_read'] = len(df)
            
            # Step 2: Filter data (pass year for filtering)
            df = self.filter_data(df, region=region, grado=grado, year=year)
            summary['rows_filtered'] = len(df)
            
            if len(df) == 0:
                msg = "No data found after filtering"
                logger.warning(msg)
                summary['errors'].append(msg)
                summary['status'] = 'no_data'  # No data after filtering
                return summary
            
            # Step 3: Validate (with flexible column checking)
            validation_report = self.validate(df)
            summary['validation_report'] = {
                'is_valid': validation_report.is_valid,
                'error_count': len(validation_report.errors),
                'warning_count': len(validation_report.warnings),
                'statistics': validation_report.statistics
            }
            
            if not validation_report.is_valid:
                for error in validation_report.errors:
                    summary['errors'].append(error)
                # Continue anyway for warnings
            
            # Step 4: Deduplicate
            df = self.deduplicate(df)
            
            # Step 5: Connect to MongoDB and UPSERT
            self._connect()
            upsert_counts = self.upsert_to_mongodb(df)
            
            summary['rows_inserted'] = upsert_counts['inserted']
            summary['rows_updated'] = upsert_counts['updated']
            summary['rows_failed'] = upsert_counts['failed']
            
            for error in upsert_counts['errors'][:10]:  # Log first 10 errors
                summary['errors'].append(error)
            
            summary['status'] = 'success'
            logger.info(f"Ingestion completed successfully | ingestion_id={self.ingestion_id} status='success' year={year}")
            
        except Exception as e:
            summary['status'] = 'failed'
            summary['errors'].append(str(e))
            logger.error(f"Ingestion failed | ingestion_id={self.ingestion_id} error={str(e)}")
        
        finally:
            # Step 6: Log audit trail
            self.log_ingestion(summary)
            self._disconnect()
        
        return summary


def ingest_enla_xlsx(file_path: str,
                     region: str = None,
                     grado: int = None,
                     mongodb_uri: str = None) -> Dict[str, Any]:
    """
    Convenience function for ENLA ingestion.
    
    Args:
        file_path: Path to Excel file
        region: Region filter
        grado: Grade filter
        mongodb_uri: MongoDB connection string
    
    Returns:
        Summary dict
    """
    ingestor = ENLAIngestor(mongodb_uri=mongodb_uri)
    return ingestor.ingest(file_path, region=region, grado=grado)
