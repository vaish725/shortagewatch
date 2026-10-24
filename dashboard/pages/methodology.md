---
title: Methodology and data
---

```sql asof
select strftime(snapshot_date, '%Y-%m-%d') as asof from shortagewatch.overview
```

```sql dq
select area, metric, value, detail from shortagewatch.data_quality
where metric in ('total', 'match_rate_all_methods', 'match_rate_product_level', 'match_rate_all_methods_24m', 'match_rate_product_level_24m',
                 'match_rate_to_family', 'match_rate_ndc_based', 'snapshots', 'letters', 'drug_related_letters')
order by area, metric
```

```sql runs
select replace(metric, 'landed_', '') as source, cast(value as integer) as records, detail as last_run
from shortagewatch.data_quality where metric like 'landed_%' order by 1
```

```sql quarantined
select replace(metric, 'quarantined_', '') as source, cast(value as integer) as quarantined
from shortagewatch.data_quality where metric like 'quarantined_%' order by 1
```

```sql prec
select
  format('{:.0f}% (95% interval {:.0f}% to {:.0f}%)', 100 * precision, 100 * ci_low, 100 * ci_high) as strict,
  format('{:.0f}% ({:.0f}% to {:.0f}%)', 100 * lenient_precision, 100 * lenient_ci_low, 100 * lenient_ci_high) as lenient,
  n_labelled
from shortagewatch.precision
```

```sql ncases
select max(n_cases) as n from shortagewatch.model_results where model = 'primary'
```

```sql pts
select signal, points, reason, status from shortagewatch.risk_points order by points desc, signal
```

<p class="text-sm">Data as of <b>{asof[0].asof}</b> (UTC).</p>

<Alert status="warning">
Not medical advice. ShortageWatch uses public FDA data for analytical and educational purposes. It is not a substitute for official FDA shortage information.
</Alert>

## What this is

Hospital pharmacy teams often learn about a drug shortage after alternatives are already being bought up. The warning signs are public but spread across separate FDA datasets with no shared key. ShortageWatch joins them, measures which signals have gone with past shortages, and ranks approved prescription drugs by those signals. It is a prioritisation aid for procurement, not a clinical tool.

## Sources and refresh

| Source | What it provides | Refresh |
|---|---|---|
| openFDA drug shortages | Current and resolved shortages, by package | Daily snapshot kept as history |
| openFDA drug enforcement | Recalls and their classification | Weekly, pulled in full |
| openFDA NDC directory | Marketed products, labelers, dosage forms | Weekly snapshot kept as history |
| FDA warning letters | Regulatory action against firms (export is partial: posted 2021-01 to 2026-04) | Weekly snapshot kept as history |

<DataTable data={runs} rows=6>
  <Column id=source />
  <Column id=records title="Records in last run" />
  <Column id=last_run title="Last run (UTC)" />
</DataTable>

Records failing schema checks are set aside rather than loaded:

<DataTable data={quarantined} rows=6 />

If a pipeline run fails, this site keeps the last good build and the date above shows how fresh it is.

## Definitions

- **Product family:** active ingredients plus dosage form, release profile (immediate, extended, delayed, liposomal) and route. Procurement teams substitute at this level.
- **Sole source:** one firm group (parent company where known) markets the family today.
- **Shortage episode:** overlapping shortage listings for a family merge into one episode; a gap, or a listing resolved and then reopened, starts a new one.
- **Watchlist population:** approved (NDA, ANDA, BLA) human prescription drugs. Over-the-counter, unapproved and homeopathic products are excluded.

## How the ranking was built

A case-control study with {ncases[0].n} shortage families, each compared with 5 sampled families that were on the market and not in shortage on the same date, using conditional logistic regression. The plan, including the hypotheses and sensitivity checks, was committed before any model was fitted, so the results cannot have been chosen after the fact: [analysis plan](https://github.com/vaish725/shortagewatch/blob/main/docs/analysis_plan.md) and [its commit](https://github.com/vaish725/shortagewatch/commit/1c0f212). Deviations made afterwards are listed in the same file.

Points per signal come from the primary model (one point is a 25% rise in odds):

<DataTable data={pts} rows=8>
  <Column id=signal />
  <Column id=points />
  <Column id=reason />
  <Column id=status />
</DataTable>

Recall and warning-letter terms are set to zero for matched sets whose look-back window starts before the data does. Each set shares one date, so such a set has no variation in that term and drops out of its estimate; it is not treated as "no recall" or "no letter".

## Match quality

<DataTable data={dq} rows=12>
  <Column id=area />
  <Column id=metric />
  <Column id=value fmt='0.000' />
  <Column id=detail />
</DataTable>

Recalls are linked to products by NDC found in the recall text where possible, and otherwise by firm and product name or by ingredient name. Ingredient-level matches cannot tell dosage forms apart. A hand-labelled sample of {prec[0].n_labelled} of them was {prec[0].strict} correct, or {prec[0].lenient} counting salt and ester forms of the matched name as correct. Because of that, ingredient-level recalls are shown on the watchlist for information and are never scored. The labels were made by one labeller, who was blind to which families were cases.

## Limits

- Results are associations, not causes: a recall and a shortage can share one cause.
- Supplier structure is measured today, so it may reflect the shortage rather than precede it.
- The FDA list counts shortages by its own definition, narrower than other trackers.
- Shortages that resolved before this project began may have left the feed, so durations lean long and only a handful of resolutions have been seen.
- Warning letters are partial and mostly reflect large manufacturers.

## Technical documentation

- [Data model documentation and lineage](https://vaish725.github.io/shortagewatch/dbt-docs/)
- [Write-up: what public FDA data can and cannot tell us](https://github.com/vaish725/shortagewatch/blob/main/docs/writeup.md)
- [Analysis plan, committed before any model was run](https://github.com/vaish725/shortagewatch/blob/main/docs/analysis_plan.md)
- [Source code and pipeline](https://github.com/vaish725/shortagewatch)
