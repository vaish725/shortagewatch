-- Rolls recall matches up to product families, keeping the method and level of each match.
-- Product-level matches map through the product NDC; ingredient-level matches map to every family
-- whose products carry that generic name, so one recall can fan out to several families.
select distinct m.recall_number, f.family_key, m.method, m.match_level
from {{ ref('int_recall_match') }} m
join {{ ref('int_product_families') }} f on f.product_key = m.matched_key
where m.match_level = 'product'
union
select distinct m.recall_number, f.family_key, m.method, m.match_level
from {{ ref('int_recall_match') }} m
join {{ ref('int_product_families') }} f on f.generic_key = m.matched_key
where m.match_level = 'ingredient'
