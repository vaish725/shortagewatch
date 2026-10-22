"""Extract FDA warning letters from the XLSX export behind the FDA warning letters page.

The export returns 1,000 rows per request and its paging is unstable (pages overlap and the
full set is never reachable in one pass), so pages are pulled in repeated rounds and de-duplicated
until a round adds nothing new. Coverage is partial by construction; see docs/data_quality_log.md.
"""
import io
import logging
import re
from datetime import datetime

import openpyxl

from ingestion.schemas.models import WarningLetter
from ingestion.utils.http import client, get
from ingestion.utils.pipeline import land

URL = (
    "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/"
    "compliance-actions-and-activities/warning-letters/datatables-data"
)
PAGES = (1, 2, 3)  # later pages only repeat earlier rows
MAX_ROUNDS = 6


def _rows(c, page: int) -> list[dict]:
    wb = openpyxl.load_workbook(io.BytesIO(get(c, URL, page=page, _format="xlsx").content))
    header, *rows = wb.active.iter_rows(values_only=True)
    keys = [re.sub(r"\W+", "_", h.strip().lower()) for h in header]
    return [dict(zip(keys, r)) for r in rows]


def pull_all(c) -> list[dict]:
    """Repeat the page pulls, keeping unique rows, until a whole round finds nothing new."""
    seen: dict[tuple, dict] = {}
    for rnd in range(MAX_ROUNDS):
        before = len(seen)
        for page in PAGES:
            for r in _rows(c, page):
                seen.setdefault((r["posted_date"], r["letter_issue_date"], r["company_name"], r["subject"]), r)
        logging.getLogger("ingestion").info("warning_letters round %d: %d unique (+%d)", rnd + 1, len(seen), len(seen) - before)
        if len(seen) == before:
            break
    return list(seen.values())


def is_drug_office(office: str | None) -> bool:
    """Drug-related issuing offices; the export covers every FDA center (food, tobacco, devices...)."""
    return bool(re.search(r"drug|cder|pharmaceutical", office or "", re.IGNORECASE))


def extract(root=None) -> int:
    with client() as c:
        records = pull_all(c)
    n = land("warning_letters", records, WarningLetter, root)
    dates = sorted(datetime.strptime(r["posted_date"], "%m/%d/%Y") for r in records if r.get("posted_date"))
    drug = [r for r in records if is_drug_office(r["issuing_office"])]
    logging.getLogger("ingestion").info(
        "warning_letters: %d unique, %d drug-related, posted %s to %s", n, len(drug), dates[0].date(), dates[-1].date()
    )
    return n


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    extract()
