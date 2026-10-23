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
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq

from ingestion.utils.ndc import extract_ndcs, product_key
from ingestion.utils.storage import RAW_ROOT, write_run_summary

_SUFFIX = re.compile(r"\b(?:and )?(?:inc|llc|ltd|limited|corp|corporation|co|company|lp|llp|plc|pharmacy)\b")


def firm_key(name: str) -> str:
    """Lowercase, drop punctuation, legal suffixes and a joining "and" so 'Pfizer Inc.' and 'PFIZER' agree."""
    s = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    return " ".join(_SUFFIX.sub(" ", s).split())


def _words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split()


def latest(source: str) -> list[dict]:
    # NDC_SNAPSHOT_DIR points parity runs at the same data/ snapshot dbt reads
    root = Path(os.getenv("NDC_SNAPSHOT_DIR", RAW_ROOT / "ndc")) if source == "ndc" else RAW_ROOT / source
    path = sorted(root.glob("dt=*/*.parquet"))[-1]
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


# Product-level methods identify a specific NDC product; generic_name only identifies the ingredient
# (one recall can map to several families), so the data model keeps the two levels apart.
LEVEL = {"openfda_block": "product", "ndc_keyword": "product", "ndc_bare": "product", "firm_text": "product", "generic_name": "ingredient"}


def summarize(recalls: list[dict], matched: dict) -> dict:
    """Match rates overall, by method, and within the 24 months before the latest report date."""
    n = len(recalls)
    by_method = Counter(m for m, _ in matched.values())
    product = sum(LEVEL[m] == "product" for m, _ in matched.values())
    latest_report = max(r["report_date"] for r in recalls)
    cutoff = f"{int(latest_report[:4]) - 2}{latest_report[4:]}"
    window = [r for r in recalls if r["report_date"] >= cutoff]
    in_window = [r["recall_number"] for r in window]
    return {
        "recalls": n,
        "matched": len(matched),
        "match_rate": round(len(matched) / n, 4),
        "product_level_rate": round(product / n, 4),
        "by_method": {m: by_method[m] for m in LEVEL},
        "window_start": cutoff,
        "window_recalls": len(window),
        "window_match_rate": round(sum(k in matched for k in in_window) / len(window), 4),
        "window_product_level_rate": round(sum(k in matched and LEVEL[matched[k][0]] == "product" for k in in_window) / len(window), 4),
    }


def main() -> None:
    recalls, ndc = latest("enforcement"), latest("ndc")
    stats = summarize(recalls, match_recalls(recalls, ndc))
    n = stats["recalls"]
    print(f"recalls: {n}, matched: {stats['matched']} ({stats['match_rate']:.1%}), product level: {stats['product_level_rate']:.1%}")
    for m, c in stats["by_method"].items():
        print(f"  {m:14s} {c:6d} ({c / n:.1%})  [{LEVEL[m]}]")
    print(f"24-month window from {stats['window_start']}: {stats['window_recalls']} recalls, "
          f"matched {stats['window_match_rate']:.1%}, product level {stats['window_product_level_rate']:.1%}")
    write_run_summary("recall_match", stats)


if __name__ == "__main__":
    main()
