# Subgroup analysis

Run on 2026-11-16 by `backend/eval/run_subgroup_analysis.py` (code: `backend/app/subgroups.py`), seed 20261116.
Each rate has a 95% Wilson interval; the largest gap between groups has a 95% Newcombe interval and is marked
**clear** when that interval excludes 0. Groups below the minimum size are shown but never compared.

## What this covers, and what it does not

There is **no pilot data yet**, so nothing here is about real people. It checks whether the fixed rules behave
differently for kinds of people and situations we can simulate or write sentences for. Age, sex, education and first
language can only be analysed once a pilot collects them; the code is ready (`--db`, `subgroups.quality_by`). The
"About you" screen already asks education and first language, optionally, for exactly this purpose.

## 1. Change engine on simulated people (2000 per group; 2 practice + 7 weekly sessions)

| Outcome | Group | n | Rate (95% CI) | Largest gap (95% CI) |
|---|---|---|---|---|
| false alarm (stable person flagged) | steady (day-to-day SD 15–25 ms) | 2000 | 5.1% (4.3%–6.2%) | +1.0 points (-0.3 to +2.3) |
|  | variable (day-to-day SD 30–40 ms) | 2000 | 4.2% (3.4%–5.1%) |  |
| a real 60 ms slowing flagged | steady (day-to-day SD 15–25 ms) | 2000 | 51.7% (49.6%–53.9%) | +29.4 points (+26.6 to +32.3) **clear** |
|  | variable (day-to-day SD 30–40 ms) | 2000 | 22.3% (20.5%–24.2%) |  |
| stable person flagged slower | changed to a slower device (+30 ms) at session 6 | 2000 | 11.7% (10.3%–13.1%) | +9.8 points (+8.3 to +11.4) **clear** |
|  | same device throughout | 2000 | 1.8% (1.3%–2.5%) |  |
| engine abstained (too few records) | irregular (6 of 9 usable, 4 after practice) | 2000 | 100.0% (99.8%–100.0%) | +100.0 points (+99.7 to +100.0) **clear** |
|  | regular (all 9 sessions usable) | 2000 | 0.0% (0.0%–0.2%) |  |

What this tells a clinician:
- **Equal false alarms, unequal detection.** The engine works in each person's own spread, so false alarms are about
  the same for steady and variable people (5.1% and 4.2%). But the same real
  60 ms slowing is flagged for 51.7% of steady people and only 22.3% of
  variable people. People whose results vary a lot day to day (fatigue, tremor, distraction, an unfamiliar device)
  need a larger change before it shows. "Within usual variation" means less for them.
- **A device change looks like a slowing.** Stable people who switch to a slower device part-way are flagged slower
  11.7% of the time, against 1.8% on one device. Each session records its
  device, and the clinician sees it; the engine does not yet compare only like with like. Pilot task: measure device
  offsets, then decide whether to split by device.
- **Irregular use means no answer, not a wrong one.** With 6 of 9 sessions usable (4 after the practice sessions, 5 are needed) the engine abstains
  100.0% of the time instead of guessing.

## 2. Emergency-phrase rule, by language

| Outcome | Group | n | Rate (95% CI) | Largest gap (95% CI) |
|---|---|---|---|---|
| emergency sentence opened help (tuning set) | Arabic | 50 | 100.0% (92.9%–100.0%) | +0.0 points (-7.1 to +7.1) |
|  | English | 82 | 100.0% (95.5%–100.0%) |  |
| ordinary sentence left alone (tuning set) | Arabic | 31 | 100.0% (89.0%–100.0%) | +1.6 points (-9.5 to +8.3) |
|  | English | 64 | 98.4% (91.7%–99.7%) |  |

These are the sentences the rule was tuned on, so both languages are near 100% by construction. The held-out rounds
(docs/EMERGENCY_BENCHMARK.md) are too small to split by language. Arabic dialect coverage is the known weak point.

## 3. Companion text understanding, by language

| Outcome | Group | n | Rate (95% CI) | Largest gap (95% CI) |
|---|---|---|---|---|
| request understood (dev set) | Arabic | 13 | 100.0% (77.2%–100.0%) | +0.0 points (-22.8 to +22.8) |
|  | English | 38 | 100.0% (90.8%–100.0%) |  |
| request understood (final set) | Arabic | 13 | 92.3% (66.7%–98.6%) | +2.3 points (-11.5 to +28.2) |
|  | English | 37 | 94.6% (82.3%–98.5%) |  |

Arabic has fewer sentences, so its interval is wide; a gap of this size cannot be ruled in or out.

## Next steps

In the pilot: collect age band, sex, education, first language, device and session language (all optional), report
every outcome above by each, with a minimum group size of 20, and have a statistician review any clear gap
before anything is changed.
