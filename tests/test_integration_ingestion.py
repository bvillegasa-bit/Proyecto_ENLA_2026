"""
Integration tests for ENLA ingestion with column standardization.

Tests the full pipeline with sample data.
"""

import pytest
import pandas as pd
from pathlib import Path
from typing import Optional
import tempfile
import os

from src.ingestion.ingest_enla import ENLAIngestor, extract_year_from_filename
from src.ingestion.column_mapping import (
    UNIFIED_SCHEMA, RENAME_2022, RENAME_2023, detect_file_format
)


class TestReadExcel2022:
    """Integration tests for reading 2022 Excel files."""

    @pytest.fixture
    def sample_2022_data(self):
        """Create sample 2022 DataFrame with original column names."""
        return pd.DataFrame({
            'Año': [2022],
            'Grado': [2],
            'Nivel': ['Secundaria'],
            'ID_estudiante': ['EST001'],
            'ID_IE': ['IE001'],
            'ID_seccion': ['SEC001'],
            'Seccion': ['A'],
            'cor_est': ['001'],
            'cod_DRE': ['DRE01'],
            'nom_DRE': ['CALLAO'],
            'cod_UGEL': ['UGEL01'],
            'nom_UGEL': ['CALLAO'],
            'Departamento': ['CALLAO'],
            'Provincia': ['CALLAO'],
            'Distrito': ['CALLAO'],
            'Gestion2': ['Publica'],
            'Area': ['Urbana'],
            'Sexo': ['M'],
            'M500_L': [500.0],
            'grupo_L': ['Alto'],
            'peso_L': [1.0],
            'M500_M': [450.0],
            'grupo_M': ['Medio'],
            'peso_M': [1.0],
            'M500_CN': [400.0],
            'grupo_CN': ['Bajo'],
            'peso_CN': [1.0],
            'pikIE_L': [450.0],
            'prob_sec_L': [0.75],
        })

    @pytest.fixture
    def sample_2022_excel(self, sample_2022_data, tmp_path):
        """Create a temporary Excel file with 2022 data."""
        file_path = tmp_path / "ENLA_2022.xlsx"
        sample_2022_data.to_excel(file_path, index=False)
        return str(file_path)

    def test_read_2022_excel_columns_standardized(self, sample_2022_excel):
        """Test that 2022 Excel file columns are standardized after read_excel()."""
        ingestor = ENLAIngestor()
        df = ingestor.read_excel(sample_2022_excel)

        # Check that standardized columns exist
        assert 'medida_lectura' in df.columns
        assert 'medida_matematica' in df.columns
        assert 'medida_ciencias' in df.columns
        assert 'id_ie' in df.columns
        assert 'id_seccion' in df.columns
        assert 'ano_evaluacion' in df.columns

        # Check that old column names are gone (renamed)
        assert 'M500_L' not in df.columns
        assert 'M500_M' not in df.columns
        assert 'M500_CN' not in df.columns
        assert 'ID_IE' not in df.columns
        assert 'ID_seccion' not in df.columns

    def test_read_2022_all_unified_schema_columns(self, sample_2022_excel):
        """Test that all UNIFIED_SCHEMA columns are present after read_excel()."""
        ingestor = ENLAIngestor()
        df = ingestor.read_excel(sample_2022_excel)

        for col in UNIFIED_SCHEMA:
            assert col in df.columns, f"Missing UNIFIED_SCHEMA column: {col}"

    def test_read_2022_extra_fields_preserved(self, sample_2022_excel):
        """Test that 2022-only fields are preserved."""
        ingestor = ENLAIngestor()
        df = ingestor.read_excel(sample_2022_excel)

        # 2022-only fields should be preserved (they're in RENAME_2022)
        assert 'pikie_lectura' in df.columns
        assert 'prob_sec_lectura' in df.columns

    def test_read_2022_year_extracted(self, sample_2022_excel):
        """Test that year is correctly extracted from filename."""
        ingestor = ENLAIngestor()
        df = ingestor.read_excel(sample_2022_excel)

        assert 'ano_evaluacion' in df.columns
        assert (df['ano_evaluacion'] == 2022).all()


class TestReadExcel2023:
    """Integration tests for reading 2023 Excel files."""

    @pytest.fixture
    def sample_2023_data(self):
        """Create sample 2023 DataFrame with original column names."""
        return pd.DataFrame({
            'M500_EM_2S_2023_CT': [500.0],
            'grupo_EM_2S_2023_CT': ['Alto'],
            'peso_CT': [1.0],
            'M500_EM_2S_2023_MA': [450.0],
            'grupo_EM_2S_2023_MA': ['Medio'],
            'peso_MA': [1.0],
            'M500_EM_2S_2023_CS': [400.0],
            'grupo_EM_2S_2023_CS': ['Bajo'],
            'peso_CS': [1.0],
            'ID_IE': ['IE001'],
            'ID_SECCION': ['SEC001'],
            'cor_est': ['001'],
            'grado_evaluacion': [2],
            'nivel': ['Secundaria'],
            'seccion': ['A'],
            'cod_DRE': ['DRE01'],
            'nom_DRE': ['CALLAO'],
            'cod_UGEL': ['UGEL01'],
            'nom_UGEL': ['CALLAO'],
            'Departamento': ['CALLAO'],
            'Provincia': ['CALLAO'],
            'Distrito': ['CALLAO'],
            'Gestion2': ['Publica'],
            'Area': ['Urbana'],
            'Sexo': ['M'],
        })

    @pytest.fixture
    def sample_2023_excel(self, sample_2023_data, tmp_path):
        """Create a temporary Excel file with 2023 data."""
        file_path = tmp_path / "ENLA_2023.xlsx"
        sample_2023_data.to_excel(file_path, index=False)
        return str(file_path)

    def test_read_2023_excel_columns_standardized(self, sample_2023_excel):
        """Test that 2023 Excel file columns are standardized after read_excel()."""
        ingestor = ENLAIngestor()
        df = ingestor.read_excel(sample_2023_excel)

        # Check that standardized columns exist
        assert 'medida_lectura' in df.columns
        assert 'medida_matematica' in df.columns
        assert 'medida_ciencias' in df.columns
        assert 'id_ie' in df.columns
        assert 'id_seccion' in df.columns

        # Check that old column names are gone (renamed)
        assert 'M500_EM_2S_2023_CT' not in df.columns
        assert 'M500_EM_2S_2023_MA' not in df.columns
        assert 'M500_EM_2S_2023_CS' not in df.columns

    def test_read_2023_all_unified_schema_columns(self, sample_2023_excel):
        """Test that all UNIFIED_SCHEMA columns are present after read_excel()."""
        ingestor = ENLAIngestor()
        df = ingestor.read_excel(sample_2023_excel)

        for col in UNIFIED_SCHEMA:
            assert col in df.columns, f"Missing UNIFIED_SCHEMA column: {col}"

    def test_read_2023_id_estudiante_none(self, sample_2023_excel):
        """Test that id_estudiante is None for 2023 (not present in original)."""
        ingestor = ENLAIngestor()
        df = ingestor.read_excel(sample_2023_excel)

        # id_estudiante should exist but be None (not present in 2023)
        assert 'id_estudiante' in df.columns
        assert df['id_estudiante'].isna().all()


class TestDetectYear:
    """Tests for year detection in the pipeline."""

    def test_detect_year_2022(self):
        """Test _detect_year() with 2022 columns."""
        ingestor = ENLAIngestor()
        df = pd.DataFrame(columns=['M500_L', 'ID_seccion'])
        year = ingestor._detect_year(df, "ENLA_2022.xlsx")
        assert year == 2022

    def test_detect_year_2023(self):
        """Test _detect_year() with 2023 columns."""
        ingestor = ENLAIngestor()
        df = pd.DataFrame(columns=['M500_EM_2S_2023_CT', 'ID_SECCION'])
        year = ingestor._detect_year(df, "ENLA_2023.xlsx")
        assert year == 2023

    def test_detect_year_unknown(self):
        """Test _detect_year() with unknown format."""
        ingestor = ENLAIngestor()
        df = pd.DataFrame(columns=['unknown_col1', 'unknown_col2'])
        year = ingestor._detect_year(df, "unknown.xlsx")
        assert year is None


class TestRenameColumns:
    """Tests for _rename_columns() method."""

    def test_rename_columns_2022(self):
        """Test _rename_columns() with 2022 data."""
        ingestor = ENLAIngestor()
        df = pd.DataFrame({
            'M500_L': [500.0],
            'ID_IE': ['IE001'],
            'ID_seccion': ['SEC001'],
        })
        result = ingestor._rename_columns(df, 2022)

        assert 'medida_lectura' in result.columns
        assert 'id_ie' in result.columns
        assert 'id_seccion' in result.columns
        assert 'M500_L' not in result.columns

    def test_rename_columns_adds_missing_schema_cols(self):
        """Test that _rename_columns() adds missing UNIFIED_SCHEMA columns."""
        ingestor = ENLAIngestor()
        df = pd.DataFrame({
            'M500_L': [500.0],
        })
        result = ingestor._rename_columns(df, 2022)

        # All UNIFIED_SCHEMA columns should exist
        for col in UNIFIED_SCHEMA:
            assert col in result.columns, f"Missing: {col}"

    def test_rename_columns_idempotent(self):
        """Test that running _rename_columns() twice doesn't break."""
        ingestor = ENLAIngestor()
        df = pd.DataFrame({
            'M500_L': [500.0],
            'ID_IE': ['IE001'],
        })
        result1 = ingestor._rename_columns(df, 2022)
        result2 = ingestor._rename_columns(result1, 2022)

        # Should have same columns
        assert set(result1.columns) == set(result2.columns)
