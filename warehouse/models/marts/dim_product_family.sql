-- One row per product family (finished human-drug products in the latest NDC directory snapshot).
with products as (
    select p.*, coalesce(f.firm_group_key, p.firm_key) as firm_group_key
    from {{ ref('int_product_families') }} p
    left join {{ ref('int_firms_normalized') }} f using (firm_key)
),
-- Large firms: the ten firm groups marketing the most families (used for the without-large-firms sensitivity check)
large_firms as (
    select firm_group_key from products group by 1
    order by count(distinct family_key) desc, firm_group_key limit 10
),
-- Most common therapeutic group among a family's products, ignoring 'other' unless nothing else is present
family_group as (
    select family_key, coalesce(arg_max(therapeutic_group, n) filter (where therapeutic_group <> 'other'), 'other') as therapeutic_group
    from (select family_key, therapeutic_group, count(*) as n from products group by 1, 2)
    group by 1
)
select
    p.family_key,
    any_value(p.ingredient_list) as ingredient_list,
    any_value(p.dosage_form_base) as dosage_form_base,
    any_value(p.release_type) as release_type,
    any_value(p.route_key) as route_key,
    any_value(p.route_source) as route_source,
    count(distinct p.product_ndc) as n_products,
    count(distinct p.firm_group_key) as n_suppliers,
    count(distinct p.firm_group_key) = 1 as is_sole_source,
    -- Approved human prescription drug: the analysis population (excludes OTC, unapproved, homeopathic, allergenic)
    bool_or(p.product_type = 'HUMAN PRESCRIPTION DRUG'
            and p.marketing_category in ('NDA', 'ANDA', 'BLA', 'NDA AUTHORIZED GENERIC')) as in_analysis_population,
    -- generic when any product is an ANDA; otherwise brand (NDA, BLA, authorised generic)
    case when bool_or(p.marketing_category = 'ANDA') then 'generic' else 'brand' end as approval_class,
    any_value(g.therapeutic_group) as therapeutic_group,
    min(p.marketing_start_date) as first_marketing_start_date,
    bool_or(p.firm_group_key in (select firm_group_key from large_firms)) as has_large_firm_supplier
from products p
join family_group g using (family_key)
group by p.family_key
