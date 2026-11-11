# OASIS-2 research experiment: stage 9 (same-visit screening) and stage 10 (conversion)

Run on 11 November 2026 on the supplied `Demographic Data.xlsx` (373 sessions, 150 subjects). Rules were fixed before the run in [IMAGING_WORKFLOW_STAGES_1_10.md](IMAGING_WORKFLOW_STAGES_1_10.md). Code: `backend/app/research_forecast.py`, `backend/scripts/run_forecast_experiment.py`; the tests check that later-visit values cannot change the inputs, that a subject is never on both sides of a split, and that missing inputs abstain.

This is population-level research reporting from one small dataset. It says nothing about any individual and is not a diagnostic or prognostic tool.

## Stage 10: does a first visit with CDR 0 later have CDR above 0?

- Cohort: 85 subjects with CDR 0 at their first visit and at least one later visit. Events: 15. Abstained for missing inputs: 0. Median follow-up 3.3 years (follow-up length varies and is not an input, so "any later visit" mixes short and long follow-up).
- Inputs: first-visit age, sex, education, MMSE, eTIV, nWBV, ASF. Evaluation: 5-fold stratified cross-validation repeated 50 times, one row per subject.

| Model | Inputs | AUROC (95% interval) | Brier skill vs prevalence | Shuffled-outcome control AUROC |
|---|---|---|---|---|
| prevalence_only | none | 0.50 (0.50–0.50) | +0.00 | – |
| age_sex | Age, Female | 0.56 (0.39–0.73) | -0.02 | 0.44 |
| mmse_only | MMSE | 0.09 (0.02–0.19) | -0.03 | 0.40 |
| nwbv_only | nWBV | 0.56 (0.39–0.72) | -0.01 | 0.50 |
| all_baseline_inputs | Age, Female, EDUC, MMSE, eTIV, nWBV, ASF | 0.43 (0.28–0.60) | -0.10 | 0.46 |

**Result.** No model shows usable skill. Every interval includes 0.5 or lies below it, and no model has a positive Brier skill. The multi-input model does not beat the simple age-and-sex baseline (0.43 against 0.56). Values below 0.5, such as the MMSE-only figure, are a known artefact of cross-validation on weak, coarse inputs (MMSE takes only five values here), which is why the shuffled-outcome control is shown: it sits at about 0.40–0.50 when there is no signal. Read those rows as "no evidence of skill", not as inverse skill. Converters were older on average (median age 80 against 75), which the age-and-sex baseline picks up only weakly.

Fifteen events cannot support a forecast model. **No forecast result is shown in the app from this experiment.**

## Stage 9: is CDR above 0 at this same visit? (screening, describes the present)

- 371 visits from 150 subjects; events 165; abstained for missing inputs 2 visits. Evaluation grouped by subject (all visits of a person stay together), 5 folds, 50 repeats.

| Model | Inputs | AUROC (95% interval) | Brier skill vs prevalence | Shuffled-outcome control AUROC |
|---|---|---|---|---|
| prevalence_only | none | 0.50 (0.50–0.50) | +0.00 | – |
| age_sex | Age, Female | 0.43 (0.33–0.52) | +0.05 | 0.45 |
| mmse_only | MMSE | 0.81 (0.74–0.87) | +0.45 | 0.41 |
| nwbv_only | nWBV | 0.68 (0.59–0.75) | +0.10 | 0.42 |
| all_baseline_inputs | Age, Female, EDUC, MMSE, eTIV, nWBV, ASF | 0.90 (0.85–0.94) | +0.49 | 0.47 |

**Result.** Discrimination is high, mostly from MMSE. That is expected and not a discovery: MMSE and CDR are both clinical measures of the same condition, so predicting one from the other is close to circular. It is not evidence that imaging-derived measures detect anything. nWBV alone is modest (0.68). All inputs are imported from the OASIS table; none was measured by NeuroTwin.

## What this allows

- Show on an evaluation page, labelled research, that same-visit screening from these inputs works at population level and that conversion could not be predicted from this dataset.
- Not allowed: any per-person risk or future-decline statement, any use of the Group label, any claim that results transfer to another scanner, clinic or population.

## Limits

- One dataset, 150 subjects, one source of labels (CDR assigned by clinicians who also gave MMSE).
- No external validation. OASIS-3 is the next candidate and is not part of this phase.
- Imported measures (eTIV, nWBV, ASF) come from OASIS processing, not from NeuroTwin's own pipeline.
- Intervals come from a subject bootstrap of cross-validated predictions and are optimistic for small samples.
- Calibration was checked in three bins; with 15 events it is not informative for stage 10.
