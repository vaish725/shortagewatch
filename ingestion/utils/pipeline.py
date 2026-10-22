"""Shared validate -> land step used by every extractor."""
import logging

from pydantic import BaseModel

from ingestion.schemas.models import validate
from ingestion.utils.storage import write_quarantine, write_raw

log = logging.getLogger("ingestion")


def land(source: str, records: list[dict], model: type[BaseModel], root=None) -> int:
    """Validate records, write valid ones to dated Parquet, log how many were quarantined."""
    good, bad = validate(records, model)
    kwargs = {"root": root} if root else {}
    path = write_raw(source, good, **kwargs)
    write_quarantine(source, bad, **kwargs)
    log.info("%s: %d landed, %d quarantined -> %s", source, len(good), len(bad), path)
    return len(good)
