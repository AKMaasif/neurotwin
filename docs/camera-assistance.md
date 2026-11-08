# Deliberate camera assistance — synthetic samples

Open **Mobile → Companion → Camera assistance · synthetic samples only**. The client supports choosing an image or requesting the device's native camera chooser through the file-input capture hint. Actual chooser behavior depends on the browser/device. There is no continuous stream or background camera. Images and displayed results clear on page refresh, navigation, workspace change or explicit Clear.

## Implemented flow

1. Read current provider availability and versioned consent text from the authorized server endpoint.
2. Choose a still JPEG/PNG/WebP sample and preview locally. Selection/preview does not upload it. Only synthetic samples without people, personal information or medical material are permitted by the stated consent; the app does not claim to automatically verify that declaration.
3. Check explicit consent, then select Send. Each completed or failed send resets the choice so resending requires another explicit consent. No automatic retry is performed.
4. The server validates and reconstructs the image, then sends a bounded request to the configured Gemini model using the existing gateway. Model output is restricted to chair, table, cup, door, book, phone, clock and keys, with approximate left/center/right image regions. At most three guesses are accepted. An unclear image must have no guesses.
5. The server renders local tentative-language templates from those categories. Free-form model text, directions, medical content, identities and tool commands are not returned. Schema violations, inconsistent output and provider failures produce an unavailable state, never a fabricated recognition. Restricting output vocabulary does not guarantee correct recognition or detect all sensitive input.
6. Clear aborts local waiting, discards the preview/result and rejects late responses. It cannot recall a request already transmitted to the provider; the UI states that limitation.

## API and boundaries

- `GET /api/patients/{pid}/camera/options`: consent text/version, byte limit, configured provider/model and readiness flag. Readiness means configuration exists, not guaranteed service health.
- `POST /api/patients/{pid}/camera/check`: raw image bytes, matching image Content-Type and `X-Camera-Consent: synthetic-camera-1`, in addition to normal cookie, CSRF and expected-actor checks. Raw body input avoids multipart temporary-file spooling.
- Only the participant role with assessment scope and an active grant to a synthetic patient can use these endpoints. Family/clinician roles, other patients and real patient records are denied. Authorization is checked before processing and after the asynchronous provider call. An in-flight revocation prevents the result from being returned, but cannot recall transmitted provider data.
- Limit: 1 MB at the request stream and decoder boundaries, at least 160 pixels per side, at most 4 megapixels, one still frame, matching actual format. Images are oriented, reduced to at most 1536 pixels per side and reconstructed as fresh JPEG pixels to discard source EXIF/text/ICC metadata. Decoding runs in a thread pool; this is not an OS-level parser sandbox.
- Configuration: `GEMINI_CAMERA_MODEL` defaults to `gemini-2.5-flash`; existing `AI_ENABLED`, API key and gateway budgets/timeouts apply. Keys stay server-side.
- The app creates no image file, care message, medical observation, model record, companion-memory entry or stored scene result. It retains only audit metadata (status, count, provider/model and consent version); failed QA/provider attempts have a generic rejection audit. Provider retention follows provider terms and is explicitly distinguished from app retention. The native camera/browser may manage its own original file outside this application's storage.

This is a bounded object-label demo, not the earlier repository's real-time world-analysis system, a navigation aid, hazard detector, emotion/cognitive assessment, medication identifier or clinical decision system. No segmentation overlay, distances, safety guarantees or automatic action is implied.

## Verification

Tests were written first and reproduced the missing route. `TEST_POSTGRES=1 uv run pytest tests/test_camera_assistance.py -q --junitxml=test-results/camera-tests.xml` passed **28 checks** across SQLite/PostgreSQL with model test doubles. They cover explicit consent, role/patient/real-data boundaries, MIME and byte/pixel limits, streamed oversize, corrupted input, metadata removal, no domain-result retention, output category/schema/uncertainty checks, provider failure and in-flight access revocation.

The related workflow/PDF-intake/gateway regression partition passed **49 checks** (`test-results/camera-integration-regression.xml`). Formatting, Ruff and whitespace checks pass.

`camera_browser_check` passed **10 scenarios**: honest provider-unavailable state; local preview/clear without upload; separate explicit consent/send; tentative output; provider failure and retry control; uncertain output; unsupported input; in-flight clear; reflow/enlarged text; navigation cleanup and family restrictions. Browser routes use explicit test doubles and providers are disabled in isolated fixtures. A pre-existing Companion illustration overflow at 320px with doubled root text was exposed and fixed with one max-width rule. The file chooser preserves the selected filename while the preview is available. Existing companion, core, research-session and care-page flows were rerun. Reports/screenshots are in ignored `test-results/camera-assistance/` and were visually inspected.

One separate live smoke request on the local API used a generated 320×240 synthetic cup drawing, no people/personal/medical data. The configured Gemini 2.5 Flash endpoint returned HTTP 200 and a schema-valid tentative result. `test-results/camera-assistance/live-smoke.json` records only connectivity metadata. This single transport/schema check is not recognition accuracy, clinical or intended-user validation. There were no live provider calls in the automated regression suites.

Physical Android/iOS camera capture, assistive technology, intended-user usability, representative recognition/adversarial-image evaluation, reviewed multilingual phrasing and production parser/process isolation remain unverified. No production deployment or GitHub push is part of this milestone.

## Primary references

The implementation uses the existing image-capable gateway, consistent with [Gemini image-understanding inputs](https://ai.google.dev/gemini-api/docs/image-understanding) and the [official Gemini 2.5 Flash model reference](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/2-5-flash). Decoder limits complement Pillow's documented [lazy loading and decompression-bomb handling](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open); no dependency upgrade was required.
