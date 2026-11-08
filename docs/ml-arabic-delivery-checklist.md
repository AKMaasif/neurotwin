# ML and Arabic delivery checklist

Requested 8 November 2026. Continue through implementation, verification and documentation without separate phase approvals.

## Remove the retired device feature
- [x] Remove backend, UI, scripts, tests and feature documentation from the current repository tree.
- [x] Remove integrations and stale references; preserve unrelated care records and Git history.
- [x] Verify retired routes are unavailable and no simulator UI remains.

## Research ML pipeline
- [x] Obtain author-deposited data with recorded source, file integrity and permission basis.
- [x] Inspect the dictionary, label meaning, protocol compatibility and missingness before selecting a target.
- [x] Split by participant and linked study pairs; prevent target/future-data leakage.
- [x] Train an interpretable baseline, calibrate on a separate partition and evaluate untouched test participants.
- [x] Record counts, metrics, uncertainty, exclusions, artifact hashes and a model card.
- [x] Keep cohort research separate from the adapted app's clinical use and illustrative estimator.
- [x] Test leakage/invalid-data/artifact/evaluation boundaries and reproducibility.

## Arabic application and voice
- [x] Explicit English/Arabic interface catalog, persistent language choice and correct HTML language/direction.
- [x] Responsive RTL layout, bidirectional user content and accessible language controls on both clients.
- [x] Arabic application commands, safe negation/cancellation, confirmations and text fallback.
- [x] Arabic speech-language selection; no silent English voice substitution.
- [x] Preserve English-only assessment stimuli; do not silently translate the instrument or clinical/user-authored records.
- [x] Record wording review status honestly; qualified Arabic clinical/linguistic sign-off remains external until supplied.
- [x] API/browser, narrow-screen/enlarged-text, voice test-double and existing workflow regression tests.

## Delivery
- [x] Full regression, code checks, updated documentation and remaining external requirements. See [verification](ml-arabic-verification.md).

Research training and software review cannot establish clinical validity of the adapted assessment, Gulf generalization, or native-speaker clinical approval. No Git history rewrite or deletion of historical clinical/audit data is part of removing a feature.

## External release gates (not complete)
- [ ] Adequately sized independent clinical labels and target-population/longitudinal validation for the intended application.
- [ ] Qualified Arabic linguistic/clinical approval for the exact wording and intended use.
- [ ] Reliable Arabic ASR, intended older-adult/dialect/noise testing and physical-device voice/accessibility evaluation.

The software and exploratory research work do not close these scientific, clinical or language-quality gates. Live speech failures and worsened calibration are retained as evidence rather than marked successful.
