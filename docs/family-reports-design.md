# Family overview and mobile reports — 7 November 2026

The family home is now a dedicated coordination surface rather than a copy of the participant home. It identifies the shared patient, prioritizes actual requests addressed to the authenticated relative, retains explicit responsibility acceptance, and provides shared-task, support, message and weekly-report entry points. Counts come from authorized saved records. Accepted requests are distinguished from completed activities; the first three pending requests are shown with a link to all requests when necessary. No availability, clinical stability, calling or external delivery is fabricated.

Patient/family weekly reports now use a mobile-specific activity record, labelled count/denominator, state list and seven dated activity rows. Four-week comparisons and action provenance remain available. Empty dates are not labelled missed activities. Live-record update time and saved/approved snapshot metadata retain the existing report contracts. Clinical reports still use the existing clinical renderer; the new mobile renderer receives only the server-projected recipient report, with no added clinical notes or measurements.

Changed files: `web/mobile/ui.js`, `app.js`, `index.html`, `web/dashboard/reports.js`; new `web/mobile/family-reports.js`, `family-reports.css` and `scripts/family_reports_design_check.cjs`. The shared report function delegates to the new renderer only when the mobile renderer exists and the audience is not clinical. Existing authentication, report approval, source-change rejection and family projections remain enforced by the same backend. No backend/schema/provider changes were made.

Verification used isolated AI-disabled SQLite data and a private media root. No paid AI calls were required; the existing report check explicitly mocks a provider outage.

| Browser command | Passed scenarios |
| --- | --- |
| `node scripts/browser_check.cjs` | 8 |
| `node scripts/report_browser_check.cjs` | 6, including recipient privacy, approved snapshots, source changes and empty weeks |
| `node scripts/message_browser_check.cjs` | 8 |
| `node scripts/ui_reference_browser_check.cjs` | 7 |
| `node scripts/family_reports_design_check.cjs` | 5: real requests/acceptance, 320/390/480px, actual report counts and seven dates, 200% text, zero-record week, high contrast and approved saved evidence |

Total: **34 browser scenarios passed** with zero script errors in passing runs. Formatting, JavaScript syntax and diff checks passed. Screenshots under ignored `test-results/family-reports/` were visually inspected. One initial test locator matched nested summaries; narrowing it to the saved-report's direct summary retained the assertion and the test passed afterward.

These are synthetic-data/browser-emulation results, not physical-device, intended-user or accessibility certification. The Python suite was not rerun for this presentation-only change. This pass and preceding UI refinements remain local until explicitly pushed to GitHub.
