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
    "recall_ingredient_24m": ("recall_ingredient", "recall of the same ingredient (form unknown) in the last 24 months"),
    "warning_letter_24m": ("warning_letter", "warning letter to a marketing firm in the last 24 months"),
}


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


def validate(df, first_recall, first_letter) -> pd.DataFrame:
    x = design(df, first_recall, first_letter)
    case_date = df[df.role == "case"].set_index("set_id").as_of_date
    train_sets = case_date[case_date < TEST_FROM].index
    test_sets = case_date[case_date >= TEST_FROM].index
    tr, te = df.set_id.isin(train_sets), df.set_id.isin(test_sets)
    cols, beta, _ = fit(df[tr], x[tr])
    model_score = x[te][cols].values @ beta
    scores = {"primary model": set_auc(df[te], model_score),
              "baseline: fewer suppliers": set_auc(df[te], -df[te].n_suppliers.values.astype(float))}
    rng = np.random.default_rng(SEED)
    rows = []
    for name, auc in scores.items():
        v = auc.values
        boots = [rng.choice(v, len(v)).mean() for _ in range(N_BOOT)]
        rows.append({"score": name, "auc": v.mean(), "ci_low": np.percentile(boots, 2.5), "ci_high": np.percentile(boots, 97.5),
                     "n_train_cases": len(train_sets), "n_test_cases": len(test_sets),
                     "note": "optimistic: supplier counts are measured today, so they carry information from after the case date"})
    return pd.DataFrame(rows)


def points(df, first_recall, first_letter) -> pd.DataFrame:
    x = design(df, first_recall, first_letter)
    cols, beta, cov = fit(df, x)
    lookup = {c: (b, np.sqrt(cov[i, i])) for i, (c, b) in enumerate(zip(cols, beta))}
    for name, v in contrasts(None, cols):
        if v.any():
            lookup[name] = (float(v @ beta), float(np.sqrt(v @ cov @ v)))
    rows = []
    for signal, (term, reason) in SIGNALS.items():
        b, se = lookup[term]
        rows.append({"signal": signal, "points": max(0, int(round(b / POINT_UNIT))), "reason": reason, "status": "primary model",
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
