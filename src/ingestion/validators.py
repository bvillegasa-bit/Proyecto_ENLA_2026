"""Data validation framework for ENLA ingestion."""

from typing import List, Tuple, Dict, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
from src.logging.setup import get_logger

logger = get_logger('validation')


@dataclass
class ValidationReport:
    """Report of validation results."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    statistics: Dict[str, Any]


class ENLAValidator:
    """Validator for ENLA data."""
    
    REQUIRED_COLUMNS = {
        'id_ie', 'id_seccion', 'nom_ie', 'nom_dre',
        'ano_evaluacion', 'grado_evaluacion',
        'cor_est_comunicacion', 'cor_est_matematica',
        'cor_est_ccss', 'cor_est_cyt'
    }
    
    SCORE_COLUMNS = [
        'cor_est_comunicacion', 'cor_est_matematica',
        'cor_est_ccss', 'cor_est_cyt'
    ]
    
    def __init__(self):
        """Initialize validator."""
        self.report = None
    
    def validate(self, df: pd.DataFrame, region: str = 'CALLAO',
                grado: int = 2) -> ValidationReport:
        """
        Validate DataFrame against ENLA requirements.
        
        Args:
            df: DataFrame to validate
            region: Expected region
            grado: Expected grade
        
        Returns:
            ValidationReport with detailed results
        """
        errors = []
        warnings = []
        statistics = {}
        
        # Step 1: Check required columns
        errors.extend(self._validate_required_columns(df))
        if errors:
            self.report = ValidationReport(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                statistics=statistics
            )
            return self.report
        
        # Step 2: Check data types
        errors.extend(self._validate_data_types(df))
        
        # Step 3: Check score ranges
        errors.extend(self._validate_score_ranges(df))
        
        # Step 4: Check for nulls
        warnings.extend(self._validate_no_nulls(df))
        
        # Step 5: Check duplicates
        warnings.extend(self._validate_duplicates(df))
        
        # Step 6: Compute statistics
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
        """Check that all required columns exist."""
        missing = self.REQUIRED_COLUMNS - set(df.columns)
        if missing:
            msg = f"Missing required columns: {', '.join(sorted(missing))}"
            logger.error(msg)
            return [msg]
        return []
    
    def _validate_data_types(self, df: pd.DataFrame) -> List[str]:
        """Verify that score columns are numeric."""
        errors = []
        for col in self.SCORE_COLUMNS:
            if col in df.columns:
                # Try to convert to numeric
                try:
                    pd.to_numeric(df[col], errors='raise')
                except (ValueError, TypeError):
                    msg = f"Column '{col}' contains non-numeric values"
                    logger.error(f"{msg} | column={col}")
                    errors.append(msg)
        return errors
    
    def _validate_score_ranges(self, df: pd.DataFrame) -> List[str]:
        """Ensure all scores are in [0, 100]."""
        errors = []
        for col in self.SCORE_COLUMNS:
            if col in df.columns:
                # Convert to numeric
                scores = pd.to_numeric(df[col], errors='coerce')
                
                # Check ranges
                invalid = ((scores < 0) | (scores > 100))
                if invalid.any():
                    invalid_count = invalid.sum()
                    msg = f"Column '{col}': {invalid_count} values out of range [0, 100]"
                    logger.error(f"{msg} | column={col} count={invalid_count}")
                    errors.append(msg)
        return errors
    
    def _validate_no_nulls(self, df: pd.DataFrame) -> List[str]:
        """Check critical columns for NULL values."""
        warnings = []
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
        """Identify duplicate rows based on key columns."""
        warnings = []
        key_cols = ['id_ie', 'id_seccion', 'ano_evaluacion']
        
        if all(col in df.columns for col in key_cols):
            duplicates = df.duplicated(subset=key_cols, keep=False)
            if duplicates.any():
                dup_count = duplicates.sum()
                msg = f"Found {dup_count} duplicate rows (by id_ie + id_seccion + ano_evaluacion)"
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
        for col in self.REQUIRED_COLUMNS:
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
