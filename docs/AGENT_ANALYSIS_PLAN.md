# Agent Analysis: two-scan comparison — inventory, gaps and staged plan

Status: all stages are built. Stages 1–2 (validation, alignment) are verified on real OASIS-2 scans. Stages 3–6 run only when
segmentations from a validated tool are imported (`AGENT_ANALYSIS_SEGMENTATION.md`); they are tested on synthetic fixtures and have
not yet run on real segmentations. Nothing here is a diagnosis, a clinical measurement or a prediction.

## What was asked

Compare two MRI scans of one person taken about 12, 15 or 18 months apart, from the original volumes (not screenshots), with
quality review, alignment, anatomical analysis, longitudinal comparison, findings review and a report, shown in a viewer whose
every highlighted region traces back to a measurement.

## What already exists (inspected before building)

| Need | Already in the repo | Notes |
|---|---|---|
| Real longitudinal data | OASIS-2 manifest: 150 subjects, 373 usable visits, `MR Delay` gives real elapsed days | OASIS has relative dates only, no calendar dates |
| Candidate pairs | Manifest pairs within ±1.5 months of target: **12 mo: 7, 15 mo: 24, 18 mo: 42** | counted across all visit pairs of a subject |
| Extracted scans on the PC | OAS2_0001, 0002, 0004, 0005 (`mpr-1` only) | 0001 MR1→MR2 = 15.0 mo; 0004 MR1→MR2 = 17.7 mo; 0002 MR1→MR2 = 18.4 mo. No 12-month subject is extracted yet |
| Reading originals | `oasis2_api._load` reads Analyze `.hdr/.img` with nibabel; native pipeline reads NIfTI | originals are never written to |
| Slice viewer, 3D scene | `SliceView.tsx`, `BrainScene.tsx`, `CompareVisits.tsx` | no overlays, no synchronised zoom yet |
| Run records, retry | `NativeScan`, `NativeRun` (JSON stages, retry via `parent_run_id`) | reused for persistence |
| Access control, audit | `research_access`, `services.audit` | clinician role required |
| Text agents | Quality Review, Evidence Explanation, Report Review (text only, draft status) | defined in `IMAGING_WORKFLOW_STAGES_1_10.md` |

## What is missing, and what it needs

| Missing | Status now | What is needed |
|---|---|---|
| Rigid alignment of the two scans | **Built (Stage 2)** with ANTsPy 0.6.3 (optional dependency) | verified on a real pair, see below |
| DICOM input | **Unavailable** | `pydicom` installs, but there is no real DICOM longitudinal data to verify against. The UI states this; Analyze/NIfTI only |
| Scanner orientation | **Unknown** for OASIS Analyze files | the affine is a default; alignment works in voxel space and no left/right or anatomical label is shown |
| Skull stripping / brain mask | **Unavailable** | a validated tool (e.g. HD-BET, SynthStrip, FreeSurfer) and its weights; none can be downloaded from this environment |
| Validated tissue and regional segmentation | **Unavailable** | FreeSurfer, FastSurfer or SynthSeg plus weights and licence. Without them, no named region (hippocampus, ventricle, cortex) may be shown |
| Regional volume change | **Unavailable** | needs the segmentation above, run on both scans with the same tool version |
| Measurement uncertainty | **Not yet** | same-session repeats (`mpr-2`…`mpr-4`) exist in the archives but are not extracted. They give a test–retest spread for any measure |
| Atlas / template with usable licence | **Unavailable** | MNI templates bundled with nilearn were not accepted; licence is unclear |
| Text explanation of results | Fallback only | Gemini is the only provider. Real OASIS data is not sent to external providers, so until that is approved the explanation is a deterministic template of verified numbers |
| Future prediction | Separate feature | `FORECAST_EXPERIMENT_OASIS2.md`: no skill beyond baselines, so none is offered here |

## Stages

| # | Stage | State | Gate to pass |
|---|---|---|---|
| 1 | Pair selection and validation | **Built** | same subject, recorded dates, interval classed against 12/15/18 mo, headers and intensities checked, mismatches become limitations |
| 2 | Native alignment | **Built** | derived files stored apart from originals; similarity must improve and parameters must be plausible, else the run is flagged |
| 3 | Quality review | **Built** | per-scan range and coverage plus alignment fit; no repeat spread, so no uncertainty |
| 4 | Anatomical analysis | **Built as import** | SynthSeg output run outside NeuroTwin; tool and version recorded; mixed versions refused; labels carried to the earlier anatomy by nearest label |
| 5 | Longitudinal comparison | **Built as import** | per-region volumes from voxel counts in each scan's own space; uncertainty shown as not estimated |
| 6 | Findings review, report, viewer | **Built** | deterministic rules and template (no language model); every region links to its measurements; viewer has layers, opacity, zoom, saved views |

Not done: a measurement-uncertainty estimate (needs the extracted repeat scans), 3D rotation, DICOM input, and a run on real
segmentations (waiting for SynthSeg output from the project owner).

## Rules the build keeps

- Originals stay read-only; derived outputs go to `imaging_data/agent_analysis/<run>/`.
- A step that cannot run says so and names what it needs. Missing is never shown as normal.
- No region is labelled diseased and nothing is called Alzheimer's; imported dataset labels are never inputs.
- The date gap is OASIS's relative `MR Delay`; no calendar dates are claimed.

## Real-data check, stages 1-2

Run with `backend/scripts/agent_analysis_check.py` on scans extracted on the PC (originals unchanged afterwards).

| Pair | Interval | Correlation before → after | Estimated movement |
|---|---|---|---|
| OAS2_0001 MR1 → MR2 | 15.0 mo (class 15) | 0.261 → 0.873 | 4.3° rotation, 13.8 mm shift |
| OAS2_0004 MR1 → MR2 | 17.7 mo (class 18) | 0.215 → 0.892 | 7.2° rotation, 19.1 mm shift |
| OAS2_0001 MR1 → OAS2_0004 MR2 | — | blocked: different people | — |

Rigid alignment takes about 25 s per pair. The correlation is measured over voxels above the earlier scan's 60th intensity
percentile, which is not a brain mask. These numbers show the alignment works on real pairs; they say nothing about brain change.
No 12-month pair is extracted yet (candidates: OAS2_0035, 0049, 0071 MR1→MR2); extract them with `scripts/oasis2_extract.py`.
