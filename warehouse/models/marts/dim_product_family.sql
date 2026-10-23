-- One row per product family (finished human drug products in the latest NDC directory snapshot).
with products as (
    select p.*, coalesce(f.firm_group_key, p.firm_key) as firm_group_key
    from {{ ref('int_product_families') }} p
    left join {{ ref('int_firms_normalized') }} f using (firm_key)
)
select
    family_key,
    any_value(ingredient_list) as ingredient_list,
    any_value(dosage_form_base) as dosage_form_base,
    any_value(release_type) as release_type,
    any_value(route_key) as route_key,
    any_value(route_source) as route_source,
    count(distinct product_ndc) as n_products,
    count(distinct firm_group_key) as n_suppliers,
    count(distinct firm_group_key) = 1 as is_sole_source
from products
group by family_key
