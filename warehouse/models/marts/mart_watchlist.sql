-- Ranked watchlist of approved prescription families not currently in shortage, scored from the signals as of the
-- latest snapshot. Points come from seeds/risk_weights.csv, written by analysis/risk_score.py from the primary
-- risk-factor model (docs/analysis_plan.md). Every row has at least one scored reason; families with none are left off.
-- same_ingredient_recall_unverified is shown but never scored: that match is only about 57% precise.
with scored as (
    select family_key, sum(points) as score, list(reason order by points desc, signal) as reasons
    from {{ ref('mart_watchlist_reasons') }}
    group by 1
),
base as (
    select s.*, d.ingredient_list
    from {{ ref('fct_family_risk_signals') }} s
    join {{ ref('dim_product_family') }} d using (family_key)
    where s.role = 'current'
)
select
    -- Ties on score: most recent product-level recall, then fewer suppliers, then most recent warning letter
    row_number() over (
        order by sc.score desc, b.last_recall_product_date desc nulls last, b.n_suppliers, b.last_warning_letter_date desc nulls last, b.family_key
    ) as rank,
    b.family_key,
    b.ingredient_list,
    b.dosage_form_base,
    b.release_type,
    b.route_key,
    b.therapeutic_group,
    sc.score,
    sc.reasons,
    array_to_string(sc.reasons, '; ') as reason_text,
    b.has_recall_ingredient_24m as same_ingredient_recall_unverified,
    b.n_suppliers,
    b.supplier_count_source,
    greatest(b.last_recall_product_date, b.last_recall_ingredient_date) as last_recall_date,
    b.last_recall_product_date,
    b.last_recall_ingredient_date,
    b.last_warning_letter_date,
    b.as_of_date,
    'primary model' as weights_status
from scored sc
join base b using (family_key)
