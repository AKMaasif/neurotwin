# Changelog

All notable changes, newest first. Versions follow `0.x` while NeuroTwin is a research prototype.

## Unreleased

### Added
- xAI Grok as a writing provider (`XAI_API_KEY`, `XAI_MODEL`) for the assistant, drafts and agents, chosen with
  `NEUROTWIN_AI_PROVIDER` or `NEUROTWIN_AGENTS_WRITER`. Meta stays the independent checker. Gemini stays available.
  Screens name the writer in use; earlier results keep the provider that made them.

### Removed
- The voice features. The assistant is typed only: the voice companion panel, voice typing (microphone) in Ask, Tell
  my clinician and family messages, and "Read aloud" are gone, with `/api/voice/status`, `/api/voice/transcribe`,
  `/api/voice/speak` and `/api/companion/config`, the speech-to-text and text-to-speech clients, the `voice_recording`
  consent scope and the `NEUROTWIN_COMPANION`, `GEMINI_TTS_*`, `NEUROTWIN_STT_DAILY_CALLS` and
  `NEUROTWIN_TTS_DAILY_CALLS` settings. Model answers no longer carry a spoken version. The model task-picker for
  wording the fixed rules miss (`companion_nlu.py`) stays for the typed assistant, on demonstration accounts with
  `assistant_model` consent. Earlier `voice_recording` consent decisions stay in the record and the FHIR export.

### Added
- Assistant redesign, phase A (`docs/ASSISTANT_WORKFLOW.md`): what the fixed rules do not know goes to one model call
  that routes and answers (`app/assistant_ai.py`): general questions ("What is the population of India?"), general
  health information, a daily routine drafted from today's tasks and saved only when the person taps Save (their own
  list, shown under Reminders; `GET/PUT/DELETE /api/me/routine`, migration 0010), and app commands checked against the
  same fixed menu. English and Arabic follow the person's message. Every answer passes a fixed guard (no doses,
  medicine changes, diagnoses, false reassurance, contact details; right language) or is replaced by a fixed reply;
  questions about the person's own health, pictures and anything not allowed get fixed wording. Demonstration accounts
  with `assistant_model` consent only; real accounts' words are never sent. Emergency and worrying words are still
  caught first. Short general questions are no longer mistaken for questions about a task.
- Calmer voice: a calm, warm female medical-assistant style (server voice Sulafat, speed 0.9); the device voice prefers
  a female voice at natural pitch. Model answers have a separate spoken version without lists or symbols.
- `docs/BUSINESS_CASE.md`: who pays, price, cost to serve, market size (UAE, GCC, Asia), target users, competitors,
  go-to-market for Abu Dhabi, Dubai, Saudi Arabia and Asia, a six-year plan and risks, with seven charts
  (`docs/business/make_charts.py`). Estimates are marked; unverified facts are listed separately. Abu Dhabi's telemedicine tariff
  (DoH Addendum 30, CPT 99091 at AED 200), the licensing and the data-residency rules are verified and cited.
- HL7 FHIR R4 export of a person's records (`GET /api/participants/{id}/fhir`, `app/fhir.py`): Patient, Observation,
  Provenance and Consent in a collection Bundle with stable ids; for the person or a clinician they chose; audited
  as `fhir.exported`; "Download FHIR R4" on the clinician report. `docs/INTEGRATION_DESIGN.md`: route to the
  facility health record, Malaffi and Sahatna, consent, identity, terminology and gates.
- Test–retest reliability code (`app/reliability.py`: ICC(2,1) and ICC(3,1) with confidence intervals, SEM,
  minimal detectable change, Bland–Altman, sample size) and subgroup analysis (`app/subgroups.py`: Wilson and Newcombe
  intervals, minimum group size), both checked against published examples, with simulation runners and a pilot
  protocol. See `docs/RELIABILITY_STUDY.md` and `docs/SUBGROUP_ANALYSIS.md`.
- `docs/DECIDE_AI.md`: readiness map and outline protocol for the first live clinical evaluation.
- Voice companion in the personal app, behind `NEUROTWIN_COMPANION` (off by default): a persistent panel, explicit
  start, voice activity detection with adjustable pauses, barge-in, captions, typing fallback, spoken replies (server voice
  for consenting demo accounts, otherwise the device voice) and a model-assisted fallback that may only pick from a fixed,
  validated menu. Every change still needs a visible Yes. See `docs/COMPANION_PLAN.md` and `docs/COMPANION_EVALUATION.md`.
- `SUBMISSION.md` (judge-facing summary), MIT `LICENSE` and `THIRD_PARTY_NOTICES.md`.
- "Today's conditions" before each activity: can you see the screen clearly, hear clearly, did you sleep well, are you
  somewhere quiet, do you feel unwell. All optional. Not seeing clearly or a noisy place make the record doubtful;
  poor sleep and hearing difficulty are noted without lowering it (quality rules 0.2). The person's education and
  first language, asked once on an "About you" screen (open to demo accounts too), shown to the clinician as context only. Migration 0009.
- Change engine 0.2: each person's first 2 sessions of a task are practice and never compared (self-reports have no
  practice period); every estimate also shows a z-score (the difference in the person's own day-to-day spread) and a
  reliable change index (Jacobson–Truax) from a named reliability figure, marked provisional because it is assumed,
  not measured. The status still comes from the 95% interval only. The benchmark compares the engine with and without
  practice sessions.
- "Do you need urgent help now?": worrying but not clearly urgent words ("I feel dizzy", "my knee hurts", "أنا تعبان")
  get this question first, with a one-tap "Yes, I need help now" button in the Ask screen and the voice companion. "No"
  says where the help button is and then carries on with what was asked (a change still needs its own Yes). A test
  renders every personal-app screen in English and Arabic and checks the urgent-help button is there; the enlarged
  companion panel no longer covers it. Held-out emergency round 5 recorded (3/20), then fixed: not breathing,
  choking, allergic reaction, fire, burns, low blood sugar, break-in, slurred speech, someone who will not wake,
  disorientation; "help me understand" and "the stroke unit" no longer fire.
- Benchmarks: change engine on simulated people, server response time, and two more held-out emergency rounds
  ([docs/BENCHMARK_REPORT_2026-11-16.md](docs/BENCHMARK_REPORT_2026-11-16.md)).

### Changed
- Voice typing (speech to text) is now for demonstration accounts only; real accounts' voices are never sent to a
  provider. The server voice is off unless `GEMINI_TTS_MODEL` is set (a Gemini key alone no longer turns it on).
- Saved analyses have a single **Run agent** button (the recorded replay); "Show result now" and "Run live" were removed.
  A new real run starts from **Run Agent Analysis** as before.

### Added
- Charts in Agent Analysis: change per region (percent or mm³), left against right, tissue-group shares and alignment fit.
  They redraw the table only, show direction without good/bad meaning, and have table views.
- Agent Activity panel in Brain Analytics, Agent Analysis: a compact status card that expands into the real workflow
  graph, step details, timeline and event list, with live updates, saved-run history and replay. Planned agents and the
  missing brain-extraction step are shown as unavailable. See `docs/AGENT_ACTIVITY.md`.
- Execution events per run (`events.jsonl`) and the `/workflow` and `/runs/{id}/activity` endpoints.

### Fixed
- Phone width (390 px), checked on every screen in English, Arabic and largest text: the patient header puts
  "Need urgent help?" on its own full-width row; the last card is no longer hidden behind the floating companion
  button; the clinician person view stacks the header above the rail and canvas so nothing runs under the mobile
  navigation; the printable report no longer overflows (wide tables and the timeline scroll inside their own box).
- Emergency words: "Help!", "please help", "I'm hurt", "I've fallen", "my chest hurts", "heart attack", "stroke",
  feeling faint and Arabic forms (سقطت، النجدة، لا أستطيع التنفس، جلطة) now open the help screen; "I fell asleep" and
  "I fell behind" no longer do. Also collapse, "can't get up", breathing difficulty, stroke signs, bleeding,
  overdose, seizure, self-harm, emergency numbers and Gulf dialect forms; "fell in love" and "stroke of luck" do not fire. New English/Arabic benchmark with a held-out history ([docs/EMERGENCY_BENCHMARK.md](docs/EMERGENCY_BENCHMARK.md)).
- The assistant no longer reads "well" in "well-being" (or "so" in "so-called") as a filler word, so "well-being
  questions" opens the wellbeing activity again instead of the check-in.
- Alignment and label warping run in a separate process. Before, the server stopped answering for the ~40 s of the
  registration, and Cancel could not take effect until it finished.

## 0.3.0 - 11 November 2026

### Added
- New landing page with one-click demo entry for the patient, clinician and family views (English and Arabic).
- Redesigned participant app: Today screen, bottom tabs, picture-card daily check-in. Answers and skip behaviour
  are unchanged.
- Redesigned family view: sidebar layout, people cards, write-preview-send notes kept.
- Brain Analytics: Compare visits for two visits of the same OASIS-2 person (elapsed days from the dataset's own
  delay, imported measures labelled as imported, voxel-axis views because orientation is unverified, not
  registered), and a descriptive trend over visits for people with three or more visits.
- OASIS-2 manifest reader and subject extractor scripts; the imaging pages are open to every clinician demo account
  in demo mode (`NEUROTWIN_IMAGING_OPEN=0` restores the explicit list).
- Research experiment on stages 9 and 10 with subject-grouped evaluation, baselines and a shuffled-outcome control.
  Result: conversion prediction showed no skill on 15 events; nothing from it is shown per person.
- Imaging workflow document for stages 1-10 with gates, targets and the three bounded agents.
- CI installs the imaging and research packages so their tests run.

### Fixed
- Family view styles no longer leak into the landing page's family card; access cards fit the window.

## Earlier in 0.3.0

### Changed
- Voice typing: clips are converted to WAV in the browser; speech is Gemini only; the request no longer asks for
  "Arabic" in a way that let the model translate.
- Arabic drafts are written fully in Arabic (glossary and Arabic month names); model timeout 120 s; demo dates are
  fixed for the whole day.

### Added
- Voice typing in the family message box: visible recording, transcript to check, clip never stored. Speech provider
  with Gemini; `scripts/try_voice.py` for a live check.
- Family messages: write, preview, then send. Authorised relatives only; the person can read and remove from view.
- Care plan and reminders: clinicians write routines for a person; the person sees today's routines in English or
  Arabic and can answer Done or Not today. No answer is never counted as missed. Demo plan seeded for Fatima.
- Clinician summary drafts: a model writes from stored facts, the output validator checks every statement, and the
  clinician approves, edits or rejects. Drafts keep their facts, model and validator version. Daily call cap.
- Output validator for model-written drafts: citations, numbers and wording are checked by rules before any person
  sees a draft.
- Provider clients for Google Gemini and Meta's Model API behind one interface, keys read from `backend/.env`, and
  `scripts/list_models.py` to see which models a key can use. No model feature is switched on yet.

### Changed
- In demo mode the front page opens any demo view in one click, with no username or password. The password form
  appears only when demo mode is off. Shared demo accounts cannot change their password or sign out other devices.

## 0.2.0 — 10 Nov 2026

### Added
- **Within-person change engine.** Compares a person's earliest 3 usable sessions with their latest 2 for one
  measure and activity version. Gives the difference with a 95% interval from the person's own variation, reads
  "within" or "outside usual variation", and abstains when there are too few usable records or no variation.
  Clinicians only. Shown on the timeline, in the detail panel and in the report.
- **Password sign-in.** scrypt password hashes, server-side sessions in an HttpOnly cookie, CSRF checks,
  rate-limited sign-in, sign-out, password change that ends other sessions, and "sign out other devices".
  An Account screen in all three views.
- **Continuous integration.** Backend tests on Python 3.10 and 3.12 and the web build run on every pull request.
- `CONTRIBUTING.md` with the branch, pull request and release workflow.

### Changed
- The demo account picker is replaced by a username and password form. Demo accounts start with the password
  `neurotwin-demo-2026` (configurable).
- Usernames are shown only to their owner.

### Not yet included
- Account creation, password reset and two-factor sign-in.
- Review of the change-engine settings by a statistician and a clinician.

## 0.1.0 — 10 Nov 2026

First version.
- Evidence core: consent, purpose-scoped sharing, append-only evidence with provenance, deterministic quality
  rules, "To check" items, an audit trail, and logs without health data.
- Personal app (English and Arabic): consent, daily check-in, reaction activity, sharing, own records with
  corrections.
- Family view of shared activity updates.
- Clinician workspace: caseload, timeline, record detail with keep or exclude decisions, Workings and access log,
  printable report.
