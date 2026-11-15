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
