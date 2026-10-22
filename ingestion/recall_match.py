"""Prototype of recall -> NDC product matching, recording which method matched each recall.

Methods, in priority order:
  openfda_block  the recall's own openfda.product_ndc enrichment
  ndc_keyword    NDC found in product_description/code_info right after the word "NDC"
  ndc_bare       NDC-shaped token in the same text, confirmed only by existing in the directory
  firm_text      same normalised firm as a labeler and its generic name appears in the description
  generic_name   a directory generic name (1 to 4 words) appears in the description; family level
                 only, no specific product, so it is the weakest method
The same logic becomes the dbt model int_recall_to_family in week 4.

Run: .venv/bin/python -m ingestion.recall_match
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq

from ingestion.utils.ndc import extract_ndcs, product_key
from ingestion.utils.storage import RAW_ROOT

_SUFFIX = re.compile(r"\b(inc|llc|ltd|limited|corp|corporation|co|company|lp|llp|plc|pharmacy)\b")


def firm_key(name: str) -> str:
    """Lowercase, drop punctuation and legal suffixes so 'Pfizer Inc.' and 'PFIZER' agree."""
    s = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    return " ".join(_SUFFIX.sub(" ", s).split())


def _words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split()


def latest(source: str) -> list[dict]:
    path = sorted((RAW_ROOT / source).glob("dt=*/*.parquet"))[-1]
    return pq.read_table(path).to_pylist()


def match_recalls(recalls: list[dict], ndc: list[dict]) -> dict[str, tuple[str, list[str]]]:
    """Return {recall_number: (method, matched 9-digit product keys)} for matched recalls."""
    by_key = {product_key(p["product_ndc"]): p for p in ndc if product_key(p["product_ndc"])}
    by_firm = defaultdict(list)
    for p in ndc:
        by_firm[firm_key(p["labeler_name"])].append(p)

    # Generic names as word tuples; very short single words (water, zinc) are too ambiguous to match on
    generics = {tuple(_words(p["generic_name"])) for p in ndc}
    generics = {g for g in generics if g and (len(g) > 1 or len(g[0]) >= 5)}

    out = {}
    for r in recalls:
        text = f"{r['product_description']} {r.get('code_info') or ''}"
        found = []

        block = json.loads(r["openfda"]) if r.get("openfda") else {}
        keys = [product_key(n) for n in block.get("product_ndc", [])]
        if hits := [k for k in keys if k in by_key]:
            out[r["recall_number"]] = ("openfda_block", sorted(set(hits)))
            continue

        for norm, has_kw in extract_ndcs(text):
            if norm[:9] in by_key:
                found.append((norm[:9], has_kw))
        if found:
            kw = [k for k, has_kw in found if has_kw]
            out[r["recall_number"]] = ("ndc_keyword", sorted(set(kw))) if kw else ("ndc_bare", sorted({k for k, _ in found}))
            continue

        desc = r["product_description"].lower()
        hits = {product_key(p["product_ndc"]) for p in by_firm.get(firm_key(r["recalling_firm"]), []) if p["generic_name"].lower() in desc}
        if hits:
            out[r["recall_number"]] = ("firm_text", sorted(hits))
            continue

        w = _words(r["product_description"])
        grams = {tuple(w[i : i + n]) for n in range(1, 5) for i in range(len(w) - n + 1)}
        if names := sorted(" ".join(g) for g in grams & generics):
            out[r["recall_number"]] = ("generic_name", names)
    return out


def main() -> None:
    recalls, ndc = latest("enforcement"), latest("ndc")
    matched = match_recalls(recalls, ndc)
    methods = Counter(m for m, _ in matched.values())
    n = len(recalls)
    print(f"recalls: {n}, matched: {len(matched)} ({len(matched) / n:.1%})")
    for m in ("openfda_block", "ndc_keyword", "ndc_bare", "firm_text", "generic_name"):
        print(f"  {m:14s} {methods[m]:6d} ({methods[m] / n:.1%})")
    # Share that carry an NDC-shaped string at all, to separate "no NDC to find" from "NDC not in directory"
    with_text = sum(bool(extract_ndcs(f"{r['product_description']} {r.get('code_info') or ''}")) for r in recalls)
    print(f"recalls with an NDC-shaped string in text: {with_text} ({with_text / n:.1%})")
    strong = sum(m != "generic_name" for m, _ in matched.values())
    print(f"matched to a specific product (excluding generic_name): {strong} ({strong / n:.1%})")
    recent = [r for r in recalls if r["report_date"] >= "20230101"]
    rm = sum(r["recall_number"] in matched for r in recent)
    print(f"recalls reported since 2023: {len(recent)}, matched: {rm} ({rm / len(recent):.1%})")
    # The directory only lists currently marketed products, so older recalls lose their NDC match
    for y in ("2018", "2021", "2024", "2026"):
        ys = [r for r in recalls if r["report_date"].startswith(y)]
        print(f"  {y}: {sum(r['recall_number'] in matched for r in ys) / len(ys):.0%} of {len(ys)}")


if __name__ == "__main__":
    main()
