"""Shortage duration: descriptive ages of active shortages and a preliminary Kaplan-Meier curve.

Only a handful of episodes are resolved, so no tests or regression are fitted. Active episodes are right-censored
at the latest snapshot. Shortages that resolved long ago may have left the feed, so observed durations lean long.

Run: python -m analysis.duration
"""
import pandas as pd
from lifelines import KaplanMeierFitter

from analysis.common import query, write_table


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    ep = query("""
        select e.episode_key, e.duration_days, e.is_active, d.dosage_form_base = 'INJECTION' as injectable
        from fct_shortage_events e join dim_product_family d using (family_key)""")
    active = ep[ep.is_active]
    groups = {"all active": active, "active injectable": active[active.injectable], "active other forms": active[~active.injectable]}
    ages = pd.DataFrame([{
        "group": g, "n": len(d), "median_days": d.duration_days.median(),
        "q25_days": d.duration_days.quantile(0.25), "q75_days": d.duration_days.quantile(0.75), "max_days": d.duration_days.max(),
    } for g, d in groups.items()])

    kmf = KaplanMeierFitter()
    kmf.fit(ep.duration_days, event_observed=(~ep.is_active).astype(int))
    km = kmf.survival_function_.join(kmf.confidence_interval_).reset_index()
    km.columns = ["days", "survival", "ci_low", "ci_high"]
    km["n_episodes"] = len(ep)
    km["n_resolved"] = int((~ep.is_active).sum())
    km["status"] = "preliminary: few resolved episodes; long-resolved shortages may be missing from the feed"
    return ages, km


if __name__ == "__main__":
    ages, km = run()
    write_table("duration_age_summary", ages)
    write_table("duration_km", km)
    print(ages.round(0).to_string(index=False))
    print(f"Kaplan-Meier: {km.n_resolved.iloc[0]} resolved of {km.n_episodes.iloc[0]} episodes; "
          f"lowest survival {km.survival.min():.3f} (CI {km.ci_low.min():.3f} to {km.ci_high.max():.3f})")
