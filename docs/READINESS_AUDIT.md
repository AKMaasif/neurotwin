# Existing-system audit and change record

Audit date: 15 November 2026. Work branch: `codex/care-journey-readiness`.

Before implementation, the existing backend, frontend, tests, migrations and documentation were inspected. The user's existing change to `frontend/package-lock.json` was retained. No provider secrets were printed or changed. No live model request, real patient upload, emergency call, deployment or commit was made.

## Existing architecture

- FastAPI, SQLAlchemy and Alembic provide authenticated APIs, persistent records, consent, care plans, concerns and audit events.
- React/TypeScript provides patient, family and clinician interfaces with English/Arabic presentation.
- Patient activities and evidence include protocol versions, context, quality, corrections and missing data. Existing comparisons are within-person research summaries.
- Activity analysis uses stored evidence and bounded model drafts with clinician review. Voice command interpretation includes fixed patterns; voice plumbing is not evidence of conversational or clinical competence.
- Brain Analytics contains imported/native research processing, MRI views and separate agent runs. This implementation does not replace its processing or claim diagnostic capability.

## Baseline

The initial backend run recorded 565 passed, 5 failed and 13 skipped. Four failures were caused by provider call-limit state leaking between tests; one depended on a real local environment key. Test fixtures now isolate provider keys/counters without editing the actual environment file. The initial frontend production build passed with an existing large imaging-chunk warning.

## Additions

- `care_journeys` and `care_journey_events` are additive migration 0008 tables. Existing concern and plan states are not rewritten.
- A concern's assigned clinician can create an idempotent linked journey and update it with revision checks. Patients can read their own shared follow-up; other clinicians cannot take ownership merely by obtaining a grant.
- A linked activity run must belong to the same person, have explicit review decisions and current source evidence. Fingerprints detect changed evidence; review digests make subsequent review changes visible.
- Source coverage is calculated before model execution. Protocol versions are kept separate in descriptive calculations.
- English/Arabic report commands open the existing eleven-day report. Consequential actions retain the existing confirmation flow.
- Request-log masking now covers activity/agent run identifiers and visit identifiers.
- Fixed software checks export actual results, counts and limitations. They use synthetic records and mock providers.

## Boundaries

Verification after implementation: full backend run 597 passed / 13 skipped; subsequent focused migration
and linked-journey run 19 passed; final readiness export 102 passed / no failures / no skips. Frontend build
passed. Chromium checked saving, 390-pixel layout, Escape after saving and shared follow-up in the Arabic
patient report. The remaining build warning concerns the existing imaging bundle size. Missing `ants`,
`sklearn` and `openpyxl` account for the skipped imaging/research/spreadsheet checks.

An audit and passing tests reduce regression risk; they cannot guarantee that every interaction is defect-free. No real clinical data migration or production database was modified as part of the test runs. Speech accuracy, live-model quality, measurement validity, real-user accessibility and clinical benefit require the separate evaluations in the evaluation plan. Skipped tests are not passes. Existing native-imaging dependency skips must be resolved on the intended imaging host before claiming that environment is verified.
