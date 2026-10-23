-- Products of each family with the firm group marketing them and the snapshot range that row was valid for.
-- Lets supplier counts be taken as of a date from the NDC history.
select
    f.family_key,
    h.product_ndc,
    coalesce(fm.firm_group_key, h.firm_key) as firm_group_key,
    h.valid_from,
    h.valid_to,
    h.is_current,
    h.marketing_end_date
from {{ ref('int_product_families') }} f
join {{ ref('int_ndc_history') }} h using (product_ndc)
left join {{ ref('int_firms_normalized') }} fm on fm.firm_key = h.firm_key
