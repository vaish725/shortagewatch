-- Look-ahead guard: every event date behind a signal must be strictly before the row's as_of_date.
-- Returns offending rows; the regression is only valid while this is empty.
select family_key, as_of_date, role, 'recall_product' as signal, last_recall_product_date as event_date
from {{ ref('fct_family_risk_signals') }} where last_recall_product_date >= as_of_date
union all
select family_key, as_of_date, role, 'recall_ingredient', last_recall_ingredient_date
from {{ ref('fct_family_risk_signals') }} where last_recall_ingredient_date >= as_of_date
union all
select family_key, as_of_date, role, 'warning_letter', last_warning_letter_date
from {{ ref('fct_family_risk_signals') }} where last_warning_letter_date >= as_of_date
