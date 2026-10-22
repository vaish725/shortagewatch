# Data Quality Log

Issues found in each source and how they are handled. Checked on 2026-10-21.

## Source access summary

| Source | Access verified | Notes |
|---|---|---|
| openFDA shortages | Yes, keyless JSON | 1,608 records, last_updated 2026-10-21 |
| openFDA enforcement | Yes, keyless JSON | 18,043 records, last_updated 2026-10-14 (weekly) |
| openFDA NDC | Yes, keyless JSON | 138,202 products, last_updated 2026-10-21 |
| RxNorm | Yes, keyless REST | name to RxCUI lookup works |
| FDA warning letters | Partial, XLSX export only | See below |

## Shortages
- One record per presentation (package NDC), not per drug: expect many records per product family.
- `status` values in a 100-record sample: Current, To Be Discontinued, Resolved (rare in the feed, so duration analysis must handle few resolved rows).
- `openfda` block is present on about 83% of records and carries `rxcui`, `route`, `substance_name`, `product_ndc`, `package_ndc`. Remaining records need name-based matching.
- Dates are `MM/DD/YYYY` strings. `shortage_reason` is only about 27% filled; `change_date` about 3%.
- Feed is a current-state snapshot with no history, so daily snapshots must start early.

## Enforcement (recalls)
- No NDC field at the top level. The `openfda` block is filled on only about 23% of records, so most recalls must be linked by firm name and product description text.
- `product_type` mixes categories; filter to drugs. `recalling_firm` is free text.
- Dates are `YYYYMMDD` strings.

## NDC directory
- `route` about 70% filled, `active_ingredients` about 97%. Product NDC is 10-digit hyphenated (for example 65691-0090); packages sit in a nested `packaging` list with their own NDCs. Normalization to 11-digit 5-4-2 is required before joins.
- `labeler_name` is the marketing labeler, not necessarily the manufacturer.

## Warning letters
- The data.gov dataset points to `fda.gov/DataSets/WarningLetters/WarningLettersDataSet.xml`, which now returns 404. The FDA Data Dashboard API needs credentials.
- Working path: the XLSX export behind the FDA warning letters page (`.../warning-letters/datatables-data?page=N&_format=xlsx`). Columns: Posted Date, Letter Issue Date, Company Name, Issuing Office, Subject, Response Letter, Closeout Letter.
- Limits found: 1,000 rows per request, `page=0` is empty, and paging is not stable. Pulling pages 1 to 12 returned only 1,797 unique rows (pages 3 onward repeated earlier rows), and the newest posted date seen was 2026-04-28. The export covers all FDA centers, so rows must be filtered to drug-related offices.
- Decision for week 2: pull pages repeatedly and de-duplicate, and measure coverage against the on-page total. If coverage stays poor, treat warning letters as a partial signal (the project allows the project to run without it).
