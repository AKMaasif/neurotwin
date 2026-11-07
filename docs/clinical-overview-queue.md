# Clinical overview and queue refinement — 7 November 2026

The clinical overview now uses the selected sage/emerald reference as an evidence workbench: assigned patient identity, actual awaiting-review/source-hold/task counts, a reported-urgent handoff strip when applicable, current activity evidence, source-verification access and five recent concerns. The old unconditional full-width decorative progress strip is removed. This remains one authorized patient workspace, not a population or hospital-wide caseload.

The review queue now has literal concern/reporter search, review-state selection, explicit Apply/Clear actions and a read-only result count. Reported urgent handoffs appear first, followed by awaiting review, requested information and completed decision states; newer records appear first within a state. All recorded states remain accessible. Filtering is local to the authorized loaded workspace and changes no clinical record. Filter inputs are excluded from the clinical unsaved-edit tracker.

Tables show attributed concerns, actual workflow status, reporter/time and the existing Review evidence action. Reported urgent change remains a human-assistance flag; it is not an inferred diagnosis or a claim that emergency dispatch occurred. Existing case decision forms, source revision checks, clinician identity and approval APIs remain unchanged. The source-review and research-model limitations are still visible without inventing results.

Responsive surfaces preserve the sidebar behavior established in the previous pass. Evidence tables wrap concern text and scroll horizontally inside labelled keyboard-focusable regions when needed. State colors and warning surfaces have explicit dark-mode treatment.

Changed: `web/dashboard/app.js`, `web/dashboard/index.html`; new `web/dashboard/clinical.js`, `web/dashboard/clinical.css`, and `scripts/clinical_design_browser_check.cjs`. No backend, schema, provider or patient-permission changes were made. Earlier local UI changes remain present; nothing in this pass was pushed to GitHub.

Verification used a fresh isolated AI-disabled SQLite database and private media root. Concern creation and review used the real authenticated APIs with synthetic data. The existing report test mocks a provider outage; there were no paid inference calls.

| Command | Passed scenarios |
| --- | --- |
| `node scripts/browser_check.cjs` | 8, including patient/family/clinician review and plan approval |
| `node scripts/report_browser_check.cjs` | 6, including recipient privacy and stale report approval |
| `node scripts/ui_reference_browser_check.cjs` | 7 |
| `node scripts/message_browser_check.cjs` | 8 |
| `node scripts/clinical_design_browser_check.cjs` | 5: actual counters, urgent-hand-off boundaries, read-only search/state/clear, 1440/1024/768px with table keyboard access, dark mode and persisted human decision |

**34 browser scenarios passed**, with no page script errors in those runs. Formatting, JavaScript syntax and diff checks pass. Screenshots under ignored `test-results/clinical-design/` were visually inspected. These are synthetic-data/browser checks, not clinical validation, intended-clinician usability testing or accessibility certification. The Python suite was not repeated for this frontend-only change.
