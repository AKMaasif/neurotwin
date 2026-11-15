# NeuroTwin readiness checklist

Updated 15 November 2026. This is a research prototype. Software checks do not establish clinical accuracy or patient benefit.

## Goal

Support an attributable, consent-controlled loop: patient concern → review of recorded evidence → bounded analysis → clinician judgment → care plan → patient acceptance → daily responses → documented follow-up. Preserve the separate MRI research workflow. A completed task is a patient report, not a verified health outcome.

## Implementation and remaining work

| Area | Current implementation / evidence | Work still required |
|---|---|---|
| Existing features | Baseline audit and regression suite; additive care-journey tables; original MRI processing retained | Real deployment backup and restore rehearsal before upgrading a populated installation |
| Complete care loop | Clinician concern inbox opens a linked journey; link a reviewed activity analysis and a plan version; record owner, next action, due date and explicit outcome; patient report shows shared follow-up | Clinician-led usability pilot of the full journey |
| State distinctions | Concern status, plan acceptance, task responses and journey outcome remain independent; closure needs a note | Review terminology with intended users |
| Evidence | Existing provenance and quality records; new source fingerprints and review digests; changed evidence blocks new review/linking | Independent evidence-adjudication cases and source-data governance review |
| Bounded agent analysis | Existing evidence ledger, checks, review, events, cancellation and failure handling retained; new data-coverage preview | Held-out live-provider benchmark, latency and cost measurements |
| Agent activity panel | Existing expandable panel remains; inspect operations and outputs rather than treating animation as proof | Observe whether clinicians can identify inputs, failures and required review |
| Patient dashboard | Existing tasks, acceptance, activities, concerns and reports retained; current care-journey follow-up added to report | Accessibility sessions on real devices; patient language review |
| Voice and text | Existing confirmation flow retained; English/Arabic eleven-day report navigation added; unknown report periods do not silently map to eleven days | Separate real spoken English and Arabic trials, dialects, accents, noise, permission denial and correction |
| Concern reporting | Existing draft/confirmation/send retained; linked journey cannot silently acknowledge or resolve concern | Service response policy, escalation ownership and operational monitoring |
| Emergencies | Existing emergency intent priority retained | Confirm local dialer integration on target devices; do not advertise a successful call without actual connection evidence |
| Care plans | Existing clinician-authored versioned plans, patient acceptance and daily responses retained; linked version visible | Confirm ambiguous instructions/units with clinician; never invent dose, amount or frequency |
| Activities | Existing check-in, reaction, memory and wellbeing activities remain research observations | Protocol review, licences, test–retest reliability, practice/device effects, Arabic adaptation and suitability; no automatic MRI or Alzheimer warning |
| QA | Fixed software scenarios, expected behavior and per-test actual results exported by readiness runner | Independent final cases separate from development fixtures; triage every skipped dependency check |
| Measurement validation | No new claim of sensitivity, specificity or clinical thresholds | Independently labelled sample, justified size, confidence intervals, false-positive/negative review and subgroup analysis |
| Usefulness | Workflow available for comparative pilot | Manual versus assisted review: time, factual errors, omissions, usefulness and assistance needed |
| Privacy/security | Existing purpose grants, revocation, sessions and CSRF retained; journey ownership checks, optimistic revisions, append-only event records; run/visit identifiers masked in request logs | Threat model review, penetration test, retention/deletion policy, vendor agreements, role review and deployment hardening |
| Submission | Evidence and limitations documented; no changes to supplied submission deck | Team, ownership, conflict declarations, deployment access, final video rules and official submission requirements confirmed by team |

## Safe demonstration

Use a clearly fictional patient. Send a concern, open its linked care journey, run the activity analysis, inspect source coverage and agent events, review the draft, link the reviewed run, create/send a plan, accept it as the patient, record a response, refresh the journey, then record the clinician's next step. Show an unavailable or changed source and a failed/ambiguous request as well. Do not present synthetic demonstration results as clinical findings.

## Verification records

See [audit](READINESS_AUDIT.md), [evaluation plan](EVALUATION_PLAN.md) and the generated local report at `backend/imaging_data/verification/readiness/report.md`. The generated report is ignored by Git because local verification output can contain environment information. It must be reviewed before sharing.
