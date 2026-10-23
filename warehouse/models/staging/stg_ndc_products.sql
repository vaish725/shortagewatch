-- One row per product NDC per snapshot date. The directory lists some product NDCs more than once
-- (separate SPL versions); keep one deterministic row so product_ndc is a usable key.
with src as (
    select * from {{ source('snapshots', 'ndc') }}
),
typed as (
    select
        dt,
        product_ndc,
        substr({{ normalize_ndc('product_ndc') }}, 1, 9) as product_key,
        labeler_name,
        {{ firm_key('labeler_name') }} as firm_key,
        generic_name,
        {{ text_key('generic_name') }} as generic_key,
        brand_name,
        dosage_form,
        upper(trim(split_part(dosage_form, ',', 1))) as dosage_form_base,
        {{ release_type('dosage_form') }} as release_type,
        {{ json_list('route', '$') }} as routes,
        list_sort(list_transform(
            {{ json_list('active_ingredients', '$[*].name') }}, lambda x: lower(trim(x)))) as ingredients,
        {{ json_list('pharm_class', '$') }} as pharm_classes,
        marketing_category,
        product_type,
        finished,
        {{ parse_date('marketing_start_date') }} as marketing_start_date,
        {{ parse_date('marketing_end_date') }} as marketing_end_date,
        {{ parse_date('listing_expiration_date') }} as listing_expiration_date
    from src
    where product_ndc is not null
)
select * exclude (rn)
from (
    select
        *,
        row_number() over (
            partition by dt, product_ndc
            order by listing_expiration_date desc nulls last, marketing_start_date desc nulls last,
                     labeler_name, dosage_form, generic_name, brand_name, marketing_category, product_type,
                     cast(finished as varchar), cast(marketing_end_date as varchar),
                     cast(routes as varchar), cast(ingredients as varchar)
        ) as rn
    from typed
)
where rn = 1
