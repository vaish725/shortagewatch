# Analysis Plan

Written and committed before any outcome model was fitted. The commit timestamp is the evidence of ordering. Changes after that commit are recorded in the Deviations section at the end, never by editing the text above it.

## Data versions

- Shortage feed: snapshot dated 2026-10-22 (UTC). NDC directory: snapshot 2026-10-22. Recalls: pull of 2026-10-22. Warning letters: snapshot 2026-10-22 (posted 2021-01-05 to 2026-04-28).
- Control sampling seed: `20261023`, 5 controls per case (dbt vars `control_seed`, `controls_per_case`).

## What was looked at while building the population

To define the population I counted shortage families by marketing category and product type, by start year, by therapeutic group, and by how many have a full warning-letter window, and I counted the eligible control pool. I did not tabulate any exposure (supplier structure, injectable form, recalls, warning letters) against case or control status, and no outcome model has been run.

## Question

Which supply-side characteristics of a drug product family are associated with the family entering a US shortage? The result is an association with the characteristics measured as described below, used to prioritise a watchlist. It is not a causal estimate.

## Design

Nested case-control design with incidence-density sampling, matched on calendar date.

- **Unit:** product family (sorted active ingredients + dosage form base + release profile + route).
- **Population:** families with at least one finished human prescription product whose marketing category is NDA, ANDA, BLA or NDA authorized generic. This removes over-the-counter, unapproved, homeopathic and allergenic products, which almost never appear on the shortage list and would otherwise inflate any signal that separates prescription from OTC. Of 300 families with a shortage episode, 285 are in the population (15 excluded: unapproved or OTC).
- **Cases:** each shortage episode of a population family, with the case date t equal to the episode start date. 285 cases.
- **Controls:** for each case, 5 families drawn at random (seeded hash order) from population families that were already marketed on t (earliest product marketing start date before t), were not in a shortage episode on t, and are not the case family. A family may be a control for one case and a case later, as is standard for incidence-density sampling. All 285 cases have 5 controls.
- **Exposures** are measured strictly before t (enforced by a test and a unit test in the warehouse).

## Exposures

| Term | Definition |
|---|---|
| sole | Exactly one firm group (parent company where known) markets the family. Measured from the current NDC directory for every row, so it describes current supply structure, not supply before the shortage. |
| generic | Any product in the family is an ANDA. Otherwise brand (NDA, BLA, authorized generic). |
| sole x generic | Interaction of the two terms above. |
| injectable | Dosage form base is INJECTION. |
| recall product 24m | At least one Class I or II recall matched to the family by NDC (product level) reported in the 24 months before t. |
| recall ingredient 24m | At least one Class I or II recall matched by generic name only (dosage form unknown) in the same window. Kept as a separate term, never merged with the product-level term. |
| warning letter 24m | At least one drug-office warning letter, by posted date, to a firm group marketing the family in the 24 months before t. |
| therapeutic group | Five dummy variables (oncology, anti-infective, cardiovascular, CNS and pain, endocrine and metabolic) against "other", from the NDC pharmacologic class text using the rules in `seeds/therapeutic_group_rules.csv`. Adjustment only. |

**Coverage rule.** Recall data start in 2012 and warning letters in 2021-01. A look-back window that begins before the data does is not evidence of no event. Each recall and warning-letter term is therefore set to 0 for every member of a set whose window is not fully covered (`recall_window_covered`, `warning_letter_window_covered`). Such sets then carry no information about that term and cannot bias it, while still contributing to the other terms. Cases with a fully covered 24-month warning-letter window: 188 of 285.

**Parameter budget.** 12 parameters: sole, generic, sole x generic, injectable, recall product, recall ingredient, warning letter, 5 therapeutic dummies. With 285 cases this is about 24 cases per parameter.

## Primary model

Conditional logistic regression (statsmodels `ConditionalLogit`), one stratum per case with its 5 controls, using all 285 sets and the 12 parameters above, with 24-month windows. Odds ratios with 95% confidence intervals.

Contrasts reported, all relative to a multi-source brand family:

- sole-source brand: exp(b_sole)
- multi-source generic: exp(b_generic)
- sole-source generic: exp(b_sole + b_generic + b_sole_x_generic)
- sole source among generics (the fragile-generic contrast): exp(b_sole + b_sole_x_generic)

**Confirmatory hypotheses (four, direction pre-specified as increased odds):**

1. H1: sole-source among generics, exp(b_sole + b_sole_x_generic) > 1.
2. H2: injectable, exp(b_injectable) > 1.
3. H3: product-level recall in the prior 24 months, exp(b_recall_product) > 1.
4. H4: warning letter in the prior 24 months to a marketing firm, exp(b_warning_letter) > 1.

Two-sided p-values with Holm adjustment across these four. Everything else is exploratory.

## Sensitivity analyses

Each re-fits the primary model with one change and reports the same odds ratios, with the number of cases next to every estimate.

1. **Without ingredient-level recall matches:** drop the recall ingredient term.
2. **Recent cases:** only cases with start date on or after 2025-10-22 (the last 12 months before the snapshot). The case count is reported; if it is small the result is described as imprecise. This check is informative about supplier counts because the current directory is closest to the true pre-shortage structure for recent cases.
3. **Look-back windows:** recall and warning-letter windows of 12, 24 and 36 months. The 36-month warning-letter window applies only to sets with full 36-month coverage (case date on or after 2024-01-05).
4. **Without large firms:** drop families with a supplier among the ten firm groups marketing the most families, from both cases and controls.
5. **Plain logistic regression check:** unconditional logistic regression on the same rows, adding case-year group indicators (up to 2018, 2019 to 2022, 2023 to 2024, 2025, 2026) and cluster-robust standard errors by family, to check that conditioning on sets does not drive the result.

## Exploratory

Therapeutic group coefficients; sole-source brand and multi-source generic contrasts; release profile and route; Class I recalls only; supplier bucket as 1, 2-3, 4 or more instead of sole; any interaction not listed above; any subgroup. These are reported as hypothesis-generating with unadjusted intervals and are not used to change the primary model.

## Limitations stated in advance

- Association, not causation. A recall and a shortage can share one cause such as a quality failure at a plant.
- Supplier structure is today's. A drug can become sole source because manufacturers left during a shortage, so cause and effect can run backwards. Weekly NDC snapshots started on 2026-10-22 will allow time-correct counts later.
- Family matching of recalls by generic name cannot distinguish dosage forms. Its precision is measured separately (below).
- Controls are reused across sets and a control may later be a case, so sets are not fully independent; intervals may be slightly optimistic.
- Shortage start dates come from the FDA feed's posting dates. Shortages that resolved long ago may have left the feed, so cases skew towards shortages that persisted.
- Warning letters are available only from 2021-01 and the export may be incomplete.

## Precision of ingredient-level recall matches

A pair is a recall and a matched generic name from the generic-name method.

**Rules, fixed before labelling.** Label 1 (correct) when the matched ingredient is an active ingredient of the recalled drug product, including each active ingredient of a combination product and of a kit component that is itself a drug. Label 0 (incorrect) when the ingredient appears only as an excipient, diluent, vehicle, packaging or device component, brand or company name, a different drug named in the text, or a food or cosmetic. Label 0 also when the text is too ambiguous to decide, and such cases are counted and reported separately as "unclear". Dosage form is deliberately ignored, because the match is ingredient level by design.

**Sample.** 100 pairs, chosen by ordering all pairs by `md5(recall_number || '|' || matched_ingredient || '|' || seed)` with seed `20261023` and taking the first 100. The labelling sheet shows only the recall product description and the matched name; it shows nothing about families, cases or controls, so labelling is blind to outcome by construction. The labeller is the AI assistant (Claude); there is one labeller and no independent second rater, which limits the evidence on label reliability.

**Reproducibility.** The sampled pairs and labels are committed as `warehouse/seeds/ingredient_match_labels.csv`. Precision is computed from that file alone, so later recall pulls do not change it. Reported as a proportion with a Wilson 95% interval.

## Duration

Descriptive only, labelled preliminary. Age distribution of the active shortage episodes (median, quartiles, by injectable versus other). Kaplan-Meier curve for time from start to resolution with active episodes right-censored, and an explicit note that only 5 episodes are resolved. Shortages that resolved long ago may have dropped out of the feed, so observed durations lean long. No log-rank tests or Cox model.

## Risk score and validation

- **Points from the primary model.** Each watchlist signal gets integer points = round(coefficient / log(1.25)), so one point is a 25% rise in odds. Signals: multi-source generic, sole-source brand, sole-source generic (sum of the three relevant coefficients), injectable, product-level recall, ingredient-level recall, warning letter. Negative or zero results give 0 points and the signal does not fire. Therapeutic group is adjustment only and carries no points. Points are written to `warehouse/seeds/risk_weights.csv`.
- **Pseudo out-of-time validation.** Fit the primary spec on sets with case date before 2025-01-01 and score sets with case date from 2025-01-01. Metric: within-set AUC (the share of case-control pairs in which the case scores higher, ties counted half), averaged over test sets, with a 95% interval from 2,000 bootstrap resamples of test sets (seed 20261023). Compared with the baseline that ranks by supplier count alone (fewer suppliers scores higher). Because supplier counts are measured today they carry information from after the case date, so the result is optimistic and is labelled as such.
- **Ties.** The watchlist is ordered by score, then most recent product-level recall, then fewer suppliers, then most recent warning letter, then family key.

## Deviations

None recorded at the time of commit.

Recorded after the models were run (2026-10-23). None of these changed an estimate or a decision rule.

1. Convergence: statsmodels `ConditionalLogit` returns no convergence flag, so a model is marked converged when all standard errors are finite and no coefficient exceeds 15 in absolute value (a guard against separation). The plan did not specify a check.
2. Precision: in addition to the strict estimate (unclear cases count as incorrect, as planned), a lenient estimate that counts the unclear cases as correct is reported, because most unclear labels were salts or esters of the matched name.
3. Without large firms: sets are kept only if both a case and at least one control remain after removing large-firm families.
4. The plain logistic check omits the sole-source contrasts because it does not use the interaction contrasts; it reports single terms only.
