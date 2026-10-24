---
title: Active shortages
---

```sql asof
select strftime(snapshot_date, '%Y-%m-%d') as asof from shortagewatch.overview
```

```sql headline
select 'Half of active shortages are older than ' || cast(round(median(age_days)) as integer) || ' days' as t from shortagewatch.active_shortages
```

<p class="text-sm">Data as of <b>{asof[0].asof}</b> (UTC).</p>

<Alert status="warning">Not medical advice. Verify against official FDA shortage information.</Alert>

## {headline[0].t}

One row per product family in an active shortage. Age is counted from the FDA posting date, so it includes the whole time the family has been listed.

```sql filtered
select * from shortagewatch.active_shortages order by age_days desc
```

Search by ingredient, form, company or reason, or click a column heading to sort.

<DataTable data={filtered} search=true rows=15 downloadable=true>
  <Column id=ingredient_list title="Ingredients" />
  <Column id=dosage_form_base title="Form" />
  <Column id=status />
  <Column id=age_days title="Age (days)" fmt=num0 />
  <Column id=shortage_reason title="Reason given by FDA" wrap=true />
  <Column id=companies title="Companies" wrap=true />
  <Column id=n_recalls_product_24m title="Recalls, 24 months" />
</DataTable>

The FDA gives a reason for only some shortages, so that column is often blank. Recall history is limited to Class I and II recalls matched to this exact product by NDC.
