# Data Quality Log

Issues found in each source and how they are handled. The live numbers are in the `mart_data_quality` dbt model (`make quality`, also printed in each CI run's job summary); this file records the reasoning behind them. Last checked 2026-10-22. All partition dates (`dt=`) and run timestamps are UTC, so an evening run in US time can carry the next day's date.

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
- **Match levels.** Matches from the openfda block, NDC text and firm+text identify a specific product (`product` level). Generic-name matches identify only the ingredient (`ingredient` level), so one recall can map to several families; the match level is kept alongside the method so the risk analysis can run with and without them.
- **Within the analysis window** (recalls reported in the 24 months before the latest report date, from 2024-10-14): 1,583 recalls, 94.3% matched, 64.5% to a specific product. This is the coverage that matters for the risk analysis, not the all-years figure.
- **Precision of the generic-name (ingredient-level) fallback**, from 100 pairs drawn with a fixed seed and labelled blind to family and outcome (rules in the analysis plan, labels in `warehouse/seeds/ingredient_match_labels.csv`, single labeller): 57 of 100 correct, 57% (Wilson 95% interval 47% to 66%). 17 further pairs were unclear because the product has a salt or ester of the matched name (for example the product is lidocaine HCl and the match is lidocaine); counting them as correct gives 74% (65% to 82%). The 26 incorrect pairs are mostly diluents and vehicles (sodium chloride, olive oil, water), descriptor words (cream, ointment, nasal) and salt counterions, so ingredient-level recall flags are noisy and the sensitivity run without them matters.
- Overall match rate by year with all methods: 84% in 2018, 86% in 2021, 93% in 2024, 94% in 2026. The 90% target applies to shortages, measured in week 4.

## NDC directory
- Product NDCs are 10-digit hyphenated; packages sit in a nested `packaging` list. `ingestion/utils/ndc.py` normalises 4-4-2, 5-3-2 and 5-4-1 layouts to 11-digit 5-4-2 (9-digit 5-4 at product level), with tests.
- 3 products were quarantined for a missing `generic_name` (hand sanitizers, irrelevant to shortages).
- `route` about 70% filled. `labeler_name` is the marketing labeler, not necessarily the manufacturer. The 26 MB bulk file is re-downloaded in full on each run.
- **Weekly snapshot.** Mondays the directory is saved to the `data` branch as zstd Parquet with 15 selected columns (about 3.3 MB, versus 35 MB raw). The directory shows today's market, so supplier counts for past shortages cannot be reconstructed; the weekly history is what will make time-correct supplier counts possible. A drug can also become sole-source because makers left during a shortage, so supplier count can be a consequence of a shortage as well as a cause.

## Warning letters
- The data.gov XML link (`fda.gov/DataSets/WarningLetters/WarningLettersDataSet.xml`) returns 404 and the Data Dashboard API needs credentials. The working path is the XLSX export behind the FDA page.
- **Correction to the week 1 note:** paging is stable, not erratic. Page 0 is empty, pages 1 and 2 hold all the rows that can be reached, and pages 3 and later only repeat them. Repeated pulls added nothing, so the reachable set is 1,797 unique rows (1,796 after validation). The `search_api_fulltext_issuing_office` filter on the page is ignored by the export.
- **Coverage:** letters posted 2021-01-05 to 2026-04-28, so the last six months are missing and the true total is unknown. The export covers every FDA center; 494 rows come from drug-related offices (matching drug, CDER or pharmaceutical). Use only as a partial firm-level signal with 36-month look-back windows, and state the date range wherever it is reported.
- Time-boxed as agreed. Coverage was not improved beyond the above.

## Pipeline operations
- The daily job snapshots shortages on its own, so a failure in any other source cannot leave a gap in shortage history. The Monday job pulls the NDC directory, recalls and warning letters as separate steps that each run even if an earlier one fails. Shortages (daily), and the NDC directory and warning letters (weekly) are committed to the `data` branch. Warning letters are kept because their export is the fragile source and older rows may disappear; recalls are re-pulled in full because openFDA keeps that history.
- Each step writes a run summary (records landed, quarantined, match rates) to `runs/` on the `data` branch and to the GitHub job summary. A failed run opens a GitHub issue. An extract that yields no valid records raises an error before it can overwrite a good partition.

## Warehouse (dbt) findings
- **Shortage records to families.** 1,597 of 1,608 records (99.3%) link to a product family, above the 90% target: 1,423 by package NDC, 6 by an NDC in the openfda block, 168 by name and dosage form, 11 unmatched. Only 88.9% are NDC-based; the 168 name matches are the weakest and are tagged `name_form`. Most unmatched-by-NDC records are discontinued products that have left the NDC directory.
- **Recall matching moved to SQL** with exact parity to the Python matcher on the same inputs (3,085 / 548 / 8 / 757 / 10,348 by method, 14,746 in total). The parity is a dbt test that fails if either side drifts.
- **Fan-out of ingredient-level matches.** The 9,575 recalls matched only by generic name map to 111,035 recall-family rows (about 12 families each); the 4,181 product-level recalls map to 4,807. Ingredient-level rows must not be counted like product-level ones, which `fct_recalls.match_level` allows.
- **Families.** 12,530 families from finished human-drug products. Every one has a route from the NDC directory, so none needed the dosage-form default or the unknown bucket; the missing routes sit on products excluded as unfinished or non-human. About two thirds of families have a single supplier group. Known limit: salt forms are not separated (for example the base and a salt of one ingredient are different families).
- **Release profile in the family key.** Extended release, delayed release and liposomal products are separate families from immediate release. Before the split there were 12,405 families; after it 12,530 (195 extended, 60 delayed, 6 liposomal), and 123 of the earlier families split. The split was made before the marts so keys do not change later.
- **Firm key.** "and Company", "& Co" and similar are now stripped, so "Eli Lilly and Company" reduces to "eli lilly". Python and SQL implement the same rule and the parity test still passes.
- **Parent-company seed reviewed** against the firms with the most shortage and recall records: 90 mappings across Pfizer/Hospira, Teva/Actavis/Watson, Hikma/West-Ward, Viatris/Mylan, Fresenius Kabi, Sandoz, Baxter, Amneal, Dr. Reddy's, Lupin, Aurobindo/Eugia/AuroMedics, Zydus, Cipla, Sagent, Accord, Apotex, Novartis, Endo/Par and Sun/Caraco, including misspelled variants found in the data. Repackagers and compounders, which dominate the recall counts, are their own groups.
- **NDC duplicates.** 2,447 rows share a product NDC with another row; one deterministic row is kept (reported as `duplicate_product_ndc_rows_dropped`).
- **Unclassified recalls.** Two recalls have classification "Not Yet Classified" and a blank or "N/A" recall number. They are kept and the accepted values include that class.
- **Shortage episodes.** 300 families have a shortage episode, 295 still active; none yet has a second episode. The episode rule (overlapping record intervals merge; a gap or a Resolved-then-Current flip splits) is covered by a unit test.
- **Determinism bug caught by the rebuild test.** The first rebuild check failed because ties in NDC de-duplication were broken arbitrarily. Full tiebreakers were added and the history models now rebuild identically, which `tests/test_warehouse.py` checks in CI.

## Risk signals and watchlist (week 5)
- **Signals are computed as of a date** (family x as_of_date x role). `current` is the latest snapshot date (12,530 families), `case` is each shortage episode's start (300), and `control` is a reference date for each family with no shortage (12,230), dealt out across the case start dates in a fixed order. Every event date behind a signal is strictly before its as_of_date: a dbt test checks the table and a unit test shows a recall or warning letter dated after the as-of date is ignored.
- **Supplier counts** use NDC history when the as-of date is covered by a snapshot and the current directory otherwise, recorded in `supplier_count_source`. Only the `current` rows have history; all case and control rows use today's directory, so the week 6 timing check should filter on this column.
- **Recall flags are split**: `has_recall_product_24m` (NDC-based) and `has_recall_ingredient_24m` (generic name, dosage form unknown) are separate columns, and the watchlist words the second as "recall of the same ingredient (form unknown)".
- **Coverage flags.** `recall_window_covered` and `warning_letter_window_covered` are false when the look-back window starts before the data does. Warning letters begin in 2021-01, so only about 57% of case and control rows have a full 36 month window; absence of a letter before 2024-01 is not evidence.
- **Observed vs inferred days.** `fct_shortage_status_daily` marks days from the first snapshot (2026-10-22) as observed; earlier days are reconstructed from posting and update dates and understate history because older resolved shortages may have left the feed.
- **Watchlist.** 11,374 families have at least one reason, from provisional weights in `seeds/risk_weights.csv`. Most (7,660) score exactly 3 from being sole source alone, which shows why the weights cannot stay as they are: the regression has to decide how much sole-source status matters on its own.
- **Volume checks warn, not fail.** The 7-snapshot average needs 7 earlier snapshots and the NDC check needs a previous weekly snapshot; until then each test warns that there is not enough history.
- **Optional sources degrade to a warning.** With no warning letter snapshot, the staging model warns and continues with an empty table. Shortages, recalls and the NDC directory remain hard failures.
- **Docs.** The dbt documentation is published at /dbt-docs/ on the project site, leaving the site root for the dashboard. The dashboard is registered as a dbt exposure so lineage ends at it.
