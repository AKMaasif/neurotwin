# Demonstration polish: current state and plan

Source: the owner's brief of 14 Nov 2026 (17 sections, 9 delivery stages). Status is stated from the code, not from older documents.

## Stage 1 — Inventory (what exists today)

| Brief item | Found in the code before this work |
|---|---|
| Brand | One `Mark` (two rings on navy) and a `Brand` that printed the translated app name. The landing page drew a different icon, Brain Analytics used a generic brain icon, the clinician caseload header showed the mark next to the word "Caseload", and the report used a bare mark |
| Landing portals | Three role cards further down the page; the hero had only "Try the demo" and scroll links |
| Clinician shell | No shared header or footer. Language and sign-out sat in a menu inside the timeline page; Brain Analytics had its own header |
| Loading / Brain Analytics entry | A plain "Opening Brain Analytics…" line; no access notice; no stage-based loading |
| Language | Stored per account; signing in sets the language from the account, which can reverse a choice made on the landing page. Brain Analytics is English only |
| Synthetic history | Demo participants have a small seeded history (about 12 sessions over five weeks); no picture-memory or WHO-5 history; no six-month generator |
| Clinician charts | Existing timeline charts and a change engine for the existing activities; no activity/wellbeing overview for the new ones |
| AI workflow | Agent infrastructure exists for MRI (Gemini drafts, Meta checks, rule checks, mock mode, activity events). No clinician "analyse activity history" workflow |
| Agent Activity panel | Exists for imaging runs only |

## Stages

| Stage | Scope | State |
|---|---|---|
| 1 | Inventory and plan | This document |
| 2 | One brand, direct portal buttons, clinician shell | **Done** (see below) |
| 3 | Real loading stages, Brain Analytics access notice and default tab | **Done** (see below) |
| 4 | Language persistence, RTL for Brain Analytics | Planned |
| 5 | Six-month reproducible synthetic history | Planned |
| 6 | Clinician charts and evidence summaries | Planned |
| 7 | Activity-analysis agents, bounded model use | Planned (needs owner's verified model list and a decision on spend limits) |
| 8 | Compact/expanded workflow panel | Planned |
| 9 | Integrated verification and documentation | Planned |

## Stage 2 — what changed

- One `Brand` component (two-ring mark + the wordmark "NeuroTwin", size and light/dark variants, optional page name). The wordmark is the product name and is the same in both languages. Used on the landing page, the clinician header, the report, the patient and family apps, and Brain Analytics (through the clinician header).
- Landing page: three portal buttons in the first screen: Clinician login (largest), Patient login, Family login. Each uses the existing one-click demo entry. On a server without demo accounts they go to the sign-in form, so nothing bypasses authentication. On phones the nav links are hidden so all three buttons fit in the first screen (390 × 844 checked).
- Clinician shell: one header (brand, current page, language, account, sign out, route back from Brain Analytics) and one narrow footer. The duplicate language and sign-out items were removed from the timeline menu, and Brain Analytics lost its own brand and back button.
- Footer status comes from `GET /api/system/status` (clinicians only): AI mode, each provider as "Configured" or "Not configured", analysis "Idle" or "Running now". It never says "available" or "live", because nothing contacts a provider to produce it; a run is counted as running only if its file changed in the last 15 minutes. No keys, model ids or addresses are returned.

## Not done in Stage 2, stated plainly

- "Available, with a recent successful check" is not implemented: there is no stored provider check yet, so the footer says what is configured and that it has not been checked.
- The still-image and transparent-video work on the landing animation (brief section 3) is not started.
- Patient and family screens were not re-checked after the brand change beyond the type-check and build.

## Stage 3 — what changed

- Workspace loading shows the real steps of the first load: opening the workspace (the session is already known), loading the caseload, loading the first person's records, rendering the views. Each step turns complete only when its data has arrived or it has rendered; there is no artificial delay. If a step fails, the screen names it ("Loading authorized records — did not finish") with Try again and Sign out. Switching people later never brings the loader back. A welcome line appears once when the workspace is ready.
- Brain Analytics: the Brain Analytics button and the footer link now open a short access notice with the exact wording requested, **Enter Brain Analytics** and **Back**. It is an introduction only: every imaging API still enforces research access on the server, and entering starts no analysis and no model call.
- Default tab is now **Images & 3D** (it was Import & processing). The context label follows the tab ("One visit" only for single-visit views; "Two visits compared" for Compare visits and Agent Analysis).
- If the 3D case is unavailable, the page says so and offers Try again, Import & processing and Compare visits.

Checked in the browser (desktop, English): staged loader with a deliberately slowed caseload request, welcome line, notice text, default tab and label, failure state. On the test server the 3D case is not prepared, so the "unavailable" state was what appeared.

Not done: progress messages for Brain Analytics beyond the existing artifact-loading progress (they are real, but there is no separate "checks" step), phone and Arabic checks of these screens (Stage 4).

## Stage 4 — what changed

- **Language persistence.** Signing in no longer replaces the language the person was looking at. Whatever is shown when they press a portal or sign in (the landing choice, or the default) is kept, stored in this browser and saved to their account. On reload the choice made in this browser wins; the account language is used only when this browser has no choice. Checked: landing English → patient demo (account Arabic) stays English after sign-in and reload; landing Arabic → clinician stays Arabic.
- **Brain Analytics** now follows the chosen language and direction: header, tabs, page label, loading and unavailable states, case bar, layer and tool labels, measurements table, region inspector and footer. The 3D scene and MRI slice panes are fixed left-to-right, so anatomy and the L/R/A/P/S/I orientation letters are never mirrored. Physical left/right CSS in these screens became logical.
- **Clinician timeline** labels: Arabic lane labels were clipped because SVG text anchors differently in right-to-left; the label column is wider in Arabic and labels are right-aligned.
- Phone header keeps the brand on one line.

**Stated gap.** Import & processing, Compare visits, Agent Analysis and Source & quality are long research panes with English-only text. In Arabic they appear in a left-to-right English block under a visible Arabic note saying so. They are not machine-translated. Arabic wording throughout is a draft and needs native review.

Checked in the browser at 1280 px and 390 px, English and Arabic: no horizontal overflow, no page errors. Not checked: real devices, screen readers.
