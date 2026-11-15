# Voice companion — phased plan

Rule for every phase: the existing assistant, tools, confirmations, consent and privacy rules stay as they are; the companion is a new layer on top, behind `NEUROTWIN_COMPANION` (off by default). Turning the flag off removes the companion completely and leaves the existing assistant screen as it was (rollback).

| Phase | Deliverable | Verified by |
|---|---|---|
| 0 | Audit, plan, feature flag + `/api/companion/config` | backend tests |
| 1 | Persistent companion shell: launcher/avatar, compact/expanded panel, controls, status text + icon, history/memory controls, typing fallback, works across patient screens | browser checks EN/AR, keyboard |
| 2 | Session state machine and audio loop: explicit start, consent + permission checks, VAD turn-taking with adjustable silence, "I'm finished", barge-in, echo guard, pause/end, cleanup | unit tests of the machine, browser tests with a fake microphone |
| 3 | Validated tools: add appointment-prep and shared follow-up; every spoken action goes through `assistant.message`; voice confirmation tied to one proposal | backend tests, API tests |
| 4 | Speech output: server TTS adapter (configurable, unverified until a live check), browser voice fallback with disclosure, speed/volume | mocked-transport tests; real voice listed as not verified |
| 5 | Model-assisted understanding, demo accounts only, new `assistant_model` consent, JSON-only proposals validated like any other | tests with a scripted client |
| 6 | Evaluation: synthetic cases and a real-voice protocol; honest counts | docs/COMPANION_EVALUATION.md |
| 7 | Dev dependency security (vite/esbuild) as its own change | `npm audit`, build |

Limits stated up front: "always live" means only while the patient has opened and started a session in an open tab; no background listening; speaker identity, mood or condition are never inferred from voice; an unanswered task is never treated as a problem.


## Status (2026-11-15)
| Phase | State |
|---|---|
| 0 Audit, plan, flag, config | done, tested |
| 1 Persistent shell | done: `personal/Companion.tsx`, 23 browser checks (microphone never opened before Start, persists across screens, EN/AR/RTL, keyboard, 44 px targets) |
| 2 Session + audio loop | done: pure state machine and VAD with 21 unit tests; browser run with a fake microphone. Real devices and real rooms **not** tested |
| 3 Validated tools | done: appointment preparation and shared follow-up added; all spoken requests use `assistant.message`; confirmations unchanged (single use, visible Yes/No) |
| 4 Speech output | built: server voice adapter (unverified against the live API) and browser voice fallback with on-screen disclosure. No real voice was heard or rated |
| 5 Model-assisted understanding | built and tested with a scripted client only; demo accounts + `assistant_model` consent; every pick validated |
| 6 Evaluation | docs/COMPANION_EVALUATION.md: dev 49/49 (tuned), final 47/50 (held out, 0 unsafe changes); real-voice protocol written, not run |
| 7 Dev dependencies | done: vite 6.4.6, vitest 5.1.0, `npm audit` 0 vulnerabilities |

Known gaps: no real-device, screen-reader or native-Arabic review; server voice and live speech/model calls unverified; "continue while minimised" only holds while the tab stays foreground-capable (browsers may still suspend audio); `ScriptProcessorNode` is deprecated (works in all current browsers; an AudioWorklet is the planned replacement); the always-on session is per open tab and ends on reload.
