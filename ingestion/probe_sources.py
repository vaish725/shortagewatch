"""Week 1 spike: pull a small sample from every source and print a field inventory.

Samples land in data/samples/. Run: .venv/bin/python ingestion/probe_sources.py
"""
import io
import json
from collections import Counter
from pathlib import Path

import httpx
import openpyxl

OUT = Path(__file__).resolve().parent.parent / "data" / "samples"
OPENFDA = "https://api.fda.gov/drug"
WL_URL = (
    "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/"
    "compliance-actions-and-activities/warning-letters/datatables-data"
)
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fill_rate(records):
    """Share of records where each top-level field is non-empty."""
    counts = Counter(k for r in records for k, v in r.items() if v not in (None, "", [], {}))
    return {k: round(c / len(records), 2) for k, c in sorted(counts.items())}


def save(name, records):
    (OUT / f"{name}.json").write_text(json.dumps(records, indent=1, default=str))
    print(f"\n[{name}] {len(records)} records saved")
    for field, rate in fill_rate(records).items():
        print(f"  {field:32s} filled {rate:.0%}")


def openfda(client, endpoint, limit):
    r = client.get(f"{OPENFDA}/{endpoint}.json", params={"limit": limit})
    r.raise_for_status()
    body = r.json()
    print(f"{endpoint}: total={body['meta']['results']['total']} last_updated={body['meta']['last_updated']}")
    return body["results"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, headers=HEADERS, follow_redirects=True) as c:
        for name, endpoint in [("shortages", "shortages"), ("enforcement", "enforcement"), ("ndc", "ndc")]:
            save(name, openfda(c, endpoint, 100))

        # RxNorm: confirm name -> RxCUI lookup works
        names = ["lisinopril", "cisplatin", "amoxicillin"]
        rx = [{"name": n, **c.get("https://rxnav.nlm.nih.gov/REST/rxcui.json", params={"name": n}).json()} for n in names]
        save("rxnorm", rx)

        # Warning letters: XLSX export of the FDA page (no JSON/XML feed is live; see docs/data_quality_log.md)
        wb = openpyxl.load_workbook(io.BytesIO(c.get(WL_URL, params={"page": 1, "_format": "xlsx"}).content))
        rows = list(wb.active.iter_rows(values_only=True))
        save("warning_letters", [dict(zip(rows[0], r)) for r in rows[1:]])


if __name__ == "__main__":
    main()
