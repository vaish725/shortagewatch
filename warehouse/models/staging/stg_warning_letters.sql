-- Warning letters, all snapshot dates, de-duplicated to one row per letter (the export is the fragile source,
-- so earlier snapshots can hold letters that later disappear from it).
-- Optional source: with no snapshot partitions yet, warn and continue with an empty table (the warning letter
-- signal is then simply absent). Shortages, recalls and the NDC directory stay hard failures.
{% if glob_count(var('data_root') ~ '/snapshots/warning_letters/dt=*/warning_letters.parquet') == 0 %}
{{ exceptions.warn("No warning_letters snapshot found under " ~ var('data_root') ~ "; continuing without the warning letter signal") }}
select
    null::date as posted_date, null::date as letter_issue_date, null::varchar as company_name,
    null::varchar as firm_key, null::varchar as issuing_office, null::boolean as is_drug_office,
    null::varchar as subject, null::date as dt
where false
{% else %}
with src as (
    select * from {{ source('snapshots', 'warning_letters') }}
),
typed as (
    select
        {{ parse_date('posted_date') }} as posted_date,
        {{ parse_date('letter_issue_date') }} as letter_issue_date,
        company_name,
        {{ firm_key('company_name') }} as firm_key,
        issuing_office,
        regexp_matches(coalesce(issuing_office, ''), '(?i)drug|cder|pharmaceutical') as is_drug_office,
        subject,
        dt
    from src
)
select * exclude (rn)
from (
    select *, row_number() over (partition by posted_date, letter_issue_date, company_name, subject order by dt desc) as rn
    from typed
)
where rn = 1
{% endif %}
