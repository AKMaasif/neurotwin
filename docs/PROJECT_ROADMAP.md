# NeuroTwin: project goal, completed work and remaining development

Status snapshot: **11 November 2026**. This is the main project progress and completion checklist. It describes implemented behavior separately from research objectives. No completion percentage is assigned because substantial model-selection and evaluation work remains unresolved.

## 1. Our goal

Develop NeuroTwin into a research brain-health monitoring application with an integrated Brain Analytics workspace. The intended imaging experience focuses on **one person**, potentially with multiple MRI visits. Users should be able to import suitable original scans, run a NeuroTwin-owned processing workflow, inspect real scan-derived anatomy, review measurements and observed changes, and receive grounded AI explanations. Abnormality analysis, Alzheimer's risk estimation and future forecasts are later objectives that require their own evaluated models.

The wider application also supports personal check-ins and activities, consent-controlled sharing, family participation updates, clinician review, and source-linked reporting.

### Agreed design decisions

- NeuroTwin owns the pages, controls, processing workflow, output records and review experience.
- **New processing will not execute FreeSurfer.** Suitable licensed imaging libraries/models may be integrated; owning the system does not require rewriting every numerical method.
- The existing FreeSurfer-generated OASIS outputs remain a clearly labelled **legacy reference**, not native NeuroTwin results.
- The application can focus on one person. Training or evaluating reliable models may still require data from many other research participants.
- Structural MRI supports anatomical analysis. Activity, connectivity and behavioral questions require appropriate additional scans or assessments.
- Language-model agents explain or review evidence; separate imaging/prediction models generate anatomical or predictive outputs.
- Dependencies control execution. Failed, missing or unreviewed inputs cannot silently become accepted analysis.
- This remains a research prototype. Current features do not establish an abnormality, Alzheimer's disease or a future clinical outcome.

## 2. What we have completed

### A. Existing application foundation

| Area | Implemented behavior | Current limitation |
| --- | --- | --- |
| Personal experience | English/Arabic check-ins, a reaction activity, consent and sharing screens, own records/corrections and clinician-written routines/reminders | Prototype activities; clinical scoring and performance are not validated |
| Family experience | Participation updates and controlled messages | Family access is deliberately restricted; no imaging access |
| Clinician workspace | Caseload, timelines, evidence tables, review decisions, access history and factual reports | Research workflows, not clinical validation |
| Access and evidence | Server-side sessions, CSRF checks, purpose-scoped clinical sharing, source attribution and audit history | Production account lifecycle, deployment hardening and review are incomplete |
| Change estimates | Deterministic within-person comparisons of activity records | Not MRI longitudinal analysis and not future prediction |
| Existing language-model support | Gemini/Meta text-provider clients and source-constrained summary-draft flow | Provider availability and output quality require live verification; existing test failures are recorded below |

These are project foundations, not features newly validated clinically by the imaging work. See STATUS.md for the older application feature inventory and its limitations.

### B. One-person legacy imaging reference viewer

The locally supplied derivative archive was inspected for `OAS1_0001_MR1`. It contains actual MRI volumes, segmentation, left/right cortical geometry, region annotations, thickness values and statistics.

Implemented inside NeuroTwin:

- [x] Interactive 3D pial, white and inflated surfaces.
- [x] Zoom, rotation, pan, reset, hemisphere visibility and mesh wireframe.
- [x] Anatomical region colors, thickness maps and transparency.
- [x] Linked MRI slices, slice selection, segmentation overlays and display controls.
- [x] Cortical region picking and a measurement inspector.
- [x] Cutting planes and camera-based Explore Inside navigation.
- [x] A table of 118 supplied measurement rows and CSV export.
- [x] Source/version information, checksums, protected artifact access and QC-pending labels.

**Boundary:** these meshes, labels and measurements were supplied as FreeSurfer derivatives. NeuroTwin did not independently produce or clinically validate them. Inside exploration currently uses surfaces and MRI planes; it is not full volumetric ray casting or microscopic anatomy. Internal structures are volume-label overlays rather than separate native subcortical meshes.

### C. Native original-MRI intake and workflow foundation

Implemented without FreeSurfer execution:

- [x] Import one `.nii`/`.nii.gz` volume or a matching `.hdr`/`.img` pair.
- [x] Confirm intended participant and T1 structural acquisition before file import.
- [x] Import the existing participant's first original raw acquisition directly from the local source archive.
- [x] Preserve original bytes and SHA-256 checksums.
- [x] Store source records and processing-attempt history separately from synthetic clinical records.
- [x] Check supported dimensions, voxel limits/spacing, data type, coordinate-transform sanity, finite values and display intensity variation.
- [x] Accept a single structural volume stored with a trailing singleton dimension; reject actual multi-volume time series.
- [x] Prepare a native display buffer with documented intensity scaling and display geometry.
- [x] Display native slices at physical aspect ratio.
- [x] Use an explicit NIfTI transform for display reorientation where present; withhold anatomical direction labels when orientation is unverified.
- [x] Persist queued/running/failed/awaiting-review/cancelled states and stage details.
- [x] Provide cancellation, eligible retry as a new attempt, bounded image-worker concurrency and restart recovery.
- [x] Enforce research-user access, importing-account ownership, CSRF protection and private artifact responses.
- [x] Make Import & processing the default analytics tab, without requiring legacy viewer artifacts to load.
- [x] Leave unavailable segmentation, measurement, agent and forecast stages explicitly blocked.

The actual original scan completed native preparation. Its stored shape is **256 × 256 × 128 × 1**, with **1.0 × 1.0 × 1.25 mm** voxel spacing. The old Analyze header does not supply an explicit NIfTI spatial transform, so anatomical orientation remains **unverified**. Its run ends at **awaiting review**, not an accepted anatomical result.

## 3. What is not finished

The following are not provided by the current native processing path:

- Independent anatomical QC and persisted imaging-review decisions.
- Brain extraction, tissue segmentation and named-region segmentation.
- Native cortical/subcortical surface reconstruction and validated thickness estimation.
- Native regional brain measurements replacing the imported reference statistics.
- Anatomical editing tools, versioned corrections and dependent reprocessing.
- Live imaging-specific quality, explanation and report-review agents.
- MRI abnormality detection or Alzheimer's risk estimation.
- MRI registration and measured change across visits.
- A trained/evaluated future-outcome prediction model.
- Full volumetric inside exploration, broader modalities or complete tool parity.
- A production-ready clinical deployment.

API keys in `.env` do not mean these features are connected. No MRI disease or forecasting capability should be inferred from the availability of Gemini or Meta clients.

## 4. Remaining development, in order

| Priority | Deliverable | Work to finish | Evidence required before calling it complete |
| --- | --- | --- | --- |
| 1 | Reliable baseline and imaging review | Repair date-dependent summary tests; independently confirm source orientation/acquisition; add stored imaging QC decisions | Relevant checks pass; reviewed findings retain reviewer, source and reason |
| 2 | Native brain extraction and segmentation | Specify the output labels; select a compatible non-FreeSurfer method/weights; verify license/hardware; integrate and evaluate on labelled data | Segmentation accuracy and failures evaluated on held-out reference cases; pending/failed QC remains visible |
| 3 | Native geometry and measurements | Reconstruct appropriate surfaces; extract physical regional volumes; specify surface-area and cortical-thickness methods separately | Geometry aligns with MRI; numerical measures agree with independently checked references; basic display meshes are not called cortical reconstructions |
| 4 | Complete processing lifecycle | Extend current stages to real algorithms; implement revision lineage, stale-output invalidation, dependency-aware reruns, duplicate handling, retention and broader resource controls | Edits/retries/restarts cannot publish stale or incomplete anatomy; attempts are reproducible |
| 5 | Complete analytics tools | Connect native labels/meshes to the viewer; add region/ROI tools, supported distances and saved views; build controlled corrections; improve inside exploration | Tool-by-tool acceptance cases pass on native artifacts; UI identifies source, units and limitations |
| 6 | Ordered AI agents | Verify configured models; define permitted research-data flow; implement three role contracts, source validation, disagreement handling and review history | Live outputs cite stored evidence; invented numbers/claims and malicious metadata are rejected or routed for review |
| 7 | Longitudinal MRI analysis | Add another visit for the same person; implement registration, compatible processing and actual-time-based change estimates | Alignment and timing reviewed; observed changes trace to accepted visits and are not labelled forecasts |
| 8 | Abnormality / Alzheimer's risk research | Define one specific target; select or train a compatible model; obtain required clinical/imaging reference data; evaluate calibration and failure cases | Independent evaluation supports the defined output and population; no unsupported diagnosis |
| 9 | Future prediction research | Define target/horizon/history; obtain a compatible model or longitudinal cohort; compare baselines; evaluate uncertainty and abstention | Participant-separated held-out evaluation, no future-data leakage and justified performance |
| 10 | Reviewed reports and full integration | Combine eligible native measurements, observed changes, model estimates and agent drafts; preserve missingness and approval history | Every statement/result has provenance; reports never silently substitute legacy outputs for native results |
| 11 | Broader capabilities and release readiness | Add only specified modalities/tools; translate imaging controls; review accessibility, storage, account/security and deployment needs | Module-specific validation, representative usability checks and deployment/research requirements satisfied |

This is a dependency order rather than a promise of fixed dates. Agent development can begin once appropriate source facts and data-use arrangements exist. Longitudinal and risk/forecast research can branch from accepted native measurements; they do not all have to wait for every advanced viewer tool.

### Immediate next milestone

**Native brain extraction and segmentation, supported by completed input/QC review.**

- [ ] Confirm how the existing original's anatomical orientation will be established and recorded.
- [ ] Define whether the first native output is a brain mask, tissue classes or named anatomical regions.
- [ ] Identify a suitable non-FreeSurfer algorithm/model and check its documented training labels, license, required inputs and hardware.
- [ ] Obtain required weights/reference labels through their authorized channels.
- [ ] Run an isolated reference case and inspect quality/failures before connecting it to the UI.
- [ ] Add the actual stage to the current worker, with versioned outputs and QC findings.
- [ ] Verify the results against independent references; preserve any remaining uncertainty.

A crude threshold or attractive mesh is not completion of anatomical segmentation. If reference labels themselves come from another software tool, record that provenance rather than claiming independent anatomical ground truth.

## 5. Intended AI-agent order

| Role | Job | It must not do |
| --- | --- | --- |
| Quality Review Agent | Explain stored QC concerns, missing evidence and review questions | Declare anatomy correct from a filename or override failed QC |
| Evidence Explanation Agent | Explain accepted measurements and eligible model outputs with source IDs | Invent measurements, diagnosis, risk percentages or forecasts |
| Report Review Agent | Check a draft against source facts; expose contradictions and unsupported wording | Treat agreement with another provider as proof of accuracy |

An orchestrator starts a role only when its required inputs are ready. Deterministic checks verify source IDs, numbers, units and allowed claims; human review precedes publication. Gemini/Meta selection is configurable. Segmentation and forecasting are distinct trained-model/algorithm stages, not conversational-agent roles.

## 6. Data we have and data still needed

| Purpose | Current position | What remains |
| --- | --- | --- |
| One-person app development | Original OASIS-1 acquisition available and successfully imported | Independent protocol/orientation/anatomical review |
| Reference 3D UI and measurements | Supplied derivative meshes, masks and statistics available | Keep legacy attribution; replace native layers only when actually computed |
| Native segmentation validation | Original scan available; legacy derivatives can be comparison material | Suitable method/weights and appropriately labelled independent evaluation data |
| Same-person change over years | The demonstrated case has one visit | A verified later visit from the same person, plus accurate interval metadata |
| Abnormality or Alzheimer's risk | No evaluated native model connected | Target-specific model and relevant reference clinical/imaging data |
| Future-outcome forecast | No evaluated forecast model connected | A suitable model or broader longitudinal training/evaluation cohort with real follow-up outcomes |
| Functional/diffusion/PET analysis | Not part of the current structural input | Modality-specific acquisitions, metadata, protocols and validation |

For future data acquisition use the authorized [OASIS access route](https://sites.wustl.edu/oasisbrains/request-access/). Follow its current terms and supplied portal instructions; individual-file downloads and approval have not been verified by this project. The earlier dataset inventory remains in FREESURFER_DEVELOPMENT_PLAN.md, but its FreeSurfer-installation/processing decision is superseded.

There is no need to download more people just to display the existing case. Broader data becomes necessary when evaluating generalizable segmentation, risk or prediction performance. Repeated acquisitions from one visit are not longitudinal follow-ups. A third visit is especially useful when testing a forecast made after two historical visits.

## 7. Verification and known limitations

Evidence already collected during implementation:

- Frontend type-check and production build passed.
- **19 focused imaging/native/log checks passed** after the latest native changes.
- Browser checks passed for original-sample import, multipart file upload with confirmation, native slice display, persisted history and phone-width layout; no browser exceptions were reported in that check.
- Legacy viewer checks passed for real anatomy loading, picking, layers, zoom, inside/reset controls, measurement lookup and narrow layouts.
- Source hashes, display buffers, six legacy meshes and cortical statistics were compared with their source files.
- The latest broad run before the final two added native checks recorded **155 passed and 9 failed**. The nine failures are in summary-draft tests whose fixed October date no longer matches rolling demo data; the same failures were reproduced on the unchanged baseline. A fresh full-suite pass is still outstanding after that issue is repaired.

Practical limits:

- Technical consistency checks are not proof of anatomical accuracy or clinical performance.
- Native input limits are currently 80 MiB source files, 160 MiB expanded compressed data and 32 million voxels; supported imports are structural volume formats, not DICOM series.
- The worker is a single-process local prototype. It persists state but does not provide a distributed queue or automatic restart-resume of interrupted computation.
- No persisted native QC acceptance, native segmentation or imaging-agent result currently exists.
- Existing provider clients are text-oriented. Raw MRI interpretation would need a separately specified, evaluated image-model interface.
- OASIS research data must remain separate from synthetic demo participants, with source/data-use conditions retained.
- Imaging controls are currently English; the wider app's Arabic support does not imply complete imaging translation.
- Production account recovery, stronger authentication, storage protection, deployment controls, data retention/deletion and representative usability/clinical review remain work items; see STATUS.md for the wider application backlog.

## 8. How we will know the project is finished

- [ ] The agreed native tool and output inventory is implemented, with deferred features explicitly listed.
- [ ] Original MRI passes through a reproducible native pipeline and appropriate QC review.
- [ ] Anatomy, surfaces, measurements and viewer selections align and retain source/version information.
- [ ] Corrections, failed jobs, retries, interrupted jobs and stale results are handled without silent replacement.
- [ ] AI-agent drafts are grounded, validated and reviewed; unavailable evidence remains unavailable.
- [ ] Every enabled abnormality/risk/forecast model has appropriate independent evaluation and clear limits.
- [ ] Reports distinguish recorded anatomy, observed change, statistical/model estimates and narrative explanations.
- [ ] Access, export, storage, recovery and applicable research/deployment requirements are satisfied for the intended environment.
- [ ] Relevant automated, browser, data-consistency and user-review checks pass, with remaining limitations documented.

The prototype can be considered complete for a limited demonstration before every research objective is achieved, but its displayed capabilities and completion claim must match that limited scope. Research goals must not be marked complete merely because the UI or agent calls run.

## 9. Documentation map

| Document | Purpose |
| --- | --- |
| PROJECT_ROADMAP.md | Main goal, completed work, remaining order and completion checklist |
| NATIVE_IMAGING_AND_AI_PLAN.md | Current processing architecture, role contracts and technical milestones |
| IMAGING_PREVIEW.md | Local preview setup, current tools, access and implementation limits |
| STATUS.md | Wider application feature inventory, experimental areas and review needs |
| ARCHITECTURE.md | Current code/service structure and native workflow foundations |
| FREESURFER_DEVELOPMENT_PLAN.md | Historical interface/data planning; engine decision explicitly superseded |

Update this roadmap whenever a milestone changes status. Record what was verified and on which source/model version; move a checklist item to completed only when its acceptance evidence exists.
