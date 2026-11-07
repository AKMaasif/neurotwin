# NeuroCompanion responsive implementation and verification

7 November 2026. Scope: Application 1, served at `/mobile/`. The clinical application at `/dashboard/` remains independent. This is a responsive frontend delivery, not a declaration that the wider clinical product is production-ready.

## Original problem and audit

The app is a FastAPI-served, plain JavaScript application with role/session state in `S`, existing authenticated API calls, and local tab navigation. It is not an iframe or a separate native mobile build. The viewport meta tag already included `width=device-width` and `viewport-fit=cover`.

The actual desktop restriction was `web/mobile/app.css` setting `#app { max-width: 480px; margin: auto; }`, combined with a fixed, centred navigation dock limited to 456px. Later `ui.css` rules added phone-style padding and a decorative frame above 600px. Pages were flat mobile sequences with no primary/contextual layout boundary. Simply increasing the maximum width would have stretched those sequences and text across desktop screens.

The entry point is `web/mobile/index.html`, controller `app.js`, mobile page renderers `ui.js`, `care-pages.js`, `family-reports.js` and `companion.js`, and existing routine controller `routines.js`. Shared messaging/report assets are loaded from `/dashboard/`; these were inspected but left unchanged. Authentication, permission checks, API contracts, scheduling, consent, data models and server code were not redesigned.

## Architecture and breakpoints

One DOM/state model serves every size. CSS handles resizing; there are no viewport-triggered page renders, duplicate desktop/mobile forms, new routing systems or new dependencies.

| Available space | Behavior and reason |
| --- | --- |
| Below 48rem (768px at the default font) | Full-width phone/foldable layout; familiar five-item bottom dock, safe-area spacing, single-column primary/contextual content. At 600px there is deliberately no forced rail. |
| At least 48rem | Labelled compact rail, because there is now space for a 7rem navigation area and readable single-column content. The rail is sticky and scrollable on short screens so Settings stays reachable. |
| At least 75rem (1200px default) | Full 15rem sidebar with labels, workspace identity, Settings and a keyboard-operable compact-navigation toggle. This does not automatically force a right-hand panel. |
| Content container at least 42rem | Balanced home/support/family/settings grids and eligible activity group columns, based on the actual space remaining after navigation. |
| Content container at least 68rem | Plan primary content and a 16–20rem care-team/support context column. This generally activates around a 1440px desktop, rather than squeezing it onto a small laptop. |
| Routine container at least 32rem | Routine actions can group horizontally. Routine lists use an auto-fitting grid with a 24rem preferred card width and a one-column minimum. |
| Ultra-wide | Entire shell is capped at 112rem (1792px default), centred with proportional gutters. Content and context remain bounded rather than stretching to the monitor edges. |

Media queries use rem units; content grids use named container queries. Without container-query support, the safe single-column page arrangement remains available. Grid/Flexbox handle layout; no new fixed-height application wrapper or extra content scroll container was added. Messaging retains its intentional conversation scroller. Sidebar scrolling exists only to keep navigation usable at short heights.

`adaptive.css` owns the shell geometry and is loaded last by the mobile entry point. The old 480px cap, phone-frame border and duplicated root padding were removed at their original mobile sources. Existing lavender/blue identity, rounded surfaces, approved-plan hierarchy and illustrations remain. The hero still uses the next approved task when available and the existing “Your day, one step at a time” fallback otherwise.

## Components and state preservation

- Header: mobile branding/Settings remain; larger screens use a wrapping topbar and sidebar Settings. Patient/workspace identity and the existing selector remain connected to the same permissions/state.
- Navigation: one five-destination nav element changes from dock to rail/sidebar. Existing participant and family destination sets remain distinct. Accessible labels, current-page state, native title tooltips and keyboard activation are preserved. Compact navigation changes only a root layout class.
- Plan: primary hero, timeline and recurring activities are separate from a semantic care-team/support context region. The latter appears below content on phones and beside it only when space permits. A lone timeline task spans its available grid rather than leaving an empty half row.
- Routines: list/grid wrapper, container-aware action layout, wrapping titles/dates/timezones and visible routine identifiers. All existing active/proposed/paused meanings, consent forms, approval restrictions and API requests remain unchanged.
- Other pages: home, support, settings, family overview, companion, reports and messages expand according to content needs. Companion and unavailable assessment explanations retain readable maximum widths. Report tables and media retain their existing local overflow/preview controls.
- Resizing preserves current tab, authenticated actor, DOM form nodes and unsaved inputs. Existing dock sizing measures safe content clearance. A mobile-only history observer maintains latest-message alignment after shell/composer resizing, while preserving the user's older reading position.

## Files in this delivery

| File | Change |
| --- | --- |
| `web/mobile/index.html` | Loads the mobile-only adaptive stylesheet. |
| `web/mobile/app.css` | Removes the original fixed phone-width wrapper. |
| `web/mobile/ui.css` | Removes obsolete root padding/phone-frame rules. |
| `web/mobile/adaptive.css` | New shell, breakpoint/container rules, spacing tokens, responsive component constraints and navigation styles. |
| `web/mobile/app.js` | Single adaptive shell/topbar/nav placement, existing page wrappers, compact toggle and message-layout hookup. |
| `web/mobile/ui.js` | Plan primary/context structure and viewport-aware dock/history geometry. |
| `web/mobile/routines.js` | Presentation-only list wrapper and routine identifier text. |
| `scripts/adaptive_mobile_browser_check.cjs` | Five-browser, eleven-size page/layout/state matrix. |
| `scripts/adaptive_state_browser_check.cjs` | Expanded forms, text/identifier stress, mocked loading/outage recovery and family/touch checks. |
| `scripts/isolated_browser_checks.py` | Allows the new/adjoining mobile checks to use isolated fixtures. |
| Existing care-pages, clinical/privacy and workspace browser scripts | Select the visible Settings action now that responsive navigation has mobile and desktop placements. Their workflow assertions remain intact. |

No Application 2 or backend source file was changed in this pass. A pre/post SHA-256 snapshot compared **52 dashboard/backend files: zero changed**. Earlier unrelated local changes were retained. No primary database records were modified by these tests; fixtures use a separate SQLite database/private media root with AI disabled. There was no GitHub push or deployment.

## Executed responsive results

All rows passed on **Chromium 156.0.8078.4, Chrome 156.0.8078.80, Edge 157.0.4341.42, Firefox 157.0 and WebKit 26.5**. These are the actual installed test versions, not a claim about every browser release.

| Viewport | Result |
| --- | --- |
| 320 × 568 | 8 pages × 5 browsers passed |
| 375 × 812 | 8 pages × 5 browsers passed |
| 430 × 932 | 8 pages × 5 browsers passed |
| 600 × 800 | 8 pages × 5 browsers passed |
| 768 × 1024 | 8 pages × 5 browsers passed |
| 1024 × 768 | 8 pages × 5 browsers passed |
| 1280 × 720 | 8 pages × 5 browsers passed |
| 1366 × 768 | 8 pages × 5 browsers passed |
| 1440 × 900 | 8 pages × 5 browsers passed |
| 1920 × 1080 | 8 pages × 5 browsers passed |
| 2560 × 1440 | 8 pages × 5 browsers passed |

**440 page/viewport/browser checks** cover Home, My Plan, My Check, Companion, Support, Settings, selected-contact Messages and Weekly summary. They check page overflow, control bounds, session/tab preservation and navigation state. All five browser runs reported zero page-script errors and navigation targets of at least 44 × 44 CSS pixels at the matrix sizes. Screenshots at 375/768/1440/2560px were captured; phone and desktop samples were visually inspected.

Additional executed checks:

- Portrait → landscape → portrait and laptop → narrow transitions retain entered memory-preference text and the original form DOM node.
- 125%, 150%, 200% and 400% **reflow-equivalent CSS viewports**, plus actual CSS text enlargement to 200%. These are explicitly not native browser toolbar zoom tests.
- Expanded real routine-consent fields retain their values across six sizes. Long unbroken routine titles/identifiers wrap; 320px with enlarged text keeps the confirmation action reachable.
- Slow workspace loading and a simulated 503 show usable loading/error states and a successful real retry. These are labelled transport test doubles, not claims about a live outage.
- Family home/tasks/reports/messages/settings/support fit six widths, preserve the family navigation set, and support touch activation.
- Real keyboard navigation opens My Plan; support actions navigate to the existing form and save a synthetic request through the actual API. Compact-navigation state is also tested.

Regression evidence after resolving failures is segmented across fresh isolated fixtures: core workflow **8**, companion **10**, weekly reports **6**, routines **9**, messages **8**, voice notes **10**, multimedia **10**, care pages **6**, family reports **5** = **72 scenarios passed**. An additional clinical/privacy run passed **6** scenarios. These preserve explicit voice recording/preview/send, recipient boundaries, consent, offline responses, report approval and review behavior. The Python suite was not rerun for this mobile presentation-only change; prior backend evidence remains separately dated.

The regression found and corrected latest-message alignment after layout and a test selector targeting a hidden sidebar Settings control. Failed historical runs remain in the test directory; the counts above use the latest successful checks, not the exit code of an earlier failed batch. Reusing the same test server for many login-heavy runs also reached its existing authentication throttle; the state check passed on a fresh test process without changing authentication limits.

## Accessibility and performance

WCAG 2.2 AA remains an engineering target, not a certification. Navigation has explicit labels/current state, visible focus, a working skip link, semantic main/nav/context regions, keyboard-operable controls and measured 44px navigation targets. Status remains text as well as color. Safe areas, dynamic viewport height, enlarged text, reduced motion and high-contrast active-navigation colors are supported. Screen-reader review and a formal contrast/accessibility audit remain necessary.

No new package, image asset, framework or font dependency was introduced. Resizing uses CSS rather than reloading data or replacing forms. Observers are limited to dock/history geometry and disconnected when replaced. A single local Chromium state-test sample recorded **LCP 296ms, CLS 0 and DOMContentLoaded 259.4ms**; it includes the login transition and is not a representative workload. **INP, field p75 and production Core Web Vitals targets were not measured or certified.**

## Reproduction and remaining validation

Start an isolated AI-disabled development API with its own database/media root. Run the matrix first to create its synthetic active/proposed routine fixtures, then run the state test against that same instance:

```text
node scripts/adaptive_mobile_browser_check.cjs
node scripts/adaptive_state_browser_check.cjs
```

Set `NEUROTWIN_BASE_URL` to that test instance. If installed browser revisions differ from Playwright's expected paths, use `PLAYWRIGHT_EXECUTABLE_PATH`, `PLAYWRIGHT_FIREFOX_EXECUTABLE_PATH` and `PLAYWRIGHT_WEBKIT_EXECUTABLE_PATH`; Chrome/Edge use their installed channels. The scripts read the existing generated demo credential privately. Results/screenshots are under ignored `test-results/adaptive-mobile/`. Test reports explicitly record unavailable/failed engines instead of claiming they passed. Repeated authentication-heavy batches should use a fresh isolated process/fixture, not weakened login protection.

Run `uv run python -m scripts.isolated_browser_checks` for the established core regression scripts. Care/family checks can also be named explicitly. Formatter, JavaScript syntax, Ruff and diff checks passed.

Remaining manual work: native toolbar zoom at all requested levels, physical foldable/phone safe areas and virtual keyboards, Android Chrome, actual iOS/macOS Safari, assistive technology and intended older-adult usability testing, and real-user performance monitoring. Windows WebKit testing does not substitute for actual Safari-device verification. Existing `/mobile/` entry URLs and state-based tab behavior are preserved; persistent per-tab deep links were not introduced. The broader project's clinical/ML/hardware/production readiness gates are unchanged.
