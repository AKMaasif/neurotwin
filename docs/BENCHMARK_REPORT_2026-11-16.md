# Benchmark report — 16 November 2026

One place for every benchmark run before submission. Each line says what was tested, the result, and where the full
output lives. All data is synthetic or developer-written. **Nothing here is a clinical accuracy, sensitivity or
specificity figure, and no clinical benefit is claimed.**

## Summary

| # | Benchmark | Result | What it means | Full report |
|---|---|---|---|---|
| 1 | Backend regression suite | 658 passed, 13 skipped (optional imaging libraries), 0 failed | Every endpoint, rule and guard has a test | `backend/tests` |
| 2 | Agent guard-rail scenarios | 71/71 | Invented numbers, unsupported claims, diagnosis requests and provider failures are all refused or handled | [AGENT_EVAL_REPORT.md](AGENT_EVAL_REPORT.md) |
| 3 | Fixed readiness scenarios | 102/102 | End-to-end demo flows behave as specified | [QA_BENCHMARK_REPORT_2026-11-15.md](QA_BENCHMARK_REPORT_2026-11-15.md) |
| 4 | Assistant understanding (English + Arabic) | Tuning set 51/51; final set 47/50 = 94%, **0 unsafe actions** | 3 known misses: "قمت بالمشي", "I want to prepare for my visit" (no action), "send a message to my daughter" (opened Messages instead of asking) | `backend/eval/run_companion_eval.py` |
| 5 | Emergency-phrase rule (English + Arabic) | Tuning set 112/112 caught, 77/80 ordinary left alone. Held-out rounds: 85%, 90%, **40%, 0%** | A word list catches the wording it knows and generalises poorly to new kinds of situation; the always-visible help button is the main route | [EMERGENCY_BENCHMARK.md](EMERGENCY_BENCHMARK.md) |
| 6 | Change engine on 16,000 simulated people | False alarms on stable people 4.1% (95% CI 3.3–5.1%); flags 59% of 3-SD and 81% of 4-SD slowings; abstains 100% when records are too few | Behaves as designed; cautious; practice effect hides part of a real slowing (59% → 31%) | [CHANGE_ENGINE_BENCHMARK.md](CHANGE_ENGINE_BENCHMARK.md) |
| 7 | Server response time (in process) | Median 6–19 ms for reads, about 40 ms for the assistant; 95th percentile under 65 ms | Fast enough for an interactive demo; network and load not included | [LATENCY_BENCHMARK.md](LATENCY_BENCHMARK.md) |

## The two findings a reviewer should not miss

**1. Emergency words: do not read the tuning figure as "100% detection".** Each held-out round was written after the
last fix and run once. Rounds 1 and 2 used similar wording and scored 85% and 90%. Rounds 3 and 4 deliberately used
new kinds of situation (collapse, stroke signs, overdose, seizure, self-harm, emergency numbers, Gulf dialect) and
scored 40% and 0%. Every miss was then added to the rule and recorded. The honest conclusion is that a word list is a
fast first line and must not be the only route to help. The personal app therefore shows an urgent-help button on
every screen, which needs no words at all. A pilot needs real wording from older adults in both languages and a
clinically reviewed list of situations.

**2. "Within usual variation" is not reassurance.** With 3 baseline and 2 recent records, the engine reliably flags only
large changes (3–4 times the person's own day-to-day spread). It keeps false alarms near the designed 5%, but a
smaller real change will often read "within". A practice gain of 40 ms makes 7.7% of stable people look faster and
halves the chance of flagging a real 3-SD slowing. The engine does not yet model practice; that is a stated limitation
and a pilot task (test–retest study).

## How to reproduce

From `backend/`:

```bash
python -m pytest -q
python eval/run_emergency_benchmark.py
python eval/run_change_benchmark.py
python eval/run_latency_benchmark.py
python eval/run_companion_eval.py final
```

Add `--write` to the three benchmark scripts to regenerate their reports. The change and emergency benchmarks also
run as tests (`tests/test_change_benchmark.py`, `tests/test_emergency_benchmark.py`), so CI fails if they regress.
