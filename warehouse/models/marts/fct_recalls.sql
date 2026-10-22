-- One row per recall and matched product family. match_level separates NDC-based (product) matches from
-- generic-name (ingredient) matches so analyses can run with and without the weaker ones.
select
    m.recall_number,
    m.family_key,
    m.method,
    m.match_level,
    r.classification,
    r.status,
    r.report_date,
    r.recalling_firm,
    r.firm_key
from {{ ref('int_recall_to_family') }} m
join {{ ref('stg_enforcement') }} r using (recall_number)
where m.family_key in (select family_key from {{ ref('dim_product_family') }})
