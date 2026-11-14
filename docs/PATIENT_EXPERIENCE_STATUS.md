# Patient experience: status

Last updated with Stage 2. Items are labelled: **Verified** (automated test or browser check run), **Simulated**, **Planned**, **Needs human approval**.

## Stage 2: care-plan acceptance and Today

| Item | State |
|---|---|
| Alembic migrations (0001 baseline, 0002 plans/acceptance); old databases adopted and stamped; downgrade to 0001 round-trips | Verified (tests + manual round trip) |
| Existing routines become a version-1 plan labelled "legacy accepted" | Verified |
| Plan lifecycle: draft, sent, accepted / declined; a question keeps the plan waiting; recall to edit; changes are a new version; accepting supersedes the old version | Verified (tests) |
| Only an accepted plan creates tasks; a draft or sent plan creates none | Verified |
| Structured fields (time or window, dates, quantity + unit, precautions) validated; a quantity without a unit is refused, never guessed | Verified |
| Today is decided by the server from the person's stored time zone (default Asia/Dubai) | Verified |
| Answers: done, not today, snooze (10/30/60/120 min allowlist), difficulty with a reason; append-only; retried requests and repeated answers add no second record | Verified |
| No answer is never stored or shown as missed; difficulty is not non-adherence; progress shows only what the person marked | Verified |
| Patient UI: plan card with Accept / Ask a question / Not now, checklist ordered by time, snooze, "this is hard" | Verified in browser at 390 px (Arabic, RTL, no page errors) |
| Clinician UI: plan versions with status, structured-field form, Send / Recall, the person's responses, difficulty reports | Written, builds; clinician screen not yet checked in a browser |
| Arabic wording for the new strings | Draft, needs a native clinical reader |
| English layout check at phone width | Planned (the demo user opens in Arabic; English check still to do) |

## Known limits
- A new version lists every routine in the plan, not only the new one. Marking what changed is planned for Stage 3 history.
- Reminder delivery (push or local notification) is Stage 3. Today only shows snoozes; it does not fire alerts.
- Accepting is recorded for the signed-in person only. Family cannot accept on someone's behalf.

## Stage 3: notifications, history, clinician review, suggested fields

| Item | State |
|---|---|
| In-app notifications (plan waiting; plan accepted / declined / question to the sending clinician). They hold the kind and plan id only, no routine or question text; private to the owner | Verified (tests) |
| Person's "Your record": what they marked over the last 14 days, plans answered; labelled patient-reported; days with nothing marked are not listed | Verified (tests) |
| Clinician "Mark as read" on a plan answer; only this sets "a clinician has read your answer" for the person | Verified (tests + browser, desktop width) |
| "Suggest fields from the text": fixed rules, not a model; every number must be in the text, units never guessed, missing time/days flagged "needs the clinician"; nothing saved until the clinician adds the routine | Verified (tests + browser) |
| Model-assisted extraction | Planned. No model is used. Any future model proposal must pass the same checks and the clinician approval |
| Arabic numerals (٣٠) in routine text are not read by the suggestion rules; they are left for the clinician | Known limit |
| Push or system notifications outside the app | Planned |
| Notification and record screens in Arabic/English at phone width | Planned for the Stage 10 sweep |

## Stage 4: text assistant

| Item | State |
|---|---|
| Fixed tool list: open screen, read today, explain instruction, mark done, mark not today, snooze, start activity, emergency | Verified (tests) |
| Understanding of words is by fixed English and Arabic patterns, **not a language model**. No health data leaves the server | Verified; model path Planned (would use the same checks and confirmation) |
| Any change (done / not today / snooze) is read back and recorded only after "Yes"; single use, 5-minute life, bound to the person; repeat confirm adds nothing | Verified (tests) |
| More than one routine could be meant: it asks which, never guesses | Verified |
| "Help" words open the urgent page at once; the assistant never calls and never says help is coming | Verified (tests, browser) |
| Audit records tool attempted / succeeded / failed / not understood, never the person's words | Verified |
| Sending anything to another person from the assistant | Not offered (needs the Stage 6 flow with its own Send step) |
| Arabic matching uses a rough root-like form and can join different words; every change is still confirmed | Known limit; needs native-speaker testing |
| Phone-width browser check in Arabic (ask, confirm, ambiguity, not understood, urgent) | Verified; English phone-width check Planned |

## Stage 5: voice and confirmed actions

| Item | State |
|---|---|
| Voice button in the assistant reuses the existing dictation: the person starts and stops recording, a red indicator and timer stay visible, the clip is never stored, voice-recording consent is required | Verified earlier (tests); reused unchanged |
| The transcript only fills the text box; the person reads and fixes it, then presses Send. A spoken change still needs the "Yes" | Verified (tests with a stand-in speech provider) |
| A repeated spoken command cannot record twice; instructions inside speech are plain words; spoken "help" opens the urgent page | Verified (tests, stand-in provider) |
| Long mixed sentences are not treated as "open a screen" requests | Verified |
| "Read aloud" button uses the device's own voice and appears only if the device has a voice for the language | Written; not tested on real devices |
| Live speech accuracy in English and Arabic, and whether intended commands are understood from real speech | **Not evaluated.** Tests use a stand-in provider and say nothing about live quality |
| Microphone capture in a real browser/device | Not tested in this environment |
| English phone-width check of the assistant | Verified (390 px) |

## Assistant conversation memory (added between Stage 5 and Stage 6)

| Item | State |
|---|---|
| Conversation kept in its own table (`assistant_messages`, migration 0005): separate from clinical evidence and care messages, visible only to the person, never given to a model, clinician or family | Verified (tests) |
| Follow-ups read from the last 30 minutes: "it", "that one", "the first/second", "the other one", "again/the same", "and the water?", a typed or spoken "yes"/"no", answers to "which one?" and "how long?" | Verified (tests, browser EN/AR) |
| "Yes" confirms only the newest waiting proposal; "no" cancels it; a new request replaces an older one; an old Yes button or id can no longer record anything | Verified |
| A topic older than 30 minutes is not assumed: the assistant asks which | Verified |
| Notices when something is already marked; recall of the last real question; recap of what was marked today (from stored records) | Verified |
| Greeting, thanks and "what can you do" answered without doing anything | Verified |
| Person can clear the conversation (also drops any waiting proposal) or switch memory off (deletes it; each message then stands alone). Kept 30 days / 200 messages, then pruned | Verified |
| The conversation survives leaving and reopening the screen | Verified (browser) |
| Understanding is still fixed English/Arabic patterns, **not a model**. It follows short, task-focused conversations; it does not hold free conversation, give advice or answer health questions | By design |
| Arabic follow-ups use the same rough root matching; need native-speaker testing | Known limit |
| The stored conversation includes the person's own words and routine text. Retention period and whether it needs its own consent scope | **Needs owner decision** |

## Stage 6: concern reporting and clinician inbox

| Item | State |
|---|---|
| Guided report: fixed topic, how long, own words (typed or dictated); preview of exactly what will be sent; Send only works if nothing changed since the preview | Verified (tests + browser, EN) |
| Recipient chosen by the server from the person's active clinical_review grants; a typed id is accepted only if on that list; no clinician chosen means the draft is kept and cannot be sent | Verified |
| States are each backed by an event with actor and time: draft, sent, delivered, acknowledged, reviewed, closed, withdrawn. "Delivered" means it is in the clinician's in-app inbox. Opening the inbox is not an acknowledgement. The person is shown only states that have an event | Verified |
| Clinician inbox: newest first, no urgency label, no ranking, no interpretation; Acknowledge, Mark reviewed, Close with optional notes; steps cannot be skipped | Verified (tests + browser, desktop) |
| Revoking sharing hides the report from the clinician; the person's record is kept | Verified |
| Withdraw before acknowledgement | Verified |
| Page states it is not an emergency route and shows Urgent help; monitoring hours are shown only if the owner sets `NEUROTWIN_MONITORING_HOURS`, otherwise it says the time is not stated | Verified; **owner must supply real monitoring hours** |
| Assistant ("report a concern", "something is wrong") only opens the flow; it creates and sends nothing | Verified |
| Audit and notifications hold events and ids, never the person's words | Verified |
| Delivery by SMS, email or push | Not built; "delivered" means in-app inbox only |
| Real-time alerting of clinicians; clinical response times; who covers when the clinician is away | **Needs owner / clinical decision**; nothing is promised to the person |
| Editing after preview keeps one draft; unsent drafts are listed with Continue / Discard; discarded drafts are not shown as sent | Verified (browser, AR) after a defect found on review |
| The person sees an in-app update badge when the clinician acknowledges, reviews or closes | Verified (browser, AR) after a defect found on review |
| Arabic phone-width run of the whole report flow | Verified (390 px, RTL, no page errors) |
| Native review of Arabic wording | Planned |

## Stage 7 — Emergency access

| Item | State |
|---|---|
| "Urgent help" button in the header of every patient screen (high contrast, 44 px target); needs no server or model to open | Verified (browser, 390 px, EN and AR) |
| Urgent screen with tap-to-dial `tel:` links; numbers come from `NEUROTWIN_EMERGENCY_NUMBERS`, with built-in 998 / 999 if the server cannot be reached or the setting is invalid | Verified (tests + browser) |
| Numbers are labelled "not checked by the people running this prototype" unless the owner sets `NEUROTWIN_EMERGENCY_VERIFIED=1` | Verified; **owner must verify the numbers for the deployment region** |
| Screen states plainly that NeuroTwin cannot place the call, cannot tell whether it went through, and cannot send anyone | Verified (copy scan in EN and AR forbids "help is coming", "contacted", "notified" and similar) |
| Written steps for when the person cannot use the screen | Verified |
| One trusted person, chosen and typed by the user: Call and Text open the phone's own dialer / messages; number validated, visible only to the user, kept out of the audit log; removable | Verified (tests + browser) |
| Opening the screen is not logged, and the module has no way to call, message or notify anyone | Verified (test) |
| Real calls to services, location sharing, automatic alerts to family or clinicians | Not built, by design |
| Real-device check that `tel:` / `sms:` open the dialer; screen reader; Arabic native review | Planned |
