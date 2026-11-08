# NeuroTwin engineering roadmap and delivery ledger

Updated 8 November 2026. This is the working plan for continuous execution, not a declaration that the application is complete. Existing working FastAPI/SQLAlchemy/plain-JavaScript components and user-selected design references remain the baseline.

## Audit and decisions

The app implements approved support plans, explicit patient responses, consented routines, family responsibility acceptance, a bounded voice/text companion, source ingestion/review/retrieval, recipient-projected reports, private multimedia messages, durable events, and patient-scoped API permissions. The selected visual-reference work is committed; preserve it. IoT, camera and dataset preflight work is committed through df6de0f; account-session work is committed through 415457a; password-change work is committed through 89db79b; the care-summary and validation-profile/documentation work was pushed in commit 7425095 on 8 November. Prior test reports describe their own code versions and do not count as fresh verification of subsequent edits.

The eight agent entries describe mixed deterministic services/adapters, not eight autonomous, clinically validated models. `app/numerics.py` uses illustrative state-space parameters. My Check now includes a separately labelled SATURN-derived research adaptation with 20 scored activity groups, explicit consent, response capture and clinician review. No clinically approved assessment suite exists. Synthetic IoT and deliberate camera workflows are described in the later milestones; physical devices, calling, background delivery and EHR connections remain unimplemented. The audit identified silent first-patient selection as an integration gap. This cycle replaces it with an explicit authorized-workspace chooser and patient-context isolation.

Original requirements reviewed: selected design direction/review, all repository implementation notes, NeuroCompanion Specification (3 pages), UX & ML Pipeline Blueprint (6 pages), Technical Specification (8 pages). Blueprint sensitivities, specificity, 60% referral reduction, subgroup fairness, causal attribution and counterfactual gains are proposed/illustrative claims, not verified results. Do not display them as measured performance or use them to block a referral. Browser audio level is not calibrated clinical dB SPL. Formal assessment protocols, clinical interpretation, norms and population thresholds require qualified review and suitable data. Requirements do not justify copying an unsafe or unsupported prototype claim into a working UI.

## Status vocabulary

- **Implemented**: code is connected, but required verification may still remain.
- **Locally verified**: named checks have actually passed against synthetic data; not clinical/device/production certification.
- **In progress / planned**: incomplete; visible controls must not imply availability.
- **External dependency**: credentials, licensed data, hardware, institutional/clinical decisions or real-device/operator work is needed. Continue independent work instead of pausing the whole project.

## Execution phases

| ID / phase | Objective and dependencies | Deliverables / acceptance criteria | State |
| --- | --- | --- | --- |
| F1 Authorized workspaces | `/patients`, grants, existing role clients | Explicit patient selection; scope-filtered list; clear patient context; cache/stream/microphone cleanup; stale-response rejection; atomic workspace loads; no unauthorized fallback | Locally verified with synthetic API/browser tests |
| F2 Clinical completion | F1, plans, cases, sources | Refine patient history/revisions and case review; source holds and human decisions stay explicit; patient switching and report privacy tested | Locally verified: overview/queue plus patient history/provenance and case decision surfaces; clinical usability review external |
| F3 Consent/privacy lifecycle | F1, grants, memory | Clear current access, revocation/export/deletion boundaries; preference export/delete through existing opt-in model; server enforcement and audit | Partial, locally verified: access directory/confirmed revocation, memory export/forget and limited participant care-summary download; complete record export/deletion/enrollment and legal retention remain |
| R1 Research capture | F1, protocol/consent contract | Versioned non-diagnostic sessions, explicit consent, quality and device metadata, cancellation, incompatible-protocol guards; formal mode remains gated | Synthetic lifecycle and SATURN-derived task/evidence/scoring/review module implemented; qualified clinical protocol/safety review and adapted-instrument validation remain external |
| R2 Statistical/ML pipeline | R1, permitted longitudinal data | Reproducible preprocessing, patient-disjoint validation, calibrated parameters, missing-data handling, provenance/artifact versions, uncertainty and subgroup evaluation | Illustrative estimator and offline dataset preflight implemented; training/calibration/real-data validation incomplete |
| A1 Agent evaluation | Current agents/services, test fixtures | At least five meaningful cases per agent; schema/source/safety failures, manual escalation, independent scores and producer attribution; reproducible report | Locally verified software contracts: at least five scenarios per registry role; live-model/clinical quality evaluation remains external |
| A2 Voice and localization | Existing companion, F1 | Supported-action matrix, safe confirmation, interruption recovery, reviewed language strings/RTL, measured speech performance | English bounded workflow implemented; multilingual/real-speech evaluation incomplete |
| I1 IoT concept and simulation | Defined event schema, consent | Detailed 3D model/interface, clearly labelled synthetic events, gaps/failures/recovery and alert provenance; no hardware claim | Synthetic consented event simulator locally verified; 3D model, physical device and organizer acceptance remain outstanding |
| I2 Deliberate camera assistance | Consent, private media, reviewed model capability | Explicit capture, quality/uncertainty, safe bounded assistance, no covert monitoring or autonomous clinical interpretation | Synthetic single-image object-label workflow locally verified; physical-device, recognition-quality and intended-user validation outstanding |
| C1 Communication/operations | Existing messaging/routines, production provider decisions | Verified background push/calling only if connected; recipient consent, delivery evidence and recovery | In-app messaging/routines implemented; background push, calls and emergency dispatch disconnected |
| G1 Geographic planning | Authorized population dataset, reviewed boundaries/disclosure controls | Versioned geography, small-cell privacy and non-inferential aggregate display; no fictitious capacity/risk data | Planned; permitted population data/boundaries external |
| P1 Identity/deployment | F1, operational ownership | Real enrollment/recovery, restricted runtime role, HTTPS, encrypted volumes/backups, scanner, parser sandbox, monitoring and tested restore | Self-service session revocation and current-password-verified changes locally verified; production preparation incomplete and service/certificate/identity decisions external |
| V1 Validation/submission | Integrated core, evidence ledger | Current regression/browser results, physical devices, intended-user/clinical review, demo and clear implemented/simulated/future labels | Automated synthetic evidence exists; real-device/clinical validation and final submission incomplete |

## Continuous work queue

Current R1 evidence: the synthetic session lifecycle backend is implemented, with explicit protocol/consent snapshots, participant-only consent, interruption/cancellation/withdrawal, declared quality/device provenance, scoped replay receipts and audit history. Targeted session, capture-boundary and workspace checks passed: **28 tests across SQLite and PostgreSQL** (`test-results/research-session-tests.xml`). Repository Ruff and whitespace checks passed. See `docs/research-sessions.md` for boundaries. The legacy synthetic session panel remains connected. A separate SATURN-derived research module now captures task responses and provisional research points; clinically approved instruments and medical interpretation remain unavailable.

1. Deliver F1 and test cross-patient isolation, revoked/no-scope grants and responses arriving after switching.
2. Complete patient/case clinical surfaces without changing approval semantics.
3. Implement missing privacy/self-service contracts that can be exercised locally; preserve explicit consent and data retention decisions.
4. Build benchmark coverage and protocol/data contracts before claiming assessment/model performance.
5. Proceed with independently implementable research/IoT integration boundaries; leave clinical/real-data functionality gated until its inputs are approved and available.
6. Run current whole-project checks after connected modules stabilize, update results and production blockers, then continue the next independent item.

Routine implementation, reversible debugging and synthetic testing are already authorized. Do not request repeated phase approvals. Do not purchase services, deploy to real users, rewrite Git history, destroy data, expose sensitive material or silently change clinical scope. A previous one-off push does not authorize automatically publishing all later changes.

## Milestone evidence

Prior implementation/audit evidence: `docs/messaging.md`, `docs/ui-reference-refinement.md`, `docs/mobile-plan-design.md`, `docs/mobile-care-pages.md`, `docs/family-reports-design.md`, `docs/clinical-overview-queue.md`. Each states actual commands, test scope and limitations. Current cycle results are added only after execution. No module is marked clinically or production validated on the basis of synthetic tests.


## 7 November execution milestone

Implemented and tested F1 workspace isolation, F2 patient/case refinements, F3 participant access visibility and companion-memory export, and A1 per-role contract evidence. [Workspace/privacy evidence](docs/workspaces-and-privacy.md) records exact overlapping test partitions and browser runs; [agent evaluation](docs/agent-contract-evaluation.md) explains scores and limits. Distinct backend regression evidence: 331 passed and one expected SQLite RLS skip, run in partitions. The eight role scores describe service contracts only. This milestone remains local and unpushed.

Resolved integration defects found during execution: message scroll restoration now follows mobile dock sizing; a second tab no longer clears the same patient's existing device reminder; revoked workspace refresh clears cached records; isolated browser fixtures include their own scheduler worker. Existing explicit multimedia send and private recipient rules remain verified.

The next independent queue is protocol/consent/provenance contracts for non-diagnostic research sessions and simulator event contracts before adding any formal patient assessment or device claims. Production enrollment, permitted research data, clinical protocol approval, physical-device tests and operational infrastructure remain gates. No diagnostic performance, real-world model learning, background delivery or hardware completion is claimed.


## Mobile responsive delivery — 7 November

Application 1 (`/mobile/`) now uses a fluid dock/rail/sidebar shell and content-driven grids, with a conditional plan context panel. The separate clinical application and backend were unchanged in this pass (52 pre/post file hashes matched). See [responsive architecture and complete viewport evidence](docs/mobile-responsive-architecture.md): five engines/channels, eleven requested viewports, eight pages, plus state/recovery and established care workflow regression. Native browser-chrome zoom, actual Safari/Android devices, assistive-technology review and field performance remain unverified. This is a frontend milestone, not production certification or a GitHub push.


## Patient/family visual identity delivery — 7 November

Implemented the attached premium design brief in Application A only: restrained indigo/ivory theme, abstract companion, current-plan response summary, non-destructive plan filters, source-aware support guidance, and coherent family/messaging/report/settings surfaces. [Implementation and visual QA report](docs/mobile-premium-redesign.md) records 560 cross-browser page checks, 128 additional role/layout checks, 72 established regression scenarios, screenshots and remaining manual validation. All 52 dashboard/backend file hashes matched the pre-change baseline. No production or clinical validation, primary data mutation, GitHub push or deployment is claimed.


## Direct reference artwork and composition correction

Replaced simplified artwork with local 3D-style clipboard, heart/hands and luminous brain assets; bundled licensed Inter and tightened the three reference-screen compositions. Desktop now composes hero and contextual content into columns while retaining the phone treatment. See [current visual-reference evidence](docs/mobile-visual-reference-v2.md). Current scope snapshot: all 52 dashboard/backend files unchanged. All work remains local; actual device/assistive-technology and field-performance validation remain outside these automated UI checks.


## Research workflow interface integration — 7 November

Connected clinician assignment/read controls in Patient workspace and a participant-only consent/status/completion panel in My Check. The existing mobile visual identity and formal-assessment gate remain intact. Errors, access-denial clearing, declared provenance, explicit consent/withdrawal and stale page-response rejection are implemented. A fresh isolated five-script browser batch passed: research workflow (9 scenarios), care pages, clinical design, core and companion. SQLite/PostgreSQL session/capture/workspace regression: 28 passed. Repository formatting, Ruff and whitespace checks passed. The local API on port 8140 was restarted and its research routes and health endpoint verified. No clinical measurement, model training, physical-device validation, production deployment or GitHub push is claimed for this cycle. See `docs/research-sessions.md`.

Next independent engineering work: IoT simulation event contracts with explicit simulation provenance, participant permission, gaps/disconnect/recovery semantics and separate human-reviewed handling. Physical-device and approved clinical capture work remains dependent on external inputs.


## Device simulator implementation — 7 November

Implemented a single explicitly simulated event stream per synthetic patient: participant permission/withdrawal, clinician injection, connection loss, missing readings, faults, recovery, sequence gaps, declared activity counts and separate manual review of test signals. No physical telemetry or automatic medical output is produced. The shared secondary panel is connected in Mobile → My Check and Dashboard → Patient workspace, without replacing the selected design. Tests were written first and reproduced missing routes before implementation.

Verification: **46 backend regression tests passed** across SQLite/PostgreSQL (IoT, research sessions, capture boundaries and workspaces; `test-results/iot-research-regression.xml`). The final IoT partition was rerun after two additional provenance/replay cases: **20 passed** (`test-results/iot-simulation-tests.xml`), overlapping 18 checks in the regression run, for 48 distinct checks across these runs. A fresh six-script browser batch passed: IoT (10 scenarios), research (9), care pages (6), clinical design (5), core (8) and companion (10), with no page errors in their passing runs. UI screenshots were visually inspected. Formatting, Ruff and whitespace checks passed. The local API was refreshed to expose the simulator routes; no production deployment or GitHub push was performed. See `docs/iot-simulation.md` for exact contracts and remaining hardware/clinical gates.


## Deliberate camera-assistance milestone — 7 November

Implemented Mobile → Companion → Camera assistance for synthetic still samples: local choose/capture hint, preview, explicit per-image provider consent, send, uncertainty/failure states and clear/navigation cleanup. The server validates image bytes/dimensions, strips source metadata, uses bounded allowlisted object/position schema and renders local tentative templates. It does not store photos or scene results, execute model actions or add medical data. Audit metadata identifies provider/model and QA status. A minimal max-width correction fixes the Companion illustration at doubled root text on 320px screens.

Verification: **28 camera API checks passed** across SQLite/PostgreSQL; **49 related workflow/PDF/gateway checks passed**. Ten browser scenarios passed with explicit test doubles; companion, core, IoT, research and care-page regressions were rerun. One separate live request with a generated synthetic cup drawing returned HTTP 200/schema-valid output from the configured Gemini 2.5 Flash model. This proves connectivity only, not recognition accuracy. Formatting/Ruff/whitespace checks pass. Local port 8140 was refreshed; no production deployment or GitHub push was performed. Detailed contracts, source references and outstanding device/clinical/quality limits: `docs/camera-assistance.md`.


## Research-data preflight milestone — 7 November

The user confirmed that an assessment instrument is **not selected yet**. Formal My Check scoring remains gated. Implemented an offline version-1 JSON validator/CLI for the existing research scalar contract: required source/permission/consent references, patient-disjoint train/validation/test splits, unique sample IDs and relative times, per-participant protocol/version/mode consistency, finite numeric bounds, separate quality/missing-value counts and explicit training gates. Reports redact identifiers and values, include reproducible normalized-input fingerprints and refuse output overwrite. No model is trained and no patient result or UI is changed.

Tests first reproduced the missing module. Final dataset/capture/numerical checks: **27 passed** (`test-results/dataset-readiness-tests.xml`). The supplied explicitly synthetic example was executed through the actual CLI and passed structural checks while remaining not ready for training. Repository Ruff, formatting and whitespace checks passed. Existing IoT/camera changes remain preserved and local; this cycle does not push to GitHub or perform external AI calls. Usage and limits: `docs/research-data-readiness.md`.

Remaining R1/R2 inputs are a selected/reviewed instrument, administration/scoring and reuse requirements, permitted longitudinal records, labels and clinically reviewed preprocessing/model-validation criteria. Presence of reference strings and synthetic test success do not establish these approvals or medical performance.


## Account-session security milestone — 7 November

Implemented authenticated account-session summaries and confirmed sign-out of other active sessions in Mobile Settings, clinical Account security and the no-patient workspace state. The requesting session and other accounts are preserved; summaries reveal no tokens/device guesses. Sign-in/revocation share a PostgreSQL account-row lock, and a waiting caller is rechecked after the lock. Shared API/camera HTTP-401 handling clears private views and returns revoked clients to sign-in on their next request. No patient permission or medical workflow changed.

Tests first reproduced missing routes. Initial account/workflow regression: **40 passed** across SQLite/PostgreSQL. Final account partition: **13 passed, 1 expected SQLite concurrency skip**; overlapping 10 prior account checks, so totals are not additive. PostgreSQL concurrent revocation, expiry, CSRF, other-account isolation and no-patient access passed. The dedicated browser flow passed **7 scenarios**; core, companion, care pages, clinical design and camera regressions also passed. Formatting/Ruff/whitespace checks passed. See `docs/account-sessions.md`; local evidence lives under ignored test-results. Production identity/enrollment/recovery, physical-device/security review and wider deployment requirements remain outstanding. No GitHub push was performed for this cycle.


## Password-change milestone — 7 November

Added current-password-verified password change to both account-security interfaces. Explicit confirmation is required; successful changes atomically replace the salted hash and sign out all own sessions, with field clearing and sign-in guidance. Added bounded/redacted body validation and in-process reauthentication throttling. PostgreSQL account locks serialize changes with sign-in/revocation and reject callers revoked while waiting. Clinical records, grants and the selected design remain intact.

Verification: password/session checks passed **36 with 2 expected SQLite concurrency skips**; the final redaction/Unicode validation partition passed **16**, overlapping 12 cases, for 40 distinct passing checks across these runs. New browser flow: **5 scenarios passed**; account-session, core, companion, care-page and clinical-design regressions passed. The browser run found and verified a fix for stale background refresh cleanup after sign-out. Ruff, formatting and whitespace checks passed. No active development credentials were changed by tests; all password mutations used isolated fixtures. See `docs/password-change.md` for contracts, evidence and remaining identity/recovery/production limits. No GitHub push was performed.


## Integrated regression milestone — 7 November

Ran the entire backend suite after the accumulated feature/security changes: **445 passed, 3 skipped** (448 collected), with no failures/errors. The skips were SQLite-only PostgreSQL concurrency/RLS variants; their PostgreSQL counterparts passed. The existing Starlette/httpx deprecation warning remains. Evidence: `test-results/integrated-regression.xml`.

Expanded the default isolated browser command from 11 to **18 flows**, adding current research, IoT, camera, account-session, password, care-page and family-report coverage. The full default batch passed all 18, including original record-preview-explicit-send voice notes and multimedia workflows. Each flow used a fresh synthetic SQLite fixture and its own worker with AI disabled. Ruff, formatting and whitespace checks passed. No application feature or clinical approval rule changed.

Applied the existing agent-contract summarizer to the completed full-suite report rather than rerunning selected tests. All eight registry roles passed their mapped contracts with at least five scenarios each; role tests overlap and are not independent model/clinical accuracy measurements. Current metadata: `test-results/integrated-agent-contracts.json` and `test-results/integrated-validation-summary.json`. Reproduction, exact browser batch and remaining validation limits: `docs/integrated-validation.md`. Current app source is committed through 89db79b; this cycle's profile/documentation changes remain local. No GitHub push or production deployment was performed.


## Participant care-summary export — 8 November

Implemented a confirmed Settings JSON download for synthetic participant workspaces, with an allowlisted projection of approved plans, linked tasks, participant-involved help and text-size preference. Current grants control included categories; drafts/private clinical records and extra fields are excluded even if review scope is present. Source-review holds and participant-statement limitations remain explicit. Server-side preparation is audited without care text, responses are private/no-store and oversize sources fail without a partial file. Client guards prevent duplicate submission, unsafe workspace switching and late downloads after navigation.

Verification: **24 backend checks passed** across SQLite/PostgreSQL (care export, memory export and workspaces); new browser flow **7 scenarios passed**, plus care-page/account/core/companion/family-report regressions. Ruff, formatting and whitespace checks passed. Default browser configuration now includes care export (19 flows); the earlier full 445-test/18-flow checkpoint predates this feature and is not represented as a new full-suite run. Exact scope and remaining complete-record/retention/identity requirements: `docs/care-summary-export.md`. No GitHub push, production deployment or medical-record deletion was performed.


## Continuous assessment delivery — 8 November

Completed the requested first publish checkpoint: care-summary export and accumulated validation/docs pushed as 7425095; remote main was verified. Selected the CC0 author-deposited SATURN 0.4.0 English source for an explicitly adapted research protocol; Mini-Cog/GPCOG/6CIT/4AT tradeoffs and reuse boundaries are documented. This selection is an engineering/research decision, not qualified clinical approval.

Implemented all 20 scored activity groups plus reading/learning screens, participant-only consent, sequential/versioned evidence capture, independent server timing, missing-evidence/null totals, bounded color-trial attempts, explicit stop/withdrawal, deterministic provisional scoring and attributed item-by-item clinician adjudication. Family access and real-patient use are rejected server-side. Background workspace/routine refreshes preserve active timed activities; interrupted material is not replayed. Assessment body-validation errors are redacted. Source assets are curated and attributed; no bundled participant logs/data are committed.

Verification is recorded in docs/assessment-verification.md after the current complete run. The earlier 445-test/18-flow evidence remains a historical checkpoint. Clinical approval, adapted-instrument validation, older-adult usability, Arabic/Gulf/device norms and real enrollment remain external; none is represented as complete.

Final assessment-cycle verification: **500 passed, 4 expected SQLite-only skips** in the full SQLite/PostgreSQL regression (504 collected); the PostgreSQL variants passed. All **20 default isolated browser flows passed**, including the five dedicated assessment scenario groups, reference designs, care-summary export and original voice-note/media workflows. New assessment checks in the full run: 45 passed plus the SQLite concurrency skip. Ruff/formatting/whitespace and curated-asset integrity checks passed. See `docs/assessment-verification.md`. No clinical/production validation is claimed. The initial requested publish checkpoint is on GitHub as 7425095; the newly built assessment work is included in the subsequent user-authorized assessment delivery commit.
