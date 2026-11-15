# Evaluation and pilot plan

Keep software correctness, agent output quality, measurement validity and clinical usefulness as separate evidence categories. Never report mock-provider passes as model accuracy.

## 1. Software QA

Run `backend/.venv/Scripts/python.exe -m pytest -q` from the repository root with the interpreter path adjusted to the working directory. Build the frontend with `npm run build` from `frontend`. Run `backend/scripts/run_readiness_checks.py` with the backend interpreter from `backend` for the fixed scenario report.

The fixed scenarios cover grants/revocation, CSRF, cross-role access, explicit follow-up, revision conflicts, independent statuses, evidence freshness, source quality, unsupported statements, confirmation, report commands, emergency priority, failures and migrations. The exported JSON contains test identifiers and actual statuses. Investigate failures and list skipped checks with their reason; do not silently exclude them from a headline total.

Add a release browser exercise on desktop and a narrow mobile viewport, in English and Arabic: report navigation, concern send confirmation, journey editing, plan acceptance, task response, error recovery, keyboard focus and print. Use isolated demo storage. Check that the MRI viewer and existing agent analysis still load on the imaging host.

## 2. Agent benchmark

Freeze a development set and a separate final set with independently adjudicated expected evidence and acceptable responses. Include insufficient baseline, missing values, assisted/interrupted activity, changed protocol, invented numbers, unsupported diagnosis, stale evidence, revoked sharing, provider timeout and contradictory records. Evaluate important stages and the full chain.

Record provider/model/version, prompt version, dataset version, case count, expected/actual result, unsupported claims, omitted facts, abstentions, failed handoffs, retry behavior, latency and cost. Human reviewers must assess semantic claims as well as numeric checks. Prevent model text from initiating unauthorized actions. Do not tune on the final set and continue calling it held out.

## 3. Activity and language validation

Obtain expert review of intended purpose, protocol, scoring, licensing and language adaptation before clinical use. Study repeated measurements under comparable conditions, reproducibility, practice effects, device effects and interruptions. Where justified, predefine analysis of reliability, measurement error and uncertainty. Diagnostic sensitivity/specificity require an independently established reference and adequate sample; no such result is established by current software tests.

For voice, test spoken English and Arabic separately, including dialect, noise, microphone permission, inaccurate transcripts and assistive needs. Record transcription accuracy, intent accuracy, clarification, cancellation, confirmation, duplicate prevention and successful task completion. Text-parser tests are not spoken interaction tests. Commission native-language review; translated labels alone do not validate a health activity.

## 4. Workflow usefulness

Use fictional/de-identified cases with appropriate approvals. Compare manual record review with assisted review using equivalent cases and counterbalanced order where feasible. Predefine time, factual errors, omissions, reviewer usefulness, task completion and assistance needed. Record experience and accessibility context. Report sample size, missing results, uncertainty and pilot limitations; do not infer patient benefit from a faster demonstration.

## Release gates

1. All relevant software checks pass; skipped environments and unresolved defects have explicit owners.
2. Restore rehearsal and migration check pass on a copy of deployment data.
3. Security, data-egress and retention configuration reviewed for actual hosting and providers.
4. Independent expert review of claims, safety boundaries and escalation process completed.
5. Pilot approval, consent, support owner and stop criteria documented before real participants.

The current work establishes software infrastructure and developer-authored regression evidence. It does not satisfy gates 2–5 automatically.
