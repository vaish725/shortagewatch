-- One row per shortage episode per product family (see int_shortage_episodes for the episode rule).
select
    e.episode_key,
    e.family_key,
    e.episode_number,
    e.start_date,
    e.end_date,
    e.is_active,
    e.n_records,
    e.duration_days
from {{ ref('int_shortage_episodes') }} e
where e.family_key in (select family_key from {{ ref('dim_product_family') }})
