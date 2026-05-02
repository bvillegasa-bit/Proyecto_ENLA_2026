"""MongoDB connection manager for ENLA pipeline."""

import os
from typing import Optional
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
from src.logging.setup import get_logger

logger = get_logger('mongo_client')


class MongoConnectionError(Exception):
    """Exception for MongoDB connection errors."""
    pass


class MongoClientManager:
    """Manages MongoDB connections and operations."""
    
    def __init__(self, mongodb_uri: Optional[str] = None):
        """
        Initialize MongoDB connection manager.
        
        Args:
            mongodb_uri: MongoDB connection string. If None, reads from MONGODB_URI env variable.
        
        Raises:
            MongoConnectionError: If no connection URI is provided or found.
        """
        self.mongodb_uri = mongodb_uri or os.getenv('MONGODB_URI', '')
        
        if not self.mongodb_uri:
            msg = "MONGODB_URI not provided or found in environment variables"
            logger.error(msg)
            raise MongoConnectionError(msg)
        
        self.client = None
        logger.info("MongoClientManager initialized")
    
    def connect(self, timeout_ms: int = 5000) -> MongoClient:
        """
        Connect to MongoDB.
        
        Args:
            timeout_ms: Connection timeout in milliseconds
        
        Returns:
            MongoClient instance
        
        Raises:
            MongoConnectionError: If connection fails
        """
        try:
            self.client = MongoClient(self.mongodb_uri, serverSelectionTimeoutMS=timeout_ms)
            # Test connection
            self.client.admin.command('ping')
            logger.info("MongoDB connection successful")
            return self.client
        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            msg = f"Failed to connect to MongoDB: {str(e)}"
            logger.error(msg)
            raise MongoConnectionError(msg)
    
    def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    def test_connection(self) -> bool:
        """
        Test MongoDB connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            if not self.client:
                self.connect()
            self.client.admin.command('ping')
            logger.info("MongoDB connection test passed")
            return True
        except Exception as e:
            logger.error(f"MongoDB connection test failed | error={str(e)}")
            return False
    
    def get_database(self, db_name: str):
        """
        Get a database object.
        
        Args:
            db_name: Database name
        
        Returns:
            Database object
        """
        if not self.client:
            self.connect()
        return self.client[db_name]
    
    def get_collection(self, db_name: str, collection_name: str):
        """
        Get a collection object.
        
        Args:
            db_name: Database name
            collection_name: Collection name
        
        Returns:
            Collection object
        """
        if not self.client:
            self.connect()
        return self.client[db_name][collection_name]


# Global connection manager instance
_mongo_manager: Optional[MongoClientManager] = None


def get_mongo_manager(mongodb_uri: Optional[str] = None) -> MongoClientManager:
    """
    Get or create the global MongoDB connection manager.
    
    Args:
        mongodb_uri: MongoDB connection string (only used on first call)
    
    Returns:
        MongoClientManager instance
    """
    global _mongo_manager
    if _mongo_manager is None:
        _mongo_manager = MongoClientManager(mongodb_uri)
    return _mongo_manager


def get_mongo_client(mongodb_uri: Optional[str] = None) -> MongoClient:
    """
    Get MongoDB client.
    
    Args:
        mongodb_uri: MongoDB connection string (optional)
    
    Returns:
        MongoClient instance
    """
    manager = get_mongo_manager(mongodb_uri)
    if manager.client is None:
        manager.connect()
    return manager.client
