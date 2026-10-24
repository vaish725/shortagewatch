---
title: Insights
---

```sql asof
select strftime(snapshot_date, '%Y-%m-%d') as asof from shortagewatch.overview
```

```sql claims
with m as (select * from shortagewatch.model_results),
orfmt as (select model, term, format('{:.2f} ({:.2f} to {:.2f})', odds_ratio, ci_low, ci_high) as e, odds_ratio as o from m)
select
  (select e from orfmt where model = 'primary' and term = 'injectable') as injectable,
  (select e from orfmt where model = 'primary' and term = 'sole_source_among_generics') as h1,
  (select e from orfmt where model = 'primary' and term = 'sole_source_brand') as brand,
  (select e from orfmt where model = 'primary' and term = 'recall_product') as recall,
  (select e from orfmt where model = 'primary' and term = 'warning_letter') as letter,
  (select e from orfmt where model = 'sens_no_large_firms' and term = 'warning_letter') as letter_nolarge,
  (select e from orfmt where model = 'sens_no_large_firms' and term = 'injectable') as inj_nolarge,
  (select max(n_cases) from m where model = 'primary') as n_cases,
  (select max(n_cases) from m where model = 'sens_no_large_firms') as n_nolarge
```

```sql val
select
  round(max(auc) filter (where score = 'shipped points score'), 2) as shipped,
  round(max(auc) filter (where score = 'baseline: injectable only'), 2) as inj_only,
  round(max(ci_low) filter (where score like 'difference%'), 2) as d_lo,
  round(max(ci_high) filter (where score like 'difference%'), 2) as d_hi,
  round(max(auc) filter (where score like 'difference%'), 2) as d,
  max(n_test_cases) as n_test
from shortagewatch.validation
```

```sql age
select
  max(median_days) filter (where "group" = 'active injectable') as inj,
  max(median_days) filter (where "group" = 'active other forms') as other
from shortagewatch.duration_age
```

```sql age_chart
select "group" as grp, median_days from shortagewatch.duration_age where "group" <> 'all active' order by 1
```

```sql km
select days, survival, ci_low, ci_high from shortagewatch.duration_km order by days
```

```sql km_meta
select max(n_resolved) as r, max(n_episodes) as n from shortagewatch.duration_km
```

```sql firms
select example_name, active_families from shortagewatch.firm_concentration order by active_families desc limit 10
```

```sql firm_top
select example_name as name, round(100 * share_of_active_families) as pct from shortagewatch.firm_concentration order by active_families desc limit 1
```

```sql val_tbl
select score, auc, ci_low, ci_high from shortagewatch.validation order by case when score like 'difference%' then 1 else 0 end, auc desc
```

```sql man
select analysis_run_date_utc as run_date, data_snapshot_cutoff as cutoff, substr(code_commit, 1, 7) as short, code_commit as full from shortagewatch.analysis_manifest
```

```sql forest
select svg from shortagewatch.forest_svg
```

<p class="text-sm">Data as of <b>{asof[0].asof}</b> (UTC).</p>

<Alert status="warning">Not medical advice. These are associations in public FDA data, not causes.</Alert>

<p class="text-sm">Analysis frozen on {man[0].run_date}, using data through {man[0].cutoff}, code commit <a href="https://github.com/vaish725/shortagewatch/commit/{man[0].full}">{man[0].short}</a>. The overview, active shortages and watchlist update daily; the results on this page are fixed so they match the pre-committed plan and the write-up.</p>

## What the evidence says

- **Injectable drugs are the clearest risk factor.** Their odds of entering shortage are {claims[0].injectable} times those of other forms.
- **The hypothesis that sole-source generics are the fragile case was not supported.** Sole source among generics: odds ratio {claims[0].h1}. Sole-source brands are, if anything, less likely to go short: {claims[0].brand}.
- **A recent product-level recall and a warning letter to a marketing firm each go with a higher risk**, at {claims[0].recall} and {claims[0].letter}.
- **The warning letter result is fragile.** Without the largest manufacturers it becomes {claims[0].letter_nolarge}. Read it as "associated with shortages, driven by large manufacturers", not as a robust risk factor.

The analysis plan, including the four hypotheses, was committed before any model was fitted (see Methodology). Based on {claims[0].n_cases} shortage families, each compared with 5 drugs not in shortage on the same date.

## Which findings hold up across checks

Each risk factor is shown for the primary model (blue, filled) and for variations of it. Bars crossing the dashed line at 1 mean the data cannot rule out no association.

{@html forest[0].svg}

Supplier counts describe today's market, not the market before each shortage, so supplier results are associations with current supply structure. The "adjusted for product count" row was added after seeing the first results, to test whether families with many products simply have more chances to be listed; it explained part of the pattern but did not change the conclusions. "Without large firms" keeps {claims[0].n_nolarge} of the {claims[0].n_cases} cases.

## How well does the score rank drugs?

<Alert status="info">
On {val[0].n_test} shortages from 2025 to 2026, held out of the fitting, the score reaches an area under the curve (AUC) of {val[0].shipped}, against {val[0].inj_only} for ranking by injectable form alone (0.5 is a coin flip, 1 is perfect). The paired difference is {val[0].d} (95% interval {val[0].d_lo} to {val[0].d_hi}), so recalls and warning letters add some value beyond injectable form. This is optimistic because supplier counts are measured today. It is a prioritisation aid, not a prediction.
</Alert>

<DataTable data={val_tbl} rows=6>
  <Column id=score title="Ranking" />
  <Column id=auc fmt='0.00' title="AUC" />
  <Column id=ci_low fmt='0.00' title="Lower 95%" />
  <Column id=ci_high fmt='0.00' title="Upper 95%" />
</DataTable>

## How long do shortages last?

<BarChart data={age_chart} x=grp y=median_days title="Active injectable shortages have lasted a median of {Math.round(age[0].inj)} days, against {Math.round(age[0].other)} for other forms" yAxisTitle="Median age in days" xAxisTitle="" />

Ages count from the FDA posting date. Shortages that resolved long ago may have dropped out of the feed, so these lean long.

<LineChart data={km} x=days y={['survival','ci_low','ci_high']} title="Preliminary: only {km_meta[0].r} of {km_meta[0].n} shortage episodes have resolved, so the resolution curve is nearly flat" yAxisTitle="Share still in shortage" xAxisTitle="Days since the shortage started" yMin=0 yMax=1 />

With so few resolved episodes the interval is wide and no tests are run. The picture improves as the daily snapshots record more resolutions.

## Who is involved in shortages?

<BarChart data={firms} x=example_name y=active_families swapXY=true title="{firm_top[0].name} is involved in {firm_top[0].pct}% of active shortage families" yAxisTitle="Active shortage families involved" xAxisTitle="" />

A family with several makers counts once for each firm group involved.
