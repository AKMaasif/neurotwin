# Imaging workflow, stages 1–10: what we build, in what order, and what is allowed to show

Prepared 11 November 2026. Extends [NATIVE_IMAGING_AND_AI_PLAN.md](NATIVE_IMAGING_AND_AI_PLAN.md) (it keeps the stage table and gates). This is a plan with explicit status; nothing marked *planned* is implemented.

## Facts established from the supplied OASIS-2 files

Inspected locally on 11 November 2026 (files stay on the author's PC, ignored by git):

- Two archives, about 11 GB and 8 GB, each a `.tar.gz`. Inside: `OAS2_<subject>_MR<n>/RAW/mpr-<k>.nifti.hdr` and `.img` (Analyze pairs; several repeats per visit).
- `Demographic Data.xlsx`: 373 sessions, 150 subjects. Columns: Subject ID, MRI ID, Group, MR Delay (days), M/F, Hand, Age, EDUC, SES, MMSE, CDR, eTIV, nWBV, ASF. The `Visit` column holds a formula, so visit order comes from `MR Delay`, never from the formula.
- Visits per subject: 2 (94), 3 (43), 4 (9), 5 (4).
- Gaps between consecutive visits: minimum about 0.5 years, median about 1.8 years. The dataset overview says "at least a year", but the table shows shorter gaps, so every interval is computed from `MR Delay`.
- Missing values: SES 19, MMSE 2. They stay missing.
- Subjects whose first visit has CDR 0: 85, of whom 15 later have CDR above 0. That is the number of events available for any conversion target.
- `eTIV`, `nWBV` and `ASF` are values supplied by OASIS. In NeuroTwin they are labelled **imported**, never "measured by NeuroTwin".
- `Group` (Nondemented / Demented / Converted) is assigned by the dataset using later information. It must never be a model input.

## The ten stages

| # | Stage | Kind | Status now | Gate before its output may be shown |
|---|---|---|---|---|
| 1 | Intake and identity | Software | OASIS-1 single scan done; OASIS-2 reader planned | Known subject, visit, `MR Delay`, file hashes |
| 2 | Technical scan QC | Software | Partly done | Valid geometry, coverage; uncertain scans routed to review |
| 3 | Image preparation | Imaging | Display preview done | Verified physical geometry; orientation shown as unverified for Analyze files |
| 4 | Brain extraction and segmentation | Imaging method | **Blocked**: no evaluated method yet | Method named, versioned, evaluated on a held-out set |
| 5 | Surfaces | Imaging method | Legacy FreeSurfer surfaces for OASIS-1 only | Mesh validity, alignment, anatomical QC |
| 6 | Measurements | Software | **Imported** OASIS values only (eTIV, nWBV, ASF) | Units and estimator defined; label imported vs native |
| 7 | Quality Review Agent | Text model | Planned | Reads stored findings only |
| 8 | Longitudinal analysis | Statistical | Planned (Level 1 and 2) | Same subject; real elapsed time; compatible processing |
| 9 | Abnormality / risk | Separate model | Planned as research experiment | Defined target, reference population, held-out evaluation |
| 10 | Forecast | Separate model | Planned as research experiment | Information at cutoff only; person-separated evaluation; beats baselines or is reported as not beating them |

Stage 4 and 5 for OASIS-2 are not completed in this phase. Stages 6, 8, 9 and 10 therefore use the **imported** measures, and the screen says so.

## Levels shown to users

1. **Level 1, observed change.** Two visits of one subject side by side, with elapsed days from `MR Delay`. Label: "Observed anatomy · no prediction".
2. **Level 2, within-person trend.** Only with at least three visits and a stated measurement uncertainty. With fewer: "Not enough visits to estimate a trend."
3. **Level 3, research forecast.** Switched on only when stage 10 evaluation passes its own rules below. It is labelled a research estimate for population-level evaluation, not a statement about any individual's future.

## Stage 9 and 10 design (decided before looking at any results)

**Targets, fixed in advance**
- Primary (stage 10): among subjects whose earliest visit has CDR 0, does CDR exceed 0 at any later visit? Events available: 15 of 85.
- Secondary: CDR at the next visit (0, 0.5, 1 or more) for all subjects.
- Stage 9 is a **cross-sectional screening** target, "CDR above 0 at this visit". It describes the present state of a visit and is never described as predicting the future.

**Inputs at the cutoff.** Only the first visit's information: age, sex, education, MMSE, eTIV, nWBV, ASF. Nothing from later visits and never `Group`. If a value is missing it is passed on as missing.

**Splits.** Group by subject. All visits of a subject are in the same fold. Repeated, stratified cross-validation by subject. No tuning on the final test fold. The same subject can never appear on both sides.

**Baselines, always reported next to the model**
- Prevalence only (no information).
- Age and sex only.
- Baseline MMSE only.
- Baseline nWBV only.

**Reported:** discrimination with a bootstrap interval, calibration (curve and error), the number of events, precision and recall at stated thresholds, failure cases, and subgroup counts. With 15 events, wide intervals are expected and will be shown.

**Abstention.** Fewer than the required visits, missing key inputs, or a subject outside the age range 60–98 produces "insufficient evidence · request review", never a number.

**Reading the result.** If the model does not clearly beat the simple baselines, the page says that. A result from OASIS-2 does not transfer to another scanner, country or population. OASIS-3 is the next external check, and is not part of this phase.

## From forecast to activities

Recommendations do not come from a model score.

1. Source: the clinician-approved care plan and cited general prevention education.
2. An observed change or a research flag can only create a prompt such as "worth discussing with your clinician". It does not change a routine.
3. A model may draft wording. A clinician approves anything that changes the care plan. No diagnosis, prescription or medication change by a model.
4. Missing activity or an unanswered reminder is never read as deterioration.
5. Family sees only what the person has agreed to share.

## Agents in this workflow

Only three are model-assisted. Everything else is ordinary software.

| Agent | Allowed input | Output | Cannot | Human reviewer |
|---|---|---|---|---|
| Quality Review Agent | Stored QC findings, provenance | Source-linked review questions | See images; pass or fail a scan | Imaging researcher |
| Evidence Explanation Agent | Accepted imported measures, observed changes, stage 9/10 evaluation summaries | Cited plain-language explanation | Invent numbers, give a personal probability | Clinician |
| Report Review Agent | Draft plus source facts | Issue list | Approve, edit numbers | Clinician |

Evaluation scenarios (at least five each, results reported with counts):
- Quality Review: orientation unverified; missing visit; three repeats disagree; instruction hidden in a file name; request to declare the scan normal.
- Evidence Explanation: single visit only; imported versus native label; model not beating baseline; request for a diagnosis; missing MMSE.
- Report Review: number mismatch; unit mismatch; unsupported "will decline" wording; cited ID not in sources; conflicting visit dates.

Real OASIS data is not sent to an external model. Until that is approved, the agents run only on synthetic facts.

## Build order (small pull requests)

1. This document and the Milestone E update.
2. OASIS-2 manifest reader: scan the archive without unpacking everything, build subject and visit records, validate against the table, report missing or mismatched sessions.
3. Level 1 compare view for two visits of one subject.
4. Table loader with imported measures and Level 2 trend with abstention.
5. Stage 9 and 10 research experiment as a reproducible script and report (splits, baselines, metrics, calibration).
6. Show stage 10 results in the app only as an evaluation page, with the rules above.
7. The three agents, evaluated on their scenarios.
8. Tests, screenshots and a limits note.

## Out of scope in this phase

Native segmentation, diagnosis, individual-level risk statements, using `Group` as an input, claims about other populations.
