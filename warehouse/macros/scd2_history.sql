{# Type 2 history rebuilt from dated snapshot partitions (column `dt`), not from dbt snapshots.
   The warehouse file is recreated on every CI run, so dbt snapshot state would be lost; the Parquet
   partitions are the durable record and this is a pure function of them (idempotent).

   One output row per record and unbroken run of identical tracked values:
     valid_from  first snapshot date with these values
     last_seen   last snapshot date with these values
     valid_to    next snapshot date after last_seen (record changed or disappeared); NULL while current
   Arguments:
     relation  staging model with one row per (key, dt)
     key       column identifying a record across snapshots
     tracked   columns whose change starts a new row
     carry     columns reported as of the last snapshot in the run (changes here do not split rows) #}
{% macro scd2_history(relation, key, tracked, carry=[]) %}
with snapshots as (
    select dt, row_number() over (order by dt) as ord from (select distinct dt from {{ relation }})
),
next_snapshot as (
    select dt, lead(dt) over (order by dt) as next_dt from snapshots
),
hashed as (
    select
        r.*,
        s.ord,
        md5(concat_ws('|', {% for c in tracked %}coalesce(cast({{ c }} as varchar), '~'){{ ',' if not loop.last }}{% endfor %})) as state_hash
    from {{ relation }} r
    join snapshots s using (dt)
),
flagged as (
    select
        *,
        case when lag(ord) over w = ord - 1 and lag(state_hash) over w = state_hash then 0 else 1 end as is_new_run
    from hashed
    window w as (partition by {{ key }} order by dt)
),
runs as (
    select *, sum(is_new_run) over (partition by {{ key }} order by dt) as run_id from flagged
),
collapsed as (
    select
        {{ key }},
        {% for c in tracked %}any_value({{ c }}) as {{ c }},{% endfor %}
        {% for c in carry %}arg_max({{ c }}, dt) as {{ c }},{% endfor %}
        min(dt) as valid_from,
        max(dt) as last_seen
    from runs
    group by {{ key }}, run_id
)
select c.*, n.next_dt as valid_to, n.next_dt is null as is_current
from collapsed c
join next_snapshot n on n.dt = c.last_seen
{% endmacro %}
