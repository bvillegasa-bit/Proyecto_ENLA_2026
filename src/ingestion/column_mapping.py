"""
Column mapping module for standardizing ENLA data column names.

This module provides:
- UNIFIED_SCHEMA: 33 standardized field names (snake_case)
- RENAME_2022 / RENAME_2023: Dictionaries to map original Excel column names to standardized names
- detect_file_format(): Function to detect the year/format of an Excel file
"""

import re
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# 1. UNIFIED SCHEMA - 33 standardized fields (snake_case)
# ---------------------------------------------------------------------------

# Core/ID (8 fields)
CORE_ID_FIELDS = [
    'ano_evaluacion',      # Year (2022, 2023, etc.)
    'grado_evaluacion',    # Grade (2 = 2do grado)
    'nivel',               # Education level (Secundaria)
    'id_estudiante',       # Student ID (from original data if available)
    'cor_est',             # Student correlation ID
    'id_ie',               # School ID
    'id_seccion',          # Section ID
    'seccion',             # Section name/code
]

# Geographic (9 fields)
GEOGRAPHIC_FIELDS = [
    'cod_dre',             # DRE code
    'nom_dre',             # DRE name
    'cod_ugel',            # UGEL code
    'nom_ugel',            # UGEL name
    'codgeo',              # Geographic code
    'departamento',        # Department
    'provincia',           # Province
    'distrito',            # District
    'estrato_dre',         # DRE stratum
]

# School (3 fields)
SCHOOL_FIELDS = [
    'gestion2',            # Management type (Publica/Privada)
    'area',                # Geographic area (Rural/Urban)
    'caracteristica2',     # School characteristic
]

# Student (4 fields)
STUDENT_FIELDS = [
    'sexo',                # Gender
    'lengua_materna',      # Native language
    'ise',                 # Socioeconomic index (category)
    'n_ise',               # ISE (numeric)
]

# Assessment: Lectura/Comunicación (3 fields)
LECTURA_FIELDS = [
    'medida_lectura',      # Score (0-1000)
    'grupo_lectura',       # Performance group
    'peso_lectura',        # Weight
]

# Assessment: Matemática (3 fields)
MATEMATICA_FIELDS = [
    'medida_matematica',   # Score (0-1000)
    'grupo_matematica',    # Performance group
    'peso_matematica',     # Weight
]

# Assessment: Ciencias (3 fields)
CIENCIAS_FIELDS = [
    'medida_ciencias',     # Score (0-1000)
    'grupo_ciencias',      # Performance group
    'peso_ciencias',       # Weight
]

# Combined: 33 standardized fields
UNIFIED_SCHEMA = (
    CORE_ID_FIELDS +
    GEOGRAPHIC_FIELDS +
    SCHOOL_FIELDS +
    STUDENT_FIELDS +
    LECTURA_FIELDS +
    MATEMATICA_FIELDS +
    CIENCIAS_FIELDS
)

# 2022-only fields (not in UNIFIED_SCHEMA, kept as additional fields)
EXTRA_2022_FIELDS = [
    'pikie_lectura',       # ITE cutoff score - Lectura
    'prob_sec_lectura',    # Probability of achievement - Lectura
    'pikie_matematica',    # ITE cutoff score - Matemática
    'prob_sec_matematica', # Probability of achievement - Matemática
    'pikie_ciencias',      # ITE cutoff score - Ciencias
    'prob_sec_ciencias',   # Probability of achievement - Ciencias
]

__all__ = [
    'UNIFIED_SCHEMA', 'RENAME_2022', 'RENAME_2023', 'YEAR_RENAME_DICTS',
    'EXTRA_2022_FIELDS', 'detect_file_format', 'extract_year_from_filename',
    'apply_column_renaming',
]


# ---------------------------------------------------------------------------
# 2. RENAME DICTIONARIES
# ---------------------------------------------------------------------------

# 2023 rename dictionary (maps original Excel columns → standardized names)
RENAME_2023 = {
    # Core/ID
    'ID_IE': 'id_ie',
    'ID_SECCION': 'id_seccion',
    'cor_est': 'cor_est',  # already standardized
    'grado_evaluacion': 'grado_evaluacion',  # already present
    'nivel': 'nivel',  # already present
    'seccion': 'seccion',  # already present
    'Año': 'ano_evaluacion',  # Spanish ñ → standard name

    # Geographic
    'cod_DRE': 'cod_dre',
    'nom_DRE': 'nom_dre',
    'nom.DRE': 'nom_dre',
    'cod_UGEL': 'cod_ugel',
    'nom_UGEL': 'nom_ugel',
    'Departamento': 'departamento',
    'Provincia': 'provincia',
    'Distrito': 'distrito',
    'Estrato_DRE': 'estrato_dre',
    'codgeo': 'codgeo',  # already present

    # School
    'Gestion2': 'gestion2',
    'Area': 'area',
    'Caracteristica2': 'caracteristica2',

    # Student
    'Sexo': 'sexo',
    'Lengua_materna': 'lengua_materna',
    'ISE': 'ise',
    'N_ISE': 'n_ise',

    # Assessment: Lectura (2023 uses CT = Comunicación)
    'M500_EM_2S_2023_CT': 'medida_lectura',
    'grupo_EM_2S_2023_CT': 'grupo_lectura',
    'peso_CT': 'peso_lectura',

    # Assessment: Matemática (2023 uses MA)
    'M500_EM_2S_2023_MA': 'medida_matematica',
    'grupo_EM_2S_2023_MA': 'grupo_matematica',
    'peso_MA': 'peso_matematica',

    # Assessment: Ciencias (2023 uses CS)
    'M500_EM_2S_2023_CS': 'medida_ciencias',
    'grupo_EM_2S_2023_CS': 'grupo_ciencias',
    'peso_CS': 'peso_ciencias',
}

# 2022 rename dictionary
RENAME_2022 = {
    # Core/ID
    'Año': 'ano_evaluacion',
    'Grado': 'grado_evaluacion',
    'Nivel': 'nivel',
    'ID_estudiante': 'id_estudiante',
    'ID_IE': 'id_ie',
    'ID_seccion': 'id_seccion',
    'Seccion': 'seccion',
    'cor_est': 'cor_est',  # already present

    # Geographic
    'cod_DRE': 'cod_dre',
    'nom_DRE': 'nom_dre',
    'nom.DRE': 'nom_dre',
    'cod_UGEL': 'cod_ugel',
    'nom_UGEL': 'nom_ugel',
    'Departamento': 'departamento',
    'Provincia': 'provincia',
    'Distrito': 'distrito',
    'Estrato_DRE': 'estrato_dre',
    'codgeo': 'codgeo',  # already present

    # School
    'Gestion2': 'gestion2',
    'Area': 'area',
    'Caracteristica2': 'caracteristica2',

    # Student
    'Sexo': 'sexo',
    'Lengua_materna': 'lengua_materna',
    'ISE': 'ise',
    'N_ISE': 'n_ise',

    # Assessment: Lectura (2022 uses L = Lectura)
    'M500_L': 'medida_lectura',
    'grupo_L': 'grupo_lectura',
    'peso_L': 'peso_lectura',

    # Assessment: Matemática (2022 uses M)
    'M500_M': 'medida_matematica',
    'grupo_M': 'grupo_matematica',
    'peso_M': 'peso_matematica',

    # Assessment: Ciencias (2022 uses CN = Ciencias Naturales)
    'M500_CN': 'medida_ciencias',
    'grupo_CN': 'grupo_ciencias',
    'peso_CN': 'peso_ciencias',

    # 2022-only columns (will be additional fields, not in UNIFIED_SCHEMA)
    'pikIE_L': 'pikie_lectura',
    'prob_sec_L': 'prob_sec_lectura',
    'pikIE_M': 'pikie_matematica',
    'prob_sec_M': 'prob_sec_matematica',
    'pikIE_CN': 'pikie_ciencias',
    'prob_sec_CN': 'prob_sec_ciencias',
}

# Combined dict for easy lookup by year
YEAR_RENAME_DICTS = {
    '2022': RENAME_2022,
    '2023': RENAME_2023,
}


# ---------------------------------------------------------------------------
# 3. FILE FORMAT DETECTION
# ---------------------------------------------------------------------------

def extract_year_from_filename(filename: str) -> Optional[int]:
    """
    Extract year from filename like: data_2022.xlsx, ENLA_2023.xlsx, enla_2021.xlsx

    Args:
        filename: Name of the Excel file

    Returns:
        Year as integer (e.g., 2022) or None if not found
    """
    match = re.search(r'20(\d{2})', filename)
    if match:
        return 2000 + int(match.group(1))
    return None


def detect_file_format(df, filename: str = None) -> Tuple[str, Optional[int]]:
    """
    Detect Excel file format/version based on distinctive columns.

    Primary detection by column patterns:
    - 'M500_EM_2S_2023_CT' → 2023
    - 'M500_L' → 2022

    Secondary detection by filename.
    Fallback: ('unknown', None)

    Args:
        df: DataFrame with original column names (after stripping whitespace)
        filename: Optional filename for fallback year detection

    Returns:
        tuple: (format_key, detected_year)
               format_key: '2022', '2023', or 'unknown'
               detected_year: integer year or None
    """
    # Primary: Check distinctive columns
    columns = set(df.columns)

    if 'M500_EM_2S_2023_CT' in columns:
        return ('2023', 2023)
    elif 'M500_L' in columns:
        return ('2022', 2022)

    # Secondary: Extract from filename
    if filename:
        year = extract_year_from_filename(filename)
        if year:
            # Determine format key from year
            format_key = str(year)
            if format_key in YEAR_RENAME_DICTS:
                return (format_key, year)
            else:
                # Future year not yet supported - return as unknown
                return ('unknown', year)

    return ('unknown', None)


# ---------------------------------------------------------------------------
# 4. HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def apply_column_renaming(df, year: str) -> object:
    """
    Apply column renaming for a specific year and ensure all UNIFIED_SCHEMA columns exist.

    Args:
        df: DataFrame with original column names
        year: Year string ('2022', '2023', etc.)

    Returns:
        DataFrame with standardized column names
    """
    if year in YEAR_RENAME_DICTS:
        rename_dict = YEAR_RENAME_DICTS[year]
        # Only rename columns that exist in the DataFrame
        rename_dict_filtered = {k: v for k, v in rename_dict.items() if k in df.columns}
        df = df.rename(columns=rename_dict_filtered)

    # Add missing UNIFIED_SCHEMA columns with None
    for col in UNIFIED_SCHEMA:
        if col not in df.columns:
            df[col] = None

    return df
