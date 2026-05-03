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
    """Create a sample raw DataFrame mimicking MongoDB output with corrected schema."""
    return pd.DataFrame({
        '_id': ['obj1', 'obj2', 'obj3'],
        'id_ie': ['IE001', 'IE002', 'IE003'],
        'id_seccion': ['SEC001', 'SEC002', 'SEC003'],
        'nom_ie': ['Colegio A', 'Colegio B', 'Colegio C'],
        'nom_dre': ['CALLAO', 'CALLAO', 'CALLAO'],
        'ano_evaluacion': [2021, 2022, 2023],
        'grado_evaluacion': [2, 2, 2],
        'cor_est': ['EST001', 'EST002', 'EST003'],  # Student identifier (single column)
        'area': ['Urban', 'Urban', 'Rural'],  # Geographic zone (NOT academic area)
        # EMA 2023 columns (3 academic areas, no 'cyt' data)
        'M500_EM_2S_2023_CT': [72.5, 65.0, 80.0],   # Comunicación/Lectura
        'grupo_EM_2S_2023_CT': ['2', '3', '1'],
        'peso_CT': [1.0, 1.0, 1.0],
        'M500_EM_2S_2023_MA': [58.3, 71.2, None],    # Matemática
        'grupo_EM_2S_2023_MA': ['3', '2', None],
        'peso_MA': [1.0, 1.0, None],
        'M500_EM_2S_2023_CS': [None, 69.5, 75.0],    # Ciencias Sociales
        'grupo_EM_2S_2023_CS': [None, '2', '2'],
        'peso_CS': [None, 1.0, 1.0],
    })


@pytest.fixture
def sample_raw_with_all_nulls() -> pd.DataFrame:
    """Create a DataFrame with all NULL EMA 2023 scores."""
    return pd.DataFrame({
        '_id': ['obj1'],
        'id_ie': ['IE001'],
        'id_seccion': ['SEC001'],
        'nom_ie': ['Colegio A'],
        'nom_dre': ['CALLAO'],
        'ano_evaluacion': [2021],
        'grado_evaluacion': [2],
        'cor_est': ['EST001'],
        'area': ['Urban'],
        # All EMA 2023 score columns are NULL
        'M500_EM_2S_2023_CT': [None],
        'grupo_EM_2S_2023_CT': [None],
        'peso_CT': [None],
        'M500_EM_2S_2023_MA': [None],
        'grupo_EM_2S_2023_MA': [None],
        'peso_MA': [None],
        'M500_EM_2S_2023_CS': [None],
        'grupo_EM_2S_2023_CS': [None],
        'peso_CS': [None],
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
    """Tests for wide-to-long format transformation (corrected schema)."""
    
    def test_pivot_creates_correct_row_count(self, mock_etl_transform: ETLTransform,
                                             sample_raw_df: pd.DataFrame):
        """Verify that output has input_rows × num_areas rows (3 academic areas)."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        expected_rows = len(sample_raw_df) * len(AREA_COLUMN_MAP)
        
        assert len(result) == expected_rows, \
            f"Expected {expected_rows} rows (3 areas × {len(sample_raw_df)} students), got {len(result)}"
    
    def test_pivot_contains_all_areas(self, mock_etl_transform: ETLTransform,
                                      sample_raw_df: pd.DataFrame):
        """Verify that all 3 academic areas are present (no 'cyt' data)."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        expected_areas = set(AREA_COLUMN_MAP.values())  # comunicacion, matematica, ccss
        actual_areas = set(result['area_academica'].unique())
        
        assert actual_areas == expected_areas, \
            f"Missing areas: {expected_areas - actual_areas}"
        # Verify 'cyt' is NOT present
        assert 'cyt' not in actual_areas, "cyt should not be present (no data)"
    
    def test_pivot_preserves_institution_and_student_ids(self, mock_etl_transform: ETLTransform,
                                                          sample_raw_df: pd.DataFrame):
        """Verify that institution IDs and student IDs (cor_est) are correctly replicated."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        
        # Each student should appear once per academic area
        ie_counts = result.groupby(['id_ie', 'cor_est']).size()
        expected_count_per_student = len(AREA_COLUMN_MAP)
        
        assert all(count == expected_count_per_student for count in ie_counts), \
            "Not all students appear in all academic areas"
    
    def test_pivot_maps_correct_scores(self, mock_etl_transform: ETLTransform,
                                       sample_raw_df: pd.DataFrame):
        """Verify that EMA 2023 scores are mapped to the correct academic area."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        
        # Check first student's comunicacion score (from M500_EM_2S_2023_CT)
        est001_com = result[
            (result['cor_est'] == 'EST001') & (result['area_academica'] == 'comunicacion')
        ]
        assert len(est001_com) == 1
        assert est001_com.iloc[0]['score'] == 72.5
        
        # Check first student's math score (from M500_EM_2S_2023_MA)
        est001_mat = result[
            (result['cor_est'] == 'EST001') & (result['area_academica'] == 'matematica')
        ]
        assert len(est001_mat) == 1
        assert est001_mat.iloc[0]['score'] == 58.3
    
    def test_pivot_preserves_geographic_area(self, mock_etl_transform: ETLTransform,
                                             sample_raw_df: pd.DataFrame):
        """Verify that 'area' column (geographic zone) is preserved correctly."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        
        # Check that geographic zone is replicated for each academic area
        est001_rows = result[result['cor_est'] == 'EST001']
        # All rows for EST001 should have 'Urban' as geographic zone
        assert all(est001_rows['area'] == 'Urban'), \
            "Geographic zone (area) not preserved correctly"
    
    def test_pivot_output_columns(self, mock_etl_transform: ETLTransform,
                                  sample_raw_df: pd.DataFrame):
        """Verify output DataFrame has expected columns (corrected schema)."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        expected_cols = {
            'id_ie', 'id_seccion', 'nom_ie', 'nom_dre',
            'year', 'area',  # Geographic zone (Rural/Urban)
            'cor_est',  # Student identifier
            'area_academica',  # Academic area (comunicacion/matematica/ccss)
            'score', 'grupo', 'peso',
            'is_null_score', 'created_at'
        }
        
        assert set(result.columns) == expected_cols, \
            f"Missing columns: {expected_cols - set(result.columns)}"


# ==========================================
# Test: Fact Record Creation
# ==========================================

class TestCreateFactRecords:
    """Tests for fact_enla table creation (corrected schema)."""
    
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
        """Verify fact DataFrame matches expected schema (area_academica + cor_est)."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        expected_cols = {'fact_id', 'id_ie', 'id_seccion', 'nom_ie',
                        'year', 'area_academica', 'cor_est', 'score', 'created_at'}
        
        assert set(fact_df.columns) == expected_cols
    
    def test_fact_year_is_integer(self, mock_etl_transform: ETLTransform,
                                  sample_raw_df: pd.DataFrame):
        """Verify year column is integer type."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        # All values should be integers
        assert fact_df['year'].dtype in [np.int64, np.int32, int]
    
    def test_fact_contains_student_id(self, mock_etl_transform: ETLTransform,
                                       sample_raw_df: pd.DataFrame):
        """Verify cor_est (student ID) is correctly populated."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        # All rows should have non-null cor_est
        assert fact_df['cor_est'].notna().all(), "Student ID (cor_est) should not be NULL"
        # Check specific values
        est001_rows = fact_df[fact_df['cor_est'] == 'EST001']
        assert len(est001_rows) == len(AREA_COLUMN_MAP), \
            "Each student should have one row per academic area"


# ==========================================
# Test: NULL Score Handling
# ==========================================

class TestNullHandling:
    """Tests for NULL score handling (corrected schema)."""
    
    def test_null_scores_marked_correctly(self, mock_etl_transform: ETLTransform,
                                           sample_raw_df: pd.DataFrame):
        """Verify that NULL scores are flagged with is_null_score=True."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        
        # EST003 has NULL matematica score (M500_EM_2S_2023_MA is None)
        est003_mat = result[
            (result['cor_est'] == 'EST003') & (result['area_academica'] == 'matematica')
        ]
        assert len(est003_mat) == 1
        assert est003_mat.iloc[0]['is_null_score'] == True
        assert pd.isna(est003_mat.iloc[0]['score'])
        
        # EST001 has valid matematica score
        est001_mat = result[
            (result['cor_est'] == 'EST001') & (result['area_academica'] == 'matematica')
        ]
        assert len(est001_mat) == 1
        assert est001_mat.iloc[0]['is_null_score'] == False
        assert not pd.isna(est001_mat.iloc[0]['score'])
    
    def test_all_null_scores(self, mock_etl_transform: ETLTransform,
                              sample_raw_with_all_nulls: pd.DataFrame):
        """Verify that all-NULL EMA 2023 scores are handled gracefully."""
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
        
        # EST001 has NULL ccss score (M500_EM_2S_2023_CS is None)
        est001_ccss = result[
            (result['cor_est'] == 'EST001') & (result['area_academica'] == 'ccss')
        ]
        assert len(est001_ccss) == 1
        assert est001_ccss.iloc[0]['is_null_score'] == True
    
    def test_null_score_count_accuracy(self, mock_etl_transform: ETLTransform,
                                        sample_raw_df: pd.DataFrame):
        """Verify NULL score count is accurate."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df)
        actual_nulls = result['is_null_score'].sum()
        
        # sample_raw_df has: EST003-MA=None (1), EST002-CS=None (1), EST001-CS=None (1)
        # Wait, looking at the fixture: 
        # EST001: CT=72.5, MA=58.3, CS=None (1 null)
        # EST002: CT=65.0, MA=71.2, CS=69.5 (0 nulls)
        # EST003: CT=80.0, MA=None, CS=75.0 (1 null)
        # Total: 2 nulls
        expected_nulls = 2
        
        assert actual_nulls == expected_nulls, \
            f"Expected {expected_nulls} NULLs, got {actual_nulls}"


# ==========================================
# Test: Data Quality Checks
# ==========================================

class TestDataQualityCheck:
    """Tests for data quality gate validation (corrected schema)."""
    
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
            'area': ['Urban'],  # Geographic zone
            'cor_est': ['EST001'],  # Student ID
            'area_academica': ['comunicacion'],
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
        
        # Make 10% of cor_est NULL (student ID is critical)
        cleaned_df = pd.DataFrame({
            'id_ie': ['IE001'] * 20,
            'id_seccion': ['SEC001'] * 20,
            'year': [2021] * 20,
            'area': ['Urban'] * 20,
            'cor_est': [None] * 2 + ['EST001'] * 18,  # 10% NULL
            'area_academica': ['comunicacion'] * 20,
            'score': [60.0] * 20,
            'is_null_score': [False] * 20,
            'created_at': [datetime.now(timezone.utc)] * 20,
        })
        
        summary = mock_etl_transform._validate_data_quality(raw_df, cleaned_df)
        
        # 10% NULL coverage should generate a warning
        assert summary.critical_null_coverage.get('cor_est', 0) == 10.0
    
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
        """Verify that academic areas processed count is accurate."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        summary = mock_etl_transform._validate_data_quality(sample_raw_df, cleaned)
        
        # Should be 3 (comunicacion, matematica, ccss - no 'cyt')
        assert summary.areas_processed == len(AREA_COLUMN_MAP)


# ==========================================
# Test: ETLResult
# ==========================================

class TestETLResult:
    """Tests for ETLResult dataclass."""
    
    def test_etl_result_has_status_property_success(self):
        """Verify ETLResult.status returns 'success' when success=True."""
        from src.etl.transform import DataQualitySummary
        
        result = ETLResult(
            success=True,
            data_quality=DataQualitySummary(),
        )
        
        assert result.status == 'success'
    
    def test_etl_result_has_status_property_failure(self):
        """Verify ETLResult.status returns 'failed' when success=False."""
        from src.etl.transform import DataQualitySummary
        
        result = ETLResult(
            success=False,
            data_quality=DataQualitySummary(),
            error_message="Test error"
        )
        
        assert result.status == 'failed'
    
    def test_etl_result_status_property_not_mutable(self):
        """Verify status is a property (derived from success), not a settable attribute."""
        from src.etl.transform import DataQualitySummary
        
        result = ETLResult(
            success=True,
            data_quality=DataQualitySummary(),
        )
        
        # Status should be derived from success
        assert result.status == 'success'
        
        # Changing success should change status
        result.success = False
        assert result.status == 'failed'


# ==========================================
# Test: Dimension Tables
# ==========================================

class TestDimensionTables:
    """Tests for dimension table creation (corrected schema)."""
    
    def test_dim_meta_has_unique_combinations(self, mock_etl_transform: ETLTransform,
                                                sample_raw_df: pd.DataFrame):
        """Verify dim_meta has unique institution-academic_area-year combos."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        dim_meta = mock_etl_transform._create_dim_meta(cleaned)
        
        # Check no duplicates (area in dim_meta = academic area)
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
    
    def test_dim_meta_uses_academic_area(self, mock_etl_transform: ETLTransform,
                                           sample_raw_df: pd.DataFrame):
        """Verify dim_meta uses academic area (not geographic zone)."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df)
        dim_meta = mock_etl_transform._create_dim_meta(cleaned)
        
        # dim_meta['area'] should have academic areas (comunicacion, matematica, ccss)
        # NOT geographic zones (Urban/Rural)
        expected_areas = set(AREA_COLUMN_MAP.values())
        actual_areas = set(dim_meta['area'].unique())
        assert actual_areas == expected_areas, \
            f"dim_meta should use academic areas, got: {actual_areas}"
    
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
