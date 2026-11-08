# ML, Arabic and device-feature removal verification

Verified 8 November 2026. These are engineering and exploratory research results, not clinical validation or qualified language approval.

## Completed checks

- Full backend regression: **520 passed, 4 skipped**, 524 collected, 665.64 seconds. Evidence: `test-results/ml-arabic-integrated.xml`. Four skips are SQLite-only concurrency/RLS cases; PostgreSQL variants passed. One existing Starlette/httpx deprecation warning remains.
- Final isolated browser regression: **20/20 flows passed**, batch `bd32caf4a0ce`, report `test-results/isolated-browser/bd32caf4a0ce/report.json`. Includes assessment, messaging, record-preview-explicit-send voice notes, original English reference design, authorization/privacy and care exports.
- Arabic browser coverage: five scenario groups, mobile widths 320/390/768/1440 and enlarged text, RTL, safe commands/confirmation, original user content, language snapshot, catalog equality and clinician benchmark report. Speech doubles establish software behavior only.
- Research source download and training repeated independently: model and evaluation reproduced exactly. Raw source and local reports remain ignored. No source rows or participant identifiers are committed in the model artifacts.
- Normal development service health returned 200. Retired device routes are absent from OpenAPI and return unavailable responses; feature backend, client, simulator tests and documentation were removed. Git history and historical care/audit records were preserved.

## Research interpretation

The author-deposited CC0 original SATURN cohort supplies 29 eligible protocol-compatible participants after exclusions. Participant/linked-pair separated partitions contain 15 training, 7 calibration and 7 test participants. Eighteen negative labels are presumed normal under the study protocol; only one negative is independently clinically rated. This prevents a credible clinical release claim.

Held-out AUC is 0.8333 with a wide group-bootstrap interval of 0.2 to 1.0. Calibration worsened Brier score from 0.1774 to 0.1890 and log loss from 0.5066 to 0.5761. The calibrated model is not promoted. Clinical use, release approval and runtime patient inference remain disabled. This cross-sectional source does not validate the adapted app or its illustrative longitudinal estimator. See [model card](ml-source-study-benchmark.md).

## Arabic interpretation

The interface contains 1,350 catalog entries with RTL layout, explicit language choice, bounded Arabic commands, confirmation and text fallback. Clinical assessment stimuli remain in their original English language. Dynamic care content is not silently translated. Qualified Arabic linguistic and clinical reviews are pending.

Live Arabic speech benchmarking completed only two of three planned cases: one command matched, one failed, then the provider became unavailable. This is a failed reliability gate, not a passing speech benchmark. Browser speech doubles do not override this result. Older-adult, Gulf dialect, noise, pronunciation and physical-device testing remain outstanding. See [localization details](arabic-localization.md).

The delivery checklist distinguishes finished engineering from the external scientific, clinical and language review gates. Local test reports and generated audio are intentionally excluded from Git.
