# Authorized workspaces, clinical review and privacy — 7 November 2026

The existing FastAPI/SQLAlchemy and plain JavaScript clients remain in place. This cycle preserves the reference-based mobile/clinical styles and explicit record → preview → send voice-note behavior. No production deployment, GitHub push or real-patient operation was performed.

## Workspace boundary

`GET /api/patients` returns same-organization patients only when the actor has an active `summary` grant, with the actor's current scope list. One authorized workspace opens automatically; multiple workspaces require an explicit choice. Zero grants show an access empty state with refresh and sign-out actions. All patient APIs still enforce server-side permissions; the picker does not grant access.

The shared controller `web/dashboard/workspaces.js` clears patient records, source selections, report history/notes, companion context, pending proposals, message drafts, attachment viewers and recording resources when switching. It closes the old conversation EventSource, disposes microphone tracks and resets request epochs. A response arriving from a previous workspace cannot update the next workspace. Compound workspace refreshes stage their results before assigning patient state. Unsaved drafts require discard confirmation; active writes block switching. Existing offline packets retain their original actor/patient keys and are not transferred to another patient.

Limited clinician grants hide editing, documents, cases and clinical report controls. Family text scaling is local to the open account session rather than attempting a participant-only preference write. A workspace refresh returning 403 clears cached patient/message context and returns to the authorized chooser. Detection depends on an app request or existing feed/poll; revocation cannot erase information already seen or downloaded.

Initial opening of another tab does not close existing reminder notifications. A deliberate patient switch closes alerts from the old context. Mobile dock geometry is measured before message scroll restoration, so selecting latest messages remains aligned after layout.

## Clinical surfaces

The patient workspace shows current approved support tasks separately from plan draft/approval/supersession history. Entries show source versions, signer/time when recorded, content-hash provenance and explicit source-review holds. The existing draft form and explicit authenticated approval API remain the only plan activation path. Research artifacts are in disclosures with their unvalidated status, rather than presenting raw model output as a clinical score.

Case review separates the original concern, reporter/time, current state, intake-stage evidence and clinician decision. New intake records name deterministic server producers; older missing producer labels remain unavailable. Intake stages are a snapshot, not a live model pipeline. Urgent handoffs have no routine approval form or dispatch claim. Existing review/version/idempotency/role checks remain enforced by the backend.

## Privacy contracts

- `GET /api/patients/{pid}/grants`: participant-only sharing permission directory, limited to the current patient and organization. Settings exposes existing active/removed permission states. Confirmed removal calls the existing revoke endpoint. Adding/restoring access still requires enrollment; self-service invitations are not connected.
- `POST /api/patients/{pid}/companion/memory/export`: explicit participant-only CSRF-protected JSON download, schema `neurotwin.companion-memory.v1`. It exports retained preferences/text only, applies existing seven-day/six-turn retention, sets `Cache-Control: no-store` and an attachment filename, and audits actor/patient/version without copying private conversation text into the audit entry.
- Existing forget resets server companion memory and in-session conversation state. It does not erase prior downloads, care messages, medical records, audit evidence or a provider's independent retention. The Settings copy states these limits. This is not a complete medical-record export or legal deletion workflow.

## Executed evidence

All tests use synthetic fixtures. Browser speech uses a fake microphone; provider outputs/failures use test doubles, not paid inference. No clinical, physical-device or intended-user validation is implied.

| Check | Actual result |
| --- | --- |
| Workspace/API workflows, SQLite + PostgreSQL | 38 passed before privacy additions |
| Privacy/companion/workflow partition | 52 passed |
| Agent-contract partition (7 test files) | 126 passed |
| Remaining backend partition (11 files) | 203 passed, 1 skipped (SQLite RLS) |
| Final workspace/access tests | 10 passed, including 2 newly added directory/revocation cases |
| Distinct backend cases across the two full partitions plus the new access cases | **331 passed, 1 skipped**; other rows overlap and must not be added again |
| Multi-patient browser script | 8 scenarios passed: explicit choice, discard/cancel, SSE close, microphone cleanup, stale response, family text scale, limited scope, revocation/empty access |
| Clinical/privacy browser script | 6 scenarios passed, including real JSON download and revoked-family cache clearing |
| Isolated browser runs, latest successful result per script | Core 8; companion 10; reports 6; routines 9; messages 8; voice notes 10; multimedia 10; reference 7; plan 5; clinical queue 5; clinical/privacy 6 |
| Additional care/family browser scripts | 6 and 5 scenarios passed |

The segmented full-suite total is not a single monolithic run. Results are in ignored `test-results/agent-contracts/`, `integration-remainder.xml`, `sharing-access-tests.xml`, `workspaces/`, `clinical-privacy/` and `isolated-browser/`. Each execution is separate from earlier UI-only evidence. The browser batch initially exposed missing scheduler setup and two client integration issues; the runner now starts a private worker for every fixture, and the corrected routine/message/multimedia paths passed on fresh isolated databases. Failed reports remain available rather than being relabelled as success.

Reproduce with `TEST_POSTGRES=1` and the existing configured test PostgreSQL instance:

```text
uv run python -m scripts.agent_contract_benchmark
uv run pytest tests/test_workspaces.py tests/test_memory_export.py tests/test_worker.py tests/test_voice_notes.py tests/test_pdf_intake.py tests/test_multimedia.py tests/test_messages.py tests/test_media_recovery.py tests/test_document_intelligence.py tests/test_care_rls.py tests/test_additional_contracts.py -q
uv run python -m scripts.isolated_browser_checks
```

The isolated browser runner needs installed Playwright Chromium (or `PLAYWRIGHT_EXECUTABLE_PATH`) and existing generated demo credentials. It launches only loopback servers, disables AI, creates a fresh SQLite database/media directory per check, runs a worker and terminates only its own processes. Fixture databases are retained under ignored `data/`; no primary data is reset. Multimedia checks use the existing synthetic media fixtures and voice-note fixture.

For the multi-patient fixture, use a dedicated `DATABASE_URL=sqlite:///./data/workspace-browser-<unique>.db`, run `uv run python -m scripts.seed_workspace_browser`, start that API, then run `node scripts/workspace_browser_check.cjs` with its base URL. This script intentionally revokes synthetic family grants; use a new isolated fixture when repeating it.

Formatting, Ruff and JavaScript checks passed. Screenshots were inspected for the new patient and limited-access surfaces. Production identity/enrollment, trained clinical models, licensed assessments, real-device/speech validation, background delivery, calling, IoT/camera workflows and operational deployment gates remain outstanding.
