"""Watchlist weights and pseudo out-of-time validation (design in docs/analysis_plan.md).

Points = round(coefficient / log(1.25)): one point is a 25% rise in odds. Negative results give 0 points.
Writes warehouse/seeds/risk_weights.csv and analysis.validation / analysis.risk_points.

Run: python -m analysis.risk_score
"""
import numpy as np
import pandas as pd
from statsmodels.discrete.conditional_models import ConditionalLogit

from analysis.common import ROOT, SEED, write_table
from analysis.risk_factors import contrasts, design, informative, load

POINT_UNIT = np.log(1.25)
TEST_FROM = pd.Timestamp("2025-01-01")
N_BOOT = 2000
WEIGHTS_SEED = ROOT / "warehouse" / "seeds" / "risk_weights.csv"

# Watchlist signal -> (model term or contrast, reason shown to the user)
SIGNALS = {
    "generic_multi_source": ("multi_source_generic", "generic product with several suppliers"),
    "sole_source_brand": ("sole_source_brand", "sole-source brand product"),
    "sole_source_generic": ("sole_source_generic", "sole-source generic product"),
    "injectable": ("injectable", "injectable dosage form"),
    "recall_product_24m": ("recall_product", "Class I or II recall of this product in the last 24 months"),
    "recall_ingredient_24m": ("recall_ingredient", "recall of the same ingredient (form unverified) in the last 24 months"),
    "warning_letter_24m": ("warning_letter", "warning letter to a marketing firm in the last 24 months"),
}
# Shown on the watchlist but never scored: exploratory estimate and only about 57% precise
INFORMATIONAL = {"recall_ingredient_24m"}


def fit(df, x):
    cols = informative(x, df.set_id)
    res = ConditionalLogit(df.role.eq("case").astype(float).values, x[cols].values, groups=df.set_id.values).fit(disp=False, method="bfgs", maxiter=500)
    return cols, np.asarray(res.params), np.asarray(res.cov_params())


def set_auc(df, score) -> pd.Series:
    """Per set: share of controls the case outranks (ties count half)."""
    d = pd.DataFrame({"set_id": df.set_id.values, "case": df.role.eq("case").values, "s": np.asarray(score)})
    case = d[d.case].set_index("set_id").s
    ctrl = d[~d.case].merge(case.rename("cs"), left_on="set_id", right_index=True)
    ctrl["win"] = (ctrl.cs > ctrl.s) + 0.5 * (ctrl.cs == ctrl.s)
    return ctrl.groupby("set_id").win.mean()


def lookup(df, x):
    """Coefficient and standard error for every model term and contrast."""
    cols, beta, cov = fit(df, x)
    out = {c: (b, float(np.sqrt(cov[i, i]))) for i, (c, b) in enumerate(zip(cols, beta))}
    for name, v in contrasts(None, cols):
        if v.any():
            out[name] = (float(v @ beta), float(np.sqrt(v @ cov @ v)))
    return out


def to_points(coef: float) -> int:
    return max(0, int(round(coef / POINT_UNIT)))


def score_points(df, x) -> tuple[dict[str, int], dict[str, str], dict]:
    """Points per signal from the primary model, kept only if the estimate survives adjustment for product count.

    A family with more products has more chances to be listed, so a signal whose points round to zero after adding
    log(product count) is dropped (post-hoc rule, recorded in the analysis plan). Returns points, status, primary lookup.
    """
    primary = lookup(df, x)
    xa = x.copy()
    xa["log_products"] = np.log(df.n_products.clip(lower=1))
    adjusted = lookup(df, xa)
    pts, status = {}, {}
    for signal, (term, _) in SIGNALS.items():
        p, pa = to_points(primary[term][0]), to_points(adjusted[term][0])
        if signal in INFORMATIONAL:
            pts[signal], status[signal] = 0, "informational: shown, not scored"
        elif p > 0 and pa == 0:
            pts[signal], status[signal] = 0, "dropped: not robust to product-count adjustment"
        else:
            pts[signal], status[signal] = p, "primary model" if p > 0 else "primary model (no positive effect)"
    return pts, status, primary


def signal_flags(x: pd.DataFrame) -> pd.DataFrame:
    """0/1 indicator per watchlist signal from the design matrix."""
    return pd.DataFrame({
        "generic_multi_source": x.generic * (1 - x.sole), "sole_source_brand": x.sole * (1 - x.generic),
        "sole_source_generic": x.sole * x.generic, "injectable": x.injectable,
        "recall_product_24m": x.recall_product, "recall_ingredient_24m": x.recall_ingredient, "warning_letter_24m": x.warning_letter,
    })


def validate(df, first_recall, first_letter) -> pd.DataFrame:
    x = design(df, first_recall, first_letter)
    case_date = df[df.role == "case"].set_index("set_id").as_of_date
    train_sets = case_date[case_date < TEST_FROM].index
    test_sets = case_date[case_date >= TEST_FROM].index
    tr, te = df.set_id.isin(train_sets), df.set_id.isin(test_sets)
    cols, beta, _ = fit(df[tr], x[tr])
    pts, _, _ = score_points(df[tr], x[tr])
    flags = signal_flags(x[te])
    scores = {
        "shipped points score": set_auc(df[te], sum(flags[k] * v for k, v in pts.items())),
        "model linear predictor": set_auc(df[te], x[te][cols].values @ beta),
        "baseline: injectable only": set_auc(df[te], x[te].injectable.values),
        "baseline: fewer suppliers": set_auc(df[te], -df[te].n_suppliers.values.astype(float)),
    }
    rng = np.random.default_rng(SEED)
    rows = []
    for name, auc in scores.items():
        v = auc.values
        boots = [rng.choice(v, len(v)).mean() for _ in range(N_BOOT)]
        rows.append({"score": name, "auc": v.mean(), "ci_low": np.percentile(boots, 2.5), "ci_high": np.percentile(boots, 97.5),
                     "n_train_cases": len(train_sets), "n_test_cases": len(test_sets),
                     "note": "optimistic: supplier counts are measured today, so they carry information from after the case date"})
    # Paired comparison on the same resampled sets: does the shipped score beat injectable status alone?
    a, b = scores["shipped points score"], scores["baseline: injectable only"].reindex(scores["shipped points score"].index)
    idx = np.random.default_rng(SEED).integers(0, len(a), size=(N_BOOT, len(a)))
    diff = (a.values[idx] - b.values[idx]).mean(axis=1)
    rows.append({"score": "difference: shipped minus injectable only", "auc": (a - b).mean(), "ci_low": np.percentile(diff, 2.5),
                 "ci_high": np.percentile(diff, 97.5), "n_train_cases": len(train_sets), "n_test_cases": len(test_sets),
                 "note": "paired bootstrap over test sets; an interval above zero means the extra signals add value"})
    return pd.DataFrame(rows)


def points(df, first_recall, first_letter) -> pd.DataFrame:
    x = design(df, first_recall, first_letter)
    pts, status, primary = score_points(df, x)
    rows = []
    for signal, (term, reason) in SIGNALS.items():
        b, se = primary[term]
        rows.append({"signal": signal, "points": pts[signal], "reason": reason, "status": status[signal],
                     "odds_ratio": np.exp(b), "ci_low": np.exp(b - 1.96 * se), "ci_high": np.exp(b + 1.96 * se)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df, fr, fl = load()
    val = validate(df, fr, fl)
    pts = points(df, fr, fl)
    pts.round(4).to_csv(WEIGHTS_SEED, index=False)
    write_table("validation", val)
    write_table("risk_points", pts)
    pd.set_option("display.width", 200)
    print(val.round(3).drop(columns="note").to_string(index=False))
    print(pts.round(3).to_string(index=False))
