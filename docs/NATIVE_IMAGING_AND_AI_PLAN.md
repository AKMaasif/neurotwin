# NeuroTwin-owned MRI processing and ordered AI workflow

For the consolidated goal, completed work, prioritized backlog and acceptance checklist, start with
[PROJECT_ROADMAP.md](PROJECT_ROADMAP.md). This file specifies the current architecture and research contracts.

## Decision and present status

The target architecture no longer runs FreeSurfer as its processing engine. NeuroTwin will own the scan workflow, artifact formats, geometry, analysis interfaces, model execution, visualization and review history. Use appropriately licensed numerical/imaging libraries and separately evaluated models rather than requiring every mathematical operation to be written from scratch.

This document supersedes the processing-engine decision in FREESURFER_DEVELOPMENT_PLAN.md. Its viewer requirements, data provenance and evaluation checks remain useful.

The legacy 3D preview uses imported FreeSurfer-generated OASIS derivatives, labelled separately from native results. Native original-scan import, technical validation, display preparation and durable run history are now implemented. The original OASIS acquisition has completed this native path with orientation review pending. Native segmentation, abnormality detection, Alzheimer risk models, forecast models and imaging AI-agent execution are not implemented.

## Product objective

One participant in the application, with one or more scan visits. Users import original volumetric MRI, run available analysis, inspect scan-derived anatomy, review results, and view eligible evaluated model outputs. Training and evaluation may require many other research participants even when the application displays only one person.

## Processing order and responsibility

The workflow runner owns dependencies and transitions. Language models cannot mark missing work complete, bypass failed QC, invent measurements or approve a release.

| Order | Component | Type | Input → output | Gate |
| --- | --- | --- | --- | --- |
| 1 | Intake and identity | Software service | Original MRI + metadata → immutable scan record and source checksum | Complete supported scan; known identity, visit and coordinate frame |
| 2 | Technical scan QC | Software service | Volume/header → geometry, coverage and protocol-specific quality findings | Reject invalid input; route uncertain quality for review |
| 3 | Image preparation | Imaging algorithms | Accepted original → versioned working volume and transforms | Verified physical geometry; no silent left/right reversal |
| 4 | Brain extraction and segmentation | Imaging model/algorithm | Working scan → masks, tissue/region labels and confidence information where supported | A compatible, versioned method must exist and pass evaluation |
| 5 | Surface reconstruction | Imaging algorithms/model | Appropriate masks and tissue boundaries → surfaces and overlays | Mesh validity, coordinate alignment and anatomical QC |
| 6 | Measurement extraction | Software service | Reviewed labels/surfaces → volume, area and supported thickness measurements | Correct units, estimator definition and source artifacts |
| 7 | Quality Review Agent | Bounded language-model role | Stored QC findings and provenance → source-linked review questions | Text agent cannot independently inspect raw MRI or replace anatomical QC |
| 8 | Longitudinal analysis | Imaging/statistical service | Accepted historical visits → registration and observed changes | Same participant; adequate timing; compatible processing |
| 9 | Abnormality / risk models | Separate imaging/statistical models | Eligible scan/features → explicitly defined finding or risk estimate | Model-specific evaluation, reference population and uncertainty |
| 10 | Forecast inference | Separate prediction model | Information available at cutoff → defined future target and horizon | Eligible history; held-out evaluation; no future-data leakage |
| 11 | Evidence Explanation Agent | Bounded language-model role | Available accepted results → cited factual explanation | Never substitutes its own disease probability or missing result |
| 12 | Report Review Agent + deterministic checks | Bounded language-model reviewer plus software validator | Draft + source facts → identified issues or review-ready draft | Numbers, citations, units, claims, missingness and consistency checked |
| 13 | Human review and publication | Reviewer-controlled workflow | Review-ready results → approved report or returned work | Review recorded; automatic checks do not establish clinical validity |

Stages 8–10 are conditional branches. A single accepted scan may support viewing and measurements without supporting change or forecasting. Reports must say a branch was unavailable rather than fabricating its result. Alzheimer's risk is one possible separately specified model target, not a capability implied by segmentation or an API key.

## AI roles and provider allocation

Start with three bounded language-model roles, rather than adding many overlapping agents. Keep provider selection configurable; role order is independent of whether Gemini or Meta supplies a response. Verify actual model availability using existing provider utilities without logging keys.

1. Quality Review Agent: summarize recorded quality concerns and missing evidence. It can recommend review, not declare anatomy correct.
2. Evidence Explanation Agent: explain source measurements, observed changes and any separately evaluated model output using cited facts.
3. Report Review Agent: identify unsupported wording, number mismatches and unresolved conflicts before human review.

Do not label a numerical operation or ordinary job worker an intelligent agent. An imaging segmentation network is also distinct from a conversational agent.

Each role must have a versioned prompt, explicit allowed inputs, structured response schema, cited source IDs, timeout/cost limits and an abstention path. Current provider clients accept text; giving a quality agent a filename is not giving it the image. Multimodal review, if later added, requires a separately defined data contract and evaluation.

The current LLM module restricts external processing to synthetic demo facts until real-data processing is permitted. Keep live OASIS imaging outside external model calls while data-use/provider arrangements are unresolved. API keys remain server-side. Never send .env contents or silently include raw MRI in a text prompt.

Using two providers does not make their agreement proof of correctness. Preserve disagreements; deterministic source checks and human review remain necessary.

## Workflow execution contract

- Durable states: pending, running, succeeded, failed, awaiting_review, blocked, skipped and cancelled.
- A stage starts only when its required dependencies succeeded and its prerequisites still hold.
- Each run records source hashes, algorithm/model/prompt versions, parameters, time, artifacts, warnings and review decisions.
- Retry transient execution errors under a limit; do not retry rejected science/QC inputs until they are corrected.
- Reuse outputs only when input hashes and producer configuration match. Input edits invalidate dependent results.
- Cancel downstream execution on failed prerequisites; preserve earlier valid artifacts and expose recovery actions.
- Record the distinction between imported results, locally computed measurements, model estimates and generated narrative.
- No fabricated progress percentages, completed jobs, confidence values or inferred normality when a stage is unavailable.

## Native processing milestones

### A. Original scan intake and geometry

- [x] Import the existing participant's original MRI volume, preserving paired headers where required.
- [x] Prepare a supported working display buffer while preserving originals and coordinate transforms.
- [x] Check dimensions, voxel spacing, datatype and finite intensities; record geometry findings and user-declared modality.
- [x] Label native inputs separately from the existing derivative preview.
- [x] Render native slices at physical aspect ratio; withhold anatomical direction labels when orientation is unverified.
- [ ] Independently verify acquisition metadata, anatomical coverage, motion and orientation; these remain pending review.

Exit: original MRI can enter the application without reading a FreeSurfer-derived segmentation or mesh.

### B. Native masks and independently generated meshes

- [ ] Specify whether the first output is a basic display mask, tissue segmentation or named-region anatomical segmentation.
- [ ] Evaluate candidate non-FreeSurfer methods, model weights, input assumptions, hardware and licenses before selecting one.
- [ ] Integrate a versioned method; a simple intensity threshold is not a validated anatomical segmentation.
- [ ] Evaluate segmentation on appropriately labelled held-out data; document provenance if labels were generated by another tool.
- [ ] Build a mesh from the accepted mask with correct physical coordinates; assess topology, surface placement and volume consistency.
- [ ] Label a basic extracted mesh as such. It is not equivalent to cortical white/pial reconstruction or a thickness estimator.

Exit: newly generated native artifacts can replace the imported display layer for their stated purpose, without claiming unvalidated regional or cortical accuracy.

### C. Regional measures and ordered jobs

- [ ] Integrate named-region labels only when an eligible model exists and its label definitions are understood.
- [ ] Measure physical volume from label occupancy and voxel volume; define area and thickness methods separately.
- [x] Add durable intake/display stage states, retry/cancellation and restart recovery.
- [ ] Extend execution to native analysis algorithms, revision dependencies, stale-output detection and reviewed artifact publication.
- [ ] Compare numerical results with independently checked references and investigate differences.
- [ ] Retain review decisions, model/version lineage and failure recovery.

Exit: real native results populate the existing analytics UI and remain reproducible. Legacy measurements cannot silently populate missing native results.

### D. Grounded AI agents

- [ ] Verify configured provider/model availability without exposing secrets.
- [ ] Implement the three role contracts, dependency order and deterministic source validator.
- [ ] Give agents only permitted structured facts, explicit missing results and source IDs.
- [ ] Store draft/review history; require human approval for publication.
- [ ] Evaluate missing-data, wrong-unit, invented-number, contradictory-review and provider-timeout scenarios, plus unsupported clinical wording and malicious text in metadata.

Exit: live agent outputs are source-grounded and reviewed; no raw-MRI disease reasoning is claimed from the current text clients.

### E. Observed changes, abnormality/risk and forecasting

- [ ] Add another scan visit when observed longitudinal analysis is needed.
- [ ] Specify each abnormality/risk target, reference population and evidence requirements independently.
- [ ] Obtain compatible trained models or a suitable multi-participant training/evaluation cohort.
- [ ] Assign participant-separated training/validation/test groups and prevent overlapping datasets or future information from leaking into features.
- [ ] Compare against meaningful baselines; evaluate error, calibration, uncertainty, subgroup/site behavior and abstention.
- [ ] Validate the final held-out model before enabling the corresponding UI result.

Exit: only outcomes justified by evidence become available. One person's data can test the application but cannot establish general disease-detection or forecasting performance.

## Completion definition

The full plan is complete only when original MRI can pass through the native pipeline, verified anatomy/measurements populate the custom UI, ordered agent outputs are traceable and reviewed, and any enabled abnormality/risk/forecast model has the stated evaluation evidence. A running set of agents alone does not meet that definition.

Milestone A now has working intake, bounded technical checks, native slice display and persistent stage/cancel/retry/restart behavior. Independent anatomical review remains open. The next implementation milestone is selecting and evaluating a native extraction/segmentation method for B. Model selection and labelled-data availability determine when B/C/E can be completed; no segmentation or forecasting accuracy is promised before evaluation.
