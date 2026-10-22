-- Maps each finished human-drug product NDC (latest directory snapshot) to a product family.
-- Family = sorted ingredient list + dosage form base + route, the level procurement substitutes at.
-- Missing route: derive from the dosage form (seed), otherwise an explicit 'UNKNOWN' bucket.
with products as (
    select * from {{ ref('stg_ndc_products') }}
    where dt = (select max(dt) from {{ ref('stg_ndc_products') }})
      and finished
      and product_type like 'HUMAN%'
      and len(ingredients) > 0
),
routed as (
    select
        p.*,
        case
            when len(p.routes) > 0 then array_to_string(list_sort(p.routes), ',')
            else coalesce(d.default_route, 'UNKNOWN')
        end as route_key,
        case
            when len(p.routes) > 0 then 'ndc'
            when d.default_route is not null then 'derived_from_dosage_form'
            else 'unknown'
        end as route_source
    from products p
    left join {{ ref('dosage_form_route_default') }} d using (dosage_form_base)
)
select
    md5(array_to_string(ingredients, '|') || '#' || dosage_form_base || '#' || route_key) as family_key,
    array_to_string(ingredients, ', ') as ingredient_list,
    dosage_form_base,
    route_key,
    route_source,
    product_ndc,
    product_key,
    firm_key,
    labeler_name,
    generic_key,
    marketing_end_date
from routed
