# Changelog

All notable changes, newest first. Versions follow `0.x` while NeuroTwin is a research prototype.

## Unreleased

### Changed
- Saved analyses have a single **Run agent** button (the recorded replay); "Show result now" and "Run live" were removed.
  A new real run starts from **Run Agent Analysis** as before.

### Added
- Charts in Agent Analysis: change per region (percent or mm³), left against right, tissue-group shares and alignment fit.
  They redraw the table only, show direction without good/bad meaning, and have table views.
- Agent Activity panel in Brain Analytics, Agent Analysis: a compact status card that expands into the real workflow
  graph, step details, timeline and event list, with live updates, saved-run history and replay. Planned agents and the
  missing brain-extraction step are shown as unavailable. See `docs/AGENT_ACTIVITY.md`.
- Execution events per run (`events.jsonl`) and the `/workflow` and `/runs/{id}/activity` endpoints.

### Fixed
- Alignment and label warping run in a separate process. Before, the server stopped answering for the ~40 s of the
  registration, and Cancel could not take effect until it finished.

## 0.3.0 - 11 November 2026

### Added
- New landing page with one-click demo entry for the patient, clinician and family views (English and Arabic).
- Redesigned participant app: Today screen, bottom tabs, picture-card daily check-in. Answers and skip behaviour
  are unchanged.
- Redesigned family view: sidebar layout, people cards, write-preview-send notes kept.
- Brain Analytics: Compare visits for two visits of the same OASIS-2 person (elapsed days from the dataset's own
  delay, imported measures labelled as imported, voxel-axis views because orientation is unverified, not
  registered), and a descriptive trend over visits for people with three or more visits.
- OASIS-2 manifest reader and subject extractor scripts; the imaging pages are open to every clinician demo account
  in demo mode (`NEUROTWIN_IMAGING_OPEN=0` restores the explicit list).
- Research experiment on stages 9 and 10 with subject-grouped evaluation, baselines and a shuffled-outcome control.
  Result: conversion prediction showed no skill on 15 events; nothing from it is shown per person.
- Imaging workflow document for stages 1-10 with gates, targets and the three bounded agents.
- CI installs the imaging and research packages so their tests run.

### Fixed
- Family view styles no longer leak into the landing page's family card; access cards fit the window.

## Earlier in 0.3.0

### Changed
- Voice typing: clips are converted to WAV in the browser; speech is Gemini only; the request no longer asks for
  "Arabic" in a way that let the model translate.
- Arabic drafts are written fully in Arabic (glossary and Arabic month names); model timeout 120 s; demo dates are
  fixed for the whole day.

### Added
- Voice typing in the family message box: visible recording, transcript to check, clip never stored. Speech provider
  with Gemini; `scripts/try_voice.py` for a live check.
- Family messages: write, preview, then send. Authorised relatives only; the person can read and remove from view.
- Care plan and reminders: clinicians write routines for a person; the person sees today's routines in English or
  Arabic and can answer Done or Not today. No answer is never counted as missed. Demo plan seeded for Fatima.
- Clinician summary drafts: a model writes from stored facts, the output validator checks every statement, and the
  clinician approves, edits or rejects. Drafts keep their facts, model and validator version. Daily call cap.
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
