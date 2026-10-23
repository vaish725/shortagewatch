-- The (family, as-of date) pairs risk signals are computed for. Signals use only information dated before the
-- as-of date, so the regression measures cases at their shortage start and controls at the same date.
--   current  every family, as of the latest shortage snapshot date (powers the watchlist)
--   case     each shortage episode, as of its start date
--   control  incidence-density sampling: for each case in the analysis population, controls_per_case families
--            drawn at random (seeded hash order) from approved prescription families that were already marketed
--            on the case date and not in shortage on it. A family can be a control for one case and a case later.
-- set_id ties a case to its controls (the matched set for conditional logistic regression).
with today as (select max(dt) as snapshot_date from {{ ref('stg_shortages') }}),
cases as (
    select episode_key as set_id, family_key, start_date as as_of_date, episode_number
    from {{ ref('fct_shortage_events') }}
    where start_date is not null
),
population as (
    select family_key, first_marketing_start_date from {{ ref('dim_product_family') }} where in_analysis_population
),
candidates as (
    select c.set_id, p.family_key, c.as_of_date
    from cases c
    join population p on p.family_key <> c.family_key and p.first_marketing_start_date < c.as_of_date
    where c.family_key in (select family_key from population)
      and not exists (
          select 1 from {{ ref('fct_shortage_events') }} e
          where e.family_key = p.family_key and e.start_date < c.as_of_date and (e.end_date is null or e.end_date >= c.as_of_date)
      )
),
drawn as (
    select *,
           row_number() over (partition by set_id order by md5(family_key || set_id || '{{ var("control_seed") }}')) as draw
    from candidates
)
select family_key, snapshot_date as as_of_date, 'current' as role, null::int as episode_number, null::varchar as set_id
from {{ ref('dim_product_family') }}, today
union all
select family_key, as_of_date, 'case', episode_number, set_id from cases
union all
select family_key, as_of_date, 'control', null::int, set_id from drawn where draw <= {{ var("controls_per_case") }}
