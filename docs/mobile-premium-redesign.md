# NeuroCompanion visual redesign — implementation report

7 November 2026. This delivery follows the attached visual reference and premium redesign brief, using the current working source checkout rather than replacing it with an older ZIP export. Scope is exclusively the patient/family application, `/mobile/`. The clinical dashboard and backend remain unchanged.

## Original design and new direction

The existing app already had functional role-aware care workflows and an adaptive shell. Its presentation mixed pill buttons, several unrelated blue/lavender panels, a literal robot illustration, repetitive card treatments and long routine metadata without a clear visual state marker. Home's hierarchy did not provide an immediate overview of the current approved plan. Family coordination, messaging and support needed a more coherent treatment.

The supplied image is a visual direction, not permission to invent its example counts, health indicators, notification bells, profile photos or “updated 12 minutes ago” metadata. This implementation takes the clear hierarchy, compact activity summary and supportive tone while using restrained surfaces and actual records. It avoids purple glows, continuous decorative animation and new clinical claims.

The design language is **quiet editorial care**: warm near-white backgrounds, midnight text, indigo actions, a restrained periwinkle secondary surface and teal/amber only where they distinguish a state or action. A small code-native landscape makes Home recognizable. A paired-path abstract mark replaces the robot, connecting the app identity and companion without a cartoon character.

## Design system

| Token / component | Implementation |
| --- | --- |
| Primary action | Indigo `#4b3cc5`; hover/pressed `#382b9c` |
| Main text | Midnight navy `#18233f` |
| Secondary text | `#556079` |
| Page / secondary surface | Near-white `#f9f9fc`; periwinkle `#eeecfa` |
| Separators | `#e2e4ed`, with stronger form boundaries |
| Semantic states | Existing text states remain authoritative; active teal, paused amber, awaiting-consent blue |
| Typography | One local sans-serif stack: Inter if installed, then Segoe UI/system sans-serif. No font CDN/download or unrelated display face added. |
| Shape | Controlled 1–1.25rem surfaces, distinct timeline entries and flatter editorial sections; buttons replace oversized pills with a quieter rectangle. |
| Interaction | Visible focus, explicit pressed/current states, subtle 140ms hover/press color changes, existing disabled/loading/error semantics. |
| Motion | Companion mark changes only for actual recording. Reduced motion disables animation/transitions. No always-moving background. |

The new `premium.css` is a mobile-only theme/component adapter, loaded after the existing adaptive styles. It does not alter a shared stylesheet or the responsive shell's breakpoints. It adds approximately 15KB of unminified CSS; there is no new package, bitmap, external asset request or framework migration. Local SVGs reserve dimensions and are decorative/hidden from assistive technology where appropriate.

## Screen changes

- **Patient Home:** preserved greeting/date and next activity; added a compact landscape-led plan entry, three differentiated quick actions and a current-plan response summary. Care-team instructions and care-circle/report access retain their real destinations.
- **Plan and shared tasks:** consistent indigo next-activity panel, quieter timeline, textual routine-state labels, wrapped identifiers and grouped controls. Added All / Not confirmed / Confirmed filters for **approved plan activities**, with counts derived from existing task records. These filters do not classify paused routines as pending, change scheduling, or affect consent. Routine cards stay below the filtered timeline.
- **My Check:** redesigned availability surface and guidance retain the explicit “not available” state. No assessment, score or medical conclusion was added.
- **Companion:** replaced the robot with a static abstract connection/voice identity; refined the status, composer, history, shortcuts and explicit confirmation surfaces. Existing recording → transcript review → send, stop/cancel and action-confirmation behavior remains connected. The mark does not imply listening while idle.
- **Support:** unified care-circle/help/concern forms and history. Added a care-team instruction panel using the current approved plan (or a source-review/unavailable message) and a real Step-by-step help destination. Emergency limitations remain explicit.
- **Family:** retained the distinct coordination overview, responsibility acceptance, shared tasks, recipient-scoped reports and family navigation. Family controls do not gain patient task responses, routine-consent controls, private companion memory or sharing administration.
- **Messages / voice notes:** mobile-only conversation, bubble, composer, selection and attachment surfaces. Recording previews, send confirmation, private media retrieval, recipient boundaries and playback behavior retain the existing shared controller.
- **Reports / Settings / Care circle:** consistent surface hierarchy and text styling; real report data, preference controls, access directory, memory export/forget, notifications and sign-out remain unchanged in meaning. Report-bar colors preserve the existing legend.

## Truthful activity summary

The Home ring shows **completed / recorded activities in the current approved plan**, not a health score, expected daily adherence or a clinical progress percentage. It uses the same non-superseded/non-routine-template task collection as the existing page. Zero completed tasks produces zero filled arc; no tasks produces an empty state rather than a fabricated denominator. Scheduled routine occurrences remain separate and accessible in My Plan. The copy labels participant-reported evidence.

Plan filters update visibility on the existing timeline DOM, preserving open routine forms and typed settings. They are local view operations: no POST, record status change, clinical decision or approval occurs. Selection remains patient-context state, cleared by the existing workspace boundary.

## Modified files

- `web/mobile/index.html`: loads `premium.css` only for Application A.
- `web/mobile/premium.css`: new tokens and presentation for all patient/family screens.
- `web/mobile/ui.js`: brand/companion SVGs, Home summary/landscape, plan filters and their non-destructive binding.
- `web/mobile/app.js`: uses the brand mark and binds the plan view controls.
- `web/mobile/care-pages.js`: source-aware care-team support panel and existing companion destination.
- `web/mobile/routines.js`: textual semantic status span; no routine operation/request changes.
- `scripts/adaptive_mobile_browser_check.cjs`: adds 360/390/480px to the established cross-browser matrix.
- `scripts/premium_mobile_browser_check.cjs`: new screenshot, count/filter, idle-recording and role-boundary checks.
- `scripts/isolated_browser_checks.py`: permits the new mobile check in an isolated fixture.

No `web/dashboard/` or `app/` source changed in this pass. A before/after SHA-256 comparison verified **52 dashboard/backend files unchanged**. Existing unrelated local work was preserved. No primary database records were modified by testing, no keys were exposed and no GitHub push/deployment occurred.

## Executed verification

All test data is isolated and synthetic, AI disabled. Provider failures/transcripts in established tests use explicit test doubles. No paid inference or real patient operation was performed.

| Check | Result |
| --- | --- |
| Adaptive matrix | **560 page/viewport/browser checks passed**: 14 sizes × 8 pages × 5 browsers, with selected-contact messaging, no page overflow/clipped controls and zero page-script errors. |
| Browser versions | Chromium 156.0.8078.4; Chrome 156.0.8078.80; Edge 157.0.4341.42; Firefox 157.0; WebKit 26.5. |
| Required phone widths | 320, 360, 375, 390, 430 and 480px all passed. |
| Preserved larger widths | 600, 768, 1024, 1280, 1366, 1440, 1920 and 2560px all passed. |
| Premium patient/family review | Eight screens per role at eight widths: **128 additional layout checks**, screenshots for all 16 role/screen combinations at 390px, actual count verification and filtering/role assertions. |
| Form preservation | Open routine form retains the same DOM node and typed grace period when filtering; resize/orientation retains inputs and current page. |
| Accessibility checks | Navigation targets at least 44px in the matrix; keyboard/touch navigation, pressed states, 200% enlarged text, high contrast, reduced-motion idle companion and reachable final controls checked. |
| Reflow | 125/150/200/400% equivalent CSS viewport tests passed; native browser-toolbar zoom remains untested. |
| Slow/error state checks | Controlled slow workspace response and 503 followed by real retry passed; revoked/role state boundaries remain existing server behavior. |
| Core care regression | Core workflow 8, companion 10, reports 6, routines 9, messages 8, voice notes 10, multimedia 10, care pages 6, family reports 5: **72 scenarios passed**, using latest successful isolated runs. |
| Static checks | Formatting, JavaScript syntax, Ruff and diff whitespace checks passed. |

The first core/companion regression exposed a duplicate accessible name after the compact quick-action description became visually hidden. The quick action now has a distinct descriptive accessible name; the full existing core/companion assertions passed again. A cross-browser batch also hit the existing five-logins-per-account/minute protection when another test used the same instance concurrently. It passed on an isolated fresh test process without weakening authentication. Failed historical runs remain in the artifacts; they are not relabelled as successes.

The Python suite was not repeated for this frontend-only delivery; prior backend results are separately dated. Reports are under ignored `test-results/adaptive-mobile/`, `premium-mobile/` and `isolated-browser/`. Sixteen patient/family screenshots were generated and visually inspected for hierarchy, wrapping, typography and controls. Fixed bottom navigation in full-page screenshots is drawn at the viewport position; reachability was separately tested by scrolling to final actions.

## Accessibility, performance and remaining limits

The implementation targets WCAG 2.2 AA but is not certified. Native screen readers, intended older-adult usability, a full contrast audit, actual Safari/iOS/Android/foldable hardware, virtual keyboards and native browser-toolbar zoom still require review. Windows WebKit is engine coverage, not certification of Safari on Apple hardware.

The final state test recorded one local Chromium sample: **LCP 160ms, CLS 0, DOMContentLoaded 117ms**. This includes a local login transition; it is not a representative production workload or field p75. INP and production Core Web Vitals were not measured. Existing licensed-assessment, clinical ML, device/infrastructure and operational readiness gates remain unchanged. The design does not turn unavailable product functionality into a completed feature.

Reproduce the new checks with an isolated AI-disabled server and existing private demo credential:

```text
node scripts/adaptive_mobile_browser_check.cjs
node scripts/premium_mobile_browser_check.cjs
node scripts/adaptive_state_browser_check.cjs
uv run python -m scripts.isolated_browser_checks
```

Set `NEUROTWIN_BASE_URL` and installed browser executable overrides as documented in `mobile-responsive-architecture.md`. Avoid concurrent login-heavy checks on the same instance; keep its rate protection intact. All visual changes are currently local and unpushed.
