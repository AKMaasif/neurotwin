# NeuroTwin — submission summary

**Future Health Digital Innovation Challenge · Population Health · Protecting brain health earlier**

> Independent research prototype. Not a medical device; it does not diagnose or predict. Every person and record in
> the demo is synthetic. Not affiliated with or endorsed by the Department of Health Abu Dhabi.

## In one line

NeuroTwin helps **clinicians, adults aged 50–75 and their families** to **notice meaningful change in a person's own
brain-health signals over time and act on it** using **short repeated activities, self-reports and consented family
support**, with every result traceable and every action clinician-reviewed.

## The problem we address

Brain changes can begin years before symptoms, but one screening score is not the full signal: language, education,
hearing, vision, mood and the day's conditions all move a single result. What matters is **change within the same
person over time**, measured honestly, and a **closed loop** so a concern leads to a named next step and a recorded
outcome rather than being lost.

## How to try it (about 5 minutes)

1. Open the live link and press a demo view. No password is needed; the views are shared synthetic accounts.
2. **Older adult (Fatima, Arabic; Yousef, English)**: give consent, do the daily check-in and the reaction activity,
   ask the assistant "what is on today?", and say or type "I need help" to see the help screen.
3. **Family (Mariam, Omar)**: see which activities were done, never the results; send a short message.
4. **Clinician (Dr. Layla)**: open a person, read the timeline and the change estimate (baseline vs recent, 95%
   interval), decide items in "To check", write a care plan, and follow a concern through its care journey.

## How it works

```
 Person (50–75) ─┐  consent per purpose, revocable   ┌─ Family: participation only, never results
                 ▼                                   │
     Activities + check-in + concerns ──► Evidence store (append-only)
                                         observed · self-reported · inferred, quality-labelled, versioned
                                                     │
                       Deterministic core (no model) ▼
                Quality rules ─► Change engine: earliest 3 vs latest 2, 95% interval, abstains when thin
                                                     │
               Model-assisted, always gated ─────────┤  drafts cite stored facts only; validator refuses invented
                                                     │  numbers, diagnoses, advice; clinician approves or rejects
                                                     ▼
            Clinician review ─► care plan & reminders ─► concern ─► care journey (next action, follow-up date,
                                                                    outcome, append-only history)
```

Safety gates: no activity without consent · no sharing without a purpose-scoped grant · emergency words open the help
screen before anything else, with no model · no change estimate without enough usable records · no model text without
validation · no change to the care plan without a visible "Yes" and a clinician decision.

Real participants' words and voices never reach an external AI provider; voice typing and the server voice are limited
to demonstration accounts ([privacy and providers](docs/COMPANION_PRIVACY_AND_PROVIDERS.md)).

## Evidence that it works as designed

| Check | Result | Where |
|---|---|---|
| Backend regression suite | 657 passed, 13 skipped (optional imaging libraries), 0 failed | `backend/tests`, CI on Python 3.10 and 3.12 |
| Frontend unit tests and build | 21 passed; type check and build pass | `frontend`, CI |
| Emergency-phrase benchmark (English and Arabic) | Tuning set: 72/72 emergencies caught, 47/50 ordinary sentences left alone. Two held-out rounds: 85% then 90% caught; every miss fixed and recorded | [EMERGENCY_BENCHMARK.md](docs/EMERGENCY_BENCHMARK.md) |
| Agent scenario benchmark | 71/71 guard-rail scenarios (altered numbers, unsupported claims, diagnosis requests, provider failure) | [AGENT_EVAL_REPORT.md](docs/AGENT_EVAL_REPORT.md) |
| Fixed readiness scenarios | 102/102 | [QA_BENCHMARK_REPORT](docs/QA_BENCHMARK_REPORT_2026-11-15.md) |
| Assistant understanding (typed or transcribed) | Developer-written English and Arabic sentences; known misses listed | `backend/eval/run_companion_eval.py` |

These are software checks on developer-written and synthetic cases. **They are not clinical accuracy, sensitivity or
specificity figures**, and no claim of clinical benefit is made.

## How it maps to the judging criteria

| Criterion | What to look at |
|---|---|
| Health impact and clinical relevance | Within-person change over time (ADPHC: "change over time, not one test moment"); conditions recorded with every session; closed loop from concern to recorded outcome; family support without exposing results |
| Technical depth and architecture | Deterministic core separate from gated model use; append-only evidence with provenance; [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Working solution and demo quality | Live link with one-click demo views; English and Arabic with right-to-left layout; voice companion |
| Responsible AI, safety and data governance | Purpose-scoped consent and sharing, audit log without values, output validator, abstention, demo-only external AI, emergency rule without a model |
| Scalability and deployment readiness | FastAPI + PostgreSQL, Alembic migrations, CI, environment-only configuration, daily provider-call caps |
| Commercial viability and path to pilot | Designed to sit beside existing screening and records systems as a clinician-review layer; pilot gates below |

## Assumptions and limitations

- Activities are prototype digital tasks, not validated instruments; change-engine settings are engineering
  defaults awaiting statistician and clinician review.
- Practice effects on repeated activities are not yet modelled; hearing, vision and mood are not yet captured per
  session, so the clinician must read change estimates with those factors in mind.
- No integration with Malaffi, Sahatna or any electronic health record exists; it is a design goal, not a feature.
- Arabic wording has not yet had a native Gulf clinical reviewer; speech recognition quality is not measured.
- Tested in desktop and phone-width browsers, not yet with older adults on real devices.

## Path to pilot

1. Clinical review of activities, wording, urgent-help copy and change-engine settings.
2. Ethics approval (Abu Dhabi DoH process) and an agreed data-residency choice for any AI provider.
3. Small usability study with adults aged 50–75 and family members, in both languages.
4. Reliability study (test–retest, practice effect) and a manual-versus-assisted review comparison with clinicians.
5. Integration study with existing records and the primary-care referral pathway.

## More detail

[README](README.md) · [Status: verified, experimental, planned](docs/STATUS.md) ·
[Evaluation plan](docs/EVALUATION_PLAN.md) · [Licence](LICENSE) · [Third-party materials](THIRD_PARTY_NOTICES.md)
