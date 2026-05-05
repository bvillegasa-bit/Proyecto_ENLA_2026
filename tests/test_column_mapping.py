"""
Unit tests for column_mapping module.

Tests for:
- detect_file_format()
- RENAME_2022 and RENAME_2023 dictionaries
- UNIFIED_SCHEMA constant
- extract_year_from_filename()
- apply_column_renaming()
"""

import pytest
import pandas as pd
from src.ingestion.column_mapping import (
    UNIFIED_SCHEMA, RENAME_2022, RENAME_2023, YEAR_RENAME_DICTS,
    detect_file_format, extract_year_from_filename, apply_column_renaming,
    CORE_ID_FIELDS, GEOGRAPHIC_FIELDS, SCHOOL_FIELDS, STUDENT_FIELDS,
    LECTURA_FIELDS, MATEMATICA_FIELDS, CIENCIAS_FIELDS
)


class TestUnifiedSchema:
    """Tests for UNIFIED_SCHEMA constant."""

    def test_unified_schema_length(self):
        """Test that UNIFIED_SCHEMA has exactly 33 fields."""
        assert len(UNIFIED_SCHEMA) == 33, f"Expected 33 fields, got {len(UNIFIED_SCHEMA)}"

    def test_unified_schema_unique(self):
        """Test that all field names in UNIFIED_SCHEMA are unique."""
        assert len(UNIFIED_SCHEMA) == len(set(UNIFIED_SCHEMA)), "UNIFIED_SCHEMA contains duplicate fields"

    def test_unified_schema_snake_case(self):
        """Test that all field names are valid snake_case."""
        import re
        pattern = re.compile(r'^[a-z][a-z0-9_]*$')
        for field in UNIFIED_SCHEMA:
            assert pattern.match(field), f"Field '{field}' is not valid snake_case"

    def test_core_id_fields_in_schema(self):
        """Test that all core ID fields are in UNIFIED_SCHEMA."""
        for field in CORE_ID_FIELDS:
            assert field in UNIFIED_SCHEMA, f"Core ID field '{field}' not in UNIFIED_SCHEMA"

    def test_geographic_fields_in_schema(self):
        """Test that all geographic fields are in UNIFIED_SCHEMA."""
        for field in GEOGRAPHIC_FIELDS:
            assert field in UNIFIED_SCHEMA, f"Geographic field '{field}' not in UNIFIED_SCHEMA"

    def test_school_fields_in_schema(self):
        """Test that all school fields are in UNIFIED_SCHEMA."""
        for field in SCHOOL_FIELDS:
            assert field in UNIFIED_SCHEMA, f"School field '{field}' not in UNIFIED_SCHEMA"

    def test_student_fields_in_schema(self):
        """Test that all student fields are in UNIFIED_SCHEMA."""
        for field in STUDENT_FIELDS:
            assert field in UNIFIED_SCHEMA, f"Student field '{field}' not in UNIFIED_SCHEMA"

    def test_assessment_fields_in_schema(self):
        """Test that all assessment fields are in UNIFIED_SCHEMA."""
        for field in LECTURA_FIELDS + MATEMATICA_FIELDS + CIENCIAS_FIELDS:
            assert field in UNIFIED_SCHEMA, f"Assessment field '{field}' not in UNIFIED_SCHEMA"


class TestExtractYearFromFilename:
    """Tests for extract_year_from_filename()."""

    def test_extract_2022(self):
        assert extract_year_from_filename("ENLA_2022.xlsx") == 2022

    def test_extract_2023(self):
        assert extract_year_from_filename("data_2023.xlsx") == 2023

    def test_extract_2021(self):
        assert extract_year_from_filename("enla_2021.xlsx") == 2021

    def test_extract_from_path(self):
        assert extract_year_from_filename("C:/data/ENLA_2022_v2.xlsx") == 2022

    def test_no_year_in_filename(self):
        assert extract_year_from_filename("data.xlsx") is None

    def test_invalid_filename(self):
        assert extract_year_from_filename("") is None


class TestDetectFileFormat:
    """Tests for detect_file_format()."""

    def test_detect_2023_by_column(self):
        """Test 2023 detection by M500_EM_2S_2023_CT column."""
        df = pd.DataFrame(columns=['M500_EM_2S_2023_CT', 'ID_IE', 'nom_DRE'])
        format_key, year = detect_file_format(df)
        assert format_key == '2023'
        assert year == 2023

    def test_detect_2022_by_column(self):
        """Test 2022 detection by M500_L column."""
        df = pd.DataFrame(columns=['M500_L', 'ID_seccion', 'nom_DRE'])
        format_key, year = detect_file_format(df)
        assert format_key == '2022'
        assert year == 2022

    def test_detect_2023_by_filename_fallback(self):
        """Test 2023 detection by filename when columns don't match."""
        df = pd.DataFrame(columns=['col1', 'col2', 'col3'])
        format_key, year = detect_file_format(df, "ENLA_2023.xlsx")
        assert format_key == '2023'
        assert year == 2023

    def test_detect_2022_by_filename_fallback(self):
        """Test 2022 detection by filename when columns don't match."""
        df = pd.DataFrame(columns=['col1', 'col2'])
        format_key, year = detect_file_format(df, "data_2022.xlsx")
        assert format_key == '2022'
        assert year == 2022

    def test_detect_unknown_format(self):
        """Test unknown format detection."""
        df = pd.DataFrame(columns=['unknown_col1', 'unknown_col2'])
        format_key, year = detect_file_format(df, "unknown.xlsx")
        assert format_key == 'unknown'
        assert year is None

    def test_detect_with_none_filename(self):
        """Test detection with None filename."""
        df = pd.DataFrame(columns=['M500_L'])
        format_key, year = detect_file_format(df, filename=None)
        assert format_key == '2022'
        assert year == 2022


class TestRenameDictionaries:
    """Tests for RENAME_2022 and RENAME_2023 dictionaries."""

    def test_rename_2022_has_mappings(self):
        """Test that RENAME_2022 has the required mappings."""
        # Check core fields
        assert 'Año' in RENAME_2022
        assert RENAME_2022['Año'] == 'ano_evaluacion'
        assert 'Grado' in RENAME_2022
        assert RENAME_2022['Grado'] == 'grado_evaluacion'
        assert 'ID_IE' in RENAME_2022
        assert RENAME_2022['ID_IE'] == 'id_ie'

    def test_rename_2022_assessment_columns(self):
        """Test that 2022 assessment columns are mapped."""
        assert 'M500_L' in RENAME_2022
        assert RENAME_2022['M500_L'] == 'medida_lectura'
        assert 'M500_M' in RENAME_2022
        assert RENAME_2022['M500_M'] == 'medida_matematica'
        assert 'M500_CN' in RENAME_2022
        assert RENAME_2022['M500_CN'] == 'medida_ciencias'

    def test_rename_2022_extra_fields(self):
        """Test that 2022-only fields are mapped."""
        assert 'pikIE_L' in RENAME_2022
        assert RENAME_2022['pikIE_L'] == 'pikie_lectura'
        assert 'prob_sec_L' in RENAME_2022
        assert RENAME_2022['prob_sec_L'] == 'prob_sec_lectura'

    def test_rename_2023_has_mappings(self):
        """Test that RENAME_2023 has the required mappings."""
        assert 'M500_EM_2S_2023_CT' in RENAME_2023
        assert RENAME_2023['M500_EM_2S_2023_CT'] == 'medida_lectura'
        assert 'M500_EM_2S_2023_MA' in RENAME_2023
        assert RENAME_2023['M500_EM_2S_2023_MA'] == 'medida_matematica'
        assert 'M500_EM_2S_2023_CS' in RENAME_2023
        assert RENAME_2023['M500_EM_2S_2023_CS'] == 'medida_ciencias'

    def test_year_rename_dicts_has_both_years(self):
        """Test that YEAR_RENAME_DICTS contains both years."""
        assert '2022' in YEAR_RENAME_DICTS
        assert '2023' in YEAR_RENAME_DICTS
        assert YEAR_RENAME_DICTS['2022'] == RENAME_2022
        assert YEAR_RENAME_DICTS['2023'] == RENAME_2023


class TestApplyColumnRenaming:
    """Tests for apply_column_renaming() function."""

    def test_rename_2022_dataframe(self):
        """Test renaming a 2022 DataFrame."""
        df = pd.DataFrame({
            'M500_L': [500.0],
            'ID_IE': ['IE001'],
            'ID_seccion': ['SEC001'],
            'nom_DRE': ['CALLAO'],
            'cor_est': ['001'],
        })
        result = apply_column_renaming(df, '2022')

        # Check renamed columns exist
        assert 'medida_lectura' in result.columns
        assert 'id_ie' in result.columns
        assert 'id_seccion' in result.columns
        assert 'nom_dre' in result.columns
        assert 'cor_est' in result.columns

        # Check old columns are gone (renamed)
        assert 'M500_L' not in result.columns
        assert 'ID_IE' not in result.columns

    def test_rename_2023_dataframe(self):
        """Test renaming a 2023 DataFrame."""
        df = pd.DataFrame({
            'M500_EM_2S_2023_CT': [500.0],
            'ID_IE': ['IE001'],
            'ID_SECCION': ['SEC001'],
            'nom_DRE': ['CALLAO'],
            'cor_est': ['001'],
        })
        result = apply_column_renaming(df, '2023')

        # Check renamed columns exist
        assert 'medida_lectura' in result.columns
        assert 'id_ie' in result.columns
        assert 'id_seccion' in result.columns

        # Check old columns are gone
        assert 'M500_EM_2S_2023_CT' not in result.columns

    def test_missing_unified_schema_columns_added(self):
        """Test that missing UNIFIED_SCHEMA columns are added with None."""
        df = pd.DataFrame({
            'M500_L': [500.0],
            'ID_IE': ['IE001'],
        })
        result = apply_column_renaming(df, '2022')

        # Check that all UNIFIED_SCHEMA columns are present
        for col in UNIFIED_SCHEMA:
            assert col in result.columns, f"Missing UNIFIED_SCHEMA column: {col}"

        # Check that missing columns have None values
        assert result['grado_evaluacion'].isna().all()
        assert result['nom_dre'].isna().all()

    def test_idempotency(self):
        """Test that running apply_column_renaming twice doesn't break."""
        df = pd.DataFrame({
            'M500_L': [500.0],
            'ID_IE': ['IE001'],
        })
        result1 = apply_column_renaming(df, '2022')
        result2 = apply_column_renaming(result1, '2022')

        # Should have same columns after second run
        assert set(result1.columns) == set(result2.columns)
        assert len(result2) == 1

    def test_unknown_year_returns_unchanged(self):
        """Test that unknown year returns DataFrame with UNIFIED_SCHEMA columns added."""
        df = pd.DataFrame({
            'col1': [1],
            'col2': [2],
        })
        result = apply_column_renaming(df, '2099')
        # No rename happens, but UNIFIED_SCHEMA columns should be added
        assert 'col1' in result.columns
        assert 'col2' in result.columns
        # All UNIFIED_SCHEMA columns should exist
        for col in UNIFIED_SCHEMA:
            assert col in result.columns, f"Missing UNIFIED_SCHEMA column: {col}"
        # Original columns should still be present
        assert result['col1'].iloc[0] == 1
        assert result['col2'].iloc[0] == 2
