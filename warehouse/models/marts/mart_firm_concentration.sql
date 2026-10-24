-- Share of active shortage families that involve each firm group (a family with several makers counts for each).
-- Concentration view for the insights page.
with active_families as (select distinct family_key from {{ ref('fct_shortage_events') }} where is_active),
involved as (
    select distinct f.family_key, coalesce(g.firm_group_key, s.firm_key) as firm_group_key
    from {{ ref('stg_shortages') }} s
    join {{ ref('int_shortage_to_family') }} f using (record_key)
    left join {{ ref('int_firms_normalized') }} g on g.firm_key = s.firm_key
    where s.dt = (select max(dt) from {{ ref('stg_shortages') }}) and s.status <> 'Resolved'
      and f.family_key in (select family_key from active_families)
)
select
    i.firm_group_key,
    max(g.example_name) as example_name,
    count(*) as active_families,
    count(*)::double / (select count(*) from active_families) as share_of_active_families
from involved i left join {{ ref('dim_firm') }} g using (firm_group_key)
group by 1
