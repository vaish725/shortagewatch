"""Extract openFDA drug recalls (enforcement reports) into dated raw Parquet."""
import logging

from ingestion.schemas.models import Recall
from ingestion.utils.http import client, fetch_openfda
from ingestion.utils.pipeline import land


def extract(root=None) -> int:
    with client() as c:
        return land("enforcement", fetch_openfda(c, "enforcement"), Recall, root)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    extract()
