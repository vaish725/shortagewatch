---
title: Watchlist
---

```sql asof
select strftime(snapshot_date, '%Y-%m-%d') as asof from shortagewatch.overview
```

```sql limits
select
  'This ranking is a prioritisation aid, not a prediction. On cases held out in time (2025 to 2026) it scores an AUC of '
  || round(max(auc) filter (where score = 'shipped points score'), 2) || ' (95% interval ' || round(max(ci_low) filter (where score = 'shipped points score'), 2)
  || ' to ' || round(max(ci_high) filter (where score = 'shipped points score'), 2) || '; 0.5 is a coin flip) and is optimistic. Ranking by injectable form alone scores '
  || round(max(auc) filter (where score = 'baseline: injectable only'), 2) || '.' as t
from shortagewatch.validation
```

```sql forms
select distinct dosage_form_base from shortagewatch.watchlist order by 1
```

```sql groups
select distinct therapeutic_group from shortagewatch.watchlist order by 1
```

<p class="text-sm">Data as of <b>{asof[0].asof}</b> (UTC).</p>

<Alert status="warning">Not medical advice. Verify against official FDA shortage information.</Alert>

## Which drugs to watch this week

Approved prescription drug families that are not in shortage today, ordered by a points score. Each point is a 25% rise in the odds of a shortage, estimated from a case-control study of past shortages. Injectable form carries the most weight; a recent product-level recall and a warning letter to a marketing firm add smaller amounts.

<Alert status="info">{limits[0].t}</Alert>

<Dropdown name=form data={forms} value=dosage_form_base title="Dosage form" multiple=true selectAllByDefault=true />
<Dropdown name=group data={groups} value=therapeutic_group title="Therapeutic group" multiple=true selectAllByDefault=true />
<Slider name=min_score title="Minimum score" min=2 max=12 step=1 defaultValue=2 size=large />

```sql filtered
select * from shortagewatch.watchlist
where dosage_form_base in ${inputs.form.value}
  and therapeutic_group in ${inputs.group.value}
  and score >= ${inputs.min_score}
order by rank
```

```sql breakdown
select
  w.ingredient_list || ' (' || lower(w.dosage_form_base) || ')' as family,
  r.reason,
  r.points
from shortagewatch.watchlist_reasons r
join shortagewatch.watchlist w using (rank)
where w.rank <= 20
order by w.rank
```

```sql top_title
select 'The top 20 are driven by injectable form plus a recent recall or warning letter' as t
```

<DataTable data={filtered} search=true rows=15 downloadable=true>
  <Column id=rank />
  <Column id=ingredient_list title="Ingredients" />
  <Column id=dosage_form_base title="Form" />
  <Column id=score />
  <Column id=reason_text title="Why it is flagged" wrap=true />
  <Column id=same_ingredient_recall_unverified title="Same-ingredient recall (unverified)" />
  <Column id=n_suppliers title="Suppliers" />
  <Column id=last_recall_product_date title="Last product recall" />
</DataTable>

"Same-ingredient recall, form unverified" is shown for information and adds no points: that match is only about 57% accurate because it cannot tell dosage forms apart.

## How the top 20 get their scores

<BarChart data={breakdown} x=family y=points series=reason type=stacked swapXY=true title={top_title[0].t} yAxisTitle="Points" />

The download button above the table exports the filtered list as CSV.
