# NeuroTwin

A brain health support prototype connecting older adults, families and clinicians. It includes a mobile-friendly companion, a clinical dashboard and a document intelligence layer.

**Synthetic data only.** This is a research prototype, not a diagnostic tool or a production clinical service.

## Features

- Accessible patient interface with large text, daily support tasks and voice/text navigation.
- Family help requests, clinician review and versioned care plans requiring explicit approval.
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

AI is disabled by default. To enable it, set `GEMINI_API_KEY`, `META_API_KEY` and `AI_ENABLED=true` in `.env`, then restart the API. Available model names and provider URLs are configurable in `.env.example`. Cloud actions require synthetic workspaces. Voice recording needs browser microphone permission. The optional `uv run python -m app.worker` projects in-app notifications; it does not send SMS or push notifications.

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
