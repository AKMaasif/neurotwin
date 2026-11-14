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
| 3 | Real loading stages, Brain Analytics access notice and default tab | Planned |
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
