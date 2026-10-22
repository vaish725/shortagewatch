-- Drug recalls from the latest pull (openFDA keeps the full recall history, so only the newest pull is read).
with src as (
    select * from {{ source('raw', 'enforcement') }}
    where dt = (select max(dt) from {{ source('raw', 'enforcement') }})
)
select
    recall_number,
    event_id,
    classification,
    status,
    recalling_firm,
    {{ firm_key('recalling_firm') }} as firm_key,
    product_description,
    code_info,
    reason_for_recall,
    {{ parse_date('report_date') }} as report_date,
    {{ parse_date('recall_initiation_date') }} as recall_initiation_date,
    {{ parse_date('termination_date') }} as termination_date,
    list_transform({{ json_list('openfda', '$.product_ndc') }}, lambda x: substr({{ normalize_ndc('x') }}, 1, 9)) as openfda_product_keys,
    dt
from src
