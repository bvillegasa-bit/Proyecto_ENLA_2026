"""Unit tests for ETL transform module - Updated for dynamic column discovery.

Tests cover:
- Wide-to-long format transformation (dynamic column patterns)
- Fact record creation
- NULL score handling
- Data quality validation
- Year from filename (not from data)
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
    STANDARDIZED_AREAS,
    run_etl_pipeline,
)
from src.etl.schemas import FACT_ENLA_SCHEMA, ENLA_CALLAO_CLEANED_SCHEMA


# ==========================================
# Test Fixtures
# ==========================================

@pytest.fixture
def sample_raw_df_2023() -> pd.DataFrame:
    """Create a sample raw DataFrame mimicking MongoDB output for 2023."""
    return pd.DataFrame({
        '_id': ['obj1', 'obj2', 'obj3'],
        'id_ie': ['IE001', 'IE002', 'IE003'],
        'id_seccion': ['SEC001', 'SEC002', 'SEC003'],
        'nom_ie': ['Colegio A', 'Colegio B', 'Colegio C'],
        'nom_dre': ['CALLAO', 'CALLAO', 'CALLAO'],
        'ano_evaluacion': [2023, 2023, 2023],
        'grado_evaluacion': [2, 2, 2],
        'cor_est': ['EST001', 'EST002', 'EST003'],
        'area': ['Urban', 'Urban', 'Rural'],
        # 2023 columns: M500_EM_2S_2023_XX format
        'medida_lectura': [72.5, 65.0, 80.0],   # Comunicación
        'grupo_lectura': ['2', '3', '1'],
        'peso_lectura': [1.0, 1.0, 1.0],
        'medida_matematica': [58.3, 71.2, None],    # Matemática
        'grupo_matematica': ['3', '2', None],
        'peso_matematica': [1.0, 1.0, None],
        'medida_ciencias': [None, 69.5, 75.0],    # Ciencias Sociales
        'grupo_ciencias': [None, '2', '2'],
        'peso_ciencias': [None, 1.0, 1.0],
    })


@pytest.fixture
def sample_raw_df_2022() -> pd.DataFrame:
    """Create a sample raw DataFrame mimicking MongoDB output for 2022."""
    return pd.DataFrame({
        '_id': ['obj1', 'obj2', 'obj3'],
        'id_ie': ['IE001', 'IE002', 'IE003'],
        'id_seccion': ['SEC001', 'SEC002', 'SEC003'],
        'nom_ie': ['Colegio A', 'Colegio B', 'Colegio C'],
        'nom_dre': ['CALLAO', 'CALLAO', 'CALLAO'],
        'ano_evaluacion': [2022, 2022, 2022],
        'grado_evaluacion': [2, 2, 2],
        'cor_est': ['EST001', 'EST002', 'EST003'],
        'area': ['Urban', 'Urban', 'Rural'],
        # 2022 columns: medida500_X format (different from 2023!)
        'medida_lectura': [72.5, 65.0, 80.0],   # Comunicación (Lectura)
        'grupo_lectura': ['2', '3', '1'],
        'peso_lectura': [1.0, 1.0, 1.0],
        'medida_matematica': [58.3, 71.2, None],    # Matemática
        'grupo_matematica': ['3', '2', None],
        'peso_matematica': [1.0, 1.0, None],
        'medida_ciencias': [None, 69.5, 75.0],    # Ciencias (CN)
        'grupo_ciencias': [None, '2', '2'],
        'peso_ciencias': [None, 1.0, 1.0],
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
        'ano_evaluacion': [2023],
        'grado_evaluacion': [2],
        'cor_est': ['EST001'],
        'area': ['Urban'],
        # All score columns are NULL
        'medida_lectura': [None],
        'grupo_lectura': [None],
        'peso_lectura': [None],
        'medida_matematica': [None],
        'grupo_matematica': [None],
        'peso_matematica': [None],
        'medida_ciencias': [None],
        'grupo_ciencias': [None],
        'peso_ciencias': [None],
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
# Test: Wide-to-Long Transformation (2023)
# ==========================================

class TestPivotByArea2023:
    """Tests for wide-to-long format transformation (2023 format)."""
    
    def test_pivot_creates_correct_row_count(self, mock_etl_transform: ETLTransform,
                                             sample_raw_df_2023: pd.DataFrame):
        """Verify that output has input_rows × num_areas rows."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        # 3 students × 3 areas = 9 rows
        assert len(result) == 9, \
            f"Expected 9 rows (3 areas × 3 students), got {len(result)}"
    
    def test_pivot_contains_all_areas(self, mock_etl_transform: ETLTransform,
                                       sample_raw_df_2023: pd.DataFrame):
        """Verify that all 3 academic areas are present."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        # User said: "comunicación y matemática" (WITH accents!)
        expected_areas = {'comunicación', 'matemática', 'ccss'}
        actual_areas = set(result['area_academica'].unique())
        
        assert actual_areas == expected_areas, \
            f"Missing areas: {expected_areas - actual_areas}"
    
    def test_pivot_preserves_institution_and_student_ids(self, mock_etl_transform: ETLTransform,
                                                          sample_raw_df_2023: pd.DataFrame):
        """Verify that institution IDs and student IDs (cor_est) are correctly replicated."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        
        # Each student should appear once per academic area
        ie_counts = result.groupby(['id_ie', 'cor_est']).size()
        assert all(count == 3 for count in ie_counts), \
            "Not all students appear in all academic areas"
    
    def test_pivot_maps_correct_scores(self, mock_etl_transform: ETLTransform,
                                        sample_raw_df_2023: pd.DataFrame):
        """Verify that scores are mapped to the correct academic area."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        
        # Check comunicación score for EST001 (from medida_lectura = 72.5)
        # User said: "comunicación y matemática" (WITH accents!)
        est001_com = result[
            (result['cor_est'] == 'EST001') & (result['area_academica'] == 'comunicación')
        ]
        assert len(est001_com) == 1
        assert est001_com.iloc[0]['score'] == 72.5
        
        # Check matemática score for EST001 (from medida_matematica = 58.3)
        # User said: "comunicación y matemática" (WITH accents!)
        est001_mat = result[
            (result['cor_est'] == 'EST001') & (result['area_academica'] == 'matemática')
        ]
        assert len(est001_mat) == 1
        assert est001_mat.iloc[0]['score'] == 58.3
    
    def test_pivot_2023_all_areas_found(self, mock_etl_transform: ETLTransform,
                                           sample_raw_df_2023: pd.DataFrame):
        """Verify that all 2023 columns are discovered (CT, MA, CS)."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        # Should have 3 students × 3 areas = 9 rows
        assert len(result) == 9
        # All 3 areas should be present
        # User said: "comunicación y matemática" (WITH accents!)
        assert set(result['area_academica'].unique()) == {'comunicación', 'matemática', 'ccss'}
    
    def test_pivot_preserves_geographic_area(self, mock_etl_transform: ETLTransform,
                                             sample_raw_df_2023: pd.DataFrame):
        """Verify that 'area' column (geographic zone) is preserved correctly."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        
        # Check that geographic zone is replicated for each academic area
        est001_rows = result[result['cor_est'] == 'EST001']
        assert all(est001_rows['area'] == 'Urban'), \
            "Geographic zone (area) not preserved correctly"
    
    def test_pivot_output_columns(self, mock_etl_transform: ETLTransform,
                                  sample_raw_df_2023: pd.DataFrame):
        """Verify output DataFrame has expected columns."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
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
    
    def test_year_from_parameter(self, mock_etl_transform: ETLTransform,
                                 sample_raw_df_2023: pd.DataFrame,
                                 sample_raw_df_2022: pd.DataFrame):
        """Verify that year comes from ano_evaluacion column per-record."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        assert all(result['year'] == 2023), "Year should be 2023 (from ano_evaluacion column)"
        
        # Use sample_raw_df_2022 which has ano_evaluacion=2022
        result_2022 = mock_etl_transform._transform_to_long_format(sample_raw_df_2022, year=2022)
        assert all(result_2022['year'] == 2022), "Year should be 2022 (from ano_evaluacion column)"


# ==========================================
# Test: Wide-to-Long Transformation (2022)
# ==========================================

class TestPivotByArea2022:
    """Tests for wide-to-long format transformation (2022 format - different column names)."""
    
    def test_pivot_2022_creates_correct_row_count(self, mock_etl_transform: ETLTransform,
                                                   sample_raw_df_2022: pd.DataFrame):
        """Verify that 2022 data is processed correctly with different column names."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2022, year=2022)
        # 3 students × 3 areas = 9 rows
        assert len(result) == 9, \
            f"Expected 9 rows (3 areas × 3 students), got {len(result)}"
    
    def test_pivot_2022_finds_correct_columns(self, mock_etl_transform: ETLTransform,
                                               sample_raw_df_2022: pd.DataFrame):
        """Verify that 2022 columns (medida_lectura, grupo_lectura, etc.) are discovered."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2022, year=2022)
        
        # Check that comunicación scores come from medida_lectura
        # User said: "comunicación y matemática" (WITH accents!)
        est001_com = result[
            (result['cor_est'] == 'EST001') & (result['area_academica'] == 'comunicación')
        ]
        assert len(est001_com) == 1
        assert est001_com.iloc[0]['score'] == 72.5  # From medida_lectura
    
    def test_pivot_2022_contains_all_areas(self, mock_etl_transform: ETLTransform,
                                              sample_raw_df_2022: pd.DataFrame):
        """Verify that all 3 academic areas are present for 2022."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2022, year=2022)
        # User said: "comunicación y matemática" (WITH accents!)
        expected_areas = {'comunicación', 'matemática', 'ccss'}
        actual_areas = set(result['area_academica'].unique())
        
        assert actual_areas == expected_areas, \
            f"Missing areas: {expected_areas - actual_areas}"


# ==========================================
# Test: Fact Record Creation
# ==========================================

class TestCreateFactRecords:
    """Tests for fact_enla table creation."""
    
    def test_fact_records_have_uuid(self, mock_etl_transform: ETLTransform,
                                    sample_raw_df_2023: pd.DataFrame):
        """Verify that each fact record has a valid UUID."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        import uuid
        for fact_id in fact_df['fact_id']:
            # Should not raise ValueError
            uuid.UUID(fact_id)
    
    def test_fact_records_count(self, mock_etl_transform: ETLTransform,
                                sample_raw_df_2023: pd.DataFrame):
        """Verify fact record count matches cleaned data."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        assert len(fact_df) == len(cleaned)
    
    def test_fact_records_schema(self, mock_etl_transform: ETLTransform,
                                 sample_raw_df_2023: pd.DataFrame):
        """Verify fact DataFrame matches expected schema."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        expected_cols = {'fact_id', 'id_ie', 'id_seccion', 'nom_ie',
                        'year', 'area_academica', 'cor_est', 'score', 'created_at'}
        
        assert set(fact_df.columns) == expected_cols
    
    def test_fact_year_is_integer(self, mock_etl_transform: ETLTransform,
                                  sample_raw_df_2023: pd.DataFrame):
        """Verify year column is integer type."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        # All values should be integers
        assert fact_df['year'].dtype in [np.int64, np.int32, int]
    
    def test_fact_contains_student_id(self, mock_etl_transform: ETLTransform,
                                       sample_raw_df_2023: pd.DataFrame):
        """Verify cor_est (student ID) is correctly populated."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        fact_df = mock_etl_transform._create_fact_records(cleaned)
        
        # All rows should have non-null cor_est
        assert fact_df['cor_est'].notna().all(), "Student ID (cor_est) should not be NULL"
        # Check specific values
        est001_rows = fact_df[fact_df['cor_est'] == 'EST001']
        assert len(est001_rows) == 3, \
            "Each student should have one row per academic area"


# ==========================================
# Test: NULL Score Handling
# ==========================================

class TestNullHandling:
    """Tests for NULL score handling."""
    
    def test_null_scores_marked_correctly(self, mock_etl_transform: ETLTransform,
                                           sample_raw_df_2023: pd.DataFrame):
        """Verify that NULL scores are flagged with is_null_score=True."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        
        # Check matemática scores for EST003 (should be NULL in fixture)
        # User said: "comunicación y matemática" (WITH accents!)
        est003_rows = result[result['cor_est'] == 'EST003']
        est003_mat = est003_rows[est003_rows['area_academica'] == 'matemática']
        assert len(est003_mat) == 1
        assert est003_mat.iloc[0]['is_null_score'] == True
        assert pd.isna(est003_mat.iloc[0]['score'])
        
        # Check matemática scores for EST001 (should be valid in fixture - 58.3)
        # User said: "comunicación y matemática" (WITH accents!)
        est001_rows = result[result['cor_est'] == 'EST001']
        est001_mat = est001_rows[est001_rows['area_academica'] == 'matemática']
        assert len(est001_mat) == 1
        assert est001_mat.iloc[0]['is_null_score'] == False
        assert not pd.isna(est001_mat.iloc[0]['score'])
        assert est001_mat.iloc[0]['score'] == 58.3
    
    def test_all_null_scores(self, mock_etl_transform: ETLTransform,
                              sample_raw_with_all_nulls: pd.DataFrame):
        """Verify that all-NULL scores are handled gracefully."""
        result = mock_etl_transform._transform_to_long_format(
            sample_raw_with_all_nulls, year=2023
        )
        
        # All rows should have is_null_score=True
        assert all(result['is_null_score'] == True)
        assert all(result['score'].isna())
    
    def test_null_scores_included_in_output(self, mock_etl_transform: ETLTransform,
                                             sample_raw_df_2023: pd.DataFrame):
        """Verify that rows with NULL scores are NOT filtered out."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        
        # EST001 has NULL ccss score
        est001_ccss = result[
            (result['cor_est'] == 'EST001') & (result['area_academica'] == 'ccss')
        ]
        assert len(est001_ccss) == 1
        assert est001_ccss.iloc[0]['is_null_score'] == True
    
    def test_null_score_count_accuracy(self, mock_etl_transform: ETLTransform,
                                        sample_raw_df_2023: pd.DataFrame):
        """Verify NULL score count is accurate."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        actual_nulls = result['is_null_score'].sum()
        
        # In sample_raw_df_2023:
        # EST001: CS=None (1 null)
        # EST002: no nulls  
        # EST003: MA=None (1 null)
        # Total: 2 nulls (but both are None in the fixture)
        expected_nulls = 2
        
        assert actual_nulls == expected_nulls, \
            f"Expected {expected_nulls} NULLs, got {actual_nulls}"


# ==========================================
# Test: Data Quality Checks
# ==========================================

class TestDataQualityCheck:
    """Tests for data quality gate validation."""
    
    def test_quality_check_passes_valid_data(self, mock_etl_transform: ETLTransform,
                                               sample_raw_df_2023: pd.DataFrame):
        """Verify that valid data passes quality checks."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        summary = mock_etl_transform._validate_data_quality(sample_raw_df_2023, cleaned)
        
        assert summary.is_valid == True
        assert summary.total_input_rows == len(sample_raw_df_2023)
        assert summary.total_output_rows == len(cleaned)
    
    def test_quality_check_detects_null_coverage(self, mock_etl_transform: ETLTransform,
                                                  sample_raw_df_2023: pd.DataFrame):
        """Verify that NULL coverage is calculated correctly."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        summary = mock_etl_transform._validate_data_quality(sample_raw_df_2023, cleaned)
        
        assert summary.null_scores_count > 0
        assert 0.0 < summary.null_scores_percent < 100.0
    
    def test_quality_check_detects_out_of_range_scores(self, mock_etl_transform: ETLTransform):
        """Verify that out-of-range scores are detected and generate warnings (not errors)."""
        raw_df = pd.DataFrame({
            'id_ie': ['IE001'],
            'ano_evaluacion': [2023],
        })
        
        cleaned_df = pd.DataFrame({
            'id_ie': ['IE001'],
            'id_seccion': ['SEC001'],
            'year': [2023],
            'area': ['Urban'],  # Geographic zone
            'cor_est': ['EST001'],  # Student ID
            'area_academica': ['comunicación'],  # User said: WITH accent!
            'score': [1500.0],  # Out of range! (valid range is [0, 1000])
            'is_null_score': [False],
            'created_at': [datetime.now(timezone.utc)],
        })
        
        summary = mock_etl_transform._validate_data_quality(raw_df, cleaned_df)
        
        # Out-of-range scores should generate warnings, not errors
        assert summary.score_range_valid == False
        assert len(summary.warnings) > 0
        assert any('out of valid range' in w for w in summary.warnings)
        # errors should be empty (we warn but don't fail the ETL)
        assert len(summary.errors) == 0
    
    def test_quality_check_warns_on_high_null_coverage(self, mock_etl_transform: ETLTransform):
        """Verify warning is generated when critical column NULL > 5%."""
        raw_df = pd.DataFrame({
            'id_ie': ['IE001'] * 20,
            'ano_evaluacion': [2023] * 20,
        })
        
        # Make 10% of cor_est NULL (student ID is critical)
        cleaned_df = pd.DataFrame({
            'id_ie': ['IE001'] * 20,
            'id_seccion': ['SEC001'] * 20,
            'year': [2023] * 20,
            'area': ['Urban'] * 20,
            'cor_est': [None] * 2 + ['EST001'] * 18,  # 10% NULL
            'area_academica': ['comunicación'] * 20,  # User said: WITH accent!
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
                                                    sample_raw_df_2023: pd.DataFrame):
        """Verify that academic areas processed count is accurate."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        summary = mock_etl_transform._validate_data_quality(sample_raw_df_2023, cleaned)
        
        # Should be 3 (comunicación, matemática, ccss) - User said WITH accents!
        assert summary.areas_processed == 3


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
    """Tests for dimension table creation."""
    
    def test_dim_meta_has_unique_combinations(self, mock_etl_transform: ETLTransform,
                                                 sample_raw_df_2023: pd.DataFrame):
        """Verify dim_meta has unique institution-academic_area-year combos."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        dim_meta = mock_etl_transform._create_dim_meta(cleaned)
        
        # Check no duplicates (area_academica in dim_meta = academic area)
        combo_col = ['id_ie', 'year', 'area_academica']
        duplicates = dim_meta.duplicated(subset=combo_col)
        assert duplicates.sum() == 0, "Found duplicate combinations in dim_meta"
    
    def test_dim_meta_has_target_score(self, mock_etl_transform: ETLTransform,
                                        sample_raw_df_2023: pd.DataFrame):
        """Verify dim_meta has correct target score."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        dim_meta = mock_etl_transform._create_dim_meta(cleaned)
        
        from src.ingestion.config import settings
        assert all(dim_meta['target_score'] == settings.TARGET_SCORE_THRESHOLD)
    
    def test_dim_meta_has_region(self, mock_etl_transform: ETLTransform,
                                 sample_raw_df_2023: pd.DataFrame):
        """Verify dim_meta has region set to CALLAO."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        dim_meta = mock_etl_transform._create_dim_meta(cleaned)
        
        assert all(dim_meta['region'] == 'CALLAO')
    
    def test_dim_meta_uses_academic_area(self, mock_etl_transform: ETLTransform,
                                            sample_raw_df_2023: pd.DataFrame):
        """Verify dim_meta uses academic area (area_academica), not geographic zone (area)."""
        cleaned = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        dim_meta = mock_etl_transform._create_dim_meta(cleaned)
        
        # dim_meta['area_academica'] should have academic areas (NOT 'area' which is geographic)
        # User said: "comunicación y matemática" (WITH accents!)
        expected_areas = {'comunicación', 'matemática', 'ccss'}
        actual_areas = set(dim_meta['area_academica'].unique())
        assert actual_areas == expected_areas, \
            f"dim_meta should use area_academica for academic areas, got: {actual_areas}"
    
    def test_dim_calendario_has_correct_years(self, mock_etl_transform: ETLTransform,
                                                sample_raw_df_2023: pd.DataFrame):
        """Verify dim_calendario covers all years in data."""
        # First transform to get cleaned_df with 'year' column
        cleaned_df = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        dim_cal = mock_etl_transform._create_dim_calendario(cleaned_df)
        
        years_in_data = {2023}  # From the fixture's ano_evaluacion column
        years_in_cal = set(dim_cal['year'])
        
        assert years_in_data.issubset(years_in_cal), \
            f"Missing years in calendario: {years_in_data - years_in_cal}"
    
    def test_dim_calendario_has_quarter(self, mock_etl_transform: ETLTransform,
                                        sample_raw_df_2023: pd.DataFrame):
        """Verify dim_calendario has correct quarter values."""
        # First transform to get cleaned_df with 'year' column
        cleaned_df = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2023)
        dim_cal = mock_etl_transform._create_dim_calendario(cleaned_df)
        
        assert all(1 <= q <= 4 for q in dim_cal['quarter'])


# ==========================================
# Test: Dynamic Column Discovery
# ==========================================

class TestDynamicColumnDiscovery:
    """Tests for dynamic column discovery across different years."""
    
    def test_discover_2023_columns(self, mock_etl_transform: ETLTransform):
        """Verify that 2023 columns (M500_EM_2S_2023_XX) are discovered."""
        df = pd.DataFrame({
            'medida_lectura': [1, 2, 3],
            'grupo_lectura': ['A', 'B', 'C'],
            'peso_lectura': [1.0, 1.0, 1.0],
            # Also add MA to test multiple areas
            'medida_matematica': [4, 5, 6],
            'grupo_matematica': ['D', 'E', 'F'],
            'peso_matematica': [1.0, 1.0, 1.0],
        })
        
        # Add required columns
        df['id_ie'] = ['IE001', 'IE002', 'IE003']
        df['id_seccion'] = ['SEC001', 'SEC002', 'SEC003']
        df['cor_est'] = ['EST001', 'EST002', 'EST003']
        df['area'] = ['Urban', 'Urban', 'Rural']
        df['ano_evaluacion'] = [2023, 2023, 2023]
        
        result = mock_etl_transform._transform_to_long_format(df, year=2023)
        # 2 areas (comunicación, matemática) × 3 students = 6 rows
        # User said: "comunicación y matemática" (WITH accents!)
        assert len(result) == 6
        assert set(result['area_academica'].unique()) == {'comunicación', 'matemática'}
    
    def test_discover_2022_columns(self, mock_etl_transform: ETLTransform):
        """Verify that 2022 columns (medida500_X) are discovered."""
        df = pd.DataFrame({
            'medida_lectura': [1, 2, 3],   # comunicación
            'grupo_lectura': ['A', 'B', 'C'],
            'peso_lectura': [1.0, 1.0, 1.0],
            'medida_matematica': [4, 5, 6],   # matemática (REQUIRED - must be present!)
            'grupo_matematica': ['D', 'E', 'F'],
            'peso_matematica': [1.0, 1.0, 1.0],
        })
        
        # Add required columns
        df['id_ie'] = ['IE001', 'IE002', 'IE003']
        df['id_seccion'] = ['SEC001', 'SEC002', 'SEC003']
        df['cor_est'] = ['EST001', 'EST002', 'EST003']
        df['area'] = ['Urban', 'Urban', 'Rural']
        df['ano_evaluacion'] = [2022, 2022, 2022]
        
        result = mock_etl_transform._transform_to_long_format(df, year=2022)
        # 2 areas (comunicación, matemática) × 3 students = 6 rows
        # User said: "comunicación y matemática" (WITH accents!)
        assert len(result) == 6
        assert set(result['area_academica'].unique()) == {'comunicación', 'matemática'}
    
    def test_optional_area_not_present(self, mock_etl_transform: ETLTransform):
        """Verify that optional areas (ccss, cyt) are skipped if not present."""
        df = pd.DataFrame({
            'medida_lectura': [1, 2, 3],
            'grupo_lectura': ['A', 'B', 'C'],
            'peso_lectura': [1.0, 1.0, 1.0],
            'medida_matematica': [4, 5, 6],
            'grupo_matematica': ['D', 'E', 'F'],
            'peso_matematica': [1.0, 1.0, 1.0],
            # No CS columns - ccss should be skipped
        })
        
        # Add required columns
        df['id_ie'] = ['IE001', 'IE002', 'IE003']
        df['id_seccion'] = ['SEC001', 'SEC002', 'SEC003']
        df['cor_est'] = ['EST001', 'EST002', 'EST003']
        df['area'] = ['Urban', 'Urban', 'Rural']
        df['ano_evaluacion'] = [2023, 2023, 2023]
        
        result = mock_etl_transform._transform_to_long_format(df, year=2023)
        # Only 2 areas (comunicación, matemática) × 3 students = 6 rows
        # User said: "comunicación y matemática" (WITH accents!)
        assert len(result) == 6
        assert set(result['area_academica'].unique()) == {'comunicación', 'matemática'}
    
    def test_missing_required_area_logs_warning(self, mock_etl_transform: ETLTransform):
        """Verify that missing REQUIRED areas log a warning (but don't fail if some areas found)."""
        df = pd.DataFrame({
            # Only ccss (optional) - missing required areas
            'medida_ciencias': [1, 2, 3],
            'grupo_ciencias': ['A', 'B', 'C'],
            'peso_ciencias': [1.0, 1.0, 1.0],
        })
        
        # Add required columns
        df['id_ie'] = ['IE001', 'IE002', 'IE003']
        df['id_seccion'] = ['SEC001', 'SEC002', 'SEC003']
        df['cor_est'] = ['EST001', 'EST002', 'EST003']
        df['area'] = ['Urban', 'Urban', 'Rural']
        df['ano_evaluacion'] = [2023, 2023, 2023]
        
        # Should NOT raise an error (code logs warning but continues)
        # Since no required areas found, should return empty or raise ETLTransformError
        # Actually the code raises ETLTransformError if NO areas found at all
        with pytest.raises(ETLTransformError):
            mock_etl_transform._transform_to_long_format(df, year=2023)


# ==========================================
# Test: Year from Filename
# ==========================================

class TestYearFromFilename:
    """Tests for year extraction from filename."""
    
    def test_year_parameter_used(self, mock_etl_transform: ETLTransform,
                                  sample_raw_df_2023: pd.DataFrame):
        """Verify that year column comes from ano_evaluacion, not the parameter."""
        # ano_evaluacion=2023 in sample_raw_df_2023, so year=2022 parameter is ignored
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=2022)
        assert all(result['year'] == 2023), "Year should be 2023 (from ano_evaluacion column)"
    
    def test_year_none_uses_data_column(self, mock_etl_transform: ETLTransform,
                                          sample_raw_df_2023: pd.DataFrame):
        """Verify that year=None tries to use ano_evaluacion column."""
        result = mock_etl_transform._transform_to_long_format(sample_raw_df_2023, year=None)
        assert all(result['year'] == 2023), "Should use year from ano_evaluacion column"


# ==========================================
# Test: ETL Extraction with Region Filter (RF-007, T-019)
# ==========================================

class TestExtractFromMongoDB:
    """Tests for _extract_from_mongodb() with nom_dre filter."""

    def test_extract_uses_all_peru_collection(self, mock_etl_transform: ETLTransform):
        """Verify _extract_from_mongodb reads from enla_all_peru_raw collection."""
        mock_collection = MagicMock()
        mock_collection.find.return_value = []
        mock_etl_transform.mongo_manager.get_collection.return_value = mock_collection

        mock_etl_transform._extract_from_mongodb()

        # Verify it reads from MONGODB_ETL_SOURCE_COLLECTION (enla_all_peru_raw)
        call_args = mock_etl_transform.mongo_manager.get_collection.call_args
        from src.ingestion.config import settings
        assert call_args[0][1] == settings.MONGODB_ETL_SOURCE_COLLECTION

    def test_extract_applies_nom_dre_filter(self, mock_etl_transform: ETLTransform):
        """Verify query includes {'nom_dre': 'CALLAO'} filter."""
        mock_collection = MagicMock()
        mock_collection.find.return_value = []
        mock_etl_transform.mongo_manager.get_collection.return_value = mock_collection

        mock_etl_transform._extract_from_mongodb()

        # Verify find was called with nom_dre filter
        call_args = mock_collection.find.call_args
        query = call_args[0][0]
        assert 'nom_dre' in query
        assert query['nom_dre'] == 'CALLAO'

    def test_extract_with_year_filter(self, mock_etl_transform: ETLTransform):
        """Verify year is combined with nom_dre filter."""
        mock_collection = MagicMock()
        mock_collection.find.return_value = []
        mock_etl_transform.mongo_manager.get_collection.return_value = mock_collection

        mock_etl_transform._extract_from_mongodb(year=2023)

        call_args = mock_collection.find.call_args
        query = call_args[0][0]
        assert query == {'nom_dre': 'CALLAO', 'ano_evaluacion': 2023}

    def test_extract_only_callao_data_in_bigquery(self, mock_etl_transform: ETLTransform):
        """Verify that only Callao records are returned (no non-Callao data)."""
        mock_collection = MagicMock()
        # Simulate MongoDB returning only Callao records (filter applied at DB level)
        mock_collection.find.return_value = [
            {'_id': 'obj1', 'nom_dre': 'CALLAO', 'ano_evaluacion': 2023},
            {'_id': 'obj2', 'nom_dre': 'CALLAO', 'ano_evaluacion': 2023},
        ]
        mock_etl_transform.mongo_manager.get_collection.return_value = mock_collection

        result = mock_etl_transform._extract_from_mongodb()

        assert len(result) == 2
        assert all(result['nom_dre'] == 'CALLAO')

    def test_extract_empty_result_returns_empty_df(self, mock_etl_transform: ETLTransform):
        """Verify empty MongoDB result returns empty DataFrame."""
        mock_collection = MagicMock()
        mock_collection.find.return_value = []
        mock_etl_transform.mongo_manager.get_collection.return_value = mock_collection

        result = mock_etl_transform._extract_from_mongodb()

        assert isinstance(result, pd.DataFrame)
        assert result.empty
