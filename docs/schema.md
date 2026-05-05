# ENLA Schema Documentation

## Overview

This document describes the **standardized schema** used in ENLA 2026 Callao after the column standardization process.

The system now uses **33 standardized fields** (snake_case) for ALL years (2022, 2023, and future years).

## Unified Schema (33 Fields)

### Core/ID Fields (8 fields)

| # | Field Name | Type | Description | Required | Example |
|---|------------|------|-------------|----------|---------|
| 1 | `ano_evaluacion` | integer | Year of evaluation | Yes | 2023 |
| 2 | `grado_evaluacion` | integer | Grade evaluated (2 = 2nd grade) | Yes | 2 |
| 3 | `nivel` | string | Education level | Yes | "Secundaria" |
| 4 | `id_estudiante` | string | Unique student ID | No* | "EST-001" |
| 5 | `cor_est` | string | Student correlation ID | Yes | "000123" |
| 6 | `id_ie` | string | School ID | Yes | "IE-456" |
| 7 | `id_seccion` | string | Section ID | Yes | "SEC-001" |
| 8 | `seccion` | string | Section name/code | Yes | "A" |

*Note: `id_estudiante` is required for 2022, but may not be present in 2023.

### Geographic Fields (9 fields)

| # | Field Name | Type | Description | Required | Example |
|---|------------|------|-------------|----------|---------|
| 9 | `cod_dre` | string | DRE code | Yes | "DRE-01" |
| 10 | `nom_dre` | string | DRE name | Yes | "DRE Lima Metropolitana" |
| 11 | `cod_ugel` | string | UGEL code | Yes | "UGEL-05" |
| 12 | `nom_ugel` | string | UGEL name | Yes | "UGEL San Juan de Lurigancho" |
| 13 | `codgeo` | string | Geographic code | No | "150132" |
| 14 | `departamento` | string | Department | Yes | "Lima" |
| 15 | `provincia` | string | Province | Yes | "Lima" |
| 16 | `distrito` | string | District | Yes | "San Juan de Lurigancho" |
| 17 | `estrato_dre` | string | DRE stratum | No | "Urbano" |

### School Fields (3 fields)

| # | Field Name | Type | Description | Required | Example |
|---|------------|------|-------------|----------|---------|
| 18 | `gestion2` | string | Management type (Publica/Privada) | Yes | "Publica" |
| 19 | `area` | string | Geographic area (Rural/Urban) | Yes | "Urbana" |
| 20 | `caracteristica2` | string | School characteristic | No | "Polidocente" |

### Student Fields (4 fields)

| # | Field Name | Type | Description | Required | Example |
|---|------------|------|-------------|----------|---------|
| 21 | `sexo` | string | Student gender | Yes | "M" / "F" |
| 22 | `lengua_materna` | string | Native language | No | "Español" |
| 23 | `ise` | string | Socioeconomic index (category) | No | "Bajo" |
| 24 | `n_ise` | float | Socioeconomic index (numeric) | No | 2.5 |

### Assessment: Lectura/Comunicación (3 fields)

| # | Field Name | Type | Description | Required | Example |
|---|------------|------|-------------|----------|---------|
| 25 | `medida_lectura` | float | Achievement score in reading | Yes | 450.5 |
| 26 | `grupo_lectura` | string | Performance group in reading | Yes | "Alto" |
| 27 | `peso_lectura` | float | Weight of reading evaluation | Yes | 1.0 |

### Assessment: Matemática (3 fields)

| # | Field Name | Type | Description | Required | Example |
|---|------------|------|-------------|----------|---------|
| 28 | `medida_matematica` | float | Achievement score in math | Yes | 420.3 |
| 29 | `grupo_matematica` | string | Performance group in math | Yes | "Medio" |
| 30 | `peso_matematica` | float | Weight of math evaluation | Yes | 1.0 |

### Assessment: Ciencias (3 fields)

| # | Field Name | Type | Description | Required | Example |
|---|------------|------|-------------|----------|---------|
| 31 | `medida_ciencias` | float | Achievement score in science | Yes | 380.7 |
| 32 | `grupo_ciencias` | string | Performance group in science | Yes | "Bajo" |
| 33 | `peso_ciencias` | float | Weight of science evaluation | Yes | 1.0 |

## 2022-Only Fields (Optional - 6 fields)

These fields are ONLY present in 2022 data and are preserved but NOT part of the UNIFIED_SCHEMA:

| Field Name | Type | Description | Example |
|------------|------|-------------|---------|
| `pikie_lectura` | float | ITE cutoff score - Reading | 450.0 |
| `prob_sec_lectura` | float | Probability of achievement - Reading | 0.75 |
| `pikie_matematica` | float | ITE cutoff score - Math | 420.0 |
| `prob_sec_matematica` | float | Probability of achievement - Math | 0.68 |
| `pikie_ciencias` | float | ITE cutoff score - Science | 380.0 |
| `prob_sec_ciencias` | float | Probability of achievement - Science | 0.62 |

## Column Mapping by Year

### 2022 → Standardized

| Standardized Field | Original 2022 Column |
|-------------------|---------------------|
| `ano_evaluacion` | `Año` |
| `grado_evaluacion` | `Grado` |
| `nivel` | `Nivel` |
| `id_estudiante` | `ID_estudiante` |
| `id_ie` | `ID_IE` |
| `id_seccion` | `ID_seccion` |
| `seccion` | `Seccion` |
| `cor_est` | `cor_est` (unchanged) |
| `cod_dre` | `cod_DRE` |
| `nom_dre` | `nom_DRE` |
| `cod_ugel` | `cod_UGEL` |
| `nom_ugel` | `nom_UGEL` |
| `codgeo` | `codgeo` (unchanged) |
| `departamento` | `Departamento` |
| `provincia` | `Provincia` |
| `distrito` | `Distrito` |
| `estrato_dre` | `Estrato_DRE` |
| `gestion2` | `Gestion2` |
| `area` | `Area` |
| `caracteristica2` | `Caracteristica2` |
| `sexo` | `Sexo` |
| `lengua_materna` | `Lengua_materna` |
| `ise` | `ISE` |
| `n_ise` | `N_ISE` |
| `medida_lectura` | `M500_L` |
| `grupo_lectura` | `grupo_L` |
| `peso_lectura` | `peso_L` |
| `medida_matematica` | `M500_M` |
| `grupo_matematica` | `grupo_M` |
| `peso_matematica` | `peso_M` |
| `medida_ciencias` | `M500_CN` |
| `grupo_ciencias` | `grupo_CN` |
| `peso_ciencias` | `peso_CN` |
| `pikie_lectura` | `pikIE_L` |
| `prob_sec_lectura` | `prob_sec_L` |
| `pikie_matematica` | `pikIE_M` |
| `prob_sec_matematica` | `prob_sec_M` |
| `pikie_ciencias` | `pikIE_CN` |
| `prob_sec_ciencias` | `prob_sec_CN` |

### 2023 → Standardized

| Standardized Field | Original 2023 Column |
|-------------------|---------------------|
| `ano_evaluacion` | `Año` (or extracted from filename) |
| `grado_evaluacion` | `grado_evaluacion` (unchanged) |
| `nivel` | `nivel` (unchanged) |
| `id_ie` | `ID_IE` |
| `id_seccion` | `ID_SECCION` |
| `seccion` | `seccion` (unchanged) |
| `cor_est` | `cor_est` (unchanged) |
| `cod_dre` | `cod_DRE` |
| `nom_dre` | `nom_DRE` |
| `cod_ugel` | `cod_UGEL` |
| `nom_ugel` | `nom_UGEL` |
| `codgeo` | `codgeo` (unchanged) |
| `departamento` | `Departamento` |
| `provincia` | `Provincia` |
| `distrito` | `Distrito` |
| `estrato_dre` | `Estrato_DRE` |
| `gestion2` | `Gestion2` |
| `area` | `Area` |
| `caracteristica2` | `Caracteristica2` |
| `sexo` | `Sexo` |
| `lengua_materna` | `Lengua_materna` |
| `ise` | `ISE` |
| `n_ise` | `N_ISE` |
| `medida_lectura` | `M500_EM_2S_2023_CT` |
| `grupo_lectura` | `grupo_EM_2S_2023_CT` |
| `peso_lectura` | `peso_CT` |
| `medida_matematica` | `M500_EM_2S_2023_MA` |
| `grupo_matematica` | `grupo_EM_2S_2023_MA` |
| `peso_matematica` | `peso_MA` |
| `medida_ciencias` | `M500_EM_2S_2023_CS` |
| `grupo_ciencias` | `grupo_EM_2S_2023_CS` |
| `peso_ciencias` | `peso_CS` |

## Detection Logic

The system uses a **hybrid detection strategy** to determine the file format:

### Primary Detection (by column patterns)
- If `M500_EM_2S_2023_CT` exists → 2023 format
- If `M500_L` exists → 2022 format

### Secondary Detection (by filename)
- Extract year from filename using regex: `20(\d{2})`
- Example: `ENLA_2023.xlsx` → 2023

### Fallback
- If detection fails → Use original column names (log warning)

## How to Add Support for New Years (2024+)

When a new year's data becomes available (e.g., 2024), follow these steps:

### 1. Create Rename Dictionary

In `src/ingestion/column_mapping.py`, add a new rename dictionary:

```python
RENAME_2024 = {
    # Core/ID
    'Año': 'ano_evaluacion',
    'ID_IE': 'id_ie',
    # ... map all columns to standardized names
    
    # Assessment columns (update these for 2024 format)
    'M500_EM_2S_2024_CT': 'medida_lectura',
    'grupo_EM_2S_2024_CT': 'grupo_lectura',
    'peso_CT': 'peso_lectura',
    # ...
}

# Add to YEAR_RENAME_DICTS
YEAR_RENAME_DICTS = {
    '2022': RENAME_2022,
    '2023': RENAME_2023,
    '2024': RENAME_2024,  # Add this
}
```

### 2. Update Detection Logic

The `detect_file_format()` function will automatically detect 2024 if the columns are distinctive. If not, ensure the filename contains the year.

### 3. Test

Create test cases with sample 2024 data to verify:
- Column detection works
- Renaming works
- All 33 UNIFIED_SCHEMA fields are present

### 4. Run Migration (if needed)

If you have existing MongoDB data for 2024 with original column names, run:

```bash
python scripts/migrate_mongo_schema.py --year 2024
```

## Before and After Standardization

### Before (2022 data in MongoDB)
```json
{
  "M500_L": 500.0,
  "grupo_L": "Alto",
  "ID_IE": "IE001",
  "nom_DRE": "CALLAO"
}
```

### After (Standardized - 2022 data in MongoDB)
```json
{
  "medida_lectura": 500.0,
  "grupo_lectura": "Alto",
  "id_ie": "IE001",
  "nom_dre": "CALLAO",
  "ano_evaluacion": 2022,
  "grado_evaluacion": 2,
  "pikie_lectura": 450.0,
  "prob_sec_lectura": 0.75
  // ... all 33 UNIFIED_SCHEMA fields present
}
```

## File Locations

- **Column Mapping Module**: `src/ingestion/column_mapping.py`
- **Migration Script**: `scripts/migrate_mongo_schema.py`
- **Validators**: `src/ingestion/validators.py` (now uses standardized names)
- **Ingestion Pipeline**: `src/ingestion/ingest_enla.py` (applies renaming in `read_excel()`)

## Notes

1. All 33 UNIFIED_SCHEMA fields are added to every document (missing fields = `None`)
2. The 2022-only fields (`pikie_*`, `prob_sec_*`) are preserved but not part of the core schema
3. MongoDB migration is idempotent (running multiple times won't break)
4. Use `--dry-run` flag on migration script to preview changes
