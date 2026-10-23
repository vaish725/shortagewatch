-- The (family, as-of date) pairs risk signals are computed for. Signals use only information dated before the
-- as-of date, so the regression can measure cases at their shortage start and controls at a reference date
-- without look-ahead bias.
--   current  every family, as of the latest shortage snapshot date (powers the watchlist)
--   case     each shortage episode, as of its start date
--   control  each family with no shortage episode, as of the start date of a case. Cases are numbered by start
--            date and controls are dealt out to them in a fixed order, so reference dates follow the case date
--            distribution and the assignment is reproducible. Week 6 can replace this with finer matching.
with today as (select max(dt) as snapshot_date from {{ ref('stg_shortages') }}),
cases as (
    select family_key, start_date as as_of_date, episode_number
    from {{ ref('fct_shortage_events') }}
    where start_date is not null
),
numbered_cases as (
    select *, row_number() over (order by as_of_date, family_key) as case_no, count(*) over () as n_cases from cases
),
controls as (
    select
        family_key,
        ((row_number() over (order by md5(family_key)) - 1) % (select count(*) from cases)) + 1 as case_no
    from {{ ref('dim_product_family') }}
    where family_key not in (select family_key from cases)
)
select family_key, snapshot_date as as_of_date, 'current' as role, null::int as episode_number
from {{ ref('dim_product_family') }}, today
union all
select family_key, as_of_date, 'case', episode_number from cases
union all
select c.family_key, n.as_of_date, 'control', null::int
from controls c join numbered_cases n using (case_no)
