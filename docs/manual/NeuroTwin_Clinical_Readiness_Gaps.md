# NeuroTwin clinical readiness gaps

**Software revision:** e9db1ca (branch feature/voice-companion)
**Date:** 16 November 2026
**Companion to:** *IFHAS-NeuroTwin_Professional_Clinical_Product_Manual.pdf*, Edition 2.0

This list covers what would have to be done before NeuroTwin could be used with real patients or presented as clinically
reliable. Nothing here has been resolved. Where a document in the repository records partial work, it is named. No
compliance with HIPAA, GDPR, UAE health-data law, ISO 13485, IEC 62304, ISO 14971 or any other standard is claimed.

Priority: **P1** blocks any use with real people. **P2** is needed before claims about accuracy or benefit. **P3** improves quality or operations.

## 1. Clinical evidence

| # | Gap | Current state | Evidence | What would close it | Priority |
|---|---|---|---|---|---|
| 1.1 | No clinical validation | No study with real participants. All data are fictional personas or de-identified OASIS scans. | Manual §2, §20 | A prospective study with ethics approval, reported against DECIDE-AI (early live evaluation of decision support) | P1 |
| 1.2 | Change thresholds not calibrated | change-engine/0.2 thresholds were set by the developer and tested only on simulated people (95.2% stable; 33.2/60.8/81.3% detection at 2/3/4 SD). | docs/CHANGE_ENGINE_BENCHMARK.md | Calibrate on real repeated measurements; report sensitivity and specificity against a clinical reference | P2 |
| 1.3 | Reliability assumed | The reliable change index uses an assumed r = 0.8 and SD 70 ms (SEM 31.3 ms, MDC 87 ms). The ICC code reproduces Shrout & Fleiss, but no test–retest data exist. | docs/RELIABILITY_STUDY.md | A test–retest study on the reaction and memory activities in the target population | P2 |
| 1.4 | Subgroup behaviour | In simulation, a 60 ms slowing is flagged in 51.7% of steady people but only 22.3% of variable people. | docs/CHANGE_ENGINE_BENCHMARK.md | Check performance by age, education, language and device; document who the tool works less well for | P2 |
| 1.5 | Activities are not validated tests | Reaction and picture-memory activities are not validated cognitive measures. | Manual §7.4 | Psychometric evaluation, or replace them with licensed instruments | P2 |
| 1.6 | No usability study | No study with older adults, family members or clinicians | — | Formative and summative usability testing (for example following IEC 62366-1 methods) | P2 |
| 1.7 | No clinical oversight structure | No named clinical safety officer or clinical governance process | — | Appoint a clinical lead; define review of flags, summaries and incidents | P1 |

## 2. Safety of the assistant and urgent-help logic

| # | Gap | Current state | Evidence | What would close it | Priority |
|---|---|---|---|---|---|
| 2.1 | Emergency phrase detection misses on new wording | The development set scores 132/132 and 94/95. Held-out rounds scored 17/20, 18/20, 8/20, 0/20 and 3/20 (4/20 counting the follow-up question). Specificity is 13–15/15. | docs/EMERGENCY_BENCHMARK.md | A large, independently written held-out set, including Arabic and colloquial wording; clinical review of the rule; clear wording that the app is not an emergency service | P1 |
| 2.2 | No fresh held-out set for the current rule | Every held-out set has since been used to tune the rule. | docs/EMERGENCY_BENCHMARK.md | Have someone other than the developer write a new set and freeze it before testing | P1 |
| 2.3 | Urgent-help numbers not verified | Numbers are shown as unverified until an operator configures them. | emergency.py; Manual §7 | Confirm local emergency and crisis numbers for each deployment region | P1 |
| 2.4 | Assistant evaluation is small and self-written | Companion set 47/50 (English 35/37, Arabic 12/13), 0 unsafe; agent eval 71/71. All sentences were written by one developer. | docs/COMPANION_EVALUATION.md | An independent test set written by target users; red-team testing | P2 |
| 2.5 | No real-voice evaluation | Spoken input was never tested with real voices, accents or hearing-impaired speech. Speech-to-text is limited to demo accounts. | voice.py; Manual §8.2 | Evaluate on recorded speech from the target population; decide on a speech provider and its terms | P2 |
| 2.6 | Model answers not exercised live | Optional model answers were tested with mocks only. | test_assistant_ai.py | A live evaluation with the chosen provider, with logging of off-menu answers | P2 |

## 3. Language and content

| # | Gap | Current state | Evidence | What would close it | Priority |
|---|---|---|---|---|---|
| 3.1 | Arabic wording not reviewed | Drafted by the developer with machine-translation help; no formal native-language or cultural review | Manual §2.5 | Review by a qualified Arabic medical translator and by members of the target community | P1 |
| 3.2 | WHO-5 in English only | No Arabic WHO-5 is offered. | Fig. 12 | Obtain and license a validated Arabic WHO-5, or remove the questionnaire for Arabic users | P2 |
| 3.3 | Health wording not clinically reviewed | Participant-facing text has not been checked by a clinician. | — | Clinical content review | P1 |

## 4. Imaging

| # | Gap | Current state | Evidence | What would close it | Priority |
|---|---|---|---|---|---|
| 4.1 | Native import incomplete | Only stages 1–3 run. Stages 4–7 (registration, segmentation, measurements, QC) are blocked. | Manual §14 | Finish and test the remaining stages | P2 |
| 4.2 | ANTs alignment not run | antspyx was not installed or run in this check. | Implementation verification report | Install and run, compare results with a reference pipeline | P2 |
| 4.3 | Segmentation not verified | SynthSeg was not run in this check; the displayed measurements are imported results. | Manual §13 | Run and compare with reference values | P2 |
| 4.4 | OASIS terms | OASIS data use terms must be respected; the data must not be redistributed. | Manual App. D | Confirm terms for any public demo; keep the data out of the repository | P1 |
| 4.5 | Imaging AI outputs are research only | Explanations, visuals and reviews were viewed from stored runs; no accuracy assessment exists. | Manual §16 | Radiologist review of outputs; error analysis | P2 |

## 5. Privacy, security and data governance

| # | Gap | Current state | Evidence | What would close it | Priority |
|---|---|---|---|---|---|
| 5.1 | No DPIA | No data protection impact assessment | — | Complete a DPIA for the intended jurisdiction | P1 |
| 5.2 | No penetration test | Security controls (scrypt hashes, sessions, CSRF, consent checks, audit) are tested in code only. | auth.py, security.py; tests | Independent security assessment | P1 |
| 5.3 | No retention policy | Withdrawing stops new records; earlier records are not deleted automatically. | Manual §19 | Define and implement retention and deletion rules | P1 |
| 5.4 | Provider agreements | No data-processing agreements with AI or speech providers | — | Agreements, or local-only processing | P1 |
| 5.5 | Secure cookies off by default | NEUROTWIN_SECURE_COOKIES defaults to "0" for local use. | Manual §5 | Require "1" with HTTPS in any deployment | P1 |
| 5.6 | Regulatory pathway undetermined | Intended use and classification not assessed in any jurisdiction | Manual §2.3 | Regulatory assessment by a qualified adviser | P1 |
| 5.7 | No standards conformity | No quality management system, software lifecycle or risk-management file | — | Decide whether ISO 13485, IEC 62304 and ISO 14971 apply, and plan accordingly | P1 |

## 6. Interoperability

| # | Gap | Current state | Evidence | What would close it | Priority |
|---|---|---|---|---|---|
| 6.1 | FHIR export not externally validated | FHIR R4 download exists; the independent library test was skipped because the library is not installed. | fhir.py; test_fhir.py | Validate against the official FHIR validator and any target profiles | P2 |
| 6.2 | EHR integration is design only | Malaffi and Sahatna integration exist only as a design document. | INTEGRATION_DESIGN.md | Implementation and conformance testing with the integration owner | P3 |

## 7. Operations

| # | Gap | Current state | Evidence | What would close it | Priority |
|---|---|---|---|---|---|
| 7.1 | No hosted deployment verified | No hosted address checked; PostgreSQL and HTTPS not tested | Manual §4 | Deploy, then test with PostgreSQL and HTTPS | P1 |
| 7.2 | No backups or monitoring | None configured | — | Backups, restore tests, uptime and error monitoring | P1 |
| 7.3 | Concern inbox hours not set | NEUROTWIN_MONITORING_HOURS is unset by default, so participants are not told when concerns are read. | Manual §5 | Set and staff the stated hours | P1 |
| 7.4 | Clean-clone install not tested | Installation was checked in the existing working copy only. | Implementation verification report | Test a fresh clone on a clean machine | P3 |
| 7.5 | Stale on-screen text | The Agent Activity panel still says "Press Run live" although that button was removed. | Manual §20.3 | One-line text fix (not made: source changes were not authorised) | P3 |
| 7.6 | Test count mismatch | SUBMISSION.md says 775 passed and 12 skipped; the run on 16 Nov 2026 gave 756 passed and 14 skipped. | Implementation verification report | Update SUBMISSION.md | P3 |

## 8. Reviews still open

| Review | Status |
|---|---|
| Owner review of this manual | Open |
| Independent clinical review | Open |
| Arabic native-language review | Open |
| Legal and regulatory review | Open |
