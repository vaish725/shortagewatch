-- Shortage episodes per product family: overlapping or touching record intervals merge into one episode.
-- A family that goes Resolved and later Current again therefore has two episodes, not one long one.
-- end_date is NULL while any interval in the episode is still open.
with intervals as (
    select family_key, start_date, end_date, coalesce(end_date, date '9999-12-31') as end_filled, record_key
    from {{ ref('int_shortage_record_intervals') }}
    where start_date is not null
),
with_prior as (
    select
        *,
        max(end_filled) over (
            partition by family_key order by start_date, end_filled
            rows between unbounded preceding and 1 preceding
        ) as prior_max_end
    from intervals
),
numbered as (
    select
        *,
        sum(case when prior_max_end is null or start_date > prior_max_end then 1 else 0 end)
            over (partition by family_key order by start_date, end_filled) as episode_number
    from with_prior
),
as_of as (select max(dt) as snapshot_date from {{ ref('stg_shortages') }})
select
    md5(family_key || '#' || cast(episode_number as varchar)) as episode_key,
    family_key,
    episode_number,
    min(start_date) as start_date,
    case when max(end_filled) = date '9999-12-31' then null else max(end_filled) end as end_date,
    max(end_filled) = date '9999-12-31' as is_active,
    count(distinct record_key) as n_records,
    date_diff('day', min(start_date),
              case when max(end_filled) = date '9999-12-31' then (select snapshot_date from as_of) else max(end_filled) end) as duration_days
from numbered
group by family_key, episode_number
