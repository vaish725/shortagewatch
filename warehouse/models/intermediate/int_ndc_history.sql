-- Type 2 history of each product NDC, so supplier counts can be reconstructed as of past dates once
-- weekly snapshots accumulate (the directory itself only shows today's market).
{{ scd2_history(
    ref('stg_ndc_products'),
    'product_ndc',
    ['labeler_name', 'dosage_form', 'marketing_end_date', 'finished'],
    ['product_key', 'firm_key', 'generic_name']
) }}
