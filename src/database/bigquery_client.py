"""BigQuery connection manager for ENLA pipeline."""

import os
from typing import Optional, List, Dict, Any
from google.cloud import bigquery
from google.cloud.bigquery import SchemaField, Table
from google.api_core.exceptions import GoogleAPIError, NotFound
import pandas as pd
from src.logging.setup import get_logger

logger = get_logger('bigquery_client')


class BigQueryConnectionError(Exception):
    """Exception for BigQuery connection errors."""
    pass


class BigQueryClientManager:
    """Manages BigQuery connections and operations."""
    
    def __init__(self, project_id: Optional[str] = None,
                 credentials_path: Optional[str] = None):
        """
        Initialize BigQuery connection manager.
        
        Args:
            project_id: GCP project ID. If None, reads from GCP_PROJECT_ID env variable.
            credentials_path: Path to service account JSON file. If None, uses default credentials.
        
        Raises:
            BigQueryConnectionError: If no project ID is provided or found.
        """
        self.project_id = project_id or os.getenv('GCP_PROJECT_ID', '')
        self.credentials_path = credentials_path or os.getenv('GCP_CREDENTIALS_PATH', None)
        
        if not self.project_id:
            msg = "GCP_PROJECT_ID not provided or found in environment variables"
            logger.error(msg)
            raise BigQueryConnectionError(msg)
        
        self.client: Optional[bigquery.Client] = None
        logger.info("BigQueryClientManager initialized", project_id=self.project_id)
    
    def connect(self) -> bigquery.Client:
        """
        Connect to BigQuery.
        
        Returns:
            BigQuery Client instance
        
        Raises:
            BigQueryConnectionError: If connection fails
        """
        try:
            client_kwargs = {"project": self.project_id}
            
            if self.credentials_path:
                from google.oauth2 import service_account
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
                client_kwargs["credentials"] = credentials
                logger.info("Using service account credentials", path=self.credentials_path)
            
            self.client = bigquery.Client(**client_kwargs)
            
            # Test connection with a simple query
            query_job = self.client.query("SELECT 1")
            query_job.result()
            
            logger.info("BigQuery connection successful", project_id=self.project_id)
            return self.client
            
        except GoogleAPIError as e:
            msg = f"Failed to connect to BigQuery: {str(e)}"
            logger.error(msg)
            raise BigQueryConnectionError(msg)
    
    def disconnect(self):
        """Close BigQuery connection."""
        if self.client:
            self.client.close()
            self.client = None
            logger.info("BigQuery connection closed")
    
    def get_client(self) -> bigquery.Client:
        """
        Get or create BigQuery client.
        
        Returns:
            BigQuery Client instance
        """
        if self.client is None:
            self.connect()
        return self.client
    
    def create_dataset(self, dataset_id: str, location: str = 'US',
                       exists_ok: bool = True) -> bigquery.Dataset:
        """
        Create a BigQuery dataset.
        
        Args:
            dataset_id: Dataset ID (without project prefix)
            location: Dataset location
            exists_ok: If True, return existing dataset instead of raising error
        
        Returns:
            BigQuery Dataset object
        
        Raises:
            BigQueryConnectionError: If dataset creation fails
        """
        if not self.client:
            self.connect()
        
        full_dataset_id = f"{self.project_id}.{dataset_id}"
        dataset_ref = bigquery.Dataset(full_dataset_id)
        dataset_ref.location = location
        
        try:
            dataset = self.client.create_dataset(dataset_ref, exists_ok=exists_ok)
            logger.info("Dataset created/verified", dataset_id=full_dataset_id)
            return dataset
        except GoogleAPIError as e:
            msg = f"Failed to create dataset {full_dataset_id}: {str(e)}"
            logger.error(msg)
            raise BigQueryConnectionError(msg)
    
    def create_table(self, dataset_id: str, table_id: str,
                     schema: List[SchemaField],
                     exists_ok: bool = True) -> Table:
        """
        Create a BigQuery table.
        
        Args:
            dataset_id: Dataset ID (without project prefix)
            table_id: Table ID
            schema: List of SchemaField objects defining table schema
            exists_ok: If True, return existing table instead of raising error
        
        Returns:
            BigQuery Table object
        
        Raises:
            BigQueryConnectionError: If table creation fails
        """
        if not self.client:
            self.connect()
        
        full_table_id = f"{self.project_id}.{dataset_id}.{table_id}"
        table_ref = bigquery.Table(full_table_id, schema=schema)
        
        try:
            table = self.client.create_table(table_ref, exists_ok=exists_ok)
            logger.info("Table created/verified", table_id=full_table_id,
                       schema_fields=len(schema))
            return table
        except GoogleAPIError as e:
            msg = f"Failed to create table {full_table_id}: {str(e)}"
            logger.error(msg)
            raise BigQueryConnectionError(msg)
    
    def load_table_from_dataframe(self, dataset_id: str, table_id: str,
                                   dataframe: pd.DataFrame,
                                   write_disposition: str = 'WRITE_TRUNCATE',
                                   schema: Optional[List[SchemaField]] = None) -> dict:
        """
        Load a pandas DataFrame to a BigQuery table.
        
        Args:
            dataset_id: Dataset ID (without project prefix)
            table_id: Table ID
            dataframe: Pandas DataFrame to load
            write_disposition: WRITE_TRUNCATE, WRITE_APPEND, or WRITE_EMPTY
            schema: Optional explicit schema (inferred from DataFrame if None)
        
        Returns:
            dict with load statistics (rows_loaded, table_id, job_id)
        
        Raises:
            BigQueryConnectionError: If load fails
        """
        if not self.client:
            self.connect()
        
        full_table_id = f"{self.project_id}.{dataset_id}.{table_id}"
        
        job_config = bigquery.LoadJobConfig(
            write_disposition=write_disposition,
        )
        
        if schema:
            job_config.schema = schema
        
        try:
            logger.info("Loading DataFrame to BigQuery",
                       table_id=full_table_id,
                       rows=len(dataframe),
                       write_disposition=write_disposition)
            
            job = self.client.load_table_from_dataframe(
                dataframe, full_table_id, job_config=job_config
            )
            job.result()  # Wait for job to complete
            
            stats = {
                'rows_loaded': len(dataframe),
                'table_id': full_table_id,
                'job_id': job.job_id,
                'destination_table': job.destination.table_id,
            }
            
            logger.info("DataFrame loaded successfully", **stats)
            return stats
            
        except GoogleAPIError as e:
            msg = f"Failed to load DataFrame to {full_table_id}: {str(e)}"
            logger.error(msg)
            raise BigQueryConnectionError(msg)
    
    def query(self, query_sql: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Execute a query and return results as a DataFrame.
        
        Args:
            query_sql: SQL query string
            params: Optional query parameters
        
        Returns:
            DataFrame with query results
        
        Raises:
            BigQueryConnectionError: If query fails
        """
        if not self.client:
            self.connect()
        
        try:
            job_config = bigquery.QueryJobConfig()
            if params:
                job_config.query_parameters = [
                    bigquery.ScalarQueryParameter(k, self._infer_type(v), v)
                    for k, v in params.items()
                ]
            
            query_job = self.client.query(query_sql, job_config=job_config)
            result = query_job.result()
            
            df = result.to_dataframe()
            logger.info("Query executed successfully",
                       rows_returned=len(df),
                       bytes_processed=query_job.total_bytes_processed)
            
            return df
            
        except GoogleAPIError as e:
            msg = f"Query execution failed: {str(e)}"
            logger.error(msg, query=query_sql)
            raise BigQueryConnectionError(msg)
    
    @staticmethod
    def _infer_type(value: Any) -> str:
        """Infer BigQuery parameter type from Python value."""
        if isinstance(value, bool):
            return "BOOL"
        elif isinstance(value, int):
            return "INT64"
        elif isinstance(value, float):
            return "FLOAT64"
        elif isinstance(value, str):
            return "STRING"
        else:
            return "STRING"
    
    def table_exists(self, dataset_id: str, table_id: str) -> bool:
        """
        Check if a table exists.
        
        Args:
            dataset_id: Dataset ID
            table_id: Table ID
        
        Returns:
            True if table exists, False otherwise
        """
        if not self.client:
            self.connect()
        
        full_table_id = f"{self.project_id}.{dataset_id}.{table_id}"
        try:
            self.client.get_table(full_table_id)
            return True
        except NotFound:
            return False


# Global connection manager instance
_bq_manager: Optional[BigQueryClientManager] = None


def get_bq_manager(project_id: Optional[str] = None,
                   credentials_path: Optional[str] = None) -> BigQueryClientManager:
    """
    Get or create the global BigQuery connection manager.
    
    Args:
        project_id: GCP project ID (only used on first call)
        credentials_path: Path to service account JSON file
    
    Returns:
        BigQueryClientManager instance
    """
    global _bq_manager
    if _bq_manager is None:
        _bq_manager = BigQueryClientManager(project_id, credentials_path)
    return _bq_manager


def get_bq_client(project_id: Optional[str] = None,
                  credentials_path: Optional[str] = None) -> bigquery.Client:
    """
    Get BigQuery client.
    
    Args:
        project_id: GCP project ID (optional)
        credentials_path: Path to service account JSON file
    
    Returns:
        BigQuery Client instance
    """
    manager = get_bq_manager(project_id, credentials_path)
    if manager.client is None:
        manager.connect()
    return manager.client
