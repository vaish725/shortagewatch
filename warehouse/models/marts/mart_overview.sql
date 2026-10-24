-- Single-row KPIs and the auto-generated summary for the dashboard landing page. New and resolved counts use
-- episode start and end dates (posting and update dates in the FDA feed), so before the daily snapshots
-- accumulate they are an approximation of week-over-week change, not a snapshot diff.
with latest as (select max(dt) as snapshot_date from {{ ref('stg_shortages') }}),
k as (
    select
        (select snapshot_date from latest) as snapshot_date,
        count(*) filter (where is_active) as active_shortages,
        count(*) filter (where start_date > (select snapshot_date from latest) - 7) as new_7d,
        count(*) filter (where end_date > (select snapshot_date from latest) - 7) as resolved_7d,
        median(duration_days) filter (where is_active) as median_active_age_days,
        count(*) filter (where is_active) - count(*) filter (where is_active and start_date <= (select snapshot_date from latest) - 7)
            + count(*) filter (where end_date > (select snapshot_date from latest) - 7) as net_basis
    from {{ ref('fct_shortage_events') }}
),
top_form as (
    select dosage_form_base, count(*) n from {{ ref('mart_active_shortages') }} group by 1 order by n desc, 1 limit 1
)
select
    k.snapshot_date,
    k.active_shortages,
    k.new_7d as new_this_week,
    k.resolved_7d as resolved_this_week,
    k.median_active_age_days,
    (select count(*) from {{ ref('mart_watchlist') }}) as watchlist_families,
    format('{} product families are in an active shortage as of {}. {} started and {} resolved in the last 7 days. The most common dosage form among active shortages is {} and the median active shortage has lasted {} days.',
           k.active_shortages, k.snapshot_date, k.new_7d, k.resolved_7d, lower(t.dosage_form_base), cast(round(k.median_active_age_days) as integer)) as summary
from k cross join top_form t
