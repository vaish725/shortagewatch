"""Write raw records to date-partitioned Parquet. Re-running a day overwrites that day's partition."""
import json
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

RAW_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"


def write_raw(source: str, records: list[dict], run_date: date | None = None, root: Path = RAW_ROOT) -> Path:
    """Write records to <root>/<source>/dt=<date>/<source>.parquet.

    Nested values (dicts, lists) are stored as JSON strings so the schema stays flat and stable.
    """
    run_date = run_date or date.today()
    flat = [{k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in records]
    # Union of keys keeps columns stable when optional fields are missing from some records
    cols = sorted({k for r in flat for k in r})
    table = pa.Table.from_pylist([{c: r.get(c) for c in cols} for r in flat])
    path = root / source / f"dt={run_date.isoformat()}" / f"{source}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def write_quarantine(source: str, bad: list[dict], run_date: date | None = None, root: Path = RAW_ROOT) -> None:
    """Keep rejected records next to the day's partition for inspection; no file when nothing was rejected."""
    if not bad:
        return
    path = root / source / f"dt={(run_date or date.today()).isoformat()}" / "quarantine.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bad, default=str))
