# Per-role contract evidence

Run `uv run python -m scripts.agent_contract_benchmark` from the repository root. Set `TEST_POSTGRES=1` to run applicable API tests on both configured PostgreSQL and isolated SQLite fixtures. The script executes tests rather than reading a historical success badge. Each future invocation writes a unique JUnit filename and a current `test-results/agent-contracts/report.json` with its evidence hash.

The eight registry entries are mixed deterministic services, templates and provider adapters, not eight clinically validated autonomous models. The reported percentage is **selected software-contract executions passing / selected executions**. It is not diagnostic accuracy, calibration, live model quality, speech accuracy or independent reliability. Shared contracts appear under more than one role; those totals must not be added as independent experiments. SQLite/PostgreSQL variants do not count as distinct scenarios. Skipped, missing or failed required contracts produce `review_required`, even if other checks pass.

| Registry role | Evidence focus | Executed scenarios / contract checks |
| --- | --- | --- |
| A1 Capture auditor | Insufficient history, poor/interrupted captures, mixed protocol/mode, duplicate time; abstention without numerical results | 6 / 6 |
| A2 Context checker | Human verification, unsupported extraction, corrected sources, source-linked drafting and in-flight source changes | 5 / 10 |
| A3 Approved-plan coach | Stale/current plans, explicit confirmation, role restrictions, idempotency and corrected-source holds | 5 / 10 |
| A4 Follow-up coordinator | Urgent holds, hidden drafts, participant consent, expired responses and source-cancelled reminders | 5 / 10 |
| A5 Voice companion | Safety before navigation, negation/stop, provider failure, empty/silent transcription and memory consent races | 5 / 10 |
| A6 Family coordination | Accepted responsibility, revoked grants, recipient changes and explicit follow-up ownership | 5 / 10 |
| A7 Factual report | Known/unknown denominators, recipient projection, stale approval, empty coverage and scheduled/historical records | 5 / 10 |
| A8 Output QA | Invalid model schemas, unsupported facts, source references, exact-fact report checking and in-flight revisions | 14 / 17 |

All listed contract executions passed in the 7 November run (126 tests across the selected files; the role rows intentionally overlap). Transport/provider behavior is mocked or disabled. Minimum scenario coverage is a software gate, not proof that a production agent is safe. Manual reviewer roles and recommendations are included per entry; human decisions remain required for clinical drafts. Future evaluation still needs approved real-world data provenance, reference labels, clinical adjudication, device/audio cohorts, Arabic/English evaluation and subgroup/error analysis. No such results are invented here.
