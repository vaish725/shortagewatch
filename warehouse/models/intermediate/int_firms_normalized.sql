-- Every firm name seen in any source, reduced to a firm key and rolled up to a parent group.
-- Parent mapping is hand curated in seeds/firm_parent_map.csv; unmapped firms are their own group.
with names as (
    select labeler_name as firm_name, firm_key, 'ndc_labeler' as source from {{ ref('stg_ndc_products') }}
    union all select company_name, firm_key, 'shortage' from {{ ref('stg_shortages') }}
    union all select recalling_firm, firm_key, 'recall' from {{ ref('stg_enforcement') }}
    union all select company_name, firm_key, 'warning_letter' from {{ ref('stg_warning_letters') }}
)
select
    n.firm_key,
    coalesce(m.parent_key, n.firm_key) as firm_group_key,
    min(n.firm_name) as example_name,
    count(*) as name_occurrences,
    list_sort(list_distinct(list(n.source))) as sources
from names n
left join {{ ref('firm_parent_map') }} m using (firm_key)
group by 1, 2
