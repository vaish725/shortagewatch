"""Extract the NDC directory from the openFDA bulk download (the API's skip cap blocks 138k records)."""
import io
import json
import logging
import zipfile

from ingestion.schemas.models import NdcProduct
from ingestion.utils.http import client, get
from ingestion.utils.pipeline import land

BULK_URL = "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip"


def extract(root=None) -> int:
    with client() as c:
        blob = get(c, BULK_URL).content
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        records = json.loads(z.read(z.namelist()[0]))["results"]
    return land("ndc", records, NdcProduct, root)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    extract()
