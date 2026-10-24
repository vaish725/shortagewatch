-- Families in shortage at the end of each week, for the trend chart. Weeks before the first snapshot are
-- reconstructed from posting dates (is_observed = false) and understate history.
select
    date_trunc('week', day)::date as week_start,
    count(distinct family_key) filter (where in_shortage and day = (select max(d2.day) from {{ ref('fct_shortage_status_daily') }} d2 where date_trunc('week', d2.day) = date_trunc('week', t.day))) as families_in_shortage,
    bool_and(is_observed) as is_observed
from {{ ref('fct_shortage_status_daily') }} t
group by 1
