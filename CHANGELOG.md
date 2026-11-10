# Changelog

All notable changes, newest first. Versions follow `0.x` while NeuroTwin is a research prototype.

## Unreleased

### Added
- Output validator for model-written drafts: citations, numbers and wording are checked by rules before any person
  sees a draft.
- Provider clients for Google Gemini and Meta's Model API behind one interface, keys read from `backend/.env`, and
  `scripts/list_models.py` to see which models a key can use. No model feature is switched on yet.

### Changed
- In demo mode the front page opens any demo view in one click, with no username or password. The password form
  appears only when demo mode is off. Shared demo accounts cannot change their password or sign out other devices.

## 0.2.0 — 10 Nov 2026

### Added
- **Within-person change engine.** Compares a person's earliest 3 usable sessions with their latest 2 for one
  measure and activity version. Gives the difference with a 95% interval from the person's own variation, reads
  "within" or "outside usual variation", and abstains when there are too few usable records or no variation.
  Clinicians only. Shown on the timeline, in the detail panel and in the report.
- **Password sign-in.** scrypt password hashes, server-side sessions in an HttpOnly cookie, CSRF checks,
  rate-limited sign-in, sign-out, password change that ends other sessions, and "sign out other devices".
  An Account screen in all three views.
- **Continuous integration.** Backend tests on Python 3.10 and 3.12 and the web build run on every pull request.
- `CONTRIBUTING.md` with the branch, pull request and release workflow.

### Changed
- The demo account picker is replaced by a username and password form. Demo accounts start with the password
  `neurotwin-demo-2026` (configurable).
- Usernames are shown only to their owner.

### Not yet included
- Account creation, password reset and two-factor sign-in.
- Review of the change-engine settings by a statistician and a clinician.

## 0.1.0 — 10 Nov 2026

First version.
- Evidence core: consent, purpose-scoped sharing, append-only evidence with provenance, deterministic quality
  rules, "To check" items, an audit trail, and logs without health data.
- Personal app (English and Arabic): consent, daily check-in, reaction activity, sharing, own records with
  corrections.
- Family view of shared activity updates.
- Clinician workspace: caseload, timeline, record detail with keep or exclude decisions, Workings and access log,
  printable report.
