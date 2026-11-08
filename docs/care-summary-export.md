# Participant care-summary download

Open **Mobile → Settings → Download your care summary**. Confirmation names the selected patient and explains that the downloaded file may contain private information and cannot be recalled. Cancelling sends no export request. The browser downloads a JSON file only while the same actor, patient, workspace epoch and Settings panel are still current. No email, messaging send or cloud storage is involved.

## Scope and API

`POST /api/patients/{pid}/care-summary/export` requires authentication, CSRF, active summary access, participant role and a synthetic patient workspace. Existing server-side patient/organization authorization applies. The endpoint does not accept another account identity from the request body.

The version-1 JSON projection contains patient summary fields and:

- Approved plans and their title/instructions, recorded sign-off and source-review hold flag, when tasks scope is granted.
- Tasks linked to those approved plans, excluding superseded tasks and routine templates, with their recorded status, instructions/scheduling and participant-statement provenance.
- Help requests involving the participant as sender or recipient, when help scope is granted.
- The text-size preference, when preferences scope is granted.

Both record kinds and payload fields are allowlisted. Extra review scope cannot add clinical material to this participant export. Drafts, clinical cases/notes, model artifacts, documents, messages/attachments, companion memory, research sessions, device events, audit logs and superseded plan history are excluded and listed in the file's scope manifest. Existing companion-memory export remains a separate explicit action. This is a limited care summary, not a complete medical-record or subject-access export.

Source-review holds are preserved rather than silently treating affected instructions as current advice. The scope manifest describes participant responses as recorded statements, not proof of medication administration or clinical stability. The JSON is a snapshot of recorded states, not a new assessment, a prediction or a historical as-of reconstruction. No clinical report or score is generated.

The source query is bounded to 1,001 records across permitted categories. More than 1,000 causes a clear failure with no partial file; an authorized partitioned export workflow remains future work. This conservative source cap may also count records later excluded by projection. The server serializes access through the existing patient-row lock, records export schema/count metadata in Audit without care text, and returns application/json with attachment/no-store headers. An audit entry records server-side export preparation, not proof that a browser saved or read the file.

The client disables duplicate submissions, participates in the existing workspace-switch busy guard, displays failures inline and requires another explicit confirmation for retry. Blob URLs are revoked after initiating the download. Changing tabs before a response prevents a late download. Downloaded copies and provider/browser/OS behavior outside the app are not subject to subsequent app access revocation.

## Verification

Tests were written first and reproduced the missing route. `TEST_POSTGRES=1 uv run pytest tests/test_care_export.py tests/test_memory_export.py tests/test_workspaces.py -q --junitxml=test-results/care-export-tests.xml` passed **24 checks** across SQLite/PostgreSQL. They cover private/draft/other-help exclusion, explicit payload projection, extra-review and reduced scopes, current source holds, authentication/CSRF/patient/role/revocation checks, synthetic-only gating, no-text audit metadata, no-store/attachment headers and fail-closed size limits. No schema migration or data deletion is performed.

The new isolated browser check passed **7 scenarios** covering cancellation, actual downloaded JSON, permission denial, service failure/retry, responsive/enlarged-text controls, stale navigation and family restrictions. Care-page, account-session, core, companion and family-report browser regressions also passed. Reports/screenshots are under ignored `test-results/care-export/`. Ruff, repository formatting and whitespace checks pass. The default browser profile now includes this flow (19 configured flows); this cycle ran the six relevant flows rather than claiming a new full 19-flow run.

The earlier 445-test/18-flow integrated checkpoint predates this feature. Its results remain tied to that checkpoint; the 24 targeted checks and six browser flows above are the current incremental evidence. Real enrollment/records, complete medical-record export, message/file export, retention/deletion requests, legal review and physical-device/usability validation remain outstanding. No live patient data or production deployment was used, and no GitHub push is part of this cycle.
