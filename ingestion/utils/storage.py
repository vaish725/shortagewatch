"""Write raw records to date-partitioned Parquet. Re-running a day overwrites that day's partition."""
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
RAW_ROOT = DATA_ROOT / "raw"
RUNS_ROOT = DATA_ROOT / "runs"


def write_raw(
    source: str, records: list[dict], run_date: date | None = None, root: Path = RAW_ROOT, columns: list[str] | None = None
) -> Path:
    """Write records to <root>/<source>/dt=<date>/<source>.parquet.

    Nested values (dicts, lists) are stored as JSON strings so the schema stays flat and stable.
    `columns` keeps only the named fields (used to slim the large NDC snapshot); output is zstd-compressed.
    """
    # Partitions use UTC dates so a run's label does not depend on the machine's timezone
    run_date = run_date or datetime.now(timezone.utc).date()
    flat = [{k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in records]
    # Union of keys keeps columns stable when optional fields are missing from some records
    cols = columns or sorted({k for r in flat for k in r})
    table = pa.Table.from_pylist([{c: r.get(c) for c in cols} for r in flat])
    path = root / source / f"dt={run_date.isoformat()}" / f"{source}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="zstd", compression_level=15)
    return path


def write_quarantine(source: str, bad: list[dict], run_date: date | None = None, root: Path = RAW_ROOT) -> None:
    """Keep rejected records next to the day's partition for inspection; no file when nothing was rejected."""
    if not bad:
        return
    path = root / source / f"dt={(run_date or datetime.now(timezone.utc).date()).isoformat()}" / "quarantine.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bad, default=str))


def write_run_summary(name: str, stats: dict, root: Path = RUNS_ROOT) -> Path:
    """Record one pipeline step's outcome (counts, match rates) as data/runs/dt=<utc date>/<name>.json."""
    now = datetime.now(timezone.utc)
    path = root / f"dt={now.date().isoformat()}" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"step": name, "run_at": now.isoformat(timespec="seconds"), **stats}, indent=1))
    return path
