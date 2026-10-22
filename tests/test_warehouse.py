"""Warehouse rebuild check. Skipped unless dbt has already built warehouse/target/shortagewatch.duckdb."""
import subprocess
import sys
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")
WAREHOUSE = Path(__file__).resolve().parents[1] / "warehouse"
DB = WAREHOUSE / "target" / "shortagewatch.duckdb"
# History and episode models; each must be a pure function of the snapshot partitions
MODELS = ["int_shortage_history", "int_ndc_history", "int_shortage_to_family", "int_shortage_record_intervals", "int_shortage_episodes", "fct_shortage_events"]


def fingerprint() -> dict[str, str]:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        return {
            m: con.sql(f"select md5(string_agg(md5(cast(t as varchar)), '' order by md5(cast(t as varchar)))) from {m} t").fetchall()[0][0]
            for m in MODELS
        }
    finally:
        con.close()


@pytest.mark.skipif(not DB.exists(), reason="warehouse not built")
def test_history_models_rebuild_identically():
    before = fingerprint()
    dbt = Path(sys.executable).parent / "dbt"
    cmd = [str(dbt) if dbt.exists() else "dbt", "run", "-s", *MODELS]
    subprocess.run(cmd, cwd=WAREHOUSE, check=True, capture_output=True)
    assert fingerprint() == before
