# Patient experience: Stage 1 inventory, baseline and plan

Status: **plan, nothing built yet.** Written 13 Nov 2026 from the code on `develop` (patient-side code is unchanged by the imaging and agent work). The brief is `Patient experience improvement` (14 sections); this file is its Stage 1 deliverable.
Words used as elsewhere in the project: *implemented and verified*, *experimental*, *blocked*, *planned*.

## 1. Baseline (before any change)

- Backend: 435 tests pass (`cd backend; python -m pytest -q`), including the imaging and agent work. The patient-side tests are `test_careplan` (10), `test_messages` (9), `test_voice` (9), `test_consent_and_sharing`, `test_evidence_and_quality`, `test_auth`.
- Frontend: `npx tsc -b` clean, `vite build` succeeds.
- Not run in this stage: phone-sized and Arabic browser checks of the existing patient app (done earlier in the project, see `STATUS.md`); real-device, screen-reader and user testing have **not** been done.

## 2. What exists, and what that means

| Brief area | Exists today | Reuse / change / missing |
|---|---|---|
| Auth, CSRF, roles, grants, consent, audit | Sessions, CSRF, `participant/family/clinician`, `clinical_review` and `participation_updates` grants, consent events with history, audit that holds no health values | **Reuse as is.** Add consent scopes only where a new data flow needs one. |
| Evidence and activities | `ActivitySession` + `Evidence` (observed / self-reported / inferred, producer, protocol version, quality, missing reason, corrections). `protocols.py` has `daily_checkin` (sleep hours/quality) and `reaction_time`, both marked prototype | **Reuse.** Add to sessions: `mode` (assessment / practice), `input_method`. Add a small task framework so a new activity is a protocol + a screen. |
| Care plan | `CarePlanItem`: free text EN/AR, day part, weekdays, active/stopped. `CarePlanReply`: done / not_today per day, latest counts, silence never stored. Clinician writes directly and the item is **active at once** | **Change substantially.** No plan version, no sending, no patient acceptance, no structured fields (frequency, time window, start/end date, quantity, unit, precautions, source link), no snooze, question, decline or difficulty. Today the patient never accepts anything, so it does not meet "only accepted plans create active tasks". |
| "Today" | `Reminders.tsx` lists today's items and Done / Not today. Day comes from the device, accepted within one day of the server date. No time zone | **Change.** Compute the local day on the server from a stored IANA time zone (default Asia/Dubai, owner to confirm). |
| Messages | Family to participant only (draft, preview, Send). Clinicians cannot read them, by design | **Missing:** patient to care team. Concerns need their own table and state machine; family messages stay separate. |
| Notifications | None | **Missing.** In-app only first, a table apart from tasks. |
| Voice | Press-to-talk dictation into a text box (`voice.tsx`, `voice.py`), Gemini speech-to-text, needs `voice_recording` consent, clip never stored, 2.5 MB and daily caps. No speech output, no assistant | **Reuse the dictation path.** Assistant, tools, speech output are missing. Live transcription quality is unmeasured; one of two live checks came back translated into Arabic (see `STATUS.md`). |
| Model access | `llm.py` Gemini and Meta clients; demo-data-only rule; output validator with Arabic word lists | **Reuse.** The assistant model only interprets; it never sees more than the patient's own permitted records. |
| Emergency | An "Urgent help" text page: "does not watch over you and cannot call anyone", UAE numbers written into a sentence. No `tel:` link, no persistent button, no trusted contacts | **Change.** Always-visible button, configured numbers, dialer handoff, fallbacks, trusted contacts. Works with no model. |
| Patient progress | `Records.tsx` (own records, corrections). The change engine and report are clinician-only | **Missing:** patient-friendly period report (for example the last eleven days). The change engine's bands stay clinician-only. |
| Accessibility | EN/AR with RTL, large cards | **Extend:** text size, contrast, speech rate, reminder settings per patient. |
| Database | SQLAlchemy `create_all`; **no migration tool** | **Decision needed** (section 6): new tables are safe, but new columns on `CarePlanItem` / `ActivitySession` will not reach an existing database. |

## 3. Instruments and activities: evidence and licensing

Nothing is selected as "validated for NeuroTwin". Each candidate is either an authorised instrument (used only as published) or a NeuroTwin research task (prototype, no norms, no thresholds).

| Candidate | Kind | What I could verify today | Status |
|---|---|---|---|
| **WHO-5** (wellbeing) | Authorised instrument | The copy I could read carries "© Psychiatric Research Unit, WHO Collaborating Center for Mental Health, Frederiksborg General Hospital" and no separate licence text. Recall period: the last two weeks. Six response options scored 5 to 0, raw score 0 to 25, multiplied by 4 for a 0 to 100 scale. The form also prints a screening cut-off (raw below 13) and a "10% change" remark. I could **not** open WHO's publication page or the owner's terms of use from here, so the licence and electronic-use conditions are **unverified**. Arabic: published Arabic validation studies exist, including in an older population; I have not seen the official Arabic wording. | **Build in Stage 8 on the owner's instruction** (terms are the owner's responsibility); the official Arabic text is still needed as an input. No AI translation. Plan: raw and 0 to 100 score only, **no cut-off and no "significant change" label**, because those belong to depression screening and were not validated for this use. Not a daily task: the two-week recall means roughly every two weeks at most. |
| **Existing reaction task** | NeuroTwin research task (v0.1) | Built, tested, marked prototype | **Keep.** Measures response speed and anticipations only. |
| **Picture-sequence memory** | NeuroTwin research task | Needs own picture set (culturally neutral icons), own scoring, own pilot | **Proposed first new cognitive task** (memory is the core family concern). Prototype label, no norms. |
| Pattern comparison, attention / inhibition, working memory, rule switching | NeuroTwin research tasks | Not started | **Roadmap** (brief asks to start with two cognitive activities and one wellbeing instrument). |
| **NIH Toolbox** | Licensed battery | The NIH page was not reachable from here. A search shows an official app and an Arabic version listing exist; licence and use conditions not verified | **Do not re-implement.** At most link out after the owner confirms terms. |
| **PROMIS** (fatigue, sleep) | Licensed, registration and scoring rules | Not verified; Arabic availability unknown | **Roadmap.** Keep the existing sleep items. A fatigue item stays "NeuroTwin question, not a published scale" until a measure is chosen. |

Rules for every activity: assessment mode has fixed instructions and no coaching; practice mode may explain and adjust difficulty; both record protocol version, language, device, input method, assistance, interruptions, completion and relevant context (existing session fields); missing and incomplete results are stored explicitly; the assistant may read the instructions but never answers, changes difficulty mid-assessment or touches a timed trial.

## 4. Design decisions (proposed, for review)

**Care-plan state machine.** `draft` (clinician) -> `extracted_tasks_reviewed` (clinician approves the structured tasks next to the original text) -> `sent` -> patient `accepted` / `question` / `declined` -> only `accepted` creates active tasks. A material edit creates plan version n+1 as a new draft; the accepted version keeps running until the patient accepts the new one (owner to confirm this rule). Stopped plans and every response are kept.

**Structured task fields.** Title, original instruction (verbatim, immutable), assigning clinician, frequency and weekdays, time or window, start and end date, quantity and unit, precautions (clinician-written), plan version, acceptance timestamps, link to the source text.

**AI-assisted extraction.** The model proposes fields from the clinician's text. Rules, not the model, then check: every number in a field must appear in the original text; a unit is accepted only if it is in the text (never guessed: "10 millimeter" is flagged, not turned into minutes); missing frequency, time or unit is flagged "needs the clinician"; no amount, duration, medication or contraindication may be added. The clinician approves before anything is sent. With no model, the clinician fills the fields by hand (same screen).

**Occurrences and responses.** One occurrence = (task, local date), unique. Responses (done, not today, snooze, difficulty) are append-only with an idempotency key so a retry or repeated voice command cannot double-record; the latest per day counts. No response means "not recorded", never missed. Completion is labelled patient-reported. Snooze moves a reminder, not the instruction.

**Concern reports.** States: draft, confirmed, sent, delivered (only where a channel can say so), acknowledged, reviewed, closed. Each change is an event with actor and time. The patient sees only what actually happened; "a clinician has seen it" appears only after an acknowledgement event. Recipient is chosen by the server from the patient's active `clinical_review` grants, never from model output. The screen states monitoring hours (owner to supply) and that it is not an emergency route.

**Assistant.** One assistant, a fixed list of tools; the model returns `{tool, arguments}` that is validated against a schema; the server checks the signed-in patient's permission and executes.

| Tool | Kind | Confirmation |
|---|---|---|
| open screen (today, activities, report, messages, get help) | navigation | none |
| read today's tasks / plan instructions / report summary | read-only, from stored records only | none |
| record Done / Not today for one named task | change | read back, then confirm |
| snooze one reminder | change | read back, then confirm |
| start an activity | navigation | none (the activity has its own start) |
| explain this instruction | read-only, shows the original beside the simple wording | none |
| start a concern report | opens the guided flow | the flow ends with its own Send confirmation |
| send a concern or report | outgoing | explicit confirmation, always |
| emergency | opens the emergency screen immediately | none, and it never calls |

No database queries, URLs, recipient ids or code from model output; retrieved text is treated as untrusted. Each tool call is logged as attempted, succeeded or failed, without the content. If the model is off or the data-approval flag is off, a rule-based matcher handles the common commands in English and Arabic and the screens work by touch. Real patient data goes to a model only when an explicit approval setting is on; the presence of API keys never switches it on (as for the other providers).

**Emergency.** A fixed button on every patient screen, independent of any model. It opens a screen with the configured number(s) for the supported region (a setting the owner verifies, not guessed from interface language), a `tel:` handoff, written fallback steps, and a separate "contact my trusted person" action. Copy states what each device can do. Nothing ever says a call connected or help is coming. Tests use mocks only.

**Patient report.** Any selected period, default "last eleven days", showing the exact dates; recorded activities with completion state and context (sleep, assistance, interruptions) side by side and no causal claim; accepted routines and self-reported answers; missing information listed; clinician-reviewed comments where present. Observed, self-reported and inferred are visually distinct. No composite score, no normal/abnormal, no MRI or risk content.

## 5. Data model sketch (new unless noted)

`CarePlan` (version, status, sent/responded times, time zone); `CarePlanItem` (extended); `PlanResponse` (accept / question / decline, append-only); `TaskOccurrence`-style unique key plus `OccurrenceResponse` (append-only, idempotency key); `Notification` (separate from tasks); `ConcernReport` and `ConcernEvent`; `AssistantAction` (tool, argument hash, status, confirmation); `EmergencyConfig` and `TrustedContact`; `PatientPreferences` (time zone, text size, contrast, speech rate, reminders); `ActivitySession` gains `mode` and `input_method`. Existing legacy care-plan rows are backfilled as "accepted (legacy, before acceptance existed)" so current demos keep working, and are labelled that way.

## 6. Decisions recorded (13 Nov 2026, project owner)

- First two cognitive activities: the existing reaction task and a new picture-sequence memory task, both prototype.
- **WHO-5 is to be built in Stage 8 on the owner's instruction; the owner takes responsibility for its terms of use.** It is still an authorised instrument, not a NeuroTwin task: official wording, recall period, response options and scoring are kept unchanged, and no cut-off or "significant change" label is applied. The Arabic wording must come from the official Arabic form; I will not translate it myself, so the owner needs to supply that text (or its source) before the Arabic version is switched on. Until then Arabic users are told that this questionnaire is not yet available in Arabic.
- Existing routines are kept and labelled "legacy-accepted"; new plans need real acceptance.
- Migrations use Alembic, with a baseline revision for the existing schema.

## 7. Stages, acceptance and open decisions

| Stage | Deliverable | Acceptance (from the brief, section 13) |
|---|---|---|
| 1 | This document | Plan reviewed |
| 2 | Plan versions, send, patient accept / question / decline, Today checklist, time zone, migration | Unaccepted plans create no tasks; occurrences unique; silence stays "not recorded"; legacy demos intact |
| 3 | In-app notifications, response history, clinician review of responses and questions | Patient sees only their own data; clinician sees responses labelled patient-reported |
| 4 | Text assistant: read-only queries and navigation | Every answer traceable to stored records; nothing invented; works with the model off |
| 5 | Voice in and out, confirmed task actions | Correct target, read-back, no duplicates on retry, failures never described as success |
| 6 | Concern reporting and clinician inbox | Nothing sent without confirmation; states shown exactly; no "seen" claim without an event |
| 7 | Emergency access | Works with no model; no connection claims; EN/AR; phone width |
| 8 | Activities: reaction task kept, one new task, WHO-5 only if licence and Arabic text are in hand | Assessment vs practice, protocol records, no borrowed validity |
| 9 | Patient report, appointment preparation, accessibility settings | Eleven-day report correct; layouts hold in EN/AR |
| 10 | End-to-end checks and the status document | All criteria checked or listed as skipped |

**Blocked or needing a person (not guessed):** WHO-5 terms of use and official English and Arabic text; the first cognitive activities beyond the reaction task; monitoring hours and expected response time wording; emergency numbers to configure and verify for the deployment region; clinical review of care-plan wording rules, concern urgency logic (a model must not be the only emergency detector) and any symptom-escalation text; native-Arabic review of all new Arabic; real-device, screen-reader and user testing; push notifications (optional, later).
