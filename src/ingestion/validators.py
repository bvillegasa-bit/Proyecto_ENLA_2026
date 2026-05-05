"""Data validation framework for ENLA ingestion."""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass
from src.logging.setup import get_logger
from src.ingestion.column_mapping import UNIFIED_SCHEMA

logger = get_logger('validation')


@dataclass
class ValidationReport:
    """Report of validation results."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    statistics: Dict[str, Any]


class ENLAValidator:
    """Validator for ENLA data.

    Works with STANDARDIZED column names (snake_case) after column_mapping
    has been applied in the ingestion pipeline.
    """

    # Core columns that should be present in ALL years (standardized names)
    CORE_COLUMNS = {
        'id_ie', 'id_seccion', 'nom_ie', 'nom_dre',
        'ano_evaluacion', 'grado_evaluacion',
        'cor_est', 'area',  # cor_est = student ID, area = geographic zone
    }

    # Numeric assessment columns (scores and weights)
    NUMERIC_COLUMNS = [
        'medida_lectura', 'peso_lectura',
        'medida_matematica', 'peso_matematica',
        'medida_ciencias', 'peso_ciencias',
    ]

    # Categorical performance group columns (letters A/B/C/D/E)
    GRUPO_COLUMNS = [
        'grupo_lectura', 'grupo_matematica', 'grupo_ciencias',
    ]

    # All assessment columns (for checking presence)
    SCORE_COLUMNS = NUMERIC_COLUMNS + GRUPO_COLUMNS

    def __init__(self):
        """Initialize validator."""
        self.report = None

    def validate(self, df: pd.DataFrame, region: str = 'CALLAO',
                 grado: int = 2) -> ValidationReport:
        """
        Validate DataFrame against ENLA requirements.

        Assumes columns have been standardized via column_mapping.py

        Args:
            df: DataFrame to validate (with standardized column names)
            region: Expected region
            grado: Expected grade

        Returns:
            ValidationReport with detailed results
        """
        errors = []
        warnings = []
        statistics = {}

        # Step1: Check required columns (UNIFIED_SCHEMA fields)
        errors.extend(self._validate_required_columns(df))

        # Step2: Check data types for score columns
        errors.extend(self._validate_data_types(df))

        # Step3: Check score ranges
        errors.extend(self._validate_score_ranges(df))

        # Step4: Check for nulls in critical columns
        warnings.extend(self._validate_no_nulls(df))

        # Step5: Check duplicates
        warnings.extend(self._validate_duplicates(df))

        # Step6: Compute statistics
        statistics = self._compute_statistics(df, errors, warnings)

        is_valid = len(errors) == 0

        self.report = ValidationReport(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            statistics=statistics
        )

        logger.info(f"Validation completed | is_valid={is_valid} error_count={len(errors)} warning_count={len(warnings)}")

        return self.report

    def _validate_required_columns(self, df: pd.DataFrame) -> List[str]:
        """Check that core required columns exist (score columns are standardized)."""
        missing = self.CORE_COLUMNS - set(df.columns)
        if missing:
            msg = f"Missing required columns: {', '.join(sorted(missing))}"
            logger.error(msg)
            return [msg]

        # Check that at least one assessment score column exists
        score_cols_present = [col for col in self.SCORE_COLUMNS if col in df.columns]
        if not score_cols_present:
            msg = f"No assessment score columns found! Expected columns like: {self.SCORE_COLUMNS[:3]}"
            logger.error(msg)
            return [msg]

        return []

    def _validate_data_types(self, df: pd.DataFrame) -> List[str]:
        """Verify that numeric columns are numeric, coercing non-numeric to NaN. Validate grupo columns as categorical."""
        errors = []
        # Process numeric columns (medida_*, peso_*)
        for col in self.NUMERIC_COLUMNS:
            if col in df.columns:
                # Convert to numeric, coercing errors to NaN
                numeric_col = pd.to_numeric(df[col], errors='coerce')
                na_count = numeric_col.isna().sum()
                if na_count > 0 and na_count < len(df):
                    # Some non-numeric values, coerced to NaN
                    df[col] = numeric_col
                    msg = f"Column '{col}' contains {na_count} non-numeric values (converted to NaN)"
                    logger.warning(f"{msg} | column={col} na_count={na_count}")
                elif na_count == len(df):
                    # All values non-numeric
                    msg = f"Column '{col}' contains only non-numeric values"
                    logger.error(f"{msg} | column={col}")
                    errors.append(msg)
        # Validate grupo columns (categorical: A/B/C/D/E or None)
        valid_grupo_values = {'A', 'B', 'C', 'D', 'E', None}
        for col in self.GRUPO_COLUMNS:
            if col in df.columns:
                invalid_mask = ~df[col].isin(valid_grupo_values)
                if invalid_mask.any():
                    invalid_count = invalid_mask.sum()
                    msg = f"Column '{col}': {invalid_count} invalid values (expected A/B/C/D/E or None)"
                    logger.warning(f"{msg} | column={col} count={invalid_count}")
        return errors

    def _validate_score_ranges(self, df: pd.DataFrame) -> List[str]:
        """Ensure medida scores are in [0, 1000]. grupo and peso columns are not scored on this scale."""
        errors = []
        # Only check medida_* columns (0-1000 scale)
        medida_cols = [col for col in df.columns if col.startswith('medida_')]
        for col in medida_cols:
            # Convert to numeric
            scores = pd.to_numeric(df[col], errors='coerce')

            # Check ranges - ENLA scores are 0-1000 scale
            invalid = ((scores < 0) | (scores > 1000))
            if invalid.any():
                invalid_count = invalid.sum()
                msg = f"Column '{col}': {invalid_count} values out of range [0, 1000]"
                logger.error(f"{msg} | column={col} count={invalid_count}")
                errors.append(msg)
        return errors

    def _validate_no_nulls(self, df: pd.DataFrame) -> List[str]:
        """Check critical columns for NULL values."""
        warnings = []
        # Core critical columns + assessment score columns
        critical_cols = ['id_ie', 'id_seccion', 'ano_evaluacion'] + self.SCORE_COLUMNS

        for col in critical_cols:
            if col in df.columns:
                null_count = df[col].isna().sum()
                if null_count > 0:
                    msg = f"Column '{col}': {null_count} NULL values found"
                    logger.warning(f"{msg} | column={col} count={null_count}")
                    warnings.append(msg)
        return warnings

    def _validate_duplicates(self, df: pd.DataFrame) -> List[str]:
        """Identify duplicate rows based on student unique key (id_ie + id_seccion + ano_evaluacion + cor_est)."""
        warnings = []
        # Match UPSERT_KEY in ingest_enla.py
        key_cols = ['id_ie', 'id_seccion', 'ano_evaluacion', 'cor_est']

        if all(col in df.columns for col in key_cols):
            duplicates = df.duplicated(subset=key_cols, keep=False)
            if duplicates.any():
                dup_count = duplicates.sum()
                msg = f"Found {dup_count} duplicate rows (by {', '.join(key_cols)})"
                logger.warning(f"{msg} | duplicate_count={dup_count}")
                warnings.append(msg)
        return warnings

    def _compute_statistics(self, df: pd.DataFrame, errors: List[str],
                            warnings: List[str]) -> Dict[str, Any]:
        """Compute summary statistics."""
        stats = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'error_count': len(errors),
            'warning_count': len(warnings),
        }

        # Null coverage (%)
        null_coverage = {}
        for col in self.CORE_COLUMNS:
            if col in df.columns:
                null_pct = (df[col].isna().sum() / len(df)) * 100
                null_coverage[col] = round(null_pct, 2)
        stats['null_coverage_percent'] = null_coverage

        # Score statistics
        score_stats = {}
        for col in self.SCORE_COLUMNS:
            if col in df.columns:
                scores = pd.to_numeric(df[col], errors='coerce')
                score_stats[col] = {
                    'min': round(scores.min(), 2),
                    'max': round(scores.max(), 2),
                    'mean': round(scores.mean(), 2),
                    'std': round(scores.std(), 2),
                }
        stats['score_statistics'] = score_stats

        return stats


def validate_dataframe(df: pd.DataFrame, region: str = 'CALLAO',
                      grado: int = 2) -> ValidationReport:
    """Convenience function to validate a DataFrame."""
    validator = ENLAValidator()
    return validator.validate(df, region=region, grado=grado)
