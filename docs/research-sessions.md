# Synthetic research session boundary

The session API implements workflow storage, not a clinical assessment or a sensor capture instrument. It remains a separate software-only panel alongside the newer SATURN-derived research activities described below. Both preserve the existing mobile reference design; qualified clinical assessment remains gated.

## Contract

- `GET /api/patients/{pid}/research/sessions` returns the explicit consent text, current software-only protocol and authorized sessions.
- `POST` to that path requires clinician role, assessment and review scopes. Only `synthetic-capture` version `1` is accepted. The assignment snapshots the protocol and starts awaiting consent.
- `POST /api/patients/{pid}/research/sessions/{rid}/transition` requires participant role and assessment scope. Explicit versioned consent activates the session; a clinician cannot consent as proxy.
- Completion requires a quality category, administration mode and self-reported device category. These are declared metadata, not verified sensor measurements. Poor-quality completion is retained without inventing a score. Interruption, cancellation and consent withdrawal are separate terminal states.
- Stale record versions and changed protocol snapshots block capture. Cancellation and withdrawal remain available after a protocol change. Command receipts bind actor, patient, session and exact request; retries do not duplicate events. Authorization is checked before replay.
- Family users cannot read the research sessions. Organization, active grant and patient binding checks apply. Non-synthetic patients are blocked.

Storage uses the existing versioned `Record` table and atomic audit/receipt transaction; no migration or destructive data operation is needed. PostgreSQL patient-row locks serialize commands using the established authorization helper. SQLite is for local development and does not provide equivalent production concurrency guarantees.

## Limits and next integration

These endpoints do not collect medical measurements, run the illustrative estimator, create recommendations, change approved care plans, or enable formal assessments. The existing direct observations endpoint remains separate; its historical synthetic research inputs are not retrospectively represented as consented sessions. No reporting or model consumer reads these session records yet. A future consumer must explicitly exclude withdrawn, incomplete and unsuitable-quality sessions and validate protocol compatibility.

Withdrawal stops the workflow but retains stored metadata and audit records. It is not medical-record deletion. Participant-facing synthetic consent/status/completion forms are connected. Adding actual approved capture instruments, retention rules and clinician-approved clinical protocols remains outstanding. No trained ML, clinical accuracy or production readiness is claimed.

## Verification

`TEST_POSTGRES=1 uv run pytest tests/test_research_sessions.py tests/test_capture_boundaries.py tests/test_workspaces.py -q --junitxml=test-results/research-session-tests.xml` exercises SQLite and isolated PostgreSQL schemas. Coverage includes explicit consent, forbidden proxy consent, family and cross-patient denial, duplicate request replay, changed command rejection, stale versions/protocols, required provenance, terminal states, withdrawal and non-synthetic rejection. Capture boundary and workspace regressions run alongside it. Ruff and whitespace checks also run. Exact results are recorded in the roadmap after the command completes.


## Connected interfaces — 7 November

In the clinical dashboard, open **Patient workspace → Research workflow · synthetic only → Load research sessions** to assign the available software-only workflow or inspect its recorded state. In the participant mobile application, open **My Check → Research workflow · synthetic only → Load research sessions**. An assignment is required before participant consent/completion controls appear. Formal My Check assessments remain unavailable. No seeded session, invented measurement, automatic model output or background notification was added.

The shared panel uses the existing patient/actor-scoped API helper and a DOM/patient/actor/epoch boundary. A response for an old page or workspace cannot render into the new page. No research data is cached in shared application state or browser storage. Writes participate in the workspace switch busy guard. Errors are displayed inline, buttons recover after failure, and denied access clears loaded session content. After uncertain saves, users are asked to refresh before retrying; existing server command receipts protect identical command retries. Research states refresh only on explicit load or after a successful action, rather than implying a live clinical feed. Family users have neither panel nor endpoint access.

The consent checkbox is required and unchecked by default. Completion requires explicit self-reported quality, administration mode and device category; none is inferred from the browser or presented as a medical measurement. Withdrawal has a confirmation describing retention. The available video administration category records an externally conducted session; it does not connect video calling.

Browser verification: `research_browser_check` passed **9 scenarios**, covering assignment/consent/completion/withdrawal, required fields, family denial, phone/tablet/desktop reflow and enlarged text, failed-request recovery, access-denial clearing and delayed-response isolation. Reports and screenshots are under ignored `test-results/research-ui/`. The initial browser fixture helper was corrected to handle the empty HTML `open` attribute and to avoid navigating family users to a participant-only tab; no application authorization was relaxed. Existing core, companion, care-page and clinical-design checks are also run in isolated fresh databases. Backend session/capture/workspace tests were rerun: **28 passed** across SQLite and PostgreSQL. Formatting, Ruff and whitespace checks pass. This remains local synthetic verification, not clinical or physical-device validation.


## Separate assessment module — 8 November 2026

The legacy software-only session API above is preserved unchanged. The new `/api/patients/{pid}/assessments` module adds actual SATURN-derived research tasks, distinct consent, evidence and deterministic scoring with clinical review. Its adaptation and clinical-use limits are documented in `assessment-selection-and-implementation.md`. The historical unavailable-state descriptions above predate this module. Qualified clinical approval and validation remain outstanding.
