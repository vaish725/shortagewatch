-- Type 2 history of each shortage record, rebuilt from all snapshot partitions (see macro scd2_history).
{{ scd2_history(
    ref('stg_shortages'),
    'record_key',
    ['status', 'availability', 'shortage_reason', 'discontinued_date'],
    ['package_ndc', 'product_key', 'company_name', 'generic_name', 'dosage_form', 'initial_posting_date', 'update_date']
) }}
