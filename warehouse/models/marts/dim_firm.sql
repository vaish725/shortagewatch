-- One row per firm group (parent company where the seed knows it, otherwise the firm itself).
select
    firm_group_key,
    min(example_name) as example_name,
    count(*) as n_name_variants,
    list_sort(list_distinct(flatten(list(sources)))) as sources
from {{ ref('int_firms_normalized') }}
group by firm_group_key
