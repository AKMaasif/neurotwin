# Reference design refinement — 7 November 2026

The selected local references remain `neurotwin-mobile-redesign/neurotwin-mobile-redesign` and `neurotwin-clinical-dashboard/neurotwin-clinical-dashboard`. The earlier review in `output/design-reference-review/DESIGN-REVIEW-AND-IMPLEMENTATION-RULES.md` governs interpretation. Source prototypes were read and their existing screenshots inspected; neither reference directory was modified.

## Mobile changes

Preserved lavender/blue canvas, white rounded surfaces, restrained blue actions, labelled navigation and a friendly blue companion. Home now gives the next real pending activity a single prominent position, followed by three action rows, the actual approved plan and care-circle/report links. Completed tasks are no longer recycled as the next action. Empty states stay truthful; source-review holds, queued responses and consent requirements remain visible.

The compact patient banner keeps the active patient and role explicit. The prototype's fake device status bar, trophy score, identity switch and unsupported disease metrics were not copied. Family accounts have Overview, Tasks, Messages, Reports and Circle destinations; companion and practical support remain accessible. The role still comes from authentication, not a cosmetic switch.

The companion uses a local CSS illustration derived from the reference's blue robot, with no remote portrait or generated raster asset. Navigation to it presents an idle state rather than claiming that the microphone is listening. Speak, transcript review, Send, Stop and confirmation behavior still use the existing implementation.

Typography respects root text scaling. Navigation reserves its measured height through ResizeObserver, including enlarged labels and safe-area padding, so the final action can scroll above the dock. Skip links, visible focus, high-contrast overrides and reduced-motion behavior are preserved/refined. This is not a WCAG certification or an older-adult usability study.

Changed mobile files: `web/mobile/app.js`, `index.html`, `companion.js`, `routines.js`; new `ui.js` and `ui.css`. Shared task and reminder actions still use the existing APIs. Home shows one routine; the plan keeps the previous routine-list behavior. Offline queues remain marked as not confirmed by the server.

## Clinical dashboard changes

Preserved the sage canvas, emerald actions, white evidence surfaces and source-verification layout. The desktop sidebar stays available and scrolls independently with its own viewport height. At tablet widths (≤1100px), an explicit Menu replaces the sidebar that previously consumed review space. Choosing a destination closes it; Escape closes it and restores focus. Active destinations have `aria-current`. Table scroll areas are keyboard-focusable labelled regions. Header actions wrap instead of colliding with patient context.

Dark-mode holds, warnings, source links, primary buttons and focus colors have explicit overrides. Neither a geographic map nor new clinical charts/metrics were fabricated. Existing implemented pages retain their workflows.

Changed clinical files: `web/dashboard/app.js`, `index.html`; new `workspace.css`.

## Verification and evidence

Commands used with the installed Chromium headless shell through `PLAYWRIGHT_EXECUTABLE_PATH` and `NEUROTWIN_BASE_URL` pointing to isolated AI-disabled test servers:

| Command | Result |
| --- | --- |
| `node scripts/ui_reference_browser_check.cjs` | 7 scenarios passed: 320/360/390/480px layouts; touch dimensions; 200% root text at 320px and reachable final action; idle companion; high contrast; distinct family navigation; clinical tablet/keyboard navigation and dark mode. |
| `node scripts/browser_check.cjs` | 8 scenarios passed on a fresh synthetic database, including patient response, family help and clinician approval. |
| `node scripts/companion_browser_check.cjs` | 10 scenarios passed, including capture/transcript confirmation, memory/preferences and interruption handling. |
| `node scripts/message_browser_check.cjs` | 8 scenarios passed, including cross-role privacy, lost response, draft navigation and sign-out. |
| `node scripts/voice_note_browser_check.cjs` | 10 scenarios passed, including actual MediaRecorder with synthetic microphone input, private playback, lost-response retry and cancellation. |
| `node scripts/report_browser_check.cjs` | 6 scenarios passed, including report sharing, stale approval and empty weeks. |
| `node scripts/routine_browser_check.cjs` | 9 scenarios passed with the isolated reminder worker: consent, notifications test double, offline snooze, family help, completion and conflict. |
| `npm run format:check`; `git diff --check`; JavaScript syntax checks | Passed. |

Total: **58 browser scenarios passed**, with no script errors in the passing runs. Layout screenshots are saved under ignored `test-results/ui-reference/`, with machine-readable `report.json`; desktop/mobile reference comparisons were visually inspected. Populated and empty home states were seen. Physical Android/iPhone, assistive-technology and intended-user sessions are still needed; browser emulation and a synthetic microphone do not establish real-device quality.

Early checks found that some existing browser scripts assume a fresh uncompleted task; rerunning those on a consumed test database failed that fixture precondition. The core workflow passed on a fresh isolated database. Navigation checks also caught access paths removed by the first family-nav change; companion/support entry points were retained and those checks passed afterward. Screenshot inspection caught an inherited reference flex style on the robot face; it was corrected and the images recaptured.

The older routine browser script hardcoded port 8140, ignoring the test environment. Its two page URLs now respect `NEUROTWIN_BASE_URL`; no assertions were removed. The synthetic test routine created during that discovery was paused through the authenticated consent API. The successful routine run used a separate SQLite database and worker. Temporary test servers/workers are stopped after verification.

No backend/schema/model/provider change was made in this pass, so the previous Python regression suite was not rerun. Its prior results remain in `docs/messaging.md`; they are not presented as newly executed tests here. These UI changes are local pending an explicit GitHub push request.
