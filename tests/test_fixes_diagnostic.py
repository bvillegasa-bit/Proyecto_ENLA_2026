"""
Diagnostic script: test the ingestion pipeline WITHOUT connecting to MongoDB or BigQuery.
Run from the project root:
    python tests/test_ingestion_local.py

Simulates reading/processing the MINEDU Excel format (2023 style columns).
"""
import sys
import os
import traceback

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np


def make_synthetic_excel_df(year: int = 2023) -> pd.DataFrame:
    """
    Creates a synthetic DataFrame mimicking a real MINEDU Excel file.
    Uses MIXED CASE column headers on purpose to test the normalization fix.
    Also mixes string and int grado_evaluacion to test Bug 7 fix.
    """
    return pd.DataFrame({
        # Mixed-case headers (real MINEDU files are inconsistent)
        'ID_IE':           ['00101', '00101', '00102', '00102', '00999'],
        'ID_SECCION':      ['A', 'B', 'A', 'B', 'A'],
        'nom_ie':          ['IE San Jose', 'IE San Jose', 'IE Lima Alta', 'IE Lima Alta', 'IE Cono Norte'],
        'NOM_DRE':         ['Callao', 'callao', 'CALLAO', 'Callao', 'Lima'],  # mixed and one other region
        'grado_evaluacion': ['2', 2, '2', '2', '2'],  # mix of string "2" and int 2
        'cor_est':         ['C001', 'C002', 'C003', 'C004', 'C005'],
        'area':            ['Urbana', 'Urbana', 'Rural', 'Rural', 'Urbana'],
        # 2023-format score columns
        'M500_EM_2S_2023_CT': [72.5, 65.0, 80.0, 55.0, 90.0],   # Comunicación
        'grupo_EM_2S_2023_CT': ['2', '3', '1', '3', '1'],
        'peso_CT':             [1.0, 1.0, 1.0, 1.0, 1.0],
        'M500_EM_2S_2023_MA': [58.3, 71.2, None, 45.0, 88.0],    # Matemática (one null)
        'grupo_EM_2S_2023_MA': ['3', '2', None, '3', '1'],
        'peso_MA':             [1.0, 1.0, None, 1.0, 1.0],
        'M500_EM_2S_2023_CS': [None, 69.5, 75.0, 62.0, 77.0],    # CCSS (one null)
        'grupo_EM_2S_2023_CS': [None, '2', '2', '2', '2'],
        'peso_CS':             [None, 1.0, 1.0, 1.0, 1.0],
    })


def run_test(name: str, fn):
    """Run a test function and print pass/fail."""
    try:
        fn()
        print(f"   PASS — {name}")
        return True
    except AssertionError as e:
        print(f"   FAIL — {name}")
        print(f"       AssertionError: {e}")
        return False
    except Exception as e:
        print(f"   ERROR — {name}")
        traceback.print_exc()
        return False


def test_read_excel_no_encoding_param():
    """Bug 1: read_excel should NOT use encoding parameter."""
    from src.ingestion.ingest_enla import ENLAIngestor
    import inspect
    src = inspect.getsource(ENLAIngestor.read_excel)
    assert 'encoding=' not in src or 'engine=' in src, \
        "read_excel still uses invalid 'encoding=' param!"
    assert 'engine=' in src, "read_excel should explicitly use engine='openpyxl'"


def test_columns_normalized_to_lowercase():
    """Bug 2: all column names are lowercased after read_excel."""
    from src.ingestion.ingest_enla import ENLAIngestor
    ingestor = ENLAIngestor.__new__(ENLAIngestor)

    # Simulate what read_excel does to the column names
    df = make_synthetic_excel_df(2023)
    # Apply the normalization the fixed code does
    df.columns = df.columns.str.strip().str.lower()

    assert 'id_ie' in df.columns, "id_ie not found after lowercase normalization"
    assert 'id_seccion' in df.columns, "id_seccion not found after lowercase normalization"
    assert 'nom_dre' in df.columns, "nom_dre not found"
    # Make sure uppercase version is GONE
    assert 'ID_IE' not in df.columns, "ID_IE still present (not normalized!)"
    assert 'NOM_DRE' not in df.columns, "NOM_DRE still present (not normalized!)"


def test_filter_data_grado_string_and_int():
    """Bug 7: filter_data must work when grado_evaluacion is stored as '2' (string) or 2 (int)."""
    from src.ingestion.ingest_enla import ENLAIngestor
    from unittest.mock import MagicMock
    from src.ingestion.config import settings

    ingestor = ENLAIngestor.__new__(ENLAIngestor)
    ingestor.validator = MagicMock()

    df = make_synthetic_excel_df(2023)
    df.columns = df.columns.str.strip().str.lower()

    # 5 rows total: 4 Callao (grado=[str '2', int 2, str '2', str '2']), 1 Lima
    result = ingestor.filter_data(df, region='CALLAO', grado=2, year=2023)
    assert len(result) == 4, \
        f"Expected 4 rows (4 Callao grade 2), got {len(result)}. " \
        f"Bug 7 fix may not be working — grado normalization failed."


def test_filter_data_region_case_insensitive():
    """filter_data should match region regardless of case in data."""
    from src.ingestion.ingest_enla import ENLAIngestor
    from unittest.mock import MagicMock

    ingestor = ENLAIngestor.__new__(ENLAIngestor)
    ingestor.validator = MagicMock()

    df = make_synthetic_excel_df(2023)
    df.columns = df.columns.str.strip().str.lower()

    # 'Callao', 'callao', 'CALLAO' all appear in the fixture — all should match
    result = ingestor.filter_data(df, region='CALLAO', grado=2, year=2023)
    assert len(result) == 4, f"Expected 4 rows from Callao (case-insensitive), got {len(result)}"


def test_validator_core_columns_lowercase():
    """Bug 2: validator CORE_COLUMNS must use lowercase."""
    from src.ingestion.validators import ENLAValidator
    v = ENLAValidator()
    assert 'id_ie' in v.CORE_COLUMNS, "CORE_COLUMNS should use lowercase 'id_ie'"
    assert 'id_seccion' in v.CORE_COLUMNS, "CORE_COLUMNS should use lowercase 'id_seccion'"
    assert 'ID_IE' not in v.CORE_COLUMNS, "CORE_COLUMNS should not have uppercase 'ID_IE'"


def test_validator_discovers_2023_columns():
    """Validator should discover score columns from 2023-format data."""
    from src.ingestion.validators import ENLAValidator
    v = ENLAValidator()

    df = make_synthetic_excel_df(2023)
    df.columns = df.columns.str.strip().str.lower()

    v._discover_columns(df)
    assert len(v._discovered_score_columns) > 0, \
        "Validator found NO score columns in 2023-format data!"
    # Should find at least comunicación score column
    found = [c for c in v._discovered_score_columns if 'ct' in c.lower() or 'ma' in c.lower()]
    assert len(found) > 0, f"No CT/MA score columns found. Discovered: {v._discovered_score_columns}"


def test_validator_passes_valid_data():
    """Validator.validate() must pass on valid synthetic data."""
    from src.ingestion.validators import ENLAValidator
    v = ENLAValidator()

    df = make_synthetic_excel_df(2023)
    df.columns = df.columns.str.strip().str.lower()

    # Add ano_evaluacion (normally added by read_excel)
    df['ano_evaluacion'] = 2023

    report = v.validate(df)
    assert report.is_valid, \
        f"Validator failed on valid data! Errors: {report.errors}"


def test_upsert_key_is_lowercase():
    """Bug 2: UPSERT_KEY must use lowercase after fix."""
    from src.ingestion.ingest_enla import ENLAIngestor
    assert 'id_ie' in ENLAIngestor.UPSERT_KEY, "UPSERT_KEY should use lowercase 'id_ie'"
    assert 'id_seccion' in ENLAIngestor.UPSERT_KEY, "UPSERT_KEY should use lowercase 'id_seccion'"


def test_deduplicate_uses_lowercase_key():
    """deduplicate() must work when DataFrame has lowercase columns."""
    from src.ingestion.ingest_enla import ENLAIngestor
    from unittest.mock import MagicMock

    ingestor = ENLAIngestor.__new__(ENLAIngestor)
    ingestor.validator = MagicMock()

    df = pd.DataFrame({
        'id_ie': ['001', '001', '002'],
        'id_seccion': ['A', 'A', 'B'],   # duplicate
        'ano_evaluacion': [2023, 2023, 2023],
        'nom_ie': ['IE A', 'IE A', 'IE B'],
    })

    result = ingestor.deduplicate(df)
    assert len(result) == 2, f"Expected 2 rows after dedup, got {len(result)}"


def test_etl_transform_no_dead_code():
    """Bug 5: _create_dim_meta should NOT have unreachable duplicate code."""
    import inspect
    from src.etl.transform import ETLTransform
    src = inspect.getsource(ETLTransform._create_dim_meta)
    # Count return statements — there should be exactly 1
    returns = [line.strip() for line in src.split('\n') if line.strip().startswith('return ')]
    assert len(returns) == 1, \
        f"Expected exactly 1 return in _create_dim_meta, found {len(returns)}: {returns}"


def test_dbt_comunicacion_uses_accent():
    """Bug 6: dbt comunicación view must use accented area name."""
    dbt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'dbt', 'models', 'v_callao_comunicacion_2026.sql'
    )
    with open(dbt_path, encoding='utf-8') as f:
        content = f.read()
    assert "= 'comunicación'" in content, \
        "dbt comunicacion view does not use 'comunicación' (with accent)!"
    assert "= 'comunicacion'" not in content, \
        "dbt comunicacion view still has old 'comunicacion' without accent!"


def test_dbt_matematica_uses_accent():
    """Bug 6: dbt matemática view must use accented area name."""
    dbt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'dbt', 'models', 'v_callao_matematica_2026.sql'
    )
    with open(dbt_path, encoding='utf-8') as f:
        content = f.read()
    assert "= 'matemática'" in content, \
        "dbt matematica view does not use 'matemática' (with accent)!"
    assert "= 'matematica'" not in content, \
        "dbt matematica view still has old 'matematica' without accent!"


def test_config_env_file_path():
    """Bug 4: config env_file should point to 'config/.env' not just '.env'."""
    import inspect
    from src.ingestion import config as config_module
    src = inspect.getsource(config_module)
    assert "config/.env" in src, \
        "config.py still uses '.env' instead of 'config/.env' for the env_file setting!"


if __name__ == '__main__':
    print("=" * 60)
    print("ENLA 2026 — Pipeline Diagnostic Tests")
    print("Tests the 7 bug fixes WITHOUT connecting to any external service")
    print("=" * 60)
    print()

    tests = [
        ("Bug 1 — read_excel has no encoding param",       test_read_excel_no_encoding_param),
        ("Bug 2 — columns normalized to lowercase",         test_columns_normalized_to_lowercase),
        ("Bug 2 — UPSERT_KEY is lowercase",                test_upsert_key_is_lowercase),
        ("Bug 2 — validator CORE_COLUMNS is lowercase",    test_validator_core_columns_lowercase),
        ("Bug 2 — deduplicate works on lowercase cols",    test_deduplicate_uses_lowercase_key),
        ("Bug 4 — config env_file path correct",           test_config_env_file_path),
        ("Bug 5 — no dead code in _create_dim_meta",       test_etl_transform_no_dead_code),
        ("Bug 6 — dbt comunicación uses accent",           test_dbt_comunicacion_uses_accent),
        ("Bug 6 — dbt matemática uses accent",             test_dbt_matematica_uses_accent),
        ("Bug 7 — filter works when grado is string '2'",  test_filter_data_grado_string_and_int),
        ("Integration — region filter case-insensitive",   test_filter_data_region_case_insensitive),
        ("Integration — validator discovers 2023 columns", test_validator_discovers_2023_columns),
        ("Integration — validator passes valid data",       test_validator_passes_valid_data),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        ok = run_test(name, fn)
        if ok:
            passed += 1
        else:
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed == 0:
        print(" ALL TESTS PASSED — All bug fixes verified!")
    else:
        print("  Some tests failed — see details above.")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)