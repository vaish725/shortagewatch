-- Parity check: recall match counts by method in SQL must equal the Python matcher
-- (ingestion/recall_match.py), run on the same inputs. Returns the methods that differ.
with py as (
    select * from read_json('{{ var("local_runs_root") }}/dt=*/recall_match.json')
    order by run_at desc limit 1
),
py_counts as (
    select 'openfda_block' as method, by_method.openfda_block as n from py
    union all select 'ndc_keyword', by_method.ndc_keyword from py
    union all select 'ndc_bare', by_method.ndc_bare from py
    union all select 'firm_text', by_method.firm_text from py
    union all select 'generic_name', by_method.generic_name from py
    union all select 'ALL', matched from py
),
dbt_counts as (
    select method, count(distinct recall_number) as n from {{ ref('int_recall_match') }} group by method
    union all select 'ALL', count(distinct recall_number) from {{ ref('int_recall_match') }}
)
select coalesce(p.method, d.method) as method, p.n as python_count, d.n as dbt_count
from py_counts p full join dbt_counts d on p.method = d.method
where coalesce(p.n, 0) <> coalesce(d.n, 0)
