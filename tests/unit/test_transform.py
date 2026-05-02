"""Unit tests for ETL transform module (Sprint 2).

Tests cover:
- Wide-to-long format transformation
- Fact record creation
- NULL score handling
- Data quality validation
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.etl.transform import (
    ETLTransform,
    ETLTransformError,
    DataQualitySummary,
    ETLResult,
    AREA_COLUMN_MAP,
    run_etl_pipeline,
)
from src.etl.schemas import FACT_ENLA_SCHEMA, ENLA_CALLAO_CLEANED_SCHEMA


# ==========================================
# Test Fixtures
# ==========================================

@pytest.fixture
def sample_raw_df() -> pd.DataFrame:
    """Create a sample raw DataFrame mimicking MongoDB output."""
    return pd.DataFrame({
        '_id': ['obj1', 'obj2', 'obj3'],
        'id_ie': ['IE001', 'IE002', 'IE003'],
        'id_seccion': ['SEC001', 'SEC002', 'SEC003'],
        'nom_ie': ['Colegio A', 'Colegio B', 'Colegio C'],
        'nom_dre': ['CALLAO', 'CALLAO', 'CALLAO'],
        'ano_evaluacion': [2021, 2022, 2023],
        'grado_evaluacion': [2, 2, 2],
        'cor_est_comunicacion': [72.5, 65.0, 80.0],
        'cor_est_matematica': [58.3, 71.2, None],
        'cor_est_ccss': [None, 69.5, 75.0],
        'cor_est_cyt': [63.0, 55.0, 82.5],
    })


@pytest.fixture
def sample_raw_with_all_nulls() -> pd.DataFrame:
    """Create a DataFrame with all NULL scores."""
    return pd.DataFrame({
        '_id': ['obj1'],
        'id_ie': ['IE001'],
        'id_seccion': ['SEC001'],
        'nom_ie': ['Colegio A'],
        'nom_dre': ['CALLAO'],
        'ano_evaluacion': [2021],
        'grado_evaluacion': [2],
        'cor_est_comunicacion': [None],
        'cor_est_matematica': [None],
        'cor_est_ccss': [None],
        'cor_est_cyt': [None],
    })


@pytest.fixture
def mock_etl_transform() -> ETLTransform:
    """Create ETLTransform with mocked dependencies."""
    with patch('src.etl.transform.get_mongo_manager') as mock_mongo, \
         patch('src.etl.transform.BigQueryClientManager') as mock_bq:
        
        mock_mongo_instance = MagicMock()
        mock_mongo.return_value = mock_mongo_instance
        
        mock_bq_instance = MagicMock()
        mock_bq.return_value = mock_bq_instance
        
        transform = ETLTransform.__new__(ETLTransform)
        transform.mongo_manager = mock_mongo_instance
        transform.bq_manager = mock_bq_instance
        transform.dataset_id = 'BI_ENLA'
        
        return transform


# ==========================================
# Test: Wide-to-Long Transformation
# ==========================================

class TestPivotByArea:
    """Tests for wide-to-long format transformation."""
    
    def test_pivot_creates_correct_row_count(self, mock_etl_transform: ETLTransform,
                                             sample_raw_df: pd.DataFrame):
        """Verify that output has input_rows × num_areas rows."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        expected_rows = len(sample_raw_df) * len(AREA_COLUMN_MAP)
        
        assert len(result) == expected_rows, \
            f"Expected {expected_rows} rows, got {len(result)}"
    
    def test_pivot_contains_all_areas(self, mock_etl_transform: ETLTransform,
                                      sample_raw_df: pd.DataFrame):
        """Verify that all 4 areas are present in output."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        expected_areas = set(AREA_COLUMN_MAP.values())
        actual_areas = set(result['area'].unique())
        
        assert actual_areas == expected_areas, \
            f"Missing areas: {expected_areas - actual_areas}"
    
    def test_pivot_preserves_institution_ids(self, mock_etl_transform: ETLTransform,
                                             sample_raw_df: pd.DataFrame):
        """Verify that institution IDs are correctly replicated across areas."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        
        # Each institution should appear once per area
        ie_counts = result.groupby('id_ie').size()
        expected_count_per_ie = len(AREA_COLUMN_MAP)
        
        assert all(count == expected_count_per_ie for count in ie_counts), \
            "Not all institutions appear in all areas"
    
    def test_pivot_maps_correct_scores(self, mock_etl_transform: ETLTransform,
                                       sample_raw_df: pd.DataFrame):
        """Verify that scores are mapped to the correct area."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        
        # Check first institution's communication score
        ie001_com = result[
            (result['id_ie'] == 'IE001') & (result['area'] == 'comunicacion')
        ]
        assert len(ie001_com) == 1
        assert ie001_com.iloc[0]['score'] == 72.5
        
        # Check first institution's math score
        ie001_mat = result[
            (result['id_ie'] == 'IE001') & (result['area'] == 'matematica')
        ]
        assert len(ie001_mat) == 1
        assert ie001_mat.iloc[0]['score'] == 58.3
    
    def test_pivot_output_columns(self, mock_etl_transform: ETLTransform,
                                  sample_raw_df: pd.DataFrame):
        """Verify output DataFrame has expected columns."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        expected_cols = {
            'id_ie', 'id_seccion', 'nom_ie', 'nom_dre',
            'year', 'area', 'score', 'is_null_score', 'created_at'
        }
        
        assert set(result.columns) == expected_cols, \
            f"Missing columns: {expected_cols - set(result.columns)}"


# ==========================================
# Test: Fact Record Creation
# ==========================================

class TestCreateFactRecords:
    """Tests for fact_enla table creation."""
    
    def test_fact_records_have_uuid(self, mock_etl_transform: ETLTransform,
                                    sample_raw_df: pd.DataFrame):
        """Verify that each fact record has a valid UUID."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        import uuid
        for fact_id in fact_df['fact_id']:
            # Should not raise ValueError
            uuid.UUID(fact_id)
    
    def test_fact_records_count(self, mock_etl_transform: ETLTransform,
                                sample_raw_df: pd.DataFrame):
        """Verify fact record count matches cleaned data."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        assert len(fact_df) == len(cleaned)
    
    def test_fact_records_schema(self, mock_etl_transform: ETLTransform,
                                 sample_raw_df: pd.DataFrame):
        """Verify fact DataFrame matches expected schema."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        expected_cols = {'fact_id', 'id_ie', 'id_seccion', 'nom_ie',
                        'year', 'area', 'score', 'created_at'}
        
        assert set(fact_df.columns) == expected_cols
    
    def test_fact_year_is_integer(self, mock_etl_transform: ETLTransform,
                                  sample_raw_df: pd.DataFrame):
        """Verify year column is integer type."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        # All values should be integers
        assert fact_df['year'].dtype in [np.int64, np.int32, int]


# ==========================================
# Test: NULL Score Handling
# ==========================================

class TestNullHandling:
    """Tests for NULL score handling."""
    
    def test_null_scores_marked_correctly(self, mock_etl_transform: ETLTransform,
                                          sample_raw_df: pd.DataFrame):
        """Verify that NULL scores are flagged with is_null_score=True."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        
        # IE003 has NULL matematica score
        ie003_mat = result[
            (result['id_ie'] == 'IE003') & (result['area'] == 'matematica')
        ]
        assert ie003_mat.iloc[0]['is_null_score'] == True
        assert pd.isna(ie003_mat.iloc[0]['score'])
        
        # IE001 has valid matematica score
        ie001_mat = result[
            (result['id_ie'] == 'IE001') & (result['area'] == 'matematica')
        ]
        assert ie001_mat.iloc[0]['is_null_score'] == False
        assert not pd.isna(ie001_mat.iloc[0]['score'])
    
    def test_all_null_scores(self, mock_etl_transform: ETLTransform,
                             sample_raw_with_all_nulls: pd.DataFrame):
        """Verify that all-NULL scores are handled gracefully."""
        result = mock_etl_transform._transform_to_long_format(
            sample_raw_with_all_nulls
        )
        
        # All rows should have is_null_score=True
        assert all(result['is_null_score'] == True)
        assert all(result['score'].isna())
    
    def test_null_scores_included_in_output(self, mock_etl_transform: ETLTransform,
                                            sample_raw_df: pd.DataFrame):
        """Verify that rows with NULL scores are NOT filtered out."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        
        # IE002 has NULL ccss, should still be in output
        ie002_ccss = result[
            (result['id_ie'] == 'IE002') & (result['area'] == 'ccss')
        ]
        assert len(ie002_ccss) == 1
        assert ie002_ccss.iloc[0]['is_null_score'] == True
    
    def test_null_score_count_accuracy(self, mock_etl_transform: ETLTransform,
                                       sample_raw_df: pd.DataFrame):
        """Verify NULL score count is accurate."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        actual_nulls = result['is_null_score'].sum()
        
        # sample_raw_df has: IE003-matematica=None, IE001-ccss=None
        expected_nulls = 2
        
        assert actual_nulls == expected_nulls, \
            f"Expected {expected_nulls} NULLs, got {actual_nulls}"


# ==========================================
# Test: Data Quality Checks
# ==========================================

class TestDataQualityCheck:
    """Tests for data quality gate validation."""
    
    def test_quality_check_passes_valid_data(self, mock_etl_transform: ETLTransform,
                                             sample_raw_df: pd.DataFrame):
        """Verify that valid data passes quality checks."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        summary = mock_etl_transform._validate_data_quality(sample_raw_df, cleaned)
        
        assert summary.is_valid == True
        assert summary.total_input_rows == len(sample_raw_df)
        assert summary.total_output_rows == len(cleaned)
    
    def test_quality_check_detects_null_coverage(self, mock_etl_transform: ETLTransform,
                                                  sample_raw_df: pd.DataFrame):
        """Verify that NULL coverage is calculated correctly."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        summary = mock_etl_transform._validate_data_quality(sample_raw_df, cleaned)
        
        assert summary.null_scores_count > 0
        assert 0.0 < summary.null_scores_percent < 100.0
    
    def test_quality_check_detects_out_of_range_scores(self, mock_etl_transform: ETLTransform):
        """Verify that out-of-range scores are detected."""
        raw_df = pd.DataFrame({
            'id_ie': ['IE001'],
            'ano_evaluacion': [2021],
        })
        
        cleaned_df = pd.DataFrame({
            'id_ie': ['IE001'],
            'id_seccion': ['SEC001'],
            'year': [2021],
            'area': ['comunicacion'],
            'score': [150.0],  # Out of range!
            'is_null_score': [False],
            'created_at': [datetime.now(timezone.utc)],
        })
        
        summary = mock_etl_transform._validate_data_quality(raw_df, cleaned_df)
        
        assert summary.score_range_valid == False
        assert len(summary.errors) > 0
    
    def test_quality_check_warns_on_high_null_coverage(self, mock_etl_transform: ETLTransform):
        """Verify warning is generated when critical column NULL > 5%."""
        raw_df = pd.DataFrame({
            'id_ie': ['IE001'] * 20,
            'ano_evaluacion': [2021] * 20,
        })
        
        # Make 10% of id_ie NULL
        cleaned_df = pd.DataFrame({
            'id_ie': [None] * 2 + ['IE001'] * 18,
            'id_seccion': ['SEC001'] * 20,
            'year': [2021] * 20,
            'area': ['comunicacion'] * 20,
            'score': [60.0] * 20,
            'is_null_score': [False] * 20,
            'created_at': [datetime.now(timezone.utc)] * 20,
        })
        
        summary = mock_etl_transform._validate_data_quality(raw_df, cleaned_df)
        
        # 10% NULL coverage should generate a warning
        assert summary.critical_null_coverage.get('id_ie', 0) == 10.0
    
    def test_quality_summary_initial_values(self):
        """Verify DataQualitySummary defaults."""
        summary = DataQualitySummary()
        
        assert summary.total_input_rows == 0
        assert summary.total_output_rows == 0
        assert summary.null_scores_count == 0
        assert summary.null_scores_percent == 0.0
        assert summary.score_range_valid == True
        assert summary.is_valid == True  # No errors initially
    
    def test_quality_check_tracks_areas_processed(self, mock_etl_transform: ETLTransform,
                                                   sample_raw_df: pd.DataFrame):
        """Verify that areas processed count is accurate."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        summary = mock_etl_transform._validate_data_quality(sample_raw_df, cleaned)
        
        assert summary.areas_processed == len(AREA_COLUMN_MAP)


# ==========================================
# Test: Dimension Tables
# ==========================================

class TestDimensionTables:
    """Tests for dimension table creation."""
    
    def test_dim_meta_has_unique_combinations(self, mock_etl_transform: ETLTransform,
                                              sample_raw_df: pd.DataFrame):
        """Verify dim_meta has unique institution-area-year combos."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        dim_meta = mock_etl_transform._create_dim_meta(cleaned)
        
        # Check no duplicates
        combo_col = ['id_ie', 'year', 'area']
        duplicates = dim_meta.duplicated(subset=combo_col)
        assert duplicates.sum() == 0, "Found duplicate combinations in dim_meta"
    
    def test_dim_meta_has_target_score(self, mock_etl_transform: ETLTransform,
                                       sample_raw_df: pd.DataFrame):
        """Verify dim_meta has correct target score."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        dim_meta = mock_etl_transform._create_dim_meta(cleaned)
        
        from src.ingestion.config import settings
        assert all(dim_meta['target_score'] == settings.TARGET_SCORE_THRESHOLD)
    
    def test_dim_meta_has_region(self, mock_etl_transform: ETLTransform,
                                 sample_raw_df: pd.DataFrame):
        """Verify dim_meta has region set to CALLAO."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        dim_meta = mock_etl_transform._create_dim_meta(cleaned)
        
        assert all(dim_meta['region'] == 'CALLAO')
    
    def test_dim_calendario_has_correct_years(self, mock_etl_transform: ETLTransform,
                                              sample_raw_df: pd.DataFrame):
        """Verify dim_calendario covers all years in data."""
        dim_cal = mock_etl_transform._create_dim_calendario(sample_raw_df)
        
        years_in_data = set(sample_raw_df['ano_evaluacion'].dropna().astype(int))
        years_in_cal = set(dim_cal['year'])
        
        assert years_in_data.issubset(years_in_cal), \
            f"Missing years in calendario: {years_in_data - years_in_cal}"
    
    def test_dim_calendario_has_quarter(self, mock_etl_transform: ETLTransform,
                                        sample_raw_df: pd.DataFrame):
        """Verify dim_calendario has correct quarter values."""
        dim_cal = mock_etl_transform._create_dim_calendario(sample_raw_df)
        
        assert all(1 <= q <= 4 for q in dim_cal['quarter'])
