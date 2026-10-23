"""Precision of ingredient-level recall matches, from the labelled sample in the seed file.

  draw:    python -m analysis.precision draw     prints the 100 sampled pairs (seeded) for labelling
  default: python -m analysis.precision          computes precision with a Wilson 95% interval

Precision uses only warehouse/seeds/ingredient_match_labels.csv, so later recall pulls do not change it.
"""
import sys
from math import sqrt

import pandas as pd

from analysis.common import ROOT, SEED, query, write_table

LABELS = ROOT / "warehouse" / "seeds" / "ingredient_match_labels.csv"
N_SAMPLE = 100


def draw() -> pd.DataFrame:
    """First N pairs (recall, matched generic name) in md5 order; shows only text, nothing about families."""
    return query(f"""
        select m.recall_number, m.matched_key as matched_ingredient, r.product_description
        from int_recall_match m join stg_enforcement r using (recall_number)
        where m.method = 'generic_name'
        order by md5(m.recall_number || '|' || m.matched_key || '|' || '{SEED}')
        limit {N_SAMPLE}""")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion; behaves well for small n and extreme p."""
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def compute() -> pd.DataFrame:
    labels = pd.read_csv(LABELS, dtype={"recall_number": str})
    n = len(labels)
    correct = int((labels.label == 1).sum())
    unclear = int((labels.note.fillna("").str.startswith("unclear")).sum())
    lo, hi = wilson(correct, n)
    # Lenient: also count the unclear cases (a salt or ester of the matched name) as correct
    llo, lhi = wilson(correct + unclear, n)
    out = pd.DataFrame([{
        "n_labelled": n, "n_correct": correct, "n_unclear": unclear,
        "precision": correct / n, "ci_low": lo, "ci_high": hi,
        "lenient_precision": (correct + unclear) / n, "lenient_ci_low": llo, "lenient_ci_high": lhi,
        "labeller": "single labeller (the AI assistant), blind to family and outcome",
    }])
    print(out.to_string(index=False))
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "draw":
        draw().to_csv(sys.stdout, index=False)
    else:
        write_table("ingredient_match_precision", compute())
