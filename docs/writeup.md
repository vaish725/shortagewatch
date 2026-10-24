# What public FDA data can (and can't) tell us about which drugs will go short next

Hospital pharmacists usually find out a drug is short when it shows up on the FDA's shortage list. By then the alternatives are already being bought up. The warning signs that come earlier (recalls, regulatory action against a manufacturer, how few firms make the drug) are public, but they live in separate FDA datasets that share no key. I built ShortageWatch to join them, find out which signals actually go with shortages, and publish a weekly watchlist with a reason attached to every flag.

This is what I learned, including the hypothesis that failed. The live dashboard is at https://vaish725.github.io/shortagewatch/ and the code is at https://github.com/vaish725/shortagewatch.

## Why the data was the hard part

The project uses four free sources: the openFDA drug shortage feed, the openFDA recall (enforcement) reports, the National Drug Code (NDC) directory, and FDA warning letters. Four problems shaped everything else.

**The shortage feed has no history.** It shows only the current state, one record per package. Across 1,608 records there are about 320 distinct product families, and a single shortage of one drug can appear as dozens of records. Counting records would inflate every number. So the unit of analysis is a product family (active ingredients, dosage form, release profile and route), and the pipeline snapshots the feed every day and keeps the dated files, because history cannot be backfilled later. Because the warehouse is rebuilt from scratch on every run, I rebuilt the change history from the dated files instead of using dbt snapshots, which would have lost their state.

**Recalls have no drug identifier.** Only 17% of recalls carry the enrichment block that links them to a product. I pulled NDC numbers out of the recall text with a regular expression, normalised them to 11 digits, and matched firm and product names as a fallback, then ingredient names as a last resort. Every match records its method. Matching rate depended heavily on age: the NDC directory lists only products on the market now, so recalls of long-gone products cannot match. For recalls in the 24-month analysis window, 94% link to a product or ingredient and 64% to a specific product. I wrote the matcher twice, in Python and in SQL, and a test fails if the counts differ by method.

**The ingredient-level fallback is noisy, and I measured how noisy.** I drew 100 matches with a fixed seed and labelled them blind to which drugs were later in shortage. Only 57% were correct (95% interval 47% to 66%). The errors were diluents such as sodium chloride, vehicles, and descriptor words. That number mattered later.

**One warning-letter source was only half available.** The documented XML file returned a 404 and the dashboard API needs credentials. The working path was an export on the FDA page that reaches roughly 1,800 letters posted between 2021 and April 2026. I treated it as a partial signal and said so wherever it appears.

## The design: commit the plan first

Looking for risk factors in a pile of data invites finding whatever is there. To prevent that, I wrote `docs/analysis_plan.md` and committed it before fitting a single model. The commit timestamp is the evidence of ordering. It names the population, the four confirmatory hypotheses, the windows, the sensitivity checks, and what would count as exploratory. Changes made afterwards are recorded in a Deviations section appended at the end, never by editing the original text.

The design is a nested case-control study. A case is a product family at the start of a shortage episode. For each case I drew 5 controls at random from approved prescription families that were already on the market and not short on that date, with a fixed seed (incidence-density sampling). Matched sets are analysed with conditional logistic regression. Two choices were important:

- **Restrict to approved prescription drugs.** The NDC directory includes over-the-counter, unapproved and homeopathic products that almost never appear on the shortage list. Left in as controls, any signal that separates prescription from OTC would look like a shortage predictor. Of 300 shortage families, 285 were in the approved prescription population.
- **Measure every signal as of a date, and test for leakage.** A recall or warning letter dated after a shortage began cannot be a risk factor for it. The risk-signal table is built at a family and as-of-date grain, and a test fails if any event date is on or after its as-of date. A unit test checks that a recall dated after the as-of date is ignored.

Coverage needed care too. Recalls start in 2012 and warning letters in 2021, so a 24-month look-back can start before the data does. For those sets the term is set to zero for every member. This is not the same as saying "no letter". Every member of a matched set shares one date and so one coverage status, and in conditional logistic regression a set with no variation in a term contributes nothing to that term's estimate. Those sets simply drop out of the estimate.

## What the data said

Results below are from 285 matched sets; intervals are 95%.

| Factor | Odds ratio |
|---|---|
| Injectable dosage form | 4.36 (3.25 to 5.86) |
| Product-level recall, prior 24 months | 1.83 (1.22 to 2.76) |
| Warning letter to a marketing firm, prior 24 months | 1.74 (1.18 to 2.56) |
| Sole source among generics | 0.76 (0.43 to 1.35) |
| Sole-source brand | 0.44 (0.22 to 0.87) |

Injectables are the clearest signal, and it held in every sensitivity check, though it roughly halved (2.2) when I removed families made by the ten largest manufacturers. A recent recall of the same product and a warning letter each go with higher odds. The warning letter effect vanishes without large firms (0.71, 0.30 to 1.68), so I describe it as driven by big manufacturers rather than as a robust risk factor.

**My main hypothesis was not supported.** I expected sole-source generics, where one remaining manufacturer supplies a drug, to be the fragile case. They were not (0.76, interval spanning 1), and sole-source brands, which are monopolies by design, had lower odds. In the most recent 12 months of cases the sole-source generic estimate was lower still (0.33, 0.12 to 0.89). Because the plan was committed first, this is a finding I can state plainly and not something I could have quietly tuned away.

Active shortages tell a related story. Active injectable shortages have been open a median of 1,319 days (about 3.6 years), against 239 days for other forms. Only 5 of 300 episodes have resolved, so I did not fit survival models and show the curve as preliminary. Shortages that resolved long ago may have left the feed, so observed durations lean long.

## What changed along the way

Three decisions after the first results, all recorded in the plan:

1. **I tested whether product count explained the supplier results.** A family counts as a case if any of its products is listed, so families with many products have more chances to appear. Adding the log of the product count was a post hoc check, and I labelled it that way. It explained part of the pattern (sole source among generics moved from 0.76 to 0.99) but not all, and it did not rescue the hypothesis. Multi-source generics, which had earned one point in the score, fell to zero points after adjustment, so I dropped that signal. Otherwise the watchlist would quietly reward "has many products".
2. **I made ingredient-level recalls informational.** Its estimate was exploratory and, at 57% precision, about four in ten of its watchlist reasons would be wrong. The watchlist shows "same-ingredient recall, form unverified" but gives it no points.
3. **I added a harder baseline.** Injectable form is 7 of the 12 possible points, so the real question is whether recalls and warning letters add anything beyond it. On shortages held out in time (fitted on cases before 2025, tested on 154 cases from 2025 to 2026), the points score reaches an AUC of 0.63 (0.58 to 0.68) against 0.57 for injectable form alone. The paired difference is 0.06 (0.03 to 0.08), which excludes zero. It is modest, and optimistic because supplier counts come from today's directory.

I also froze the inference. If the models refit on every pipeline run, the odds ratios would drift away from the committed plan and from this write-up. So the dashboard keeps its overview, active shortages and watchlist signals live, and the Insights page reads results committed with their date and code commit.

## What this can and cannot tell you

- **Associations, not causes.** A recall and a shortage can share one root cause, such as a plant quality failure.
- **Supplier structure is today's.** A drug can become sole source because makers left during a shortage, so cause and effect can run backwards. Weekly NDC snapshots started on 2026-10-22 will allow time-correct counts.
- **The FDA list defines shortages narrowly** compared with other trackers, and cases skew toward shortages that persisted.
- **The watchlist is a prioritisation aid.** An AUC of 0.63 means it ranks better than chance and better than injectable form alone, not that it predicts which drug is next.

## What I would do with more data

The daily snapshots will eventually give real out-of-time data, which would replace the pseudo out-of-time split and make duration modelling possible as more shortages resolve. A stop-list for diluents and descriptor words should raise the ingredient-level match precision, but it needs a fresh labelled sample to show it worked. Time-correct supplier counts would settle whether supplier structure is a cause or a consequence. Drug pricing data would add an economic signal of tight supply.

The most useful lesson was procedural. Writing the plan down first made a null result usable, and measuring the weakest link in the pipeline (a 57% precise match) changed what the product is willing to claim.
