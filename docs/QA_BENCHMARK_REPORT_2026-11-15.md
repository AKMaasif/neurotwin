# QA and benchmark report — 15 November 2026

## Scope and environment

Local Windows checkout, branch `codex/care-journey-readiness`, including uncommitted implementation changes. Backend tests use disposable test databases; browser checks use a separate synthetic database and loopback server on port 8013. The user's existing server on port 8012 was not changed. No real patient records, emergency calls or live model/audio requests were used.

These are developer-authored software regression and agent-contract scenarios. They are not an independent held-out model benchmark, penetration test, diagnostic validation or proof of clinical benefit. Test groups overlap: do not add their counts to estimate unique coverage.

## Results

| Check | Actual result | Evidence |
|---|---|---|
| Full backend regression | 598 passed, 13 skipped, zero failed; 313.12 seconds; one test-client deprecation warning | `backend/imaging_data/verification/full-qa.xml` and `full-qa-output.txt` |
| Fixed readiness scenarios | 102 passed; zero failed, errors or skipped | `backend/imaging_data/verification/readiness/report.md` and `report.json` |
| Agent scenario benchmark | 71 marked scenarios passed; 72 test functions passed including supporting check | [Agent evaluation report](AGENT_EVAL_REPORT.md) |
| Frontend type check and production build | Passed; existing 607.72 kB imaging chunk warning remains | `npm run build` |
| Browser integration | Journey saved; 390-pixel dialog has no horizontal overflow; Escape closes after saving; Arabic RTL patient report shows shared note; no captured JavaScript runtime errors | `backend/imaging_data/verification/browser-result.json` and screenshots |
| Assistant browser integration | English and Arabic typed commands open the report with eleven days selected | `backend/imaging_data/verification/assistant-browser.json` |
| Python dependency compatibility | Passed: no broken installed requirements | `python -m pip check` |
| Frontend dependency security audit | Not clear: 1 high and 1 moderate affected package, no critical packages reported | `backend/imaging_data/verification/npm-audit.json` |

The backend regression covers authentication, consent/revocation, family access, CSRF, activity/evidence handling, concern reporting, confirmation and repeat prevention, care-plan acceptance, linked follow-up, source freshness, provider failures, migrations and available imaging operations. Mock transcription tests do not measure actual speech accuracy.

## Agent benchmark interpretation

Prepared responses exercise A1–A9 reviewer/explainer/planner/report/visual stages, Arabic glossary/back-translation checks and same-session noise contracts. Cases include altered numbers, unsupported citations, diagnosis requests, quality gates, provider unavailability and disagreement. Passing means the tested guardrail accepted or refused that specific prepared response as expected. It does not establish the miss rate on new paraphrases or the quality of Gemini/Meta outputs.

## Local performance observations

Twenty serial measured requests per endpoint after one excluded warm-up, against six months of synthetic history, with one client and other test processes running:

| Endpoint | Median | 95th percentile | Maximum |
|---|---|---|---|
| Activity source coverage preview | 29.21 ms | 30.45 ms | 30.92 ms |
| Linked journey list | 10.70 ms | 11.73 ms | 11.88 ms |

Raw measurements are in `backend/imaging_data/verification/performance.json`; percentiles use the nearest-rank method. No production acceptance threshold was predefined. This is not a load, concurrency, MRI-processing or model-latency benchmark. No comparison with manual clinician review was performed.

## Findings and next actions

1. **Security finding:** npm audit flags direct development dependency Vite 5.4.11 as high and transitive esbuild as moderate. Multiple advisories concern development-server access and file/editor handling. Review and update the toolchain to versions that clear the complete current audit, then rebuild and repeat browser/regression checks. Do not assume the audit's suggested version resolves every advisory. No automatic dependency upgrade or lockfile rewrite was performed by this test run. This finding alone does not establish compromise or exploitability of the built app served by FastAPI.
2. **Incomplete imaging/research environment:** `ants`, `sklearn` and `openpyxl` are unavailable for relevant optional tests. Install compatible dependencies on the intended processing environment and run those checks before claiming full imaging/forecast/spreadsheet verification.
3. **Build warning:** the imaging bundle exceeds the build tool's 500 kB warning threshold. Assess real-device loading before deciding whether further splitting is needed.
4. **Maintenance warning:** FastAPI/Starlette's test client reports an httpx deprecation warning. It does not fail the tests, but should be addressed in a separately verified dependency update.
5. **External evaluation still required:** held-out live-provider factuality and failure metrics; actual spoken English/Arabic recognition and intent trials; native-language review; activity reliability/practice/device studies; clinician/patient accessibility sessions; manual-versus-assisted review study; deployment restore rehearsal and independent security review.

The application is not clinically validated or production-certified by these results. See [evaluation plan](EVALUATION_PLAN.md) for the remaining study and release gates. Local verification artifacts are ignored by Git and should be reviewed before sharing.
