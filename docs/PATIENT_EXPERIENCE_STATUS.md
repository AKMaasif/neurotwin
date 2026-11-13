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
