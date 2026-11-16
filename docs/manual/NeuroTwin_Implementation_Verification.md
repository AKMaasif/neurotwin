# NeuroTwin implementation verification

**Date of checks:** 16 November 2026
**Companion to:** *IFHAS-NeuroTwin_Professional_Clinical_Product_Manual.pdf*, Edition 2.0

This report says what was run, what was only read in the source, and what could not be checked. The application source
code was not modified. Secrets in `.env` were not read into this report.

## 1. Version and environment

| Item | Value |
|---|---|
| Repository | https://github.com/AKMaasif/neurotwin.git (local working copy D:\NeuroTwin) |
| Branch | feature/voice-companion |
| Commit | e9db1ca, "Assistant: model answers, daily routine, calmer voice; FHIR, reliability, business case" |
| Working tree | Clean except for untracked `.claude/` and `docs/manual/` |
| Remote state | Not checked. Whether the remote contains e9db1ca is unknown. |
| Operating system | Windows 11 Pro (10.0.26200) |
| Python | 3.14.7 (backend virtual environment) |
| Node / npm | 26.7.0 / 12.1.0 |
| Licence | MIT (LICENSE); THIRD_PARTY_NOTICES.md present |

## 2. Tests executed

| Check | Command | Result |
|---|---|---|
| Backend test suite | `python -m pytest` in backend | **756 passed, 14 skipped, 0 failed**, 1 warning, 370.68 s (6 min 10 s) |
| Frontend unit tests | `npx vitest run` in frontend | **60 passed** of 60 |
| Frontend production build | `npm run build` in frontend | Succeeded |
| Running application | Backend on port 8020 with a scratch database; screens driven in headless Chromium | 64 screens captured and used in the manual |

**Discrepancy:** SUBMISSION.md reports 775 passed and 12 skipped. Today's run on the same commit gave 756 passed and 14
skipped. The cause was not investigated (possibly optional dependencies or a different environment). SUBMISSION.md was
not edited.

**Skipped tests include** the independent FHIR library check (fhir.resources is not installed; installing it was not
permitted in this session) and tests that need optional imaging libraries or provider keys.

## 3. How the screenshots were taken

| Setting | Value |
|---|---|
| Browser | Headless Chromium via Playwright (helper script in the session scratch folder) |
| Database | Scratch SQLite file `shots.db`, not the project database |
| Environment | `NEUROTWIN_SEED_HISTORY=1`, `NEUROTWIN_IMAGING_USERS=demo-dr-layla`, `NEUROTWIN_COMPANION=1`, `NEUROTWIN_AI_PROVIDER=off`, `NEUROTWIN_AGENTS_MODE=mock` |
| Port | 8020 |
| Data shown | Fictional demo personas; de-identified OASIS-1 and OASIS-2 scans already prepared on this machine |
| Editing | None. Images were only resized and converted to JPEG for the PDF. |

Because no AI provider was enabled, all drafted text in the screenshots is scripted demonstration text. The manual says
this wherever it appears. Agent Analysis screens show a run (OAS2_0071) recorded earlier with live providers; viewing
and replaying it does not call any provider.

## 4. Features: status and how each was checked

**Ran** = exercised in the running app or by tests today. **Source** = read in code only.

| Feature | Status in manual | Ran | Source | Notes |
|---|---|---|---|---|
| Sign-in, sessions, CSRF | Available | Yes | Yes | auth.py, security.py |
| Demo entry | Available, needs configuration | Yes | Yes | Demo mode only |
| Today and daily routine | Available | Yes | Yes | /api/me/routine |
| Daily check-in | Available | Yes | — | |
| Reaction activity and conditions | Available, needs validation | Yes | Yes | Practice sessions excluded |
| Picture memory | Available, needs validation | Yes | — | Not a validated test |
| Reminders, care plans | Available | Yes | Yes | careplan.py |
| Tell my clinician | Available | Yes | Yes | concerns.py |
| Messages, family notes | Available | Yes | Yes | 300 characters, 5 per day |
| My last days, appointment summary | Available | Yes | Yes | |
| WHO-5 | Partial | Yes | — | English only |
| Reading and display | Partial | Yes | — | |
| Consent and sharing | Available | Yes | Yes | Four scopes |
| About you | Available | Yes | Yes | profile.py |
| Urgent help | Available, needs configuration | Yes | Yes | emergency.py |
| Typed assistant (fixed rules) | Available | Yes | Yes | assistant.py |
| Assistant model answers | Needs configuration | Tests only (mocked) | Yes | assistant_ai.py |
| Voice companion | Off by default, needs configuration and validation | Screen only | Yes | Speech-to-text demo accounts only; browser voice fallback in speak.ts |
| Family view | Available | Yes | — | |
| Clinician caseload, timeline | Available, clinician oversight | Yes | — | |
| Change estimates (change-engine/0.2) | Available, needs validation | Yes | Yes | change.py |
| Summary drafts | Needs configuration, clinician oversight | Scripted mode | Yes | drafts.py, validator.py |
| Access log | Available | Yes | Yes | GET /api/participants/{pid}/audit, last 200 events |
| Concerns and care journeys | Available, clinician oversight | Yes | Yes | Five outcomes |
| Activity analysis | Needs configuration, oversight, validation | Scripted mode, scratch DB | Yes | SVG and CSV export in ActivityAnalysis.tsx |
| Brain Analytics 3D and measurements | Research preview | Yes | Yes | CSV export in BrainAnalytics.tsx |
| Native MRI import | Partial, research preview | Stages 1–3 | Yes | Stages 4–7 blocked |
| Compare visits | Research preview | Yes | — | Trend needs 3 or more visits |
| Agent Analysis replay | Available, research preview | Yes | Yes | No provider calls |
| Agent Analysis live run | Needs configuration | No | Yes | Needs keys and antspyx |
| AI explanation, visual, review, ask | Needs configuration, oversight, validation | Stored outputs only | Yes | |
| Clinician review, family release | Clinician oversight | Yes | Yes | |
| FHIR R4 export | Available, needs validation | Yes | Yes | fhir.py |
| Hosted deployment | Not available | No | — | |
| EHR / Malaffi / Sahatna | Planned | No | Design document | INTEGRATION_DESIGN.md |

## 5. Configuration defaults checked in source

| Variable | Default | Meaning |
|---|---|---|
| NEUROTWIN_DATABASE_URL | backend/neurotwin.db (SQLite) | Database location |
| NEUROTWIN_SECURE_COOKIES | 0 | Must be 1 behind HTTPS |
| NEUROTWIN_DEFAULT_TIMEZONE | Asia/Dubai | |
| NEUROTWIN_MONITORING_HOURS | unset | Text telling participants when the concern inbox is read |
| NEUROTWIN_ACTIVITY_RUNS | backend/activity_runs | Folder for activity-analysis runs |
| NEUROTWIN_AGENTS_SEND_IMAGES | off | 1 allows rendered views to be sent to a provider, each recorded in the egress record |
| NEUROTWIN_IMAGING_ROOT, NATIVE_ROOT | under backend/imaging_data | Imaging data locations |

The full list is in Section 5 of the manual.

## 6. Not verified

| Item | Reason |
|---|---|
| Live AI and speech providers | No keys used; AI_PROVIDER=off for all checks |
| ANTs alignment (antspyx) | Not installed or run |
| SynthSeg segmentation | Not run |
| Install from a clean clone | Checked in the existing working copy only |
| PostgreSQL and HTTPS | Not tested |
| Hosted deployment | No hosted address was available |
| Public remote state | Not checked |
| Independent FHIR validation | Library not installed |

## 7. Observations

- **Stale on-screen text:** the Agent Activity panel's idle message still says "Press Run live", but that button has been removed. Recorded in §20.3 of the manual; not fixed because source changes were not authorised.
- **Side effect of the checks:** a folder `backend/imaging_data/native/84764e8b-8387-4cc8-8a6f-79487e2313b8` was created at 21:18 on 16 Nov 2026 while the native import screens were captured. It is git-ignored and has not been deleted.
- **Scratch database only:** the scripted activity analysis and all other writes were made in the scratch database `shots.db`, not in backend/neurotwin.db.
