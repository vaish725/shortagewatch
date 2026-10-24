"""Risk-factor models for shortage entry (design in docs/analysis_plan.md).

Primary: conditional logistic regression over matched sets (one case + its sampled controls).
Sensitivity models change one thing each. Results go to analysis.model_results in the warehouse.

Run: python -m analysis.risk_factors
"""
import numpy as np
import pandas as pd
from statsmodels.discrete.conditional_models import ConditionalLogit
import statsmodels.api as sm

from analysis.common import query, write_table

THERAPEUTIC = ["oncology", "anti_infective", "cardiovascular", "cns_pain", "endocrine_metabolic"]
BASE_TERMS = ["sole", "generic", "sole_x_generic", "injectable", "recall_product", "recall_ingredient", "warning_letter"]
RECENT_CUTOFF = "2025-10-22"  # last 12 months before the 2026-10-22 snapshot


def load() -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    """Case and control rows in the analysis population, plus the first recall and warning letter dates."""
    df = query("""
        select set_id, role, family_key, as_of_date, n_suppliers, n_products, approval_class, is_injectable, therapeutic_group,
               has_large_firm_supplier, last_recall_product_date, last_recall_ingredient_date, last_warning_letter_date
        from fct_family_risk_signals
        where role in ('case', 'control') and in_analysis_population""")
    firsts = query("select (select min(report_date) from stg_enforcement) r, (select min(posted_date) from stg_warning_letters) l")
    for c in ("as_of_date", "last_recall_product_date", "last_recall_ingredient_date", "last_warning_letter_date"):
        df[c] = pd.to_datetime(df[c])
    return df, pd.Timestamp(firsts.r[0]), pd.Timestamp(firsts.l[0])


def design(df, first_recall, first_letter, recall_months=24, letter_months=24) -> pd.DataFrame:
    """Build the model matrix. A recall or letter term is 0 for a whole set when its look-back window starts
    before the data does (absence is then not evidence)."""
    x = pd.DataFrame(index=df.index)
    x["sole"] = (df.n_suppliers == 1).astype(float)
    x["generic"] = (df.approval_class == "generic").astype(float)
    x["sole_x_generic"] = x.sole * x.generic
    x["injectable"] = df.is_injectable.astype(float)

    def flag(last, months, first):
        covered = (df.as_of_date - pd.DateOffset(months=months)) >= first
        within = last >= (df.as_of_date - pd.DateOffset(months=months))
        return (within & covered).astype(float)

    x["recall_product"] = flag(df.last_recall_product_date, recall_months, first_recall)
    x["recall_ingredient"] = flag(df.last_recall_ingredient_date, recall_months, first_recall)
    x["warning_letter"] = flag(df.last_warning_letter_date, letter_months, first_letter)
    for g in THERAPEUTIC:
        x[f"tg_{g}"] = (df.therapeutic_group == g).astype(float)
    return x


def informative(x: pd.DataFrame, sets: pd.Series) -> list[str]:
    """Columns with some variation inside at least one set (the rest carry no information)."""
    within = x.groupby(sets).transform(lambda c: c - c.mean())
    return [c for c in x.columns if (within[c].abs() > 1e-12).any()]


def contrasts(res, cols) -> list[tuple[str, np.ndarray]]:
    """Linear combinations of coefficients reported alongside single terms."""
    def vec(**w):
        v = np.zeros(len(cols))
        for k, val in w.items():
            if k in cols:
                v[cols.index(k)] = val
        return v
    return [
        ("sole_source_brand", vec(sole=1)),
        ("multi_source_generic", vec(generic=1)),
        ("sole_source_generic", vec(sole=1, generic=1, sole_x_generic=1)),
        ("sole_source_among_generics", vec(sole=1, sole_x_generic=1)),
    ]


def fit_conditional(df, x, name, notes="") -> tuple[pd.DataFrame, object]:
    cols = informative(x, df.set_id)
    dropped = [c for c in x.columns if c not in cols]
    res = ConditionalLogit(df.role.eq("case").astype(float).values, x[cols].values, groups=df.set_id.values).fit(disp=False, method="bfgs", maxiter=500)
    beta, cov = np.asarray(res.params), np.asarray(res.cov_params())
    se = np.sqrt(np.diag(cov))
    n_cases = int(df.role.eq("case").sum())
    meta = dict(model=name, n_cases=n_cases, n_rows=len(df), converged=bool(np.isfinite(se).all() and np.abs(beta).max() < 15),  # finite SEs and no runaway coefficient (separation)
                notes=(notes + (f" dropped (no within-set variation): {', '.join(dropped)}." if dropped else "")).strip())
    rows = []
    for c, b, s in zip(cols, beta, se):
        rows.append({**meta, "term": c, "kind": "term", "coef": b, "se": s})
    for cname, v in contrasts(res, cols):
        if v.any():
            rows.append({**meta, "term": cname, "kind": "contrast", "coef": float(v @ beta), "se": float(np.sqrt(v @ cov @ v))})
    return finish(pd.DataFrame(rows)), res


def finish(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    z = t.coef / t.se
    from scipy.stats import norm
    t["odds_ratio"] = np.exp(t.coef)
    t["ci_low"] = np.exp(t.coef - 1.96 * t.se)
    t["ci_high"] = np.exp(t.coef + 1.96 * t.se)
    t["p_value"] = 2 * (1 - norm.cdf(np.abs(z)))
    return t


def holm(p: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjustment."""
    order = sorted(p, key=p.get)
    out, running = {}, 0.0
    for i, k in enumerate(order):
        running = max(running, min(1.0, (len(p) - i) * p[k]))
        out[k] = running
    return out


def plain_logit(df, x, name) -> pd.DataFrame:
    """Unconditional logistic regression on the same rows plus case-year groups, clustered by family."""
    yr = df.as_of_date.dt.year
    groups = pd.cut(yr, [0, 2018, 2022, 2024, 2025, 3000], labels=["le2018", "2019_22", "2023_24", "2025", "2026"])
    z = pd.concat([x, pd.get_dummies(groups, prefix="yr", drop_first=True, dtype=float)], axis=1)
    z = sm.add_constant(z)
    y = df.role.eq("case").astype(float)
    res = sm.Logit(y, z).fit(disp=False, cov_type="cluster", cov_kwds={"groups": pd.factorize(df.family_key)[0]})
    t = pd.DataFrame({"model": name, "term": z.columns, "kind": "term", "coef": res.params.values, "se": res.bse.values,
                      "n_cases": int(y.sum()), "n_rows": len(df), "converged": bool(res.mle_retvals["converged"]),
                      "notes": "unconditional logistic check with case-year indicators, cluster-robust SE by family"})
    return finish(t[t.term != "const"].copy())


def run_all() -> pd.DataFrame:
    df, first_recall, first_letter = load()
    out = []

    def conditional(name, sub, drop=(), recall_months=24, letter_months=24, notes=""):
        x = design(sub, first_recall, first_letter, recall_months, letter_months).drop(columns=list(drop))
        t, _ = fit_conditional(sub, x, name, notes)
        out.append(t)
        return t

    primary = conditional("primary", df, notes="24 month windows, all matched sets")
    conditional("sens_no_ingredient_recall", df, drop=["recall_ingredient"], notes="ingredient-level recall term removed")
    recent_sets = df[(df.role == "case") & (df.as_of_date >= RECENT_CUTOFF)].set_id
    conditional("sens_recent_cases", df[df.set_id.isin(recent_sets)], notes=f"cases starting on or after {RECENT_CUTOFF}")
    for m in (12, 36):
        conditional(f"sens_window_{m}m", df, recall_months=m, letter_months=m, notes=f"{m} month recall and warning letter windows")
    conditional("sens_no_large_firms", drop_large(df), notes="families with a top-10 firm group supplier removed")
    # Post-hoc, exploratory (added after the primary results; see Deviations in docs/analysis_plan.md): a family
    # with more products has more chances to be listed, which could explain the supplier results.
    x = design(df, first_recall, first_letter)
    x["log_products"] = np.log(df.n_products.clip(lower=1))
    t, _ = fit_conditional(df, x, "explore_log_products", "POST HOC: primary model plus log(number of product NDCs in the family)")
    out.append(t)
    x = design(df, first_recall, first_letter)
    out.append(plain_logit(df, x, "check_plain_logit"))

    res = pd.concat(out, ignore_index=True)
    # Holm adjustment over the four confirmatory hypotheses (primary model only)
    conf = {"sole_source_among_generics": "H1", "injectable": "H2", "recall_product": "H3", "warning_letter": "H4"}
    p = {k: float(primary.loc[primary.term == k, "p_value"].iloc[0]) for k in conf if (primary.term == k).any()}
    adj = holm(p)
    res["confirmatory"] = res.apply(lambda r: conf.get(r.term) if r.model == "primary" else None, axis=1)
    res["p_holm"] = res.apply(lambda r: adj.get(r.term) if r.model == "primary" and r.term in adj else None, axis=1)
    return res


def drop_large(df: pd.DataFrame) -> pd.DataFrame:
    """Remove families with a large-firm supplier from cases and controls, then keep sets that still have a case and a control."""
    d = df[~df.has_large_firm_supplier]
    ok = d.groupby("set_id").role.agg(lambda r: ("case" in set(r)) and ("control" in set(r)))
    return d[d.set_id.isin(ok[ok].index)]


if __name__ == "__main__":
    res = run_all()
    write_table("model_results", res)
    show = res[res.model == "primary"][["term", "kind", "odds_ratio", "ci_low", "ci_high", "p_value", "confirmatory", "p_holm"]]
    pd.set_option("display.width", 160)
    print(show.round(3).to_string(index=False))
    print(res.groupby("model").agg(n_cases=("n_cases", "first"), n_rows=("n_rows", "first"), converged=("converged", "all")))
