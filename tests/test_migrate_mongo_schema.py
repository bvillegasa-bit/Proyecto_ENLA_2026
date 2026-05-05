"""
Tests for MongoDB migration script.

Tests for:
- MongoSchemaMigrator class
- Dry-run mode
- Migration logic
- Rollback logic
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from scripts.migrate_mongo_schema import MongoSchemaMigrator
from src.ingestion.column_mapping import RENAME_2022, RENAME_2023, YEAR_RENAME_DICTS


class TestMongoSchemaMigratorInit:
    """Tests for MongoSchemaMigrator initialization."""

    def test_init_defaults(self):
        """Test initialization with default parameters."""
        migrator = MongoSchemaMigrator()
        assert migrator.db_name == 'enla_db'
        assert migrator.collection_name == 'enla_callao_raw'
        assert migrator.dry_run == False
        assert migrator.batch_size == 1000

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        migrator = MongoSchemaMigrator(
            mongodb_uri='mongodb://custom:27017',
            db_name='custom_db',
            collection_name='custom_coll',
            dry_run=True,
            batch_size=500
        )
        assert migrator.mongodb_uri == 'mongodb://custom:27017'
        assert migrator.db_name == 'custom_db'
        assert migrator.dry_run == True
        assert migrator.batch_size == 500


class TestBuildRenameOp:
    """Tests for _build_rename_op() method."""

    def test_build_normal_migration(self):
        """Test building rename op for normal migration."""
        migrator = MongoSchemaMigrator()
        rename_dict = {'OldName': 'new_name', 'OtherOld': 'other_new'}
        result = migrator._build_rename_op(rename_dict, reverse=False)
        assert result == {'OldName': 'new_name', 'OtherOld': 'other_new'}

    def test_build_rollback(self):
        """Test building rename op for rollback (reverse)."""
        migrator = MongoSchemaMigrator()
        rename_dict = {'OldName': 'new_name', 'OtherOld': 'other_new'}
        result = migrator._build_rename_op(rename_dict, reverse=True)
        assert result == {'new_name': 'OldName', 'other_new': 'OtherOld'}


class TestMigrateYear:
    """Tests for migrate_year() method."""

    @patch('scripts.migrate_mongo_schema.MongoSchemaMigrator._get_existing_columns')
    @patch('scripts.migrate_mongo_schema.MongoSchemaMigrator.connect')
    @patch('scripts.migrate_mongo_schema.MongoSchemaMigrator.disconnect')
    def test_migrate_year_dry_run(self, mock_disconnect, mock_connect, mock_get_existing):
        """Test migrate_year() in dry-run mode."""
        mock_get_existing.return_value = ['M500_L', 'ID_IE', 'cor_est']

        migrator = MongoSchemaMigrator(dry_run=True)
        migrator.client = Mock()
        migrator.collection = Mock()
        migrator.collection.find_one.return_value = {'M500_L': 500, 'ID_IE': 'IE001'}
        migrator.collection.count_documents.return_value = 100

        result = migrator.migrate_year(2022, rollback=False)

        assert result['dry_run'] == True
        assert result['updated_count'] == 100
        mock_get_existing.assert_called_once_with(2022)

    @patch('scripts.migrate_mongo_schema.MongoSchemaMigrator._get_existing_columns')
    def test_migrate_year_no_docs(self, mock_get_existing):
        """Test migrate_year() when no documents exist for year."""
        mock_get_existing.return_value = []

        migrator = MongoSchemaMigrator()
        result = migrator.migrate_year(2022, rollback=False)

        assert result['updated_count'] == 0
        assert result['error_count'] == 0

    def test_migrate_year_no_rename_dict(self):
        """Test migrate_year() for unsupported year."""
        migrator = MongoSchemaMigrator()
        result = migrator.migrate_year(2099, rollback=False)

        assert 'error' in result


class TestRollback:
    """Tests for rollback functionality."""

    @patch('scripts.migrate_mongo_schema.MongoSchemaMigrator._get_existing_columns')
    @patch('scripts.migrate_mongo_schema.MongoSchemaMigrator.connect')
    @patch('scripts.migrate_mongo_schema.MongoSchemaMigrator.disconnect')
    def test_rollback_dry_run(self, mock_disconnect, mock_connect, mock_get_existing):
        """Test rollback in dry-run mode."""
        mock_get_existing.return_value = ['medida_lectura', 'id_ie', 'cor_est']

        migrator = MongoSchemaMigrator(dry_run=True)
        migrator.client = Mock()
        migrator.collection = Mock()
        migrator.collection.find_one.return_value = {'medida_lectura': 500, 'id_ie': 'IE001'}

        result = migrator.migrate_year(2022, rollback=True)

        assert result['dry_run'] == True


class TestPreviewChanges:
    """Tests for preview_changes() method."""

    @patch('scripts.migrate_mongo_schema.MongoSchemaMigrator._get_existing_columns')
    def test_preview_changes(self, mock_get_existing):
        """Test preview_changes() output."""
        mock_get_existing.return_value = ['M500_L', 'ID_IE', 'cor_est']

        migrator = MongoSchemaMigrator()
        migrator.client = Mock()
        migrator.collection = Mock()
        migrator.collection.find_one.return_value = {'M500_L': 500, 'ID_IE': 'IE001'}
        migrator.collection.count_documents.return_value = 100

        # Just verify it doesn't crash
        migrator.preview_changes(year=2022)


class TestGetExistingColumns:
    """Tests for _get_existing_columns() method."""

    def test_get_existing_columns_with_docs(self):
        """Test when documents exist."""
        migrator = MongoSchemaMigrator()
        migrator.collection = Mock()
        migrator.collection.find_one.return_value = {
            '_id': 'some_id',
            'M500_L': 500,
            'ID_IE': 'IE001',
            'cor_est': '001'
        }

        result = migrator._get_existing_columns(2022)

        assert 'M500_L' in result
        assert 'ID_IE' in result
        assert '_id' not in result  # MongoDB _id should be excluded

    def test_get_existing_columns_no_docs(self):
        """Test when no documents exist."""
        migrator = MongoSchemaMigrator()
        migrator.collection = Mock()
        migrator.collection.find_one.return_value = None

        result = migrator._get_existing_columns(2022)

        assert result == []
