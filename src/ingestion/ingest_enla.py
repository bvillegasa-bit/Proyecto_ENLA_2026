"""ENLA data ingestion module from Excel to MongoDB."""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
from pymongo.errors import MongoError, DuplicateKeyError

from src.logging.setup import get_logger
from src.ingestion.validators import ENLAValidator, ValidationReport
from src.ingestion.config import settings
from src.database.mongo_client import get_mongo_client, MongoConnectionError

logger = get_logger('ingestion')


class IngestionError(Exception):
    """Base exception for ingestion errors."""
    pass


class ENLAIngestor:
    """
    Complete ENLA data ingestion pipeline.
    
    Responsibilities:
    1. Read Excel file with encoding handling
    2. Filter by region and grade
    3. Validate data quality
    4. Deduplicate using compound key
    5. UPSERT into MongoDB
    6. Log audit trail
    """
    
    REQUIRED_COLUMNS = {
        'id_ie', 'id_seccion', 'nom_ie', 'nom_dre',
        'ano_evaluacion', 'grado_evaluacion',
        'cor_est_comunicacion', 'cor_est_matematica',
        'cor_est_ccss', 'cor_est_cyt'
    }
    
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
        
        logger.info("ENLAIngestor initialized",
                   db_name=db_name,
                   collection_raw=collection_raw,
                   ingestion_id=self.ingestion_id)
    
    def _connect(self):
        """Connect to MongoDB."""
        try:
            self.client = get_mongo_client(self.mongodb_uri)
            self.db = self.client[self.db_name]
            self.mongo_collection = self.db[self.collection_raw]
            self.log_collection = self.db[self.collection_log]
            logger.info("MongoDB connection successful")
        except MongoConnectionError as e:
            logger.error("Failed to connect to MongoDB", error=str(e))
            raise IngestionError(f"MongoDB connection failed: {e}")
    
    def _disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    def read_excel(self, file_path: str, encoding: str = 'latin-1') -> pd.DataFrame:
        """
        Read Excel file with encoding handling.
        
        Args:
            file_path: Path to Excel file
            encoding: Primary encoding (default: latin-1, fallback: utf-8)
        
        Returns:
            DataFrame
        
        Raises:
            FileNotFoundError: If file does not exist
            IngestionError: If file cannot be read
        """
        path = Path(file_path)
        
        if not path.exists():
            msg = f"Input file not found at {file_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)
        
        try:
            # Try primary encoding
            df = pd.read_excel(path, encoding=encoding)
            logger.info("Excel file read successfully",
                       file_path=str(path),
                       rows=len(df),
                       encoding=encoding)
        except (UnicodeDecodeError, Exception) as e:
            logger.warning("Primary encoding failed, trying utf-8",
                          file_path=str(path),
                          error=str(e))
            try:
                df = pd.read_excel(path, encoding='utf-8')
                logger.info("Excel file read with utf-8",
                           file_path=str(path),
                           rows=len(df))
            except Exception as e2:
                msg = f"Cannot read Excel file: {str(e2)}"
                logger.error(msg)
                raise IngestionError(msg)
        
        # Normalize column names to lowercase
        df.columns = df.columns.str.lower().str.strip()
        
        return df
    
    def filter_data(self, df: pd.DataFrame,
                   region: str = None,
                   grado: int = None) -> pd.DataFrame:
        """
        Filter data by region, grade, and years.
        
        Args:
            df: DataFrame to filter
            region: Region name (default from settings)
            grado: Grade level (default from settings)
        
        Returns:
            Filtered DataFrame
        """
        region = region or settings.ENLA_REGION
        grado = grado or settings.ENLA_GRADO
        
        original_size = len(df)
        
        # Normalize region column
        if 'nom_dre' in df.columns:
            df['nom_dre'] = df['nom_dre'].str.upper().str.strip()
        
        # Apply filters
        df = df[df['nom_dre'] == region.upper()]
        
        if 'grado_evaluacion' in df.columns:
            df = df[df['grado_evaluacion'] == grado]
        
        if 'ano_evaluacion' in df.columns:
            df = df[df['ano_evaluacion'].isin(settings.ENLA_YEARS)]
        
        filtered_size = len(df)
        
        logger.info("Data filtered",
                   original_rows=original_size,
                   filtered_rows=filtered_size,
                   region=region,
                   grado=grado)
        
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
        
        logger.info("Validation completed",
                   is_valid=report.is_valid,
                   error_count=len(report.errors),
                   warning_count=len(report.warnings))
        
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
        
        logger.info("Deduplication completed",
                   original_rows=original_size,
                   deduplicated_rows=deduplicated_size,
                   duplicates_removed=duplicates_removed)
        
        return df
    
    def upsert_to_mongodb(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        UPSERT DataFrame rows to MongoDB.
        
        Args:
            df: DataFrame to insert
        
        Returns:
            Dict with insert/update counts
        """
        if not self.mongo_collection:
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
                
            except MongoError as e:
                counts['failed'] += 1
                error_msg = f"Row {idx}: {str(e)}"
                counts['errors'].append(error_msg)
                logger.warning("Failed to upsert row",
                             row_index=idx,
                             error=str(e))
        
        logger.info("UPSERT completed",
                   inserted=counts['inserted'],
                   updated=counts['updated'],
                   failed=counts['failed'])
        
        return counts
    
    def log_ingestion(self, summary: Dict[str, Any]):
        """
        Log ingestion event to MongoDB audit trail.
        
        Args:
            summary: Ingestion summary to log
        """
        if not self.log_collection:
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
            logger.info("Ingestion logged to MongoDB audit trail",
                       ingestion_id=self.ingestion_id)
        except MongoError as e:
            logger.error("Failed to log ingestion to MongoDB",
                        error=str(e))
    
    def ingest(self, file_path: str,
              region: str = None,
              grado: int = None) -> Dict[str, Any]:
        """
        Execute full ingestion pipeline.
        
        Args:
            file_path: Path to Excel file
            region: Region filter (default from settings)
            grado: Grade filter (default from settings)
        
        Returns:
            Summary dict with ingestion results
        """
        summary = {
            'status': 'failed',
            'timestamp': datetime.utcnow().isoformat(),
            'ingestion_id': self.ingestion_id,
            'file_path': file_path,
            'rows_read': 0,
            'rows_filtered': 0,
            'rows_inserted': 0,
            'rows_updated': 0,
            'rows_failed': 0,
            'validation_report': {},
            'errors': []
        }
        
        try:
            # Step 1: Read Excel
            logger.info("Starting ingestion pipeline", file_path=file_path)
            df = self.read_excel(file_path)
            summary['rows_read'] = len(df)
            
            # Step 2: Filter data
            df = self.filter_data(df, region=region, grado=grado)
            summary['rows_filtered'] = len(df)
            
            if len(df) == 0:
                msg = "No data found after filtering"
                logger.warning(msg)
                summary['errors'].append(msg)
                summary['status'] = 'success'  # Not an error, just empty result
                return summary
            
            # Step 3: Validate
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
            logger.info("Ingestion completed successfully",
                       ingestion_id=self.ingestion_id,
                       status='success')
            
        except Exception as e:
            summary['status'] = 'failed'
            summary['errors'].append(str(e))
            logger.error("Ingestion failed",
                        ingestion_id=self.ingestion_id,
                        error=str(e))
        
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
