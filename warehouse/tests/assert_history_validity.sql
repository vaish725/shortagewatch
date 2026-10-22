-- History rows must span a real interval: valid_from <= last_seen < valid_to (valid_to is NULL while current).
select 'shortage' as model, record_key as key, valid_from, last_seen, valid_to from {{ ref('int_shortage_history') }}
where valid_from > last_seen or valid_to <= last_seen
union all
select 'ndc', product_ndc, valid_from, last_seen, valid_to from {{ ref('int_ndc_history') }}
where valid_from > last_seen or valid_to <= last_seen
