-- One row per active shortage episode with the detail the dashboard table needs: age, dominant status, reason and
-- availability among its active records, and the family's recall history. Pre-aggregated so the dashboard never
-- reads the large daily fact table.
with latest as (select max(dt) as snapshot_date from {{ ref('stg_shortages') }}),
active_records as (
    select s.*, f.family_key
    from {{ ref('stg_shortages') }} s
    join {{ ref('int_shortage_to_family') }} f using (record_key)
    where s.dt = (select snapshot_date from latest) and s.status <> 'Resolved' and f.family_key is not null
),
detail as (
    select
        family_key,
        mode(status) as status,
        mode(shortage_reason) filter (where shortage_reason is not null) as shortage_reason,
        mode(availability) filter (where availability is not null) as availability,
        mode(therapeutic_category) as therapeutic_category,
        list(distinct company_name order by company_name) as companies
    from active_records group by 1
)
select
    e.episode_key,
    e.family_key,
    d.ingredient_list,
    d.dosage_form_base,
    d.release_type,
    d.route_key,
    e.start_date,
    e.duration_days as age_days,
    e.n_records,
    x.status,
    x.shortage_reason,
    x.availability,
    x.therapeutic_category,
    array_to_string(x.companies[1:3], '; ') || case when len(x.companies) > 3 then ' and ' || (len(x.companies) - 3) || ' more' else '' end as companies,
    s.last_recall_product_date,
    s.n_recalls_product_24m,
    s.n_suppliers,
    (select snapshot_date from latest) as as_of_date
from {{ ref('fct_shortage_events') }} e
join {{ ref('dim_product_family') }} d using (family_key)
left join detail x using (family_key)
left join {{ ref('fct_family_risk_signals') }} s on s.family_key = e.family_key and s.role = 'current'
where e.is_active
