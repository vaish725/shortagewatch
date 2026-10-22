-- Every family has at least one supplier and one product.
select family_key from {{ ref('dim_product_family') }} where n_suppliers < 1 or n_products < 1
