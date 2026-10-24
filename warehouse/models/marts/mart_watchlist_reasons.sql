-- One row per watchlist family and scored signal that fired, with its points. Only signals with positive points
-- in seeds/risk_weights.csv appear (signals marked informational or dropped carry 0 points and never fire here).
-- Signals use the as-of-latest-snapshot row of fct_family_risk_signals for approved prescription families that are
-- not in a shortage and still have a marketed product.
with weights as (select signal, points, reason from {{ ref('risk_weights') }} where points > 0),
base as (
    select * from {{ ref('fct_family_risk_signals') }}
    where role = 'current' and in_analysis_population and not in_active_shortage and n_products > 0
),
fired as (
    select family_key, 'generic_multi_source' as signal from base where approval_class = 'generic' and n_suppliers > 1
    union all select family_key, 'sole_source_brand' from base where approval_class = 'brand' and n_suppliers = 1
    union all select family_key, 'sole_source_generic' from base where approval_class = 'generic' and n_suppliers = 1
    union all select family_key, 'injectable' from base where is_injectable
    union all select family_key, 'recall_product_24m' from base where has_recall_product_24m
    union all select family_key, 'warning_letter_24m' from base where last_warning_letter_date >= as_of_date - interval 24 month
)
select f.family_key, f.signal, w.points, w.reason
from fired f join weights w using (signal)
