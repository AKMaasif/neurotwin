# DECIDE-AI readiness map and first-live-evaluation protocol

**Reporting guideline:** DECIDE-AI, for the early-stage clinical evaluation of decision support systems driven by
artificial intelligence (Vasey et al., *Nature Medicine* 2022;28:924–933, also *BMJ* 2022;377:e070904). It covers the
first small-scale live use of a decision support system, with clinicians and patients, before a comparative trial.

**Where NeuroTwin is:** it has **not** had any live clinical evaluation. Every person and record in the demo is
synthetic. So this document does two things: for each DECIDE-AI reporting area it says what exists **today** and where
to find it, and it sets out what the **first live evaluation** must add and report. Item wording below is paraphrased
and grouped by theme; check it against the published checklist before a study is registered or a paper is written.

## What is being evaluated

| Component | Kind | Role in a decision | Status |
|---|---|---|---|
| Change engine (`backend/app/change.py`, change-engine/0.2) | Deterministic statistics, no model | Shows the clinician whether a person's recent results differ from their own earlier ones (95% interval, z-score, provisional reliable change index), or abstains | Working, tested on simulated people |
| Quality rules (`backend/app/quality.py`, quality-rules/0.2) | Deterministic rules | Label each record usable, doubtful or unusable, using today's conditions | Working, engineering defaults |
| Clinician summary drafts (`backend/app/drafts.py`) | Language model (Gemini or Meta, configurable) behind an output validator (`output-validator/0.2`) | Drafts a summary from stored facts only; the clinician approves, edits or rejects | Working with demo accounts; no clinician evaluation |
| Assistant and voice companion (`backend/app/assistant.py`) | Fixed rules; an optional model fallback for demonstration accounts only, which may only choose from a fixed menu | Helps the older adult act on their own reminders; any change needs a visible Yes; emergencies go to the help screen first | Working; text-understanding evaluation only |
| Brain Analytics agents (imaging) | Research workflow on OASIS-2 data | Not used for any decision about a person | Research only, out of scope for a first clinical evaluation |

The core that a clinician acts on (change engine and quality rules) is **not** machine learning. DECIDE-AI is applied
here to the whole clinician-facing decision support, because the reporting questions (intended use, users, workflow,
errors, human factors) apply equally, and because model-written drafts are part of it.

## Readiness map

Legend: **Ready** = exists and can be reported now · **Partly** = designed or simulated, needs live data · **Not yet** = must be done in the study.

### Title, abstract, introduction

| Area (paraphrased) | Status | Where it is today | The first live evaluation must |
|---|---|---|---|
| Identify the study as an early-stage live evaluation of an AI-based decision support system | Not yet | — | Use this wording in the title and abstract |
| Clinical problem, intended use, intended users and the place in the care pathway | Ready | `SUBMISSION.md` (problem, how it works), `docs/PROJECT_BRIEF.md` | State the pathway in the pilot site (primary care, memory clinic) and the decision the clinician makes with it |
| Objectives, including which outcomes are about safety, usability and workflow rather than effectiveness | Partly | `docs/EVALUATION_PLAN.md` | Pre-register objectives; no effectiveness claim at this stage |

### Methods

| Area (paraphrased) | Status | Where it is today | The first live evaluation must |
|---|---|---|---|
| Research governance: registration, ethics approval, funding | Not yet | Path to pilot in `SUBMISSION.md` | Abu Dhabi DoH research ethics approval; register the protocol |
| Participants (patients): eligibility, recruitment, numbers | Partly | Intended population 50–75, both languages; reliability sample size 39 (`docs/RELIABILITY_STUDY.md`) | Report eligibility, how people were approached, how many declined, age, sex, education, first language, device |
| Participants (users): which clinicians, their experience and how many | Not yet | Clinician role exists; demo clinician only | Report profession, experience, prior use of digital tools, number of users |
| Description of the system and its version | Ready | Components table above; every result carries its method and version (`change-engine/0.2`, `quality-rules/0.2`, `output-validator/0.2`, model name per draft) | Freeze versions for the study and report them |
| Data the system was developed and tuned on | Ready | Change engine: no training data, settings are engineering defaults; emergency rule tuned on developer-written sentences (`backend/eval/emergency_set.jsonl`); drafts use a general model, not trained here | State clearly that no patient data was used for development |
| Input data: how it is captured, quality checks, missing data | Ready | Activities and self-reports with provenance (`docs/ARCHITECTURE.md`); today's conditions; quality rules; missing never counted as a miss | Report the share of doubtful, unusable and missing records, by subgroup (`eval/run_subgroup_analysis.py --db`) |
| Implementation: setting, integration into the clinical workflow, user training | Partly | Clinician workspace, care plan, concern and care journey loop; FHIR R4 export but no EHR connection yet (`docs/INTEGRATION_DESIGN.md`) | Describe the site, when clinicians look, how long training took, and what happens outside the app |
| How the system's output is shown and used, and who decides | Ready | The clinician decides every item in "To check", approves drafts, writes care plans; the person confirms every change with a visible Yes | Record each decision and whether the clinician agreed with, changed or ignored the output |
| Safety: how errors, harms and near misses are identified, recorded and escalated | Partly | Emergency rule first, "Do you need urgent help now?", urgent-help button on every screen (tested), output validator, audit log without values, abstention (`docs/EMERGENCY_BENCHMARK.md`, `docs/AGENT_EVAL_REPORT.md`) | Name a safety officer; define harms and near misses; stop criteria; weekly review of every validator refusal and every emergency-screen opening |
| Human factors: usability evaluation methods | Not yet | Designed for older adults (large text, picture cards, Arabic right-to-left, voice); phone-width checks | Task-based usability sessions with older adults, family members and clinicians, in both languages; System Usability Scale; think-aloud |
| Statistical analysis plan, including subgroups | Partly | Test–retest code (`backend/app/reliability.py`), subgroup code (`backend/app/subgroups.py`), both checked against published figures | Pre-specify analyses: ICC(2,1), SEM, MDC; agreement between clinicians with and without the system; subgroups by language, education, first language, device, age band; minimum group size 20 |

### Results (to be reported by the study)

| Area (paraphrased) | Status | What to report |
|---|---|---|
| Participants: flow, baseline characteristics, losses | Not yet | Flow diagram; characteristics by subgroup |
| Implementation: how the system was actually used, deviations, changes during the study | Not yet | Usage logs (already recorded per session and decision), any version change |
| Main results: the system's outputs, the users' decisions, agreement and disagreement | Not yet | Share of estimates that abstained, were "outside", led to a clinician action; draft approval, edit and rejection rates |
| Safety and errors | Not yet | Every harm, near miss, validator miss, emergency false alarm and miss, with the investigation |
| Human factors | Not yet | Usability scores, time per task, problems found, how users' trust changed |
| Subgroups | Partly (benchmarks only) | `docs/SUBGROUP_ANALYSIS.md` shows on simulation that a device change looks like a slowing and that variable people need a larger change to be flagged; the study must measure both on real people |

### Discussion and other information

| Area (paraphrased) | Status | Where it is today |
|---|---|---|
| Support for the intended use and next stage | Not yet | — |
| Safety and errors in context | Partly | Known limitations listed in `SUBMISSION.md` and `docs/STATUS.md` |
| Strengths and limitations | Ready | `SUBMISSION.md`, "Assumptions and limitations" |
| Data availability | Ready | Synthetic demo data and generators are in the repository; real data would stay under the approved data-residency arrangement |
| Code availability | Ready | Full source, MIT licence (`LICENSE`), third-party notices |
| Conflicts of interest | Not yet | To be declared by the study team |

## First live evaluation: outline protocol (for review, not approved)

1. **Design:** single-site, prospective, observational first live use (IDEAL stage 2a). No change to usual care is
   required by the system; clinicians use it alongside their normal practice.
2. **Participants:** adults aged 50–75 who choose to take part, with an optional family member; clinicians at the site.
3. **Duration:** 8–12 weeks, enough for 2 practice sessions and 5 compared sessions per activity.
4. **Primary outcomes (safety and feasibility):** harms and near misses; emergency-screen openings (false alarms and
   misses found by review); validator refusals and misses; share of usable records; completion and drop-out.
5. **Secondary outcomes:** test–retest reliability (`eval/run_reliability_study.py --db`), usability, clinician time
   per review, draft acceptance, clinician agreement with "outside usual variation", subgroup results.
6. **Stop criteria:** any serious harm plausibly linked to the system; an emergency miss; a validator miss that
   reached a person; data leaving the agreed residency.
7. **What happens to the findings:** a statistician and clinician decide on the practice period, window sizes and
   the reliability figure; the provisional marks are removed only after that decision.

## Related documents

[EVALUATION_PLAN.md](EVALUATION_PLAN.md) · [RELIABILITY_STUDY.md](RELIABILITY_STUDY.md) ·
[SUBGROUP_ANALYSIS.md](SUBGROUP_ANALYSIS.md) · [EMERGENCY_BENCHMARK.md](EMERGENCY_BENCHMARK.md) ·
[CHANGE_ENGINE_BENCHMARK.md](CHANGE_ENGINE_BENCHMARK.md) · [STATUS.md](STATUS.md)
