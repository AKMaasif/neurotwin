# NeuroTwin engineering roadmap and delivery ledger

Updated 7 November 2026. This is the working plan for continuous execution, not a declaration that the application is complete. Existing working FastAPI/SQLAlchemy/plain-JavaScript components and user-selected design references remain the baseline.

## Audit and decisions

The app implements approved support plans, explicit patient responses, consented routines, family responsibility acceptance, a bounded voice/text companion, source ingestion/review/retrieval, recipient-projected reports, private multimedia messages, durable events, and patient-scoped API permissions. The latest visual passes are local and not yet pushed; preserve them. Prior test reports describe their own code versions and do not count as fresh verification of subsequent edits.

The eight agent entries describe mixed deterministic services/adapters, not eight autonomous, clinically validated models. `app/numerics.py` uses illustrative state-space parameters. My Check has an honest unavailable state; no complete assessment suite exists. Camera assistance, IoT, calling, background delivery and EHR connections are not implemented. The audit identified silent first-patient selection as an integration gap. This cycle replaces it with an explicit authorized-workspace chooser and patient-context isolation.

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
| F3 Consent/privacy lifecycle | F1, grants, memory | Clear current access, revocation/export/deletion boundaries; preference export/delete through existing opt-in model; server enforcement and audit | Partial, locally verified: access directory/confirmed revocation, memory export/forget; full record export/deletion/enrollment and legal retention remain |
| R1 Research capture | F1, protocol/consent contract | Versioned non-diagnostic sessions, explicit consent, quality and device metadata, cancellation, incompatible-protocol guards; formal mode remains gated | Synthetic session lifecycle API implemented; patient-facing integration, actual capture instruments and formal clinical protocol/safety review remain outstanding |
| R2 Statistical/ML pipeline | R1, permitted longitudinal data | Reproducible preprocessing, patient-disjoint validation, calibrated parameters, missing-data handling, provenance/artifact versions, uncertainty and subgroup evaluation | Illustrative estimator implemented; training/calibration/real-data validation incomplete |
| A1 Agent evaluation | Current agents/services, test fixtures | At least five meaningful cases per agent; schema/source/safety failures, manual escalation, independent scores and producer attribution; reproducible report | Locally verified software contracts: at least five scenarios per registry role; live-model/clinical quality evaluation remains external |
| A2 Voice and localization | Existing companion, F1 | Supported-action matrix, safe confirmation, interruption recovery, reviewed language strings/RTL, measured speech performance | English bounded workflow implemented; multilingual/real-speech evaluation incomplete |
| I1 IoT concept and simulation | Defined event schema, consent | Detailed 3D model/interface, clearly labelled synthetic events, gaps/failures/recovery and alert provenance; no hardware claim | Planned; physical device/organizer acceptance external |
| I2 Deliberate camera assistance | Consent, private media, reviewed model capability | Explicit capture, quality/uncertainty, safe bounded assistance, no covert monitoring or autonomous clinical interpretation | Planned |
| C1 Communication/operations | Existing messaging/routines, production provider decisions | Verified background push/calling only if connected; recipient consent, delivery evidence and recovery | In-app messaging/routines implemented; background push, calls and emergency dispatch disconnected |
| G1 Geographic planning | Authorized population dataset, reviewed boundaries/disclosure controls | Versioned geography, small-cell privacy and non-inferential aggregate display; no fictitious capacity/risk data | Planned; permitted population data/boundaries external |
| P1 Identity/deployment | F1, operational ownership | Real enrollment/recovery, restricted runtime role, HTTPS, encrypted volumes/backups, scanner, parser sandbox, monitoring and tested restore | Production preparation incomplete; service/certificate/identity decisions external |
| V1 Validation/submission | Integrated core, evidence ledger | Current regression/browser results, physical devices, intended-user/clinical review, demo and clear implemented/simulated/future labels | Automated synthetic evidence exists; real-device/clinical validation and final submission incomplete |

## Continuous work queue

Current R1 evidence: the synthetic session lifecycle backend is implemented, with explicit protocol/consent snapshots, participant-only consent, interruption/cancellation/withdrawal, declared quality/device provenance, scoped replay receipts and audit history. Targeted session, capture-boundary and workspace checks passed: **28 tests across SQLite and PostgreSQL** (`test-results/research-session-tests.xml`). Repository Ruff and whitespace checks passed. See `docs/research-sessions.md` for boundaries. Patient-facing capture and real instruments remain unimplemented; this milestone does not activate My Check or produce medical scores.

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
