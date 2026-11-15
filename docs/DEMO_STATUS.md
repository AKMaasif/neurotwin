# NeuroTwin demonstration — status (branch `feature/demo-polish`)

Independent research prototype. Not clinically validated; no diagnosis, prediction or composite brain-health score. Data shown in the demo is **synthetic and labelled**.

## Implemented and verified (what was actually run)

| Area | Evidence |
|---|---|
| Brand, direct portal entry, clinician shell, loading screens | Browser checks (desktop + phone, EN/AR) during Stages 2–3 |
| Language persistence and RTL | Browser checks EN/AR; sign-in keeps the chosen language |
| Six-month synthetic history (deterministic, idempotent, labelled) | `tests/test_synthetic_history.py` (13 tests) + browser |
| Charts and evidence summaries (range chips, table alternative, no-answer ≠ missed, WHO-5 shown as recorded) | Browser checks, `tests/test_change.py` |
| Activity analysis: ten stages, citation-linked statements, validator, independent check, clinician decisions | `tests/test_activity_analysis.py` (17 tests), browser check of the review screen (desktop EN, phone AR) |
| Agent Activity panel (compact/expanded, run id, software/AI/clinician badges) | Browser check |
| Full backend suite | 593 passed (before the Stage 9 front-end-only changes; backend unchanged since) |
| Front-end type check and production build | `npx tsc -b`, `npx vite build` clean |
| Brain Analytics: Compare visits and Import & processing translated to Arabic | Browser check (desktop AR) |

## Experimental or simulated

- AI text in the demo is **scripted** (`NEUROTWIN_AGENTS_MODE=mock`). Nothing here shows live model quality.
- Provider footer states ("Available", "Not verified") reflect connectivity checks held in memory; they reset on restart.
- Routine replies cover about six weeks, not six months.

## Not verified

- Live Gemini / Meta model runs; the model list and spend limits are owner decisions.
- Real devices, screen readers, keyboard-only audit.
- Arabic wording is a draft and needs native clinical-language review.
- Official Arabic WHO-5 text is not yet supplied.
- Brain Analytics "AI agent" tab and its sub-panels remain English-only (labelled); the 3D/MRI panes are kept left-to-right deliberately; server-produced technical text is English.
- Image panes show black when scans are not prepared on the server (this test server had none).

## Awaiting qualified human approval

- Any clinical use, thresholds or norms; clinician review of prompts and wording.
- Merge of PRs #75 and #76 and of this branch (done by the owner; nothing has been merged or deployed).
