# Continuous assessment delivery checklist

Requested 8 November 2026. Work items are sequential; routine implementation and synthetic testing do not require another phase approval.

1. Publish the already verified local work.
   - [x] Review staged changes and credential patterns.
   - [x] Commit and push care-summary export, validation profile and documentation.
   - [x] Verify remote main equals 7425095b1061a638e8f1f13a202eb69af4180470.
2. Review and select the assessment approach.
   - [x] Compare primary administration/scoring/reuse sources.
   - [x] Record selection rationale, source/version, language/mode limits and reuse status.
   - [x] Separate research implementation from qualified clinical approval; never fabricate an approval or licensing agreement.
3. Implement the connected assessment workflow.
   - [x] Clinician assignment, immutable protocol snapshot and participant consent.
   - [x] Sequential activities, raw response capture, timestamps and quality metadata.
   - [x] Server-side deterministic scoring of appropriate structured evidence.
   - [x] Interruption/cancellation/withdrawal and stale/replayed-command checks.
   - [x] Clinician review with independent item-level adjudication and attributed outcome.
   - [x] Patient/family projections that protect answers and draft scores.
   - [x] Accessible mobile UI, clinical dashboard controls and preserved reference design.
   - [x] SQLite/PostgreSQL unit/integration and end-to-end browser tests.
   - [x] Update roadmap, limitations and current verification evidence.

External boundaries: no synthetic test or logged-in demo clinician can establish clinical validation, institutional authorization or rights-holder permission. The software must represent pending clinical/reuse status honestly while continuing all implementable work.

Selected source: SATURN 0.4.0 English (CC0 author deposit). Delivered protocol: saturn-derived-research 1.0, an explicitly unvalidated adaptation. Source/reuse review and the research implementation do not close the external clinical-approval requirement.

Delivery evidence: full backend 500 passed / 4 expected SQLite-only skips; all 20 isolated browser flows passed. Details and reproduction: assessment-verification.md. The new assessment implementation is included in the user-authorized assessment delivery commit; the earlier care-summary checkpoint is pushed as 7425095.

External clinical-readiness checklist (not completed):
- [ ] Named qualified clinical lead and documented approval for the exact adapted protocol.
- [ ] Intended-population/language/device validation and consent/capacity policy.
- [ ] Real-user accessibility, follow-up governance and production operational approval.
