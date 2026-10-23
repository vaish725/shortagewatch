{{ config(severity='warn') }}
-- Warns (never fails) when a weekly NDC snapshot differs by more than 20% from the previous one, or when there is
-- no earlier snapshot to compare with.
with counts as (select dt, count(*) as n from {{ ref('stg_ndc_products') }} group by dt),
latest as (select * from counts order by dt desc limit 1),
previous as (select * from counts where dt < (select dt from latest) order by dt desc limit 1)
select 'no earlier NDC snapshot to compare with' as warning
where not exists (select 1 from previous)
union all
select 'NDC snapshot size moved ' || round(100 * abs(l.n - p.n) / p.n) || '% from the previous snapshot'
from latest l, previous p
where abs(l.n - p.n) / p.n > 0.2
