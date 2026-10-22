# Data Quality Log

Issues found in each source and how they are handled. Last checked 2026-10-21.

## Source access summary

| Source | Access | Landed by | Volume |
|---|---|---|---|
| openFDA shortages | Keyless JSON, 2 pages of 1,000 | `ingestion/sources/shortages.py` | 1,608 records |
| openFDA enforcement | Keyless JSON, 19 pages | `ingestion/sources/enforcement.py` | 18,043 records |
| openFDA NDC | Bulk download (API skip cap is 25,000, directory has 138,202) | `ingestion/sources/ndc.py` | 138,199 landed, 3 quarantined |
| RxNorm | Keyless REST, name to RxCUI works | not yet extracted; needed only as a matching tiebreaker | n/a |
| FDA warning letters | XLSX export behind the FDA page | `ingestion/sources/warning_letters.py` | 1,796 unique, 494 drug-related |

Every record passes a pydantic model on key fields; rejects are written to `quarantine.json` beside the day's partition and counted in the run log. Only the 3 NDC rows below have been quarantined so far.

## Shortages
- **Unit is the package, not the shortage.** 1,608 records collapse to about 323 product families (active ingredient + dosage form + route, preliminary), median 2 records per family and up to 69. All counts and durations must be taken at family level, never record level. The rollup is built in staging (`int_product_families`, week 4).
- **Few resolved records.** Full-feed status counts: Current 1,141, To Be Discontinued 448, Resolved 19 records. At family level that is 146 Current, 172 To Be Discontinued and only 5 Resolved. The week 1 sample of 100 had 1 resolved record, so the sample was not misleading. Consequence: duration analysis rests on right-censored (still active) shortages, and Kaplan-Meier confidence intervals will be wide. The write-up must say so. The daily snapshots will add resolutions over time.
- Update types: Reverified 939, New 460, Revised 209.
- `openfda` enrichment block is missing on 294 records (18%). Where present it carries `rxcui`, `route`, `substance_name` and NDCs. The rest need name-based family matching.
- 10 records have a null `dosage_form`. Dates are `MM/DD/YYYY` strings. `shortage_reason` is only about 27% filled.
- The feed is a current-state snapshot with no history. The daily workflow commits a dated Parquet file to the `data` branch; the first run succeeded on 2026-10-22 UTC.

## Enforcement (recalls)
- All 18,043 records are drug recalls, dates are `YYYYMMDD` strings, and `recalling_firm` is free text.
- No NDC field. The `openfda` block links only 17.1% of recalls to a directory product. 56% of records mention "NDC" in `product_description` or `code_info`, and 54% contain an NDC-shaped string.
- **Match rate by method** (`make match`, against the current NDC directory):

| Method | Recalls | Share |
|---|---|---|
| openfda block | 3,085 | 17.1% |
| NDC after keyword in text | 548 | 3.0% |
| bare NDC-shaped token confirmed by directory | 8 | 0.0% |
| same firm as a labeler + generic name in text | 757 | 4.2% |
| directory generic name in text (family level, weakest) | 10,348 | 57.4% |
| **Matched to any product or family** | **14,746** | **81.7%** |
| Matched to a specific product (all methods but generic name) | 4,398 | 24.4% |

- **NDC extraction alone lifts specific-product matches only from 17% to 24%**, not far above the openfda block. Reason: the NDC directory lists only currently marketed products, so NDCs cited by old recalls often no longer exist. Of unmatched recalls with a keyword NDC, about half have a labeler that is absent from the directory entirely. Specific-product match rate by report year runs from 9 to 25% before 2020, 37% in 2021, 53% in 2024 and 73% in 2026.
- The generic-name fallback operates at the product family level, which is the project's unit of analysis, so it is adequate for rolling recalls up to families. It cannot tell dosage forms apart, so a recall of one form can be attributed to every family of that ingredient. An 8-record spot check found all plausible, but precision has not been measured; treat it as the weakest method and keep the method column through to the marts so results can be reported with and without it.
- Overall match rate by year with all methods: 84% in 2018, 86% in 2021, 93% in 2024, 94% in 2026. The project target of 90% applies to shortages, measured in week 4.

## NDC directory
- Product NDCs are 10-digit hyphenated; packages sit in a nested `packaging` list. `ingestion/utils/ndc.py` normalises 4-4-2, 5-3-2 and 5-4-1 layouts to 11-digit 5-4-2 (9-digit 5-4 at product level), with tests.
- 3 products were quarantined for a missing `generic_name` (hand sanitizers, irrelevant to shortages).
- `route` about 70% filled. `labeler_name` is the marketing labeler, not necessarily the manufacturer. The 26 MB bulk file is re-downloaded in full on each run.

## Warning letters
- The data.gov XML link (`fda.gov/DataSets/WarningLetters/WarningLettersDataSet.xml`) returns 404 and the Data Dashboard API needs credentials. The working path is the XLSX export behind the FDA page.
- **Correction to the week 1 note:** paging is stable, not erratic. Page 0 is empty, pages 1 and 2 hold all the rows that can be reached, and pages 3 and later only repeat them. Repeated pulls added nothing, so the reachable set is 1,797 unique rows (1,796 after validation). The `search_api_fulltext_issuing_office` filter on the page is ignored by the export.
- **Coverage:** letters posted 2021-01-05 to 2026-04-28, so the last six months are missing and the true total is unknown. The export covers every FDA center; 494 rows come from drug-related offices (matching drug, CDER or pharmaceutical). Use only as a partial firm-level signal with 36-month look-back windows, and state the date range wherever it is reported.
- Time-boxed as agreed. Coverage was not improved beyond the above.
