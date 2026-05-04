"""Data validation framework for ENLA ingestion."""

import re
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
    """Validator for ENLA data.
    
    Uses DYNAMIC column discovery via regex patterns to handle
    different years with DIFFERENT column naming conventions:
    - 2023: M500_EM_2S_2023_CT, grupo_EM_2S_2023_CT, peso_CT
    - 2022: medida500_L, grupo_L, pes_o_L
    - etc.
    """
    
    # Core columns that should be present in ALL years
    CORE_COLUMNS = {
        'ID_IE', 'ID_SECCION', 'nom_ie', 'nom_dre',
        'ano_evaluacion',  # grado_evaluacion optional - added with default 2 if missing
        'cor_est', 'area',  # cor_est = student ID, area = geographic zone
    }
    
    # Academic area patterns for DYNAMIC column discovery
    # Column names CHANGE per year - use regex patterns to find them
    # NOTE: Keys use ACCENTED names as per user requirement: "comunicación y matemática" (WITH accents!)
    AREA_PATTERNS = {
        'comunicación': {
            'measure_patterns': [r'M500.*(CT|L)$', r'M500.*(CT|L)[^_]*$', r'medida500.*(CT|L)$'],
            'group_patterns': [r'grupo.*(CT|L)$', r'grupo.*(CT|L)[^_]*$'],
            'weight_patterns': [r'peso.*(CT|L)$', r'pes_o.*(CT|L)$'],
            'required': True,  # OBLIGATORY area (user: "comunicación... son obligatorias")
        },
        'matemática': {
            'measure_patterns': [r'M500.*(MA|M)$', r'M500.*(MA|M)[^_]*$', r'medida500.*(MA|M)$'],
            'group_patterns': [r'grupo.*(MA|M)$', r'grupo.*(MA|M)[^_]*$'],
            'weight_patterns': [r'peso.*(MA|M)$', r'pes_o.*(MA|M)$'],
            'required': True,  # OBLIGATORY area (user: "matemática... son obligatorias")
        },
        'ccss': {
            'measure_patterns': [r'M500.*(CS|CN)$', r'M500.*(CS|CN)[^_]*$', r'medida500.*(CS|CN)$'],
            'group_patterns': [r'grupo.*(CS|CN)$', r'grupo.*(CS|CN)[^_]*$'],
            'weight_patterns': [r'peso.*(CS|CN)$', r'pes_o.*(CS|CN)$'],
            'required': False,  # Optional area
        },
        'cyt': {
            'measure_patterns': [r'M500.*CY$', r'M500.*CY[^_]*$'],
            'group_patterns': [r'grupo.*CY$', r'grupo.*CY[^_]*$'],
            'weight_patterns': [r'peso.*CY$', r'pes_o.*CY$'],
            'required': False,  # Optional area
        },
    }
    
    def __init__(self):
        """Initialize validator."""
        self.report = None
        self._discovered_score_columns = []  # Will be populated during validation
    
    def validate(self, df: pd.DataFrame, region: str = 'CALLAO',
                 grado: int = 2) -> ValidationReport:
        """
        Validate DataFrame against ENLA requirements.
        
        Uses DYNAMIC column discovery - does NOT require hardcoded column names.
        
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
        
        # Step 0: Discover actual column names in this year's data
        self._discover_columns(df)
        logger.info(f"Discovered score columns: {self._discovered_score_columns}")
        
        # Step1: Check required columns (only core columns - score columns are dynamic)
        errors.extend(self._validate_required_columns(df))
        
        # Step2: Check data types
        errors.extend(self._validate_data_types(df))
        
        # Step3: Check score ranges
        errors.extend(self._validate_score_ranges(df))
        
        # Step4: Check for nulls
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
    
    def _discover_columns(self, df: pd.DataFrame):
        """Discover actual column names using regex patterns."""
        self._discovered_score_columns = []
        
        for area_name, patterns in self.AREA_PATTERNS.items():
            # Search for measure column (score)
            for col in df.columns:
                found = False
                for pattern in patterns['measure_patterns']:
                    if re.search(pattern, col, re.IGNORECASE):
                        self._discovered_score_columns.append(col)
                        logger.info(f"Found score column for '{area_name}': {col}")
                        found = True
                        break
                if found:
                    break
    
    def _validate_required_columns(self, df: pd.DataFrame) -> List[str]:
        """Check that core required columns exist (score columns are dynamic)."""
        missing = self.CORE_COLUMNS - set(df.columns)
        if missing:
            msg = f"Missing required columns: {', '.join(sorted(missing))}"
            logger.error(msg)
            return [msg]
        
        # Also check that at least one score column was found
        if not self._discovered_score_columns:
            msg = f"No score columns found! Available columns: {list(df.columns)[:20]}"
            logger.error(msg)
            return [msg]
        
        return []
    
    def _validate_data_types(self, df: pd.DataFrame) -> List[str]:
        """Verify that score columns are numeric, coercing non-numeric to NaN."""
        errors = []
        warnings = []
        for col in self._discovered_score_columns:
            if col in df.columns:
                # Convert to numeric, coercing errors to NaN
                original = df[col].copy()
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
        return errors
    
    def _validate_score_ranges(self, df: pd.DataFrame) -> List[str]:
        """Ensure all scores are in [0, 100]."""
        errors = []
        for col in self._discovered_score_columns:
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
        # Core critical columns + discovered score columns
        critical_cols = ['ID_IE', 'ID_SECCION', 'ano_evaluacion'] + self._discovered_score_columns
        
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
        key_cols = ['ID_IE', 'ID_SECCION', 'ano_evaluacion']
        
        if all(col in df.columns for col in key_cols):
            duplicates = df.duplicated(subset=key_cols, keep=False)
            if duplicates.any():
                dup_count = duplicates.sum()
                msg = f"Found {dup_count} duplicate rows (by ID_IE + ID_SECCION + ano_evaluacion)"
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
        
        # Score statistics (using discovered columns)
        score_stats = {}
        for col in self._discovered_score_columns:
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
