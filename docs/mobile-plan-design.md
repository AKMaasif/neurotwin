# Mobile My Plan design — 7 November 2026

This pass gives My Plan a distinct daily-itinerary layout while preserving the selected lavender/blue mobile reference. A solid blue next-step panel, a restrained decorative orbit, warm morning/cool afternoon/evening markers, connected activity cards and a quiet care-team note replace the flat card feed. The decorative orbit is hidden from assistive technology and represents no health score or completion percentage.

The next step is a real pending activity without a source-review hold. Its link targets the corresponding timeline card rather than duplicating its response controls. Morning, Afternoon, Evening and Other activities group the existing approved period labels; activities with unknown periods remain in Other activities without inventing a scheduled time. Empty periods are omitted. Counts explicitly describe saved participant reports, not clinical adherence or cognitive health.

Done, Later, Step guide, reminders, offline queue status, routine consent and family follow-up retain the existing APIs. Confirmed timeline cards have a separate appearance and no visible repeat response buttons. Family viewers retain shared-task context and cannot receive participant completion controls. Source-review warnings and full care instructions remain present. The supported routine manager remains below the timeline rather than being replaced by nonfunctional mock controls.

Changed files: `web/mobile/ui.js`, `web/mobile/app.js`, `web/mobile/index.html`; new `web/mobile/plan.css` and `scripts/plan_design_browser_check.cjs`. No backend/schema/provider changes were needed. Earlier reference-refinement changes remain local alongside this pass.

Verified with AI disabled, a fresh isolated SQLite database, private media root and a test reminder worker:

| Check | Result |
| --- | --- |
| `node scripts/plan_design_browser_check.cjs` | 5 scenarios passed: 320/390/480px, unique timeline identities, 200% text, reachable last action, next-step target, persisted completion, high contrast and family permissions. |
| `node scripts/companion_browser_check.cjs` | 10 scenarios passed. |
| `node scripts/message_browser_check.cjs` | 8 scenarios passed. |
| `node scripts/routine_browser_check.cjs` | 9 scenarios passed with the isolated worker. |
| `npm run format:check`, JavaScript syntax checks, `git diff --check` | Passed. |

Total: 32 browser scenarios passed, with zero page script errors in those runs. Screenshots under ignored `test-results/plan-design/` were visually inspected. The new layout was tested with synthetic records, not real patient data. Physical-device, assistive-technology and older-adult usability sessions remain required; this is not a claim of accessibility certification. The previous Python suite was not rerun for this frontend-only change. Temporary test processes are stopped after verification; the main application remains on port 8140.
