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
