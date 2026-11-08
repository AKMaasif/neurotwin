# Integrated software validation — checkpoint 89db79b

This milestone checks the current application together after the research, camera and account-security additions. It does not establish clinical accuracy, intended-user usability or production readiness. Formal assessment scoring remains gated because an instrument has not been selected.

## Reproduce locally

Run from the project directory with its development dependencies and an isolated-test-capable PostgreSQL connection configured. Keep the normal application database separate from generated fixtures.

```powershell
$env:TEST_POSTGRES = "1"
uv run pytest -q --junitxml=test-results/integrated-regression.xml
uv run python -m scripts.chat_fixtures
uv run python -m scripts.isolated_browser_checks
uv run ruff check .
npm run format:check
git diff --check
```

If Chromium's installed executable differs from Playwright's expected revision, set `PLAYWRIGHT_EXECUTABLE_PATH` to the existing installed Chromium executable before the browser command. This is an environment override, not an instruction to download or run an arbitrary executable.

Backend fixtures test SQLite and disposable PostgreSQL schemas. The tests disable or replace provider inference; no live patient inputs or external AI requests are required. PostgreSQL-specific concurrency/RLS checks cannot be claimed from a SQLite-only run. Read actual skip reasons in the JUnit report.

The browser runner creates a fresh synthetic SQLite database, private media directory and scheduler worker for each selected flow, with AI disabled. Its 18 default flows cover core, companion, reports, routines, text messaging, voice notes, multimedia, reference UI, plan design, clinical design/privacy, care pages, family report design, research sessions, simulation, camera, account sessions and password changes. Large cross-browser matrices and separately guarded security fixtures remain optional and are not implied by this profile.

Generate the synthetic media fixtures first. The default voice-note flow prepares its own microphone WAV before the multimedia flow uses it. If running multimedia alone on a clean checkout, run the fixture-generation command and voice-note check first. No primary patient data is reset or deleted. Existing fixture/report files remain in ignored data/test-results directories.

## Evidence and interpretation

The completed full backend run passed **445 tests with 3 skips** (448 collected), with no failures/errors. The three skips were the SQLite variants of concurrent session revocation, restricted PostgreSQL message-table RLS and concurrent password changes; their PostgreSQL variants passed. The existing Starlette/httpx TestClient deprecation warning remains. Evidence: ignored `test-results/integrated-regression.xml`. The expanded default browser run passed **all 18 flows**, each against its own fresh synthetic database/media directory and worker. Evidence: `test-results/isolated-browser/4b38933c68a3/report.json`. A passing software contract is not clinical/model accuracy. Mocked camera/provider browser responses are labelled test doubles; events remain simulated; private media tests use generated files and a synthetic microphone.

Clinical protocol selection, permitted longitudinal data/model validation, physical-device/speech/older-adult testing, actual hardware, production enrollment/recovery, deployment and external communication integrations remain independent outstanding work. These test commands do not publish to GitHub or deploy the application.


The existing agent-contract summarizer was applied directly to this full JUnit report, without rerunning or double-counting its selected cases. All eight roles reported contracts_passed: A1 had 6 scenarios, A2–A7 had 5 each, and A8 had 14. These rows overlap and must not be summed as independent experiments. The report retains producer/reviewer attribution and the raw-report SHA-256 in ignored `test-results/integrated-agent-contracts.json`. Passing statuses measure selected deterministic/service contracts, not clinical accuracy or the reliability of eight independently trained agents.


The current application code is based on committed revision `89db79b`; this verification cycle adds only the expanded browser profile and documentation. Ruff, repository formatting and whitespace checks passed. The normal local development service is health-checked separately; the regression commands never use it as their browser fixture. Consolidated local metadata is in ignored `test-results/integrated-validation-summary.json`. No full cross-browser/physical-device matrix, production deployment or live-model evaluation was performed in this cycle.


This checkpoint precedes the participant care-summary export. The later feature has its own incremental evidence in `docs/care-summary-export.md`; the current default browser profile has 19 configured flows. The recorded 18-flow run above is historical checkpoint evidence, not a claim that the new export was part of that run.


## Assessment delivery checkpoint — 8 November 2026

The later working-tree assessment milestone passed the complete current suite: **500 passed, 4 expected SQLite-only skips** (504 collected), plus all **20 default isolated browser flows**. This supersedes the earlier checkpoint for current engineering coverage without changing its historical figures. The new skip is concurrent assessment assignment, whose PostgreSQL variant passed. Full evidence, adaptation limitations and reproduction: [Assessment verification](assessment-verification.md). Clinical approval/validation and real-device/intended-user testing remain external.
