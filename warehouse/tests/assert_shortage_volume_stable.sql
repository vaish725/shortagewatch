{{ config(severity='warn') }}
-- Warns (never fails) when the latest shortage snapshot size moves more than 20% from the average of the previous
-- 7 snapshots, which catches silent API changes. With fewer than 7 earlier snapshots it warns that there is not
-- enough history to judge.
with counts as (select dt, count(*) as n from {{ ref('stg_shortages') }} group by dt),
latest as (select * from counts order by dt desc limit 1),
prior as (select * from counts where dt < (select dt from latest) order by dt desc limit 7)
select 'not enough history: ' || (select count(*) from prior) || ' of 7 earlier snapshots' as warning
where (select count(*) from prior) < 7
union all
select 'snapshot size moved ' || round(100 * abs(l.n - a.avg_n) / a.avg_n) || '% from the 7-snapshot average'
from latest l, (select avg(n) as avg_n from prior) a
where (select count(*) from prior) >= 7 and abs(l.n - a.avg_n) / a.avg_n > 0.2
