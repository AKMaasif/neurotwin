# NeuroTwin

A brain health support prototype connecting older adults, families and clinicians. It includes a mobile-friendly companion, a clinical dashboard and a document intelligence layer.

**Synthetic data only.** This is a research prototype, not a diagnostic tool or a production clinical service.

## Features

- Accessible patient interface with large text, daily support tasks and voice/text navigation.
- One-step activity coaching, confirmed changes, family acceptance status and opt-in companion memory.
- Family help requests, clinician review and versioned care plans requiring explicit approval.
- Private patient–family–clinician text and voice conversations with explicit opening acknowledgements and safe send retries.
- Time-zone-aware routines, quiet hours, snoozing, consented family follow-up and offline response reconciliation.
- PDF, Word, Excel, CSV, text and image intake with background processing, local OCR and source references.
- Keyword search, optional semantic retrieval and separately labelled AI visual descriptions.
- Patient-scoped permissions, sessions, CSRF protection, audit events and stale-source checks.
- A research state-space estimator with illustrative parameters; it is not a trained Alzheimer's prediction model.

The frontend uses plain JavaScript and CSS served by FastAPI. SQLAlchemy supports SQLite for local setup and PostgreSQL for development testing. Cloud adapters use Gemini and Meta Muse; keys remain on the server.

## Run locally

Prerequisites: Python 3.11+ and [uv](https://docs.astral.sh/uv/). Node.js 20+ is needed only for frontend formatting and browser checks. LibreOffice is optional for legacy `.doc` conversion; install it locally or set `DOCUMENT_SOFFICE` in `.env`.

```sh
uv sync --frozen
uv run python -m app.bootstrap
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8140
```

In another terminal, start the document worker:

```sh
uv run python -m app.document_jobs
```

Open the [mobile app](http://127.0.0.1:8140/mobile/), [clinical dashboard](http://127.0.0.1:8140/dashboard/) or [API docs](http://127.0.0.1:8140/docs).

Bootstrap creates an ignored `.env` with a generated `DEMO_PASSWORD`. Local accounts are `participant`, `family`, `clinician` and `other`. Use separate browser profiles for independent roles. SQLite is the default; set `DATABASE_URL` before applying migrations to use PostgreSQL. `scripts/local_postgres.py` optionally provisions a separate loopback-only development cluster when PostgreSQL tools are available.

AI is disabled by default. To enable it, set `GEMINI_API_KEY`, `META_API_KEY` and `AI_ENABLED=true` in `.env`, then restart the API. Available model names and provider URLs are configurable in `.env.example`. Cloud actions require synthetic workspaces. Voice recording needs browser microphone permission. Run `uv run python -m app.worker` in a separate terminal for routine scheduling and in-app notification projection. It does not send SMS or background push notifications.

## Checks

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run alembic check
npm ci
npm run format:check
npx playwright install chromium
npm run test:browser
```

To also test PostgreSQL, configure a development database with permission to create temporary schemas, set `TEST_POSTGRES=1`, then run pytest. Tests use disposable schemas, not the application's existing records. On PowerShell, set the flag with `$env:TEST_POSTGRES='1'`.

With the API and document worker running, check document ingestion using:

```sh
uv run python -m scripts.generate_document_fixtures
npm run test:documents
uv run python -m scripts.retrieval_benchmark
```

Browser checks create fictional records in the local workspace. Screenshots and test output stay in ignored `test-results/`. The source browser check and provider smoke scripts make paid synthetic inference calls; run them deliberately after configuring keys. `PLAYWRIGHT_EXECUTABLE_PATH` can point browser checks at an existing Chromium executable.

Companion memory is off by default. Participants can remember preferences and up to 6 text exchanges for 7 days, separately permit AI context sharing, or forget them. Expired entries are purged on the next memory access. Memory is not exposed to family or clinician accounts. Activity coaching reads the current approved plan; saved task/setting changes require confirmation. Recording stops on navigation or interruption, and transcripts require Send before execution. Finished companion recordings go to the configured speech provider; the app does not retain audio from those companion recordings. Spoken replies use the browser/device speech service. Background push delivery remains unfinished; the routines below provide server scheduling, in-app reminders and permission-based device alerts while the app is visible.

```sh
uv run python -m scripts.companion_benchmark
node scripts/companion_browser_check.cjs
```

The companion browser check uses a synthetic microphone and mocked ASR/speech output to test recording, cancellation and confirmation behavior; it does not measure speech recognition accuracy. Provider smoke checks are separate paid calls.

## Routines and reminders

Clinicians propose daily routines from approved activities in Dashboard > Daily routines. Participants confirm them in My Plan > Daily routines, choose weekdays and date ranges, adjust quiet hours and optionally authorize a family contact to follow up after a grace period. Participants can also schedule an approved activity themselves. Automatic family follow-up is off by default.

Keep `uv run python -m app.worker` running. It retries transient database errors without marking a delivery successful. It creates one dated occurrence per routine and local date, using the selected IANA time zone. Ambiguous clock times use the earlier occurrence; nonexistent times shift to the first valid minute. Scheduler recovery catches up at most seven dates. Activities older than 24 hours expire as unconfirmed, never automatically missed. Pauses, changed plans and revoked grants cancel pending reminders.

Done, snooze and explicit help requests are participant reports. A reminder acknowledgement does not complete the activity or accept responsibility for helping. Family follow-up uses the existing help-request acceptance flow. Three snoozes per occurrence are allowed, with a 15-minute default; quiet hours postpone automatic reminders and follow-up.

On supported secure browser contexts, Settings > Device notifications requests permission for generic alerts while the app is open and visible. The service worker contains no offline app cache or push subscription. A browser-requested alert is not proof it was displayed or read. Denied/unsupported notifications leave in-app reminders available. Notification text omits patient names and activity details.

An already-open app can queue responses in IndexedDB when connectivity fails. Packets contain IDs and action/version metadata, not document or activity text. They are labelled unconfirmed until the server acknowledges them. Reconnect retries use idempotent commands; changed routines or expired access require review and never overwrite current server state. Queued actions expire after 24 hours. The server also rejects late responses if the scheduler was unavailable. Sign-out warns before discarding unsent responses and closes device alerts. Production browser-storage protections and real-device delivery testing are still required.

```sh
node scripts/routine_browser_check.cjs
```

This synthetic browser test exercises real IndexedDB/network interruption and service-worker registration. Notification display is a test double because the headless environment denies native notification display. Actual device notification visibility is not validated. Core and companion browser checks accept `NEUROTWIN_BASE_URL` for isolated local test instances.

## Weekly reports

Open **Activity report** in the clinical dashboard, or **Weekly summary** from mobile Home. Choose a week ending and reporting timezone. Seven-day counts and four-week comparisons use recorded activity denominators, not an inferred adherence or cognitive-health score. Routine activities use their scheduled date; one-time activities use their creation date. Late responses can revise a live historical week. Dates without records do not establish missed activities, and historical expected schedules are unavailable.

Clinicians can save frozen clinical or recipient-specific family snapshots. Family snapshots exclude clinical documents, research measurements, review notes and companion memory; only approved reports are visible to the named, currently authorized relative. Scope reductions hide incompatible saved reports. Source changes block approval of an old draft. AI fact selection is optional, synthetic-only and restricted to exact computed facts; unsupported output is rejected. No report automatically changes a care plan. Snapshot approvals are in-app clinician decisions, not external signatures or dispatch.

Reporting fails explicitly above 10,000 source records, occurrences or matching events. Timelines show at most 200 actions with truncation disclosed; saved-report lists show 12 recent snapshots. Larger deployments need partitioned reporting and pagination.

```sh
node scripts/report_browser_check.cjs
```

The report browser check supports `NEUROTWIN_BASE_URL`, uses synthetic accounts, and simulates an AI outage without a paid inference call. It verifies clinical/family views, approval sharing, stale-source rejection and empty weeks. Backend tests additionally check exact-fact AI validation and permission changes during generation on SQLite and PostgreSQL.

## Care-circle messages

Open **Care messages** in the clinical dashboard, or **Messages** from mobile Home or Support. Each conversation is bound to one patient and its two participants; clinician assignment does not expose other people’s private conversations. Both people need an active patient grant with the `messages` scope. Access is checked again for history, sends, retries and opening acknowledgements, including requests that reuse an earlier command ID. Removing either grant or messaging scope blocks that conversation.

Text messages contain up to 2,000 characters and are saved directly in the app. Voice notes use the same conversation permissions and acknowledgements, with the additional bounds below. They are excluded from ordinary workspaces, weekly reports and AI context. Contacts show the number not yet acknowledged as opened. Fetching a conversation does not create a receipt: the recipient explicitly acknowledges the displayed incoming messages. “Opened in app” is not proof of comprehension, treatment adherence or external delivery. Message content is excluded from audit metadata.

The client shows 40 messages per page, with Older and Latest controls, literal search and media-type filters. Authenticated SSE reconciles the canonical conversation with polling recovery, avoids replacing text during typing/playback, and retains drafts only in session memory. A lost send response keeps the exact text and command ID for retry; the server prevents duplicate messages. Drafts and pending requests are cleared on sign-out, access expiry or a new login. Reloading or closing the app can lose unsent text, and the browser is asked to warn first. No persistent offline/background delivery queue is provided. The companion can open Messages or Weekly summary; it cannot send messages or acknowledge them automatically.

This is an unmonitored, synthetic in-app channel. It does not send SMS, email, push or calls, and messages do not modify approved care plans. Production identity, retention and encrypted storage work described below remain necessary.

```sh
node scripts/message_browser_check.cjs
```

The browser check accepts `NEUROTWIN_BASE_URL`, uses separate synthetic role sessions, and tests direct-message privacy, explicit acknowledgements, escaped content, a genuinely committed message with a lost HTTP response, duplicate-free retry, draft navigation and sign-out isolation. Backend tests cover pagination, patient and organization boundaries, scope revocation, atomic acknowledgements and companion navigation on SQLite and PostgreSQL.

## Voice notes

In a conversation, choose **Record voice note**, then **Finish recording**. You can play the local preview, add optional text and explicitly choose **Send voice note**, or discard it. The recorder finishes automatically after 20 seconds. Recording permission and unfinished capture are cancelled on navigation or when the page is hidden; a late permission result stops its tracks without recording or sending. Preview drafts remain only in session memory. Changing contact asks before discarding an unsent note, and sign-out clears local audio and object URLs.

Sent clips are stored as validated mono 16-bit PCM WAV at 16 or 24 kHz, with a 30-second server limit and a 2 MB file limit. Multipart requests are bounded before spooling, and uploaded metadata/trailing chunks are discarded when canonical PCM is rebuilt. Audio and message metadata are saved in one transaction. Stable message IDs and content hashes make retries safe after a lost upload response. An unconfirmed upload keeps the original audio and caption for retry. Reloading or closing the browser can lose that local copy, so check the conversation before recording the same message again.

Playback requires the current grants of both conversation participants and a matching patient/participant pair. There are no public audio URLs. Fetches use `no-store` and do not mark a message opened; opening acknowledgement remains explicit. Playing or recording a note does not change the care plan, invoke an AI/speech provider or add audio to companion memory or reports. Voice-note upload and playback are limited to synthetic development workspaces. Production encryption, retention and device testing remain unfinished.

```sh
node scripts/voice_note_browser_check.cjs
```

The browser check accepts `NEUROTWIN_BASE_URL` and uses a generated tone as the microphone source, actual MediaRecorder/PCM conversion and muted native playback. It tests preview-before-upload, private playback, a committed upload with a lost response, idempotent retry, cancellation, late permission and text fallback. Permission denial is injected; real-device microphone quality and speech intelligibility are not validated.

## Multimedia care messages

Both clients share private text/voice/image/video/audio/PDF/document conversations, explicit previews and sending, per-file progress and resumable chunks, reply/search/withdrawal, custom waveform playback, distinct delivery/open/playback acknowledgements and authenticated realtime reconciliation. Media bytes are outside the database in a private filesystem store; existing voice URLs remain compatible and legacy clips have a verified-copy migration.

See [the architecture, API, storage policy, exact file list and test report](docs/messaging.md) before deployment. Verification: 301 full-regression passes plus 10 additional recovery passes, one expected SQLite RLS skip, and 50 browser scenarios. Physical Android/iOS, live antivirus, production identity, OS parser sandbox, encryption at rest and organizational privacy review remain unverified. Synthetic unscanned development is explicitly labelled; production uploads fail closed without a configured working scanner. This is not E2EE or production certification.

```sh
uv run alembic upgrade head
uv run python -m app.media_maintenance migrate-legacy
uv run python -m app.media_maintenance cleanup
uv run python -m app.worker
uv run python -m scripts.chat_fixtures
node scripts/multimedia_browser_check.cjs
```

Legacy migration copies at most 25 clips per invocation; repeat until `processed: 0`. Run browser/security checks only against an isolated synthetic test database. The security browser script intentionally revokes a test grant and has an additional explicit environment guard documented in the architecture report.

## Project layout

- `app/`: API, authentication, database models, AI adapters, document processing and workers.
- `web/mobile/`, `web/dashboard/`: reference-style clients.
- `migrations/`: versioned database schema.
- `tests/`, `scripts/`: automated tests, development setup and smoke checks.
- `.env.example`: configuration template; `uv.lock` and `package-lock.json` pin dependencies.

## Current limits

Uploads are limited to 8 files per batch, 10 MB per file and 50 active documents per patient. Document processing preserves page, paragraph, table, worksheet or cell references where available. OCR and native table extraction can miss or misorder content; warnings and partial results require original-source review. Legacy XLS visuals, handwriting, Arabic and complex layouts are not fully validated. Semantic indexing is bounded to 40 chunks per document; keyword retrieval is capped at 4,000 chunks per search.

Source facts require individual human verification. AI visual descriptions are interpretations and are excluded from clinical fact extraction. Reprocessing or removing a source invalidates dependent plans and indexes.

Real patient data, production identity/RLS, isolated malware scanning, encrypted storage lifecycle/restore, distributed infrastructure and clinical validation remain unfinished. EHR connectivity, video calls, external reminder delivery and emergency dispatch are not connected. Keep this development server on loopback and do not enter real patient records.


## Current engineering milestone

Authorized patient switching, clinician plan/case review and participant privacy controls are documented in [workspace and privacy verification](docs/workspaces-and-privacy.md). Multiple authorized patients require a deliberate choice; switching clears private drafts, microphone resources and stale responses. Settings supports confirmed access removal and an explicit export of retained companion memory; this is not a complete medical-record export/deletion process.

[Per-role contract evaluation](docs/agent-contract-evaluation.md) provides reproducible software checks for all eight registry roles. Scores are contract pass rates, not clinical accuracy. The [development ledger](DEVELOPMENT_PLAN.md) distinguishes locally verified, planned and externally gated work.

[Research dataset preflight](docs/research-data-readiness.md) checks provenance references, split leakage, missing values and protocol consistency offline. Its synthetic example demonstrates the data contract only; formal assessments, model training and clinical validation remain gated.
