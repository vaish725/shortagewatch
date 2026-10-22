-- Warning letters, all snapshot dates, de-duplicated to one row per letter (the export is the fragile source,
-- so earlier snapshots can hold letters that later disappear from it).
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
