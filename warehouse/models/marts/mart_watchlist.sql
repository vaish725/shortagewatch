-- Ranked watchlist of families not currently in shortage, scored from the signals as of the latest snapshot.
-- Points come from seeds/risk_weights.csv (provisional until the week 6 regression sets them). Every row carries
-- at least one reason; families with no signal are left off.
with weights as (select signal, points, reason from {{ ref('risk_weights') }}),
base as (
    select s.*, d.ingredient_list
    from {{ ref('fct_family_risk_signals') }} s
    join {{ ref('dim_product_family') }} d using (family_key)
    where s.role = 'current' and not s.in_active_shortage and s.n_products > 0
),
fired as (
    select family_key, 'sole_source' as signal from base where supplier_bucket = '1'
    union all select family_key, 'few_suppliers' from base where supplier_bucket = '2-3'
    union all select family_key, 'injectable' from base where is_injectable
    union all select family_key, 'recall_product_24m' from base where has_recall_product_24m
    union all select family_key, 'recall_ingredient_24m' from base where has_recall_ingredient_24m
    union all select family_key, 'warning_letter_36m' from base where has_warning_letter_36m
),
scored as (
    select
        f.family_key,
        sum(w.points) as score,
        list(w.reason order by w.points desc, w.signal) as reasons
    from fired f join weights w using (signal)
    group by 1
)
select
    row_number() over (order by sc.score desc, b.family_key) as rank,
    b.family_key,
    b.ingredient_list,
    b.dosage_form_base,
    b.release_type,
    b.route_key,
    sc.score,
    sc.reasons,
    array_to_string(sc.reasons, '; ') as reason_text,
    b.n_suppliers,
    b.supplier_count_source,
    greatest(b.last_recall_product_date, b.last_recall_ingredient_date) as last_recall_date,
    b.last_recall_product_date,
    b.last_recall_ingredient_date,
    b.last_warning_letter_date,
    b.as_of_date,
    'provisional' as weights_status
from scored sc
join base b using (family_key)
