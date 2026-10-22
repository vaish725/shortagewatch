from datetime import date

import pyarrow.parquet as pq

from ingestion.recall_match import firm_key, match_recalls
from ingestion.schemas.models import Shortage, validate
from ingestion.sources.warning_letters import is_drug_office
from ingestion.utils.storage import write_raw

GOOD = {"generic_name": "Cisplatin", "company_name": "X", "status": "Current", "initial_posting_date": "01/01/2024", "package_ndc": "0409-4888-10"}


def test_validate_quarantines_missing_key_fields():
    good, bad = validate([GOOD, {"generic_name": "Y"}], Shortage)
    assert len(good) == 1 and len(bad) == 1


def test_write_raw_is_idempotent_and_flattens_nested(tmp_path):
    rec = {**GOOD, "openfda": {"rxcui": ["1"]}}
    for _ in range(2):  # rerunning the same day overwrites the partition
        path = write_raw("shortages", [rec], date(2026, 1, 2), root=tmp_path)
    assert path.parent.name == "dt=2026-01-02"
    rows = pq.read_table(path).to_pylist()
    assert len(rows) == 1 and rows[0]["openfda"] == '{"rxcui": ["1"]}'


def test_firm_key_strips_suffixes_and_punctuation():
    assert firm_key("Pfizer Inc.") == firm_key("PFIZER, INC") == "pfizer"


def test_drug_office_filter():
    assert is_drug_office("Center for Drug Evaluation and Research | CDER")
    assert not is_drug_office("Center for Tobacco Products")


def test_match_recalls_records_method():
    ndc = [{"product_ndc": "0409-4888", "labeler_name": "Hospira, Inc.", "generic_name": "Cisplatin"}]
    base = {"recalling_firm": "Other Co", "openfda": None}
    recalls = [
        {**base, "recall_number": "D-1", "product_description": "Cisplatin vial NDC 0409-4888-10", "code_info": ""},
        {**base, "recall_number": "D-2", "product_description": "cisplatin injection", "code_info": ""},
        {**base, "recall_number": "D-3", "product_description": "unrelated saline", "code_info": ""},
    ]
    out = match_recalls(recalls, ndc)
    assert out["D-1"][0] == "ndc_keyword" and out["D-2"][0] == "generic_name" and "D-3" not in out


def test_land_refuses_empty_pull(tmp_path):
    import pytest

    from ingestion.utils.pipeline import land

    with pytest.raises(RuntimeError):
        land("shortages", [{"generic_name": "only one field"}], Shortage, root=tmp_path)
    assert not list(tmp_path.rglob("*.parquet"))  # nothing overwritten


def test_summarize_separates_product_and_ingredient_levels():
    from ingestion.recall_match import summarize

    recalls = [{"recall_number": f"D-{i}", "report_date": "20260101"} for i in range(4)]
    matched = {"D-0": ("ndc_keyword", ["x"]), "D-1": ("generic_name", ["y"])}
    s = summarize(recalls, matched)
    assert s["match_rate"] == 0.5 and s["product_level_rate"] == 0.25
    assert s["by_method"]["generic_name"] == 1
