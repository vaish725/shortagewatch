-- One row per shortage-affected family per day, from the first known shortage start to the latest snapshot.
-- Days before the first snapshot are reconstructed from record posting and update dates (is_observed = false);
-- from the first snapshot on they are observed. Older resolved shortages may have dropped out of the feed,
-- so inferred days understate history.
with bounds as (
    select min(start_date) as first_day, (select max(dt) from {{ ref('stg_shortages') }}) as last_day,
           (select min(dt) from {{ ref('stg_shortages') }}) as first_snapshot
    from {{ ref('int_shortage_episodes') }}
),
families as (select distinct family_key from {{ ref('fct_shortage_events') }}),
days as (
    select unnest(generate_series(first_day, last_day, interval 1 day))::date as day, first_snapshot from bounds
)
select
    f.family_key,
    d.day,
    e.episode_number,
    e.episode_number is not null as in_shortage,
    count(distinct r.record_key) as n_records_in_shortage,
    d.day >= d.first_snapshot as is_observed
from families f
cross join days d
left join {{ ref('fct_shortage_events') }} e on e.family_key = f.family_key
 and e.start_date <= d.day and (e.end_date is null or d.day <= e.end_date)
left join {{ ref('int_shortage_record_intervals') }} r on r.family_key = f.family_key
 and r.start_date <= d.day and (r.end_date is null or d.day <= r.end_date)
group by f.family_key, d.day, e.episode_number, d.first_snapshot
