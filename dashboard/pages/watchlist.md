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

Approved prescription drug families that are not in shortage today, ordered by a points score. Each point is a 25% rise in the odds of a shortage, estimated from a case-control study of past shortages (recall and warning-letter windows are 24 months). Injectable form carries the most weight; a recent product-level recall and a warning letter to a marketing firm add smaller amounts.

<Alert status="info">{limits[0].t}</Alert>

```sql all_rows
select rank, ingredient_list, dosage_form_base, score, replace(replace(replace(reason_text, 'Class I or II recall of this product in the last 24 months', 'product recall, 24 months'), 'warning letter to a marketing firm in the last 24 months', 'warning letter, 24 months'), 'injectable dosage form', 'injectable') as reason_text,
  case when same_ingredient_recall_unverified then 'same-ingredient recall, form unverified' end as note
from shortagewatch.watchlist order by rank
```

```sql injectables
select rank, ingredient_list, route_key, score, replace(replace(replace(reason_text, 'Class I or II recall of this product in the last 24 months', 'product recall, 24 months'), 'warning letter to a marketing firm in the last 24 months', 'warning letter, 24 months'), 'injectable dosage form', 'injectable') as reason_text, last_recall_product_date
from shortagewatch.watchlist where dosage_form_base = 'INJECTION' order by rank limit 100
```

```sql recalled
select rank, ingredient_list, dosage_form_base, score, replace(replace(replace(reason_text, 'Class I or II recall of this product in the last 24 months', 'product recall, 24 months'), 'warning letter to a marketing firm in the last 24 months', 'warning letter, 24 months'), 'injectable dosage form', 'injectable') as reason_text, last_recall_product_date
from shortagewatch.watchlist where reason_text like '%Class I or II recall%' order by rank limit 100
```

```sql letters
select rank, ingredient_list, dosage_form_base, score, replace(replace(replace(reason_text, 'Class I or II recall of this product in the last 24 months', 'product recall, 24 months'), 'warning letter to a marketing firm in the last 24 months', 'warning letter, 24 months'), 'injectable dosage form', 'injectable') as reason_text, last_warning_letter_date
from shortagewatch.watchlist where reason_text like '%warning letter%' order by rank limit 100
```

```sql counts
select format('{:,}', count(*)) as n from shortagewatch.watchlist
```

All {counts[0].n} families are searchable in the first tab, and the other tabs are preset views of the top 100. Use the search box to filter by ingredient, form or reason, click a column heading to sort, and use the download button for CSV.

<Tabs>
<Tab label="All families">
<DataTable data={all_rows} search=true rows=15 downloadable=true>
  <Column id=rank />
  <Column id=ingredient_list title="Ingredients" />
  <Column id=dosage_form_base title="Form" />
  <Column id=score />
  <Column id=reason_text title="Why it is flagged" wrap=true />
  <Column id=note title="Note" wrap=true />
</DataTable>
</Tab>
<Tab label="Injectables">
<DataTable data={injectables} search=true rows=15 downloadable=true>
  <Column id=rank />
  <Column id=ingredient_list title="Ingredients" />
  <Column id=route_key title="Route" />
  <Column id=score />
  <Column id=reason_text title="Why it is flagged" wrap=true />
  <Column id=last_recall_product_date title="Last product recall" />
</DataTable>
</Tab>
<Tab label="Recent product recall">
<DataTable data={recalled} search=true rows=15 downloadable=true>
  <Column id=rank />
  <Column id=ingredient_list title="Ingredients" />
  <Column id=dosage_form_base title="Form" />
  <Column id=score />
  <Column id=reason_text title="Why it is flagged" wrap=true />
  <Column id=last_recall_product_date title="Last product recall" />
</DataTable>
</Tab>
<Tab label="Warning letter">
<DataTable data={letters} search=true rows=15 downloadable=true>
  <Column id=rank />
  <Column id=ingredient_list title="Ingredients" />
  <Column id=dosage_form_base title="Form" />
  <Column id=score />
  <Column id=reason_text title="Why it is flagged" wrap=true />
  <Column id=last_warning_letter_date title="Last warning letter" />
</DataTable>
</Tab>
</Tabs>

"Same-ingredient recall, form unverified" (the Note column) is shown for information and adds no points: that match is only about 57% accurate because it cannot tell dosage forms apart.

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

## How the top 20 get their scores

<BarChart data={breakdown} x=family y=points series=reason type=stacked swapXY=true title={top_title[0].t} yAxisTitle="Points" />

