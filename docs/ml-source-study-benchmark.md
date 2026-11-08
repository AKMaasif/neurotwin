# Original-source ML research benchmark

8 November 2026. Status: trained, calibrated and evaluated for exploratory research. **Clinical release and application-patient inference are blocked.** This does not calibrate the older illustrative longitudinal state-space estimator.

## Permitted data and provenance

Source: Bissig, Erten-Lyons, Lutsep and Kaye, SATURN author deposit, DOI https://doi.org/10.5061/dryad.02v6wwpzr ; accessible mirror https://zenodo.org/records/3962060 . The repository metadata identifies the deposit as CC0-1.0. The acquisition script checks that license identifier and verifies the two published file checksums before writing to ignored `data/ml-source/` storage:

- `SATURN_DATA_2020_06JUN_24_DATA_worksheet.csv`: MD5 `ea4fcc55d829a47ea7ca04fb17c031ab`.
- `SATURN_DATA_2020_06JUN_24_INFO_worksheet.csv`: MD5 `b0fa655a0a4267241b6704ca82012b2e`.

The actual data file SHA-256 is `c55464a3c729a2ab7fa795977201acb7098c5da0ef1d0d2b3e602c0076b31204`. Raw participant data, identifiers, notes, audio and split membership are not included in the repository or served by the application. Published artifacts contain aggregate evaluation and JSON numerical parameters, not patient rows or a pickle executable.

## Target and cohort decision

The source CSV contains 79 participants across three development phases. The dictionary documents different tasks, mathematics questions and time-limit handling in earlier phases. We restrict this benchmark to phase 3, English source-study participants aged 50–89. Thirty-nine rows from earlier phases and eleven final-phase rows without a reference label are excluded, leaving **29 eligible participants**.

The target is the original study's **CDR greater than zero versus rated/presumed normal**. It is cross-sectional, not a forecast of future decline, an Alzheimer's diagnosis, or an outcome from our mobile adaptation. The dictionary explicitly defines CDR `-1` as presumed normal under the original study protocol, usually a study partner. It is not a negative clinical CDR score. Missing `NA` labels are excluded; they are never silently changed to normal.

The CLI excludes presumed-normal labels unless the operator explicitly supplies `--allow-presumed-normal`. This benchmark includes them with that flag and exposes their counts. **Only one negative participant has an independent clinical rating; the other 18 negatives are presumed normal.** Neither the calibration nor test partition has an independently clinically rated negative. This is a major limitation, not a clinical validation cohort.

## Leakage controls and training

- Features are restricted to original SATURN total, age and years of education. CDR components, TYPE, clinic, MoCA outcomes and identifiers are excluded from model inputs.
- Education is present in the source study; a matching reviewed education-intake contract is not currently collected by the app. No missing app input is invented to enable inference.
- Participant IDs must be unique. Linked patient–partner dyads identified by COUPLE remain together across all splits. Splits are fixed before fitting or test evaluation; test seeds are not searched to improve results.
- Median imputation, standardization and regularized logistic regression are fit on training participants only. Missing source totals are rejected instead of zero-filled. The source authors' original score aggregation differs from our app's missing-evidence policy; they are not interchangeable.
- A fixed regularized sigmoid calibrator is fit only on the separate validation partition. No test thresholds or hyperparameters are tuned. The classification threshold is fixed at 0.5.
- The prevalence-only baseline, uncalibrated model and calibrated model are all reported. Calibration is not automatically deemed successful.
- Fixed seeds: split 42/43; model 44; calibrator 45; group bootstrap 46. The runtime library version is recorded in the evaluation artifact.

| Partition | Participants | Linked groups | Positive | Negative | Presumed-normal negatives |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training | 15 | 10 | 5 | 10 | 9 |
| Calibration | 7 | 5 | 2 | 5 | 5 |
| Untouched test | 7 | 5 | 3 | 4 | 4 |

## Actual held-out results

| Model | ROC AUC | Brier score (lower is better) | Log loss | Balanced accuracy |
| --- | ---: | ---: | ---: | ---: |
| Training-prevalence baseline | 0.500 | 0.254 | 0.703 | 0.500 |
| Uncalibrated logistic regression | 0.833 | 0.177 | 0.507 | 0.708 |
| Validation-calibrated model | 0.833 | 0.189 | 0.576 | 0.667 |

The calibrated confusion matrix is `[[4, 0], [2, 1]]`, ordered negative/positive. These are seven test participants, not percentages established for a target population. The linked-group bootstrap ROC AUC interval is approximately **0.20–1.00**, with 987 valid replicates out of 1,000. Five held-out dyads cannot support precise clinical, subgroup or Gulf-population claims.

Calibration worsened both Brier score and log loss compared with the uncalibrated model. It improved on a prevalence-only baseline, but this does not establish useful clinical calibration. Neither model is promoted for patient use. All artifacts explicitly retain `clinical_use=false`, `release_approved=false` and `runtime_patient_inference=false`.

## Application integration

Dashboard → Patient workspace → **Source-study ML benchmark** loads the evaluated original-cohort results. `GET /api/patients/{pid}/research-model` requires a clinician's review scope in a synthetic workspace, verifies the model artifact checksum, returns an allowlisted report and records an attributed read audit. It accepts no inference or training request and reads no current patient's task answers. Family and participant access are rejected.

The existing illustrative numerical estimator remains separately labelled. Training a source-study classifier cannot estimate longitudinal process/measurement noise or validate the adapted activity protocol. No weekly report, care plan, triage queue or patient assessment is automatically changed by this benchmark.

## Reproduce

```powershell
uv sync
uv run python -m scripts.fetch_research_data
uv run python -m scripts.train_research_model data/ml-source/saturn-original.csv data/my-new-model-run --allow-presumed-normal
```

Use a new output directory: overwriting an existing run is refused. The training CLI accepts only the checksum-pinned author source, preventing unrelated uploads from being mislabelled as this study. Review the permission and dictionary again if the source release changes. On this machine, a separate fresh download/train run reproduced both the model bytes and evaluation JSON exactly. See `research-artifacts/original-saturn-v1/` for the committed benchmark artifacts.

## Remaining clinical/model requirements

A sufficiently sized, permitted cohort matching the actual app protocol, appropriate independently assessed negative and positive labels, reviewed feature availability, external population/device evaluation and subgroup analysis are still required. Longitudinal prediction additionally needs repeated visits and time-aware outcome definitions. Qualified clinical approval and real-patient governance remain outstanding. The original English/Oregon cohort does not establish Arabic, Gulf, smartphone or adapted-test validity.
