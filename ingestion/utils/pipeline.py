"""Shared validate -> land step used by every extractor."""
import logging

from pydantic import BaseModel

from ingestion.schemas.models import validate
from ingestion.utils.storage import write_quarantine, write_raw, write_run_summary

log = logging.getLogger("ingestion")


def land(source: str, records: list[dict], model: type[BaseModel], root=None, columns: list[str] | None = None) -> int:
    """Validate records, write valid ones to dated Parquet, log how many were quarantined."""
    good, bad = validate(records, model)
    # An empty or fully rejected pull means the source changed shape; fail before overwriting a good partition
    if not good:
        raise RuntimeError(f"{source}: no valid records ({len(bad)} quarantined)")
    kwargs = {"root": root} if root else {}
    path = write_raw(source, good, columns=columns, **kwargs)
    write_quarantine(source, bad, **kwargs)
    if root is None:
        write_run_summary(source, {"landed": len(good), "quarantined": len(bad)})
    log.info("%s: %d landed, %d quarantined -> %s", source, len(good), len(bad), path)
    return len(good)
