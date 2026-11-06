# Multimedia care messaging

## Audit and implementation plan

The existing stack is FastAPI, SQLAlchemy/PostgreSQL (SQLite in tests), cookie sessions with CSRF, and plain JavaScript shared by `/mobile/` and `/dashboard/`. No external object-storage or realtime provider exists. `CareMessage` holds text/voice metadata; `CareAudio` holds legacy WAV bytes. The existing voice workflow records, previews and explicitly sends, canonicalizes PCM, checks both grants on playback and uses sender command IDs for safe retry. Messages are excluded from clinical reports and companion memory. Existing baseline: 245 software tests and 36 browser scenarios, using synthetic microphone input rather than real-device validation.

Verified gaps: binary voice storage in the database, five-second polling, native audio controls, no generic attachments/upload sessions, no canonical conversation/membership records, no distinct delivery/playback receipts, no replies/search/withdrawal, and a large composer. These are extensions to the current stack, not a new backend.

Implementation order: additive schema and compatibility adapters; private filesystem object adapter and bounded media processor; resumable uploads and atomic sends; durable event log and authenticated SSE; receipts, replies/search/withdrawal; responsive composer, previews and custom audio controls; integration/browser/regression tests. Preserve legacy APIs and stored audio. The pre-change source backup is `data/backups/pre-multimedia-code.zip` (ignored). Back up the database before applying the additive migration; do not run downgrade against real records. Legacy binary rows remain available while an idempotent copy command moves their contents into private objects.

## Design decisions

Direct conversations remain private to their two participants. A deterministic UUID derives from the patient and sorted participant IDs; stored participant rows reference grants. No implicit care-team groups are introduced. Active grants/scopes, organization, role and session expiry are checked server-side; old records remain retained but become inaccessible. The existing Grant model has no expiry timestamp: relationship lifecycle services must deactivate ended relationships. A changed clinician creates a different pair/conversation. A restored grant restores access under the same direct-pair policy. Archiving affects new sends, not clinical retention.

New media belongs in a private local object store below ignored `data/private-messages`, outside both static roots. Database rows contain opaque keys and metadata, not Base64/large binaries. This is the local adapter for the current deployment, not a public bucket or a new vendor. Backend-authenticated streaming/downloads recheck grants on every request, avoiding bearer URLs that outlive revocation. No permanent public URLs are generated. A production storage adapter must provide shared persistent storage, restrictive OS permissions, encryption at rest and backups.

Uploads are explicit-send operations, resumable by verified byte offset. One stable key identifies the logical message; each attachment has a stable upload/attachment ID. Received chunks are fsynced before acknowledging offsets. Recovery truncates uncommitted bytes to the database offset. Validation runs in a separate bounded process, using Pillow/PDF raster reconstruction, restricted Office/text reconstruction and PyAV/FFmpeg parsing. Antivirus status is explicit; a missing scanner is never called a clean scan. Production must fail closed without the configured scanner. Only synthetic development can use the documented structurally validated, unscanned mode. Rejected/quarantined media never appears as a recipient-ready attachment.

The database commits ready attachment references, a canonical message and a minimal sequenced event together. SSE reads this durable outbox; clients refetch canonical history and deduplicate IDs. Session and relationship checks repeat while connected. Client receipt acknowledgement means synchronized to a recipient device; explicit Open remains distinct from playback start/end. Playback completion means an ended event from that recipient client, not evidence of comprehension or medication administration.

Drafts and media remain in session memory. Refresh recovery uses server upload sessions and command lookup; users reselect matching files to resume unconfirmed bytes. No recordings are placed in localStorage/IndexedDB, no background upload or automatic sending of an unapproved recording. Network failures retain stable keys. Cancellation discards only uncommitted data; a committed message remains in history even if its HTTP response was lost.

## Boundaries and deployment review

Messaging remains an unmonitored support channel. It does not change care plans or send SMS/email/push/calls. There is no server-blind E2EE: the backend and its authorized operators can process message content. No custom encryption is introduced. HTTPS, managed encryption at rest, production identity, OS/container isolation, retention duration, legal applicability, incident response and vendor review must be assessed before real patient deployment. Original uncommitted/quarantined objects expire; committed/withdrawn clinical-context objects are retained until an approved retention policy exists. Withdrawal hides recipient content without destroying audit evidence.

Real Android Chrome/iOS Safari microphone, camera and playback checks require physical devices and are reported as unverified unless actually performed. Desktop browser automation and mobile viewport emulation do not constitute physical-device validation. PostgreSQL table-owner/service-role bypass of RLS must be distinguished from a restricted runtime-role deployment.

## Schema, constraints and migration

| Table | Purpose and constraints |
| --- | --- |
| `care_conversations` | Canonical patient/direct pair; unique `(patient_id, first_user, second_user)`; ordered sequence; active/archived status. |
| `care_participants` | Unique `(conversation_id, user_id)`; references current grant; notifications default off. |
| `care_messages` | Existing rows retained. Nullable conversation/reply/withdrawal fields are additive. Unique `(sender_id, command_id)`; pair and timeline indexes; explicit recipient-open timestamp retained. |
| `care_attachments` | One row serves as upload session and eventual attachment; unique `(uploader_id, client_attachment_id)`; original checksum, byte offset, expiry, verified metadata and private object keys. Nullable `message_id` until commit. |
| `care_receipts` | Unique `(message_id, recipient_id)`; delivery, playback-start and playback-end timestamps. |
| `care_events` | Transactional append-only outbox; unique `(conversation_id, sequence)`; minimal message ID/type payload. |
| `care_audio` | Legacy compatibility table. New rows are empty markers; old bytes remain readable until verified copy migration. |

Additive migrations: `20261106_voice_notes.py` and `cd1f07616c71_multimedia_care_conversations_uploads_.py`. The latter backfills canonical identities and membership rows, adds named FKs/indexes, installs PostgreSQL policies and guards destructive downgrade when media exists. It has been applied to the local PostgreSQL database; `uv run alembic check` reports no missing operations. Two existing voice clips were copied into private objects, verified by SHA-256, then their database bytes were cleared. A second migration-copy invocation processed zero rows, demonstrating idempotence.

Backups made before this change are ignored local artifacts: `data/backups/pre-multimedia-code.zip` and `data/backups/pre-multimedia-db.dump`. Restore the database, code and corresponding object-store snapshot together into an isolated instance before switching traffic. Do not downgrade a populated media schema. Object storage is outside the database transaction: committed references are transactional, while abandoned filesystem writes are recovered/truncated or swept after expiry. This is deliberately not a claim of an atomic filesystem/database commit.

## States and the sender-to-recipient path

```text
Local selection/recording -> Preview -> explicit Send
  -> reserve upload ID -> uploading(offset) -> verifying(leased subprocess)
  -> ready -> atomic message + attachments + event commit -> committed
                    \-> rejected / quarantined (never recipient-ready)
Uncommitted upload -> cancelled or expired -> object cleanup
Committed message -> withdrawn tombstone; evidence retained

Client send state: preview -> preparing -> uploading -> verifying -> sending -> saved
Failures: paused / waiting for network / failed / rejected -> explicit resume or cancel
Voice: recording <-> paused -> processing -> preview -> sending -> unconfirmed/retry or saved
```

1. The sender chooses a contact with an active grant and records/selects local media. No upload is made during preview.
2. Send captures the caption/reply and stable UUID command. Files reserve stable per-file IDs with source size/SHA-256; 1 MB chunks acknowledge durable offsets.
3. The worker validates source integrity and actual format, scans when configured, rebuilds a safe derivative, measures audio duration/waveform and creates thumbnails. A lease/nonce prevents stale workers from publishing or deleting a newer result. Two processing slots per API process and timeouts bound concurrent parsing.
4. The server rechecks both grants, ownership, patient/pair, readiness, command IDs and derivative checksum, then commits the message, every attachment reference and event in one database transaction. Failed validation rolls back the entire send.
5. The recipient's authenticated SSE connection receives an ID/type/sequence notice. It refetches canonical history; the client acknowledges synchronized incoming IDs as delivered. Open remains an explicit separate action; playback receipts arise from actual player events.
6. Last-event cursors, canonical refetch and ID uniqueness prevent duplicate/out-of-order notices from duplicating bubbles. The server rechecks the session and grants approximately every second and closes revoked streams. Browser account changes clear sensitive state through BroadcastChannel; cookie replacement also invalidates the previous server session.

Patient-row locking serializes commands for that patient in PostgreSQL. Unique constraints are the final duplicate barrier. This is suitable for the current bounded deployment, but patient-level serialization and per-subscriber database polling need load testing and a shared event transport before large-scale rollout. SQLite is a single-instance development/test option; PostgreSQL is required for production.

## API and event contracts

All routes below are relative to `/api/patients/{pid}/messages`. Cookies authenticate requests; mutations require `X-CSRF-Token`. Shared clients send `X-Expected-Actor` to reject stale identity after cookie changes. Raw media requests still repeat server authorization. No object key or public listing endpoint is exposed.

| Method/path | Contract |
| --- | --- |
| `GET /inbox` | Authorized contacts with role, last preview/time, not-opened count and revision. |
| `GET /threads/{peer}` | Canonical messages; `limit` 1–100 (client 40), keyset `before`, literal `q` ≤120 chars, and `kind=text/voice/audio/image/video/document`. |
| `POST /threads/{peer}` | `{command_id, body, attachment_ids: [], reply_to_id: null}`. Text ≤2,000 chars; text or ready attachments required. Same key/same payload returns the existing message; conflicting reuse returns 409. |
| `GET /threads/{peer}/command/{key}` | Reconcile an uncertain send without creating another message. |
| `POST /threads/{peer}/voice` | Compatible multipart voice endpoint: `command_id`, optional `caption`, either a verified voice `upload_id` or legacy PCM WAV file. |
| `POST /threads/{peer}/opened` | Existing explicit-open acknowledgement for displayed incoming IDs. |
| `GET /media-policy` | Current sizes/counts and scanner configuration status; configuration does not prove scanner availability. |
| `POST /threads/{peer}/uploads` | `{client_message_id,client_attachment_id,filename,content_type,size,sha256,kind}`; returns ID, authoritative offset, status, expiry and chunk size. |
| `GET /uploads/{id}` | Uploader-only current offset/status and safe metadata. |
| `PATCH /uploads/{id}` | Raw chunk with `Upload-Offset`; offset mismatch 409; oversized chunk 413. Not a full TUS implementation. |
| `POST /uploads/{id}/complete` | Lease/verify/process existing bytes; idempotent for ready/committed/blocked states. `?retry_scan=true` permits retry after scanner-required/unavailable quarantine only when a scanner is configured. Malware blocks are not unblocked this way. |
| `DELETE /uploads/{id}` | Cancels uncommitted upload; committed sends require withdrawal. |
| `GET /threads/{peer}/uploads` | Current uploader's unexpired unfinished uploads for refresh recovery. |
| `GET /uploads/{id}/preview` | Uploader-only verified, uncommitted derivative; no recipient access and no send side effect. |
| `GET /attachments/{id}/content` | Authorized committed derivative; optional `thumbnail=true` or `download=true`; supports byte ranges. |
| `POST /threads/{peer}/receipts` | `{message_ids,event}` where event is `delivered`, `playback_started`, or `playback_completed`; recipient-only and idempotent; end requires start. |
| `POST /threads/{peer}/messages/{id}/withdraw` | Author-only within 24 hours. Hides body/media from normal retrieval while retaining evidence. |
| `GET /threads/{peer}/events` | SSE with `after`/`Last-Event-ID`; `care`, `reset` and `revoked` events; no message content in events. |

SSE example: `id: 12`, `event: care`, `data: {"sequence":12,"type":"message.created","message_id":"opaque-id","conversation_id":"opaque-id"}`. Heartbeats do not imply that another person is online. A 100-event batch is replayed by increasing sequence. Sequence rollback sends reset and refetch. The browser defers rendering while someone is typing, recording, or playing media, avoiding interrupted input/playback. Failed receipt acknowledgements remain in a bounded session-only retry queue.

## File policy and processing

These are NeuroTwin development resource limits, not borrowed WhatsApp limits. MB here means 1,048,576 bytes.

| Category | Allowed extensions | Default limit | Processing |
| --- | --- | --- | --- |
| Images | JPG/JPEG, PNG, WEBP | 8 MB; 16 MP | Decode, validate matching actual format, EXIF transpose, strip metadata and encode JPEG/thumbnail. |
| Video | MP4, WEBM | 32 MB; 120 s; dimensions ≤1920; ≤7200 video frames | Validate/decode supported streams, remux without source metadata, generate thumbnail. H.264/VP8/VP9 and AAC/Opus/Vorbis allowlist; actual playback varies by device codec support. |
| Audio file | WAV, MP3, M4A, OGG, audio WEBM | 12 MB; 120 s | Actual container decode; mono 16-bit/24 kHz WAV derivative with measured RMS waveform. |
| Recorded voice | WAV, WEBM, OGG, M4A | 2 MB; client 20 s active time, server ≤30 s | Actual recorder MIME retained; normalize to measured WAV. Compatible legacy PCM uploads remain supported. |
| Documents | PDF, DOCX, XLSX, TXT, CSV | 10 MB | Reconstruct restricted derivatives; no active HTML/SVG, executable content, macro documents or archive attachments. |

Maximum six attachments and 48 MB combined source/processed bytes per message; 256 MB reserved actor quota and 100 uploads/actor/day. Limits are exposed through the policy API and configured using `MEDIA_*` in `.env.example`. Processing may expand media, and an oversized derivative is rejected before commit. Quotas conservatively count committed/withdrawn evidence and active uploads, not just current previews.

PDFs are reconstructed as raster pages (≤20 pages, 4 MP/page, 40 MP total), without active annotations. DOCX/XLSX use bounded ZIP expansion and safe XML; reject macros, embeddings, external relationships and spreadsheet formulas; reconstruct text/tables or values. TXT/CSV require UTF-8 without unsafe controls and neutralize spreadsheet formula prefixes. Reconstruction can change layout, remove signatures/formulas and reduce accessibility/searchable PDF text; the interface labels these as safety-processed copies. The protected original is retained for reviewed operational/retention processes, not exposed as an unchecked download. Messaging is not a replacement for formally signed clinical-document ingestion.

The EICAR signature rejection in structural processing is a known-test defense, not a full antivirus engine. Configure `MEDIA_SCAN_EXECUTABLE` as an actual ClamAV-compatible scanner executable, kept current. Scanner code 0 allows further structural checks, 1 quarantines malware, any other result/unavailability quarantines. Development permits synthetic structurally validated files only when `MEDIA_ALLOW_UNSCANNED_DEVELOPMENT=true`; production cannot use that exception. No real antivirus service is installed in the verified local environment. Scan-adapter retry tests use a clearly scoped test double and do not establish antivirus efficacy.

## Storage, access, encryption and retention

There is no new storage bucket/vendor. The private filesystem root defaults to `data/private-messages`, with keys shaped as `{conversation-uuid}/{attachment-uuid}/original` and `.../ready-{processing-nonce}` plus `.thumb`. Legacy copies use `ready-legacy`. Source filenames never choose paths. Keys reject traversal, absolute paths and unsafe separators; the root must remain outside `web/`. Public static routes cannot retrieve these files.

Media uses authenticated proxy URLs, not signed bearer URLs. Thus there is no signed-URL TTL to configure or public URL to leak. Every fetch/download/range request validates current role, organization, patient and both grants. `no-store`, `nosniff` and safe filename disposition apply. In-progress downloads and bytes already downloaded cannot be clawed back; revocation prevents later requests and clears active UI/subscriptions, not external copies. Metadata does not grant access to the private original.

PostgreSQL policies in `app/care_policies.py` independently scope SELECT/INSERT/UPDATE/DELETE on all seven care tables, and a trigger rejects content mutation/unauthorized receipt or withdrawal changes. Normal DELETE is denied; events are append-only. A real non-owner `NOBYPASSRLS` test role verifies private reads, allowed/forged inserts, receipt updates, content-update denial, delete denial and revocation. API checks also work in SQLite. The local database owner still bypasses RLS: production must separate migration/maintenance credentials from a restricted runtime role, retain identity/grant-table privileges only server-side, and never expose SQL credentials to clients. Audit rows follow the existing append-only API convention; the database owner can still alter audit rows, so this is not cryptographic tamper evidence. Configure runtime audit INSERT/SELECT only and external immutable audit export before deployment.

The server sees plaintext for validation, search and CDR. Operators with authorized storage/database access can read it. Production API rejects non-HTTPS scheme and adds HSTS; cookies are HttpOnly, SameSite strict and Secure in production. Set `ALLOWED_HOSTS` to the real deployment host, terminate TLS at a trusted proxy, and accept forwarded scheme headers only from that proxy. The loopback development server remains HTTP. This change does not provision a certificate, encrypted volume, KMS or database encryption. Managed encryption-at-rest and encrypted coordinated backups/restore must be configured and verified by deployment operations. No custom cryptography or E2EE claim.

General care access logs redact identifiers/search paths. Audit events contain IDs, safe result codes and provenance, not full message/caption/media. AI providers are not called for care media, and messages do not flow into weekly reports, companion memory, medication instructions or approved-plan mutations. External notifications/calls remain disconnected.

Uncommitted uploads expire after 24 hours. `uv run python -m app.worker` sweeps every five minutes; `uv run python -m app.media_maintenance cleanup` also runs manually. A sweep processes at most 100 expired rows and removes old unreferenced files under the private root. Committed and withdrawn originals/derivatives are never auto-deleted. Set a reviewed clinical retention/deletion/export policy before real data; indefinite development retention is not a production policy. `uv run python -m app.media_maintenance migrate-legacy` copies at most 25 legacy rows per invocation; repeat until processed=0. Do not allow maintenance credentials into the frontend.

## Browser behavior and deployment limits

Shared plain-JS components render one canonical conversation in both clients. Sender bubbles, date/not-opened separators, contact previews, replies, literal search/type filters, copy, author withdrawal, safe document cards and image/video viewers remain within the existing visual style. Custom players use actual waveform samples and server duration, 1/1.5/2× speed, seek, loading/retry states and session-memory playback positions. No autoplay or fabricated presence. Microphone MIME feature detection, final `dataavailable`, pause/resume, track cleanup, permission/device errors and explicit preview/send remain implemented.

Refresh loses unsent local captions/replies and incomplete microphone bytes by design. Verified voice drafts can be recovered privately for preview and explicit Send. Generic files must be reselected and matched by original size/hash to resume existing offsets; no sensitive bytes are persisted in IndexedDB/localStorage. Incomplete microphone drafts cannot be recreated from bytes never uploaded: the user cancels that upload and records again. An already committed message remains visible/reconcilable even if the final HTTP response was lost. There is no background delivery, persistent offline outbox, push, typing presence, groups, EHR integration or calling service introduced here.

The parser is a separate timeout-bounded process with format/dimension/page/sample limits and two slots per API worker. It is not an OS/container sandbox, does not enforce an OS memory/network limit locally, and must run with low privileges, no network, resource limits and a restricted scratch volume in production. Synchronous upload verification is bounded for this deployment; distributed deployments require shared private storage, coordinated processing leases, distributed quotas and load testing. Disk ACLs, filesystem/database backup coordination and disaster-restore verification remain operational work.

## Exact changed files

Frontend:

- `web/dashboard/messages.js`, `messages.css`, `voice-notes.js`, `audio.js`, `chat-media.js`, `chat-view.js`, `chat.css`, `app.js`, `index.html`.
- `web/mobile/app.js`, `index.html`, `companion.js` (uses the shared PCM helper).

Backend/API:

- `app/messages.py`, `voice_notes.py`, `care_domain.py`, `care_realtime.py`.
- `app/media_uploads.py`, `media_store.py`, `media_processor.py`, `media_maintenance.py`.
- `app/care_policies.py`, `care_logging.py`, `db.py`, `security.py`, `upload_limits.py`, `config.py`, `main.py`, `worker.py`.
- `migrations/versions/20261106_voice_notes.py`, `migrations/versions/cd1f07616c71_multimedia_care_conversations_uploads_.py`.
- `.env.example`, `pyproject.toml`, `uv.lock`, `README.md`, this architecture document.

Tests/fixtures:

- `tests/conftest.py`, `test_voice_notes.py`, `test_multimedia.py`, `test_care_rls.py`, `test_media_recovery.py`.
- `scripts/chat_fixtures.py`, `voice_note_browser_check.cjs`, `multimedia_browser_check.cjs`, `messaging_security_browser_check.cjs`.
- `scripts/message_browser_check.cjs`: narrowed two exact-text locators to the timeline because matching contact previews are now present; assertions were retained.

## Test evidence — 7 November 2026

| Verification | Actual result |
| --- | --- |
| Full regression: `$env:TEST_POSTGRES='1'; uv run pytest -q --junitxml=test-results/software-tests.xml` | **301 passed, 1 skipped**, 650.10 s; no failures. This run collected before the additional recovery file was added. |
| Additional recovery/HTTPS/scanner-adapter tests: `uv run pytest tests/test_media_recovery.py -q --junitxml=test-results/media-recovery-tests.xml` with `TEST_POSTGRES=1` | **10 passed**, 15.46 s, on SQLite and PostgreSQL. |
| Earlier targeted care suite: `uv run pytest tests/test_care_rls.py tests/test_multimedia.py tests/test_messages.py tests/test_voice_notes.py -q` | **128 passed, 1 skipped**; overlap with full regression, not added to totals. |
| `node scripts/browser_check.cjs` | **8 scenarios passed**. |
| `node scripts/companion_browser_check.cjs` | **10 scenarios passed**. |
| `node scripts/message_browser_check.cjs` | **8 scenarios passed**; repeated after UI fixes. |
| `node scripts/voice_note_browser_check.cjs` | **10 scenarios passed**; repeated after UI fixes. |
| `node scripts/multimedia_browser_check.cjs` | **10 scenarios passed**. Real fixture uploads, 13 types plus clinician PDF; authorized cross-client retrieval, custom playback, receipts, reply/search/withdrawal, interrupted multi-chunk refresh/resume, duplicate/out-of-order event handling, capture pause/resume and viewport checks. |
| `node scripts/messaging_security_browser_check.cjs` | **4 scenarios passed**: inline video decode, verified voice recovery without auto-send, cookie-switch stream invalidation/stale-actor guard, grant-revocation stream/state cleanup. |
| `uv run ruff check app tests scripts`; `uv run ruff format --check app tests scripts` | Passed; 57 Python files already formatted. |
| `npm run format:check`; `git diff --check` | Passed. Git reports existing Windows line-ending normalization notices only. |
| `uv run alembic upgrade head`; `uv run alembic check` | Applied/current; no new upgrade operations detected. |
| Restarted main loopback server on 8140; authenticated role smoke checks | Health, both clients, shared assets and media policy available; both migrated voice clips remain retrievable as valid WAV. Isolated 8141 test API stopped. |

Combined distinct software cases: **311 passed, 1 expected skip** across the full and additional recovery runs. Browser evidence: **50 passed scenarios**, with zero browser script errors. The one skip is PostgreSQL RLS on the SQLite parameter; the real PostgreSQL restricted-role test passed. A pre-existing FastAPI/Starlette TestClient deprecation warning remains; no test assertions were removed. Generated reports and screenshots stay ignored under `test-results/`, rather than committing synthetic databases/media. Desktop/mobile layout screenshots were visually inspected; automated mobile emulation is not a real phone test.

Browser checks used the installed Chromium headless shell through `PLAYWRIGHT_EXECUTABLE_PATH` and `NEUROTWIN_BASE_URL=http://127.0.0.1:8141`, with AI disabled and a separate synthetic SQLite database/private root. The security script deliberately revokes that test database's family grant; it requires `NEUROTWIN_DESTRUCTIVE_SYNTHETIC_TEST=1` and the isolated port. Do not point it at the main demo or real patients. Backend tests use disposable PostgreSQL schemas and temporary private roots. The tests used actual Pillow/PyAV/PDF/Office processing and private filesystem I/O; scanner-adapter and permission-denial tests explicitly inject those boundaries. No paid AI calls were needed.

The existing software/browser assertions remain in place. Initial new-browser failures identified a timeline flex-shrink bug and missing refresh-recovery lookup on contact selection; these were fixed and the affected checks rerun. Broad text locators became ambiguous when contact previews were added; timeline-scoped selectors fixed the tests without weakening the checks. The full run and later targeted recovery run provide separate JUnit artifacts rather than falsely describing one combined invocation.

Manual/device verification still required:

| Platform or operational check | Status |
| --- | --- |
| Installed desktop Chromium: fake microphone MediaRecorder, private playback, actual video codec decode | Automated pass; synthetic tone, not a physical microphone. |
| Mobile viewport at 390×844; desktop at 1440×1000 | Automated pass and screenshot inspection. |
| Physical Android Chrome: microphone permission/device loss, capture, camera, background/interruption and playback | **Not run — device required.** |
| Physical iOS Safari: supported recorder MIME, pause/resume, memory/interruption, seek/video/fullscreen | **Not run — device required.** |
| Windows physical microphone/speech intelligibility; assistive technology and older-adult usability study | **Not run — human validation required.** |
| Live ClamAV, deployment TLS certificate, encryption-at-rest/KMS, encrypted restore, low-privilege worker sandbox, scale/soak and production identity | **Not provisioned/verified locally.** |
| Clinical/legal retention, consent lifecycle, export/incident response and regulatory applicability | **Requires organizational/qualified review.** |

## References checked for implementation

- [MDN recorder MIME support](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static) and [final data events](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event).
- [TUS offset/resume semantics](https://tus.io/protocols/resumable-upload): the local adapter documents its own authenticated chunk API; it does not falsely claim complete TUS compatibility.
- [OWASP upload defenses](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).
- [PostgreSQL row security and owner bypass](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).
- [PyAV container APIs](https://pyav.org/docs/stable/api/container.html); implementation is verified against installed PyAV 16.1.0.
- [Sri Lanka DPA notice](https://www.dpa.gov.lk/notice.php): this is a review reference, not an engineering claim of legal compliance. Qualified counsel must determine applicability for the operating organization, location and deployment date.
