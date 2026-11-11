# NeuroTwin integrated brain-imaging analytics workspace — development workflow

Prepared 11 November 2026. Planning document only: no imaging service or prediction model has been implemented by this work.

**Architecture update:** the project owner has chosen a NeuroTwin-owned processing pipeline without FreeSurfer execution. [NATIVE_IMAGING_AND_AI_PLAN.md](NATIVE_IMAGING_AND_AI_PLAN.md) supersedes this document's engine/install decisions. Keep the UI requirements and validation principles as reference. The existing viewing preview still uses clearly labelled imported FreeSurfer derivatives.

## 1. Objective and current position

Build NeuroTwin's own brain-imaging analytics workspace, with a FreeSurfer/Freeview-like range of analysis and interaction capabilities. Users import scans, initiate analysis, inspect slices and reconstructed brains, select regions, review measurements, correct supported artifacts, compare visits and inspect evaluated AI forecasts inside NeuroTwin. FreeSurfer and other explicitly selected imaging engines provide processing behind NeuroTwin's interface.

The product deliverable is the integrated NeuroTwin experience. Installing FreeSurfer, opening an external window, showing screenshots, or displaying a generic 3D brain does not satisfy that deliverable. Native desktop tools may be used by developers as reference implementations while the corresponding in-app tools are built.

Repository findings: the frontend is React/TypeScript; the backend is FastAPI/SQLAlchemy. Existing AI clients support factual summary drafts. The current change engine is deterministic and is explicitly not a prediction model. The architecture already anticipates a separate imaging service and store. Existing demo users and synthetic activity records must not be linked to real dataset participants.

The overall roadmap aims for a broad imaging workspace; structural T1 MRI is the first delivery increment. Do not quietly drop requested functionality by calling the initial increment complete parity. Exact parity must be audited against a named FreeSurfer/Freeview release and agreed tool inventory: viewing, structural analysis, editing, longitudinal analysis and modality-specific modules each need defined inputs and checks. Version-specific or unsupported tools must remain visible in the requirements register with an explicit status.

## 1A. What the workspace analyzes

| Evidence | Supported interpretation to design for | Additional development needed |
| --- | --- | --- |
| Structural T1 MRI | Anatomical regions, cortical surfaces, thickness, regional volume | Structural pipeline and QC |
| Repeated structural MRI | Observed anatomical change between visits | Compatible processing, registration and longitudinal QC |
| T2 / FLAIR | Additional tissue contrast; protocol-specific supporting analysis | Explicit compatible pipeline; lesion analysis is not implied by importing FLAIR |
| Diffusion MRI | White-matter pathways and diffusion measurements | Diffusion preprocessing, tractography and QC |
| Functional MRI | Protocol-dependent activity/connectivity estimates | Functional preprocessing, statistical specification and QC |
| Cognitive/behavioral assessments | Recorded performance and self-reports | Validated instruments and explicit linkage to scan visits |
| Historical scans plus a trained model | A defined future outcome estimate | Leakage-free training and independent evaluation |

Structural MRI alone does not establish behavior, emotions, cognition or a diagnosis. Functional imaging also does not directly read behavior or thoughts. Product labels must identify the actual measured signal and its analytical limits. The existing prototype's activities are not automatically validated prediction labels.

## 1B. User workflow inside NeuroTwin

1. Open **Brain Analytics** from the clinician/research workspace.
2. Select a participant and visit, or create an authorized research record.
3. Import a scan or series. NeuroTwin identifies candidate sequences, shows metadata and flags missing or unsuitable inputs.
4. Select an analysis protocol. Show required scans, expected outputs, installed engine/version and available resources; explain unavailable protocols.
5. Submit analysis and follow progress inside the workspace. A failure offers a specific recovery action; completed processing enters QC.
6. Open the analysis layout: axial, coronal and sagittal slices plus a 3D panel. Switch layers, navigate with a linked cursor, inspect labels and select a region.
7. Inspect selected-region measurements and their source artifacts. Units, quality, atlas and processing version remain available.
8. Review segmentation and surfaces. Where supported, make controlled edits inside NeuroTwin, preview affected outputs, save a revision and request reprocessing.
9. Select another visit to compare aligned anatomy, measurements and observed rates of change.
10. Open the forecast tab only when an eligible evaluated model and adequate inputs exist. Review horizon, input history, uncertainty and limitations.
11. Save a review, export permitted measurements or produce a reviewed report. Reopening the case restores the authorized workspace state.

These are product steps, not instructions to operate a separate desktop application.

## 1C. Layout and interaction contract

- **Left panel:** participant/visit selector, scan series, derived volumes, surfaces and layer visibility.
- **Central area:** configurable four-panel layout with orthogonal slices and a scan-derived 3D brain; maximize any panel.
- **Tool rail:** navigation, window/level, measurement, region selection, annotation, supported editing and comparison modes.
- **Right inspector:** selected region, coordinates, numerical results, atlas information, QC findings and provenance.
- **Bottom panel:** processing status, warnings, visit timeline, selected-region trends and review history.
- **Workspace tabs:** Overview, Images & 3D, Regions & Measurements, Compare Visits, Quality & Edits, AI Forecasts, Reports, Processing.

Selection is shared: clicking a region in a slice, surface or table updates the same region inspector. Layer controls distinguish geometry from scalar overlays. A color scale names its quantity and units. Comparison selection cannot silently mix people. Research MRI tools prioritize desktop interaction; narrow layouts provide deliberate panel switching rather than shrinking all controls.

## 1D. Feature parity register to complete before implementation

Every row below needs subtools recorded against the chosen reference release. Record: tool ID, reference behavior, input/artifact formats, NeuroTwin interaction, engine operation, dependencies, acceptance example, release increment and status. “Planned” is not “supported.”

| Capability family | NeuroTwin tools to specify | Verification |
| --- | --- | --- |
| Volume navigation | Linked cursors, slice scroll, pan/zoom, orientation, viewport layouts, coordinates | Known landmarks and geometry |
| Layer rendering | Window/level, contrast, colormaps, opacity, label lookup, overlay ordering | Reference volume/label agreement |
| Surface rendering | White/pial/inflated surfaces, hemisphere selection, annotations, scalar maps, clipping where specified | Mesh, vertex and annotation correspondence |
| Inspection | Region picking, distances, ROI/point-set tools and time courses where inputs support them | Units, coordinate transforms and saved state |
| Structural computation | Segmentation, parcellation, reconstruction, thickness, area and volume | Engine outputs and QC agreement |
| Registration/comparison | Specified transforms, aligned overlays, synchronized visits and change maps | Correct transforms and matching identities |
| Editing | Voxel/label edits, ROI/point edits, supported reconstruction corrections, undo/redo and revision save | Reversible edits, rerun dependencies and numerical effects |
| Longitudinal computation | Cross/base/long dependencies, visit selection, compatible regional rates | Reproducible reviewed paired results |
| Group analysis | Cohort filters, selected statistical protocol and maps | Independently checked statistical example |
| Specialized anatomy | Version-specific subfield/nuclei tools | Required acquisitions and module-specific QC |
| Diffusion/function/PET | Distinct analysis and viewing protocols | Modality-specific reference cases |
| NeuroTwin AI | Forecasts and grounded explanation of stored results | Held-out model evaluation and source traceability |

Sources for inventory: [Freeview tools](https://surfer.nmr.mgh.harvard.edu/fswiki/FreeviewGuide), [FreeSurfer documentation](https://surfer.nmr.mgh.harvard.edu/fswiki/Home), [TRACULA diffusion workflow](https://surfer.nmr.mgh.harvard.edu/fswiki/Tracula). The register is a proposed coverage framework, not a claim that every listed tool ships with every version.

## 2. Scope and analysis pages

| Page / workspace | Required behavior | Delivery stage |
| --- | --- | --- |
| Research participant and MRI library | Dataset identity, visit chronology, acquisition details, permissions, scan and artifact inventory | First release |
| Import and validation | NIfTI import; complete DICOM-series conversion; source/derivative distinction; missing metadata and duplicate checks | First release |
| Processing centre | Queued/running/completed/failed jobs; step information; protected logs; cancel/retry; software version | First release |
| Anatomical viewer | Axial/sagittal/coronal views, linked cursor, orientation labels, window/level, segmentation opacity and labels | First release |
| Surface viewer | Left/right white and pial surfaces, inflated view, region selection, annotations and thickness overlays | First release |
| Measurements | Volumes, cortical thickness, area, units, atlas, quality, provenance and export | First release |
| Quality review | Inspect boundaries and alignment, record findings, accept/exclude, identify reprocessing needs | First release |
| Longitudinal comparison | Select visits; aligned overlays; observed differences and annualized rates; processing compatibility | Second release |
| Reports | Source-linked, reviewed factual reports and structured measurement exports | Second release |
| AI experiments and forecast | Target, horizon, model version, held-out evaluation, uncertainty and abstention | After forecasting gate |
| Advanced editing | In-app controlled corrections, edit history, reruns and dependencies; Freeview used for development comparison only | Dedicated delivery increment |
| Advanced research modules | Hippocampal subfields, other specialized segmentations, group analysis, diffusion/fMRI/PET | Separate specifications |

Freeview is the reference desktop inspection/editing tool. NeuroTwin owns the application UI and interaction model, validated against reference anatomy and outputs. A desktop launch is not completion of an in-app feature. The [Freeview guide](https://surfer.nmr.mgh.harvard.edu/fswiki/FreeviewGuide) documents viewing and editing tools.

## 2A. Page and data availability rules

Each analysis module declares its supported scan types and prerequisites. Scan upload does not enable every tool automatically. A diffusion module needs diffusion volumes and gradient information; a structural T1 volume cannot supply tractography. A functional module needs suitable functional series and acquisition metadata; task analyses also need their experimental timing. PET requires its own acquisition and protocol metadata. Exact requirements must be finalized per selected engine and analysis.

For the first build download native T1 volumes, repeat visits, acquisition metadata, timing and dictionaries as listed below. Obtain T2/FLAIR, diffusion (including b-values/b-vectors and applicable distortion-correction data), functional scans or PET only when that module's protocol has been specified. No single dataset or scan format supplies every planned capability.

## 2B. System components behind the analytics page

1. **Workspace UI:** viewers, region inspector, tools, editing, comparison, charts and reports.
2. **Workspace state:** participant, visits, active layers, coordinate frames, selected region, view settings and revisions.
3. **Authorized imaging API:** upload, artifact streaming, job submission, result queries, reviews and exports.
4. **Protocol registry:** supported engines/versions, required input modalities, allowed parameters and output contracts.
5. **Processing service:** isolated workers, durable dependencies, resource limits and restart/retry handling.
6. **Artifact adapters:** preserve original engine files; produce validated web-consumable volumes/meshes while retaining transforms, labels and scalar correspondence.
7. **Results and review service:** source-linked measurements, quality states, edit revisions and published results.
8. **Forecast service:** separate trained model, eligibility checks, versioned inference and evaluation record.

Choose volume/mesh viewers through a compatibility prototype before committing to libraries. Validate supported formats, editing extensibility, rendering performance and redistribution terms. A generic 3D library alone does not supply MRI analysis.

## 3. Data to obtain, in order

### A. Software and a reference dataset

1. [FreeSurfer download and installation](https://surfer.nmr.mgh.harvard.edu/fswiki/DownloadAndInstall).
2. [Release packages and system requirements](https://surfer.nmr.mgh.harvard.edu/fswiki/rel7downloads).
3. [Free license registration](https://surfer.nmr.mgh.harvard.edu/registration.html): obtain license.txt; keep personal license information out of source control.
4. [Official Windows/WSL guidance](https://surfer.nmr.mgh.harvard.edu/fswiki/FS7_wsl). Select a Linux environment supported by the chosen release; verify Freeview graphics separately.
5. [Official tutorial dataset instructions](https://surfer.nmr.mgh.harvard.edu/fswiki/FsTutorial/Data). The page links the complete tutorial archive and describes its long-tutorial directory. Its approximate 8 GB size is historical documentation, not a verified current download size.
6. [Tutorial archive](https://surfer.nmr.mgh.harvard.edu/pub/data/tutorial_data.tar.gz): obtain through the documentation above. The archive was not downloaded or integrity-tested during planning.

Use the tutorial's processed volumes, surfaces, annotations and statistics for viewer/parser checks, not as a forecasting training cohort. Tutorial documentation and processed examples may use older FreeSurfer versions; label them accordingly.

### B. OASIS-2: initial longitudinal engineering dataset

Start at the [official OASIS site](https://sites.wustl.edu/oasisbrains/), follow [Request Access](https://sites.wustl.edu/oasisbrains/request-access/), and use the [dataset download page](https://sites.wustl.edu/oasisbrains/datasets/) according to the supplied instructions and terms. Do not assume an individual scan has a public direct link.

OASIS describes OASIS-2 as 150 participants and 373 sessions, with repeated visits at least one year apart. Several T1 acquisitions within a visit are repeats from the same visit, not additional longitudinal time points. Source: [official dataset overview](https://sites.wustl.edu/oasisbrains/).

Download:

- [ ] Original/native-space structural T1 acquisitions for selected participants at at least two visits.
- [ ] All companion headers and metadata for each downloaded volume.
- [ ] Participant/session clinical-demographic tables and their data dictionary.
- [ ] Visit identifiers and actual elapsed-time fields; do not infer intervals from MR1/MR2 labels or integer ages.
- [ ] Acquisition descriptions, quality notes, release documentation, citations and data-use terms.

If the provided volume is an Analyze-style .img/.hdr pair, keep both files; use a documented conversion and verify orientation and geometry. Do not rename extensions to convert data. Prefer appropriate native structural inputs rather than atlas-registered or already skull-stripped derivatives for the standard processing workflow. The exact archive layout must be inspected after authorized access.

Pilot recommendation: 5–10 participants, each with two usable visits; include three visits where available. This is an engineering sample size, not evidence that an AI model can be trained adequately.

### C. OASIS-3: larger forecasting research candidate

Use the same [OASIS access application](https://sites.wustl.edu/oasisbrains/request-access/). That page currently directs users to create NITRC accounts; use the portal and project access instructions supplied after review. Older documents mention XNAT Central, so do not rely on an old hostname alone. The [NITRC OASIS-3 project](https://www.nitrc.org/ir/data/projects/OASIS3) requires project-authorized access.

Request/download only the subset needed:

- [ ] Repeated 3D T1-weighted MRI volumes and accompanying acquisition metadata.
- [ ] Participant, MR-session and clinical/cognitive tables, with the current dictionaries.
- [ ] Relative study days for both imaging and clinical visits, plus matching identifiers.
- [ ] Scanner/site/protocol fields and QC information where available.
- [ ] Optional existing FreeSurfer derivatives and their processing versions, for comparison or pipeline development.
- [ ] T2/FLAIR only if the specified analysis requires them and suitable paired acquisitions exist.

OASIS-3 contains longitudinal imaging and clinical data and some FreeSurfer-derived products. Do not assume every participant has the required follow-up or that every derivative was generated with a compatible method. OASIS dates are represented by relative study timing. Source: [official overview](https://sites.wustl.edu/oasisbrains/).

Imaging and clinical visits may occur on different days. Define matching windows and reject ambiguous matches. Do not assume a clinical visit is the same event as an MRI session.

### D. ADNI: optional later external evaluation

[Apply for ADNI data access](https://adni.loni.usc.edu/data-samples/adni-data/#AccessData). The [official access guidance](https://support.adni4.org/hc/en-us/articles/31090030057236-I-am-a-researcher-how-do-I-access-ADNI-research-data-or-samples) distinguishes data access from biospecimen requests.

If approved, select repeated structural T1 scans, linked visit/clinical tables, acquisition/QC information and dictionaries. ADNI supplies MRI images and numerical/QC tables; see its [MRI data description](https://adni.loni.usc.edu/data-samples/adni-data/neuroimaging/mri/). Use this as a separately evaluated cohort after resolving protocol and population differences, not an automatic pool with OASIS.

Do not download PET, diffusion, functional MRI, genetics or an entire multimodal archive for the initial structural module.

### Access verification limits

Official indexed OASIS pages and access instructions were found, but direct page fetches intermittently returned HTTP 502 during this review. No authenticated dataset access, individual scan download, archive checksum or participant-specific scan interval was verified. Accordingly, the plan provides official entry pages rather than promises of working individual-file links. Follow the current data-use terms for storage, collaborators and redistribution.

## 4. Input and storage contract

Canonical working scan: a complete 3D T1-weighted NIfTI volume (.nii.gz), with preserved acquisition metadata. Prefer good gray/white contrast and approximately 1 mm isotropic acquisition for the standard reconstruction workflow; suitability depends on scan quality, not just extension. Sources: [input guidance](https://surfer.nmr.mgh.harvard.edu/fswiki/FreeSurferBeginnersGuide), [recon-all inputs](https://surfer.nmr.mgh.harvard.edu/fswiki/recon-all).

Accept original DICOM as a complete series and convert under a versioned procedure. Preserve originals. FreeSurfer also uses .mgz/.mgh internally. Conversion must preserve spatial geometry; [mri_convert documentation](https://surfer.nmr.mgh.harvard.edu/fswiki/mri_convert) describes supported formats and orientation caveats.

Minimum manifest fields:

| Group | Fields |
| --- | --- |
| Identity | Dataset/release, research subject ID, visit ID, acquisition/run ID, internal linkage ID |
| Timing | Relative study day or permitted date, age at scan where available, timing precision |
| Acquisition | Modality, sequence, scanner/site, field strength, voxel dimensions, volume dimensions, orientation |
| Provenance | Source path/accession, checksum, download date, terms reference, conversion tool/version |
| Processing | Job ID, FreeSurfer/OS version, options, atlas, input checksums, output checksums, timestamps |
| Review | QC state, reviewer, findings, edits, excluded artifacts and reasons |
| Learning | Cohort inclusion, split assignment, prediction cutoff, target visit, target definition |

Use a BIDS-compatible organization where possible; keep source, converted, processed and model artifacts separate. [BIDS anatomical naming](https://github.com/bids-standard/bids-specification/blob/master/src/modality-specific-files/magnetic-resonance-imaging-data.md) supports T1w volumes and JSON metadata. Relative study-day metadata must remain explicit; do not invent calendar dates.

Store large volumes outside the application database and outside git. The database stores controlled artifact references and metadata. Research cohort identities remain separate from NeuroTwin's synthetic demo identities.

## 5. Development workflow and exit checks

### Stage 0 — Specify the research questions before construction

- [ ] Create a capability inventory: each requested tool, modality, input, output, page, implementation route and acceptance criterion.
- [ ] Select the reference FreeSurfer/Freeview release and audit its menus/tool families against the parity register.
- [ ] Design the analytics workspace and walkthroughs for import, region inspection, edits, comparison and reports.
- [ ] Specify shared selection, coordinates, layer state and workspace restoration before implementing individual panels.
- [ ] Build a prototype with reference MRI/surface artifacts to settle viewer and edit-tool compatibility.
- [ ] Freeze first-release structural scope and mark advanced modules separately.
- [ ] Specify observed comparisons separately from forecasts.
- [ ] Choose one initial forecasting target, such as regional volume at a defined future horizon; establish tolerance for visit timing.
- [ ] Decide whether prediction uses one baseline scan or multiple historical scans.
- [ ] Define who reviews QC, who evaluates statistics and what evidence permits a forecast to be displayed.
- [ ] Define image access, retention, revocation and export rules appropriate to the selected research data.

Exit: a requirements matrix and target specification exist; no unspecified “brain health score” or generic prediction accuracy is promised.

### Stage 1 — Establish the processing environment

- [ ] Inventory CPU, supported instruction set, RAM, available disk and Windows/WSL configuration.
- [ ] Select and pin a supported FreeSurfer release and Linux environment.
- [ ] Obtain the license and record installation configuration.
- [ ] Open reference data in Freeview and run a representative reconstruction outside NeuroTwin.
- [ ] Measure elapsed time, peak RAM and disk growth on this machine; derive concurrency and storage limits from measurements.
- [ ] Record a reproducible installation/run manifest.

The current release page lists 32 GB+ system memory for version 8 processing, versus 16 GB+ for version 7, and an installed image around 16–19 GB. Use release-specific requirements and benchmark outputs rather than assuming a fixed per-participant disk cost. Source: [release requirements](https://surfer.nmr.mgh.harvard.edu/fswiki/rel7downloads).

Exit: one real scan completes successfully, outputs can be inspected and the machine's practical limits are known.

### Stage 2 — Acquire and validate the pilot cohort

- [ ] Complete relevant access requests and record permitted use.
- [ ] Download a small longitudinal subset plus metadata and dictionaries.
- [ ] Validate participant/visit joins, actual intervals and repeat acquisitions within visits.
- [ ] Reject incomplete, corrupted, inappropriate-modality or inadequately documented inputs with clear reasons.
- [ ] Verify conversion preserves dimensions, geometry and left/right orientation.
- [ ] Inspect input quality and select usable acquisitions under a recorded policy.
- [ ] Produce a cohort manifest and download inventory with checksums.

Exit: at least one valid paired participant can be processed; the complete pilot inventory has explicit inclusion/exclusion reasons.

### Stage 3 — Build the imaging service and job system

Proposed architecture: React workspace → authorized FastAPI routes → imaging metadata/store → durable job queue → isolated Linux FreeSurfer worker → artifact validation → QC → published measurements and viewer assets.

- [ ] Introduce schema migrations and records for research subjects, visits, scans, artifacts, processing jobs, QC reviews and model runs.
- [ ] Implement durable job states: queued, running, cancel requested, cancelled, failed, awaiting QC, completed.
- [ ] Validate allowed parameters; do not expose arbitrary shell commands or filesystem paths through the UI.
- [ ] Enforce per-subject job dependencies, resource limits, cancellation and retry behavior.
- [ ] Isolate partial outputs and publish artifacts only after validation.
- [ ] Make duplicate submissions idempotent; reconcile interrupted jobs after worker restart.
- [ ] Recheck access for every artifact request and export; prevent public static-file access.
- [ ] Test invalid uploads, archive traversal, oversized/decompression-heavy files, unauthorized reads and revoked access.

Exit: submit, fail, cancel, restart and retry work without duplicate final records or cross-participant access.

### Stage 4 — Implement structural analysis and measurements

- [ ] Run independent reconstruction for each accepted session.
- [ ] Preserve native outputs and processing configuration.
- [ ] Parse aseg.stats and left/right cortical parcellation statistics with explicit units and atlas/version.
- [ ] Extract available volumes, thickness, surface area and intracranial-volume estimates; represent missing measurements explicitly.
- [ ] Validate extracted results against the source statistics files.
- [ ] Catalogue volumes, white/pial/inflated surfaces, annotations and vertex overlays separately.
- [ ] Keep failed/incomplete jobs out of completed-result views.

Exit: displayed/exported numbers match source outputs and point to their exact scan, job and atlas.

### Stage 5 — Build and verify the viewers

- [ ] Evaluate a volume/surface viewer using real pilot artifacts before choosing a library; check license, formats and geometry handling.
- [ ] Implement linked orthogonal slices, labels, overlays and intensity controls.
- [ ] Implement surface rotation/zoom, hemisphere visibility, region selection and thickness color scales with units.
- [ ] Validate volume affine and FreeSurfer surface coordinate transforms; verify anatomical landmarks and left/right consistency.
- [ ] If exporting meshes, retain vertex indexing and corresponding annotations/measurements or document a validated mapping.
- [ ] Confirm a selected region corresponds across surfaces, slice overlays and measurements.
- [ ] Compare the web rendering with Freeview on representative accepted and problematic scans.
- [ ] Check loading failures, memory limits, large assets, keyboard controls, English and Arabic layouts.

Exit: geometry and label alignment are verified; browser loading is usable on agreed devices. Decorative meshes cannot substitute for scan-derived anatomy.

### Stage 5A — Implement in-app editing and tool parity increments

- [ ] Establish read-only viewing first; enable each edit tool only after its protocol and checks exist.
- [ ] Add selected ROI, point/measurement and segmentation-edit tools in individually reviewable increments.
- [ ] Define coordinate frame, brush units, label constraints, undo/redo and unsaved-edit behavior.
- [ ] Preserve immutable originals; store edited derivatives as explicit revisions with actor, reason and parent artifacts.
- [ ] Distinguish review annotations from edits that alter analysis inputs.
- [ ] Explain which jobs and measurements become stale after a correction; rerun and review affected dependencies.
- [ ] Compare the intended edit and its reconstructed output with independently inspected reference cases.
- [ ] Handle concurrent edits, abandoned sessions and interrupted saves without corrupting published artifacts.
- [ ] Update the parity register after each tool passes, showing any remaining limitation explicitly.

Exit: the delivered tools work inside NeuroTwin and their changes are traceable. An external editing workaround does not count as completed in-app editing. Full editing parity remains open until every agreed reference tool passes its checks.

### Stage 6 — Add QC and longitudinal measurement

FreeSurfer's longitudinal workflow processes individual visits, creates a within-subject template, then processes each visit against that template. Follow [official longitudinal processing](https://surfer.nmr.mgh.harvard.edu/fswiki/LongitudinalProcessing), with the [tutorial](https://surfer.nmr.mgh.harvard.edu/fswiki/FsTutorial/LongitudinalTutorial) as a worked reference.

- [ ] Inspect skull stripping, gray/white and pial boundaries, segmentation and registration.
- [ ] Keep automated warnings and human QC decisions separately; a successful process is not proof of anatomical quality.
- [ ] Model CROSS → BASE → LONG dependencies and record which visits contributed to each template.
- [ ] Store separate results when new visits or corrections require reprocessing; never silently mix old/new template results.
- [ ] Compare compatible atlases, versions, units and accepted visits only.
- [ ] Compute observed differences and annualized rates using actual elapsed time; show the formula and endpoints.
- [ ] Distinguish measured variation from a clinical interpretation; do not invent single-person significance thresholds.
- [ ] Keep corrections versioned and rerun affected dependencies before publishing replacement results.

Exit: a paired scan workflow is reproducible and reviewed; charts label results as observed estimates and retain their provenance.

### Stage 7 — Develop forecasting as a separate experiment

- [ ] Freeze the population, target, horizon, input history and exclusion rules.
- [ ] Split by participant before fitting preprocessing, feature selection, normalization or models; account for related groups and dataset overlap.
- [ ] Keep the final test set untouched during development; use training/validation data for model selection and calibration.
- [ ] Compare with persistence (future value equals latest observed value), simple demographic regression and a historical trend baseline when history exists.
- [ ] Begin with measurement-based models; justify complexity using held-out results.
- [ ] Evaluate errors in measurement units, performance by horizon, subgroup/site failures, uncertainty coverage and abstention behavior.
- [ ] Evaluate on an independent cohort where feasible and document distribution differences.
- [ ] Save model, feature schema, preprocessing, training data version and complete evaluation report.

Critical leakage rule: at prediction time, features may depend only on information already available. A baseline measurement extracted using a longitudinal template containing the target future scan leaks future anatomy. For baseline-only prediction, use independently processed baseline inputs. For history-based prediction, construct features only from historical scans available at the cutoff. Document how independently assessed future targets are produced and audit all template membership.

Two visits can support an observed pair and potentially a baseline-to-follow-up training example. A third visit is particularly useful when predicting after two historical scans, but a small number of paired people is not sufficient evidence for a reliable model.

Exit: predeclared evaluation criteria are met on held-out participants, baselines are reported and the intended use is justified. Otherwise keep the experiment unavailable as a product forecast.

### Stage 8 — Integrate reviewed results into NeuroTwin

- [ ] Add clinician imaging navigation and research permissions while preserving existing family restrictions.
- [ ] Label measured anatomy, observed change and forecast estimates distinctly.
- [ ] Display model version, prediction cutoff, forecast horizon, input visits and uncertainty for every forecast.
- [ ] Define a dedicated structured forecast contract; do not weaken the existing factual-summary validator to admit predictions accidentally.
- [ ] Prevent an LLM from inventing measurements or converting a forecast into a diagnosis.
- [ ] Export source-linked measurements and reviewed reports; apply dataset redistribution terms.
- [ ] Exercise a complete import → process → QC → compare → report workflow with failure/recovery cases.
- [ ] Run relevant backend checks, frontend build, permission checks and visual verification of the new pages.

Exit: research users can trace each result to source scans and reproduce its processing; unsupported forecasts remain unavailable.

## 6. Advanced-feature backlog

For each item below, write a separate protocol, dataset specification, worker resource estimate and test plan before scheduling implementation:

- Specialized hippocampal/amygdala/thalamic segmentation and other version-specific analysis tools.
- Remaining surface/voxel/ROI editing tools with validated reruns inside NeuroTwin; Freeview remains a development reference.
- Surface registration, smoothing and cohort/group statistical analysis.
- Diffusion tractography, functional MRI and PET analysis with their modality-specific acquisitions.
- Future surface or full-volume generation, with anatomical fidelity and longitudinal evaluation beyond visual plausibility.
- A controlled local launcher for desktop tools, if requested; this is distinct from web viewer development.

## 7. Ready-to-build checklist

- [ ] First-release features and advanced backlog are agreed.
- [ ] The product specification explicitly requires NeuroTwin's own integrated analytics UI.
- [ ] Named-reference parity register covers requested tool families and records deferred items.
- [ ] Page layout, shared selection behavior and complete user walkthrough are specified.
- [ ] Each analysis module has a scan/metadata prerequisites checklist and an unavailable-state design.
- [ ] In-app edits, immutable artifacts and reprocessing consequences are specified.
- [ ] Dataset access, use restrictions and storage arrangements are recorded.
- [ ] Pilot native T1 volumes, companion files, metadata and dictionaries are available.
- [ ] Participant/visit identities and intervals are verified.
- [ ] Supported processing environment and practical RAM/disk limits are confirmed.
- [ ] A reference FreeSurfer run and Freeview inspection succeed.
- [ ] Artifact schema, job lifecycle, migrations and permission model are specified.
- [ ] Viewer prototype correctly aligns reference anatomy and labels.
- [ ] QC acceptance rules and review responsibilities are documented.
- [ ] Forecast target and leakage-free evaluation design are written; prediction remains a later gate.

Recommended first construction milestone: an integrated NeuroTwin Brain Analytics page for one research participant with two native T1 visits, processed and quality-reviewed, with linked slices, scan-derived surfaces, region picking, verified measurements and observed comparison. Users complete that workflow inside NeuroTwin. Editing parity, additional modalities and AI forecasting follow as explicit increments; the first milestone does not claim the whole requested toolset is complete.

## 8. Delivery order and completion record

| Increment | User-visible result | Completion evidence |
| --- | --- | --- |
| A: Product specification | Full workspace design and feature register ready for review | Walkthrough, tool matrix, input contracts and acceptance examples |
| B: Reference viewer | Real MRI and surface artifacts navigable inside NeuroTwin | Geometry, region and overlay comparison with reference tools |
| C: Structural analysis | Upload, processing, QC and verified numerical results in one workspace | End-to-end pilot and failure recovery |
| D: Longitudinal analytics | Two visits compared inside the same workspace | Verified timing, alignment and observed measurement changes |
| E: Editing and expanded parity | Agreed correction and inspection tools in the application | Tool-by-tool acceptance record and rerun checks |
| F: Specialized modalities | Additional modules enabled for suitable inputs | Per-module dataset, protocol and QC evidence |
| G: Evaluated forecasting | Eligible research forecasts with uncertainty | Leakage audit, held-out report and documented limitations |

Increment F and G may proceed independently after their prerequisites are satisfied. Before reporting completion, list exactly which tools are delivered, which remain deferred, and which were excluded from the agreed scope. Preserve the full-workspace objective throughout incremental development.
