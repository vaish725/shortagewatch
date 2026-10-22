-- Data quality metrics in long form (area, metric, value, detail): match rates, quarantine counts,
-- unknown-route families and coverage windows. docs/data_quality_log.md is the narrative; this is the live numbers.
with recall_total as (select count(*) as n from {{ ref('stg_enforcement') }}),
recall_best as (select recall_number, any_value(method) as method, any_value(match_level) as match_level from {{ ref('int_recall_match') }} group by 1),
recall_window as (
    select (select max(report_date) from {{ ref('stg_enforcement') }}) - interval 2 year as start_date
),
runs as (
    -- Latest run summary per extract step, from the data branch run log
    select step, landed, quarantined, run_at
    from read_json('{{ var("data_root") }}/runs/dt=*/*.json', union_by_name = true, ignore_errors = true)
    where step in ('shortages', 'enforcement', 'ndc', 'warning_letters')
    qualify row_number() over (partition by step order by run_at desc) = 1
),
metrics as (
    select 'recalls' as area, 'total' as metric, (select n from recall_total)::double as value, null as detail
    union all
    select 'recalls', 'matched_' || method, count(*)::double, match_level from recall_best group by method, match_level
    union all
    select 'recalls', 'match_rate_all_methods', count(*)::double / (select n from recall_total), 'all years' from recall_best
    union all
    select 'recalls', 'match_rate_product_level',
           count(*) filter (where match_level = 'product')::double / (select n from recall_total), 'all years' from recall_best
    union all
    select 'recalls', 'match_rate_all_methods_24m',
           count(b.recall_number)::double / count(*), 'from ' || (select start_date from recall_window)::varchar
    from {{ ref('stg_enforcement') }} r left join recall_best b using (recall_number)
    where r.report_date >= (select start_date from recall_window)
    union all
    select 'recalls', 'match_rate_product_level_24m',
           count(*) filter (where b.match_level = 'product')::double / count(*), 'from ' || (select start_date from recall_window)::varchar
    from {{ ref('stg_enforcement') }} r left join recall_best b using (recall_number)
    where r.report_date >= (select start_date from recall_window)
    union all
    select 'shortages', 'records_' || method, count(*)::double, null from {{ ref('int_shortage_to_family') }} group by method
    union all
    select 'shortages', 'match_rate_to_family',
           count(*) filter (where method <> 'unmatched')::double / count(*), 'target 0.90' from {{ ref('int_shortage_to_family') }}
    union all
    select 'shortages', 'match_rate_ndc_based',
           count(*) filter (where method in ('package_ndc', 'openfda_ndc'))::double / count(*), 'excludes name_form' from {{ ref('int_shortage_to_family') }}
    union all
    select 'shortages', 'families_with_episode', count(distinct family_key)::double, null from {{ ref('fct_shortage_events') }}
    union all
    select 'shortages', 'snapshots', count(distinct dt)::double,
           min(dt)::varchar || ' to ' || max(dt)::varchar from {{ ref('stg_shortages') }}
    union all
    select 'families', 'total', count(*)::double, null from {{ ref('dim_product_family') }}
    union all
    -- Fixed list so a zero (for example no families with an unknown route) still shows up as a row
    select 'families', 'route_' || s.route_source, count(d.family_key)::double, null
    from (select unnest(['ndc', 'derived_from_dosage_form', 'unknown']) as route_source) s
    left join {{ ref('dim_product_family') }} d using (route_source)
    group by s.route_source
    union all
    select 'families', 'sole_source', count(*)::double, null from {{ ref('dim_product_family') }} where is_sole_source
    union all
    select 'ndc', 'duplicate_product_ndc_rows_dropped',
           (select count(*) from {{ source('snapshots', 'ndc') }} where dt = (select max(dt) from {{ ref('stg_ndc_products') }}))
           - (select count(*) from {{ ref('stg_ndc_products') }} where dt = (select max(dt) from {{ ref('stg_ndc_products') }})),
           null
    union all
    select 'ndc', 'snapshots', count(distinct dt)::double, min(dt)::varchar || ' to ' || max(dt)::varchar from {{ ref('stg_ndc_products') }}
    union all
    select 'warning_letters', 'letters', count(*)::double,
           min(posted_date)::varchar || ' to ' || max(posted_date)::varchar from {{ ref('stg_warning_letters') }}
    union all
    select 'warning_letters', 'drug_related_letters', count(*)::double, null from {{ ref('stg_warning_letters') }} where is_drug_office
    union all
    select 'ingestion', 'landed_' || step, landed::double, run_at::varchar from runs
    union all
    select 'ingestion', 'quarantined_' || step, quarantined::double, run_at::varchar from runs
)
select * from metrics
