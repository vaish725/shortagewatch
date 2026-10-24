"""Export the tables the dashboard reads from the warehouse to CSV files in dashboard/sources/shortagewatch/.

CSV keeps the dashboard independent of the DuckDB file version. The files are build artifacts (not committed).
Live tables come from the warehouse (`make transform`); inference tables come from the committed analysis/results/.
Run:  python -m analysis.export_dashboard
"""
import json

import pandas as pd

from analysis.common import ROOT, connect

OUT = ROOT / "dashboard" / "sources" / "shortagewatch"
RESULTS = ROOT / "analysis" / "results"

# name -> query. Pre-aggregated marts only: the daily fact table never reaches the static site.
TABLES = {
    "overview": "select * from mart_overview",
    "trend": "select week_start, families_in_shortage, is_observed from mart_shortage_trend_weekly where week_start >= date '2015-01-01' order by 1",
    "active_shortages": "select * exclude (episode_key, family_key) from mart_active_shortages order by age_days desc",
    "watchlist": "select * exclude (reasons, family_key) from mart_watchlist order by rank",
    "watchlist_reasons": "select w.rank, r.signal, r.points, r.reason from mart_watchlist_reasons r join mart_watchlist w using (family_key) order by w.rank, r.points desc",
    "firm_concentration": "select example_name, active_families, share_of_active_families from mart_firm_concentration order by active_families desc limit 15",
    "data_quality": "select area, metric, value, detail from mart_data_quality order by area, metric",
}


# Frozen inference: these come from analysis/results/ (committed), never from the live warehouse
FROZEN = {
    "model_results": "model, term, kind, odds_ratio, ci_low, ci_high, p_value, confirmatory, p_holm, n_cases, converged, notes",
    "risk_points": "signal, points, reason, status, odds_ratio, ci_low, ci_high",
    "validation": "score, auc, ci_low, ci_high, n_train_cases, n_test_cases, note",
    "precision": "*",
    "duration_age": "*",
    "duration_km": "days, survival, ci_low, ci_high, n_episodes, n_resolved, status",
}
FROZEN_FILES = {"precision": "ingredient_match_precision", "duration_age": "duration_age_summary"}

FOREST_TERMS = [
    ("sole_source_among_generics", "Sole source among generics (H1, not supported)"),
    ("injectable", "Injectable form (H2)"),
    ("recall_product", "Product-level recall, 24 months (H3)"),
    ("warning_letter", "Warning letter to a marketing firm (H4)"),
    ("sole_source_brand", "Sole-source brand (exploratory)"),
    ("recall_ingredient", "Same-ingredient recall, form unverified (exploratory)"),
]
FOREST_MODELS = [
    ("primary", "Primary model"),
    ("sens_no_ingredient_recall", "Without ingredient-level recalls"),
    ("sens_recent_cases", "Cases from the last 12 months"),
    ("sens_window_12m", "12-month windows"),
    ("sens_window_36m", "36-month windows"),
    ("sens_no_large_firms", "Without large firms"),
    ("explore_log_products", "Adjusted for product count (post hoc)"),
    ("check_plain_logit", "Plain logistic check"),
]


def forest_svg(results) -> str:
    """Forest plot of odds ratios as a static inline SVG (log scale), grouped by risk factor, primary model first.

    Static SVG renders at build time, scales to phone width and takes its colours from the page text colour.
    """
    import math

    lo_axis, hi_axis = 0.1, 16.0
    width, label_w, row_h, head_h, pad = 760, 330, 19, 26, 8
    plot_l, plot_r = label_w + 10, width - 20

    def x(v: float) -> float:
        v = min(max(v, lo_axis), hi_axis)
        return plot_l + (math.log(v) - math.log(lo_axis)) / (math.log(hi_axis) - math.log(lo_axis)) * (plot_r - plot_l)

    lookup = {(r.model, r.term): r for r in results.itertuples()}
    out, y = [], pad
    for term, term_label in FOREST_TERMS:
        rows = [(m, lab) for m, lab in FOREST_MODELS if (m, term) in lookup]
        if not rows:
            continue
        out.append(f'<text x="0" y="{y + 14}" font-weight="700" font-size="13" fill="currentColor">{term_label}</text>')
        y += head_h
        for model, label in rows:
            r = lookup[(model, term)]
            primary = model == "primary"
            cy = y + row_h / 2
            colour = "#2563eb" if primary else "currentColor"
            out.append(f'<text x="14" y="{cy + 4}" font-size="12" fill="currentColor" opacity="{1 if primary else 0.8}">{label} (n={int(r.n_cases)})</text>')
            out.append(f'<line x1="{x(r.ci_low):.1f}" y1="{cy}" x2="{x(r.ci_high):.1f}" y2="{cy}" stroke="{colour}" stroke-width="{2.5 if primary else 1.5}"/>')
            fill = colour if primary else "none"
            out.append(f'<circle cx="{x(r.odds_ratio):.1f}" cy="{cy}" r="{4.5 if primary else 3.5}" fill="{fill}" stroke="{colour}" stroke-width="1.5"/>')
            y += row_h
        y += 8
    axis_y = y + 4
    out.append(f'<line x1="{x(1):.1f}" y1="{pad}" x2="{x(1):.1f}" y2="{axis_y}" stroke="currentColor" stroke-dasharray="4 3" opacity="0.6"/>')
    out.append(f'<line x1="{plot_l}" y1="{axis_y}" x2="{plot_r}" y2="{axis_y}" stroke="currentColor" opacity="0.5"/>')
    for t in (0.125, 0.25, 0.5, 1, 2, 4, 8):
        out.append(f'<line x1="{x(t):.1f}" y1="{axis_y}" x2="{x(t):.1f}" y2="{axis_y + 5}" stroke="currentColor" opacity="0.5"/>')
        out.append(f'<text x="{x(t):.1f}" y="{axis_y + 18}" font-size="11" text-anchor="middle" fill="currentColor">{t:g}</text>')
    out.append(f'<text x="{(plot_l + plot_r) / 2:.1f}" y="{axis_y + 34}" font-size="11" text-anchor="middle" fill="currentColor">Odds ratio of entering shortage (log scale; 1 = no association; bars are 95% intervals)</text>')
    height = axis_y + 42
    return (f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Forest plot of odds ratios for each risk factor across the primary and sensitivity models" '
            f'style="width:100%;height:auto;max-width:{width}px">' + "".join(out) + "</svg>")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect()
    try:
        for name, sql in TABLES.items():
            path = OUT / f"{name}.csv"
            con.sql(f"copy ({sql}) to '{path}' (header, delimiter ',')")
            print(f"{name}: {con.sql(f'select count(*) from ({sql})').fetchall()[0][0]} rows")
        for name, cols in FROZEN.items():
            src = RESULTS / f"{FROZEN_FILES.get(name, name)}.csv"
            con.sql(f"copy (select {cols} from read_csv('{src}')) to '{OUT / (name + '.csv')}' (header, delimiter ',')")
        manifest = json.loads((RESULTS / "manifest.json").read_text())
        pd.DataFrame([manifest]).to_csv(OUT / "analysis_manifest.csv", index=False)
        results = con.sql(f"select model, term, odds_ratio, ci_low, ci_high, n_cases from read_csv('{RESULTS / 'model_results.csv'}')").df()
    finally:
        con.close()
    pd.DataFrame({"svg": [forest_svg(results)]}).to_csv(OUT / "forest_svg.csv", index=False)
    print("forest_svg: 1 row")


if __name__ == "__main__":
    main()
