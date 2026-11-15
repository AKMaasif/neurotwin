# Demonstration polish: current state and plan

Source: the owner's brief of 14 Nov 2026 (17 sections, 9 delivery stages). Status is stated from the code, not from older documents.

## Stage 1 — Inventory (what exists today)

| Brief item | Found in the code before this work |
|---|---|
| Brand | One `Mark` (two rings on navy) and a `Brand` that printed the translated app name. The landing page drew a different icon, Brain Analytics used a generic brain icon, the clinician caseload header showed the mark next to the word "Caseload", and the report used a bare mark |
| Landing portals | Three role cards further down the page; the hero had only "Try the demo" and scroll links |
| Clinician shell | No shared header or footer. Language and sign-out sat in a menu inside the timeline page; Brain Analytics had its own header |
| Loading / Brain Analytics entry | A plain "Opening Brain Analytics…" line; no access notice; no stage-based loading |
| Language | Stored per account; signing in sets the language from the account, which can reverse a choice made on the landing page. Brain Analytics is English only |
| Synthetic history | Demo participants have a small seeded history (about 12 sessions over five weeks); no picture-memory or WHO-5 history; no six-month generator |
| Clinician charts | Existing timeline charts and a change engine for the existing activities; no activity/wellbeing overview for the new ones |
| AI workflow | Agent infrastructure exists for MRI (Gemini drafts, Meta checks, rule checks, mock mode, activity events). No clinician "analyse activity history" workflow |
| Agent Activity panel | Exists for imaging runs only |

## Stages

| Stage | Scope | State |
|---|---|---|
| 1 | Inventory and plan | This document |
| 2 | One brand, direct portal buttons, clinician shell | **Done** (see below) |
| 3 | Real loading stages, Brain Analytics access notice and default tab | **Done** (see below) |
| 4 | Language persistence, RTL for Brain Analytics | Planned |
| 5 | Six-month reproducible synthetic history | Planned |
| 6 | Clinician charts and evidence summaries | **Done** (see below) |
| 7 | Activity-analysis agents, bounded model use | Planned (needs owner's verified model list and a decision on spend limits) |
| 8 | Compact/expanded workflow panel | Planned |
| 9 | Integrated verification and documentation | Planned |

## Stage 2 — what changed

- One `Brand` component (two-ring mark + the wordmark "NeuroTwin", size and light/dark variants, optional page name). The wordmark is the product name and is the same in both languages. Used on the landing page, the clinician header, the report, the patient and family apps, and Brain Analytics (through the clinician header).
- Landing page: three portal buttons in the first screen: Clinician login (largest), Patient login, Family login. Each uses the existing one-click demo entry. On a server without demo accounts they go to the sign-in form, so nothing bypasses authentication. On phones the nav links are hidden so all three buttons fit in the first screen (390 × 844 checked).
- Clinician shell: one header (brand, current page, language, account, sign out, route back from Brain Analytics) and one narrow footer. The duplicate language and sign-out items were removed from the timeline menu, and Brain Analytics lost its own brand and back button.
- Footer status comes from `GET /api/system/status` (clinicians only): AI mode, each provider as "Configured" or "Not configured", analysis "Idle" or "Running now". It never says "available" or "live", because nothing contacts a provider to produce it; a run is counted as running only if its file changed in the last 15 minutes. No keys, model ids or addresses are returned.

## Not done in Stage 2, stated plainly

- "Available, with a recent successful check" is not implemented: there is no stored provider check yet, so the footer says what is configured and that it has not been checked.
- The still-image and transparent-video work on the landing animation (brief section 3) is not started.
- Patient and family screens were not re-checked after the brand change beyond the type-check and build.

## Stage 3 — what changed

- Workspace loading shows the real steps of the first load: opening the workspace (the session is already known), loading the caseload, loading the first person's records, rendering the views. Each step turns complete only when its data has arrived or it has rendered; there is no artificial delay. If a step fails, the screen names it ("Loading authorized records — did not finish") with Try again and Sign out. Switching people later never brings the loader back. A welcome line appears once when the workspace is ready.
- Brain Analytics: the Brain Analytics button and the footer link now open a short access notice with the exact wording requested, **Enter Brain Analytics** and **Back**. It is an introduction only: every imaging API still enforces research access on the server, and entering starts no analysis and no model call.
- Default tab is now **Images & 3D** (it was Import & processing). The context label follows the tab ("One visit" only for single-visit views; "Two visits compared" for Compare visits and Agent Analysis).
- If the 3D case is unavailable, the page says so and offers Try again, Import & processing and Compare visits.

Checked in the browser (desktop, English): staged loader with a deliberately slowed caseload request, welcome line, notice text, default tab and label, failure state. On the test server the 3D case is not prepared, so the "unavailable" state was what appeared.

Not done: progress messages for Brain Analytics beyond the existing artifact-loading progress (they are real, but there is no separate "checks" step), phone and Arabic checks of these screens (Stage 4).

## Stage 4 — what changed

- **Language persistence.** Signing in no longer replaces the language the person was looking at. Whatever is shown when they press a portal or sign in (the landing choice, or the default) is kept, stored in this browser and saved to their account. On reload the choice made in this browser wins; the account language is used only when this browser has no choice. Checked: landing English → patient demo (account Arabic) stays English after sign-in and reload; landing Arabic → clinician stays Arabic.
- **Brain Analytics** now follows the chosen language and direction: header, tabs, page label, loading and unavailable states, case bar, layer and tool labels, measurements table, region inspector and footer. The 3D scene and MRI slice panes are fixed left-to-right, so anatomy and the L/R/A/P/S/I orientation letters are never mirrored. Physical left/right CSS in these screens became logical.
- **Clinician timeline** labels: Arabic lane labels were clipped because SVG text anchors differently in right-to-left; the label column is wider in Arabic and labels are right-aligned.
- Phone header keeps the brand on one line.

**Stated gap.** Import & processing, Compare visits, Agent Analysis and Source & quality are long research panes with English-only text. In Arabic they appear in a left-to-right English block under a visible Arabic note saying so. They are not machine-translated. Arabic wording throughout is a draft and needs native review.

Checked in the browser at 1280 px and 390 px, English and Arabic: no horizontal overflow, no page errors. Not checked: real devices, screen readers.

## Gap closure after Stage 4

- **Hero video.** The clip has a black studio background and no alpha channel. It now sits directly on the hero colour: `mix-blend-mode: screen` turns the black into the page colour and a soft mask feathers the edges. The frame, border and black shade are gone. Browsers without blend support get the previous framed look. Play/pause, reduced-motion, Data Saver and the still poster are unchanged. Checked at 1280 px in English and Arabic and at 390 px. Limit: screen blending lightens dark parts of the clip slightly; a true alpha video would need the source footage.
- **Footer provider state.** `/api/system/status` still never contacts a provider. A provider is shown **Available · answered a recent call** only when a real (not scripted) model call made by clinical work succeeded within the last hour, **Unavailable · latest call failed** after a failed call (until a later success), otherwise **Configured**. Records are in memory, so a server restart returns every provider to Configured. Tests: `test_provider_check_states`, `test_invoke_records_outcome`. Not verified against a live Gemini or Meta call.
- **Patient and family screens** re-checked in the browser after the brand change (desktop English, 390 px Arabic and English): one NeuroTwin brand, no overflow, no page errors.

## Stage 5 — six months of synthetic history

Module `backend/app/synthetic_history.py`; tests `backend/tests/test_synthetic_history.py` (12).

- **What it creates** (for `demo-fatima`, Arabic, and `demo-yousef`, English; 182 days back from a reference date): daily check-ins (sleep hours, sleep quality), reaction activity about three times a week, picture-sequence memory about weekly, and WHO-5 fortnightly for the English profile only (no approved Arabic wording exists). It includes assisted sessions, interrupted sessions, skipped questions (`skipped_by_participant`), days with no session at all, a multi-week gap with no records, and a few weeks of shorter sleep with slower responses so charts have something to show. No score, composite or interpretation is written; WHO-5 raw totals equal the published sum.
- **Care-plan replies** to the existing accepted plan's routines (done, not today, difficulty, snooze) from the day each routine exists. No reply on a day is stored as nothing, never as a miss. The demo seed now dates the plan and its routines to the start of the six weeks of sessions, so replies cover about six weeks, not six months, until a longer plan history exists.
- **Reproducible.** Each day's content is a pure function of (seed, participant, date) using a hash-seeded generator. Same seed gives the same data in two databases; a different seed differs.
- **Idempotent, no reset.** Sessions carry the device tag `synthetic-history/1` and replies a fixed idempotency key; both are looked up before writing. Re-running changes nothing; a later reference date only extends. It never edits or removes a record, never writes on a day where the demo seed already has a session of the same activity, and never touches an existing (even revoked) access grant.
- **Labelled.** Sessions and evidence are tagged with the dataset id and version; the clinician workspace shows the dataset label "Synthetic demonstration" with counts and dates (`dataset` on `/api/clinician/participants`). The OASIS imaging case is separate and untouched.
- **Review queue.** The normal quality rules run on every record. Items older than 14 days are written as already reviewed ("kept", noted as synthetic) so the queue is not flooded; recent ones stay open.
- **Demo access.** If a demo person has no clinical-review grant for Dr. Layla, one is created (with a participation consent) so the history is visible. Existing grants are left alone.
- **Switch.** Off by default (tests unchanged). `NEUROTWIN_SEED_HISTORY=1` applies it at startup; `start-imaging.ps1` now sets it. Also `python -m app.synthetic_history --seed N --ref-date YYYY-MM-DD --tz Asia/Dubai`.

Observed: the existing timeline and change panel load the history but are not yet designed for six months (crowded axis labels, session markers overlap, the plot is wider than its pane). That is Stage 6.

## Stage 6 — clinician charts (six months)

- **Range filter** (6 weeks, 3 months, 6 months, all records) with the shown dates and the note "Each chart has its own scale. Nothing is combined into one score." Baseline/recent bands and change estimates are drawn only for "All records", because they are computed over the whole record.
- **Axis** switches from weekly to month ticks for long spans; session markers shrink as days get crowded (A/U flags show only when there is room).
- **Separate charts, each with its own scale:** reaction time, sleep hours, sleep quality, picture-memory rounds right (0–4), WHO-5 raw total (0–25, published English wording; no cut-off, no band, no change label), and routine replies per week as counts by what the person marked. The routine chart states that a day with no reply is not a missed routine and shows no percentage. There is no composite brain-health score anywhere.
- **Tooltips** on hover and keyboard focus: value, date and time, quality with reasons, record id, session id, and for sessions whether it was helped and whether the person reported being unwell. Each record opens the existing detail pane (source record, producer, workings).
- **Table alternative** under every chart (date, value, quality, record, session) plus a weekly table for routine replies; the existing Table view still lists every record.
- **Backend:** `GET /api/participants/{id}/routine-replies` (clinician with a grant only; self-reported; audited; no adherence or "missed" figure).
- **Rule enforced:** the change engine no longer produces any label for WHO-5 (`NO_CHANGE_LABEL`); tested.
- Phone: the chart scrolls sideways inside its card instead of being cut off.

Checked in the browser (English and Arabic, desktop and 390 px): hover details, range filter, new lanes, no overflow, no page errors. Not checked: screen-reader reading of the SVG points, real touch devices. The chart plot is left-to-right in Arabic (time runs left to right) with Arabic labels right-aligned.

## Stage 7 — Activity analysis (backend + bounded model use)

- `backend/app/activity_analysis.py`, `activity_analysis_api.py`. A clinician starts a run for one participant and range (6 weeks / 3 months / 6 months). Nothing starts by opening the page.
- Chain: collect records → profile data quality → describe the person against themselves → build numbered facts (software); draft statements → challenge → independent check → propose charts (AI model); validate wording and numbers (software); clinician decision (human).
- Every AI statement must cite fact ids, add no number not in the facts and avoid forbidden wording; failures are shown as refused, not hidden. Charts are only *proposed* by a model and are drawn by software from recorded values.
- Modes: `live` (real provider, demo data only), `mock` (scripted stand-ins, labelled), `off`. Real participant data is never sent to an external provider.
- Runs are stored as files under `activity_runs/` (git-ignored); no new database tables.
- Status: implemented and unit-tested with the scripted client. **Not verified against a live model.**

## Stage 8 — Agent Activity panel and clinician review (frontend)

- `frontend/src/clinician/ActivityAnalysis.tsx`, opened from "Analyze activity history" on the participant stage.
- Compact panel shows run id, progress and each step with a Software / AI model / Clinician badge and status; expanded view adds summary, provider, model, prompt version, scripted/verified flag and timestamps.
- Statements show citation chips that reveal the fact text, the independent-check result, and validator problems. Doubts, questions and proposed charts (with a values table and dropped suggestions) can each be marked Keep or Discard; a note and "Save my decisions" record only the clinician's own decisions.
- English and Arabic (RTL); step names and notes are localised, model text stays English and is labelled as such.
- Verified: TypeScript build, production build, browser check at desktop (EN) and phone width (AR). Not verified: real devices, screen readers, native Arabic review.

## Stage 8 follow-up — run control, interruption and clinician wording

- `POST /api/activity-analysis/runs/{id}/cancel` (cooperative: checked before each stage; a model call already in flight may still finish at the provider) and `/retry` (a *new* run id with `retry_of`).
- A run recorded as queued/running but not executing in this process is reported as **interrupted** (server restart or crash); it is never shown as done.
- A second start for a person with an active run returns that run (no duplicate billable runs from a double click or second tab).
- Review decisions now include **edit**: the clinician's own wording is stored as theirs (not model output).
- Stages carry `deps`; the expanded panel lays out the workflow by dependency level, lists "After: …", shows the event timeline, and links to the proposed charts and the report.
- Tests: 6 new in `tests/test_activity_analysis.py` (interrupted, cancel, duplicate start, internal failure + retry, edit, dependencies).
- Still not covered: a real server kill mid-run (simulated here by an unclaimed "running" file), live provider failure/quota behaviour, keyboard-only and large-text audit.

## Chart export and Brain Analytics preparation steps

- Proposed charts can be downloaded as SVG or CSV. Each export carries the measure, protocol version, range, the ids of the plotted records, the run id and fact ids, a "drawn by software; suggested by a model" statement and the synthetic-data label where it applies. Verified by downloading both files from the running app.
- Brain Analytics loading now shows four real steps (case, MRI volume and labels, left surfaces, right surfaces) in English or Arabic, driven by the actual artifact loads; no step is shown before it starts.

## Browser history and session routing

The app draws screens from state, not URLs, so Back used to leave the page. `frontend/src/nav.ts` + `useLayer.ts` now manage history:

- Signed in: the stack is always `[ … , guard, view(0), view(n) … ]`. Back can reach `guard` but never what lies below it, and reaching it puts the person straight back on their dashboard. Back therefore never goes to sign-in or the landing page, however many times it is pressed. Refreshing keeps this.
- A screen or dialog above the dashboard (Brain Analytics and its notice, report, activity analysis, mobile panes, patient sub-pages, family Write/Account) is a *layer* with one history entry. Browser Back closes it; closing it with the app's own Back/Close removes that entry, so there are no dead entries. Transitions (analysis → report) are serialized so entries cannot get out of step.
- Only an explicit Sign out, or an ended session, leaves the dashboard. On either, history is cleared of dashboard state; Back/Forward then show only sign-in/landing. The API and app shell are served `Cache-Control: no-store`, and a page restored from the back/forward cache re-checks the session before showing anything.
- Sign-in is unchanged: the same one-click portal buttons and demo accounts.
- Verified with a scripted browser (`nav.js`: 30 checks) for clinician, patient and family, including reload, expired session, Sign out, Back and Forward; plus a backend test for the headers. Not verified: real Safari/Firefox/mobile browsers, and the real browser back/forward cache (headless Chromium does not reproduce it).
- Not in history: tabs inside Brain Analytics and in-page chip filters, which are controls within one screen.
