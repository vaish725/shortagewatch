-- Normalised NDCs must be 11 digits (9 for a product-only NDC found in recall text) and product keys 9 digits.
select 'shortage_package' as source, package_ndc_norm as value from {{ ref('stg_shortages') }}
where package_ndc_norm is not null and not regexp_matches(package_ndc_norm, '^[0-9]{11}$')
union all
select 'ndc_product', product_key from {{ ref('stg_ndc_products') }}
where not regexp_matches(product_key, '^[0-9]{9}$')
union all
select 'recall_text', ndc_norm from {{ ref('int_recall_ndc_tokens') }}
where not regexp_matches(ndc_norm, '^([0-9]{9}|[0-9]{11})$')
