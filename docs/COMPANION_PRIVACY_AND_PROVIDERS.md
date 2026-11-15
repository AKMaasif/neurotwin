# Voice companion — privacy, providers and configuration

## Switches (environment)
| Variable | Meaning |
|---|---|
| `NEUROTWIN_COMPANION=1` | Turns the companion on. Off by default. Off means the old Ask screen and typed assistant only; nothing else changes (rollback = unset it). |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Speech-to-text (existing). Without them there is no voice input and the panel says so. |
| `GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE` | Server voice (optional, unverified until a live check). Without them the browser's own voice is used. |
| `NEUROTWIN_TTS_DAILY_CALLS` (200), `NEUROTWIN_NLU_DAILY_CALLS` (100), `NEUROTWIN_STT_DAILY_CALLS` (100) | Daily provider-call caps. |
Keys stay on the server and are never sent to the browser or written to logs.

## Consent scopes (each its own, revocable, recorded)
- `voice_recording`: lets the app turn short spoken turns into text on the server. Asked inside the panel before the first use. Withdrawing it ends the session and releases the microphone.
- `assistant_model`: lets a language/speech provider be used for (a) understanding wording the fixed rules miss and (b) the synthetic server voice. **Demonstration accounts (synthetic data) only.** Real participants never reach an external provider; they get fixed rules and the device voice.

## Data flow
1. The microphone opens only after: the person opens the panel, presses Start talking, voice consent is on, and the browser allows it. It never opens by itself.
2. Audio is cut into one turn at a time in the browser (WAV, 16 kHz) and sent to `/api/voice/transcribe`. The server does not store audio.
3. The text goes to `/api/assistant/message`: fixed rules first. Only if they fail, only for a consenting demo account, a model may choose **one item from a fixed menu**; the server validates it. Changes are always shown with Yes/No and recorded only after Yes.
4. Spoken replies are the same sentences shown on screen. With the server voice, the reply text (never audio of the person) is sent to the speech provider; otherwise the device voice speaks it locally.

## What is and is not stored
- Session context (the last turns shown in the panel): in the browser tab only; gone on End, sign-out or reload.
- Optional history: the existing assistant memory (30 days / 200 messages), switchable off and clearable from the panel and the Ask screen.
- Preferences (speed, volume, pause length, captions): this browser only.
- Clinical records and care messages: never copied into memory; replies come from the live care-plan API every time.
- Audit: counts and event names only (`companion.spoken`, `companion.nlu_used`, `voice.transcribed` …). No audio, no words, no model output.

## Not done
No wake word and no background listening. No identification of the speaker, mood or health from voice. No emergency call: the urgent screen opens and says the app cannot call anyone.
