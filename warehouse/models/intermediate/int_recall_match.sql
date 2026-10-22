-- Matches each recall to NDC directory products, recording which method matched. First method wins:
--   openfda_block  the recall's own openfda.product_ndc enrichment        (product level)
--   ndc_keyword    NDC after the word NDC in the text                      (product level)
--   ndc_bare       NDC-shaped token in the text, confirmed by the directory (product level)
--   firm_text      same firm as a labeler and its generic name in the text  (product level)
--   generic_name   a directory generic name (1-4 words) in the text          (ingredient level, weakest)
-- Mirrors ingestion/recall_match.py; tests/assert_recall_match_parity.sql keeps the two in step.
-- One row per recall, method and matched key; matched_key is a 9 digit product key or a generic name.
with directory as (
    select distinct product_key from {{ ref('stg_ndc_products') }}
    where dt = (select max(dt) from {{ ref('stg_ndc_products') }})
),
current_products as (
    select * from {{ ref('stg_ndc_products') }}
    where dt = (select max(dt) from {{ ref('stg_ndc_products') }})
),
recalls as (
    select * from {{ ref('stg_enforcement') }}
),
openfda_block as (
    select distinct r.recall_number, 1 as priority, 'openfda_block' as method, 'product' as match_level, k.product_key as matched_key
    from recalls r, unnest(r.openfda_product_keys) as k(product_key)
    where k.product_key in (select product_key from directory)
),
ndc_text as (
    select distinct t.recall_number, t.has_keyword, t.product_key
    from {{ ref('int_recall_ndc_tokens') }} t
    where t.product_key in (select product_key from directory)
),
ndc_keyword as (
    select recall_number, 2, 'ndc_keyword', 'product', product_key from ndc_text where has_keyword
),
ndc_bare as (
    -- A recall is "bare" only when none of its directory-confirmed NDCs follow the keyword
    select recall_number, 3, 'ndc_bare', 'product', product_key from ndc_text
    where recall_number not in (select recall_number from ndc_text where has_keyword)
),
firm_text as (
    select distinct r.recall_number, 4, 'firm_text', 'product', p.product_key
    from recalls r
    join current_products p on p.firm_key = r.firm_key
    where contains(lower(r.product_description), lower(p.generic_name))
),
generics as (
    select distinct generic_key from current_products
    where generic_key <> '' and (contains(generic_key, ' ') or length(generic_key) >= 5)
),
words as (
    select
        recall_number,
        list_filter(string_split({{ text_key('product_description') }}, ' '), lambda w: w <> '') as w
    from recalls
),
grams as (
    select distinct
        recall_number,
        array_to_string(list_slice(w, i, i + n - 1), ' ') as gram
    from (
        select recall_number, w, n, unnest(generate_series(1, greatest(len(w) - n + 1, 0))) as i
        from words, (select unnest([1, 2, 3, 4]) as n)
    )
),
generic_name as (
    select recall_number, 5, 'generic_name', 'ingredient', gram
    from grams where gram in (select generic_key from generics)
),
all_matches as (
    select * from openfda_block
    union all select * from ndc_keyword
    union all select * from ndc_bare
    union all select * from firm_text
    union all select * from generic_name
),
best as (
    select recall_number, min(priority) as priority from all_matches group by 1
)
select m.recall_number, m.method, m.match_level, m.matched_key
from all_matches m
join best b on b.recall_number = m.recall_number and b.priority = m.priority
