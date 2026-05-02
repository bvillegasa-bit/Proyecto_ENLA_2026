"""Focused unit tests for normalization logic (Sprint 3).

Tests cover:
- Basic min-max normalization
- Edge case: all same values (min == max)
- Edge case: single data point
- Negative raw values
- Inverse transform (reversing normalization)
- Custom normalization ranges
- NaN preservation through normalization cycle
"""

import pytest
import pandas as pd
import numpy as np

from src.features.engineer import FeatureEngineer


# ==========================================
# Test Fixtures
# ==========================================

@pytest.fixture
def feature_engineer() -> FeatureEngineer:
    """Create a FeatureEngineer with default parameters."""
    engineer = FeatureEngineer.__new__(FeatureEngineer)
    engineer.bq_manager = None
    engineer.target_threshold = 60.0
    engineer.norm_min = -1.0
    engineer.norm_max = 1.0
    engineer.dataset_id = 'BI_ENLA'
    engineer._norm_params_store = {}
    return engineer


@pytest.fixture
def feature_engineer_custom_range() -> FeatureEngineer:
    """Create a FeatureEngineer with custom normalization range [0, 1]."""
    engineer = FeatureEngineer.__new__(FeatureEngineer)
    engineer.bq_manager = None
    engineer.target_threshold = 60.0
    engineer.norm_min = 0.0
    engineer.norm_max = 1.0
    engineer.dataset_id = 'BI_ENLA'
    engineer._norm_params_store = {}
    return engineer


# ==========================================
# Test: Basic Normalization
# ==========================================

class TestBasicNormalization:
    """Tests for standard min-max normalization."""

    def test_simple_min_max_case(self, feature_engineer: FeatureEngineer):
        """Verify basic normalization with clear min/max."""
        df = pd.DataFrame({'feature': [10.0, 20.0, 30.0, 40.0, 50.0]})
        params = {'feature': (10.0, 50.0)}

        result = feature_engineer.normalize_features(df, params)

        # 10 → -1, 20 → -0.5, 30 → 0, 40 → 0.5, 50 → 1
        expected = [-1.0, -0.5, 0.0, 0.5, 1.0]
        actual = result['feature'].tolist()

        for a, e in zip(actual, expected):
            assert abs(a - e) < 1e-10

    def test_single_feature_column(self, feature_engineer: FeatureEngineer):
        """Verify normalization works with only one column."""
        df = pd.DataFrame({'score': [0.0, 50.0, 100.0]})
        params = {'score': (0.0, 100.0)}

        result = feature_engineer.normalize_features(df, params)

        assert abs(result['score'].iloc[0] - (-1.0)) < 1e-10
        assert abs(result['score'].iloc[2] - 1.0) < 1e-10


# ==========================================
# Test: All Same Values
# ==========================================

class TestAllSameValues:
    """Tests for edge case where all values are identical."""

    def test_all_same_values_maps_to_midpoint(self, feature_engineer: FeatureEngineer):
        """Verify that when min == max, all values map to midpoint."""
        df = pd.DataFrame({'feature': [42.0, 42.0, 42.0]})
        params = {'feature': (42.0, 42.0)}

        result = feature_engineer.normalize_features(df, params)

        # Midpoint of [-1, 1] = 0
        assert all(result['feature'] == 0.0)

    def test_all_same_values_custom_range(self, feature_engineer_custom_range: FeatureEngineer):
        """Verify midpoint mapping works with custom range [0, 1]."""
        df = pd.DataFrame({'feature': [99.0, 99.0, 99.0]})
        params = {'feature': (99.0, 99.0)}

        result = feature_engineer_custom_range.normalize_features(df, params)

        # Midpoint of [0, 1] = 0.5
        assert all(result['feature'] == 0.5)

    def test_single_value_same_as_all_same(self, feature_engineer: FeatureEngineer):
        """Verify single data point is treated like all-same-values case."""
        df = pd.DataFrame({'feature': [55.0]})
        params = {'feature': (55.0, 55.0)}

        result = feature_engineer.normalize_features(df, params)

        assert result['feature'].values[0] == 0.0


# ==========================================
# Test: Single Value
# ==========================================

class TestSingleValue:
    """Tests for normalization with only one data point."""

    def test_single_point_normalization(self, feature_engineer: FeatureEngineer):
        """Verify single point gets midpoint value."""
        df = pd.DataFrame({'feature': [100.0]})
        params = {'feature': (100.0, 100.0)}

        result = feature_engineer.normalize_features(df, params)

        assert result['feature'].values[0] == 0.0

    def test_single_point_does_not_crash(self, feature_engineer: FeatureEngineer):
        """Verify normalization doesn't crash with single point."""
        df = pd.DataFrame({'feature': [42.0]})
        params = {'feature': (42.0, 42.0)}

        # Should not raise any exception
        result = feature_engineer.normalize_features(df, params)

        assert len(result) == 1


# ==========================================
# Test: Negative Values
# ==========================================

class TestNegativeValues:
    """Tests for normalization with negative raw values."""

    def test_negative_raw_values(self, feature_engineer: FeatureEngineer):
        """Verify normalization works with negative raw values."""
        df = pd.DataFrame({'feature': [-100.0, -50.0, 0.0, 50.0]})
        params = {'feature': (-100.0, 50.0)}

        result = feature_engineer.normalize_features(df, params)

        # -100 → -1, 50 → 1, 0 → (0 - (-100)) / 150 * 2 - 1 = 100/150*2-1 = 0.333...
        assert abs(result['feature'].iloc[0] - (-1.0)) < 1e-10
        assert abs(result['feature'].iloc[3] - 1.0) < 1e-10

    def test_all_negative_values(self, feature_engineer: FeatureEngineer):
        """Verify normalization with all negative values."""
        df = pd.DataFrame({'feature': [-30.0, -20.0, -10.0]})
        params = {'feature': (-30.0, -10.0)}

        result = feature_engineer.normalize_features(df, params)

        assert abs(result['feature'].iloc[0] - (-1.0)) < 1e-10
        assert abs(result['feature'].iloc[2] - 1.0) < 1e-10

    def test_mixed_positive_negative(self, feature_engineer: FeatureEngineer):
        """Verify normalization spanning zero."""
        df = pd.DataFrame({'trend': [-0.5, 0.0, 0.5]})
        params = {'trend': (-0.5, 0.5)}

        result = feature_engineer.normalize_features(df, params)

        assert abs(result['trend'].iloc[0] - (-1.0)) < 1e-10
        assert abs(result['trend'].iloc[1] - 0.0) < 1e-10
        assert abs(result['trend'].iloc[2] - 1.0) < 1e-10


# ==========================================
# Test: Inverse Transform
# ==========================================

class TestInverseTransform:
    """Tests for reversing normalization (denormalization)."""

    def test_inverse_transform_default_range(self, feature_engineer: FeatureEngineer):
        """Verify you can reverse normalization with default [-1, 1] range."""
        raw_values = [10.0, 30.0, 50.0, 70.0, 90.0]
        df = pd.DataFrame({'feature': raw_values})
        params = {'feature': (10.0, 90.0)}

        # Normalize
        normalized = feature_engineer.normalize_features(df, params)

        # Denormalize manually: x = (normalized + 1) / 2 * (max - min) + min
        for i, raw in enumerate(raw_values):
            norm_val = normalized['feature'].iloc[i]
            recovered = (norm_val + 1.0) / 2.0 * (90.0 - 10.0) + 10.0
            assert abs(recovered - raw) < 1e-10

    def test_inverse_transform_custom_range(self, feature_engineer_custom_range: FeatureEngineer):
        """Verify reverse normalization with custom [0, 1] range."""
        raw_values = [20.0, 40.0, 60.0, 80.0, 100.0]
        df = pd.DataFrame({'feature': raw_values})
        params = {'feature': (20.0, 100.0)}

        # Normalize
        normalized = feature_engineer_custom_range.normalize_features(df, params)

        # Denormalize: x = normalized * (max - min) + min
        for i, raw in enumerate(raw_values):
            norm_val = normalized['feature'].iloc[i]
            recovered = norm_val * (100.0 - 20.0) + 20.0
            assert abs(recovered - raw) < 1e-10

    def test_inverse_preserves_order(self, feature_engineer: FeatureEngineer):
        """Verify inverse transform preserves relative ordering."""
        raw_values = [5.0, 15.0, 25.0, 35.0, 45.0]
        df = pd.DataFrame({'feature': raw_values})
        params = {'feature': (5.0, 45.0)}

        normalized = feature_engineer.normalize_features(df, params)

        # Order should be preserved
        for i in range(len(raw_values) - 1):
            assert normalized['feature'].iloc[i] < normalized['feature'].iloc[i + 1]


# ==========================================
# Test: NaN Preservation
# ==========================================

class TestNaNPreservation:
    """Tests for NaN handling through normalization."""

    def test_nan_survives_normalization(self, feature_engineer: FeatureEngineer):
        """Verify NaN values remain NaN after normalization."""
        df = pd.DataFrame({'feature': [10.0, np.nan, 30.0]})
        params = {'feature': (10.0, 30.0)}

        result = feature_engineer.normalize_features(df, params)

        assert result['feature'].iloc[0] == -1.0
        assert pd.isna(result['feature'].iloc[1])
        assert result['feature'].iloc[2] == 1.0

    def test_all_nan_column(self, feature_engineer: FeatureEngineer):
        """Verify all-NaN column is handled gracefully."""
        df = pd.DataFrame({'feature': [np.nan, np.nan, np.nan]})
        params = {'feature': (0.0, 0.0)}  # From compute_normalization_params fallback

        # Should not raise
        result = feature_engineer.normalize_features(df, params)

        assert all(pd.isna(result['feature']))

    def test_mixed_features_nan(self, feature_engineer: FeatureEngineer):
        """Verify NaN in one feature doesn't affect others."""
        df = pd.DataFrame({
            'feature_a': [10.0, 20.0, 30.0],
            'feature_b': [np.nan, 50.0, np.nan],
        })
        params = {
            'feature_a': (10.0, 30.0),
            'feature_b': (50.0, 50.0),
        }

        result = feature_engineer.normalize_features(df, params)

        # feature_a should be fully normalized
        assert abs(result['feature_a'].iloc[0] - (-1.0)) < 1e-10
        assert abs(result['feature_a'].iloc[2] - 1.0) < 1e-10

        # feature_b NaN positions preserved, non-NaN mapped to midpoint
        assert pd.isna(result['feature_b'].iloc[0])
        assert result['feature_b'].iloc[1] == 0.0  # midpoint (min==max)
        assert pd.isna(result['feature_b'].iloc[2])


# ==========================================
# Test: Normalization Parameter Computation
# ==========================================

class TestNormParamsComputation:
    """Tests for compute_normalization_params method."""

    def test_basic_params(self, feature_engineer: FeatureEngineer):
        """Verify min/max computed correctly."""
        df = pd.DataFrame({
            'avg_score_2023': [50.0, 70.0, 90.0],
            'trend': [-0.3, 0.0, 0.3],
        })

        params = feature_engineer.compute_normalization_params(
            df, ['avg_score_2023', 'trend']
        )

        assert params['avg_score_2023'] == (50.0, 90.0)
        assert params['trend'] == (-0.3, 0.3)

    def test_params_with_nan(self, feature_engineer: FeatureEngineer):
        """Verify NaN values are excluded from min/max computation."""
        df = pd.DataFrame({
            'trend': [-0.5, np.nan, 0.5],
        })

        params = feature_engineer.compute_normalization_params(df, ['trend'])

        assert params['trend'] == (-0.5, 0.5)

    def test_params_all_nan(self, feature_engineer: FeatureEngineer):
        """Verify fallback when all values are NaN."""
        df = pd.DataFrame({
            'variance': [np.nan, np.nan, np.nan],
        })

        params = feature_engineer.compute_normalization_params(df, ['variance'])

        assert params['variance'] == (0.0, 0.0)

    def test_params_missing_column(self, feature_engineer: FeatureEngineer):
        """Verify missing columns are skipped gracefully."""
        df = pd.DataFrame({
            'avg_score_2023': [50.0, 70.0],
        })

        params = feature_engineer.compute_normalization_params(
            df, ['avg_score_2023', 'nonexistent']
        )

        assert 'avg_score_2023' in params
        assert 'nonexistent' not in params
