-- NDCs found in recall free text (product description + code info), normalised, one row per recall and NDC.
-- has_keyword is true when any occurrence directly follows the word NDC (high confidence).
with recalls as (
    select recall_number, product_description || ' ' || coalesce(code_info, '') as text
    from {{ ref('stg_enforcement') }}
),
tokens as (
    select
        recall_number,
        unnest({{ ndc_tokens('text') }}) as raw_ndc,
        {{ ndc_keyword_tokens('text') }} as keyword_ndcs
    from recalls
),
normalised as (
    select
        recall_number,
        {{ normalize_ndc('raw_ndc') }} as ndc_norm,
        list_contains(keyword_ndcs, raw_ndc) as is_keyword
    from tokens
)
select
    recall_number,
    ndc_norm,
    substr(ndc_norm, 1, 9) as product_key,
    bool_or(is_keyword) as has_keyword
from normalised
where ndc_norm is not null
group by recall_number, ndc_norm
