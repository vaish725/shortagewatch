"""Shared helpers for the analysis scripts: warehouse access and result tables."""
import os
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "warehouse" / "target" / "shortagewatch.duckdb"
SEED = 20261023  # one seed for every random step (matches the dbt control_seed)


def connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    # Staging views hold paths relative to warehouse/, so queries must run from there
    os.chdir(ROOT / "warehouse")
    return duckdb.connect(str(WAREHOUSE_DB), read_only=read_only)


def query(sql: str) -> pd.DataFrame:
    con = connect()
    try:
        return con.sql(sql).df()
    finally:
        con.close()


def write_table(name: str, df: pd.DataFrame) -> None:
    """Replace analysis.<name> in the warehouse so the dashboard can read the results."""
    con = connect(read_only=False)
    try:
        con.sql("create schema if not exists analysis")
        con.register("df_in", df)
        con.sql(f"create or replace table analysis.{name} as select * from df_in")
    finally:
        con.close()
