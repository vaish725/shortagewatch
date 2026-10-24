---
title: ShortageWatch
---

```sql asof
select strftime(snapshot_date, '%Y-%m-%d') as asof from shortagewatch.overview
```

```sql kpi
select * from shortagewatch.overview
```

```sql trend_title
select
  'Shortages are at ' || cast(last(families_in_shortage order by week_start) as integer) || ' product families, up from '
  || cast(first(families_in_shortage order by week_start) filter (where week_start >= date '2022-01-01') as integer) || ' at the start of 2022' as t
from shortagewatch.trend
```

```sql trend
select week_start, families_in_shortage from shortagewatch.trend where week_start >= date '2018-01-01' order by 1
```

<p class="text-sm">Data as of <b>{asof[0].asof}</b> (UTC). Refreshed daily from public FDA data.</p>

<Alert status="warning">
Not medical advice. ShortageWatch is a procurement prioritisation aid built on public FDA data. Verify against official FDA shortage information before acting.
</Alert>

## What changed

{kpi[0].summary}

<BigValue data={kpi} value=active_shortages title="Active shortages" />
<BigValue data={kpi} value=new_this_week title="New this week" />
<BigValue data={kpi} value=resolved_this_week title="Resolved this week" />
<BigValue data={kpi} value=median_active_age_days title="Median active age (days)" fmt=num0 />

New and resolved counts come from FDA posting and update dates. They become exact snapshot comparisons as the daily snapshots accumulate (the first was taken on 2026-10-22).

## Trend

<LineChart data={trend} x=week_start y=families_in_shortage title={trend_title[0].t} yAxisTitle="Product families in shortage" xAxisTitle="Week" />

Weeks before the first snapshot (2026-10-22) are reconstructed from FDA posting dates. Shortages that resolved long ago may have left the feed, so earlier weeks understate history.

## Where to go next

- [Watchlist](/watchlist): approved prescription drugs not yet in shortage, ranked, with the reason for each flag.
- [Active shortages](/active-shortages): what is short now, how long, and why.
- [Insights](/insights): what the evidence says about which drugs go short.
- [Methodology and data](/methodology): sources, definitions, limits, pipeline status.
