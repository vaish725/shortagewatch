"""Extract the openFDA drug shortages feed (current-state snapshot) into dated raw Parquet."""
import logging

from ingestion.utils.http import client, fetch_openfda
from ingestion.utils.storage import write_raw

log = logging.getLogger("ingestion")


def extract(root=None) -> int:
    with client() as c:
        records = fetch_openfda(c, "shortages")
    kwargs = {"root": root} if root else {}
    path = write_raw("shortages", records, **kwargs)
    log.info("shortages: %d records -> %s", len(records), path)
    return len(records)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    extract()
