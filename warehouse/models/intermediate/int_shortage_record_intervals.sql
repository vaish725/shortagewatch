-- Shortage intervals per record, from its status history. A record that is Resolved and later Current again
-- yields two intervals. Where the history only ever saw a record already Resolved, the interval is
-- back-filled from its posting date to its update date (the resolution date proxy).
with history as (
    select
        h.*,
        f.family_key,
        case when h.status = 'Resolved' then 'resolved' else 'active' end as status_class
    from {{ ref('int_shortage_history') }} h
    join {{ ref('int_shortage_to_family') }} f using (record_key)
    where f.family_key is not null
),
with_prev as (
    select *, lag(status_class) over (partition by record_key order by valid_from) as prev_class from history
),
runs as (
    select
        *,
        sum(case when prev_class is null or prev_class <> status_class then 1 else 0 end)
            over (partition by record_key order by valid_from) as class_run
    from with_prev
),
classes as (
    select
        record_key,
        family_key,
        status_class,
        class_run,
        min(valid_from) as class_from,
        arg_max(initial_posting_date, valid_from) as initial_posting_date,
        arg_max(update_date, valid_from) as update_date
    from runs
    group by record_key, family_key, status_class, class_run
),
sequenced as (
    select
        *,
        row_number() over w as seq,
        lead(status_class) over w as next_class,
        lead(class_from) over w as next_from
    from classes
    window w as (partition by record_key order by class_run)
)
select record_key, family_key,
       case when seq = 1 then initial_posting_date else class_from end as start_date,
       case when next_class = 'resolved' then next_from end as end_date
from sequenced
where status_class = 'active'
union all
select record_key, family_key,
       initial_posting_date,
       greatest(coalesce(update_date, initial_posting_date), initial_posting_date)
from sequenced
where status_class = 'resolved' and seq = 1
