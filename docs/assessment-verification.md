# Assessment engineering verification — 8 November 2026

This evidence concerns synthetic software behavior, not clinical accuracy, diagnostic validity, older-adult usability certification or production approval.

## Executed checks

- Targeted assessment checkpoint: 42 checks passed across SQLite and disposable PostgreSQL schemas. This preceded the additional response-redaction and concurrent-assignment tests, which are included in the full regression below.
- Complete isolated browser profile: all 20 flows passed. Evidence: `test-results/isolated-browser/ce1853e9f31d/report.json`. Each flow used a fresh synthetic database/private media directory and worker, with AI disabled.
- Dedicated assessment browser scenarios passed: clinician assignment/participant consent/family denial; all 22 sequential screens and 20 scored groups; clinician evidence review and participant-note projection; withdrawal; navigation interruption without replay. Console errors: zero. Responsive checks included widths 320, 390, 768 and 1440, with 200% root text at 320px. This is not a full assistive-technology or physical-device matrix.
- Existing core, companion, reports, routines, text messages, record-preview-explicit-send voice notes, multimedia, UI references, plan/clinical design, privacy, care pages, family reports, research lifecycle, IoT, camera, account sessions, password and care-summary export flows all passed in that profile.
- Ruff, repository Prettier formatting and whitespace checks passed. Four curated unchanged source stimulus files matched their recorded SHA-256 values; downloaded archive matched the published MD5. No participant dataset/example log was added to the application assets.
- Local development API: health 200; unauthenticated assessment request 401. Main service uses loopback port 8140. Destructive account/capture tests used isolated fixtures, not this service.

## Complete backend regression

Full backend regression passed **500 tests with 4 expected SQLite-only skips** (504 collected), with no failures/errors. The PostgreSQL variants of concurrent account revocation, concurrent password changes, restricted message-table RLS and concurrent assessment assignment passed; SQLite cannot exercise those PostgreSQL guarantees. The assessment module contributed 45 passing checks and one of those SQLite skips in this complete run. The existing Starlette/httpx TestClient deprecation warning remains.

Evidence: `test-results/assessment-integrated-regression.xml` (SHA-256: `74b9a7347e55270cedd7b50d7c3e4fd68e20c936bf138fbe8b7c700b4fedfa39`). The tests use disposable PostgreSQL schemas and in-memory SQLite fixtures, not enrolled/normal patient records. This is current working-tree engineering evidence, not the historical 445-test checkpoint.


## Reproduction

```powershell
$env:TEST_POSTGRES = '1'
uv run pytest -q --junitxml=test-results/assessment-integrated-regression.xml
uv run python -m scripts.chat_fixtures
# Use an installed supported Playwright browser; optional local executable override.
uv run python scripts/isolated_browser_checks.py
uv run ruff check .
npm run format:check
git diff --check
```

The browser runner defaults to 20 named flows and refuses arbitrary script paths. The dedicated assessment browser script additionally refuses the normal port-8140 service. The test databases, media, logs and reports are ignored local artifacts. PostgreSQL fixtures create/drop only their generated `nt_test_*` schemas; they do not reset the normal patient database.

## Remaining external requirements

Qualified clinical sign-off, adapted-instrument fidelity/validation, Arabic/Gulf/device norms, consent/capacity policy, physical-device/older-adult/assistive-technology evaluation, clinical follow-up governance and production identity/storage/operations remain incomplete. No test in this file authorizes lifting the synthetic-only API gate.
