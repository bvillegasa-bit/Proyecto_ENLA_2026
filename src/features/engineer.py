"""Feature engineering module for ENLA 2026 Callao ML prediction pipeline.

Engineers features for each subject area independently:
1. Calculate per-year average scores per institution
2. Compute trend (year-over-year change)
3. Compute variance (standard deviation across years)
4. Normalize features to [-1, 1] range
5. Generate binary target labels (success/failure vs meta threshold)

Data flow:
    fact_enla (BigQuery) → Feature engineering → enla_callao_features + enla_feature_normalization_params
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from src.logging.setup import get_logger
from src.database.bigquery_client import BigQueryClientManager, BigQueryConnectionError
from src.ingestion.config import settings
from src.features.schemas import FEATURES_SCHEMA, NORM_PARAMS_SCHEMA

logger = get_logger('feature_engineer')


# ==========================================
# Custom Exceptions
# ==========================================

class FeatureEngineeringError(Exception):
    """Exception for feature engineering errors."""
    pass


# ==========================================
# Data Classes
# ==========================================

from dataclasses import dataclass, field


@dataclass
class FeaturePipelineResult:
    """Result of the complete feature engineering pipeline."""
    areas_processed: int = 0
    total_features: int = 0
    normalization_params_loaded: int = 0
    status: str = "pending"
    errors: List[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Check if pipeline completed without errors."""
        return len(self.errors) == 0 and self.status == "success"

    @property
    def is_valid(self) -> bool:
        """Check if pipeline has no errors (regardless of status)."""
        return len(self.errors) == 0


# ==========================================
# Feature Engineering Constants
# ==========================================

AREAS = ['comunicación', 'matemática', 'ccss']  # Removed 'cyt' - no data available | User said: "comunicación y matemática" WITH accents!
FEATURE_COLS = ['avg_score_2023', 'avg_score_2022', 'avg_score_2021', 'trend', 'variance']
YEARS = [2021, 2022, 2023]

# Areas that use per-year prediction (2022, 2023)
YEAR_SPECIFIC_AREAS = ['comunicación', 'matemática']

# Areas that use general prediction (all years combined)
GENERAL_AREAS = ['ccss', 'cyt']

# Years for per-year prediction
PREDICTION_YEARS = [2022, 2023]


# ==========================================
# FeatureEngineer Class
# ==========================================

class FeatureEngineer:
    """Engineers features for ENLA prediction models.

    For each area independently:
    1. Calculates per-year average scores per institution
    2. Computes trend (YoY change = (2023 - 2022) / 2022)
    3. Computes variance (std dev across 2021, 2022, 2023)
    4. Normalizes features to [-1, 1] using min-max normalization
    5. Generates binary target labels based on meta threshold
    """

    def __init__(self, bigquery_client: Optional[BigQueryClientManager] = None,
                 target_threshold: float = 500.0,
                 norm_min: float = -1.0,
                 norm_max: float = 1.0):
        """
        Initialize FeatureEngineer.

        Args:
            bigquery_client: BigQueryClientManager instance. If None, uses global manager.
            target_threshold: Default score threshold for target generation.
            norm_min: Minimum value for normalized range.
            norm_max: Maximum value for normalized range.
        """
        self.bq_manager = bigquery_client
        self.target_threshold = target_threshold
        self.norm_min = norm_min
        self.norm_max = norm_max
        self.dataset_id = settings.GCP_DATASET_ID

        # Store normalization params per area for reproducibility
        self._norm_params_store: Dict[str, Dict[str, Tuple[float, float]]] = {}

        logger.info(f"FeatureEngineer initialized | target_threshold={self.target_threshold} norm_range={(self.norm_min, self.norm_max)} areas={AREAS}")

    def _get_bq_manager(self) -> BigQueryClientManager:
        """Get or create BigQuery manager."""
        if self.bq_manager is None:
            from src.database.bigquery_client import get_bq_manager
            self.bq_manager = get_bq_manager()
        return self.bq_manager

    # ==========================================
    # Core Feature Calculation Methods
    # ==========================================

    def calculate_yearly_averages(self, df: pd.DataFrame, area: str) -> pd.DataFrame:
        """
        Group by institution, compute average score per year for a given area.

        Averages across sections if an institution has multiple sections.
        NULL scores are excluded from averages (not treated as 0).

        Args:
            df: DataFrame from fact_enla with columns: id_ie, nom_ie, year, area_academica, score
            area: Subject area to filter for (comunicación, matemática, ccss, cyt)

        Returns:
            DataFrame with columns: institution_id, nom_ie, avg_2021, avg_2022, avg_2023
            Each row is one institution, each year is a separate column.
        """
        logger.info(f"Calculating yearly averages | area={area} input_rows={len(df)}")

        # Filter to the target area and exclude NULL scores
        area_df = df[df['area_academica'] == area].copy()
        area_df = area_df.dropna(subset=['score'])

        if area_df.empty:
            logger.warning(f"No valid data for area '{area}', returning empty DataFrame")
            return pd.DataFrame(columns=['institution_id', 'nom_ie', 'avg_2021', 'avg_2022', 'avg_2023'])

        # Group by institution and year, compute mean (averages across sections)
        # Use as_index=False to keep group keys as columns
        yearly = area_df.groupby(['id_ie', 'nom_ie', 'year'], as_index=False)['score'].mean()

        # Initialize result with unique institutions
        result = yearly[['id_ie', 'nom_ie']].drop_duplicates().copy()

        # Add year columns manually (avoid pivot_table issues with single-year data)
        for year in YEARS:
            year_data = yearly[yearly['year'] == year]
            if not year_data.empty:
                # Map id_ie to average score for this year
                avg_map = dict(zip(year_data['id_ie'], year_data['score']))
                result[f'avg_{year}'] = result['id_ie'].map(avg_map)
            else:
                result[f'avg_{year}'] = np.nan

        # Rename id_ie to institution_id
        result = result.rename(columns={'id_ie': 'institution_id'})

        logger.info(f"Yearly averages calculated | area={area} institutions={len(result)} years_with_data={[y for y in YEARS if not result[f'avg_{y}'].isna().all()]}")

        return result

    def calculate_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate year-over-year trend = (avg_2023 - avg_2022) / avg_2022.

        Handles division by zero: if avg_2022 == 0, trend = 0.
        If either value is NULL, trend = NULL.

        Args:
            df: DataFrame with columns: avg_2022, avg_2023

        Returns:
            DataFrame with added 'trend' column
        """
        df = df.copy()

        logger.info("Calculating trend (YoY change)")

        # Create trend column
        df['trend'] = np.where(
            df['avg_2022'].isna() | df['avg_2023'].isna(),
            np.nan,
            np.where(
                df['avg_2022'] == 0,
                0.0,  # Avoid division by zero
                (df['avg_2023'] - df['avg_2022']) / df['avg_2022']
            )
        )

        valid_trends = df['trend'].notna().sum()
        logger.info(f"Trend calculation complete | valid_trends={valid_trends}")

        return df

    def calculate_variance(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate standard deviation across 2021, 2022, 2023 scores.

        Uses ddof=0 (population std dev) for consistency.
        If all values are NULL, variance = NULL.
        If only one year has data, variance = 0.

        Args:
            df: DataFrame with columns: avg_2021, avg_2022, avg_2023

        Returns:
            DataFrame with added 'variance' column
        """
        df = df.copy()

        logger.info("Calculating variance (std dev across years)")

        score_cols = ['avg_2021', 'avg_2022', 'avg_2023']
        available_cols = [c for c in score_cols if c in df.columns]

        if available_cols:
            # Row-wise std dev, skipping NaN values
            df['variance'] = df[available_cols].std(axis=1, ddof=0)
        else:
            df['variance'] = np.nan

        valid_variance = df['variance'].notna().sum()
        logger.info(f"Variance calculation complete | valid_variance={valid_variance}")

        return df

    # ==========================================
    # Normalization Methods
    # ==========================================

    def compute_normalization_params(self, df: pd.DataFrame,
                                     feature_cols: Optional[List[str]] = None) -> Dict[str, Tuple[float, float]]:
        """
        Compute min/max for each feature column.

        Args:
            df: DataFrame with raw feature columns
            feature_cols: List of column names to compute params for.
                         If None, uses default FEATURE_COLS.

        Returns:
            Dict mapping feature name to (min_value, max_value) tuple.
        """
        cols = feature_cols or FEATURE_COLS
        norm_params = {}

        logger.info(f"Computing normalization parameters | features={cols}")

        for col in cols:
            if col not in df.columns:
                logger.warning(f"Feature column '{col}' not found, skipping")
                continue

            valid_values = df[col].dropna()

            if valid_values.empty:
                logger.warning(f"No valid values for '{col}', setting min=max=0")
                norm_params[col] = (0.0, 0.0)
            else:
                min_val = float(valid_values.min())
                max_val = float(valid_values.max())
                norm_params[col] = (min_val, max_val)

                logger.debug(f"Normalization params for '{col}': min={min_val:.4f}, max={max_val:.4f}")

        return norm_params

    def normalize_features(self, df: pd.DataFrame,
                           norm_params: Dict[str, Tuple[float, float]],
                           norm_min: Optional[float] = None,
                           norm_max: Optional[float] = None) -> pd.DataFrame:
        """
        Apply min-max normalization: norm_min + (norm_max - norm_min) * (x - min) / (max - min)

        Default formula with norm_min=-1, norm_max=1:
            normalized = 2 * (x - min) / (max - min) - 1

        Handles edge case where min == max (all same values → normalized to midpoint).

        Args:
            df: DataFrame with raw feature columns
            norm_params: Dict of {feature: (min, max)} from compute_normalization_params
            norm_min: Target minimum for normalized range (default: self.norm_min)
            norm_max: Target maximum for normalized range (default: self.norm_max)

        Returns:
            DataFrame with normalized feature columns (overwrites raw values in-place columns)
        """
        df = df.copy()
        t_min = norm_min if norm_min is not None else self.norm_min
        t_max = norm_max if norm_max is not None else self.norm_max
        range_span = t_max - t_min

        logger.info("Normalizing features", norm_range=(t_min, t_max))

        for feature, (f_min, f_max) in norm_params.items():
            if feature not in df.columns:
                logger.warning(f"Feature '{feature}' not found in DataFrame, skipping normalization")
                continue

            span = f_max - f_min

            if span == 0:
                # All values are the same → map to midpoint of target range
                midpoint = (t_min + t_max) / 2.0
                df[feature] = np.where(df[feature].isna(), np.nan, midpoint)
                logger.debug(f"Feature '{feature}' has zero span, mapping to midpoint {midpoint}")
            else:
                # Standard normalization
                df[feature] = np.where(
                    df[feature].isna(),
                    np.nan,
                    t_min + range_span * (df[feature] - f_min) / span
                )

        return df

    # ==========================================
    # Target Generation
    # ==========================================

    def generate_target(self, df: pd.DataFrame,
                        meta_threshold: float) -> pd.DataFrame:
        """
        Generate binary target label.

        target = 1 if raw_avg_score_2023 > meta_threshold, else 0.
        If raw_avg_score_2023 is NULL, target = NULL.

        Args:
            df: DataFrame with 'raw_avg_score_2023' column
            meta_threshold: Score threshold for success/failure

        Returns:
            DataFrame with added 'target' column
        """
        df = df.copy()

        logger.info(f"Generating target labels | threshold={meta_threshold}")

        df['target'] = np.where(
            df['raw_avg_score_2023'].isna(),
            np.nan,
            np.where(df['raw_avg_score_2023'] > meta_threshold, 1, 0)
        ).astype('float64')  # Use float64 to allow NaN

        success_count = int((df['target'] == 1).sum())
        failure_count = int((df['target'] == 0).sum())
        logger.info(f"Target generation complete | success={success_count} failure={failure_count} null_target={int(df['target'].isna().sum())}")

        return df

    # ==========================================
    # Full Pipeline Methods
    # ==========================================

    def engineer_features_for_area(self, area: str,
                                    meta_overrides: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """
        Full feature engineering pipeline for one area.

        For year-specific areas (comunicación, matemática):
        - Creates separate rows for each year (2022, 2023)
        - Each row has features for that specific year

        For general areas (ccss, cyt):
        - Creates one row per institution with all years combined
        - Uses standard feature engineering

        Steps:
        1. Query fact_enla from BigQuery
        2. Calculate yearly averages
        3. For year-specific: create per-year rows
        4. Calculate trend and variance
        5. Compute normalization parameters
        6. Normalize features
        7. Generate target labels

        Args:
            area: Subject area (comunicación, matemática, ccss, cyt)
            meta_overrides: Optional dict of {institution_id: threshold} to override default threshold

        Returns:
            DataFrame with all features for the area (may have multiple rows per institution for year-specific areas)
        """
        logger.info(f"Starting feature engineering for area: {area}")

        # Step1: Query data
        bq_manager = self._get_bq_manager()

        # Debug: Check what's in fact_enla before querying
        try:
            debug_query = f"""
                SELECT area_academica, COUNT(*) as cnt
                FROM `{bq_manager.project_id}.{self.dataset_id}.fact_enla`
                GROUP BY area_academica
            """
            debug_df = bq_manager.query(debug_query)
            logger.info(f"Areas in fact_enla: {debug_df.to_dict('records')}")

            count_query = f"""
                SELECT COUNT(*) as total
                FROM `{bq_manager.project_id}.{self.dataset_id}.fact_enla`
            """
            total_df = bq_manager.query(count_query)
            logger.info(f"Total rows in fact_enla: {total_df['total'][0]}")
        except Exception as e:
            logger.warning(f"Debug query failed: {e}")

        query = f"""
            SELECT id_ie, nom_ie, year, area_academica, score
            FROM `{bq_manager.project_id}.{self.dataset_id}.fact_enla`
            WHERE area_academica = '{area}'
            AND year IN (2021, 2022, 2023)
        """
        logger.info("Querying fact_enla", area=area)
        raw_df = bq_manager.query(query)

        if raw_df.empty:
            logger.warning(f"No data found for area '{area}' in fact_enla")
            # Return empty DataFrame with expected columns instead of failing
            return pd.DataFrame(columns=['id_ie', 'nom_ie', 'avg_2021', 'avg_2022', 'avg_2023', 'trend', 'variance',
                                         'raw_avg_score_2023', 'raw_avg_score_2022', 'raw_avg_score_2021',
                                         'raw_trend', 'raw_variance', 'avg_score_2023', 'avg_score_2022',
                                         'avg_score_2021', 'area', 'target', 'feature_id', 'created_at', 'institution_id', 'meta_threshold', 'year'])

        # Step 2: Calculate yearly averages
        avg_df = self.calculate_yearly_averages(raw_df, area)

        if avg_df.empty:
            # Enhanced debug logging
            valid_scores_count = raw_df[raw_df['area_academica'] == area]['score'].notna().sum()
            logger.warning(
                f"No valid averages for area '{area}' - "
                f"Total rows for area: {len(raw_df[raw_df['area_academica'] == area])}, "
                f"Valid (non-NULL) scores: {valid_scores_count}, "
                f"Years available: {sorted(raw_df[raw_df['area_academica'] == area]['year'].unique().tolist())}"
            )
            # Return empty DataFrame with expected columns instead of failing
            return pd.DataFrame(columns=['id_ie', 'nom_ie', 'avg_2021', 'avg_2022', 'avg_2023', 'trend', 'variance',
                                         'raw_avg_score_2023', 'raw_avg_score_2022', 'raw_avg_score_2021',
                                         'raw_trend', 'raw_variance', 'avg_score_2023', 'avg_score_2022',
                                         'avg_score_2021', 'area', 'target', 'feature_id', 'created_at', 'institution_id', 'meta_threshold', 'year'])

        # Step 3: Handle year-specific vs general areas
        if area in YEAR_SPECIFIC_AREAS:
            # Create per-year rows for 2022 and 2023
            return self._engineer_features_per_year(avg_df, area, meta_overrides)
        else:
            # Standard feature engineering for general areas
            return self._engineer_features_general(avg_df, area, meta_overrides)

    def _engineer_features_per_year(self, avg_df: pd.DataFrame, area: str,
                                     meta_overrides: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """
        Feature engineering for year-specific areas (comunicación, matemática).

        Creates separate rows for each year (2022, 2023).
        Each row contains features for predicting that specific year.

        Args:
            avg_df: DataFrame with yearly averages
            area: Subject area
            meta_overrides: Optional threshold overrides

        Returns:
            DataFrame with per-year feature rows
        """
        logger.info(f"Engineering per-year features for area '{area}'")

        all_rows = []

        for year in PREDICTION_YEARS:
            year_df = avg_df.copy()
            year_df['avg_2021'] = year_df['avg_2021'].fillna(0.0)

            # For each year, we need to create features that would be available at prediction time
            # For predicting year Y, we use data from years < Y
            if year == 2022:
                # No 2021 data available, use avg_2022 as the target basis
                # (this makes 2022 the "train on known data" model)
                year_df['avg_score'] = year_df['avg_2022']
                year_df['raw_avg_score'] = year_df['avg_2022']
                # Trend: not applicable for first prediction year, set to 0
                year_df['trend'] = 0.0
                year_df['raw_trend'] = 0.0
                # Variance: not applicable for single year, set to 0
                year_df['variance'] = 0.0
                year_df['raw_variance'] = 0.0
            elif year == 2023:
                # To predict 2023, use 2022 data as feature, target = binary(avg_2023 > threshold)
                year_df['avg_score'] = year_df['avg_2023']
                year_df['raw_avg_score'] = year_df['avg_2023']
                # Trend: 2023 vs 2022
                year_df['trend'] = np.where(
                    year_df['avg_2022'].isna() | year_df['avg_2023'].isna(),
                    np.nan,
                    np.where(
                        year_df['avg_2022'] == 0,
                        0.0,
                        (year_df['avg_2023'] - year_df['avg_2022']) / year_df['avg_2022']
                    )
                )
                year_df['raw_trend'] = year_df['trend']
                # Variance: std dev of 2021, 2022, 2023
                score_cols = ['avg_2021', 'avg_2022', 'avg_2023']
                year_df['variance'] = year_df[score_cols].std(axis=1, ddof=0)
                year_df['raw_variance'] = year_df['variance']

            # Add year column
            year_df['year'] = year

            # Prepare raw columns
            year_df['raw_avg_score_2023'] = year_df['avg_2023']
            year_df['raw_avg_score_2022'] = year_df['avg_2022']
            year_df['raw_avg_score_2021'] = year_df['avg_2021']

            # Normalize features
            # For simplicity, normalize avg_score to [-1, 1]
            raw_feature_cols = ['avg_2021', 'avg_2022', 'avg_2023']
            norm_params = self.compute_normalization_params(year_df, raw_feature_cols)
            year_df = self.normalize_features(year_df, norm_params)

            # Rename to final column names
            year_df = year_df.rename(columns={
                'avg_2023': 'avg_score_2023',
                'avg_2022': 'avg_score_2022',
                'avg_2021': 'avg_score_2021',
            })

            # Generate target based on that year's score
            meta_threshold = self.target_threshold
            if meta_overrides:
                year_df['target'] = year_df.apply(
                    lambda row: 1 if row['raw_avg_score'] > meta_overrides.get(row['institution_id'], meta_threshold) else 0,
                    axis=1
                ).astype('float64')
            else:
                year_df['target'] = np.where(
                    year_df['raw_avg_score'].isna(),
                    np.nan,
                    np.where(year_df['raw_avg_score'] > meta_threshold, 1, 0)
                ).astype('float64')

            # Filter out rows with NaN target (no valid target data)
            before = len(year_df)
            year_df = year_df.dropna(subset=['target'])
            after = len(year_df)
            if after < before:
                logger.info(f"Dropped {before - after} rows with NaN target for year {year}")

            # Add area column
            year_df['area_academica'] = area

            all_rows.append(year_df)

        # Combine all years
        if not all_rows:
            logger.warning(f"No rows generated for area '{area}'")
            return pd.DataFrame()

        result_df = pd.concat(all_rows, ignore_index=True)
        logger.info(f"Per-year feature engineering complete for area '{area}' | total_rows={len(result_df)}")

        return result_df

    def _engineer_features_general(self, avg_df: pd.DataFrame, area: str,
                                     meta_overrides: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """
        Standard feature engineering for general areas (ccss, cyt).

        One row per institution with all years combined.

        Args:
            avg_df: DataFrame with yearly averages
            area: Subject area
            meta_overrides: Optional threshold overrides

        Returns:
            DataFrame with features
        """
        logger.info(f"Engineering general features for area '{area}'")

        # Calculate trend
        avg_df = self.calculate_trend(avg_df)

        # Calculate variance
        avg_df = self.calculate_variance(avg_df)

        # Prepare raw columns for output (copy before normalization)
        raw_cols = {
            'raw_avg_score_2023': 'avg_2023',
            'raw_avg_score_2022': 'avg_2022',
            'raw_avg_score_2021': 'avg_2021',
            'raw_trend': 'trend',
            'raw_variance': 'variance',
        }
        for raw_col, src_col in raw_cols.items():
            if src_col in avg_df.columns:
                avg_df[raw_col] = avg_df[src_col].copy()
            else:
                avg_df[raw_col] = np.nan

        # Compute normalization parameters
        raw_feature_cols = ['avg_2023', 'avg_2022', 'avg_2021', 'trend', 'variance']
        norm_params = self.compute_normalization_params(avg_df, raw_feature_cols)

        # Store for later BigQuery insert
        self._norm_params_store[area] = norm_params

        # Normalize features
        avg_df = self.normalize_features(avg_df, norm_params)

        # Rename normalized columns to final names
        col_rename = {
            'avg_2023': 'avg_score_2023',
            'avg_2022': 'avg_score_2022',
            'avg_2021': 'avg_score_2021',
        }
        avg_df = avg_df.rename(columns=col_rename)

        # Generate target labels
        meta_threshold = self.target_threshold
        avg_df = self.generate_target(avg_df, meta_threshold)

        # Add area_academica column (academic area, NOT geographic zone)
        avg_df['area_academica'] = area

        # year is NULL for general areas
        avg_df['year'] = np.nan

        # Filter out rows with NaN target
        before = len(avg_df)
        avg_df = avg_df.dropna(subset=['target'])
        after = len(avg_df)
        if after < before:
            logger.info(f"Dropped {before - after} rows with NaN target for general area '{area}'")

        logger.info(f"General feature engineering complete for area '{area}' | institutions={len(avg_df)}")

        return avg_df

    def engineer_all_areas(self, meta_overrides: Optional[Dict[str, float]] = None) -> Dict[str, pd.DataFrame]:
        """
        Run feature engineering for all available areas.

        For year-specific areas (comunicación, matemática):
        - Creates per-year rows (2022, 2023)

        For general areas (ccss, cyt):
        - Creates one row per institution

        Uses DYNAMIC area discovery from fact_enla table to handle
        any accent variations (e.g., 'comunicación' vs 'comunicacion').

        Args:
            meta_overrides: Optional dict of {institution_id: threshold} overrides

        Returns:
            Dict mapping area name to DataFrame with features
        """
        results = {}
        errors = []

        logger.info("Starting feature engineering for all areas")

        # DYNAMIC AREA DISCOVERY: Query areas from database
        # This avoids hardcoding and handles accent variations
        try:
            bq_manager = self._get_bq_manager()
            check_query = f"""
                SELECT area_academica, COUNT(*) as cnt
                FROM `{bq_manager.project_id}.{self.dataset_id}.fact_enla`
                GROUP BY area_academica
            """
            available_areas_df = bq_manager.query(check_query)
            available_areas = available_areas_df['area_academica'].tolist() if not available_areas_df.empty else []
            logger.info(f"Areas found in fact_enla: {available_areas}")

            # Use areas from database (dynamic discovery)
            areas_to_process = available_areas

            if not areas_to_process:
                logger.warning("No areas found in fact_enla! Falling back to AREAS constant.")
                areas_to_process = AREAS

        except Exception as e:
            logger.warning(f"Could not query areas from database: {e}. Using AREAS constant.")
            areas_to_process = AREAS

        logger.info(f"Processing areas: {areas_to_process}")

        for area in areas_to_process:
            try:
                df = self.engineer_features_for_area(area, meta_overrides)
                results[area] = df
                logger.info(f"Area '{area}' processed: {len(df)} rows")
            except Exception as e:
                error_msg = f"Error processing area '{area}': {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
                results[area] = pd.DataFrame()

        logger.info(f"All areas processed | areas_with_data={sum(1 for df in results.values() if not df.empty)} errors={len(errors)}")

        return results

    # ==========================================
    # BigQuery Loading Methods
    # ==========================================

    def save_normalization_params(self, norm_params: Dict[str, Tuple[float, float]],
                                  area: str) -> List[Dict]:
        """
        Format normalization params for BigQuery insert.

        Args:
            norm_params: Dict of {feature_name: (min_value, max_value)}
            area: Subject area

        Returns:
            List of dicts ready for BigQuery insertion
        """
        records = []
        created_at = datetime.now(timezone.utc)

        for feature_name, (min_val, max_val) in norm_params.items():
            records.append({
                'param_id': str(uuid.uuid4()),
                'area_academica': area,  # NOTE: BigQuery schema expects 'area_academica', not 'area'
                'feature_name': feature_name,
                'min_value': min_val,
                'max_value': max_val,
                'created_at': created_at,
            })

        logger.info(f"Prepared {len(records)} normalization parameter records for area '{area}'")
        return records

    def run_full_pipeline(self, meta_overrides: Optional[Dict[str, float]] = None) -> FeaturePipelineResult:
        """
        Complete feature engineering pipeline.

        1. Engineer features for all areas
        2. Combine into single DataFrame
        3. Load enla_callao_features to BigQuery
        4. Load enla_feature_normalization_params to BigQuery
        5. Return summary

        Args:
            meta_overrides: Optional dict of {institution_id: threshold} overrides

        Returns:
            FeaturePipelineResult with execution summary
        """
        result = FeaturePipelineResult(status="running")
        all_norm_records = []

        try:
            logger.info("=" * 60)
            logger.info("Starting Full Feature Engineering Pipeline")
            logger.info("=" * 60)

            # Step 1: Engineer features for all areas
            area_results = self.engineer_all_areas(meta_overrides)

            # Step 2: Combine all areas into single DataFrame
            all_frames = []
            total_institutions = 0

            for area, df in area_results.items():
                if df.empty:
                    logger.warning(f"No data for area '{area}' - skipping")
                    continue

                # Add feature_id and created_at
                df = df.copy()
                df['feature_id'] = [str(uuid.uuid4()) for _ in range(len(df))]
                df['created_at'] = datetime.now(timezone.utc)

                # Ensure correct column order
                # NOTE: BigQuery schema expects 'area_academica', not 'area'
                expected_cols = [
                    'feature_id', 'area_academica', 'institution_id', 'nom_ie',
                    'year',
                    'avg_score_2023', 'avg_score_2022', 'avg_score_2021',
                    'trend', 'variance',
                    'target',
                    'raw_avg_score_2023', 'raw_avg_score_2022', 'raw_avg_score_2021',
                    'raw_trend', 'raw_variance',
                    'meta_threshold', 'created_at',
                ]

                # Add meta_threshold if not present
                if 'meta_threshold' not in df.columns:
                    df['meta_threshold'] = self.target_threshold

                # Only include columns that exist
                available_cols = [c for c in expected_cols if c in df.columns]
                df = df[available_cols]

                all_frames.append(df)
                total_institutions += len(df)

                # Step 3: Collect normalization params
                if area in self._norm_params_store:
                    norm_records = self.save_normalization_params(
                        self._norm_params_store[area], area
                    )
                    all_norm_records.extend(norm_records)

            if not all_frames:
                result.status = "failed"
                result.errors.append("No features generated for any area - fact_enla may be empty or have no matching data")
                logger.error("Pipeline failed: No features generated for any area")
                return result

            # Combine all areas
            combined_df = pd.concat(all_frames, ignore_index=True)

            result.areas_processed = len([a for a, df in area_results.items() if not df.empty])
            result.total_features = total_institutions

            logger.info(f"Combined features: {len(combined_df)} rows across {result.areas_processed} areas")

            # Step 4: Load to BigQuery (skip if empty)
            if combined_df.empty:
                logger.warning("No features to load - combined DataFrame is empty, skipping BigQuery load")
                result.status = "partial_success"
                result.errors.append("No features generated - DataFrame is empty (likely no 2022 data in fact_enla)")
                return result

            bq_manager = self._get_bq_manager()
            bq_manager.connect()
            bq_manager.create_dataset(self.dataset_id, location=settings.GCP_LOCATION)

            # Load features table
            logger.info("Loading enla_callao_features to BigQuery")
            feature_stats = bq_manager.load_table_from_dataframe(
                self.dataset_id, 'enla_callao_features',
                combined_df, write_disposition='WRITE_TRUNCATE',
                schema=FEATURES_SCHEMA
            )
            logger.info(f"Features table loaded | rows={feature_stats.get('rows_loaded')}")

            # Load normalization params table
            if all_norm_records:
                norm_df = pd.DataFrame(all_norm_records)
                logger.info("Loading enla_feature_normalization_params to BigQuery")
                norm_stats = bq_manager.load_table_from_dataframe(
                    self.dataset_id, 'enla_feature_normalization_params',
                    norm_df, write_disposition='WRITE_TRUNCATE',
                    schema=NORM_PARAMS_SCHEMA
                )
                result.normalization_params_loaded = len(all_norm_records)
                logger.info(f"Normalization params loaded | rows={norm_stats.get('rows_loaded')}")

            result.status = "success"

            logger.info(f"Feature Engineering Pipeline completed successfully | areas_processed={result.areas_processed} total_features={result.total_features} norm_params_loaded={result.normalization_params_loaded}")

        except BigQueryConnectionError as e:
            error_msg = f"BigQuery connection error: {str(e)}"
            result.errors.append(error_msg)
            result.status = "failed"
            logger.error(error_msg)

        except FeatureEngineeringError as e:
            error_msg = f"Feature engineering error: {str(e)}"
            result.errors.append(error_msg)
            result.status = "failed"
            logger.error(error_msg)

        except Exception as e:
            error_msg = f"Unexpected pipeline error: {str(e)}"
            result.errors.append(error_msg)
            result.status = "failed"
            logger.error(error_msg, exc_info=True)

        finally:
            try:
                if self.bq_manager:
                    self.bq_manager.disconnect()
            except Exception as e:
                logger.warning("Error during connection cleanup", error=str(e))

        return result


# ==========================================
# Convenience Function
# ==========================================

def run_feature_pipeline(bigquery_client: Optional[BigQueryClientManager] = None,
                         meta_overrides: Optional[Dict[str, float]] = None) -> FeaturePipelineResult:
    """
    Run the complete feature engineering pipeline.

    Args:
        bigquery_client: BigQueryClientManager instance (optional)
        meta_overrides: Optional dict of {institution_id: threshold} overrides

    Returns:
        FeaturePipelineResult with execution summary
    """
    engineer = FeatureEngineer(bigquery_client=bigquery_client,
                                target_threshold=settings.TARGET_SCORE_THRESHOLD)
    return engineer.run_full_pipeline(meta_overrides=meta_overrides)
