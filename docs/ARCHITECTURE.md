# Architecture

```
 Older adult ─┐                         ┌─ Clinician
 Family ──────┼── Web app (React) ──────┤
              │   personal · family     │   clinician dashboard
              └───────────┬─────────────┘
                          │  /api (JSON, session cookie + CSRF)
                ┌─────────▼──────────┐
                │  FastAPI service   │   main.py      routes, reply shapes
                │                    │   security.py  passwords, sessions, access
                │                    │   auth.py      sign-in and account routes
                │  deterministic     │   services.py  every state change + audit
                │  core, no models   │   quality.py   evidence-quality rules
                │                    │   protocols.py versioned activities
                └─────────┬──────────┘
                          │ SQLAlchemy
                    SQLite (dev) / PostgreSQL
```

## Clinician workspace (frontend/src/clinician)

| Part | File | What it shows |
| --- | --- | --- |
| Caseload (left) | `Caseload.tsx` | People, the Review card, the To check queue with batch decisions |
| Stage (centre) | `Stage.tsx`, `Timeline.tsx`, `EvidenceTable.tsx` | Tool rail, selection pill, Export report, the timeline lanes or the table |
| Detail (right) | `Detail.tsx`, `Decide.tsx` | The selected record or session, its provenance and the Keep / Exclude decision |
| Activity (bottom) | `Dock.tsx` | Workings for the selected session; the access log |
| Report | `Report.tsx` | Printable summary from `GET /report` |

## Rules the code keeps

- **Who can see what is decided in one place** (`security.py`). A participant sees their own records. A clinician
  needs an active `clinical_review` grant. A family member needs `participation_updates` and gets a summary built
  by `services.family_view`, which has no access to values at all.
- **Every change goes through `services.py`** and writes an audit event. Routes never write to tables directly.
- **Evidence is append-only.** Only `status` and `superseded_by_id` change on an evidence row.
- **Quality rules never alter data.** They label it and raise "To check" items. Missing data must carry a reason.
- **Versions travel with data.** Each record keeps its activity code and version; the chart only plots one version.
- **Logs carry no health data.** `logs.py` logs method, masked path, status and time; uvicorn runs with
  `--no-access-log`.

## Tables

| Table | Holds |
| --- | --- |
| `users` | Role (participant, family, clinician), language, username, scrypt password hash |
| `login_sessions` | Signed-in browsers: hash of the session token, CSRF token, expiry |
| `consent_events` | One row per decision; the newest row per scope is the current state |
| `access_grants` | Owner, grantee, purpose, created, revoked |
| `activity_sessions` | Activity and version, language, device, assisted, unwell, interruptions, status |
| `evidence` | Kind, measure, value or missing reason, unit, producer, version, quality and reasons, status, supersedes |
| `review_items` | "To check" items: reason, raised by (rules version), resolved by, note |
| `audit_events` | Actor, action, target, time — never values |

## API

| Method and path | Who |
| --- | --- |
| `POST /api/auth/login`, `GET /api/auth/session`, `POST /api/auth/logout` | Anyone / signed in |
| `POST /api/account/password`, `GET /api/account/sessions`, `POST /api/account/sessions/revoke-others` | Signed in |
| `GET /api/demo-accounts`, `POST /api/auth/demo-enter` | Anyone, demo mode only: list demo views and open one without a password |
| `GET /api/me`, `PUT /api/me/language` | Signed in |
| `GET/POST /api/consents` | Participant |
| `GET/POST /api/grants`, `GET /api/grants/candidates`, `POST /api/grants/{id}/revoke` | Participant |
| `POST /api/sessions`, `POST /api/sessions/{id}/complete` | Participant with consent |
| `GET /api/participants/{id}/sessions`, `/evidence`, `/review-items`, `/audit` | Participant (own) or clinician with grant |
| `GET /api/evidence/{id}` | Same |
| `POST /api/evidence/{id}/amend` | Participant, self-reports only |
| `POST /api/evidence/{id}/withdraw` | Participant or clinician with grant, reason required |
| `POST /api/review-items/{id}/resolve` | Clinician with grant: decision `keep` or `exclude`, note required |
| `POST /api/review-items/resolve-batch` | Same, several items, all or nothing |
| `GET /api/participants/{id}/report` | Participant (own) or clinician with grant; logged |
| `GET /api/clinician/participants` | Clinician |
| `GET /api/family/shared` | Family |

Interactive API docs: http://127.0.0.1:8000/docs while the server runs.

## Where later parts attach

- **Change engine**: reads current, usable-or-doubtful evidence of one version; writes `inferred` records through
  `services.record_inferred`, which already enforces sources and producer type.
- **Model-assisted drafting**: receives evidence ids, never raw tables; its output goes through a validator, then
  into a clinician review queue. No model output reaches a participant or family without approval.
- **Imaging research module**: a separate service and store, linked by participant id and consent scope only.
