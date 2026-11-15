# NeuroTwin voice companion — current-state audit (before any change)

Branch `feature/voice-companion`, from `main` at `126d11a`. Established from code and runs, not from earlier documents.

## What exists and works

| Area | State |
|---|---|
| Patient app | `PersonalApp.tsx` draws one screen at a time from state (`Screen`), with Home tiles, tab bar, `Display` settings (large text, contrast, quiet screen) and EN/AR + RTL. Back/forward is handled by `nav.ts` layers. |
| Assistant (typed) | `personal/Assistant.tsx` + `backend/app/assistant.py`. **Fixed English/Arabic patterns, no language model.** Tools: `open_screen`, `read_today`, `explain_instruction`, `mark_done`, `mark_not_today`, `snooze`, `start_activity`, `emergency`, `start_concern`, plus chat/recall/recap. Changes are proposed with a `confirmation_id`, expire after 5 minutes, run once, and are revalidated on the server. |
| Assistant memory | `assistant_messages`, patient-only, never given to a model/clinician/family, 30 days / 200 messages, clearable, switchable off. Topic goes stale after 30 minutes. |
| Voice input | `voice.tsx` records **only after a button press**, shows a recording indicator and timer, converts to 16 kHz WAV in the browser, sends to `/api/voice/transcribe`. Server needs the `voice_recording` consent, caps 2.5 MB and a daily call limit, never stores audio, audits "transcribed" without words. Text only goes to a text box. |
| Speech provider | `GeminiClient.transcribe` (a multimodal model) is the only STT. No streaming, no VAD, no turn detection. |
| Voice output | Browser `speechSynthesis` only ("Read aloud"), voice chosen by language; no server TTS, no consistent voice. |
| Emergency | Fixed emergency pattern opens the Urgent screen; the assistant never calls and never says help is coming. |
| Privacy rule | Project rule: only synthetic (`is_demo`) data may go to external providers; real participant data never does. |

## What does not exist (so is not claimed)

Persistent conversational session; hands-free listening; voice-activity or end-of-turn detection; barge-in; echo handling; model-assisted understanding; server text-to-speech; an avatar/launcher; a companion state machine; consent for sending conversation to a model; a feature flag for any of this.

## Baseline

- Backend: full suite passes (600 tests) on `main`.
- Existing assistant/voice tests: `test_assistant.py`, `test_assistant_memory.py`, `test_voice.py`, `test_voice_assistant.py`.
- `npm audit --omit=dev`: 0 vulnerabilities. `npm audit` (dev): esbuild ≤0.24.2 / vite ≤6.4.3 (dev-server request exposure, affects `vite dev` only, not the built app). To be fixed as a separate, verified change.
- No frontend unit-test runner is installed; browser checks use Playwright scripts.

## Reusable pieces (extended, not duplicated)

`assistant.message/confirm/cancel/history/clear/set_memory` (all tool execution and confirmation), `voice.transcribe` (consent, limits), `PersonalApp` (host), `useLayer`/`nav.ts` (history), `Display` settings, i18n, consent API.

## Risks found

- Nothing models "the microphone is open" across screens: `VoiceButton` is per-screen and releases on unmount.
- Spoken "yes" is currently typed text through `message()`; it is tied to the single pending proposal, which is the right rule to keep.
- Provider capabilities for streaming STT/TTS are unverified; model names alone prove nothing.
