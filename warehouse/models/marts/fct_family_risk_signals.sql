-- Risk signals per product family as of a date (grain: family x as_of_date x role). Every event date used is
-- strictly before as_of_date (tests/assert_no_signal_leakage.sql). Recall flags are kept separate for NDC
-- based (product level) and generic-name based (ingredient level) matches, so analyses can drop the weaker one.
with spine as (
    select s.*, d.dosage_form_base, d.release_type, d.route_key, d.approval_class, d.therapeutic_group,
           d.in_analysis_population, d.has_large_firm_supplier
    from {{ ref('int_signal_dates') }} s
    join {{ ref('dim_product_family') }} d using (family_key)
),
first_ndc as (select min(dt) as first_snapshot from {{ ref('stg_ndc_products') }}),

-- Suppliers as of the date: NDC history once snapshots cover it, otherwise today's directory
suppliers as (
    select
        s.family_key, s.as_of_date, s.role,
        count(distinct l.firm_group_key) as n_suppliers,
        count(distinct l.product_ndc) as n_products
    from spine s
    cross join first_ndc f
    join {{ ref('int_family_labelers') }} l on l.family_key = s.family_key
     and (
            (s.as_of_date >= f.first_snapshot and l.valid_from <= s.as_of_date and (l.valid_to is null or l.valid_to > s.as_of_date))
         or (s.as_of_date < f.first_snapshot and l.is_current)
     )
    where l.marketing_end_date is null or l.marketing_end_date >= s.as_of_date
    group by 1, 2, 3
),

recalls as (
    select
        s.family_key, s.as_of_date, s.role,
        max(r.report_date) filter (where r.match_level = 'product') as last_recall_product_date,
        max(r.report_date) filter (where r.match_level = 'ingredient') as last_recall_ingredient_date,
        count(distinct r.recall_number) filter (where r.match_level = 'product' and r.report_date >= s.as_of_date - interval 24 month) as n_recalls_product_24m,
        count(distinct r.recall_number) filter (where r.match_level = 'ingredient' and r.report_date >= s.as_of_date - interval 24 month) as n_recalls_ingredient_24m
    from spine s
    join {{ ref('fct_recalls') }} r on r.family_key = s.family_key
    where r.classification in ('Class I', 'Class II') and r.report_date < s.as_of_date
    group by 1, 2, 3
),

-- Firm groups marketing each family, then drug-related warning letters to them (public from the posted date)
family_firms as (
    select distinct family_key, firm_group_key from {{ ref('int_family_labelers') }}
),
letters as (
    select w.posted_date, g.firm_group_key
    from {{ ref('stg_warning_letters') }} w
    join {{ ref('int_firms_normalized') }} g on g.firm_key = w.firm_key
    where w.is_drug_office
),
warning as (
    select s.family_key, s.as_of_date, s.role, max(l.posted_date) as last_warning_letter_date
    from spine s
    join family_firms ff on ff.family_key = s.family_key
    join letters l on l.firm_group_key = ff.firm_group_key and l.posted_date < s.as_of_date
    group by 1, 2, 3
),

active_shortage as (
    select distinct s.family_key, s.as_of_date, s.role
    from spine s
    join {{ ref('fct_shortage_events') }} e on e.family_key = s.family_key
     and e.start_date < s.as_of_date and (e.end_date is null or e.end_date >= s.as_of_date)
),

coverage as (
    select
        (select min(report_date) from {{ ref('stg_enforcement') }}) as first_recall,
        (select min(posted_date) from {{ ref('stg_warning_letters') }}) as first_letter
)

select
    s.family_key,
    s.as_of_date,
    s.role,
    s.episode_number,
    s.set_id,
    s.in_analysis_population,
    s.approval_class,
    s.therapeutic_group,
    s.has_large_firm_supplier,
    s.dosage_form_base,
    s.release_type,
    s.route_key,
    s.dosage_form_base = 'INJECTION' as is_injectable,
    coalesce(sup.n_suppliers, 0) as n_suppliers,
    coalesce(sup.n_products, 0) as n_products,
    case when s.as_of_date >= f.first_snapshot then 'history' else 'current' end as supplier_count_source,
    case
        when coalesce(sup.n_suppliers, 0) = 0 then '0'
        when sup.n_suppliers = 1 then '1'
        when sup.n_suppliers <= 3 then '2-3'
        else '4+'
    end as supplier_bucket,
    rec.last_recall_product_date,
    rec.last_recall_ingredient_date,
    coalesce(rec.n_recalls_product_24m, 0) as n_recalls_product_24m,
    coalesce(rec.n_recalls_ingredient_24m, 0) as n_recalls_ingredient_24m,
    coalesce(rec.n_recalls_product_24m, 0) > 0 as has_recall_product_24m,
    coalesce(rec.n_recalls_ingredient_24m, 0) > 0 as has_recall_ingredient_24m,
    w.last_warning_letter_date,
    coalesce(w.last_warning_letter_date >= s.as_of_date - interval 36 month, false) as has_warning_letter_36m,
    a.family_key is not null as in_active_shortage,
    s.as_of_date - interval 24 month >= c.first_recall as recall_window_covered,
    c.first_letter is not null and s.as_of_date - interval 36 month >= c.first_letter as warning_letter_window_covered
from spine s
cross join first_ndc f
cross join coverage c
left join suppliers sup using (family_key, as_of_date, role)
left join recalls rec using (family_key, as_of_date, role)
left join warning w using (family_key, as_of_date, role)
left join active_shortage a using (family_key, as_of_date, role)
