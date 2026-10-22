"""Extract the openFDA drug shortages feed (current-state snapshot) into dated raw Parquet."""
import logging

from ingestion.schemas.models import Shortage
from ingestion.utils.http import client, fetch_openfda
from ingestion.utils.pipeline import land


def extract(root=None) -> int:
    with client() as c:
        return land("shortages", fetch_openfda(c, "shortages"), Shortage, root)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    extract()
