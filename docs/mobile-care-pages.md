# Mobile care pages — 7 November 2026

Support, Settings and My Check now follow the selected lavender/blue mobile direction with distinct page hierarchy and accessible labelled controls. The source reference folders remain unchanged.

Support includes a care-circle introduction, practical-help/concern anchors, actual authorized help contacts, existing request submission/acceptance/history and a separately presented concern form. There is no fake online status, calling service or emergency dispatch. The existing unmonitored-service boundary remains visible.

Settings groups reading comfort, companion-memory consent, device alerts and session controls. Text size continues to save through the backend; contrast applies to the open app, exposes its pressed state and does not rerender/discard unsaved memory-form input. An explicit note distinguishes transient companion audio from privately stored, explicitly sent message voice notes. No new privacy promises or integrations were introduced.

My Check has a deliberate availability state and an illustrative document/waiting motif. It states that guided assessments are not available in this build, offers the working concern/plan routes, and generates no assessment score. Research assessment implementation is still separate work.

Changed: `web/mobile/app.js`, `web/mobile/index.html`; new shared renderers `web/mobile/care-pages.js`, styles `web/mobile/care-pages.css` and browser check `scripts/care_pages_browser_check.cjs`. Existing form IDs, authenticated endpoints, consent logic and role checks are preserved. No backend/schema/provider changes were made.

Verification used isolated AI-disabled SQLite data and a separate private media root/worker. Screenshots were visually reviewed under ignored `test-results/care-pages/`.

| Browser command | Passed scenarios |
| --- | --- |
| `node scripts/care_pages_browser_check.cjs` | 6: three screens at 320/390/480px and 200% text; final-action reachability; contrast/unsaved input; backend text preference/reload; honest assessment availability; real contacts/help submission and concern review. |
| `node scripts/browser_check.cjs` | 8 |
| `node scripts/companion_browser_check.cjs` | 10 |
| `node scripts/message_browser_check.cjs` | 8 |
| `node scripts/ui_reference_browser_check.cjs` | 7 |
| `node scripts/routine_browser_check.cjs` | 9 |
| `node scripts/voice_note_browser_check.cjs` | 10 |

Formatting, JavaScript syntax and diff checks pass. These are browser-emulation/synthetic-data checks, not physical-device testing or accessibility certification. The Python suite was not repeated for this frontend-only pass. Existing earlier UI refinements remain local with these changes until a GitHub push is requested.

The main PostgreSQL development process was found stopped. Its existing workspace-specific cluster was restarted on loopback port 55439, connectivity verified, and the main API started on 8140. No database replacement or migration was needed for these UI changes. Temporary test services are stopped after verification.
