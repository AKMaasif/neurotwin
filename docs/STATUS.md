# Status — version 0.2 (10 Nov 2026)

Four lists, kept separate on purpose. Software tests passing is not evidence of clinical accuracy, and nothing
here has been tried with real older adults, families or clinicians yet.

## Implemented and verified

Verified by the 148 automated backend tests (`backend/tests/`), a clean type-check and production build of the web
app, and a scripted click-through of every screen in Chromium, at phone width (420 px) and desktop width (1360 px),
in English and Arabic.

| Area | What works | How it was checked |
| --- | --- | --- |
| Care plan and reminders | A clinician with a clinical-review grant writes routines (English, Arabic or both; time of day; weekdays). The person sees today's routines in their language, marked as from their clinician, and may answer Done or Not today. Unanswered is never stored or shown as missed. Stopping keeps the history. | `tests/test_careplan.py` (10 tests: access, validation, latest-answer-counts, silence not stored, stop, weekday filter, audit holds no text, 12-routine limit); click-through in Chromium in Arabic (right-to-left) and English. Not yet tested on a real phone or with users. |
| Family messages | A family member with an active sharing grant writes a short message (300 characters, no web addresses), sees a preview of exactly what will be sent, and only then presses Send. Drafts reach nobody; a newer draft replaces an older one; the grant is checked again at Send; 5 messages a day per person. The person reads messages, can remove them from their own view (kept in the record), and is never asked to reply. Clinicians have no route to them and no model sees them. | `tests/test_messages.py` (9 tests); Chromium click-through at phone width in Arabic. Not yet tested on a real phone or with families. |
| Voice typing (plumbing) | In the family message box, "Speak instead" records only after a press, shows a red indicator and timer, releases the microphone on stop, sends the clip once to the speech provider (never stored), and puts the words in the text box for the person to fix. The message still needs Preview and Send. Participants need voice-recording consent; 2.5 MB and daily caps; hidden when no provider is set. | `tests/test_voice.py` (9 tests with a stand-in provider); Chromium click-through with a fake microphone. **Live transcription quality is not measured**, and the Meta speech endpoint shape is unverified (see Experimental). |
| Consent | Give, withdraw, give again; history kept; no session starts or completes without consent; withdrawing keeps earlier records | Tests: `test_consent_and_sharing.py` |
| Sharing | Purpose-scoped grants (`clinical_review` for clinicians, `participation_updates` for family); revoke stops access at once and deletes nothing; family never reaches evidence | Tests, 13 cases |
| Evidence record | Observed / self-reported / inferred kept apart; producer, protocol version and session conditions on every record; missing values need a reason and are never stored as a value | Tests: `test_evidence_and_quality.py` |
| Corrections | Self-reports are corrected by a new record that supersedes the old; observed results cannot be edited, only withdrawn with a reason; both kept and visible | Tests |
| Quality rules | Interrupted, abandoned, assisted, unwell, out-of-range, too few valid taps, early taps, unknown version: labelled, never dropped or changed; review items raised once per session for session-wide reasons | Tests, 9 parametrised cases |
| Inferred records | Refused unless produced by a rule or model, with sources that exist, belong to the same person and are usable | Service-level test (nothing infers yet) |
| Demo entry | In demo mode the front page opens any demo view in one click, with no username or password. It works only for accounts flagged as demo and only while demo mode is on; password change and "sign out other devices" are refused for these shared accounts | Tests: 4 cases in `test_auth.py` + click-through |
| Sign-in | Username and password (shown only when demo mode is off); scrypt hashes; HttpOnly SameSite=Strict session cookie with server-side sessions stored as hashes; CSRF token on every change; 5 failed attempts per minute per username and address; one message for any wrong username or password; sign-out; 8-hour sessions; password change (15–300 characters, current password required) ends other sessions; sign out other devices; usernames shown only to their owner; all audited without secrets | Tests: `test_auth.py`, 12 cases + click-through |
| Access and audit | Forged or expired sessions refused; people cannot read each other; every view or change by someone else is in the access log, without values | Tests |
| Logs | Request logs hold method, masked path, status and time only | Test checks values, free text, tokens and person ids never appear |
| Personal app | Consent, check-in (3 questions, each skippable; Continue needs an answer), reaction activity (practice + 5 taps, stop at any time, interruptions counted), sharing, records with corrections, urgent-help and about pages | Click-through, both languages |
| Family view | Shows only which activities were done and when; shows a plain notice when sharing ends | Click-through + test |
| Clinician workspace | Three panes and an activity dock. Caseload: people grouped by "needs review", a Review card that leads to the work, a To check queue grouped by reason with multi-select. Timeline: one lane per measure on one time axis, sessions with their conditions (interrupted, helped, unwell, open items), doubtful points hollow, unusable and withdrawn records counted on the lane floor and never plotted; table view. Detail: the selected record or session with what it rests on, quality reasons, producer, history, and a Keep / Exclude decision with a required note. Activity: Workings (how the selected session became what is shown, from stored records only) and the access log. Export report. Keys J/K/Esc/W. One pane at a time with a bottom bar below 1100 px. | Click-through at 1440 px and 820 px, English and Arabic |
| Review decisions | Keep (record stays, label unchanged) or Exclude (record withdrawn with the note; a session-wide reason excludes the whole session); batch decisions are all-or-nothing | Tests: `test_review_and_report.py` |
| Change engine | Within-person comparison per measure and activity version: earliest 3 usable records against the latest 2, difference with a t-based 95% interval from the person's own variation; "within" or "outside usual variation"; abstains with too few usable records or no variation; doubtful records counted only when the clinician switches them on; never pools versions; clinicians only, logged. Shown as baseline and recent bands on the timeline, in the detail panel and in the report | Tests: `test_change.py`, 12 cases + click-through |
| Output validator | Refuses a model-written draft when a statement cites nothing or an unknown fact, contains a number not in its cited facts, uses diagnostic, predictive, treatment, advisory, normative or reassuring wording (English and Arabic word lists, Arabic digits read as numbers), or is empty or too long. Lists every problem with its statement | Tests: `test_validator.py`, 20 cases. Rule behaviour only: miss and over-block rates are not measured |
| Report | Server-built factual summary: sessions by status, records by measure and quality, value ranges of usable and doubtful records, open items, decisions with notes; generating it is logged | Tests + click-through |

## Experimental or simulated

- **Speech to text has never run against a real provider.** Gemini is called through its audio input and Meta through
  an OpenAI-style `/audio/transcriptions` call that is a guess until `scripts/try_voice.py` has been run with a real
  recording. Accuracy in Gulf Arabic and with older voices is unmeasured.

- **Sign-in has no account recovery, two-factor sign-in or account creation yet.** Accounts exist only as demo
  accounts with a shared starting password; the rate limit is held in memory for a single server process.
- **Demo mode is open to anyone who can reach the server.** That is intended for judging and demos with synthetic
  data. A server holding real data must run with `NEUROTWIN_SEED_DEMO=0`.
- **All data is synthetic.** The demo accounts and six weeks of records are invented to exercise the screens.
- **Clinician summary drafts are tested with a stand-in model only.** The flow is verified by 14 tests and a
  click-through: facts built from records (no participant free text), one retry with the validator's reasons,
  twice-refused drafts stored without showing their text, approve with edits marked as the clinician's, reject with
  a reason, clinicians with a grant only, a daily call cap, audit events. What a live Gemini or Meta model actually
  writes, how often the validator refuses it, and its Arabic quality are not yet measured: run
  `scripts/try_draft.py --all` with real keys. Model listing with both keys has been run live once (10 Nov 2026).
- **Approved summaries stay in the clinician workspace.** They are not shown to participants or family.
- **Both activities are NeuroTwin prototypes** (`daily_checkin 0.1`, `reaction_time 0.1`). They are not published
  instruments, have no validated scoring, norms or thresholds, and none should be read into them.
- **Reaction timing in a browser** depends on the device, screen and touch latency. Timing accuracy on real
  tablets and phones has not been measured.
- **Arabic wording** is a first draft in Modern Standard Arabic by the development team, not yet reviewed by a
  native speaker or adapted for Gulf usage.

## Planned

- Account creation and invitations, password reset by a verified route, optional two-factor sign-in, role management.
- Encryption at rest; PostgreSQL deployment inside the UAE; a shared rate-limit store when running more than one process.
- Activities chosen and reviewed with clinicians, each versioned with its instructions and scoring.
- A clinician assistant panel (questions about the stored records), behind the same validator.
- Model-assisted wording of reminders (not started; routines are clinician-written text today); voice typing for more screens (only the family message box has it).

- Deletion requests handled by the research team (separate from withdrawal).
- Optional imaging research module (clinician-directed, research only), after the core is validated.

## Awaiting qualified approval

| Item | Who |
| --- | --- |
| Which activities to use, their instructions, scoring and any adaptation | Clinical reviewer |
| Change-engine settings: 3 baseline and 2 recent records, 95% interval, doubtful excluded by default; whether a reliable-change method with published test-retest reliability should replace it once real activities are chosen | Statistician + clinical reviewer |
| Output-validator word lists and limits, and a labelled set of drafts to measure what it misses and over-blocks | Clinical reviewer + Arabic reviewer |
| Which model provider may process which data, and where (UAE data-residency) | Project owner + legal/ethics |
| Quality-rule cut-offs (fewer than 3 valid taps unusable; 2+ early taps doubtful; valid ranges) — engineering defaults now | Clinical reviewer + statistician |
| Consent text, in both languages | Ethics committee + clinical reviewer |
| Arabic wording across the apps | Native-speaker reviewer (Gulf) |
| Urgent-help wording and numbers (UAE: ambulance 998, police 999) | Clinical reviewer |
| Accessibility on real devices with older adults | Accessibility lead + usability study |
| Any use with real participants | Research ethics approval (Abu Dhabi DoH process) |
