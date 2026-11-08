# Arabic application and voice delivery

8 November 2026. The mobile application and clinician dashboard now support English and Modern Standard Arabic interface copy, semantic RTL layout and bounded Arabic app commands. Arabic wording is an **engineering-reviewed draft**. Qualified Arabic clinical/linguistic sign-off, older-adult usability and real-device speech quality are not established.

## Use

Choose **العربية** in the application-language selector on sign-in or Mobile → Settings. The clinician dashboard also exposes the selector in its header. The browser stores a public language preference under `neurotwin.locale`; both clients on that origin use it. This preference is not a patient record or account-language promise across different devices. Switching language reloads the client; modified text input prompts a warning. A running assessment or voice/write operation cannot switch language through the control.

## Interface architecture

`web/dashboard/ar-catalog.json` is the editable canonical catalog; `ar-catalog.js` is its compiled browser bundle. The current catalog contains **1,350 static strings**, including interface copy and public static server-error messages. A rebuild preserves existing catalog edits instead of overwriting reviewed wording with another provider response. No runtime translation service is used to render the interface.

`ntUi` translates literal template segments before interpolating dynamic values. Names, care instructions, messages, source text, document content, identifiers, amounts and other interpolated records are never passed through the static translator. Values are substituted once; HTML escaping remains the caller's existing responsibility. Only text and human-facing accessibility/placeholder attributes are localized; technical values/classes/IDs are preserved. Native language names remain recognizable in the selector.

The HTML element declares `lang=ar` and `dir=rtl`; Arabic dates use `ar-AE` display formatting. Machine-readable dates, timezone identifiers and protocol reference dates are unchanged. User content uses automatic bidi direction where appropriate. Passwords, technical JSON, source stimuli and sequencing controls retain their required direction. The decorative hero/illustrations are positioned for RTL. Native Arabic-capable system fonts are used without a new remote font dependency.

The previous navigation used an English accessible label as a CSS/DOM selector. Localizing that label exposed a real failure. Navigation now uses a stable `data-primary-navigation` hook, while its accessible name can change language. Existing English theme/reference behavior is preserved.

W3C guidance used for language/direction semantics: https://www.w3.org/International/questions/qa-html-dir . Actual native screen readers, phone keyboards, browser zoom and intended older-adult readability remain separate manual testing requirements.

## Assessment and care-content boundary

The research activity questions, memory targets, word choices, drawing stimuli, protocol consent and scoring reference remain English. The Arabic interface explicitly states that changing application language does not translate or validate the assessment. English comprehension consent is still required. Trial direction/meaning must not silently change with interface direction.

Approved clinical instructions, family messages, source documents and clinician-authored reports are displayed in their original language. A care team can author Arabic content through the existing reviewed workflows. The app does not automatically translate a clinical record, change an approved plan or claim an Arabic SATURN version. English-only care content is not silently read by an Arabic voice.

## Arabic command workflow

Input → explicit recording finish → Arabic Gemini transcription → editable transcript → explicit Send → bounded command proposal → confirmation for a change → existing permission/version checks. Recording alone never executes a command. Arabic recordings explicitly use Gemini; English retains the existing configured Meta route. The interface discloses the Arabic provider before recording. A failure does not silently switch providers.

The Arabic parser normalizes common alef variants, diacritics, tatweel, whitespace and terminal punctuation. It supports named navigation, text-size proposals, reading the approved plan, activity guidance, later/done proposals, help status and stop/cancel. Unknown or ambiguous requests ask for clarification. Arabic negation blocks execution proposals; urgent-help phrases are handled before the negation check. No emergency service is automatically contacted.

Examples:

| Arabic input | Effect |
| --- | --- |
| افتح الإعدادات | Open Settings |
| افتح خطتي | Open My Plan |
| افتح الرسائل | Open Messages |
| كبر الخط | Propose larger text; confirmation required |
| اقرأ خطتي | Read/display the approved plan in its original language |
| انتهيت | Propose an activity response; confirmation required |
| لا تفتح الإعدادات | Clarify; do not navigate |
| توقف / إلغاء | Stop or cancel the companion action |

`Turn.locale` accepts only `en` or `ar`. External processing remains synthetic-only. Arabic transcription returns text and provider provenance, not an executable intent. Audio is not retained by the application endpoint; provider-side terms/retention require separate governance. The provider adapter constrains JSON output, preserves negation in its instruction, bounds text length and redacts provider errors.

Spoken UI output chooses an installed Arabic voice explicitly and sets an Arabic language tag. Without an Arabic voice, the user receives a localized text fallback. It never silently substitutes an English voice. The existing stop/cancel and transcript-review controls remain connected. Voice messages in care conversations retain their separate record → preview → explicit-send workflow.

## Actual speech evidence and limits

Browser checks use clearly identified speech test doubles to verify routing, selected language, cancellation and missing-voice fallback. They are not recognition or pronunciation measurements.

An optional live smoke test generated generic Arabic command audio; no patient audio was used. The current Gemini path completed two of three planned cases, with one command match and one recognition error, followed by a provider-unavailable result. An additional dedicated-model probe was unavailable and was not enabled. The earlier Meta probe also had a recognition error/provider failure. Therefore **live Arabic ASR quality has not passed a release criterion**. The interface labels speech recognition experimental and requires transcript review; typing remains available.

These tiny generated-speech probes cannot establish older-adult, Gulf-dialect, noisy-room, spontaneous-speech or browser-voice performance, even if a later run passes. Recorded local evidence: `test-results/arabic-live-voice/report.json`; the optional reproduction command is `uv run python -m scripts.arabic_voice_benchmark`. Do not repeatedly tune against these few cases and call them an independent test set.

## Wording and release review

The catalog was produced from public static source copy using a configured translation provider, with glossary constraints and engineering review/checks. No user records, private documents, credentials or actual patient content were submitted for translation. Malformed provider output was rejected rather than silently published as a partial catalog. Safety-copy checks preserve the distinction between review and approval, experimental and validated, and saving a request versus emergency dispatch.

Required external reviewers: a qualified Arabic language reviewer and a clinical reviewer familiar with older adults/cognitive impairment. They must check respectful wording, instructions, comprehension, consent, error recovery, urgent-help text, terminology and spoken delivery. Record their identity/qualification, exact catalog/protocol version and approved scope. No such sign-off has been supplied; the visible draft notice must remain.

## Maintain and test

```powershell
node scripts/prepare_localization.cjs --catalog-only
uv run python -m scripts.translate_interface
node node_modules/prettier/bin/prettier.cjs --write web/dashboard/ar-catalog.js
uv run pytest tests/test_arabic.py tests/test_arabic_voice.py -q
uv run python scripts/isolated_browser_checks.py arabic_browser_check
```

The source-tagging tool is idempotent and may be run without `--catalog-only` when introducing supported new source literals. Review its diff. The translation build needs the configured provider only for missing translations; it preserves canonical edits. Runtime rendering needs no translation key. The isolated browser runner creates its own synthetic database and refuses arbitrary script paths. Windows browser output is decoded explicitly as UTF-8 so Arabic error messages do not crash the test harness.

Language is fixed for each loaded page. A language change in another tab takes effect on reload, so it cannot change the wording or direction of an assessment already in progress.
