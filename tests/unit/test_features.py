"""Unit tests for feature engineering module (Sprint 3).

Tests cover:
- Yearly average calculation (grouping, multi-section handling)
- Trend calculation (YoY change, division by zero)
- Variance calculation (std dev across years)
- Feature normalization (min-max scaling)
- Target generation (threshold comparison)
- Edge cases (NULL handling, single institution, all same scores)
- Full pipeline integration
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from src.features.engineer import (
    FeatureEngineer,
    FeatureEngineeringError,
    FeaturePipelineResult,
    AREAS,
    FEATURE_COLS,
    YEARS,
    run_feature_pipeline,
)
from src.features.schemas import FEATURES_SCHEMA, NORM_PARAMS_SCHEMA


# ==========================================
# Test Fixtures
# ==========================================

@pytest.fixture
def sample_fact_df() -> pd.DataFrame:
    """Create a sample fact_enla DataFrame with multiple institutions, sections, and years."""
    return pd.DataFrame({
        'id_ie': [
            'IE001', 'IE001',  # IE001 has 2 sections in 2021
            'IE001', 'IE001',  # IE001 has 2 sections in 2022
            'IE001',           # IE001 has 1 section in 2023
            'IE002',           # IE002 has 1 section per year
            'IE002',
            'IE002',
            'IE003',           # IE003 only has data for 2021 and 2023
            'IE003',
        ],
        'nom_ie': [
            'Colegio A', 'Colegio A',
            'Colegio A', 'Colegio A',
            'Colegio A',
            'Colegio B', 'Colegio B', 'Colegio B',
            'Colegio C', 'Colegio C',
        ],
        'year': [2021, 2021, 2022, 2022, 2023, 2021, 2022, 2023, 2021, 2023],
        'area_academica': ['comunicación'] * 10,  # With accent to match actual data
        'score': [70.0, 80.0, 72.0, 78.0, 85.0, 60.0, 65.0, 55.0, 90.0, 95.0],
    })


@pytest.fixture
def sample_fact_all_areas() -> pd.DataFrame:
    """Create a sample DataFrame with all 4 areas."""
    records = []
    for ie_id, name in [('IE001', 'Colegio A'), ('IE002', 'Colegio B')]:
        for year in [2021, 2022, 2023]:
            for area in AREAS:
                base = 70 if area == 'comunicación' else 65
                records.append({
                    'id_ie': ie_id,
                    'nom_ie': name,
                    'year': year,
                    'area_academica': area,
                    'score': base + year - 2021 + (5 if ie_id == 'IE002' else 0),
                })
    return pd.DataFrame(records)


@pytest.fixture
def mock_bq_manager():
    """Create a mocked BigQueryClientManager."""
    manager = MagicMock()
    manager.project_id = 'test-project'
    manager.dataset_id = 'BI_ENLA'
    return manager


@pytest.fixture
def feature_engineer(mock_bq_manager) -> FeatureEngineer:
    """Create a FeatureEngineer with mocked BQ client."""
    engineer = FeatureEngineer.__new__(FeatureEngineer)
    engineer.bq_manager = mock_bq_manager
    engineer.target_threshold = 60.0
    engineer.norm_min = -1.0
    engineer.norm_max = 1.0
    engineer.dataset_id = 'BI_ENLA'
    engineer._norm_params_store = {}
    return engineer


# ==========================================
# Test: Yearly Averages
# ==========================================

class TestYearlyAverages:
    """Tests for per-year average score calculation."""

    def test_basic_yearly_averages(self, feature_engineer: FeatureEngineer,
                                   sample_fact_df: pd.DataFrame):
        """Verify correct grouping and averaging for a single area."""
        result = feature_engineer.calculate_yearly_averages(
            sample_fact_df, 'comunicación'
        )

        assert len(result) == 3  # 3 unique institutions
        assert set(result.columns) == {'institution_id', 'nom_ie', 'avg_2021', 'avg_2022', 'avg_2023'}

    def test_averages_multi_section(self, feature_engineer: FeatureEngineer,
                                     sample_fact_df: pd.DataFrame):
        """Verify that multiple sections are averaged correctly."""
        result = feature_engineer.calculate_yearly_averages(
            sample_fact_df, 'comunicación'
        )

        # IE001 2021: (70 + 80) / 2 = 75.0
        ie001_2021 = result[result['institution_id'] == 'IE001']['avg_2021'].values[0]
        assert ie001_2021 == 75.0

    def test_missing_year_is_nan(self, feature_engineer: FeatureEngineer,
                                  sample_fact_df: pd.DataFrame):
        """Verify that institutions missing a year get NaN for that year."""
        result = feature_engineer.calculate_yearly_averages(
            sample_fact_df, 'comunicación'
        )

        # IE003 has no 2022 data
        ie003_2022 = result[result['institution_id'] == 'IE003']['avg_2022'].values[0]
        assert pd.isna(ie003_2022)

    def test_empty_area_returns_empty_df(self, feature_engineer: FeatureEngineer,
                                          sample_fact_df: pd.DataFrame):
        """Verify that filtering a non-existent area returns empty DataFrame."""
        result = feature_engineer.calculate_yearly_averages(
            sample_fact_df, 'matemática'  # No matemática data in sample
        )

        assert result.empty

    def test_null_scores_excluded(self, feature_engineer: FeatureEngineer):
        """Verify that NULL scores are excluded from averages."""
        df = pd.DataFrame({
            'id_ie': ['IE001', 'IE001', 'IE001'],
            'nom_ie': ['Colegio A'] * 3,
            'year': [2021, 2021, 2021],
             'area_academica': ['comunicación'] * 3,  # With accent
             'score': [70.0, np.nan, 80.0],
        })

        result = feature_engineer.calculate_yearly_averages(df, 'comunicación')
        # Should average only the two valid scores: (70 + 80) / 2 = 75.0
        assert result['avg_2021'].values[0] == 75.0


# ==========================================
# Test: Trend Calculation
# ==========================================

class TestTrendCalculation:
    """Tests for year-over-year trend calculation."""

    def test_basic_trend(self, feature_engineer: FeatureEngineer):
        """Verify trend = (2023 - 2022) / 2022."""
        df = pd.DataFrame({
            'institution_id': ['IE001'],
            'nom_ie': ['Colegio A'],
            'avg_2021': [70.0],
            'avg_2022': [80.0],
            'avg_2023': [88.0],
        })

        result = feature_engineer.calculate_trend(df)

        # (88 - 80) / 80 = 0.1
        assert abs(result['trend'].values[0] - 0.1) < 1e-10

    def test_declining_trend(self, feature_engineer: FeatureEngineer):
        """Verify negative trend when scores decline."""
        df = pd.DataFrame({
            'institution_id': ['IE001'],
            'nom_ie': ['Colegio A'],
            'avg_2021': [70.0],
            'avg_2022': [80.0],
            'avg_2023': [60.0],
        })

        result = feature_engineer.calculate_trend(df)

        # (60 - 80) / 80 = -0.25
        assert abs(result['trend'].values[0] - (-0.25)) < 1e-10

    def test_division_by_zero(self, feature_engineer: FeatureEngineer):
        """Verify trend = 0 when avg_2022 = 0."""
        df = pd.DataFrame({
            'institution_id': ['IE001'],
            'nom_ie': ['Colegio A'],
            'avg_2021': [70.0],
            'avg_2022': [0.0],
            'avg_2023': [50.0],
        })

        result = feature_engineer.calculate_trend(df)

        assert result['trend'].values[0] == 0.0

    def test_nan_trend_when_missing_year(self, feature_engineer: FeatureEngineer):
        """Verify trend is NaN when 2022 or 2023 is missing."""
        df = pd.DataFrame({
            'institution_id': ['IE001', 'IE002'],
            'nom_ie': ['Colegio A', 'Colegio B'],
            'avg_2021': [70.0, 60.0],
            'avg_2022': [np.nan, 80.0],
            'avg_2023': [85.0, np.nan],
        })

        result = feature_engineer.calculate_trend(df)

        assert pd.isna(result.iloc[0]['trend'])  # IE001: missing 2022
        assert pd.isna(result.iloc[1]['trend'])  # IE002: missing 2023

    def test_zero_change(self, feature_engineer: FeatureEngineer):
        """Verify trend = 0 when scores don't change."""
        df = pd.DataFrame({
            'institution_id': ['IE001'],
            'nom_ie': ['Colegio A'],
            'avg_2021': [70.0],
            'avg_2022': [75.0],
            'avg_2023': [75.0],
        })

        result = feature_engineer.calculate_trend(df)

        assert result['trend'].values[0] == 0.0


# ==========================================
# Test: Variance Calculation
# ==========================================

class TestVarianceCalculation:
    """Tests for standard deviation across years."""

    def test_basic_variance(self, feature_engineer: FeatureEngineer):
        """Verify std dev calculation across 3 years."""
        df = pd.DataFrame({
            'institution_id': ['IE001'],
            'nom_ie': ['Colegio A'],
            'avg_2021': [70.0],
            'avg_2022': [80.0],
            'avg_2023': [90.0],
        })

        result = feature_engineer.calculate_variance(df)

        # Population std dev of [70, 80, 90] = sqrt(66.67) ≈ 8.165
        expected = np.std([70.0, 80.0, 90.0], ddof=0)
        assert abs(result['variance'].values[0] - expected) < 1e-10

    def test_zero_variance_same_scores(self, feature_engineer: FeatureEngineer):
        """Verify variance = 0 when all scores are the same."""
        df = pd.DataFrame({
            'institution_id': ['IE001'],
            'nom_ie': ['Colegio A'],
            'avg_2021': [75.0],
            'avg_2022': [75.0],
            'avg_2023': [75.0],
        })

        result = feature_engineer.calculate_variance(df)

        assert result['variance'].values[0] == 0.0

    def test_variance_with_missing_year(self, feature_engineer: FeatureEngineer):
        """Verify variance is computed with available years only."""
        df = pd.DataFrame({
            'institution_id': ['IE001'],
            'nom_ie': ['Colegio A'],
            'avg_2021': [70.0],
            'avg_2022': [np.nan],
            'avg_2023': [90.0],
        })

        result = feature_engineer.calculate_variance(df)

        # std dev of [70, 90] with ddof=0
        expected = np.std([70.0, 90.0], ddof=0)
        assert abs(result['variance'].values[0] - expected) < 1e-10


# ==========================================
# Test: Normalization
# ==========================================

class TestNormalization:
    """Tests for min-max feature normalization."""

    def test_compute_normalization_params(self, feature_engineer: FeatureEngineer):
        """Verify min/max computation for feature columns."""
        df = pd.DataFrame({
            'avg_score_2023': [70.0, 80.0, 90.0],
            'trend': [0.1, -0.2, 0.0],
            'variance': [5.0, 10.0, 2.0],
        })

        params = feature_engineer.compute_normalization_params(
            df, ['avg_score_2023', 'trend', 'variance']
        )

        assert params['avg_score_2023'] == (70.0, 90.0)
        assert params['trend'] == (-0.2, 0.1)
        assert params['variance'] == (2.0, 10.0)

    def test_basic_normalization_formula(self, feature_engineer: FeatureEngineer):
        """Verify normalization formula: 2*(x-min)/(max-min)-1."""
        df = pd.DataFrame({
            'feature_a': [50.0, 75.0, 100.0],
        })

        params = {'feature_a': (50.0, 100.0)}
        result = feature_engineer.normalize_features(df, params)

        # Min (50) → -1, Max (100) → 1, Mid (75) → 0
        assert abs(result['feature_a'].values[0] - (-1.0)) < 1e-10
        assert abs(result['feature_a'].values[1] - 0.0) < 1e-10
        assert abs(result['feature_a'].values[2] - 1.0) < 1e-10

    def test_normalization_preserves_nan(self, feature_engineer: FeatureEngineer):
        """Verify NaN values remain NaN after normalization."""
        df = pd.DataFrame({
            'feature_a': [50.0, np.nan, 100.0],
        })

        params = {'feature_a': (50.0, 100.0)}
        result = feature_engineer.normalize_features(df, params)

        assert pd.isna(result.iloc[1]['feature_a'])

    def test_normalization_zero_span(self, feature_engineer: FeatureEngineer):
        """Verify handling when min == max (all same values)."""
        df = pd.DataFrame({
            'feature_a': [75.0, 75.0, 75.0],
        })

        params = {'feature_a': (75.0, 75.0)}
        result = feature_engineer.normalize_features(df, params)

        # All same values → mapped to midpoint (0.0 for [-1, 1] range)
        assert all(result['feature_a'] == 0.0)

    def test_custom_normalization_range(self, feature_engineer: FeatureEngineer):
        """Verify normalization works with custom min/max range."""
        df = pd.DataFrame({
            'feature_a': [0.0, 50.0, 100.0],
        })

        params = {'feature_a': (0.0, 100.0)}
        result = feature_engineer.normalize_features(df, params, norm_min=0.0, norm_max=1.0)

        assert abs(result['feature_a'].values[0] - 0.0) < 1e-10
        assert abs(result['feature_a'].values[1] - 0.5) < 1e-10
        assert abs(result['feature_a'].values[2] - 1.0) < 1e-10

    def test_normalization_with_missing_columns(self, feature_engineer: FeatureEngineer):
        """Verify graceful handling of missing feature columns."""
        df = pd.DataFrame({
            'feature_a': [50.0, 75.0, 100.0],
        })

        params = {'feature_a': (50.0, 100.0), 'feature_b': (0.0, 1.0)}
        # Should not raise, just skip feature_b
        result = feature_engineer.normalize_features(df, params)

        assert 'feature_a' in result.columns


# ==========================================
# Test: Target Generation
# ==========================================

class TestTargetGeneration:
    """Tests for binary target label generation."""

    def test_target_above_threshold(self, feature_engineer: FeatureEngineer):
        """Verify target = 1 when score > threshold."""
        df = pd.DataFrame({
            'raw_avg_score_2023': [65.0, 80.0, 100.0],
        })

        result = feature_engineer.generate_target(df, meta_threshold=60.0)

        assert all(result['target'] == 1.0)

    def test_target_below_threshold(self, feature_engineer: FeatureEngineer):
        """Verify target = 0 when score <= threshold."""
        df = pd.DataFrame({
            'raw_avg_score_2023': [30.0, 59.9, 60.0],
        })

        result = feature_engineer.generate_target(df, meta_threshold=60.0)

        assert all(result['target'] == 0.0)

    def test_target_nan_for_null_score(self, feature_engineer: FeatureEngineer):
        """Verify target is NaN when score is NULL."""
        df = pd.DataFrame({
            'raw_avg_score_2023': [70.0, np.nan, 50.0],
        })

        result = feature_engineer.generate_target(df, meta_threshold=60.0)

        assert result.iloc[0]['target'] == 1.0
        assert pd.isna(result.iloc[1]['target'])
        assert result.iloc[2]['target'] == 0.0

    def test_target_custom_threshold(self, feature_engineer: FeatureEngineer):
        """Verify target uses custom threshold."""
        df = pd.DataFrame({
            'raw_avg_score_2023': [55.0, 75.0],
        })

        result = feature_engineer.generate_target(df, meta_threshold=70.0)

        assert result.iloc[0]['target'] == 0.0  # 55 < 70
        assert result.iloc[1]['target'] == 1.0  # 75 > 70


# ==========================================
# Test: Edge Cases
# ==========================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_area_returns_empty(self, feature_engineer: FeatureEngineer):
        """Verify that invalid area returns empty DataFrame (no error raised)."""
        result = feature_engineer.engineer_features_for_area('invalid_area')
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        # Verify expected columns exist in empty DataFrame
        assert 'institution_id' in result.columns
        assert 'area' in result.columns

    def test_all_same_scores(self, feature_engineer: FeatureEngineer):
        """Verify pipeline handles institutions with identical scores."""
        df = pd.DataFrame({
            'id_ie': ['IE001'] * 3,
            'nom_ie': ['Colegio A'] * 3,
            'year': [2021, 2022, 2023],
             'area_academica': ['comunicación'] * 3,  # With accent
             'score': [70.0, 70.0, 70.0],
        })

        avg_df = feature_engineer.calculate_yearly_averages(df, 'comunicación')
        assert len(avg_df) == 1
        assert avg_df['avg_2021'].values[0] == 70.0
        assert avg_df['avg_2022'].values[0] == 70.0
        assert avg_df['avg_2023'].values[0] == 70.0

        # Trend should be 0 (no change)
        trend_df = feature_engineer.calculate_trend(avg_df)
        assert trend_df['trend'].values[0] == 0.0

        # Variance should be 0 (no variation)
        var_df = feature_engineer.calculate_variance(avg_df)
        assert var_df['variance'].values[0] == 0.0

    def test_single_institution(self, feature_engineer: FeatureEngineer):
        """Verify pipeline works with a single institution."""
        df = pd.DataFrame({
            'id_ie': ['IE001'] * 3,
            'nom_ie': ['Colegio A'] * 3,
            'year': [2021, 2022, 2023],
             'area_academica': ['comunicación'] * 3,  # With accent
             'score': [60.0, 70.0, 80.0],
        })

        avg_df = feature_engineer.calculate_yearly_averages(df, 'comunicación')
        assert len(avg_df) == 1

    def test_all_null_scores_for_area(self, feature_engineer: FeatureEngineer):
        """Verify graceful handling when all scores are NULL."""
        df = pd.DataFrame({
            'id_ie': ['IE001'] * 3,
            'nom_ie': ['Colegio A'] * 3,
            'year': [2021, 2022, 2023],
             'area_academica': ['comunicación'] * 3,  # With accent
             'score': [np.nan, np.nan, np.nan],
        })

        result = feature_engineer.calculate_yearly_averages(df, 'comunicación')
        assert result.empty

    def test_normalization_params_all_nan(self, feature_engineer: FeatureEngineer):
        """Verify normalization params when all values are NaN."""
        df = pd.DataFrame({
            'trend': [np.nan, np.nan, np.nan],
        })

        params = feature_engineer.compute_normalization_params(df, ['trend'])
        assert params['trend'] == (0.0, 0.0)

    def test_feature_pipeline_result_defaults(self):
        """Verify FeaturePipelineResult default values."""
        result = FeaturePipelineResult()

        assert result.areas_processed == 0
        assert result.total_features == 0
        assert result.normalization_params_loaded == 0
        assert result.status == "pending"
        assert result.errors == []
        assert result.is_valid == True  # No errors initially
        assert result.is_success == False  # Not yet completed

    def test_feature_pipeline_result_with_errors(self):
        """Verify is_success is False when errors exist."""
        result = FeaturePipelineResult(
            status="failed",
            errors=["Error 1", "Error 2"],
        )

        assert result.is_success == False


# ==========================================
# Test: Schema Verification
# ==========================================

class TestSchemas:
    """Tests for BigQuery schema definitions."""

    def test_features_schema_has_required_columns(self):
        """Verify FEATURES_SCHEMA contains all required columns."""
        schema_cols = {field.name for field in FEATURES_SCHEMA}
        required_cols = {
            'feature_id', 'area_academica', 'institution_id', 'nom_ie',
            'avg_score_2023', 'avg_score_2022', 'avg_score_2021',
            'trend', 'variance',
            'target',
            'raw_avg_score_2023', 'raw_avg_score_2022', 'raw_avg_score_2021',
            'raw_trend', 'raw_variance',
            'meta_threshold', 'created_at',
        }

        assert required_cols.issubset(schema_cols)

    def test_norm_params_schema_has_required_columns(self):
        """Verify NORM_PARAMS_SCHEMA contains all required columns."""
        schema_cols = {field.name for field in NORM_PARAMS_SCHEMA}
        required_cols = {'param_id', 'area_academica', 'feature_name', 'min_value', 'max_value', 'created_at'}

        assert required_cols.issubset(schema_cols)

    def test_feature_id_is_required(self):
        """Verify feature_id is REQUIRED mode."""
        feature_id_field = next(f for f in FEATURES_SCHEMA if f.name == 'feature_id')
        assert feature_id_field.mode == 'REQUIRED'

    def test_institution_id_is_required(self):
        """Verify institution_id is REQUIRED mode."""
        inst_field = next(f for f in FEATURES_SCHEMA if f.name == 'institution_id')
        assert inst_field.mode == 'REQUIRED'
