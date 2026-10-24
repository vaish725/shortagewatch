-- One row per shortage record per snapshot date. The feed is package level: many records per drug.
-- No natural key exists (presentation text is free-form), so identity is package NDC + company + posting date,
-- with a sequence number to separate the few exact collisions.
with src as (
    select * from {{ source('snapshots', 'shortages') }}
    where dt <= cast('{{ var("snapshot_cutoff") }}' as date)
),
typed as (
    select
        dt,
        package_ndc,
        {{ normalize_ndc('package_ndc') }} as package_ndc_norm,
        company_name,
        {{ firm_key('company_name') }} as firm_key,
        generic_name,
        dosage_form,
        status,
        availability,
        therapeutic_category,
        shortage_reason,
        presentation,
        update_type,
        {{ parse_date('initial_posting_date') }} as initial_posting_date,
        {{ parse_date('update_date') }} as update_date,
        {{ parse_date('discontinued_date') }} as discontinued_date,
        list_transform({{ json_list('openfda', '$.product_ndc') }}, lambda x: substr({{ normalize_ndc('x') }}, 1, 9)) as openfda_product_keys,
        {{ json_list('openfda', '$.route') }} as openfda_routes,
        {{ json_list('openfda', '$.substance_name') }} as openfda_substances
    from src
),
sequenced as (
    select
        *,
        row_number() over (
            partition by dt, package_ndc, company_name, initial_posting_date
            order by presentation, update_date, status, availability, shortage_reason, update_type,
                     discontinued_date, generic_name, dosage_form, therapeutic_category
        ) as dup_seq
    from typed
)
select
    md5(concat_ws('|', package_ndc, company_name, cast(initial_posting_date as varchar), cast(dup_seq as varchar))) as record_key,
    substr(package_ndc_norm, 1, 9) as product_key,
    * exclude (dup_seq)
from sequenced
