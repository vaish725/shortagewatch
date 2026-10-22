"""Extract the NDC directory from the openFDA bulk download (the API's skip cap blocks 138k records)."""
import io
import json
import logging
import zipfile

from ingestion.schemas.models import NdcProduct
from ingestion.utils.http import client, get
from ingestion.utils.pipeline import land

# Columns kept in the weekly snapshot; the nested packaging/openfda blocks make up most of the file size
KEEP = [
    "product_ndc", "generic_name", "brand_name", "labeler_name", "dosage_form", "route", "active_ingredients",
    "marketing_category", "application_number", "marketing_start_date", "marketing_end_date",
    "listing_expiration_date", "finished", "product_type", "pharm_class",
]
BULK_URL = "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip"


def extract(root=None) -> int:
    with client() as c:
        blob = get(c, BULK_URL).content
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        records = json.loads(z.read(z.namelist()[0]))["results"]
    # Sorted by NDC so repeated weekly snapshots compress well
    records.sort(key=lambda r: r.get("product_ndc") or "")
    return land("ndc", records, NdcProduct, root, columns=KEEP)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    extract()
