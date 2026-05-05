"""
MongoDB Schema Migration Script for ENLA Column Standardization.

This script migrates existing MongoDB documents from original column names
to standardized snake_case names defined in src/ingestion/column_mapping.py

Usage:
    python scripts/migrate_mongo_schema.py [--dry-run] [--rollback] [--year YEAR]
    
Options:
    --dry-run       Preview changes without executing them
    --rollback      Reverse the migration (standardized → original names)
    --year YEAR     Migrate only documents for specific year (2022 or 2023)
    --batch-size N  Number of documents to process in each batch (default: 1000)
"""

import argparse
import logging
import sys
from typing import Dict, List, Any, Optional
from pymongo import MongoClient, UpdateMany
from pymongo.errors import PyMongoError
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('migration')

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ingestion.column_mapping import (
    RENAME_2022, RENAME_2023, YEAR_RENAME_DICTS, UNIFIED_SCHEMA
)


class MongoSchemaMigrator:
    """Migrate MongoDB schema to use standardized column names."""

    def __init__(
        self,
        mongodb_uri: str = None,
        db_name: str = 'enla_db',
        collection_name: str = 'enla_callao_raw',
        dry_run: bool = False,
        batch_size: int = 1000
    ):
        """
        Initialize migrator.

        Args:
            mongodb_uri: MongoDB connection string
            db_name: Database name
            collection_name: Collection to migrate
            dry_run: If True, only preview changes
            batch_size: Number of documents per batch
        """
        self.mongodb_uri = mongodb_uri or os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        self.db_name = db_name
        self.collection_name = collection_name
        self.dry_run = dry_run
        self.batch_size = batch_size

        self.client = None
        self.db = None
        self.collection = None

        logger.info(f"Initialized migrator | db={db_name} collection={collection_name} dry_run={dry_run}")

    def connect(self):
        """Connect to MongoDB."""
        try:
            self.client = MongoClient(self.mongodb_uri)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            # Test connection
            self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB | {self.mongodb_uri}")
        except PyMongoError as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    def _build_rename_op(self, rename_dict: Dict[str, str], reverse: bool = False) -> Dict[str, str]:
        """
        Build MongoDB $rename operation from rename dictionary.

        Args:
            rename_dict: Original mapping (original_name → standardized_name)
            reverse: If True, swap keys and values (for rollback)

        Returns:
            Dictionary suitable for $rename operator
        """
        if reverse:
            # For rollback: standardized → original
            return {v: k for k, v in rename_dict.items()}
        else:
            # Normal migration: original → standardized
            return rename_dict

    def _get_existing_columns(self, year: int) -> List[str]:
        """
        Get a sample document to see what columns exist.

        Args:
            year: Year to check

        Returns:
            List of column names in the sample document
        """
        sample = self.collection.find_one({'ano_evaluacion': year})
        if sample:
            # Remove MongoDB _id field
            columns = [k for k in sample.keys() if k != '_id']
            return columns
        return []

    def migrate_year(self, year: int, rollback: bool = False) -> Dict[str, Any]:
        """
        Migrate documents for a specific year.

        Args:
            year: Year to migrate (2022 or 2023)
            rollback: If True, perform rollback instead of migration

        Returns:
            Dictionary with migration statistics
        """
        year_str = str(year)
        if year_str not in YEAR_RENAME_DICTS:
            logger.error(f"No rename dictionary found for year {year}")
            return {'error': f'No rename dictionary for year {year}'}

        rename_dict = YEAR_RENAME_DICTS[year_str]
        rename_op = self._build_rename_op(rename_dict, reverse=rollback)

        # Get existing columns to only rename fields that actually exist
        existing_columns = self._get_existing_columns(year)
        if not existing_columns:
            logger.warning(f"No documents found for year {year}")
            return {'updated_count': 0, 'skipped_count': 0, 'error_count': 0}

        logger.info(f"Sample document columns for {year}: {existing_columns[:10]}...")

        # Filter rename operations to only include fields that exist
        if rollback:
            # For rollback, check if standardized names exist
            applicable_renames = {k: v for k, v in rename_op.items() if k in existing_columns}
        else:
            # For migration, check if original names exist
            applicable_renames = {k: v for k, v in rename_op.items() if k in existing_columns}

        if not applicable_renames:
            logger.info(f"No applicable renames for year {year} (rollback={rollback})")
            return {'updated_count': 0, 'skipped_count': 0, 'error_count': 0}

        logger.info(f"Applying {len(applicable_renames)} renames for year {year}: {list(applicable_renames.items())[:5]}...")

        if self.dry_run:
            logger.info(f"[DRY RUN] Would apply $rename: {applicable_renames}")
            doc_count = self.collection.count_documents({'ano_evaluacion': year})
            return {
                'updated_count': doc_count,
                'skipped_count': 0,
                'error_count': 0,
                'dry_run': True,
                'renames': applicable_renames
            }

        # Perform the migration in batches
        updated_count = 0
        error_count = 0
        skipped_count = 0

        # We need to update all documents for this year
        # Using update_many with $rename
        try:
            # Build the $rename operation
            rename_operation = {'$rename': applicable_renames}

            # Update all documents for this year
            result = self.collection.update_many(
                {'ano_evaluacion': year},
                rename_operation
            )

            updated_count = result.modified_count
            logger.info(f"Year {year}: Updated {updated_count} documents")

        except PyMongoError as e:
            logger.error(f"Error migrating year {year}: {e}")
            error_count += 1

        return {
            'updated_count': updated_count,
            'skipped_count': skipped_count,
            'error_count': error_count
        }

    def migrate_all(self, rollback: bool = False, specific_year: Optional[int] = None):
        """
        Migrate all years or a specific year.

        Args:
            rollback: If True, perform rollback
            specific_year: Only migrate this year (if specified)

        Returns:
            Dictionary with overall statistics
        """
        years = [specific_year] if specific_year else [2022, 2023]

        total_stats = {
            'years_processed': 0,
            'total_updated': 0,
            'total_skipped': 0,
            'total_errors': 0,
            'by_year': {}
        }

        for year in years:
            logger.info(f"{'Rolling back' if rollback else 'Migrating'} year {year}...")
            year_stats = self.migrate_year(year, rollback=rollback)
            total_stats['by_year'][year] = year_stats
            total_stats['years_processed'] += 1
            total_stats['total_updated'] += year_stats.get('updated_count', 0)
            total_stats['total_skipped'] += year_stats.get('skipped_count', 0)
            total_stats['total_errors'] += year_stats.get('error_count', 0)

        return total_stats

    def preview_changes(self, year: Optional[int] = None):
        """
        Preview what changes will be made without executing them.

        Args:
            year: Specific year to preview (or all if None)
        """
        years = [year] if year else [2022, 2023]

        print("\n" + "="*80)
        print("MIGRATION PREVIEW (DRY RUN)")
        print("="*80)

        for yr in years:
            yr_str = str(yr)
            if yr_str not in YEAR_RENAME_DICTS:
                print(f"\nYear {yr}: No rename dictionary found - SKIPPING")
                continue

            rename_dict = YEAR_RENAME_DICTS[yr_str]
            existing = self._get_existing_columns(yr)

            print(f"\nYear {yr}:")
            print(f"  Documents in DB: {self.collection.count_documents({'ano_evaluacion': yr})}")
            print(f"  Existing columns (sample): {existing[:10]}...")

            # Show what will be renamed
            applicable = {k: v for k, v in rename_dict.items() if k in existing}
            print(f"  Columns to rename: {len(applicable)}")
            for orig, std in list(applicable.items())[:10]:
                print(f"    {orig} → {std}")
            if len(applicable) > 10:
                print(f"    ... and {len(applicable) - 10} more")

        print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Migrate ENLA MongoDB schema to standardized column names'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without executing them'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Reverse the migration (standardized → original names)'
    )
    parser.add_argument(
        '--year',
        type=int,
        choices=[2022, 2023],
        help='Migrate only specific year'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Number of documents per batch (default: 1000)'
    )
    parser.add_argument(
        '--mongodb-uri',
        type=str,
        help='MongoDB connection string (overrides MONGODB_URI env var)'
    )

    args = parser.parse_args()

    # Initialize migrator
    migrator = MongoSchemaMigrator(
        mongodb_uri=args.mongodb_uri,
        dry_run=args.dry_run,
        batch_size=args.batch_size
    )

    try:
        migrator.connect()

        if args.dry_run:
            # Just preview changes
            migrator.preview_changes(year=args.year)
        else:
            # Perform migration or rollback
            action = "rollback" if args.rollback else "migration"
            logger.info(f"Starting {action}...")

            stats = migrator.migrate_all(
                rollback=args.rollback,
                specific_year=args.year
            )

            print("\n" + "="*80)
            print(f"MIGRATION COMPLETE: {action.upper()}")
            print("="*80)
            print(f"Years processed: {stats['years_processed']}")
            print(f"Total documents updated: {stats['total_updated']}")
            print(f"Total documents skipped: {stats['total_skipped']}")
            print(f"Total errors: {stats['total_errors']}")

            if stats.get('by_year'):
                print("\nBy year:")
                for year, year_stats in stats['by_year'].items():
                    print(f"  {year}: updated={year_stats.get('updated_count', 0)}, "
                          f"errors={year_stats.get('error_count', 0)}")

            print("="*80 + "\n")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        migrator.disconnect()


if __name__ == '__main__':
    main()
