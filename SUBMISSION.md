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

1. Open the [live demo](https://aasif-6379-neurotwin.hf.space/) and press a demo view (the free hosting sleeps when
   idle, so the first load can take a minute). No password is needed; the views are shared synthetic accounts.
2. **Older adult (Fatima, Arabic; Yousef, English)**: give consent, do the daily check-in and the reaction activity
   (answering "Today's conditions" first),
   ask the assistant "what is on today?", and type "I need help" to see the help screen. In Ask NeuroTwin,
   press "Allow AI answers", then ask a general question ("What is the population of India?" or "كم عدد سكان الهند؟")
   or "Make me a daily routine", and save it as your own routine.
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
screen before anything else, with no model, and worrying words ("I feel dizzy") get "Do you need urgent help now?" · no change estimate without enough usable records · no model text without
validation · no change to the care plan without a visible "Yes" and a clinician decision.

Real participants' words never reach an external AI provider; model answers in the typed assistant are limited
to demonstration accounts ([privacy and providers](docs/COMPANION_PRIVACY_AND_PROVIDERS.md)).

## Evidence that it works as designed

| Check | Result | Where |
|---|---|---|
| Backend regression suite | 727 passed, 14 skipped (optional imaging, research and FHIR libraries not installed), 0 failed | `backend/tests`, CI on Python 3.10 and 3.12 |
| Frontend unit tests and build | 39 passed; type check and build pass | `frontend`, CI |
| Emergency-phrase rule (English and Arabic) | Tuning set: 132/132 emergencies caught, 94/95 ordinary sentences left alone. Five held-out rounds: 85%, 90%, then 40%, 0% and 15% on deliberately new kinds of situation; every miss fixed and recorded. The word list is a first line: worrying words get "Do you need urgent help now?", and the urgent-help button is on every screen (a test renders all 19 screens in English and Arabic) | [EMERGENCY_BENCHMARK.md](docs/EMERGENCY_BENCHMARK.md) |
| Change engine on 16,000 simulated people | False alarms on stable people 4.8% (95% CI 3.9–5.8%); flags 61% of 3-SD and 81% of 4-SD slowings; abstains when records are too few. Setting aside the first 2 sessions as practice cuts false "faster" flags on learners from 7.7% to 3.3% and finds 54% (was 31%) of slowings hidden by learning | [CHANGE_ENGINE_BENCHMARK.md](docs/CHANGE_ENGINE_BENCHMARK.md) |
| Server response time (in process) | Median 6–19 ms for reads, about 40 ms for the assistant; 95th percentile under 65 ms | [LATENCY_BENCHMARK.md](docs/LATENCY_BENCHMARK.md) |
| Agent scenario benchmark | 71/71 guard-rail scenarios (altered numbers, unsupported claims, diagnosis requests, provider failure) | [AGENT_EVAL_REPORT.md](docs/AGENT_EVAL_REPORT.md) |
| Fixed readiness scenarios | 102/102 | [QA_BENCHMARK_REPORT](docs/QA_BENCHMARK_REPORT_2026-11-15.md) |
| Test–retest analysis code | ICC, SEM and minimal detectable change reproduce Shrout & Fleiss exactly; on simulated studies it recovers a true ICC 0.80 as 0.79 with 94% interval coverage, and shows that using the practice sessions lowers it to 0.75. Pilot protocol: 39 people | [RELIABILITY_STUDY.md](docs/RELIABILITY_STUDY.md) |
| Subgroup analysis | Same false-alarm rate for steady and variable people, but a real 60 ms slowing is flagged for 52% of steady and 22% of variable people; a switch to a slower device is flagged as slowing 11.7% vs 1.8%. Ready to run on pilot data by education, first language, language and device | [SUBGROUP_ANALYSIS.md](docs/SUBGROUP_ANALYSIS.md) |
| FHIR R4 export | A person's records as a FHIR R4 Bundle (Patient, Observation with UCUM units and data-absent reasons, Provenance, Consent); stable ids, references resolve, R4 rules checked in 8 tests; only the person or their chosen clinician, audited | [INTEGRATION_DESIGN.md](docs/INTEGRATION_DESIGN.md) |
| Assistant AI answers and safety guard | 42 tests: routing, unsafe answers blocked (dose, medicine change, diagnosis, reassurance, contact details, wrong language), routine checks, consent and real-account protection, provider failure; checked live with Gemini in English and Arabic | `backend/tests/test_assistant_ai.py` |
| Assistant understanding (typed) | Final set 47/50 = 94% (English and Arabic), 0 unsafe actions; 3 known misses listed | `backend/eval/run_companion_eval.py` |

All runs, with the two findings a reviewer should not miss: [BENCHMARK_REPORT_2026-11-16.md](docs/BENCHMARK_REPORT_2026-11-16.md).

These are software checks on developer-written and synthetic cases. **They are not clinical accuracy, sensitivity or
specificity figures**, and no claim of clinical benefit is made.

## How it maps to the judging criteria

| Criterion | What to look at |
|---|---|
| Health impact and clinical relevance | Within-person change over time (ADPHC: "change over time, not one test moment") with practice sessions set aside, z-score and reliable change index; vision, hearing, sleep, setting and feeling unwell asked before every activity, education and first language once, all shown to the clinician; closed loop from concern to recorded outcome; family support without exposing results |
| Technical depth and architecture | Deterministic core separate from gated model use; append-only evidence with provenance; [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Working solution and demo quality | Live link with one-click demo views; English and Arabic with right-to-left layout; typed assistant |
| Responsible AI, safety and data governance | Purpose-scoped consent and sharing, audit log without values, output validator, abstention, demo-only external AI, emergency rule without a model; subgroup analysis; DECIDE-AI readiness map |
| Scalability and deployment readiness | FastAPI + PostgreSQL, Alembic migrations, CI, HL7 FHIR R4 export, environment-only configuration, daily provider-call caps |
| Commercial viability and path to pilot | [Business case](docs/BUSINESS_CASE.md): providers pay AED 15 per enrolled person per month (cost to serve about USD 1.18, margin about 71%), less a year than one AED 200 remote-data review Abu Dhabi already pays for (DoH Addendum 30, CPT 99091); GCC 60+ population triples by 2050 and UAE dementia cases rise 18-fold; no verified competitor is Arabic-first or measures change over time; Abu Dhabi, Dubai, Saudi Arabia, then Asia; pilot gates below |

## Assumptions and limitations

- Activities are prototype digital tasks, not validated instruments; change-engine settings are engineering
  defaults awaiting statistician and clinician review.
- The first 2 sessions of each activity are treated as practice and never compared; the length of the practice period
  is an engineering default. The z-score is descriptive, and the reliable change index uses an assumed test–retest
  reliability (marked provisional on screen) until a reliability study measures one. The analysis code and protocol
  are ready; no reliability has been measured on real people.
- Today's conditions (seeing the screen, hearing, sleep, a quiet place, feeling unwell) are asked before each activity
  and education and first language once; they label results for the clinician but do not adjust them, because no
  normative adjustment exists yet. The rules for which conditions lower a record's quality are engineering defaults
  awaiting clinical review. Mood is captured by the WHO-5 (English) and the check-in, not per activity.
- Records export as HL7 FHIR R4 (download only). No connection to Malaffi, Sahatna or any electronic health record
  exists; the route (through the facility's own health record, not directly to Malaffi) is designed in
  [INTEGRATION_DESIGN.md](docs/INTEGRATION_DESIGN.md) and must be confirmed with DoH and Malaffi. Activity codes are
  NeuroTwin's own; no LOINC mapping yet.
- AI answers in the assistant use an outside model (Grok or Gemini, set on the server) for demonstration accounts that agreed to it; real
  accounts' words are never sent. Answers pass fixed safety rules (no doses, medicine changes, diagnoses or contact
  details) but can still be wrong, and say so on screen. Picture generation is not built.
- Arabic wording has not yet had a native Gulf clinical reviewer.
- Every screen checked in desktop browsers and at phone width (390 px) in English, Arabic and largest text; not yet
  tested with older adults on real devices.

## Path to pilot

1. Clinical review of activities, wording, urgent-help copy and change-engine settings.
2. Ethics approval (Abu Dhabi DoH process) and an agreed data-residency choice for any AI provider.
3. Small usability study with adults aged 50–75 and family members, in both languages.
4. Reliability study (test–retest, practice effect; code and protocol ready) and a manual-versus-assisted review
   comparison with clinicians, reported against DECIDE-AI ([readiness map](docs/DECIDE_AI.md)).
5. Integration study with existing records and the primary-care referral pathway: FHIR R4 export exists; next are
   the official HL7 validator, a DoH/Malaffi conversation and one EMR vendor sandbox ([design](docs/INTEGRATION_DESIGN.md)).

## More detail

[README](README.md) · [Status: verified, experimental, planned](docs/STATUS.md) ·
[Evaluation plan](docs/EVALUATION_PLAN.md) · [DECIDE-AI readiness](docs/DECIDE_AI.md) · [Integration design](docs/INTEGRATION_DESIGN.md) · [Licence](LICENSE) · [Third-party materials](THIRD_PARTY_NOTICES.md)
