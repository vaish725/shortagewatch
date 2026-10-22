-- Links each shortage record (latest snapshot) to a product family. Methods, in priority order:
--   package_ndc  the record's own package NDC is in the directory
--   openfda_ndc  an NDC in the record's openfda block is in the directory
--   name_form    weakest: every ingredient of a family appears in the record's generic name and the dosage form
--                word agrees. Needed for discontinued products that left the directory; ties pick the lowest key.
-- Records matching none stay unmatched (and are counted in mart_data_quality).
with current_records as (
    select * from {{ ref('stg_shortages') }}
    where dt = (select max(dt) from {{ ref('stg_shortages') }})
),
by_package as (
    select r.record_key, 1 as priority, 'package_ndc' as method, f.family_key
    from current_records r
    join {{ ref('int_product_families') }} f on f.product_key = r.product_key
),
by_openfda as (
    select r.record_key, 2, 'openfda_ndc', f.family_key
    from current_records r, unnest(r.openfda_product_keys) as k(product_key)
    join {{ ref('int_product_families') }} f on f.product_key = k.product_key
),
by_ndc as (
    select * from by_package union all select * from by_openfda
),
families as (
    select distinct family_key, ingredient_list, dosage_form_base from {{ ref('int_product_families') }}
),
by_name as (
    select r.record_key, 3, 'name_form', f.family_key
    from current_records r
    join families f
      on f.dosage_form_base = upper(split_part(split_part(r.dosage_form, ',', 1), ' ', -1))
     and list_bool_and(list_transform(
            string_split(f.ingredient_list, ', '),
            lambda i: contains({{ text_key('r.generic_name') }}, {{ text_key('i') }})))
    where r.record_key not in (select record_key from by_ndc)
),
ranked as (
    select
        *,
        row_number() over (partition by record_key order by priority, family_key) as rn
    from (select * from by_ndc union all select * from by_name)
)
select
    r.record_key,
    coalesce(k.method, 'unmatched') as method,
    k.family_key
from current_records r
left join (select * from ranked where rn = 1) k using (record_key)
