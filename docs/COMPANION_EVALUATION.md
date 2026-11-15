# Voice companion — evaluation and real-voice protocol

Status date: 2026-11-15. Everything below was run in a development container with **no live speech or language provider**.

## What was measured, and what it means

| Layer | Method | Result | Not shown by this |
|---|---|---|---|
| Session state machine | 10 unit tests (21 in the file with the items below; `frontend/src/companion/companion.test.ts`, `npm test`) | pass | real timing in a browser |
| Voice activity detection | 6 unit tests on synthetic loudness tracks: long pause, 20 s continuous speech, cough/click, steady noise, 45 s cap, leaked assistant voice vs. real barge-in | pass | real rooms, real voices, real loudspeakers |
| Echo / television filter | 2 unit tests on text overlap | pass | acoustic echo (that depends on the browser's echo cancellation) |
| Text → allowed action (fixed rules) | `backend/eval/run_companion_eval.py` on the **dev** set (49 sentences, 13 Arabic): 49/49 after rules were adjusted to fix 4 failures | tuned on this set, so optimistic | generalisation |
| Same, **final** set (50 sentences, 13 Arabic), run once after the rules were frozen | **47/50 (94 %)**. English 35/37, Arabic 12/13. **0 unsafe changes** (no change tool chosen when it should not have been). Failures: Arabic "قمت بالمشي" missed; "I want to prepare for my visit" not understood; "send a message to my daughter" opened the Messages screen (navigation only, nothing sent). | author-written sentences, same author as the rules, small n | real speech, real people, dialects |
| Model-assisted fallback | 28 backend tests with a scripted client (`tests/test_companion_nlu.py`): only a fixed menu is accepted; item numbers, minutes and screens are validated; ids/URLs/free text from the model are ignored; no consent or flag means no model call | pass | any real model's behaviour. No live model was called. |
| Browser flow | Playwright with a fake microphone playing a recorded tone pattern and a scripted transcript (`cv1.js`, 11 checks): launcher, consent, start, greeting by display name, one turn, exactly one transcription call, end releases the microphone, no page errors | pass | real speech recognition, real devices |

Honest caveats:
- The dev and final sentence sets were written by the same developer in one sitting, before either was run. The final set was run once; its failures were **not** fixed afterwards, and the numbers above are as run. Rules were adjusted only against the dev set.
- Test pass rates are software tests, not accuracy in the intended population, and not diagnostic or clinical evidence.
- The speech service (Gemini audio input) and the server voice (Gemini speech output) were **not** called. The speech-output request format is unverified against the live API; a live check is listed below.

## Real-voice evaluation protocol (to be run by people, on real devices)

Purpose: find out whether the companion works for the people it is for, before any claim is made.

1. **Participants.** Older adults (including some with memory concerns), in English and Arabic (Gulf and Levantine/Egyptian dialect speakers if in scope), with a range of hearing, vision, speech and device familiarity. Informed consent for audio capture used only for the evaluation; recordings stored separately from the app, deleted on a stated date. Target sample to be agreed with a qualified reviewer (state the number actually used).
2. **Devices.** At least: one Android phone and Chrome, one iPhone and Safari, one laptop, one tablet; with and without headphones; speaker volume from low to loud. TV on in one condition.
3. **Scripts.** 30 requests per language covering every allowed action, plus ambiguity ("the other one"), slow speech with long pauses, corrections, and the five emergency words. Participants also say whatever they would naturally say.
4. **Measure per language and per device:** word error rate against a human transcript; wrong-action rate (a change proposed for the wrong task); missed-command rate; false activation from TV or the companion's own voice; premature cut-off rate at the default 1.8 s pause; time to first spoken reply; how often the person needed typing; completion of "mark done → Yes" and "report a concern → send". Report counts and intervals, not only percentages.
5. **Accessibility.** Screen reader (VoiceOver, TalkBack, NVDA), keyboard-only, 200 % zoom, high contrast, Arabic right-to-left layout, reduced motion; judged by people who use these every day.
6. **Safety checks.** Say the emergency words in every condition; confirm the urgent screen opens and nothing says a call was made. Revoke voice consent mid-session and confirm the microphone indicator goes off. Close the tab, sign out, lose the network, unplug the microphone, and confirm the microphone is released each time.
7. **Voice quality.** A listening panel rates the server voice and the device voice for clarity, warmth and pronunciation of the item names, in both languages. Only an adult male-sounding **synthetic** voice is used; no real person's voice is imitated.
8. **Decision.** A pass/fail threshold must be set **before** the study by the clinical lead; until then the companion stays behind its flag and is described as an experimental prototype.

## Live checks still to run (need a key and a person)

- Gemini speech output: confirm the request/response shape and the voice name used (`GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE`).
- Gemini audio transcription for the 1.8 s end-of-turn flow and 16 kHz WAV clips, English and Arabic.
- Latency end to end on a mobile connection.
