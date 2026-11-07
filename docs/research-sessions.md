# Synthetic research session boundary

The session API implements workflow storage, not a clinical assessment or a sensor capture instrument. It preserves the existing mobile reference design and the honest My Check unavailable state.

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

Withdrawal stops the workflow but retains stored metadata and audit records. It is not medical-record deletion. Adding actual approved instruments, participant-facing consent/capture screens, retention rules and clinician-approved clinical protocols remains outstanding. No trained ML, clinical accuracy or production readiness is claimed.

## Verification

`TEST_POSTGRES=1 uv run pytest tests/test_research_sessions.py tests/test_capture_boundaries.py tests/test_workspaces.py -q --junitxml=test-results/research-session-tests.xml` exercises SQLite and isolated PostgreSQL schemas. Coverage includes explicit consent, forbidden proxy consent, family and cross-patient denial, duplicate request replay, changed command rejection, stale versions/protocols, required provenance, terminal states, withdrawal and non-synthetic rejection. Capture boundary and workspace regressions run alongside it. Ruff and whitespace checks also run. Exact results are recorded in the roadmap after the command completes.
